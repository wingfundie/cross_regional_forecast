// Offline Playwright QA for Flagship A (Constraint Pressure Atlas v2) + 3 Compressed Event Atlases v2
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {createRequire} = require('node:module');

const modules = process.argv[2] || path.join(process.env.USERPROFILE, '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium} = createRequire(path.join(modules, '_qa_resolver.cjs'))('playwright');
const root = __dirname;
const qa = path.join(root, 'qa');
fs.mkdirSync(qa, {recursive: true});
const assert = (v, m) => { if (!v) throw new Error(m); };

(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1100}});
  page.setDefaultTimeout(120000);
  const errors = [], requests = [];
  page.on('pageerror', e => { console.error('[PAGEERROR]', e.message); errors.push(e.message); });
  page.on('console', m => { if (m.type() === 'error') { console.error('[CONSOLE]', m.text()); errors.push(m.text()); } });
  await page.route(/^https?:/, r => { requests.push(r.request().url()); r.abort(); });

  await page.goto(pathToFileURL(path.join(root, 'Constraint_Pressure_Atlas_v2.html')).href, {waitUntil: 'load'});
  await page.waitForSelector('html.ready', {timeout: 60000});
  await page.addStyleTag({content: 'html{scroll-behavior:auto!important}*{animation:none!important;transition:none!important}'});

  const integrity = await page.evaluate(() => {
    const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
    const missing = [...document.querySelectorAll('a[href^="#"]')].map(e => e.getAttribute('href').slice(1)).filter(id => id && !document.getElementById(id));
    let maxConsecFigs = 0;
    document.querySelectorAll('.chapter-content').forEach(cc => {
      let run = 0;
      for (const ch of cc.children) {
        if (ch.tagName === 'FIGURE') { run += 1; maxConsecFigs = Math.max(maxConsecFigs, run); } else { run = 0; }
      }
    });
    const text = document.querySelector('.research-body').innerText;
    return {
      duplicates: [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))],
      missing,
      charts: document.querySelectorAll('.js-plotly-plot').length,
      diagrams: document.querySelectorAll('.mechanism-panel').length,
      directories: document.querySelectorAll('.dir-widget tbody tr').length,
      katex: document.querySelectorAll('.research-body .katex').length,
      katexErrors: document.querySelectorAll('.katex-error').length,
      rawDisplayMath: (text.match(/\$\$/g) || []).length,
      rawPlaceholders: (document.body.innerHTML.match(/\{\{[a-zA-Z0-9_:]+\}\}/g) || []).length,
      maxConsecFigs,
      overflow: document.documentElement.scrollWidth > innerWidth,
    };
  });

  assert(!integrity.duplicates.length, 'duplicate ids ' + integrity.duplicates);
  assert(!integrity.missing.length, 'missing anchors ' + integrity.missing);
  assert(integrity.charts === 12, 'expected 12 charts, got ' + integrity.charts);
  assert(integrity.diagrams === 3, 'expected 3 diagrams, got ' + integrity.diagrams);
  assert(integrity.directories >= 20, 'directory rows ' + integrity.directories);
  assert(integrity.katex >= 15 && !integrity.katexErrors, 'katex ' + integrity.katex + ' errors ' + integrity.katexErrors);
  assert(!integrity.rawDisplayMath, 'raw $$');
  assert(!integrity.rawPlaceholders, 'unfilled placeholders');
  assert(integrity.maxConsecFigs <= 2, 'consecutive figures ' + integrity.maxConsecFigs);
  assert(!integrity.overflow, 'desktop overflow');

  const shot = async (sel, file) => {
    const loc = page.locator(sel).first();
    await loc.evaluate(el => el.scrollIntoView({block: 'start'}));
    await page.waitForTimeout(250);
    await page.screenshot({path: path.join(qa, file)});
  };
  await page.screenshot({path: path.join(qa, 'desktop_hero.png')});
  await shot('#fig-a1', 'desktop_parity.png');
  await shot('#fig-a6', 'desktop_contractions.png');
  await shot('#fig-a9', 'desktop_econ_duids.png');

  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(400);
  const mob = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth}));
  assert(mob.scroll <= mob.width, 'mobile overflow ' + JSON.stringify(mob));
  await shot('#top', 'mobile_hero.png');

  // Also smoke-test all 3 standalone compressed Event Atlases v2 (verify gzip DecompressionStream renders!)
  const atlasChecks = [];
  await page.setViewportSize({width: 1440, height: 1000});
  for (const slug of ['vni', 'qni', 'vsa']) {
    const fp = path.join(root, '..', 'event_atlases_v2', slug + '_event_atlas_v2.html');
    await page.goto(pathToFileURL(fp).href, {waitUntil: 'load'});
    await page.waitForSelector('html.ready', {timeout: 30000});
    const info = await page.evaluate(() => ({
      options: document.querySelectorAll('#event-select option').length,
      plots: document.querySelectorAll('.js-plotly-plot').length,
      overflow: document.documentElement.scrollWidth > innerWidth,
    }));
    assert(info.options >= 70 && info.plots >= 4 && !info.overflow, slug + ' atlas check failed: ' + JSON.stringify(info));
    atlasChecks.push({slug, ...info});
  }

  assert(!errors.length, 'browser errors: ' + errors.join('; '));
  assert(!requests.length, 'external requests: ' + requests.join('; '));
  const res = {passed: true, integrity, mobile: mob, atlasChecks};
  fs.writeFileSync(path.join(qa, 'browser_checks.json'), JSON.stringify(res, null, 2));
  console.log(JSON.stringify(res, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
