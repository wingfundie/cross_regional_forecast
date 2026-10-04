"""Check report evidence, downloads, controls, offline rendering, and responsive layout."""
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import unquote,urlsplit

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/nempy_forward_forecast_visual_ste_20261004'


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    soup=BeautifulSoup((OUT/'index.html').read_text(encoding='utf-8'),'html.parser')
    ids=[n['id'] for n in soup.select('[id]')]
    errors=[]
    if len(ids)!=len(set(ids)):errors.append('Duplicate IDs')
    downloads=[]
    for a in soup.select('a[href]'):
        href=a['href'];u=urlsplit(href)
        if href.startswith('data:'):
            payload=base64.b64decode(href.split(',',1)[1])
            filename=a.get('download','')
            if filename.endswith('.csv'):
                rows=list(csv.DictReader(io.StringIO(payload.decode())))
                path=OUT/'data'/filename
                if not path.exists() or path.read_text(encoding='utf-8')!=payload.decode():
                    # Normalize platform newlines before comparison.
                    if not path.exists() or path.read_text(encoding='utf-8').replace('\r\n','\n')!=payload.decode().replace('\r\n','\n'):
                        errors.append('CSV download mismatch: '+filename)
                downloads.append(dict(file=filename,rows=len(rows)))
            elif filename.endswith('.json'):
                json.loads(payload)
            continue
        if u.scheme or u.netloc:continue
        if not u.path and u.fragment and unquote(u.fragment) not in ids:errors.append('Missing anchor: '+href)
        if u.path and u.path!='verification.json' and not (OUT/unquote(u.path)).is_file():errors.append('Missing file: '+href)
    for selector,attr in [('img[src]','src'),('script[src]','src'),('link[rel="stylesheet"]','href')]:
        for n in soup.select(selector):
            if n.get(attr,'').startswith(('http:','https:','//')):errors.append('External rendering dependency')
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for row in manifest['inputs']+manifest['outputs']:
        if digest(ROOT/row['path'])!=row['sha256']:errors.append('Hash mismatch: '+row['path'])
    audit=json.loads((OUT/'source_audit.json').read_text(encoding='utf-8'))
    for row in audit['sources']:
        if digest(ROOT/row['path'])!=row['sha256']:errors.append('Changed source: '+row['path'])
    old=list(csv.DictReader((ROOT/'reports/nempy_forward_forecast_design_20261004/evidence.csv').open(encoding='utf-8')))
    data=json.loads((OUT/'data/research_evidence.json').read_text(encoding='utf-8'))
    for ic in ['QNI','VNI']:
        for target in ['export_tight','import_tight']:
            previous=[float(r['value']) for r in old if r['connector']==ic and r['target']==target]
            current=[r['skill_pct'] for r in data['skill'] if r['connector']==ic and r['target']==target]
            if previous!=current:errors.append(f'Changed skill values: {ic} {target}')
    for r in data['coverage']:
        match=[x for x in old if x['connector']==r['connector'] and x['metric']=='interval_coverage_pct' and float(x['nominal'])==r['nominal_pct']]
        if len(match)!=1 or float(match[0]['value'])!=r['observed_pct']:errors.append('Changed coverage values')
    review=json.loads((OUT/'language_review.json').read_text(encoding='utf-8'))
    for key in ['over_limit','paragraphs_over_six_sentences','contractions','selected_complex_words']:
        if review[key]:errors.append('Language structure check failed: '+key)
    browser_errors=[];layouts=[];controls=[]
    qa=OUT/'qa';qa.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='msedge',headless=True)
        for name,width,height in [('desktop',1440,1050),('mobile',390,844)]:
            page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
            page.on('pageerror',lambda e:browser_errors.append(str(e)))
            page.goto((OUT/'index.html').as_uri(),wait_until='load')
            dimensions=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
            if dimensions['width']!=dimensions['scroll']:errors.append('Page overflow: '+name)
            page.screenshot(path=str(qa/f'{name}_hero.png'))
            targets=[('skill','#fig-skill'),('outage','#diagram-outage_chain'),('geometry','#fig-geometry'),
                     ('simulator','#simulator'),('workflow','#diagram-run_flow'),
                     ('month','h2[id^="17-"]'),('methods','h2[id^="16-"]')]
            for label,selector in targets:
                el=page.locator(selector).first
                el.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
                if el.locator('img').count():el.locator('img').evaluate('(img)=>img.decode()')
                page.screenshot(path=str(qa/f'{name}_{label}.png'))
            if name=='desktop':
                checks=[(700,600,'400.00 MW','466.67 MW','400.00 MW'),
                        (850,600,'550.00 MW','566.67 MW','550.00 MW'),
                        (850,0,'850.00 MW','566.67 MW','566.67 MW'),
                        (100,1400,'Infeasible','66.67 MW','Infeasible')]
                for R,P,f,e,c in checks:
                    page.locator('#rhs').evaluate('(el,value)=>{el.value=value;el.dispatchEvent(new Event("input",{bubbles:true}))}',R)
                    page.locator('#reference').evaluate('(el,value)=>{el.value=value;el.dispatchEvent(new Event("input",{bubbles:true}))}',P)
                    actual=[page.locator('#'+key).inner_text() for key in ['fixed-result','equation-result','combined-result']]
                    if actual!=[f,e,c]:errors.append(f'Control mismatch: {R},{P}: {actual}')
                    controls.append(dict(rhs=R,reference=P,outputs=actual))
                page.locator('#reset-sim').click()
                if page.locator('#fixed-result').inner_text()!='400.00 MW':errors.append('Reset failed')
                first=page.locator('details.chart-data').first
                first.locator('summary').click()
                if not first.get_attribute('open')=='':errors.append('Data disclosure failed')
                first.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
                page.screenshot(path=str(qa/'desktop_data_table.png'))
                page.select_option('#section-jump',page.locator('h2[id^="17-"]').first.get_attribute('id'))
                page.wait_for_function('window.scrollY>0')
            layouts.append(dict(name=name,viewport=[width,height],dimensions=dimensions))
            page.close()
        browser.close()
    errors.extend(browser_errors)
    result=dict(status='passed' if not errors else 'failed',errors=errors,charts=len(soup.select('figure')),
                diagrams=len(soup.select('.design-figure')),embedded_csv_downloads=downloads,
                source_values_match_original=True if not any('Changed' in e for e in errors) else False,
                source_hashes_checked=len(audit['sources']),manifest_hashes_checked=len(manifest['inputs'])+len(manifest['outputs']),
                browser_errors=browser_errors,layouts=layouts,interactive_cases=controls,
                language_structure='passed' if not any('Language' in e for e in errors) else 'failed',
                full_ste_conformity='unverified; see language_review.json',
                visual_review='Screenshots captured; visual inspection pending.')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    if errors:raise SystemExit(1)


if __name__=='__main__':main()
