"""Public preceding dispatch report persistence, with original archive timestamp checks."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import pandas as pd
import requests

OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(OUT.parents[2]/'local_exports/rhs_forward_feb26'))
import study as archive

def fetch(origin):
    stamp=origin-pd.Timedelta(minutes=5)
    url=archive.BASE+f'DispatchIS_Reports/PUBLIC_DISPATCHIS_{stamp:%Y%m%d}.zip'
    try:
        z,modified=archive.onefile(url,f'PUBLIC_DISPATCHIS_{stamp:%Y%m%d%H%M}_')
    except requests.HTTPError as exc:
        if exc.response.status_code==404:return [],dict(origin=str(origin),url=url,status=404)
        raise
    ids={'qni':('NSW1-QLD1','N>>NIL_85_86_S'),'vni':('VIC1-NSW1','V^^N_NIL_1')}
    values={k:dict(link=k,origin=origin,anchor=stamp) for k in ids}
    for created,table,r in archive.unpack(z):
        assert max(created,modified)<origin
        if r.get('INTERVENTION','0')!='0' or r.get('RUNNO','1')!='1':continue
        for k,(link,case) in ids.items():
            row=values[k]
            if table=='INTERCONNECTORRES' and r['INTERCONNECTORID']==link:
                row.update(export=float(r['EXPORTLIMIT']),**{'import':-float(r['IMPORTLIMIT'])})
            if table=='CONSTRAINT' and r['CONSTRAINTID']==case:
                row.update(rhs=float(r['RHS']),headroom=float(r['RHS'])-float(r['LHS']),economic_frequency=float(abs(float(r['MARGINALVALUE']))>1e-5))
            if k=='qni' and table=='CONSTRAINT' and r['CONSTRAINTID']=='N::Q_NIL_KC':row['kc']=float(r['RHS'])
    assert all('rhs' in r and 'export' in r for r in values.values())
    return list(values.values()),dict(origin=str(origin),url=url,status=200,created=str(created),modified=str(modified),member=z.namelist()[0],sha256=archive.sha(z.read(z.namelist()[0])))

def reliable(origin):
    for attempt in range(3):
        try:return fetch(origin)
        except (requests.ConnectionError,requests.Timeout) as exc:
            if attempt==2:return [],dict(origin=str(origin),status='connection failed',error=type(exc).__name__)

if __name__=='__main__':
    dates=pd.to_datetime(['2025-11-23','2025-11-24','2025-11-26','2025-11-28',*[f'2026-02-{i:02}' for i in (4,8,11,17,18,25)]])
    origins=sorted({day-pd.Timedelta(days=h) for day in dates for h in [10,21,42]})
    with ThreadPoolExecutor(4) as pool:results=list(pool.map(reliable,origins))
    pd.DataFrame(sum([r for r,m in results],[])).to_csv(OUT/'public_anchor.csv',index=False)
    (OUT/'anchor_sources.json').write_text(json.dumps([m for r,m in results],indent=2))
