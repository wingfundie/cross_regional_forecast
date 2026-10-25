import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright';
const out=process.argv[2];if(!out)throw Error('Pass a QA output directory');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(60000);
const errors=[],checks=[];
page.on('pageerror',e=>errors.push(String(e)));
try{
  const html=path.resolve(out,'../index.html');
  await page.goto(pathToFileURL(html).href,{waitUntil:'load'});
  if(await page.locator('h2').count()!==15)errors.push('Full tutorial section count is not 15');
  for(const [name,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
    await page.setViewportSize({width,height});await page.evaluate(()=>scrollTo(0,0));
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
    checks.push({viewport:name,document_overflow:overflow});if(overflow)errors.push(name+' overflows');
    await page.screenshot({path:path.join(out,'hero_'+name+'.png')});
    await page.locator('pre').first().screenshot({path:path.join(out,'install_'+name+'.png')});
    if(name==='mobile')await page.locator('figure').first().screenshot({path:path.join(out,'figure_mobile.png')});
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('img').first().screenshot({path:path.join(out,'profile_figure.png')});
  const table=page.locator('h3#actual-output-from-the-worked-example + p + .table-wrap');
  await table.screenshot({path:path.join(out,'worked_results.png')});
  await page.getByRole('link',{name:'Input reference',exact:true}).click();
  checks.push({anchor:await page.evaluate(()=>location.hash)});
  const links=await page.locator('a[href]').evaluateAll(elements=>elements.map(a=>a.getAttribute('href')));
  for(const href of links){
    if(href.startsWith('http'))continue;
    if(href.startsWith('#')){
      const found=await page.evaluate(id=>!!document.getElementById(id),decodeURIComponent(href.slice(1)));
      if(!found)errors.push('Missing anchor '+href);
    }else{
      try{await fs.access(path.resolve(path.dirname(html),decodeURIComponent(href)))}
      catch{errors.push('Missing download '+href)}
    }
  }
  await fs.writeFile(path.join(out,'browser_checks.json'),JSON.stringify({passed:!errors.length,errors,checks,local_links_checked:links.filter(h=>!h.startsWith('http')).length},null,2));
  console.log(JSON.stringify({passed:!errors.length,errors,checks}));
  if(errors.length)process.exitCode=1;
}finally{await browser.close()}
