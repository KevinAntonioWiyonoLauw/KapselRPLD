import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Dashboard e2e + accessibility tests (#19).
// Requires the stack running: backend (mock) + dashboard at BASE_URL.

async function waitLoaded(page: Page) {
  await page.goto("/");
  await expect(page.getByText("Total pekerjaan")).toBeVisible({ timeout: 30_000 });
}

test("dashboard loads with KPI cards and 6 tabs", async ({ page }) => {
  await waitLoaded(page);
  await expect(page.getByText("Tingkat sukses")).toBeVisible();
  for (const t of ["Ringkasan", "Konektivitas", "Pekerjaan", "Konflik", "Pemetaan", "Integrasi"]) {
    await expect(page.getByRole("tab", { name: t })).toBeVisible();
  }
});

test("tabs navigate and jobs tab shows pagination", async ({ page }) => {
  await waitLoaded(page);
  await page.getByRole("tab", { name: "Pekerjaan" }).click();
  // Fresh CI DB may have zero jobs (empty state) -> pagination may be absent.
  // Accept either the pagination range or the explicit empty state.
  await expect(
    page.getByText(/Menampilkan\s+\d+[–-]\d+\s+dari\s+\d+\s+pekerjaan/)
      .or(page.getByText("Belum ada data"))
  ).toBeVisible();
});

test("dark mode toggle applies and persists across reload", async ({ page }) => {
  await waitLoaded(page);
  // start from a known light state
  await page.evaluate(() => localStorage.setItem("theme", "light"));
  await page.reload();
  await expect(page.getByText("Total pekerjaan")).toBeVisible();
  const isDark = () => page.evaluate(() => document.documentElement.classList.contains("dark"));
  expect(await isDark()).toBe(false);
  await page.getByRole("button", { name: /mode gelap/i }).click();
  expect(await isDark()).toBe(true);
  expect(await page.evaluate(() => localStorage.getItem("theme"))).toBe("dark");
  await page.reload();
  await expect(page.getByText("Total pekerjaan")).toBeVisible();
  expect(await isDark()).toBe(true); // persisted
});

test("login resolves a role and shows the badge", async ({ page }) => {
  await waitLoaded(page);
  // default token is the dev admin token -> role badge appears
  await expect(page.locator('[aria-label^="Peran saat ini"]')).toBeVisible();
});

test("dashboard has no serious accessibility violations", async ({ page }) => {
  await waitLoaded(page);
  // Ensure data has finished loading before scanning (avoid transient states).
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical"
  );
  expect(
    serious,
    "Pelanggaran a11y serius: " + JSON.stringify(serious.map((v) => v.id))
  ).toEqual([]);
});
