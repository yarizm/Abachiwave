import { test as baseTest } from "@playwright/test";

/**
 * The project's Playwright entry point. Specs import `test` and `expect` from
 * here rather than from `@playwright/test` so every case carries the shared
 * guards below.
 *
 * The re-exports below are named rather than a `export *`: a star export also
 * carries Playwright's own `test`, and which of the two a spec ends up with
 * then depends on module-format details. A guard that silently stops running
 * is worse than no guard, so leave no room for it.
 */

export { expect, request } from "@playwright/test";
export type { Locator, Page } from "@playwright/test";

/**
 * `scrollWidth` and `clientWidth` are rounded to integers, so a sub-pixel layout
 * can report a 1px difference with nothing actually wrong. Anything wider is a
 * real overflow.
 */
const OVERFLOW_TOLERANCE_PX = 1;

/** Enough offenders to see the pattern, few enough to read in a CI log. */
const MAX_REPORTED_OFFENDERS = 5;

type OverflowReport = {
  documentWidth: number;
  viewportWidth: number;
  offenders: string[];
};

/**
 * Reports elements that push the document wider than the viewport.
 *
 * Serialized and run inside the page, so it must stay self-contained: anything
 * it references from module scope is undefined by the time it executes.
 *
 * Only the deepest offenders are reported. An element that overflows drags
 * every ancestor with it, so listing the ancestors says nothing about the
 * cause. Elements inside a scroll container are skipped for the same reason:
 * that container absorbs them, so they are not why the document grew.
 */
function collectHorizontalOverflow([tolerance, limit]: [number, number]): OverflowReport | null {
  const root = document.documentElement;
  const overflow = root.scrollWidth - root.clientWidth;
  if (overflow <= tolerance) {
    return null;
  }

  const edge = root.clientWidth + tolerance;
  const overflowing = new Set<Element>();
  for (const element of document.body.querySelectorAll("*")) {
    const rect = element.getBoundingClientRect();
    if (rect.width === 0 || rect.right + window.scrollX <= edge) {
      continue;
    }
    let clipped = false;
    for (
      let parent = element.parentElement;
      parent && parent !== root;
      parent = parent.parentElement
    ) {
      if (getComputedStyle(parent).overflowX !== "visible") {
        clipped = true;
        break;
      }
    }
    if (!clipped) {
      overflowing.add(element);
    }
  }

  // The deepest offender is often an anonymous <p> or <span>; the rule that set
  // the floor lives on an ancestor. Report a short path so the message names
  // something a stylesheet search can find.
  const name = (element: Element): string =>
    element.tagName.toLowerCase() +
    Array.from(element.classList)
      .map((className) => "." + className)
      .join("");

  const describe = (element: Element): string => {
    const path = [name(element)];
    for (
      let parent = element.parentElement;
      parent && parent !== document.body && path.length < 3;
      parent = parent.parentElement
    ) {
      path.unshift(name(parent));
    }
    const rect = element.getBoundingClientRect();
    return `${path.join(" > ")} (${Math.round(rect.width)}px wide, right edge ${Math.round(rect.right + window.scrollX)}px)`;
  };

  const deepest = Array.from(overflowing).filter(
    (element) => !Array.from(element.children).some((child) => overflowing.has(child)),
  );
  return {
    documentWidth: root.scrollWidth,
    viewportWidth: root.clientWidth,
    offenders: (deepest.length > 0 ? deepest : Array.from(overflowing))
      .slice(0, limit)
      .map(describe),
  };
}

export const test = baseTest.extend<{ horizontalOverflowGuard: void }>({
  /**
   * Fails any test that leaves the document scrollable sideways.
   *
   * A page wider than its viewport rarely fails an assertion directly. It shows
   * up as a click that never lands, because the button's hit point sits under a
   * neighbour that the stretched layout moved on top of it — a 60s timeout that
   * names the wrong element and says nothing about width. This turns that into
   * a named failure at the test that caused it.
   */
  horizontalOverflowGuard: [
    async ({ page }, use, testInfo) => {
      await use();

      // A failing test has its own story; a second error here would bury it.
      if (testInfo.status !== testInfo.expectedStatus || page.isClosed()) {
        return;
      }

      let report: OverflowReport | null = null;
      try {
        report = await page.evaluate(collectHorizontalOverflow, [
          OVERFLOW_TOLERANCE_PX,
          MAX_REPORTED_OFFENDERS,
        ] as [number, number]);
      } catch {
        // The page navigated or closed as the test ended, so there is no layout
        // left to measure. Skipping beats a teardown flake: every other case
        // still checks, and a real regression shows up in all of them.
        return;
      }

      if (report === null) {
        return;
      }
      throw new Error(
        [
          `The document is ${report.documentWidth}px wide in a ${report.viewportWidth}px viewport.`,
          "Widest elements escaping the viewport:",
          ...report.offenders.map((offender) => `  - ${offender}`),
        ].join("\n"),
      );
    },
    { auto: true },
  ],
});
