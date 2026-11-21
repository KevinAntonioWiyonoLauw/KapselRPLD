const puppeteer = require("puppeteer-core");
const path = require("path");
const fs = require("fs");

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const OUT = path.resolve(__dirname, "..", "..", "docs", "screenshots");
const URL = process.env.DASH_URL || "http://localhost:3000";

fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: "new",
    args: ["--no-sandbox", "--disable-gpu", "--window-size=1440,1000"],
  });

  const page = await browser.newPage();
  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push("pageerror: " + e.message));

  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });
  console.log("goto", URL);
  await page.goto(URL, { waitUntil: "networkidle2", timeout: 60000 });
  await page.waitForFunction(() => document.body.innerText.includes("Total pekerjaan"), { timeout: 30000 });
  await sleep(2500);

  const tabs = ["overview", "connections", "jobs", "conflicts", "mappings", "integrations"];
  for (let i = 0; i < tabs.length; i++) {
    const handles = await page.$$('[role="tab"]');
    if (handles[i]) await handles[i].click();
    await sleep(1800);
    const file = path.join(OUT, `dashboard-${tabs[i]}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log("saved", file);
  }

  // Mobile pass (R-03): check horizontal overflow and capture overview.
  const mobile = await browser.newPage();
  await mobile.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true });
  await mobile.goto(URL, { waitUntil: "networkidle2", timeout: 60000 });
  await mobile.waitForFunction(() => document.body.innerText.includes("Total pekerjaan"), { timeout: 30000 });
  await sleep(2500);
  const overflow = await mobile.evaluate(() => ({
    scrollW: document.documentElement.scrollWidth,
    clientW: document.documentElement.clientWidth,
  }));
  console.log("MOBILE overflow check:", JSON.stringify(overflow), overflow.scrollW > overflow.clientW + 1 ? "OVERFLOW!" : "OK");
  await mobile.screenshot({ path: path.join(OUT, "dashboard-mobile-overview.png"), fullPage: true });
  console.log("saved mobile overview");

  if (consoleErrors.length) {
    console.log("CONSOLE ERRORS:\n" + consoleErrors.join("\n"));
  } else {
    console.log("CONSOLE ERRORS: none");
  }

  await browser.close();
  console.log("DONE");
})().catch((e) => {
  console.error("ERROR", e);
  process.exit(1);
});
