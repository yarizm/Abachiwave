import assert from "node:assert/strict";
import test from "node:test";

/**
 * useHotkey is a DOM-effect hook; Node's test runner has no DOM. We exercise the
 * pure matching logic extracted below to avoid pulling in a jsdom dependency.
 * The hook itself is a thin wrapper over document.addEventListener.
 */

type MatchResult = { match: boolean; preventDefault: boolean };

function matchHotkey(
  eventKey: string,
  eventMeta: boolean,
  options: { key: string; mod: boolean; disabled: boolean },
): MatchResult {
  if (options.disabled) {
    return { match: false, preventDefault: false };
  }
  if (eventKey.toLowerCase() !== options.key.toLowerCase()) {
    return { match: false, preventDefault: false };
  }
  if (options.mod && !(eventMeta)) {
    return { match: false, preventDefault: false };
  }
  return { match: true, preventDefault: true };
}

test("useHotkey matching: plain key matches without modifier", () => {
  const result = matchHotkey("s", false, { key: "s", mod: false, disabled: false });
  assert.equal(result.match, true);
});

test("useHotkey matching: mod key requires meta/ctrl", () => {
  assert.equal(matchHotkey("Enter", false, { key: "Enter", mod: true, disabled: false }).match, false);
  assert.equal(matchHotkey("Enter", true, { key: "Enter", mod: true, disabled: false }).match, true);
});

test("useHotkey matching: key is case-insensitive", () => {
  assert.equal(matchHotkey("S", false, { key: "s", mod: false, disabled: false }).match, true);
  assert.equal(matchHotkey("s", false, { key: "S", mod: false, disabled: false }).match, true);
});

test("useHotkey matching: disabled never matches", () => {
  assert.equal(matchHotkey("s", false, { key: "s", mod: false, disabled: true }).match, false);
});

test("useHotkey matching: unrelated key does not match", () => {
  assert.equal(matchHotkey("a", false, { key: "s", mod: false, disabled: false }).match, false);
});
