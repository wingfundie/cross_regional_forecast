import fs from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';

const out=process.argv[2];if(!out)throw Error('Pass QA output directory');
await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true});
const errors=[],checks=[],shots=[];
const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
page.setDefaultTimeout(60000);
page.on('pageerror',e=>errors.push(String(e)));
for(const name of ['index','conditions','limits','validation']){
  await page.goto(`http://127.0.0.1:8062/${name}.html`,{waitUntil:'networkidle'});
  for(const [label,width,height] of [['desktop',1440,1000],['mobile',390,844]]){
    await page.setViewportSize({width,height});await page.evaluate(()=>window.scrollTo(0,0));
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
    checks.push({surface:name,viewport:label,document_overflow:overflow});if(overflow)errors.push(`${name} overflows at ${width}px`);
    const file=path.join(out,`${name}_${label}.png`);await page.screenshot({path:file});shots.push(file);
  }
  await page.setViewportSize({width:1440,height:1000});
  if(await page.locator('figure').count()){
    const file=path.join(out,`${name}_figure.png`);await page.locator('figure').first().screenshot({path:file});shots.push(file);
  }
}
await page.goto('http://127.0.0.1:8061',{waitUntil:'networkidle'});
await page.waitForFunction(()=>document.querySelector('#connector')?.options.length===6,null,{polling:100,timeout:60000});
await page.selectOption('#connector','VNI');await page.selectOption('#quarter','1');await page.selectOption('#era','pre_pec_market');await page.selectOption('#method','table');
await page.click('#run');await page.waitForFunction(()=>!document.querySelector('#run').disabled,null,{polling:100,timeout:60000});
if(!(await page.locator('#message').innerText()).includes('Profile calculated'))throw Error(await page.locator('#message').innerText());
checks.push({surface:'selector',rows:await page.locator('#rows tr').count(),method:'table'});
if(await page.locator('#rows tr').count()!==48)errors.push('Selector did not produce 48 intervals');
await page.evaluate(()=>window.scrollTo(0,0));let file=path.join(out,'selector_desktop.png');await page.screenshot({path:file});shots.push(file);
file=path.join(out,'selector_results.png');await page.locator('#results').screenshot({path:file});shots.push(file);
await page.getByRole('button',{name:'12:00',exact:true}).click();
file=path.join(out,'selector_evidence.png');await page.locator('#detail').screenshot({path:file});shots.push(file);
await page.setViewportSize({width:390,height:844});await page.evaluate(()=>window.scrollTo(0,0));
const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2);
if(overflow)errors.push('Selector overflows at mobile width');
file=path.join(out,'selector_mobile.png');await page.screenshot({path:file});shots.push(file);
await page.setViewportSize({width:1440,height:1000});await page.selectOption('#era','current');await page.click('#run');
await page.waitForFunction(()=>!document.querySelector('#run').disabled,null,{polling:100,timeout:60000});
if(!(await page.locator('#message').innerText()).includes('Profile calculated'))throw Error(await page.locator('#message').innerText());
if(!(await page.locator('#detail').isHidden()))errors.push('Old interval evidence remained visible after recalculation');
checks.push({surface:'selector',case:'unobserved current-era Q1',rows:await page.locator('#rows tr').count(),message:await page.locator('#chart').innerText()});
const bad=await page.evaluate(async()=>{const r=await fetch('/api/select',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({connector:'VNI',quarter:5,half_hour:0})});return r.status});
if(bad!==400)errors.push('Invalid quarter did not return HTTP 400');
await browser.close();
await fs.writeFile(path.join(out,'browser_checks.json'),JSON.stringify({passed:errors.length===0,errors,checks,screenshots:shots},null,2));
console.log(JSON.stringify({passed:errors.length===0,errors,screenshots:shots.length,checks:checks.length}));
if(errors.length)process.exitCode=1;
