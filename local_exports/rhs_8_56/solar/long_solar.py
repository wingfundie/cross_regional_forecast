"""SA regional rooftop long-lead proxies with original publication clocks and signed RHS attribution."""
import io,csv,json,sys
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd
from replay import OUT,ROOT,rhs
sys.path.insert(0,str(ROOT/'local_exports/rhs_forward_feb26'))
import study as archive
AUDIT=[]
LEADS=[10,21,42]
def light(stamps):
    """Flat horizontal solar geometry proxy near Adelaide, evaluated at interval midpoint."""
    t=pd.DatetimeIndex(stamps)-pd.Timedelta(minutes=15)
    phase=2*np.pi*(t.dayofyear.to_numpy()-1)/365.25
    decl=.006918-.399912*np.cos(phase)+.070257*np.sin(phase)-.006758*np.cos(2*phase)+.000907*np.sin(2*phase)-.002697*np.cos(3*phase)+.00148*np.sin(3*phase)
    eqtime=229.18*(.000075+.001868*np.cos(phase)-.032077*np.sin(phase)-.014615*np.cos(2*phase)-.040849*np.sin(2*phase))
    # NEM UTC+10 meridian is 150 E. Keep all timestamps in that fixed clock.
    angle=np.radians((t.hour.to_numpy()*60+t.minute.to_numpy()+4*(138.6-150)+eqtime)/4-180)
    lat=np.radians(-34.9)
    return np.maximum(0,np.sin(lat)*np.sin(decl)+np.cos(lat)*np.cos(decl)*np.cos(angle))
def parse(blob):
    with ZipFile(io.BytesIO(blob)) as nested:
        csvdata=nested.read(nested.namelist()[0])
    lines=csv.reader(io.StringIO(csvdata.decode('utf-8-sig')))
    h=next(lines); created=pd.Timestamp(' '.join(h[5:7])); names=next(lines)[4:]
    return created,[dict(zip(names,row[4:])) for row in lines if row[0]=='D']
def actual(thu):
    url=archive.BASE+f'ROOFTOP_PV/ACTUAL/PUBLIC_ROOFTOP_PV_ACTUAL_MEASUREMENT_{thu:%Y%m%d}.zip'
    b,_=archive.fetch(url);AUDIT.append(dict(product='actual',url=url,bytes=len(b),sha256=archive.sha(b)))
    rows=[]
    with ZipFile(io.BytesIO(b)) as z:
        for i in z.infolist():
            blob=z.read(i); t,data=parse(blob);mod=pd.Timestamp(datetime(*i.date_time))
            for row in data:
                if row['REGIONID']=='SA1' and row['TYPE']=='MEASUREMENT':
                    rows.append(dict(end=pd.Timestamp(row['INTERVAL_DATETIME']),actual=float(row['POWER']),issue=t,modified=mod,member=i.filename,quality=row.get('QI')))
    return rows
def lookup(origin):
    run=origin-pd.Timedelta(minutes=30)
    thu=run-pd.Timedelta(days=(run.weekday()-3)%7)
    u=archive.BASE+f'ROOFTOP_PV/FORECAST/PUBLIC_ROOFTOP_PV_FORECAST_{thu:%Y%m%d}.zip'
    z,mod=archive.onefile(u,f'PUBLIC_ROOFTOP_PV_FORECAST_{run:%Y%m%d%H%M%S}_')
    with z:
        rd=csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]),encoding='utf-8-sig'))
        h=next(rd);t=pd.Timestamp(' '.join(h[5:7]));head=next(rd)[4:]
        vals=[r for x in rd if x[0]=='D' for r in [dict(zip(head,x[4:]))] if r['REGIONID']=='SA1']
    assert max(t,pd.Timestamp(mod))<=origin
    return dict(origin=origin,issue=t,modified=mod,first=min(r['INTERVAL_DATETIME'] for r in vals),last=max(r['INTERVAL_DATETIME'] for r in vals),source=u)
def capture():
    weeks=pd.date_range('2025-11-06','2026-03-05',freq='W-THU')
    a=pd.DataFrame([r for v in ThreadPoolExecutor(4).map(actual,weeks) for r in v]).sort_values(['end','issue'])
    # Multiple files can publish the same measurement interval; retain the first vintage.
    a=a.drop_duplicates('end',keep='first')
    a.to_csv(OUT/'original_sa_readings.csv',index=False)
    return a
def main():
    if '--capture' in sys.argv:
        a=capture()
    else:
        a=pd.read_csv(OUT/'original_sa_readings.csv',parse_dates=['end','issue','modified'])
    a=a.set_index('end')
    feb=a.loc['2026-02-01':'2026-02-28'].copy();energy=feb.groupby(feb.index.normalize()).actual.sum()
    assert feb.groupby(feb.index.normalize()).size().eq(48).all()
    dark=energy.idxmin()
    dates={pd.Timestamp(2026,2,j):'routine' for j in [1,8,15,22]}
    dates[dark]='low_PV_stress'
    dates[pd.Timestamp(2026,2,19)]='QNI_event_transfer'
    origins=sorted({d-pd.Timedelta(days=l) for d in dates for l in LEADS})
    if '--capture' in sys.argv:
        vintages=pd.DataFrame(list(ThreadPoolExecutor(3).map(lookup,origins)))
        vintages.to_csv(OUT/'issued_coverage.csv',index=False)
        (OUT/'source_hashes.json').write_text(json.dumps(AUDIT+archive.log,indent=2))
    else:vintages=pd.read_csv(OUT/'issued_coverage.csv')
    rows=[]
    for day,cohort in dates.items():
        block=feb[feb.index.normalize()==day]
        for lead in LEADS:
            origin=day-pd.Timedelta(days=lead)
            vintage=vintages[pd.to_datetime(vintages.origin)==origin].iloc[0]
            assert pd.Timestamp(vintage['last'])<day
            elig=a[(a.issue<origin)&(a.modified<origin)]
            for stamp,r in block.iterrows():
                hist=elig[elig.index.time==stamp.time()].tail(21)
                assert len(hist)==21
                y=hist.actual.to_numpy()
                geometry=light(hist.index)
                last=lambda start,stop,g:y[stop-1]
                median=lambda start,stop,g:np.median(y[start:stop])
                def adjusted(start,stop,g):
                    sun=geometry[start:stop]
                    # Near the horizon roof orientation and interval averaging dominate.
                    if g<.08 or np.min(sun)<.08:return median(start,stop,g)
                    return np.median(y[start:stop]/sun)*g
                # Replay forecasts made at the same nominal lead for each prior calibration delivery.
                matched_res=[[],[],[]]
                clock_series=a[a.index.time==stamp.time()]
                for ct,cy in hist.actual.tail(7).items():
                    virtual_origin=ct.normalize()-pd.Timedelta(days=lead)
                    prior=clock_series[(clock_series.issue<virtual_origin)&(clock_series.modified<virtual_origin)].tail(14)
                    if len(prior)<14:continue
                    past=prior.actual.to_numpy();solar=light(prior.index);target=light([ct])[0]
                    alt=np.median(past/solar)*target if target>=.08 and solar.min()>=.08 else np.median(past)
                    for ei,value in enumerate([past[-1],np.median(past),alt]):matched_res[ei].append(abs(cy-value))
                for ei,(method,fn) in enumerate([('last published clock',last),('14-day same clock median',median),('geometry-adjusted 14-day median',adjusted)]):
                    forecast=float(fn(7,21,light([stamp])[0]))
                    band=max(matched_res[ei]) if len(matched_res[ei])==7 else np.nan
                    covered=float(abs(r.actual-forecast)<=band) if np.isfinite(band) else np.nan
                    rows.append(dict(end=stamp,origin=origin,lead_days=lead,cohort=cohort,method=method,actual=r.actual,prediction=forecast,band=band,covered=covered,error=forecast-r.actual,last_input_end=hist.index[-1],last_input_published=max(hist.issue.max(),hist.modified.max())))
    d=pd.DataFrame(rows);d['daylight']=d.end.dt.hour.between(7,18)
    d.to_csv(OUT/'pv_predictions.csv',index=False)
    def summarize(x):
        e=x.error
        return pd.Series(dict(n=len(e),dates=x.end.dt.normalize().nunique(),mae=e.abs().mean(),bias=e.mean(),p95=e.abs().quantile(.95),band_n=x.covered.count(),coverage=x.covered.mean(),mean_width=2*x.band.mean()))
    metrics=d.groupby(['cohort','lead_days','method','daylight']).apply(summarize,include_groups=False)
    metrics.to_csv(OUT/'pv_metrics.csv')
    c=pd.read_csv(OUT/'case_replays.csv');c['end']=pd.to_datetime(c.end).dt.tz_localize(None)
    c['slot']=c.end.dt.ceil('30min');z=c.merge(d.rename(columns={'end':'slot'}),on='slot',validate='many_to_many')
    assert len(z)==72*9
    for idx,row in z.iterrows():
        z.at[idx,'pv_substituted_rhs']=rhs(row,pv=row.prediction)[0]
        z.at[idx,'target_time_public_pv_rhs']=rhs(row,pv=row.actual)[0]
    z['rhs_error']=z.pv_substituted_rhs-z.published_rhs
    z['bridge_error']=z.target_time_public_pv_rhs-z.published_rhs
    z[['end','slot','origin','lead_days','method','cohort','SA_ASEFS2','actual','prediction','active_branch','published_rhs','pv_substituted_rhs','rhs_error','bridge_error']].to_csv(OUT/'rhs_pv_substitution.csv',index=False)
    print(dark,metrics.loc['routine'].xs(True,level='daylight')[['mae','coverage']]);print(z.groupby(['lead_days','method']).rhs_error.apply(lambda x:x.abs().mean()))
if __name__=='__main__':main()

