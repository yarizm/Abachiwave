import { expect, test } from "@playwright/test";

test.use({ colorScheme: "dark" });

test("hydrates the system dark theme without replacing the app shell", async ({ page }) => {
  const hydrationErrors: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error" && /hydration/i.test(message.text())) {
      hydrationErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    if (/hydration/i.test(error.message)) {
      hydrationErrors.push(error.message);
    }
  });

  await page.context().clearCookies();
  await page.goto("/projects");

  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const themeToggle = page.getByRole("button", { name: "Toggle theme" });
  await expect(themeToggle.locator(".theme-toggle-sun")).toBeVisible();
  await expect(themeToggle.locator(".theme-toggle-moon")).toBeHidden();

  await themeToggle.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(themeToggle.locator(".theme-toggle-sun")).toBeHidden();
  await expect(themeToggle.locator(".theme-toggle-moon")).toBeVisible();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.waitForLoadState("networkidle");

  expect(hydrationErrors).toEqual([]);
});
