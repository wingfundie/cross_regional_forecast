"""Bango thermal-formulation fixed-window public-data feasibility experiment."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import struct
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pandas as pd
from lxml import etree

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT/'local_exports/rhs_forward_feb26'))
import study as pilot
EQ='N>999_9GL_NIL'
DUID=['BANGOWF1','GOONSF1','JEMALNG1','PARSF1']
BETA=np.array([1,.266,.375,.266])
MVA='MVA_BAN_9GL'
RATING='NRATCN_BANYS9GL'
FEATURES=[RATING,MVA,*DUID]
REG=['TOTALDEMAND','SS_WIND_CLEAREDMW','SS_SOLAR_CLEAREDMW']
TRAIN=range(9,16)
EVAL=[19,20,22]
DEFDATE='2025/12/02 00:00:00'
SCALE=1.197
BASE='https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/2026/NEMDE_2026_02/NEMDE_Market_Data/NEMDE_Files/'
def write(df,name):
    body=df.to_csv(index=False).encode()
    if len(body)>10_000_000:raise ValueError('Oversize result')
    (OUT/name).write_bytes(body)
def roots(t):
    return t.find('NemSpdInputs'),t.find('NemSpdOutputs')
def case_values(day):
    date=f'202602{day:02d}'
    url=BASE+'NemSpdOutputs_'+date+'_loaded.zip'
    start,cat=pilot.directory(url)
    picks=[i for i in cat if any(f'{date}{n:03d}00.loaded' in i.filename for n in range(73,97))]
    assert len(picks)==24
    low=start+picks[0].header_offset
    high=start+cat[cat.index(picks[-1])+1].header_offset-1
    block,head=pilot.fetch(url,f'{low}-{high}',cap=22_000_000);assert head.startswith(f'bytes {low}-{high}/')
    observations=[]
    for item in picks:
        o=start+item.header_offset-low
        assert block[o:o+4]==b'PK\x03\x04'
        nn,extra=struct.unpack_from('<HH',block,o+26); off=o+30+nn+extra
        val=block[off:off+item.compress_size]
        if item.compress_type==8:val=zlib.decompress(val,-15)
        assert len(val)==item.file_size and zlib.crc32(val)==item.CRC
        if val.startswith(b'PK'):
            z=ZipFile(io.BytesIO(val));val=z.read(z.namelist()[0])
        case=etree.fromstring(val);i,out=roots(case)
        p=i.find('.//Period');ts=pd.Timestamp(p.get('PeriodID')).tz_localize(None)
        if 'rating-panel' in sys.argv:
            rated={e.get('SpdID'):float(e.get('Value')) for e in p.iter('EnteredValuePeriod') if 'RAT' in e.get('SpdID','') and e.get('Value') is not None}
            observations.append(dict(end=ts,member=item.filename,xml_sha256=pilot.sha(val),**rated))
            continue
        row=dict(end=ts,source=url,member=item.filename,xml_sha256=pilot.sha(val))
        entity=i.find(f'.//GenericConstraint[@ConstraintID="{EQ}"]')
        sol=out.find(f'.//ConstraintSolution[@ConstraintID="{EQ}"][@Intervention="0"]')
        if i.find('Case').get('Intervention')!='False' or entity is None or sol is None:
            observations.append(dict(row,invoked=False));continue
        assert entity.get('Version')==sol.get('Version')=='20251202000000_1'
        analog=i.find(f'.//ScadaValues[@SpdID="{MVA}"]')
        assert analog.get('Can_Use_Value')=='True'
        row.update(invoked=True,sensor_time=analog.get('EMS_TimeStamp'),rhs=float(sol.get('RHS')),
                   marginal=float(sol.get('MarginalValue')),violation=float(sol.get('Deficit')))
        row[MVA]=float(analog.get('Value'));row[RATING]=float(p.find(f'.//EnteredValuePeriod[@SpdID="{RATING}"]').get('Value'))
        for uid in DUID:
            plant=i.find(f'.//Trader[@TraderID="{uid}"]')
            row[uid]=float(plant.find('.//TraderInitialCondition[@InitialConditionID="InitialMW"]').get('Value'))
        row['formula_rhs']=float(SCALE*(row[RATING]-row[MVA]-10)+sum(row[k]*w for k,w in zip(DUID,BETA)))
        assert abs(row['formula_rhs']-row['rhs'])<0.00002,(ts,row['formula_rhs'],row['rhs'])
        observations.append(row)
    return observations
def case_capture():
    obs=[x for result in ThreadPoolExecutor(3).map(case_values,[*TRAIN,*EVAL]) for x in result]
    write(pd.DataFrame(obs),'case_observations.csv')
    print(pd.DataFrame(obs).groupby(pd.to_datetime([x['end'] for x in obs]).day).invoked.sum())
if __name__=='__main__' and 'cases' in sys.argv:case_capture()

def forecast(job):
    kind,stamp,slots=job; issued,mod=pilot.forecast_file(kind,stamp)
    rows={}
    for created,table,r in pilot.unpack(issued):
        if r.get('INTERVENTION','0')!='0':continue
        end=r.get('DATETIME') or r.get('INTERVAL_DATETIME')
        if end not in slots:continue
        row=rows.setdefault(end,{})
        if r.get('REGIONID')=='NSW1' and 'TOTALDEMAND' in r:
            row.update({k:float(r[k]) for k in REG})
        if r.get('CONSTRAINTID')==EQ:
            assert r['GENCONID_EFFECTIVEDATE']==DEFDATE and r['GENCONID_VERSIONNO']=='1'
            row['official']=float(r['RHS']);row['official_lhs']=float(r['LHS'])
    n=issued.namelist()[0]
    return [dict(run=n,created=created,modified=mod,product=kind,end=pd.Timestamp(t),**v) for t,v in rows.items()]
def parse_public_start(item):
    run,issue=item
    # Dispatch files are often produced before their interval-ending label.
    # Choose the latest pair with both original members time-stamped before this issue.
    for stamp in (issue.ceil('5min'),issue.floor('5min')):
        members={}
        for folder,token in [('Dispatch_SCADA','DISPATCHSCADA'),('DispatchIS_Reports','DISPATCHIS')]:
            url=pilot.BASE+f'{folder}/PUBLIC_{token}_{stamp:%Y%m%d}.zip'
            z,mod=pilot.onefile(url,f'PUBLIC_{token}_{stamp:%Y%m%d%H%M}_')
            with io.TextIOWrapper(z.open(z.namelist()[0])) as f:
                h=next(csv.reader(f))
            if max(pd.Timestamp(' '.join(h[5:7])),mod)>issue:break
            members[token]=(z,mod)
        if len(members)==2:break
    assert len(members)==2
    ans=dict(run=run,reference_end=stamp)
    for token,(z,mod) in members.items():
        with io.TextIOWrapper(z.open(z.namelist()[0])) as f:
            rd=csv.reader(f);h=next(rd);created=pd.Timestamp(' '.join(h[5:7])); assert max(created,mod)<=issue
            ans[token+'_created']=created;ans[token+'_modified']=mod;ans[token+'_member']=z.namelist()[0]
            headers={}
            for line in rd:
                if line[0]=='I':headers[line[2]]=line[4:]
                elif line[0]=='D' and line[2] in ('UNIT_SCADA','CONSTRAINT','REGIONSUM'):
                    r=dict(zip(headers[line[2]],line[4:]))
                    if r.get('DUID') in DUID and line[2]=='UNIT_SCADA':ans[r['DUID']]=float(r['SCADAVALUE'])
                    if r.get('INTERVENTION','0')!='0':continue
                    if r.get('CONSTRAINTID')==EQ and r['GENCONID_EFFECTIVEDATE']==DEFDATE and r['GENCONID_VERSIONNO']=='1':ans['rhs']=float(r['RHS'])
                    if r.get('REGIONID')=='NSW1':ans.update({k:float(r[k]) for k in REG})
    return ans
def regions(day):
    date=f'202602{day:02d}'
    url=pilot.BASE+'DispatchIS_Reports/PUBLIC_DISPATCHIS_'+date+'.zip'
    data,_=pilot.fetch(url)
    arc=ZipFile(io.BytesIO(data));result=[];targets=pilot.targets(day)
    relevant={x.strftime('%Y%m%d%H%M') for x in [targets[0]-pd.Timedelta(minutes=5),*targets]}
    for info in arc.infolist():
        stamp=info.filename.split('_')[2]
        if stamp not in relevant:continue
        blob=arc.read(info);z=ZipFile(io.BytesIO(blob));end=pd.to_datetime(stamp,format='%Y%m%d%H%M')
        rec=dict(end=end,source=url,member=info.filename,member_sha256=pilot.sha(blob),archive_sha256=pilot.sha(data),modified=pd.Timestamp(*info.date_time))
        for created,table,r in pilot.unpack(z):
            if r.get('INTERVENTION','0')!='0':continue
            if r.get('REGIONID')=='NSW1' and 'TOTALDEMAND' in r:
                rec.update({k:float(r[k]) for k in REG});rec['created']=created
            if r.get('CONSTRAINTID')==EQ and r['GENCONID_EFFECTIVEDATE']==DEFDATE and r['GENCONID_VERSIONNO']=='1':
                rec['lhs']=float(r['LHS']);rec['public_rhs']=float(r['RHS'])
        result.append(rec)
    return result
def capture_forecasts():
    jobs=[]
    for day in EVAL:
        ends=pilot.targets(day)
        jobs.append(('PREDISPATCHIS',pd.Timestamp(f'2026-02-{day-1} 16:30'),pilot.timeset(ends[5::6])))
        for k in range(4):
            six=ends[k*6:k*6+6]
            jobs.append(('P5MIN',six[0]-pd.Timedelta(minutes=30),pilot.timeset([six[0]-pd.Timedelta(minutes=5),*six])))
    fc=pd.DataFrame([r for rr in ThreadPoolExecutor(3).map(forecast,jobs) for r in rr])
    assert fc[REG].notna().all().all()
    write(fc,'issued.csv')
    orig=pd.DataFrame(ThreadPoolExecutor(3).map(parse_public_start,fc.groupby('run').created.first().items()))
    write(orig,'origin.csv')
    (OUT/'forecast_sources.json').write_text(json.dumps(pilot.log,indent=2))
def capture_regions():
    hist=pd.DataFrame([r for rr in ThreadPoolExecutor(4).map(regions,[*TRAIN,*EVAL]) for r in rr])
    write(hist,'regional_dispatch.csv')
if __name__=='__main__' and 'forecasts' in sys.argv:capture_forecasts()
if __name__=='__main__' and 'regions' in sys.argv:capture_regions()

if __name__=='__main__' and 'rating-panel' in sys.argv:
    rows=[x for rr in ThreadPoolExecutor(3).map(case_values,[*TRAIN,*EVAL]) for x in rr]
    write(pd.DataFrame(rows),'rating_panel.csv')

def model_rhs(x):
    return SCALE*(x[RATING]-x[MVA]-10)+sum(x[uid]*wt for uid,wt in zip(DUID,BETA))
def weighted(x):
    return sum(x[uid]*w for uid,w in zip(DUID,BETA))
def forecast_inputs_and_check():
    obs=pd.read_csv(OUT/'case_observations.csv',parse_dates=['end']);assert obs.invoked.all()
    regional=pd.read_csv(OUT/'regional_dispatch.csv',parse_dates=['end','created','modified']).set_index('end').sort_index()
    regional_lag=regional[REG].copy();regional_lag.index=regional_lag.index+pd.Timedelta(minutes=5)
    obs=obs.merge(regional_lag,left_on='end',right_index=True,validate='one_to_one').merge(regional[['lhs','public_rhs']],left_on='end',right_index=True)
    assert len(obs)==240 and (obs.rhs-obs.public_rhs).abs().max()<1e-5
    training=obs[obs.end.dt.day.isin(TRAIN)].copy();testing=obs[obs.end.dt.day.isin(EVAL)].copy()
    training['clock']=training.end.dt.ceil('30min').dt.time
    fc=pd.read_csv(OUT/'issued.csv',parse_dates=['end','created','modified'])
    origins=pd.read_csv(OUT/'origin.csv').set_index('run')
    assert training.end.max()+pd.Timedelta(days=1)<fc.created.min()
    assert not origins[[*DUID,'rhs']].isna().any().any()
    sens={MVA:-SCALE,RATING:SCALE,**dict(zip(DUID,BETA))}
    shares={k:training[k].sum()/training['SS_WIND_CLEAREDMW' if k==DUID[0] else 'SS_SOLAR_CLEAREDMW'].sum() for k in DUID}
    xcols=[*DUID,'TOTALDEMAND']
    design=np.column_stack([np.ones(len(training)),training[xcols].values])
    coef=np.linalg.lstsq(design,training[MVA],rcond=None)[0]
    def load_model(x):
        return coef[0]+sum(float(x[col])*c for col,c in zip(xcols,coef[1:]))
    pred=[]
    for _,truth in testing.iterrows():
        end=truth.end; slot=end.ceil('30min');clock=slot.time()
        normal=training[training.clock.eq(clock)]
        for mode,ff in fc.groupby('product'):
            if mode=='P5MIN':
                stamp=slot-pd.Timedelta(minutes=55)
                run=next(n for n in ff.run.unique() if stamp.strftime('%Y%m%d%H%M') in n.split('_')[2:3])
            else:
                run=next(n for n in ff.run.unique() if (end-pd.Timedelta(days=1)).strftime('%Y%m%d') in n.split('_')[2])
            runrows=ff[ff.run.eq(run)].set_index('end')
            met=runrows.loc[end-pd.Timedelta(minutes=5) if mode=='P5MIN' else slot]
            direct=runrows.loc[end if mode=='P5MIN' else slot]
            anchor=origins.loc[run]
            assert max(met.created,met.modified)<end-pd.Timedelta(minutes=5)
            for method in ('clock profile','regional generation shares','last public state','regional change from last public state','AEMO issued'):
                row=dict(end=end,slot=slot,issue=met.created,run=run,horizon=mode,method=method,
                         actual_rhs=truth.rhs,actual_lhs=truth.lhs,actual_bind=abs(truth.marginal)>1e-5)
                if method=='AEMO issued':
                    row.update(rhs=direct.get('official',np.nan),forward_lhs=direct.get('official_lhs',np.nan))
                else:
                    x={RATING:training[RATING].median(),'TOTALDEMAND':met.TOTALDEMAND}
                    for uid in DUID:
                        field='SS_WIND_CLEAREDMW' if uid==DUID[0] else 'SS_SOLAR_CLEAREDMW'
                        if method=='clock profile': value=normal[uid].mean()
                        elif method=='regional generation shares': value=shares[uid]*met[field]
                        elif method=='last public state': value=anchor[uid]
                        else: value=max(0.,anchor[uid]+shares[uid]*(met[field]-anchor[field]))
                        x[uid]=value
                    anchor_line=training[RATING].median()-10-(anchor.rhs-weighted(anchor))/SCALE
                    if method=='clock profile':x[MVA]=normal[MVA].mean()
                    elif method=='regional generation shares': x[MVA]=load_model(x)
                    elif method=='last public state':x[MVA]=anchor_line
                    else:x[MVA]=anchor_line+load_model(x)-load_model(anchor)
                    row.update(x);row.update(rhs=model_rhs(x),forward_lhs=weighted(x))
                    for k,c in sens.items():
                        row[k+'_error']=x[k]-truth[k]
                    if method=='last public state':assert abs(row['rhs']-anchor.rhs)<1e-7
                pred.append(row)
    preds=pd.DataFrame(pred);write(preds,'forecast_predictions.csv')
    assert preds.rhs.notna().all()
    ns=[];cs=[];bind=[]
    for (h,m),g in preds.groupby(['horizon','method']):
        a=g.groupby('slot').mean(numeric_only=True)
        err=a.rhs-a.actual_rhs
        cs.append(dict(horizon=h,method=m,n=len(err),mae=err.abs().mean(),bias=err.mean(),max_abs=err.abs().max(),native_5min_mae=(g.rhs-g.actual_rhs).abs().mean()))
        for k,c in sens.items():
            if m=='AEMO issued':continue
            e=a[k+'_error'];ns.append(dict(horizon=h,method=m,input=k,n=len(e),mae=e.abs().mean(),bias=e.mean(),one_at_a_time_rhs_mae=e.abs().mean()*abs(c)))
        for label,lhs in [('historical LHS held fixed',g.actual_lhs),('forward LHS',g.forward_lhs)]:
            alert=(g.rhs-lhs)<=.1
            ref=g.actual_bind.astype(bool)
            bind.append(dict(horizon=h,method=m,lhs=label,n=len(g),positives=int(ref.sum()),alerts=int(alert.sum()),hits=int((ref&alert).sum()),false_alerts=int((~ref&alert).sum()),missed=int((ref&~alert).sum())))
    write(pd.DataFrame(ns),'input_metrics.csv');write(pd.DataFrame(cs),'rhs_metrics.csv');write(pd.DataFrame(bind),'binding.csv')
    d=testing.copy()
    d['input_only_model']=[load_model(r) for _,r in d.iterrows()]
    d['clock_model']=[training.loc[training.clock.eq(t.ceil('30min').time()),MVA].mean() for t in d.end]
    d['slot']=d.end.dt.ceil('30min')
    write(d[['end','slot',MVA,'input_only_model','clock_model']],'terminal_diagnostic.csv')
    (OUT/'model.json').write_text(json.dumps(dict(training_dates=list(TRAIN),evaluation_dates=EVAL,rating=training[RATING].median(),unit_shares=shares,loading_regression=dict(zip(['constant',*xcols],coef))),indent=2))
    print(pd.DataFrame(cs).to_string(index=False))
if __name__=='__main__' and 'score' in sys.argv:forecast_inputs_and_check()
