"""Recreate the dated state, electrical quantity and outage proxy tests. NEM time throughout."""
from __future__ import annotations
import csv, hashlib, io, json, sys, struct, zlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT))
from functools import lru_cache
from nemic.common import session
ARCHIVE='https://www.nemweb.com.au/Reports/ARCHIVE/'

def fetch(url, byte_range):
    with session().get(url,headers={'Range':'bytes='+byte_range},timeout=(10,45),stream=True) as response:
        response.raise_for_status()
        if response.status_code!=206:raise ValueError('Expected byte range')
        buffer=io.BytesIO()
        for chunk in response.iter_content(262144):
            if buffer.tell()+len(chunk)>12_000_000:raise ValueError('Unexpected source size')
            buffer.write(chunk)
        return buffer.getvalue(),response.headers['Content-Range']

@lru_cache(maxsize=48)
def directory(url):
    tail,header=fetch(url,'-131072')
    return int(header.split()[1].split('-')[0]),ZipFile(io.BytesIO(tail)).infolist()

BASE='https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/2026/NEMDE_2026_02/NEMDE_Market_Data/NEMDE_Files/'
TRAIN=list(range(9,16))
TEST=[19,20,22]
DAYS=sorted(set(TRAIN+[17,18,19,20,21,22]))
ENDS=[(10,30),(11,0),(11,30),(12,0)]
POINTS={'BU_SH1_LINE_220KV':'bus voltage (kV)','APDLOAD_MVAR':'reactive load (MVAr)',
        'MORTLAKE_INERTIA':'generator inertia (source units)','BL_PREVDI_TARGET':'previous target (MW)'}
EXTRA={'OFFER_TAS1':'from-region offer (MW)','OFFER_VIC1':'to-region offer (MW)',
       'BL_SWITCH_SELECTED':'winning switch (state)','T^V_NIL_9':'timer equation RHS (MW)'}
INFO=pd.read_csv(ROOT/'reports/rhs_replay/inventory/inputs.csv',keep_default_na=False)
STATUS=set(INFO.loc[INFO.spd_type.eq('S'),'spd_id'])
SOURCES=[]
def digest(b):return hashlib.sha256(b).hexdigest()
def ts(day,h,m):return pd.Timestamp(year=2026,month=2,day=day,hour=h,minute=m)
def get_member(u,pattern):
    start,entries=directory(u)
    entry,=[e for e in entries if e.filename.startswith(pattern)]
    off=start+entry.header_offset
    b,r=fetch(u,f'{off}-{off+entry.compress_size+len(entry.filename)+len(entry.extra)+550}')
    assert r.startswith(f'bytes {off}-') and b[:4]==b'PK\x03\x04'
    a,c=struct.unpack_from('<HH',b,26); b=b[30+a+c:30+a+c+entry.compress_size]
    raw=zlib.decompress(b,-15) if entry.compress_type==8 else b
    assert zlib.crc32(raw)==entry.CRC and len(raw)==entry.file_size
    SOURCES.append(dict(url=u,member=entry.filename,bytes=len(raw),sha256=digest(raw),member_modified=str(datetime(*entry.date_time))))
    return raw,datetime(*entry.date_time)
def case(dt):
    u=BASE+f'NemSpdOutputs_{dt:%Y%m%d}_loaded.zip'
    num=(dt.hour*60+dt.minute-240)//5; raw,modified=get_member(u,f'NEMSPDOutputs_{dt:%Y%m%d}{num:03d}00.loaded')
    root=ET.fromstring(raw);i=root.find('NemSpdInputs');o=root.find('NemSpdOutputs')
    assert pd.Timestamp(i.find('.//Period').get('PeriodID')).tz_localize(None)==dt
    assert i.find('Case').get('Intervention')=='False'
    vals={}; flags={}
    for typ,points in [('S',STATUS),('A',POINTS)]:
        for el in i.findall(f'.//ConstraintScadaData[@SpdType="{typ}"]/ScadaValuesCollection/ScadaValues'):
            name=el.get('SpdID')
            if name in points and el.get('Can_Use_Value')=='True':
                value=float(el.get('Value'))
                if typ=='S' and value not in (0.,1.):continue
                if name in vals:raise ValueError('Duplicate '+name)
                vals[name]=value
    bl=i.find('.//InterconnectorPeriod[@InterconnectorID="T-V-MNSP1"]')
    for e in bl.findall('.//MNSPOffer'):vals['OFFER_'+e.get('RegionID')]=float(e.get('MaxAvail'))
    vals['BL_SWITCH_SELECTED']=int(o.find('.//PeriodSolution[@Intervention="0"]').get('SwitchRunBestStatus'))
    vals['T^V_NIL_9']=float(o.find('.//ConstraintSolution[@ConstraintID="T^V_NIL_9"][@Intervention="0"]').get('RHS'))
    assert abs(vals['T^V_NIL_9']-(594-244*vals['GTOWN_FL_TIMER']))<1e-5
    vals['case_time']=dt
    # The dispatch case tracks invoked sets on equations in the period.
    active_ids={e.get('ConstraintID') for e in i.findall('.//GenericConstraintPeriod')}
    sets=sorted({t.get('GenConSetID') for e in i.findall('.//GenericConstraint') if e.get('ConstraintID') in active_ids
                 for t in e.findall('.//ConstraintTrkItem') if t.get('Intervention')=='False'})
    return vals,dict(case_time=dt,sets='|'.join(sets))
def time_fields(stamp,kind):
    if kind=='dispatch':
        u=ARCHIVE+f'DispatchIS_Reports/PUBLIC_DISPATCHIS_{stamp:%Y%m%d}.zip'
        zp,mtime=get_member(u,f'PUBLIC_DISPATCHIS_{stamp:%Y%m%d%H%M}_')
    elif kind=='scada':
        u=ARCHIVE+f'Dispatch_SCADA/PUBLIC_DISPATCHSCADA_{stamp:%Y%m%d}.zip'
        zp,mtime=get_member(u,f'PUBLIC_DISPATCHSCADA_{stamp:%Y%m%d%H%M}_')
    else:
        if kind=='P5MIN':u=ARCHIVE+f'P5_Reports/PUBLIC_P5MIN_{stamp:%Y%m%d}.zip'
        else:
            sunday=stamp-pd.Timedelta(days=(stamp.weekday()+1)%7)
            last=sunday+pd.Timedelta(days=6)
            u=ARCHIVE+f'PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_{sunday:%Y%m%d}_{last:%Y%m%d}.zip'
        zp,mtime=get_member(u,f'PUBLIC_{kind}_{stamp:%Y%m%d%H%M}_')
    z=ZipFile(io.BytesIO(zp));return z.read(z.namelist()[0]),mtime
def get_dispatch(stamp,which):
    b,m=time_fields(stamp,'dispatch');z=csv.reader(io.TextIOWrapper(io.BytesIO(b),encoding='utf-8-sig'))
    hd=next(z);created=pd.Timestamp(' '.join(hd[5:7])); header={}
    result={'created':created,'modified':m,'endpoint':stamp}
    for r in z:
        if r[0]=='I':header[r[2]]=r[4:]
        elif r[0]=='D' and r[2] in ('REGIONSUM','CONSTRAINT','INTERCONNECTORRES'):
            d=dict(zip(header[r[2]],r[4:]))
            if d.get('INTERVENTION')!='0':continue
            if d.get('REGIONID'):result[d['REGIONID']]=float(d['TOTALDEMAND'])
            if d.get('CONSTRAINTID')=='T^V_NIL_9': result['timer_rhs']=float(d['RHS'])
            if d.get('INTERCONNECTORID')=='T-V-MNSP1':result['target']=float(d['MWFLOW'])
    return result
def get_scada(stamp):
    b,m=time_fields(stamp,'scada');z=csv.reader(io.TextIOWrapper(io.BytesIO(b),encoding='utf-8-sig'))
    hd=next(z);created=pd.Timestamp(' '.join(hd[5:7]));result={}
    for r in z:
        if r[0]=='I':h=r[4:]
        if r[0]=='D' and (('MORTLK11' in r) or ('MORTLK12' in r)):
            d=dict(zip(h,r[4:]));result[d['DUID']]=float(d['SCADAVALUE'])
    assert set(result)=={'MORTLK11','MORTLK12'}
    return dict(scada_created=created,scada_modified=m,**result)
def get_fc(spec):
    product,dt,stamp=spec;raw,m=time_fields(stamp,product);z=csv.reader(io.TextIOWrapper(io.BytesIO(raw),encoding='utf-8-sig'))
    hd=next(z);created=pd.Timestamp(' '.join(hd[5:7])); origin=max(pd.Timestamp(m),created)
    assert origin < dt-pd.Timedelta(minutes=5)
    h={}; result=dict(product=product,end=dt,origin=origin,issued=created)
    for row in z:
        if row[0]=='I':h[row[2]]=row[4:]
        elif row[0]=='D' and row[2] in ('REGIONSOLUTION','REGION_SOLUTION','CONSTRAINTSOLUTION','CONSTRAINT_SOLUTION','INTERCONNECTORSOLN','INTERCONNECTOR_SOLN'):
            r=dict(zip(h[row[2]],row[4:])); t=r.get('DATETIME',r.get('INTERVAL_DATETIME'))
            if r.get('INTERVENTION')!='0' or t not in {dt.strftime('%Y/%m/%d %H:%M:%S'),(dt-pd.Timedelta(minutes=5)).strftime('%Y/%m/%d %H:%M:%S')}:continue
            same=t==dt.strftime('%Y/%m/%d %H:%M:%S')
            if same and 'REGIONID'in r:result[r['REGIONID']]=float(r['TOTALDEMAND'])
            if same and r.get('CONSTRAINTID')=='T^V_NIL_9':result['issued_timer_rhs']=float(r['RHS'])
            if r.get('INTERCONNECTORID')=='T-V-MNSP1' and ((product=='P5MIN' and not same) or (product=='PREDISPATCHIS' and same)):
                result['issued_bl_prev_target']=float(r['MWFLOW'])
    return dict(**result,**get_anchor(origin))

@lru_cache(maxsize=128)
def get_anchor(origin):
    reference=origin.ceil('5min')
    latest=get_dispatch(reference,'dispatch')
    scada=get_scada(reference)
    if max(latest['created'],latest['modified'],scada['scada_created'],scada['scada_modified'])>origin:
        reference=reference-pd.Timedelta(minutes=5)
        latest=get_dispatch(reference,'dispatch')
        scada=get_scada(reference)
    assert max(latest['created'],latest['modified'],scada['scada_created'],scada['scada_modified'])<=origin
    return dict(anchor_timer_rhs=latest['timer_rhs'],anchor_target=latest['target'],anchor_end=reference,
                anchor_created=latest['created'],anchor_modified=latest['modified'],**scada)
def capture():
    instants=[ts(day,h,m) for day in DAYS for h,m in ENDS]
    raw=list(ThreadPoolExecutor(4).map(case,instants))
    a=pd.DataFrame([v for v,s in raw]).set_index('case_time')
    pd.DataFrame([s for v,s in raw]).to_csv(OUT/'case_sets.csv',index=False)
    # Earlier dated training region demand and plant labels are dispatch-only.
    def pair(t):return dict(case_time=t,**get_dispatch(t,'dispatch'),**get_scada(t))
    hist=pd.DataFrame(ThreadPoolExecutor(4).map(pair,[x for x in instants if x.day in TRAIN])).set_index('case_time')
    a.join(hist).to_csv(OUT/'case_points.csv',na_rep='')
    specs=[]
    for day in TEST:
        for h,m in ENDS:
            dt=ts(day,h,m)
            specs.extend([('P5MIN',dt,dt-pd.Timedelta(minutes=55)),
                          ('PREDISPATCHIS',dt,ts(day-1,16,30))])
    pd.DataFrame(ThreadPoolExecutor(3).map(get_fc,specs)).to_csv(OUT/'issue_data.csv',index=False)
    verify_previous_target()
    publish_sources(SOURCES)
def publish_sources(records):
    issues=pd.read_csv(OUT/'issue_data.csv',parse_dates=['end','anchor_end'])
    anchor_stamps=set(issues.anchor_end.dt.strftime('%Y%m%d%H%M'))
    training_stamps={ts(d,h,m).strftime('%Y%m%d%H%M') for d in TRAIN for h,m in ENDS}
    check_stamps={(ts(d,h,m)-pd.Timedelta(minutes=5)).strftime('%Y%m%d%H%M') for d in TEST for h,m in ENDS}
    canonical={}
    for rec in records:
        name=rec['member']
        if name.startswith(('PUBLIC_DISPATCHIS_','PUBLIC_DISPATCHSCADA_')):
            stamps=anchor_stamps|training_stamps
            if name.startswith('PUBLIC_DISPATCHIS_'):stamps=stamps|check_stamps
            if name.split('_')[2] not in stamps:continue
        canonical[name]=dict(url=rec['url'],member=name,sha256=rec.get('sha256') or rec['member_sha256'],
                             member_modified=pd.Timestamp(rec['member_modified']).isoformat())
    ordered=[canonical[k] for k in sorted(canonical)]
    (OUT/'sources.json').write_text(json.dumps(ordered,indent=2))
    validation=[r for r in ordered if r['member'].startswith('PUBLIC_DISPATCHIS_') and r['member'].split('_')[2] in check_stamps]
    (OUT/'validation_sources.json').write_text(json.dumps(validation,indent=2))

def verify_previous_target():
    cases=pd.read_csv(OUT/'case_points.csv',index_col='case_time',parse_dates=['case_time'])
    ends=[t for t in cases.index if t.day in TEST]
    records=list(ThreadPoolExecutor(3).map(lambda t:get_dispatch(t-pd.Timedelta(minutes=5),'dispatch'),ends))
    pd.DataFrame([dict(end=t,case_previous_target=cases.at[t,'BL_PREVDI_TARGET'],dispatch_target_previous_5min=r['target'],
                       signed_difference=cases.at[t,'BL_PREVDI_TARGET']-r['target']) for t,r in zip(ends,records)]).to_csv(OUT/'previous_target_validation.csv',index=False)

def evaluate():
    cases=pd.read_csv(OUT/'case_points.csv',index_col='case_time',parse_dates=['case_time'])
    iss=pd.read_csv(OUT/'issue_data.csv',parse_dates=['end','origin'])
    hist=cases[cases.index.day.isin(TRAIN)]
    rows=[]; digital=[]
    for _,r in iss.iterrows():
        t=r.end
        prior=t-pd.Timedelta(days=1 if r['product']=='P5MIN' else 2)
        obs=cases.loc[t]; anchor=cases.loc[prior]
        byclock=hist[hist.index.time==t.time()]
        def add(k,method,y):
            if pd.isna(y) or pd.isna(obs[k]):return
            rows.append(dict(product=r['product'],end=t,origin=r.origin,point=k,method=method,actual=obs[k],estimate=y))
        for k in list(POINTS)+list(EXTRA):
            add(k,'Prior public case at same clock',anchor[k])
            base=byclock[k].dropna()
            if not base.empty:
                add(k,'Training clock reference',base.mode().iloc[0] if k in ('BL_SWITCH_SELECTED','MORTLAKE_INERTIA') else base.median())
        for k,region in [('BU_SH1_LINE_220KV','TAS1'),('APDLOAD_MVAR','VIC1')]:
            eligible=hist[[region,k]].dropna()
            nearest=(eligible[region]-r[region]).abs().sort_values().index[:3]
            add(k,'Three closest training regional demands',eligible.loc[nearest,k].mean())
        eligible=hist.dropna(subset=['MORTLAKE_INERTIA','MORTLK11','MORTLK12'])
        mask=(eligible.MORTLK11.gt(5)==(r.MORTLK11>5)) & (eligible.MORTLK12.gt(5)==(r.MORTLK12>5))
        matched=eligible.loc[mask,'MORTLAKE_INERTIA']
        if len(matched):add('MORTLAKE_INERTIA','Origin plant output state',matched.median())
        # A zero prior transfer can indicate an inactive frequency switch; it does not identify a zero offer.
        close_to_zero=abs(r.issued_bl_prev_target)<0.1
        switch_hist=hist.loc[hist.BL_PREVDI_TARGET.abs().lt(.1)==close_to_zero,'BL_SWITCH_SELECTED'].dropna()
        if len(switch_hist):add('BL_SWITCH_SELECTED','Issued transfer class and training switch mode',switch_hist.mode().iloc[0])
        add('BL_PREVDI_TARGET','Last dispatch target at origin',r.anchor_target)
        add('BL_PREVDI_TARGET','Issued prior-step or half-hour target',r.issued_bl_prev_target)
        add('T^V_NIL_9','Latest dispatch timer RHS',r.anchor_timer_rhs)
        add('T^V_NIL_9','Issued equation RHS',r.issued_timer_rhs)
        for k in sorted(STATUS.intersection(cases.columns)):
            if pd.isna(obs[k]) or pd.isna(anchor[k]) or byclock[k].dropna().empty:continue
            mode=byclock[k].dropna().mode().iloc[0]
            digital.append(dict(product=r['product'],end=t,origin=r.origin,point=k,
                                actual=int(obs[k]),prior_case=int(anchor[k]),clock_mode=int(mode)))
    a=pd.DataFrame(rows)
    a.to_csv(OUT/'predictions.csv',index=False)
    a['error']=a.estimate-a.actual
    a['abs_error']=a.error.abs()
    a.groupby(['product','point','method']).agg(n=('error','count'),mae=('abs_error','mean'),bias=('error','mean'),max_abs=('abs_error','max'),truth_min=('actual','min'),truth_max=('actual','max')).reset_index().to_csv(OUT/'metrics.csv',index=False)
    bands=[]
    for k in list(POINTS)+list(EXTRA):
        lo,hi=hist[k].min(),hist[k].max()
        held=cases.loc[cases.index.day.isin(TEST),k].dropna()
        bands.append(dict(point=k,training_n=hist[k].count(),lo=lo,hi=hi,width=hi-lo,n=len(held),covered=held.between(lo,hi).sum()))
    pd.DataFrame(bands).to_csv(OUT/'training_envelopes.csv',index=False)
    s=pd.DataFrame(digital)
    s.to_csv(OUT/'status_predictions.csv',index=False)
    s['prior_miss']=s.actual!=s.prior_case;s['clock_miss']=s.actual!=s.clock_mode
    s.groupby('product').agg(n=('actual','count'),points=('point','nunique'),prior_miss=('prior_miss','sum'),clock_miss=('clock_miss','sum')).to_csv(OUT/'status_metrics.csv')
    s.groupby(['product','prior_miss']).agg(n=('actual','count'),clock_miss=('clock_miss','sum')).to_csv(OUT/'status_change_metrics.csv')
    outage(iss)

def outage(iss):
    base=ROOT/'data/forecast_experiments/vni_diurnal_nos_v2/nos/weeks'
    weeks={}
    manifest=[]
    for day in (13,20):
        folder=base/f'PUBLIC_NETWORK_202602{day}'
        reports=pd.read_parquet(folder/'reports.parquet').set_index('generated_nem')
        changes=pd.read_parquet(folder/'changes.parquet').sort_values('generated_nem')
        rows=pd.read_parquet(folder/'rows.parquet')
        data={r.row_id:(r.table,json.loads(r.fields_json)) for r in rows.itertuples()}
        weeks[day]=reports,changes,data
        md=json.loads((folder/'manifest.json').read_text());manifest.append(dict(url=md['url'],archive_sha256=md['raw_sha256']))
    sets=pd.read_csv(OUT/'case_sets.csv',parse_dates=['case_time']).set_index('case_time').sets
    out=[]
    closed={'WDRAWN','CANCELLED','COMPLETE','COMPLETED','REPLACED','RESUBMIT'}
    for _,r in iss.iterrows():
        origin=r.origin;t=r.end
        reports,changes,data=weeks[20 if origin.day>=20 else 13]
        snap=reports.index[reports.index<=origin-pd.Timedelta(minutes=2)].max()
        states=changes.loc[changes.generated_nem<=snap].drop_duplicates('row_id',keep='last')
        current=[data[k] for k in states.loc[states.present,'row_id']]
        universe={d['GENCONSETID'] for tab,d in current if tab=='OUTAGECONSTRAINTSET'}
        ids={d['OUTAGEID'] for tab,d in current if tab=='OUTAGEDETAIL'}
        eligible=set()
        for tab,d in current:
            if tab!='OUTAGEDETAIL' or d['OUTAGESTATUSCODE'] in closed or d.get('RESUBMITOUTAGEID') in ids:continue
            # Use actual timestamps only if reported in the cutoff snapshot and already reached.
            fmt='%Y/%m/%d %H:%M:%S'
            now=origin.strftime(fmt); target=t.strftime(fmt)
            start=d.get('ACTUAL_STARTTIME') or ''
            start=start if start and start<=now else d['STARTTIME']
            end=d.get('ACTUAL_ENDTIME') or ''
            end=end if end and end<=now else d['ENDTIME']
            if start and end and start<target<=end:eligible.add(d['OUTAGEID'])
        pred={d['GENCONSETID'] for tab,d in current if tab=='OUTAGECONSTRAINTSET' and d['OUTAGEID'] in eligible and
              (not d['STARTINTERVAL'] or d['STARTINTERVAL']<=target) and (not d['ENDINTERVAL'] or d['ENDINTERVAL']>=target)}
        actual=set(sets[t].split('|'))
        prior=set(sets[t-pd.Timedelta(days=1 if r['product']=='P5MIN' else 2)].split('|'))
        for name in sorted(universe):
            out.append(dict(product=r['product'],end=t,origin=origin,network_report=snap,member=reports.loc[snap,'member'],
                            constraint_set=name,actual=int(name in actual),scheduled=int(name in pred),prior_case=int(name in prior)))
    z=pd.DataFrame(out);z.to_csv(OUT/'outage_predictions.csv',index=False)
    m=[]
    for product,g in z.groupby('product'):
        for meth in ('scheduled','prior_case'):
            tp=int(((g.actual==1)&(g[meth]==1)).sum())
            fp=int(((g.actual==0)&(g[meth]==1)).sum())
            fn=int(((g.actual==1)&(g[meth]==0)).sum())
            m.append(dict(product=product,method=meth,n=len(g),sets=g.constraint_set.nunique(),tp=tp,fp=fp,fn=fn,precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None))
    pd.DataFrame(m).to_csv(OUT/'outage_metrics.csv',index=False)
    (OUT/'outage_sources.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':
    if '--refetch' in sys.argv or not (OUT/'issue_data.csv').exists():capture()
    evaluate()
