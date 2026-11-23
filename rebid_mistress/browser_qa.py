"""Local offline browser checks and desktop/mobile screenshots, no external requests."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rebid_mistress.core import *
from playwright.sync_api import sync_playwright

def main():
    qa=REPORTS/'qa';qa.mkdir(exist_ok=True)
    errors=[];external=[];checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        page.on('pageerror',lambda e:errors.append(e.stack or str(e)))
        page.on('request',lambda r:external.append(r.url) if r.url.startswith(('http://','https://')) else None)
        page.goto((REPORTS/'index.html').as_uri(),wait_until='load',timeout=120000)
        page.wait_for_function('window.rebidExplorerReady === true',timeout=120000)
        checks.append(dict(check='explorer initialises offline',passed=True))
        page.screenshot(path=str(qa/'desktop.png'),full_page=False)
        checks.append(dict(check='ten requested portfolio summaries',passed=page.locator('.digest-card').count()==10))
        page.evaluate("document.getElementById('portfolio-highlights').scrollIntoView({block:'start',behavior:'instant'})");page.screenshot(path=str(qa/'portfolio_desktop.png'))
        page.locator('#digest-energyaustralia').screenshot(path=str(qa/'portfolio_ea_desktop.png'))
        digest_offer=page.locator('#digest-energyaustralia [data-offer]').first
        expected_offer=digest_offer.get_attribute('data-offer');digest_offer.click();page.wait_for_timeout(400)
        checks.append(dict(check='portfolio rebid links open matching evidence',passed=expected_offer in page.locator('#detail').inner_text()))
        page.evaluate("document.getElementById('explorer').scrollIntoView({block:'start',behavior:'instant'})");page.screenshot(path=str(qa/'explorer_desktop.png'))
        def matching_count():return int(page.locator('#count').inner_text().split(' matching')[0].replace(',',''))
        total=matching_count()
        for control in ['region','technology','controller','plant','direction','block']:
            if control=='plant':page.select_option('#plant',label='Mount Piper')
            else:page.select_option('#'+control,index=1)
            checks.append(dict(check=control+' filter narrows evidence',passed=0<matching_count()<total))
            page.select_option('#'+control,index=0)
        page.fill('#to','2026-10-10T08:00');page.locator('#to').dispatch_event('change')
        checks.append(dict(check='submission-time filter',passed=0<matching_count()<total))
        page.fill('#to','2026-10-11T04:00');page.locator('#to').dispatch_event('change')
        page.fill('#query','price');checks.append(dict(check='reason search',passed=0<matching_count()<total));page.fill('#query','')
        page.select_option('#direction','LOAD');page.locator('#revisions button').first.click();page.wait_for_timeout(400)
        checks.append(dict(check='LOAD has distinct economic interpretation',passed='willingness to buy' in page.locator('#heatplot').inner_text()))
        page.select_option('#direction','')
        page.select_option('#plant',label='Mount Piper');page.wait_for_timeout(300)
        checks.append(dict(check='plant filter',passed='Mount Piper' in page.locator('#revisions').inner_text()))
        page.fill('#query','a-string-with-no-rebid-match');page.wait_for_timeout(200)
        checks.append(dict(check='empty search state',passed='0 matching revisions' in page.locator('#count').inner_text()))
        page.fill('#query','');page.locator('#revisions button').first.click();page.wait_for_timeout(400)
        checks.append(dict(check='revision details',passed=page.locator('#band-table table tbody tr').count()==10))
        page.locator('#stackplot').scroll_into_view_if_needed();page.screenshot(path=str(qa/'stack_desktop.png'))
        checks.append(dict(check='desktop width',passed=page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+2')))
        page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)');page.wait_for_timeout(1200);page.screenshot(path=str(qa/'mobile.png'))
        page.evaluate("document.getElementById('portfolio-highlights').scrollIntoView({block:'start',behavior:'instant'})");page.screenshot(path=str(qa/'portfolio_mobile.png'))
        page.locator('#digest-energyaustralia').screenshot(path=str(qa/'portfolio_ea_mobile.png'))
        page.evaluate("document.getElementById('explorer').scrollIntoView({block:'start',behavior:'instant'})");page.screenshot(path=str(qa/'explorer_mobile.png'))
        page.locator('#stackplot').screenshot(path=str(qa/'stack_mobile.png'))
        checks.append(dict(check='mobile stack remains rendered',passed=page.locator('#stackplot .main-svg').count()>0 and page.locator('#stackplot').bounding_box()['height']>=400))
        scroll_ok=page.locator('#stackplot').evaluate('(e)=>{e.parentElement.scrollLeft=e.parentElement.scrollWidth;return e.parentElement.scrollLeft>0}')
        checks.append(dict(check='mobile dense chart scrolls horizontally',passed=scroll_ok))
        page.locator('#stackplot').locator('..').screenshot(path=str(qa/'stack_mobile_right.png'))
        checks.append(dict(check='mobile width',passed=page.evaluate('document.documentElement.scrollWidth<=window.innerWidth+2')))
        if not checks[-1]['passed']:print('Overflow:',page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>395 && !e.closest('.table-wrap,.chart-scroll,.interactive-chart')).slice(0,20).map(e=>[e.tagName,e.id,e.className,e.getBoundingClientRect().width])"))
        browser.close()
    checks += [dict(check='no browser errors',passed=not errors),dict(check='no network dependencies',passed=not external)]
    write_json(STATE/'browser_qa.json',dict(html_sha256=sha(REPORTS/'index.html'),checks=checks,errors=errors,external_requests=external,passed=all(c['passed'] for c in checks),visual_inspection=False,screenshots=[str(x) for x in qa.glob('*.png')]))
    print(json.dumps(checks,indent=2))

if __name__=='__main__':main()
