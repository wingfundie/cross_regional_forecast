"""Small forward RHS pilot. All market times in fixed UTC+10."""
from pathlib import Path
import io,csv,json,hashlib,struct,zlib
from datetime import datetime,timedelta
from zipfile import ZipFile
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from nemic.common import session
import pandas as pd
import numpy as np

OUT=Path(__file__).resolve().parent
BASE="https://www.nemweb.com.au/Reports/ARCHIVE/"
log=[]
def sha(b): return hashlib.sha256(b).hexdigest()
def fetch(u, byte_range=None, cap=12_000_000):
    with session().get(u,headers={"Range":"bytes="+byte_range} if byte_range else {},timeout=(10,45),stream=True) as r:
        r.raise_for_status()
        if byte_range and r.status_code!=206: raise ValueError("Expected byte range")
        p=io.BytesIO()
        for c in r.iter_content(262144):
            if p.tell()+len(c)>cap:raise ValueError("Unexpected source size")
            p.write(c)
        return p.getvalue(),r.headers.get("Content-Range","")
@lru_cache(maxsize=12)
def directory(u):
    tail,head=fetch(u,"-131072")
    start=int(head.split()[1].split("-")[0])
    return start,ZipFile(io.BytesIO(tail)).infolist()
def onefile(u,pattern):
    start,cat=directory(u)
    i,=[i for i in cat if i.filename.startswith(pattern)]
    offset=start+i.header_offset
    high=offset+i.compress_size+30+len(i.filename)+len(i.extra)+512
    b,header=fetch(u,f"{offset}-{high}")
    assert header.startswith(f"bytes {offset}-") and b[:4]==b"PK\x03\x04"
    nn,ex=struct.unpack_from("<HH",b,26); p=30+nn+ex
    c=b[p:p+i.compress_size]
    v=zlib.decompress(c,-15) if i.compress_type==8 else c
    assert len(v)==i.file_size and zlib.crc32(v)==i.CRC
    log.append(dict(url=u,member=i.filename,member_sha256=sha(v),member_modified=datetime(*i.date_time).isoformat()))
    return ZipFile(io.BytesIO(v)),datetime(*i.date_time)
def forecast_file(kind,stamp):
    if kind=="P5MIN":
        url=BASE+f"P5_Reports/PUBLIC_P5MIN_{stamp:%Y%m%d}.zip"
    else:
        sun=stamp-timedelta(days=(stamp.weekday()+1)%7)
        url=BASE+f"PredispatchIS_Reports/PUBLIC_PREDISPATCHIS_{sun:%Y%m%d}_{sun+timedelta(days=6):%Y%m%d}.zip"
    return onefile(url,f"PUBLIC_{kind}_{stamp:%Y%m%d%H%M}_")
if __name__=="__main__" and "--inspect" in sys.argv:
    for kind,stamp in [('PREDISPATCHIS','2026-02-18 16:30'),('P5MIN','2026-02-19 09:35')]:
        z,dt=forecast_file(kind,pd.Timestamp(stamp));f=io.TextIOWrapper(z.open(z.namelist()[0]),encoding='utf-8-sig')
        seen=set()
        for r in csv.reader(f):
            if r[0]=='C' and len(r)>5:print(r)
            if len(r)>3 and r[0]=='I' and any(k in r[2] for k in ('REGION','CONSTRAINT','INTERCONNECTOR')): print(r[:15],' ... ',[v for v in r if v in ['DATETIME','INTERVAL_DATETIME','GENCONID_EFFECTIVEDATE','METEREDMWFLOW','MWFLOW','RHS','RUNCODE','TOTALDEMAND']])
            if r[0]=='D' and any(v in r for v in ('DATASNAP_DFS_NSYD','DATASNAP_TE_967_1','N::Q_NIL_KC')) and r[2]+next(v for v in r if v in ('DATASNAP_DFS_NSYD','DATASNAP_TE_967_1','N::Q_NIL_KC')) not in seen:
                k=next(v for v in r if v in ('DATASNAP_DFS_NSYD','DATASNAP_TE_967_1','N::Q_NIL_KC'));print(r[:23]);seen.add(r[2]+k)

CTRL='DATASNAP_DFS_NSYD'
TER='DATASNAP_TE_967_1'
KC='N::Q_NIL_KC'
LABELS={CTRL:'sydney',TER:'terr',KC:'rhs'}
ISSUED='Issued AEMO'
POP='Population share'
SHARE='Fixed historical share'
CLOCK='Clock and day-type share'
LEVEL='Clock and day-type level'
TRDAYS=list(range(9,16))
TEDAYS=[19,20,22]
def targets(day):
    return pd.date_range(f'2026-02-{day:02d} 10:05',periods=24,freq='5min')
def unpack(z):
    with io.TextIOWrapper(z.open(z.namelist()[0]),encoding='utf-8-sig') as f:
        rd=csv.reader(f);head=next(rd);issued=pd.Timestamp(' '.join(head[5:7]));headers={}
        for r in rd:
            if r[0]=='I': headers[r[2]]=r[4:]
            elif r[0]=='D' and r[2] in {'REGIONSUM','REGION_SOLUTION','REGIONSOLUTION','CONSTRAINT','CONSTRAINT_SOLUTION','CONSTRAINTSOLUTION','INTERCONNECTORRES','INTERCONNECTOR_SOLN','INTERCONNECTORSOLN'}:
                yield issued,r[2],dict(zip(headers[r[2]],r[4:]))
def select(z,is_actual,allow):
    values={}
    for created,table,r in unpack(z):
        if r.get('INTERVENTION','0')!='0' or r.get('RUNNO','1')!='1':continue
        if r.get('CONSTRAINTID') in LABELS:
            if r['GENCONID_VERSIONNO']!='1':continue
            assert r['GENCONID_EFFECTIVEDATE'].startswith('2023/05/01' if r['CONSTRAINTID']==KC else '2024/07/11')
            key=LABELS[r['CONSTRAINTID']];val=float(r['RHS'])-(0 if key=='rhs' else 10000)
        elif r.get('REGIONID') in ['NSW1','QLD1'] and 'TOTALDEMAND' in r:
            key=r['REGIONID'];val=float(r['TOTALDEMAND'])
        elif r.get('INTERCONNECTORID')=='N-Q-MNSP1' and 'METEREDMWFLOW' in r and is_actual:
            key='flow';val=float(r['METEREDMWFLOW'])
        else:continue
        t=r.get('INTERVAL_DATETIME') or r.get('DATETIME') or r.get('SETTLEMENTDATE')
        if t not in allow:continue
        values.setdefault(pd.Timestamp(t),{})[key]=val
    return created,values
def timeset(ids):return {t.strftime('%Y/%m/%d %H:%M:%S') for t in ids}
def observed(day):
    ends=targets(day); u=BASE+f'DispatchIS_Reports/PUBLIC_DISPATCHIS_{ends[0]:%Y%m%d}.zip'
    raw,_=fetch(u); daily=ZipFile(io.BytesIO(raw))
    log.append(dict(url=u,archive_sha256=sha(raw),bytes=len(raw)))
    rows=[];names={f'{t:%Y%m%d%H%M}' for t in ends}
    for i in daily.infolist():
        if i.filename.split('_')[2] not in names:continue
        b=daily.read(i); z=ZipFile(io.BytesIO(b)); created,records=select(z,True,timeset(ends))
        for dt,row in records.items():
            rows.append(dict(end=dt,**row,created=created,modified=datetime(*i.date_time),member=i.filename,member_sha256=sha(b)))
    assert len(rows)==24
    return rows
def issued_data(spec):
    kind,stamp,ends=spec
    z,modified=forecast_file(kind,stamp)
    created,data=select(z,False,timeset(ends))
    run=next(x for x in z.namelist() if x.upper().endswith('.CSV'))
    assert max(created,modified)<min(ends)-pd.Timedelta(minutes=5)
    assert set(data)==set(ends),(run,set(ends)-set(data))
    return [dict(end=t,created=created,modified=modified,run=run,product=kind,**r) for t,r in data.items()]
def capture():
    observed_rows=list(ThreadPoolExecutor(4).map(observed,TRDAYS+TEDAYS))
    obs=pd.DataFrame([r for rows in observed_rows for r in rows]).sort_values('end')
    assert obs[['sydney','terr','rhs','NSW1','QLD1','flow']].notna().all().all()
    obs.to_csv(OUT/'observations.csv',index=False)
    specs=[]
    for day in TEDAYS:
        ends=targets(day)
        specs.append(('PREDISPATCHIS',ends[0].normalize()-pd.Timedelta(days=1)+pd.Timedelta(hours=16,minutes=30),list(ends[5::6])))
        for g in range(4):
            six=ends[g*6:g*6+6]; specs.append(('P5MIN',six[0]-pd.Timedelta(minutes=30),list(six)))
    out=list(ThreadPoolExecutor(3).map(issued_data,specs))
    forecasts=pd.DataFrame([r for rows in out for r in rows]).sort_values(['product','end'])
    assert forecasts[['sydney','terr','rhs','NSW1','QLD1']].notna().all().all()
    forecasts.to_csv(OUT/'issued_forecasts.csv',index=False)
    import openpyxl
    pop={}
    for code,sheet in [('0004','Table 2'),('0003','Table 5')]:
        u=f'https://www.abs.gov.au/statistics/people/population/regional-population/2023-24/32180DS{code}_2001-24.xlsx'
        b,_=fetch(u);log.append(dict(url=u,sha256=sha(b),table=sheet))
        w=openpyxl.load_workbook(io.BytesIO(b),read_only=True,data_only=True)
        records=iter(w[sheet].values)
        for r in records:
            if 2024 in r: pos=r.index(2024);break
        for r in records:
            if r[1] in {'Sydney','Wollongong','Newcastle - Maitland','New South Wales','Australian Capital Territory'}:pop[r[1]]=int(r[pos])
    assert len(pop)==5
    (OUT/'population.json').write_text(json.dumps(pop,indent=2))
    u='https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2024/MMSDM_2024_07/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_DVD_GENERICCONSTRAINTRHS_202407010000.zip'
    b,_=fetch(u);z=ZipFile(io.BytesIO(b));log.append(dict(url=u,sha256=sha(b)))
    f=csv.reader(io.TextIOWrapper(z.open(z.namelist()[0])));next(f); cols=next(f)[4:]
    definitions=pd.DataFrame([r[4:] for r in f if len(r)>7 and r[4] in (CTRL,TER) and r[5]=='2024/07/11 00:00:00' and r[6]=='1'],columns=cols)
    definitions.to_csv(OUT/'monitor_definitions.csv',index=False)
    assert set(definitions[definitions.SCOPE.eq('PD') & definitions.SPD_TYPE.eq('E')].SPD_ID)=={'N_SYDNEY','N_TERRANORA'}
    (OUT/'sources.json').write_text(json.dumps(log,indent=2))
PERSIST='Latest public reading'
ANCHOR='Latest reading plus regional change'
def historical_origins(fc):
    def get(item):
        run,issue=item
        t=issue.floor('5min')
        url=BASE+f'DispatchIS_Reports/PUBLIC_DISPATCHIS_{t:%Y%m%d}.zip'
        z,modified=onefile(url,f'PUBLIC_DISPATCHIS_{t:%Y%m%d%H%M}_')
        created,values=select(z,True,timeset([t]))
        assert max(created,modified)<=issue
        return dict(run=run,origin_reference=t,created=created,modified=modified,
                    member=z.namelist()[0],**values[t])
    origins=pd.DataFrame(ThreadPoolExecutor(3).map(get,fc.groupby('run').created.first().items()))
    assert origins[['sydney','terr','rhs','flow','NSW1','QLD1']].notna().all().all()
    origins.to_csv(OUT/'origins.csv',index=False)
    (OUT/'origin_sources.json').write_text(json.dumps([r for r in log if 'DispatchIS_Reports/' in r['url'] and 'member' in r],indent=2))
def network(n,q,i,d):
    return 1383-.001*(i+d)**2-.0239*n+.0524*q-.6394*d
def calculate():
    obs=pd.read_csv(OUT/'observations.csv',parse_dates=['end','created','modified'])
    fc=pd.read_csv(OUT/'issued_forecasts.csv',parse_dates=['end','created','modified'])
    if not (OUT/'origins.csv').exists() or '--cached' not in sys.argv: historical_origins(fc)
    origins=pd.read_csv(OUT/'origins.csv').set_index('run')
    pop=json.loads((OUT/'population.json').read_text())
    rate=sum(pop[x] for x in ['Sydney','Newcastle - Maitland','Wollongong'])/(pop['New South Wales']+pop['Australian Capital Territory'])
    obs['slot']=obs.end.dt.ceil('30min');obs['clock']=obs.slot.dt.time;obs['weekend']=obs.slot.dt.weekday>=5
    train=obs[obs.end.dt.day.isin(TRDAYS)]
    assert train[['created','modified']].max().max()<fc.created.min()
    rows=[]
    for (kind,slot),batch in fc.groupby(['product',fc.end.dt.ceil('30min')]):
        truth=obs[obs.slot==slot]
        assert len(truth)==6 and len(batch)==(6 if kind=='P5MIN' else 1)
        assert batch.run.nunique()==1
        group=train[(train.clock==slot.time())&(train.weekend==(slot.weekday()>=5))]
        assert len(group) in (12,30)
        common=dict(product=kind,slot=slot,issue=batch.created.iloc[0],trained_days=len(TRDAYS),
                    source_file=batch.run.iloc[0],n_forecast_steps=len(batch))
        anchor=origins.loc[batch.run.iloc[0]]
        for method in [ISSUED,POP,SHARE,CLOCK,LEVEL,PERSIST,ANCHOR]:
            for loc in ['sydney','terr','rhs']:
                if method==POP and loc!='sydney':continue
                if method==ISSUED: pred=batch[loc]
                elif method==POP: pred=rate*batch.NSW1
                elif method==PERSIST: pred=anchor[loc]
                elif method==ANCHOR:
                    dn=batch.NSW1-anchor.NSW1
                    if loc=='rhs':
                        d=anchor.terr+dn*(train.terr.sum()/train.NSW1.sum())
                        pred=anchor.rhs+network(batch.NSW1,batch.QLD1,anchor.flow,d)-network(anchor.NSW1,anchor.QLD1,anchor.flow,anchor.terr)
                    else: pred=anchor[loc]+dn*(train[loc].sum()/train.NSW1.sum())
                elif loc=='rhs' and method==LEVEL: pred=group.rhs.mean()
                elif loc=='rhs':
                    h=train if method==SHARE else group
                    d=batch.NSW1*(h.terr.sum()/h.NSW1.sum())
                    i=h.flow.mean()
                    pred=network(batch.NSW1,batch.QLD1,i,d)
                elif method==LEVEL: pred=group[loc].mean()
                else:
                    h=train if method==SHARE else group
                    pred=batch.NSW1*h[loc].sum()/h.NSW1.sum()
                predicted=float(np.mean(pred)); actual=truth[loc].mean()
                rows.append(dict(**common,target=loc,method=method,predicted=predicted,actual=actual,error=predicted-actual))
    d=pd.DataFrame(rows);assert (d.groupby(['product','target','method']).size()==12).all()
    d.to_csv(OUT/'predictions.csv',index=False)
    s=d.groupby(['target','product','method']).error.agg(n='size',bias='mean',mae=lambda x:x.abs().mean(),max_abs=lambda x:x.abs().max())
    s.to_csv(OUT/'metrics.csv');print(s.to_string(float_format=lambda v:f'{v:.2f}'))
    print('population fraction',rate)
if __name__=='__main__' and '--inspect' not in sys.argv:
    if '--cached' not in sys.argv:capture()
    calculate()
