// Browser QA for the offline v3 report. Usage: node qa_report.cjs [PATH_TO_NODE_MODULES_WITH_PLAYWRIGHT]
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
  page.on('pageerror', e => { console.error('[PAGEERROR]', e.stack || e.message); errors.push(e.message); });
  page.on('console', m => { if (m.type() === 'error') { console.error('[CONSOLE]', m.text()); errors.push(m.text()); } });
  await page.route(/^https?:/, r => { requests.push(r.request().url()); r.abort(); });
  await page.goto(pathToFileURL(path.join(root, 'Interregional_Valuation_Research_v3.html')).href, {waitUntil: 'load'});
  await page.waitForSelector('html.ready', {timeout: 60000});
  await page.addStyleTag({content: 'html{scroll-behavior:auto!important}*{animation:none!important;transition:none!important}'});

  const shot = async (sel, file) => {
    const loc = page.locator(sel).first();
    await loc.evaluate(el => el.scrollIntoView({block: 'start'}));
    await page.waitForTimeout(300);
    await page.screenshot({path: path.join(qa, file)});
  };

  const integrity = await page.evaluate(() => {
    const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
    const missing = [...document.querySelectorAll('a[href^="#"]')].map(e => e.getAttribute('href').slice(1)).filter(id => id && !document.getElementById(id));
    const text = document.querySelector('.research-body').innerText;
    // Check no 3+ consecutive bare <figure> elements without prose between them
    let maxConsecFigs = 0;
    document.querySelectorAll('.chapter-content').forEach(cc => {
      let run = 0;
      for (const ch of cc.children) {
        if (ch.tagName === 'FIGURE') { run += 1; maxConsecFigs = Math.max(maxConsecFigs, run); }
        else { run = 0; }
      }
    });
    // Check zero snake_case rule labels on Exhibit N23
    const n23 = document.getElementById('n23');
    const n23Labels = n23 && n23.data ? n23.data.flatMap(t => (t.y || []).map(String)) : [];
    const snakeLabels = n23Labels.filter(s => /^[a-z0-9]+_[a-z0-9_]+$/.test(s));
    return {
      duplicates: [...new Set(ids.filter((id, i) => ids.indexOf(id) !== i))],
      missing,
      charts: document.querySelectorAll('.js-plotly-plot').length,
      newCharts: NEWCHARTS.length,
      renderedNew: NEWCHARTS.filter(c => document.getElementById(c.id) && document.getElementById(c.id).classList.contains('js-plotly-plot')).length,
      diagrams: document.querySelectorAll('.mechanism-panel').length,
      callouts: document.querySelectorAll('.vb-callout').length,
      katex: document.querySelectorAll('.research-body .katex').length,
      katexErrors: document.querySelectorAll('.katex-error').length,
      rawDisplayMath: (text.match(/\$\$/g) || []).length,
      rawPlaceholders: (document.body.innerHTML.match(/\{\{[a-zA-Z0-9_:]+\}\}/g) || []).length,
      downloads: document.querySelectorAll('a[download]').length,
      chapters: document.querySelectorAll('details.chapter').length,
      maxConsecFigs,
      snakeLabels,
      defaultDirection: document.getElementById('selectedRoute') ? document.getElementById('selectedRoute').textContent : '',
      overflow: document.documentElement.scrollWidth > innerWidth,
    };
  });

  assert(!integrity.duplicates.length, 'duplicate ids ' + integrity.duplicates);
  assert(!integrity.missing.length, 'missing anchors ' + integrity.missing);
  assert(integrity.renderedNew === integrity.newCharts && integrity.newCharts >= 25, 'inline charts rendered ' + integrity.renderedNew);
  assert(integrity.diagrams === 5, 'diagrams ' + integrity.diagrams);
  assert(integrity.callouts >= 8, 'callouts ' + integrity.callouts);
  assert(integrity.katex >= 100 && !integrity.katexErrors, 'katex ' + integrity.katex + ' errors ' + integrity.katexErrors);
  assert(!integrity.rawDisplayMath, 'raw $$ in text');
  assert(!integrity.rawPlaceholders, 'unfilled placeholders');
  assert(integrity.maxConsecFigs <= 2, '3+ consecutive bare figures: ' + integrity.maxConsecFigs);
  assert(!integrity.snakeLabels.length, 'snake_case chart labels: ' + integrity.snakeLabels);
  assert(integrity.defaultDirection.includes('VIC → NSW'), 'default route not VIC -> NSW: ' + integrity.defaultDirection);
  assert(!integrity.overflow, 'desktop overflow');

  const calc = await page.evaluate(() => ({
    total: $('marketTotal').textContent,
    energy: $('marketEnergy').textContent,
    edge: $('marketEdge').textContent,
    hours: $('impliedHours').textContent,
    unit: $('unitEdge').textContent,
  }));
  assert(calc.total === '$34.00' && calc.energy === '$18.00' && calc.edge === '−$4.00', 'workbench mismatch ' + JSON.stringify(calc));

  await page.screenshot({path: path.join(qa, 'desktop_hero.png')});
  for (const [s, f] of [
    ['#fig-v1', 'desktop_sra_decomp.png'],
    ['#fig-v2', 'desktop_loop_waterfall.png'],
    ['#historicalExplorer', 'desktop_explorer.png'],
    ['#fig-n4', 'desktop_auctions.png'],
    ['#fig-n12', 'desktop_hedging.png'],
    ['#valuationLab', 'desktop_workbench.png'],
    ['#chapter-10', 'desktop_implementation.png'],
  ]) await shot(s, f);

  await page.setViewportSize({width: 390, height: 844});
  await page.waitForTimeout(600);
  const mob = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth}));
  assert(mob.scroll <= mob.width, 'mobile overflow ' + JSON.stringify(mob));
  for (const [s, f] of [['#top', 'mobile_hero.png'], ['#fig-v1', 'mobile_sra_decomp.png'], ['#chapter-7', 'mobile_auctions.png']]) {
    await shot(s, f);
  }

  assert(!errors.length, 'browser errors ' + errors.join('; '));
  assert(!requests.length, 'external requests ' + requests.join('; '));

  const result = {passed: true, integrity, calc, mobile: mob, browserErrors: errors, externalRequests: requests};
  fs.writeFileSync(path.join(qa, 'browser_checks.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
  await browser.close();
  process.exit(0);
})().catch(e => { console.error(e); process.exit(1); });
