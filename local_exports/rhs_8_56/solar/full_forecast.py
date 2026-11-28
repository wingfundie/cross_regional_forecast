"""Genuine 10/21/42-day complete-equation forecast from a pre-origin case profile."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import io,struct,sys,zlib
from zipfile import ZipFile
import numpy as np
import pandas as pd
from replay import OUT,rhs,readcase
from long_solar import archive,LEADS
TARGETS={'2026-02-01':1,'2026-02-15':97,'2026-02-19':73}
def prior_cases(job):
    target,start,lead=job
    origin=target-pd.Timedelta(days=lead)
    prior=origin-pd.Timedelta(days=2)
    # End of the historical trading day and next 04:00 publication cycle precede the cutoff.
    published_cycle=prior+pd.Timedelta(days=1,hours=4)
    assert published_cycle<origin
    url=f'https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/{prior:%Y}/NEMDE_{prior:%Y_%m}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{prior:%Y%m%d}_loaded.zip'
    first,allinfo=archive.directory(url)
    names={f'NEMSPDOutputs_{prior:%Y%m%d}{index:03d}00.loaded'.lower() for index in range(start,start+24)}
    picks=[i for i in allinfo if i.filename.lower() in names];assert len(picks)==24
    lo=first+picks[0].header_offset;hi=first+allinfo[allinfo.index(picks[-1])+1].header_offset-1
    body,head=archive.fetch(url,f'{lo}-{hi}',cap=18_000_000)
    assert head.startswith(f'bytes {lo}-{hi}/')
    rows=[]
    for item in picks:
        p=first+item.header_offset-lo
        name_len,extra=struct.unpack_from('<HH',body,p+26)
        p+=30+name_len+extra
        chunk=body[p:p+item.compress_size]
        if item.compress_type==8:chunk=zlib.decompress(chunk,-15)
        assert len(chunk)==item.file_size and zlib.crc32(chunk)==item.CRC
        if chunk.startswith(b'PK'):
            with ZipFile(io.BytesIO(chunk)) as z:chunk=z.read(z.namelist()[0])
        r=readcase(chunk,item.filename,url)
        if r is None:continue
        assert abs(r['calculated_rhs']-r['published_rhs'])<.00005
        assert pd.Timestamp(datetime(*item.date_time))<origin
        r.update(prior_end=r['end'],end=pd.Timestamp(r['end']).tz_localize(None)+(target-prior),origin=origin,lead_days=lead,publication_cycle=published_cycle,member_time=datetime(*item.date_time))
        rows.append(r)
    return rows
def main():
    if '--capture' in sys.argv:
        jobs=[(pd.Timestamp(d),s,l) for d,s in TARGETS.items() for l in LEADS]
        anchors=pd.DataFrame(r for block in ThreadPoolExecutor(3).map(prior_cases,jobs) for r in block)
        anchors.to_csv(OUT/'prior_states.csv',index=False)
    anchors=pd.read_csv(OUT/'prior_states.csv',parse_dates=['end']);anchors['slot']=anchors.end.dt.ceil('30min')
    cases=pd.read_csv(OUT/'case_replays.csv');cases['end']=pd.to_datetime(cases.end).dt.tz_localize(None)
    pv=pd.read_csv(OUT/'pv_predictions.csv',parse_dates=['end']).rename(columns={'end':'slot'})
    rows=[]
    for a in anchors.to_dict('records'):
        t=a['end'];lead=a['lead_days'];actual=cases[cases.end==t].iloc[0]
        matched=pv[(pv.slot==a['slot'])&(pv.lead_days==lead)]
        routes={'prior published clock RHS':(a['published_rhs'],a['active_branch'])}
        for q in matched.itertuples():
            val,branch,_=rhs(a,pv=q.prediction);routes[q.method]=(val,branch)
            if q.method=='geometry-adjusted 14-day median':
                # Without a certified controlled-capacity registry, use only the pre-origin
                # same-clock electrical share; avoid dividing by a near-dark observation.
                controlled=a['SA_SAPN_CONTRL_PV']
                if a['SA_ASEFS2']>50:
                    controlled=q.prediction*controlled/a['SA_ASEFS2']
                val,branch,_=rhs(a,pv=q.prediction,SA_SAPN_CONTRL_PV=controlled)
                routes['geometry plus controlled electrical share']=(val,branch)
        for method,(pr,branch) in routes.items():
            rows.append(dict(end=t,slot=a['slot'],origin=a['origin'],lead_days=lead,prior_end=a['prior_end'],forecast_rhs=pr,actual_rhs=actual.published_rhs,predicted_branch=branch,actual_branch=actual.active_branch,method=method))
    f=pd.DataFrame(rows);f['error']=f.forecast_rhs-f.actual_rhs;f.to_csv(OUT/'full_forecast.csv',index=False)
    blocks=f.groupby(['method','lead_days','slot']).agg(n=('end','size'),forecast=('forecast_rhs','mean'),actual=('actual_rhs','mean')).query('n==6')
    blocks['error']=blocks.forecast-blocks.actual
    blocks.to_csv(OUT/'full_halfhours.csv')
    scores=blocks.reset_index().groupby(['method','lead_days']).error.agg(n='size',mae=lambda x:x.abs().mean(),bias='mean',p95=lambda x:x.abs().quantile(.95))
    scores.to_csv(OUT/'full_scores.csv')
    print(scores);print('unique native rows',len(anchors))
if __name__=='__main__':main()
