"""Held-out local load, renewables and storage study. Run with --fetch once."""
from pathlib import Path
import sys, io, csv, json, hashlib
from zipfile import ZipFile
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / 'local_exports/rhs_forward_feb26'))
import study as archive

FIT = list(range(9, 16))
CAL = [17, 18]
TEST = [23, 25, 28]
POINTS = {'DATASNAP_DFS_NSYD':'Sydney area', 'DATASNAP_TE_967_1':'Terranora',
          'DATASNAP_DFS_NCAN':'Canberra', 'DATASNAP_DFS_NCWEST':'Central West NSW',
          'DATASNAP_DFS_SWNSW':'Southwest NSW'}
UNITS = {'CAPTL_WF':'wind', 'CULLRGWF':'wind', 'BANGOWF1':'wind', 'GOONSF1':'solar',
         'ORABESS1':'battery', 'TARBESS1':'battery'}
LOG = []


def slots(day):
    start = pd.Timestamp(2026,2,day)
    return [start + pd.Timedelta(minutes=x) for x in (630,660,1050,1080)]


def read_report(z):
    with io.TextIOWrapper(z.open(z.namelist()[0]), encoding='utf-8-sig') as stream:
        rows = csv.reader(stream)
        head = next(rows)
        created = pd.Timestamp(' '.join(head[5:7]))
        headers = {}
        for row in rows:
            if row[0]=='I':
                headers[row[2]] = row[4:]
            if row[0]!='D' or row[2] not in {'PRICE','REGIONSUM','REGION_PRICES','REGION_SOLUTION',
                'REGIONSOLUTION','CONSTRAINT','CONSTRAINT_SOLUTION','CONSTRAINTSOLUTION','UNIT_SCADA'}:
                continue
            fields = dict(zip(headers[row[2]],row[4:]))
            if fields.get('INTERVENTION','0')!='0' or fields.get('RUNNO','1')!='1':
                continue
            yield created, fields


def parse(z, allowed):
    result = {}
    for created, r in read_report(z):
        stamp = r.get('SETTLEMENTDATE') or r.get('INTERVAL_DATETIME') or r.get('DATETIME')
        if stamp not in allowed:
            continue
        out = result.setdefault(stamp,{})
        if r.get('REGIONID')=='NSW1':
            for src, key in [('RRP','price'),('TOTALDEMAND','nsw'),('SS_WIND_CLEAREDMW','wind'),
                             ('SS_SOLAR_CLEAREDMW','solar')]:
                if r.get(src):
                    out[key] = float(r[src])
        if r.get('CONSTRAINTID') in POINTS:
            assert r['GENCONID_EFFECTIVEDATE']=='2024/07/11 00:00:00' and r['GENCONID_VERSIONNO']=='1'
            out[POINTS[r['CONSTRAINTID']]] = float(r['RHS'])-10000
        if r.get('DUID') in UNITS:
            out[r['DUID']] = float(r['SCADAVALUE'])
    return created,result


def observations(item):
    day, dates = item
    merged = {}
    for folder,prefix in [('DispatchIS_Reports','DISPATCHIS'),('Dispatch_SCADA','DISPATCHSCADA')]:
        url = archive.BASE+f'{folder}/PUBLIC_{prefix}_{day:%Y%m%d}.zip'
        body,_ = archive.fetch(url)
        LOG.append(dict(url=url,bytes=len(body),sha256=archive.sha(body)))
        with ZipFile(io.BytesIO(body)) as daily:
            for member in daily.infolist():
                stamp = pd.Timestamp(member.filename.split('_')[2])
                if stamp not in dates:
                    continue
                raw = daily.read(member)
                with ZipFile(io.BytesIO(raw)) as z:
                    created, rr = parse(z,archive.timeset([stamp]))
                row = merged.setdefault(stamp,dict(end=stamp))
                row.update(rr[stamp.strftime('%Y/%m/%d %H:%M:%S')])
                row[prefix+'_created']=created
                row[prefix+'_modified']=pd.Timestamp(*member.date_time)
                row[prefix+'_member']=member.filename
                row[prefix+'_sha256']=archive.sha(raw)
    assert len(merged)==len(dates)
    return list(merged.values())


def specs():
    for day in CAL+TEST:
        ends=slots(day)
        yield 'PREDISPATCHIS',ends[0].normalize()-pd.Timedelta(days=1)+pd.Timedelta(hours=16,minutes=30),ends
        for t in ends:
            native=pd.date_range(t-pd.Timedelta(minutes=25),t,freq='5min')
            yield 'P5MIN',native[0]-pd.Timedelta(minutes=30),list(native)


def forecast(spec):
    kind, stamp, dates = spec
    z, modified = archive.forecast_file(kind,stamp)
    created, rows = parse(z,archive.timeset(dates))
    run=z.namelist()[0]
    assert len(rows)==len(dates) and max(created,modified)<min(dates)-pd.Timedelta(minutes=5)
    # Latest issued half-hourly PV file strictly on/before the market report creation.
    origin=created.floor('30min')
    thursday=origin-pd.Timedelta(days=(origin.weekday()-3)%7)
    url=archive.BASE+f'ROOFTOP_PV/FORECAST/PUBLIC_ROOFTOP_PV_FORECAST_{thursday:%Y%m%d}.zip'
    pvz, pv_modified=archive.onefile(url,f'PUBLIC_ROOFTOP_PV_FORECAST_{origin:%Y%m%d%H%M%S}_')
    with io.TextIOWrapper(pvz.open(pvz.namelist()[0])) as stream:
        rd=csv.reader(stream);head=next(rd);pv_created=pd.Timestamp(' '.join(head[5:7]))
        assert max(pv_created,pv_modified)<=created
        hdr=next(rd)[4:]
        pv={pd.Timestamp(r['INTERVAL_DATETIME']):float(r['POWERMEAN'])
            for raw in rd if raw[0]=='D' for r in [dict(zip(hdr,raw[4:]))] if r['REGIONID']=='NSW1'}
    return [dict(end=pd.Timestamp(t),run=run,kind=kind,issue=created,modified=modified,
                 pv_issue=pv_created,pv_modified=pv_modified,pv_run=pvz.namelist()[0],
                 pv=pv[pd.Timestamp(t).ceil('30min')],**v) for t,v in rows.items()]


def capture():
    fc=pd.DataFrame([r for group in ThreadPoolExecutor(4).map(forecast,specs()) for r in group])
    fc.to_csv(OUT/'forecast_inputs.csv',index=False)
    required=set(fc.issue.dt.floor('5min'))
    for day in FIT+CAL+TEST:
        for end in slots(day):
            required.update(pd.date_range(end-pd.Timedelta(minutes=25),end,freq='5min'))
    groups=[(day,{t for t in required if t.normalize()==day}) for day in sorted({t.normalize() for t in required})]
    obs=pd.DataFrame([r for lst in ThreadPoolExecutor(4).map(observations,groups) for r in lst]).sort_values('end')
    obs.to_csv(OUT/'observed_inputs.csv',index=False)
    url='https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2024/MMSDM_2024_07/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_DVD_GENERICCONSTRAINTRHS_202407010000.zip'
    data,_=archive.fetch(url)
    LOG.append(dict(url=url,sha256=archive.sha(data)))
    with ZipFile(io.BytesIO(data)) as z, io.TextIOWrapper(z.open(z.namelist()[0])) as stream:
        rd=csv.reader(stream);next(rd); cols=next(rd)[4:]
        defs=pd.DataFrame([r[4:] for r in rd if r[0]=='D' and r[4] in POINTS and r[5]=='2024/07/11 00:00:00' and r[6]=='1'],columns=cols)
    for monitor in POINTS:
        g=defs[(defs.GENCONID==monitor)&(defs.SCOPE=='PD')]
        assert sorted(zip(g.SPD_TYPE,g.FACTOR))==[('C','10000'),('E','1')]
    defs.to_csv(OUT/'definitions.csv',index=False)
    (OUT/'sources.json').write_text(json.dumps(LOG+archive.log,indent=2))


def evaluate():
    observed=pd.read_csv(OUT/'observed_inputs.csv',parse_dates=['end','DISPATCHIS_created',
             'DISPATCHIS_modified','DISPATCHSCADA_created','DISPATCHSCADA_modified']).set_index('end').sort_index()
    fc=pd.read_csv(OUT/'forecast_inputs.csv',parse_dates=['end','issue','modified','pv_issue','pv_modified'])
    pvpath=next((ROOT/'data/tables/ROOFTOP_PV_ACTUAL').glob('*202602*'))
    pv=pd.read_parquet(pvpath).query("REGIONID=='NSW1' and TYPE=='MEASUREMENT'").copy()
    pv['slot']=pd.to_datetime(pv.INTERVAL_DATETIME)
    pv=pv.set_index('slot',verify_integrity=True)
    pv['POWER']=pv.POWER.astype(float)
    data=[]
    variables=list(POINTS.values())+list(UNITS)
    for day in FIT+CAL+TEST:
        for t in slots(day):
            block=observed.loc[pd.date_range(t-pd.Timedelta(minutes=25),t,freq='5min')]
            assert len(block)==6 and block[variables+['price','wind','solar','nsw']].notna().all().all()
            data.append(dict(slot=t,**block[variables+['price','wind','solar','nsw']].mean().to_dict(),
                             pv=pv.loc[t,'POWER'],pv_revision=pv.loc[t,'LASTCHANGED']))
    actual=pd.DataFrame(data).set_index('slot')
    train=actual[actual.index.day.isin(FIT)]
    assert pd.to_datetime(train.pv_revision).max()<fc.issue.min()
    pop=json.loads((ROOT/'local_exports/rhs_forward_feb26/population.json').read_text())
    popshare=sum(pop[x] for x in ['Sydney','Newcastle - Maitland','Wollongong'])/(pop['New South Wales']+pop['Australian Capital Territory'])
    rows=[]
    for (kind,t), b in fc.groupby(['kind',fc.end.dt.ceil('30min')]):
        assert len(b)==(6 if kind=='P5MIN' else 1) and b.run.nunique()==1
        issue=b.issue.iloc[0];a=observed.loc[issue.floor('5min')]
        assert max(a[k] for k in a.index if k.endswith(('_created','_modified')))<=issue
        same=train[train.index.time==t.time()]
        for target in variables+['Regional rooftop PV']:
            group=UNITS.get(target,'load')
            if target=='Regional rooftop PV':
                previous=pv[(pd.to_datetime(pv.LASTCHANGED)<issue)&(pv.index<=issue)].iloc[-1]
                out={'Last available historical PV estimate (revision-time proxy)':float(previous.POWER),
                     'Same-clock mean':same.pv.mean(),'Issued regional PV forecast':b.pv.mean()}
                truth=actual.loc[t,'pv']
            else:
                truth=actual.loc[t,target]
                out={'Persistence':a[target],'Same-clock mean':same[target].mean()}
                if group=='load':
                    share=train[target].sum()/train.nsw.sum()
                    matched=same[target].sum()/same.nsw.sum()
                    out.update({'Fixed demand share':b.nsw.mean()*share,'Clock demand share':b.nsw.mean()*matched,
                        'Anchor plus regional change':a[target]+share*(b.nsw.mean()-a.nsw),
                        'Issued local monitor':b[target].mean()})
                    # Learn demand and PV deviations within each clock slot, with no held-out targets.
                    predictors=train[['nsw','pv',target]]
                    residual=predictors-predictors.groupby(predictors.index.time).transform('mean')
                    beta=np.linalg.lstsq(residual[['nsw','pv']],residual[target],rcond=None)[0]
                    out['Clock plus demand and PV']=same[target].mean()+beta @ (b[['nsw','pv']].mean()-same[['nsw','pv']].mean())
                    if target=='Sydney area':out['Population share']=popshare*b.nsw.mean()
                elif group in ('wind','solar'):
                    ratio=train[target].sum()/train[group].sum()
                    out['Issued regional generation share']=ratio*b[group].mean()
                    out['Anchor plus generation change']=a[target]+ratio*(b[group].mean()-a[group])
                else:
                    out['Idle scenario']=0.
                    quantiles=train.price.quantile([1/3,2/3]).to_numpy()
                    buckets=np.searchsorted(quantiles,train.price)
                    levels=train[target].groupby(buckets).median()
                    out['Price-bin signed MW']=np.mean([levels.get(j,train[target].median()) for j in np.searchsorted(quantiles,b.price)])
            for method,pred in out.items():
                rows.append(dict(target=target,kind=kind,slot=t,issue=issue,forecast=pred,actual=truth,
                                 method=method,error=pred-truth,partition='calibration' if t.day in CAL else 'evaluation'))
    df=pd.DataFrame(rows)
    grp=['target','kind','method']
    band=df[df.partition=='calibration'].groupby(grp).error.apply(lambda g:g.abs().max()).rename('band').reset_index()
    df=df.merge(band,on=grp,validate='many_to_one')
    df['covered']=df.error.abs()<=df.band+1e-9
    df.to_csv(OUT/'predictions.csv',index=False)
    scored=df[df.partition=='evaluation'].groupby(grp).agg(n=('error','size'),mae=('error',lambda g:g.abs().mean()),
        bias=('error','mean'),max_abs=('error',lambda g:g.abs().max()),band_mw=('band','first'),coverage=('covered','mean'))
    assert scored.n.eq(12).all()
    scored.to_csv(OUT/'scores.csv')
    print(f'{len(scored)} comparisons, {len(df)} scored/calibration rows')
    return df


if __name__=='__main__':
    if '--fetch' in sys.argv: capture()
    evaluate()
