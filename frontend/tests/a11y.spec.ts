import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockApi } from "./mockApi";

async function assertNoSerious(
  page: import("@playwright/test").Page,
  label: string,
  opts: { excludeLeaflet?: boolean } = {},
) {
  let builder = new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]);
  // Nearby schools share map coordinates; pin spacing is geographic, not layout. Skip leaflet
  // chrome for target-size while still scanning the list, legend, and pin card.
  if (opts.excludeLeaflet) {
    builder = builder.exclude(".leaflet-marker-icon").exclude(".leaflet-control-zoom");
  }
  const results = await builder.analyze();
  const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(bad, `${label}: ${bad.map((v) => `${v.id} (${v.impact})`).join(", ")}`).toEqual([]);
}

test.describe("accessibility", () => {
  test.beforeEach(async ({ page }) => {
    await mockApi(page);
  });

  test("landing chat has no serious/critical axe violations", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByLabel("Conversation")).toBeVisible();
    await assertNoSerious(page, "landing");
  });

  test("results + evidence + map toggle at 360px", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 740 });
    await page.goto("/");
    await page.getByRole("button", { name: /Middle school in Seattle/i }).click();
    await expect(page.getByText(/quick question|Here’s what I’ll look for|Here are/i).first()).toBeVisible({
      timeout: 15_000,
    });
    // Advance to results fixture
    const skip = page.getByRole("button", { name: /Just show me results|Looks right/i });
    if (await skip.count()) await skip.first().click();
    await expect(page.locator(".card.compact, .results").first()).toBeVisible({ timeout: 15_000 });
    await assertNoSerious(page, "results-360");

    const mapTab = page.getByRole("tab", { name: /Map/i });
    if (await mapTab.count()) {
      await mapTab.click();
      await expect(page.getByRole("region", { name: /Map of the schools/i })).toBeVisible({ timeout: 10_000 });
      await assertNoSerious(page, "map-360", { excludeLeaflet: true });
    }
  });

  test("saved and community views", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Saved/i }).click();
    await expect(page.getByRole("heading", { name: /Saved schools/i })).toBeVisible();
    await assertNoSerious(page, "saved");

    await page.getByRole("button", { name: /Community/i }).click();
    await expect(page.getByRole("search").or(page.getByLabel(/Find a school|school/i)).first()).toBeVisible({
      timeout: 10_000,
    });
    await assertNoSerious(page, "community");
  });

  test("dark mode landing", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /Dark mode/i }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await assertNoSerious(page, "dark-landing");
  });

  test("persona switcher stays behind demo mode", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("button", { name: /Demo controls/i })).toBeVisible();
    await expect(page.getByLabel(/Viewing as/i)).toHaveCount(0);

    await page.getByRole("button", { name: /Demo controls/i }).click();
    await expect(page.getByLabel(/Viewing as/i)).toBeVisible();
    await expect(page.getByLabel(/Viewing as/i)).toHaveValue("parent_a");
    await page.getByLabel(/Viewing as/i).selectOption("school_staff");
    await expect(page.getByLabel(/Viewing as/i)).toHaveValue("school_staff");

    await page.getByRole("button", { name: /Demo controls/i }).click();
    await expect(page.getByLabel(/Viewing as/i)).toHaveCount(0);

    await page.goto("/?demo=1");
    await expect(page.getByLabel(/Viewing as/i)).toBeVisible();
    await assertNoSerious(page, "demo-mode-landing");
  });
});
