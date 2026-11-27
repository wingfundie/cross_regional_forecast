"""Test correct scheduled-load bridge using an earlier public SCADA report."""
from pathlib import Path
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
import io,csv,json
import numpy as np
import pandas as pd
import importlib.util
spec=importlib.util.spec_from_file_location("flow_study",Path(__file__).with_name("study.py"))
flow=importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)
OUT=flow.OUT
POINTS={'SHPUMP':'NSW1','PUMP1':'QLD1','PUMP2':'QLD1'}

def one(group):
    date,ends=group
    url=flow.previous.BASE+f'Dispatch_SCADA/PUBLIC_DISPATCHSCADA_{date:%Y%m%d}.zip'
    raw,_=flow.previous.fetch(url);z=ZipFile(io.BytesIO(raw));files={i.filename.split('_')[2]:i for i in z.infolist()}
    rows=[]
    for t in ends:
        m=files[t.strftime('%Y%m%d%H%M')];b=z.read(m);inner=ZipFile(io.BytesIO(b))
        with io.TextIOWrapper(inner.open(inner.namelist()[0])) as stream:
            rd=csv.reader(stream);h=next(rd);created=pd.Timestamp(' '.join(h[5:7]));fields=next(rd)
            vals={r[5]:float(r[6]) for r in rd if len(r)>6 and r[5] in POINTS}
        assert set(vals)==set(POINTS),(t,vals)
        rows.append(dict(end=t,issued=created,modified=pd.Timestamp(*m.date_time),sha256=flow.previous.sha(b),
                        member=m.filename,**vals))
    return rows,dict(url=url,bytes=len(raw),sha256=flow.previous.sha(raw))

def collect():
    a=pd.read_csv(OUT/'injection_scenarios.csv',parse_dates=['end','origin_interval'])
    required=sorted(set(a.end)|set(a.origin_interval))
    groups={}
    for t in required:groups.setdefault(t.date(),[]).append(t)
    with ThreadPoolExecutor(max_workers=3) as p: sources=list(p.map(one,groups.items()))
    pd.DataFrame([r for rows,_ in sources for r in rows]).to_csv(OUT/'load_scada.csv',index=False)
    (OUT/'load_scada_sources.json').write_text(json.dumps([r for _,r in sources],indent=2))

def run():
    a=pd.read_csv(OUT/'injection_scenarios.csv',parse_dates=['end','origin_interval','issued'])
    o=pd.read_csv(OUT/'public_dispatch.csv',parse_dates=['end']).set_index('end')
    loads=pd.read_csv(OUT/'load_scada.csv',parse_dates=['end','issued','modified']).set_index('end')
    m=pd.read_csv(OUT/'rhs_predictions.csv',parse_dates=['end','issued','origin_interval','period_end'])
    ref=m[m.method=='issued AEMO RHS'].set_index(['product','end'])
    rows=[]; diag=[]
    for _,s in a.iterrows():
        anchor=loads.loc[s.origin_interval]
        assert max(anchor.issued,anchor.modified)<=s.issued
        p=flow.formula(s.forecast_nsw+anchor.SHPUMP,s.forecast_qld+anchor.PUMP1+anchor.PUMP2,
                       s.initial_flow,s.estimated_terr)
        k=(s['product'],s.end)
        z=ref.loc[k].to_dict();z.update(product=k[0],end=k[1],method='issued flow and local load with prior scheduled-load SCADA',
             predicted_rhs=p,error=p-z['actual_rhs'],headroom=p-z['issued_lhs'],
             headroom_error=(p-z['issued_lhs'])-z['actual_headroom'])
        rows.append(z)
        if s['product']=='P5MIN':
            observed=o.loc[s.end];actual=loads.loc[s.end]
            n,q=observed.NSW1_TOTALDEMAND,observed.QLD1_TOTALDEMAND;i=observed['meter_'+flow.DIRECT];d=observed.terr
            for name,nn,qq in [('plain region',n,q),('all dispatchable load',n+observed.NSW1_DISPATCHABLELOAD,q+observed.QLD1_DISPATCHABLELOAD),
                               ('three metered pumps',n+actual.SHPUMP,q+actual.PUMP1+actual.PUMP2)]:
                f=flow.formula(nn,qq,i,d)
                diag.append(dict(end=s.end,phase=s.phase,method=name,regional_nsw=nn,regional_qld=qq,predicted=f,
                                 observed=observed.rhs,error=f-observed.rhs))
    z=pd.DataFrame(rows)
    for prod,g in z.groupby('product'):
        band=g.loc[g.phase=='calibration','headroom_error'].abs().quantile(.9,interpolation='higher')
        z.loc[g.index,'band']=band
    z['call']=np.select([z.headroom-z.band>1e-4,z.headroom+z.band<=1e-4],['clear','at risk'],default='uncertain')
    z.to_csv(OUT/'scheduled_load_predictions.csv',index=False)
    dd=pd.DataFrame(diag);dd.to_csv(OUT/'regional_semantics.csv',index=False)
    res=z[z.phase=='test'].groupby('product').error.agg(['size',lambda x:x.abs().mean(),'mean',lambda x:x.abs().max()])
    res.columns=['n','mae','bias','max_abs'];res.to_csv(OUT/'scheduled_load_scores.csv')
    print(res);print(dd[dd.phase=='test'].groupby('method').error.agg(['size',lambda x:x.abs().mean(),lambda x:x.abs().max()]))
if __name__=='__main__':
    import sys
    if '--download' in sys.argv: collect()
    run()


