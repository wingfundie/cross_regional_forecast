"""Evidence/manifest and offline-document gates. Visual inspection is recorded separately."""
from bs4 import BeautifulSoup
from .core import *
from .analyse import result

def run():
    checks=[]
    def check(name,condition,detail=''):
        checks.append(dict(check=name,passed=bool(condition),detail=detail))
    a=result('reconstruction_audit');check('Effective offers link to accepted history',a.missing_offer_links.sum()==0)
    check('Band MW and maximum availability match Bidmove',a.volume_mismatches.sum()==0)
    prices=result('prices');check('288 unique price intervals per region',prices.groupby('REGIONID').SETTLEMENTDATE.nunique().eq(288).all())
    event=prices[prices.SETTLEMENTDATE.eq(SPIKE)].set_index('REGIONID').RRP
    check('Confirmed NSW price cap',abs(event.get('NSW1',0)-23200)<.001)
    units=result('units');inv=load_table('inventory');check('Every inventory DUID has an account',set(units.DUID)==set(inv.DUID))
    p=result('panel');check('Every unit has 288 delivery slots',p.groupby('DUID').size().eq(288).all())
    check('No duplicate unit observations',not p.duplicated(['DUID','delivery']).any())
    port=result('portfolios');valid=port[port.complete]
    check('Replacement never exceeds shortfall',(valid.matched_mw<=valid.shortfall_mw+.001).all())
    check('Replacement never exceeds incremental supply',(valid.matched_mw<=valid.incremental_mw+.001).all())
    check('Missing portfolio evidence stays missing',port.loc[~port.complete,'matched_mw'].isna().all())
    f=result('forecast');check('Frozen forecast processed before signal',(f.LASTCHANGED<SIGNAL).all())
    check('Forecast targets retain half-hour endpoints',f.delivery.dt.minute.isin([0,30]).all())
    h=load_table('headers');check('Structured reasons retained',all(c in h for c in ['REBIDEXPLANATION','REBID_EVENT_TIME','REBID_AWARE_TIME','REBID_DECISION_TIME','REBID_CATEGORY']))
    from .reconstruct import PRICES
    import numpy as np
    bd=load_table('bidmove_BIDDAYOFFER_D');number(bd,PRICES)
    active=h[h.offer_id.isin(result('effective').offer_id)].merge(bd[['DUID','DIRECTION']+PRICES],on=['DUID','DIRECTION'],suffixes=('_accepted','_effective'),validate='many_to_one')
    check('Effective daily price ladders reconcile',all(np.allclose(pd.to_numeric(active[c+'_accepted']),active[c+'_effective'],atol=.001,equal_nan=True) for c in PRICES))
    html=REPORTS/'index.html';soup=BeautifulSoup(html.read_text(encoding='utf-8'),'html.parser')
    anchors=[x['id'] for x in soup.select('[id]')];check('No duplicate anchors',len(anchors)==len(set(anchors)))
    missing=[]
    for node in soup.select('a[href]'):
        href=node['href']
        if href.startswith('#') and href[1:] not in anchors:missing.append(href)
        elif not href.startswith(('http:','https:','#','data:','mailto:')) and not (REPORTS/href).exists():missing.append(href)
    check('All local links and downloads exist',not missing,missing)
    external=[n.get('src') for n in soup.select('script[src],img[src]') if str(n.get('src','')).startswith('http')]
    external += [n.get('href') for n in soup.select('link[rel=stylesheet]') if str(n.get('href','')).startswith('http')]
    check('No external rendering dependencies',not external,external)
    manifest=json.loads((STATE/'report_manifest.json').read_text())
    check('HTML matches report manifest',manifest['html_sha256']==sha(html))
    check('Download hashes match',all((REPORTS/'downloads'/name).exists() and sha(REPORTS/'downloads'/name)==digest for name,digest in manifest['downloads'].items()))
    check('Every plant has a report section',len(soup.select('.plant-account'))==units.plant.nunique())
    from .portfolio_digest import FAMILIES
    check('All ten requested portfolio highlights present',[n.get_text() for n in soup.select('.digest-card h3')]==list(FAMILIES))
    digest=pd.read_csv(REPORTS/'downloads/portfolio_digest_rebids.csv')
    source_reasons=h.set_index('offer_id').REBIDEXPLANATION
    check('Portfolio rebid reasons match accepted headers',all(r.reason==source_reasons.loc[r.offer_id] for r in digest.itertuples()))
    members=pd.read_csv(REPORTS/'downloads/portfolio_digest_members.csv')
    check('Callide Trading remains separate from CS Energy',set(members.loc[members.digest_portfolio.eq('Callide Trading'),'DUID'])=={'CPP_3','CPP_4'} and not members.loc[members.digest_portfolio.eq('CS Energy'),'DUID'].isin(['CPP_3','CPP_4']).any())
    qa=STATE/'browser_qa.json'
    q=json.loads(qa.read_text()) if qa.exists() else {}
    check('Browser QA matches report hash',q.get('html_sha256')==sha(html))
    check('Browser checks passed',q.get('passed',False))
    check('Desktop and mobile images visually reviewed',q.get('visual_inspection',False))
    test_path=STATE/'repository_tests.json';tests=json.loads(test_path.read_text()) if test_path.exists() else {}
    check('Full repository test suite passed',tests.get('exit_code')==0 and tests.get('command')=='python -m pytest -q')
    write_json(STATE/'validation.json',dict(checks=checks,passed=all(x['passed'] for x in checks),limitations=['Historical registry snapshot; public dissemination times unverified; FCAS excluded; no causal or financial hedge estimates']))
    print(json.dumps(checks,indent=2))
    if not all(x['passed'] for x in checks):raise ValueError('Validation gates incomplete')

if __name__=='__main__':run()
