// Browser QA for the offline v2 report. Usage: node qa_report.cjs [PATH_TO_NODE_MODULES_WITH_PLAYWRIGHT]
const fs=require('node:fs');const path=require('node:path');const {pathToFileURL}=require('node:url');const {createRequire}=require('node:module');
const modules=process.argv[2]||path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
const {chromium}=createRequire(path.join(modules,'_qa_resolver.cjs'))('playwright');
const root=__dirname,qa=path.join(root,'qa');fs.mkdirSync(qa,{recursive:true});
const assert=(v,m)=>{if(!v)throw new Error(m);};
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(120000);
 const errors=[],requests=[];page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
 await page.route(/^https?:/,r=>{requests.push(r.request().url());r.abort();});
 await page.goto(pathToFileURL(path.join(root,'Interregional_Valuation_Research_v2.html')).href,{waitUntil:'load'});
 await page.waitForSelector('html.ready',{timeout:60000});
 await page.addStyleTag({content:'html{scroll-behavior:auto!important}*{animation:none!important;transition:none!important}'});
 const shot=async(sel,file)=>{await page.locator(sel).evaluate(el=>el.scrollIntoView({block:'start'}));await page.waitForTimeout(300);await page.screenshot({path:path.join(qa,file)});};
 const integrity=await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);const missing=[...document.querySelectorAll('a[href^="#"]')].map(e=>e.getAttribute('href').slice(1)).filter(id=>id&&!document.getElementById(id));
  const text=document.querySelector('.research-body').innerText;
  return {duplicates:[...new Set(ids.filter((id,i)=>ids.indexOf(id)!==i))],missing,charts:document.querySelectorAll('.js-plotly-plot').length,newCharts:NEWCHARTS.length,
   renderedNew:NEWCHARTS.filter(c=>document.getElementById(c.id)&&document.getElementById(c.id).classList.contains('js-plotly-plot')).length,
   diagrams:document.querySelectorAll('.mechanism-panel').length,katex:document.querySelectorAll('.research-body .katex').length,katexErrors:document.querySelectorAll('.katex-error').length,
   rawDisplayMath:(text.match(/\$\$/g)||[]).length,rawPlaceholders:(document.body.innerHTML.match(/\{\{[a-zA-Z0-9_]+\}\}/g)||[]).length,
   downloads:document.querySelectorAll('a[download]').length,chapters:document.querySelectorAll('details.chapter').length,overflow:document.documentElement.scrollWidth>innerWidth};});
 assert(!integrity.duplicates.length,'duplicate ids '+integrity.duplicates);assert(!integrity.missing.length,'missing anchors '+integrity.missing);
 assert(integrity.renderedNew===integrity.newCharts&&integrity.newCharts===27,'new charts rendered '+integrity.renderedNew);
 assert(integrity.charts>=36,'total charts '+integrity.charts);assert(integrity.diagrams===5,'diagrams '+integrity.diagrams);
 assert(integrity.katex>=100&&!integrity.katexErrors,'katex '+integrity.katex+' errors '+integrity.katexErrors);assert(!integrity.rawDisplayMath,'raw $$ in text');assert(!integrity.rawPlaceholders,'unfilled placeholders');
 assert(!integrity.overflow,'desktop overflow');
 // window toggle and directions
 const combos=[];for(const w of ['full','v1']){await page.selectOption('#window',w);const qs=await page.evaluate(()=>[...document.querySelectorAll('#quarter option')].map(o=>o.value));
  for(let d=0;d<8;d++){await page.selectOption('#direction',String(d));for(const q of qs){await page.selectOption('#quarter',q);const ok=await page.evaluate(()=>{const r=route(),v=D().spreads.find(x=>x.complete&&x.direction===r.base&&x.quarter===$('quarter').value);return v?$('totalValue').textContent===money(v.spread*r.sign):$('selectedRoute').textContent.includes('not in this window');});assert(ok,'value mismatch '+w+' '+d+' '+q);combos.push(1);}}}
 await page.selectOption('#window','full');
 const calc=await page.evaluate(()=>({total:$('marketTotal').textContent,energy:$('marketEnergy').textContent,edge:$('marketEdge').textContent,hours:$('impliedHours').textContent,unit:$('unitEdge').textContent,spread:$('spreadHours').textContent}));
 assert(calc.total==='$34.00'&&calc.energy==='$18.00'&&calc.edge==='−$4.00','workbench aligned with worked example '+JSON.stringify(calc));
 const payoff=await page.evaluate(()=>{const t=document.querySelector('#payoffChart').data;return t[0].y.every((v,i)=>Math.abs(v-t[1].y[i]-t[2].y[i])<1e-9);});assert(payoff,'payoff identity');
 await page.screenshot({path:path.join(qa,'desktop_hero.png')});
 for(const [s,f] of [['#v2-auctions','desktop_auctions.png'],['#v2-hedging','desktop_hedging.png'],['#v2-loss','desktop_loss.png'],['#v2-loop','desktop_loop.png'],['#v2-counterprice','desktop_mechanisms.png'],['#v2-valuation','desktop_valuation.png'],['#historicalExplorer','desktop_history.png'],['#chapter-8','desktop_math.png'],['#visualAtlas','desktop_atlas.png']])await shot(s,f);
 await page.setViewportSize({width:390,height:844});await page.waitForTimeout(800);
 const mob=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));assert(mob.scroll<=mob.width,'mobile overflow '+JSON.stringify(mob));
 for(const [s,f] of [['#top','mobile_hero.png'],['#v2-auctions','mobile_auctions.png'],['#chapter-3','mobile_math.png'],['#v2-hedging','mobile_hedging.png']])await shot(s,f);
 await page.setViewportSize({width:1440,height:1100});await page.emulateMedia({media:'print'});await page.pdf({path:path.join(qa,'print_check.pdf'),format:'A4',printBackground:true});
 assert(!errors.length,'browser errors '+errors.join('; '));assert(!requests.length,'external requests '+requests.join('; '));
 const result={passed:true,integrity,combinations:combos.length,calc,mobile:mob,browserErrors:errors,externalRequests:requests};
 fs.writeFileSync(path.join(qa,'browser_checks.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
 await browser.close();process.exit(0);
})().catch(e=>{console.error(e);process.exit(1);});
