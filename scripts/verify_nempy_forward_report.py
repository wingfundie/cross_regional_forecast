"""Check report hashes/links and capture desktop/mobile browser layouts."""
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/nempy_forward_forecast_design_20261004'


def main():
    html = (OUT/'index.html').read_text(encoding='utf-8')
    soup = BeautifulSoup(html, 'html.parser')
    ids = [e['id'] for e in soup.select('[id]')]
    errors = []
    if len(ids) != len(set(ids)):
        errors.append('Duplicate anchors')
    for a in soup.select('a[href]'):
        u = urlsplit(a['href'])
        if u.scheme or u.netloc:
            continue
        if not u.path and u.fragment and unquote(u.fragment) not in ids:
            errors.append('Missing anchor: '+a['href'])
        if u.path and u.path != 'verification.json' and not (OUT/unquote(u.path)).is_file():
            errors.append('Missing file: '+a['href'])
    for tag, attr in [('script','src'), ('img','src'), ('link','href')]:
        for e in soup.select(f'{tag}[{attr}]'):
            value = e[attr]
            if value.startswith(('http:', 'https:', '//')):
                errors.append('External rendering dependency: '+value)
    manifest = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for row in manifest['inputs']+manifest['outputs']:
        if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest() != row['sha256']:
            errors.append('Hash mismatch: '+row['path'])
    source = json.loads((OUT/'source_audit.json').read_text(encoding='utf-8'))
    for row in source['sources']:
        if hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest() != row['sha256']:
            errors.append('Source changed: '+row['path'])
    shots = OUT/'qa'; shots.mkdir(exist_ok=True)
    layouts = []
    browser_errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel='msedge')
        for name, width, height in [('desktop',1440,1000),('mobile',390,844)]:
            page = browser.new_page(viewport={'width':width,'height':height}, device_scale_factor=1)
            page.on('pageerror', lambda e: browser_errors.append(str(e)))
            page.goto((OUT/'index.html').as_uri(), wait_until='load')
            page.screenshot(path=str(shots/f'{name}_hero.png'))
            dimensions = page.evaluate('({width:innerWidth, scroll:document.documentElement.scrollWidth})')
            if dimensions['scroll'] > dimensions['width']:
                errors.append(f'Document-wide overflow on {name}: {dimensions}')
            for area, selector in [('chart','figure'),('table','.table-wrap'),
                                  ('methods','h2[id="15-validation-separate-engine-correctness-from-forecast-quality"]')]:
                element = page.locator(selector).first
                element.evaluate("element => element.scrollIntoView({block:'start',behavior:'instant'})")
                if area == 'chart':
                    element.locator('img').evaluate('(image) => image.decode()')
                page.screenshot(path=str(shots/f'{name}_{area}.png'))
            layouts.append(dict(name=name,viewport=[width,height],dimensions=dimensions,
                                screenshots=[f'qa/{name}_{area}.png' for area in ['hero','chart','table','methods']]))
            page.close()
        browser.close()
    errors.extend(browser_errors)
    result = dict(static_checks='passed' if not errors else 'failed',errors=errors,
                  anchor_count=len(ids),table_count=len(soup.find_all('table')),
                  embedded_chart_count=len(soup.find_all('img')),
                  verified_manifest_entries=len(manifest['inputs'])+len(manifest['outputs']),
                  source_hashes_verified=len(source['sources']),
                  browser_layouts=layouts,browser_errors=browser_errors,
                  visual_review='Screenshots captured; awaiting visual inspection.',
                  repository_tests='See final verification update.')
    (OUT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
