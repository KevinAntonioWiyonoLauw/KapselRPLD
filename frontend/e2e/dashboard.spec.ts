import { test, expect, Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

// Dashboard e2e + accessibility tests (#19), updated for the login form.
// Requires the stack running: backend (mock) + dashboard at BASE_URL.
// Demo account: admin / admin123 (from .env).

async function login(page: Page) {
  await page.goto("/");
  await page.locator("#username").fill("admin");
  await page.locator("#password").fill("admin123");
  await page.getByRole("button", { name: "Masuk" }).click();
}

async function waitLoaded(page: Page) {
  await login(page);
  await expect(page.getByText("Total pekerjaan")).toBeVisible({ timeout: 30_000 });
}

test("login form authenticates and reveals the dashboard", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Masuk ke Console" })).toBeVisible();
  // Wrong password is rejected.
  await page.locator("#username").fill("admin");
  await page.locator("#password").fill("salah-sekali");
  await page.getByRole("button", { name: "Masuk" }).click();
  await expect(page.getByRole("alert")).toBeVisible();
  // Correct credentials log in.
  await page.locator("#password").fill("admin123");
  await page.getByRole("button", { name: "Masuk" }).click();
  await expect(page.getByText("Total pekerjaan")).toBeVisible({ timeout: 30_000 });
});

test("dashboard loads with KPI cards and 6 tabs", async ({ page }) => {
  await waitLoaded(page);
  await expect(page.getByText("Tingkat sukses")).toBeVisible();
  for (const t of ["Ringkasan", "Konektivitas", "Pekerjaan", "Konflik", "Pemetaan", "Integrasi"]) {
    await expect(page.getByRole("tab", { name: t })).toBeVisible();
  }
});

test("tabs navigate and jobs tab shows the jobs panel", async ({ page }) => {
  await waitLoaded(page);
  await page.getByRole("tab", { name: "Pekerjaan" }).click();
  // The jobs panel header is always present after navigating to the tab,
  // regardless of how many jobs exist (fresh CI DB may have zero).
  await expect(page.getByText("Riwayat pekerjaan sinkronisasi")).toBeVisible();
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
  await expect(page.locator('[aria-label^="Peran saat ini"]')).toBeVisible();
});

test("logout returns to the login form", async ({ page }) => {
  await waitLoaded(page);
  await page.getByRole("button", { name: "Keluar" }).click();
  await expect(page.getByRole("heading", { name: "Masuk ke Console" })).toBeVisible();
});

test("login page has no serious accessibility violations", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Masuk ke Console" })).toBeVisible();
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious, "Pelanggaran a11y serius (login): " + JSON.stringify(serious.map((v) => v.id))).toEqual([]);
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
