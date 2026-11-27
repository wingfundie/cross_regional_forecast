"""Forward flow and NSW/QLD RHS study. Market time is fixed UTC+10.
Run with --download once, or from retained CSVs with no argument.
"""
from __future__ import annotations
import csv
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'local_exports/rhs_forward_feb26'))
import study as previous

FIT = list(range(9,16))
CAL = [16,17]
TEST = [19,20,22]
LINKS = ('N-Q-MNSP1','NSW1-QLD1','VIC1-NSW1','V-SA','V-S-MNSP1','T-V-MNSP1')
REGIONS = ('NSW1','QLD1')
EQ = 'N::Q_NIL_KC'
TER = 'DATASNAP_TE_967_1'
DIRECT = 'N-Q-MNSP1'
VARS = ('TOTALDEMAND','DISPATCHABLELOAD','INITIALSUPPLY','CLEAREDSUPPLY')
SOURCES = []

def dates(day):
    return pd.date_range(f'2026-02-{day:02d} 10:05',periods=24,freq='5min')

def clock_specs():
    specs=[]
    for day in CAL+TEST:
        end=dates(day)
        specs.append(('PREDISPATCHIS', end[0].normalize()-pd.Timedelta(hours=7,minutes=30),
                      [end[0].floor('30min')]+list(end[5::6])))
        for n in range(0,24,6):
            first=end[n]
            specs.append(('P5MIN',first-pd.Timedelta(minutes=30),
                          [first-pd.Timedelta(minutes=5)]+list(end[n:n+6])))
    return specs

def extract(z, allowed):
    want={t.strftime('%Y/%m/%d %H:%M:%S') for t in allowed}
    data={}
    for issued,_,r in previous.unpack(z):
        if r.get('INTERVENTION','0')!='0' or r.get('RUNNO','1')!='1':
            continue
        ts=r.get('INTERVAL_DATETIME') or r.get('DATETIME') or r.get('SETTLEMENTDATE')
        if ts not in want:
            continue
        row=data.setdefault(ts,{})
        uid=r.get('INTERCONNECTORID')
        if uid in LINKS and 'MWFLOW' in r:
            row['target_'+uid]=float(r['MWFLOW'])
            row['meter_'+uid]=float(r['METEREDMWFLOW'])
        if r.get('REGIONID') in REGIONS and 'TOTALDEMAND' in r:
            for field in VARS:
                row[r['REGIONID']+'_'+field]=float(r[field])
        cid=r.get('CONSTRAINTID')
        if cid in {EQ,TER}:
            version='2023/05/01' if cid==EQ else '2024/07/11'
            assert r['GENCONID_EFFECTIVEDATE'].startswith(version) and r['GENCONID_VERSIONNO']=='1'
            if cid==TER: row['terr']=float(r['RHS'])-10000
            else:
                row.update(rhs=float(r['RHS']),lhs=float(r['LHS']),mv=float(r['MARGINALVALUE']),violation=float(r['VIOLATIONDEGREE']))
    return issued,{pd.Timestamp(k):v for k,v in data.items()}

def get_forecast(spec):
    kind,stamp,ends=spec
    z,modified=previous.forecast_file(kind,stamp)
    issued,rows=extract(z,ends)
    assert set(rows)==set(ends) and modified>=issued
    return [dict(product=kind,run=z.namelist()[0],end=t,issue=issued,modified=modified,**row)
            for t,row in rows.items()]

def get_actual(group):
    date,required=group
    url=previous.BASE+f'DispatchIS_Reports/PUBLIC_DISPATCHIS_{date:%Y%m%d}.zip'
    b,_=previous.fetch(url)
    z=ZipFile(io.BytesIO(b))
    file_by_suffix={r.filename.split('_')[2]:r for r in z.infolist() if r.filename.startswith('PUBLIC_DISPATCHIS_')}
    rows=[]
    for t in sorted(required):
        member=file_by_suffix[t.strftime('%Y%m%d%H%M')]
        raw=z.read(member)
        created,values=extract(ZipFile(io.BytesIO(raw)),[t])
        rows.append(dict(end=t,issue=created,modified=pd.Timestamp(*member.date_time),member=member.filename,
                         member_sha256=previous.sha(raw),**values[t]))
    return rows,dict(url=url,sha256=previous.sha(b),bytes=len(b))

def download():
    with ThreadPoolExecutor(max_workers=3) as pool:
        fc=pd.DataFrame([r for group in pool.map(get_forecast,clock_specs()) for r in group])
    assert len(fc)==5*(4*7+5)
    wanted={t for day in FIT+CAL+TEST for t in dates(day)}
    wanted.update(fc.issue.dt.floor('5min').unique())
    grouped={}
    for t in wanted:
        t=pd.Timestamp(t); grouped.setdefault(t.date(),[]).append(t)
    with ThreadPoolExecutor(max_workers=3) as pool:
        archives=list(pool.map(get_actual,sorted(grouped.items())))
    obs=pd.DataFrame([r for rows,_ in archives for r in rows]).sort_values('end')
    assert not obs.end.duplicated().any()
    if obs.isna().any().any() or fc.isna().any().any():
        raise ValueError(f'Missing observations {obs.isna().sum()} or forecasts {fc.isna().sum()}')
    obs.to_csv(OUT/'public_dispatch.csv',index=False)
    fc.sort_values(['product','issue','end']).to_csv(OUT/'issued_values.csv',index=False)
    sources=[raw for _,raw in archives]+previous.log
    (OUT/'sources.json').write_text(json.dumps(sources,indent=2))

def formula(n,q,i,d):
    return 1383-.001*(i+d)**2-.0239*n+.0524*q-.6394*d

def average(z):
    return float(z.mean())

def calculate():
    obs=pd.read_csv(OUT/'public_dispatch.csv',parse_dates=['end','issue','modified']).set_index('end').sort_index()
    fc=pd.read_csv(OUT/'issued_values.csv',parse_dates=['end','issue','modified'])
    fit_idx=[t for day in FIT for t in dates(day)]
    hist=obs.loc[fit_idx].copy()
    hist['clock']=hist.index.ceil('30min').time
    hist['weekend']=hist.index.weekday>=5
    assert max(hist.modified)<min(fc.issue)
    tracks=[]; rhs=[]; align=[]
    frac=hist.terr.sum()/hist.NSW1_TOTALDEMAND.sum()
    for run,b in fc.groupby('run'):
        b=b.sort_values('end').set_index('end')
        kind=b['product'].iat[0];issued=b.issue.iat[0];modified=b.modified.iat[0]
        origin=obs.loc[issued.floor('5min')]
        assert max(origin.issue,origin.modified)<=issued
        for pos in range(1,len(b)):
            end=b.index[pos];prev=b.iloc[pos-1];now=b.iloc[pos]
            native=5 if kind=='P5MIN' else 30
            assert end-b.index[pos-1]==pd.Timedelta(minutes=native)
            for k,t in enumerate(pd.date_range(end-pd.Timedelta(minutes=native-5),end,freq='5min')):
                assert max(issued,modified)<t-pd.Timedelta(minutes=5)
                actual=obs.loc[t]
                peers=hist[(hist.clock==t.ceil('30min').time()) & (hist.weekend==(t.weekday()>=5))]
                assert len(peers) in (12,30)
                common=dict(product=kind,end=t,period_end=end,run=run,issued=issued,origin_interval=origin.name,
                            lead_to_end_minutes=(t-issued).total_seconds()/60,phase='calibration' if t.day in CAL else 'test')
                for link in LINKS:
                    offered=prev['target_'+link]
                    ramp=offered+(k*5/native)*(now['target_'+link]-offered)
                    methods={'persist':origin['meter_'+link], 'clock profile':peers['meter_'+link].mean(),
                             'prior issued target':offered,'issued ramp':ramp}
                    for method,p in methods.items():
                        tracks.append(dict(**common,link=link,method=method,prediction=p,actual=actual['meter_'+link],
                                           first_five_in_period=(k==0)))
                    if link==DIRECT:
                        selected=ramp
                n,q=now.NSW1_TOTALDEMAND,now.QLD1_TOTALDEMAND
                n0,q0=origin.NSW1_TOTALDEMAND,origin.QLD1_TOTALDEMAND
                dn=n-n0
                initial_sched_n=prev.NSW1_DISPATCHABLELOAD+(k*5/native)*(now.NSW1_DISPATCHABLELOAD-prev.NSW1_DISPATCHABLELOAD)
                initial_sched_q=prev.QLD1_DISPATCHABLELOAD+(k*5/native)*(now.QLD1_DISPATCHABLELOAD-prev.QLD1_DISPATCHABLELOAD)
                mapped_n=n+initial_sched_n; mapped_q=q+initial_sched_q
                prev_exact=origin.rhs
                old_i=origin['meter_'+DIRECT];old_d=origin.terr
                annual_d=n*frac; local_d=now.terr
                regional_anchor=prev_exact+formula(n,q,old_i,old_d+dn*frac)-formula(n0,q0,old_i,old_d)
                methods={'RHS persistence':prev_exact,'clock RHS profile':peers.rhs.mean(),
                         'regional forecast with clock flow and fixed load share':formula(n,q,peers['meter_'+DIRECT].mean(),annual_d),
                         'regional forecast change from observed RHS':regional_anchor,
                         'issued AEMO RHS':now.rhs,
                         'issued flow and local load with total demand':formula(n,q,selected,local_d),
                         'issued flow, local load and adjusted regional demand':formula(mapped_n,mapped_q,selected,local_d)}
                # Predeclared perturbation illustrates a user regional scenario. Not scored as a point forecast.
                scenario=now.rhs+formula(mapped_n+100,mapped_q,selected,local_d+100*frac)-formula(mapped_n,mapped_q,selected,local_d)
                align.append(dict(**common,initial_flow=selected,estimated_terr=local_d,forecast_nsw=n,forecast_qld=q,
                                  prev_load_nsw=initial_sched_n,prev_load_qld=initial_sched_q,scenario_nsw_change=100,
                                  scenario_terr_change=100*frac,issued_rhs=now.rhs,scenario_rhs=scenario,
                                  scenario_delta=scenario-now.rhs))
                for method,p in methods.items():
                    rhs.append(dict(**common,method=method,predicted_rhs=p,actual_rhs=actual.rhs,issued_lhs=now.lhs,
                                    actual_lhs=actual.lhs,economic_bind=abs(actual.mv)>1e-5,
                                    issued_economic_bind=abs(now.mv)>1e-5,violation=actual.violation))
    tr=pd.DataFrame(tracks); rr=pd.DataFrame(rhs); al=pd.DataFrame(align)
    for x in (tr,rr,al):
        assert not x.isna().any().any()
    tr['error']=tr.prediction-tr.actual
    rr['error']=rr.predicted_rhs-rr.actual_rhs
    rr['headroom']=rr.predicted_rhs-rr.issued_lhs
    rr['actual_headroom']=rr.actual_rhs-rr.actual_lhs
    rr['headroom_error']=rr.headroom-rr.actual_headroom
    rr['band']=np.nan
    for (prod,method),g in rr.groupby(['product','method']):
        band=g.loc[g.phase=='calibration','headroom_error'].abs().quantile(.9,interpolation='higher')
        rr.loc[g.index,'band']=band
    rr['call']=np.select([rr.headroom-rr.band>1e-4,rr.headroom+rr.band<=1e-4],['clear','at risk'],default='uncertain')
    tr.to_csv(OUT/'flow_predictions.csv',index=False)
    rr.to_csv(OUT/'rhs_predictions.csv',index=False)
    al.to_csv(OUT/'injection_scenarios.csv',index=False)
    def summary(g):
        return pd.Series(dict(n=len(g),mae=g.error.abs().mean(),bias=g.error.mean(),max_abs=g.error.abs().max()))
    ind=tr.phase.eq('test')
    ts=tr[ind].groupby(['product','link','method']).apply(summary,include_groups=False)
    ts.to_csv(OUT/'flow_scores.csv')
    ts0=tr[ind&tr.first_five_in_period].groupby(['product','link','method']).apply(summary,include_groups=False)
    ts0.to_csv(OUT/'period_start_flow_scores.csv')
    rs=rr[rr.phase.eq('test')].groupby(['product','method']).apply(summary,include_groups=False)
    rs.to_csv(OUT/'rhs_scores.csv')
    def risk_score(g):
        truth=g.economic_bind
        significant=(g.call=='at risk'); uncertain=(g.call=='uncertain'); clear=(g.call=='clear')
        return pd.Series(dict(n=len(g),economic_bind=truth.sum(),economic_episodes=count_episodes(g,truth),confirmed_bind=(truth&significant).sum(),
                 missed_bind=(truth&clear).sum(),uncertain_bind=(truth&uncertain).sum(),false_alert=(~truth&significant).sum(),
                 uncertain=uncertain.sum(),clear=clear.sum(),band=g.band.iat[0],band_covered=(g.headroom_error.abs()<=g.band+1e-9).sum(),
                 issued_economic_true_positive=(truth&g.issued_economic_bind).sum(),
                 issued_economic_false_positive=(~truth&g.issued_economic_bind).sum(),
                 issued_economic_false_negative=(truth&~g.issued_economic_bind).sum()))
    bits=rr[rr.phase.eq('test')].groupby(['product','method']).apply(risk_score,include_groups=False)
    bits.to_csv(OUT/'binding_scores.csv')
    print(rs.to_string());print(ts.xs(DIRECT,level='link').to_string());print(bits.xs('issued AEMO RHS',level='method').to_string())

def count_episodes(g,x):
    t=g.loc[x,'end'].sort_values()
    return int((t.diff()!=pd.Timedelta(minutes=5)).sum())

if __name__=='__main__':
    if '--download' in sys.argv: download()
    calculate()
