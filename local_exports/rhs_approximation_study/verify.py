"""Independently recompute scorecards and inspect the generated page while offline."""
from pathlib import Path
from urllib.parse import unquote, urlsplit
from collections import Counter
import json
import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parent
qa = out/'verification'
qa.mkdir(exist_ok=True)
results = {}

def frame(name):
    return pd.read_csv(out/name)

def compare(rows, group, estimates, actual, score, label):
    calc = (rows[estimates]-rows[actual]).abs().groupby([rows[x] for x in group]).mean().sort_index()
    official = score.set_index(group).mae.sort_index()
    assert calc.index.equals(official.index) and np.allclose(calc.values,official.values,atol=1e-7)
    results[label] = len(calc)

local=frame('local/predictions.csv').query("partition=='evaluation'")
compare(local,['target','kind','method'],'forecast','actual',frame('local/scores.csv'),'local_score_groups')
flow=frame('flows/rhs_predictions.csv').query("phase=='test'")
compare(flow,['product','method'],'predicted_rhs','actual_rhs',frame('flows/rhs_scores.csv'),'qni_score_groups')
fl=frame('flows/flow_predictions.csv').query("phase=='test'")
compare(fl,['product','link','method'],'prediction','actual',frame('flows/flow_scores.csv'),'interconnector_score_groups')
th=frame('thermal/forecast_predictions.csv').groupby(['slot','horizon','method'])[['rhs','actual_rhs']].mean().reset_index()
compare(th,['horizon','method'],'rhs','actual_rhs',frame('thermal/rhs_metrics.csv'),'thermal_score_groups')
st=frame('states/predictions.csv')
compare(st,['product','point','method'],'estimate','actual',frame('states/metrics.csv'),'state_score_groups')
outages=frame('states/outage_predictions.csv')
for r in frame('states/outage_metrics.csv').itertuples():
    subset=outages[outages['product'].eq(r.product)]
    outcomes=Counter(zip(subset.actual,subset[r.method]))
    assert (r.tp,r.fp,r.fn)==(outcomes[(1,1)],outcomes[(0,1)],outcomes[(1,0)])
results['outage_score_groups']=4

doc=BeautifulSoup((out/'index.html').read_text(encoding='utf8'),'html.parser')
for anchor in doc.select('a[href]'):
    url=urlsplit(anchor['href'])
    if url.scheme:continue
    if url.path:assert (out/unquote(url.path)).is_file(),url.path
    elif url.fragment:assert doc.find(id=unquote(url.fragment)),url.fragment
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    for name,width,height in [('desktop',1365,900),('mobile',390,844)]:
        context=browser.new_context(viewport={'width':width,'height':height},offline=True)
        page=context.new_page()
        errors=[];page.on('pageerror',lambda exc:errors.append(str(exc)))
        page.goto((out/'index.html').as_uri())
        assert not errors and page.locator('figure img').count()==2
        assert page.evaluate('Array.from(document.images).every(i=>i.complete && i.naturalWidth>0)')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
        assert page.locator('section').count()==10
        page.screenshot(path=str(qa/(name+'.png')))
        page.locator('figure').first.screenshot(path=str(qa/(name+'_figure.png')))
        results[name]={'width':width,'height':height,'offline_figures':2,'sections':10}
        context.close()
    browser.close()
(qa/'checks.json').write_text(json.dumps(results,indent=2))
print(results)
