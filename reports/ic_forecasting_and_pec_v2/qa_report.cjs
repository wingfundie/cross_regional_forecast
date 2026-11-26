const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");

const modules = process.argv[2] || path.join(process.env.USERPROFILE, ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules");
const { chromium } = createRequire(path.join(modules, "_qa_resolver.cjs"))("playwright");

const HERE = __dirname;
const HTML_FILE = path.join(HERE, "IC_Forecasting_and_PEC_v2.html");
const QA_DIR = path.join(HERE, "qa");
fs.mkdirSync(QA_DIR, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  const errs = [];
  page.on("pageerror", (e) => errs.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errs.push("console: " + m.text()); });

  await page.goto("file:///" + HTML_FILE.replace(/\\/g, "/"), { waitUntil: "load" });
  await page.waitForTimeout(1600);

  const check = await page.evaluate(() => {
    const ids = [...document.querySelectorAll("[id]")].map((e) => e.id);
    const dupes = ids.filter((v, i) => ids.indexOf(v) !== i);
    const missing = [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute("href").slice(1)).filter((h) => h && !document.getElementById(h));
    const charts = [...document.querySelectorAll(".plot")].filter((p) => p.querySelector(".main-svg")).length;
    const diagrams = document.querySelectorAll(".mechanism-panel").length;
    const katex = document.querySelectorAll(".katex").length;
    const katexErr = document.querySelectorAll(".katex-error").length;
    const text = document.body.innerText;
    const rawMath = (text.match(/\$\$[\s\S]*?\$\$/g) || []).length;
    const rawPh = (text.match(/\{\{[a-zA-Z0-9_:]+\}\}/g) || []).length;
    const overflow = document.documentElement.scrollWidth > window.innerWidth + 2;
    let maxConsec = 0, cur = 0;
    const bodyEl = document.querySelector(".report-body") || document.querySelector("article") || document.querySelector("main") || document.body;
    for (const el of bodyEl.children) {
      if (el.matches("figure.inline-exhibit, .mechanism-panel")) { cur++; maxConsec = Math.max(maxConsec, cur); }
      else if (el.matches("p, h2, h3, h4, ul, ol, table, blockquote, .table-wrap, .part-banner, .workbench")) { cur = 0; }
    }
    return { duplicates: dupes, missing, charts, diagrams, katex, katexErrors: katexErr, rawDisplayMath: rawMath, rawPlaceholders: rawPh, maxConsecFigs: maxConsec, overflow };
  });

  await page.screenshot({ path: path.join(QA_DIR, "desktop_hero.png") });
  for (const [sel, fn] of [
    ["#fig-c1", "desktop_pec_configs.png"],
    ["#fig-c3", "desktop_loop_bridge.png"],
    ["#fig-c7", "desktop_longrange.png"],
    ["#fig-c9", "desktop_clustering.png"],
  ]) {
    const loc = page.locator(sel);
    if (await loc.count()) {
      await loc.scrollIntoViewIfNeeded();
      await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(QA_DIR, fn) });
    }
  }

  const mpage = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await mpage.goto("file:///" + HTML_FILE.replace(/\\/g, "/"), { waitUntil: "load" });
  await mpage.waitForTimeout(1000);
  const mcheck = await mpage.evaluate(() => ({ width: window.innerWidth, scroll: document.documentElement.scrollWidth }));
  await mpage.screenshot({ path: path.join(QA_DIR, "mobile_hero.png") });

  await browser.close();
  const ok = errs.length === 0 && check.duplicates.length === 0 && check.missing.length === 0 && check.charts === 10 && check.katexErrors === 0 && check.rawDisplayMath === 0 && check.rawPlaceholders === 0 && !check.overflow && mcheck.scroll <= mcheck.width + 2 && check.maxConsecFigs <= 2;
  console.log(JSON.stringify({ passed: ok, errors: errs, integrity: check, mobile: mcheck }, null, 2));
  if (!ok) process.exit(1);
})();
