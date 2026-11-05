import { test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { mockApi } from "./mockApi";

const out = join(process.cwd(), "..", "docs", "screenshots");

test.describe("pitch screenshots", () => {
  test.beforeEach(async ({ page }) => {
    mkdirSync(out, { recursive: true });
    await mockApi(page);
  });

  async function results(page: import("@playwright/test").Page) {
    await page.goto("/");
    await page.getByRole("button", { name: /Middle school in Seattle/i }).click();
    await page.getByText(/quick question|Here’s what I’ll look for|Here are/i).first().waitFor({ timeout: 15_000 });
    const skip = page.getByRole("button", { name: /Just show me results|Looks right/i });
    if (await skip.count()) await skip.first().click();
    await page.locator(".card.compact").first().waitFor({ timeout: 20_000 });
  }

  test("desktop and mobile, light and dark", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await results(page);
    await page.screenshot({ path: join(out, "desktop-light.png"), fullPage: true });

    await page.getByRole("button", { name: /Dark mode/i }).click();
    await page.screenshot({ path: join(out, "desktop-dark.png"), fullPage: true });

    await page.setViewportSize({ width: 360, height: 740 });
    await page.screenshot({ path: join(out, "mobile-360-dark.png"), fullPage: true });

    await page.getByRole("button", { name: /Light mode/i }).click();
    await page.screenshot({ path: join(out, "mobile-360-light.png"), fullPage: true });

    const mapTab = page.getByRole("tab", { name: /Map/i });
    if (await mapTab.count()) {
      await mapTab.click();
      await page.getByRole("region", { name: /Map of the schools/i }).waitFor({ timeout: 10_000 });
      await page.screenshot({ path: join(out, "mobile-360-map-light.png"), fullPage: true });
    }
  });
});
