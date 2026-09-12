"""Reproducible, scoped interconnector event atlas. See methodology in docs/."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from .common import DATA, ROOT, PROCESSED, dump, session
from .constraint_longitudinal import archive_url, path_bytes

VERSION = '1.1-event-atlas-1'
DEFAULT = ROOT / 'configs/event_vni_2y.json'


def settings(path=DEFAULT):
    c = json.loads(Path(path).read_text())
    c['root'] = DATA / c['output_dir']
    c['standing'] = DATA / c['standing_dir']
    c['root'].mkdir(parents=True, exist_ok=True)
    return c


def save(frame, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp.parquet')
    frame.to_parquet(tmp, index=False, compression='zstd')
    tmp.replace(path)


def log(c, item):
    item = {'logged_at_utc': str(pd.Timestamp.now(tz='UTC')), **item}
    with (c['root'] / 'source_manifest.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(item, default=str) + '\n')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8*1024*1024), b''): h.update(block)
    return h.hexdigest()


def guard(c, reserve=0):
    used = path_bytes(c['root']) + path_bytes(DATA / c['base_study_dir'])
    if used + reserve > c['disk_cap_bytes']: raise RuntimeError('10 GB study storage guard')
    if shutil.disk_usage(c['root']).free - reserve < c['min_free_bytes']:
        raise RuntimeError('Free-space reserve guard')
    return used


def local_table(c, name, columns):
    frames = []
    for p in sorted((DATA / 'tables' / name).glob('*.parquet')):
        import pyarrow.parquet as pq
        cols = [x for x in columns if x in pq.read_schema(p).names]
        f = pd.read_parquet(p, columns=cols)
        f['time'] = pd.to_datetime(f.SETTLEMENTDATE)
        f = f[f.time.between(pd.Timestamp(c['start'])-pd.Timedelta(days=2),
                            pd.Timestamp(c['end'])+pd.Timedelta(days=2))]
        if 'REGIONID' in f: f = f[f.REGIONID.isin(c['regions'])]
        if len(f):
            frames.append(f)
            log(c, {'kind':'local_source', 'path':str(p.relative_to(ROOT)), 'sha256':digest(p),
                    'rows_retained':len(f), 'columns':cols, 'regions':c['regions']})
    return pd.concat(frames, ignore_index=True)


def deduplicate(f, key, pricing=False):
    f = f.copy()
    for x in ['INTERVENTION','RUNNO']:
        f[x] = pd.to_numeric(f.get(x, 0), errors='coerce')
    if pricing: f = f[f.INTERVENTION.eq(0)]
    f['LASTCHANGED'] = pd.to_datetime(f.LASTCHANGED, errors='coerce')
    return f.sort_values(['time',key,'INTERVENTION','RUNNO','LASTCHANGED']).drop_duplicates(['time',key], keep='last')


def cap_at(time):
    # Effective-dated AEMC settings; source URLs recorded in the study configuration.
    t = pd.DatetimeIndex(time)
    return np.where(t >= '2026-07-01', 23200., np.where(t >= '2025-07-01',20300.,17500.))


def price_regime(flags, suspended):
    # APCFLAG is a bitmask: 4 is MPC/market-floor binding, NOT administered pricing.
    flags=pd.to_numeric(flags,errors='coerce')
    v=flags.fillna(0).astype('int64')
    return flags.notna() & v.map(lambda x: (x & (1|2|8))==0) & suspended.eq(0)


def detector(capacity, percentile=.9):
    """Series must be on a complete five-minute grid, with missing data as NaN."""
    drop = capacity.shift(6) - capacity
    month = capacity.index.to_period('M').astype(str)
    positive = drop.where(drop.gt(0))
    thresholds = positive.groupby(month).quantile(percentile)
    counts = positive.groupby(month).count()
    thresholds[counts.lt(100)] = np.nan
    cutoff = pd.Series(month,index=capacity.index).map(thresholds)
    valid = capacity.notna().rolling(7,min_periods=7).sum().eq(7)
    sharp = valid & drop.gt(0) & drop.ge(cutoff)
    onset = sharp & ~sharp.shift(1,fill_value=False)
    return pd.DataFrame({'drop_mw':drop,'threshold_mw':cutoff,'sharp':sharp,'onset':onset}), thresholds, counts


def landmarks(window, baseline):
    """Stop at the first sustained recovery; do not absorb a later independent dip."""
    trough=np.inf;trough_time=pd.NaT;streak=[]
    for t,value in window.items():
        if not np.isfinite(value):return trough_time,trough,pd.NaT
        if value<trough:trough=value;trough_time=t;streak=[]
        if baseline>trough and value>=trough+.9*(baseline-trough):
            streak.append(t)
            if len(streak)==3:return trough_time,trough,streak[0]
        else:streak=[]
    return trough_time,trough,pd.NaT


def screen(c):
    root=c['root']; start=pd.Timestamp(c['start']); end=pd.Timestamp(c['end'])
    icpath=PROCESSED/'ic_5min.parquet'; f=pd.read_parquet(icpath)
    f=f[f.INTERCONNECTORID.eq(c['interconnector'])].sort_values('time').drop_duplicates('time')
    idx=pd.date_range(start-pd.Timedelta(hours=3), end+pd.Timedelta(hours=3),freq='5min')
    ic=f.set_index('time').reindex(idx); ic.index.name='time'
    log(c,{'kind':'local_source','path':str(icpath.relative_to(ROOT)),'sha256':digest(icpath)})
    pc=['SETTLEMENTDATE','REGIONID','INTERVENTION','RUNNO','RRP','ROP','APCFLAG','MARKETSUSPENDEDFLAG','LASTCHANGED']
    prices=deduplicate(local_table(c,'DISPATCHPRICE',pc),'REGIONID',True)
    for col in ['RRP','ROP','APCFLAG','MARKETSUSPENDEDFLAG']: prices[col]=pd.to_numeric(prices[col],errors='coerce')
    prices['mpc']=cap_at(prices.time)
    prices['ordinary']=price_regime(prices.APCFLAG,prices.MARKETSUSPENDEDFLAG)
    prices['mpc_hit']=prices.ordinary & prices.RRP.sub(prices.mpc).abs().le(.01)
    prices['near_mpc']=prices.ordinary & prices.RRP.ge(.9*prices.mpc)
    save(prices,root/'prices_5min.parquet')
    for region in c['regions']:
        p=prices[prices.REGIONID.eq(region)].set_index('time')
        for field in ['RRP','mpc_hit','near_mpc','ordinary','mpc']:
            ic[f'{region}_{field}']=p[field].reindex(idx)
    regs=['SETTLEMENTDATE','REGIONID','INTERVENTION','RUNNO','LASTCHANGED','TOTALDEMAND','AVAILABLEGENERATION',
          'SS_WIND_CLEAREDMW','SS_SOLAR_CLEAREDMW','SS_WIND_UIGF','SS_SOLAR_UIGF','LORSURPLUS']
    context=deduplicate(local_table(c,'DISPATCHREGIONSUM',regs),'REGIONID')
    for col in regs[5:]: context[col]=pd.to_numeric(context[col],errors='coerce')
    save(context,root/'regional_context.parquet')
    for region in c['regions']:
        p=context[context.REGIONID.eq(region)].set_index('time')
        for field in regs[5:]: ic[f'{region}_{field}']=p[field].reindex(idx)
    save(ic.reset_index(),root/'screen_timeseries.parquet')
    rows=[]; thresholds=[]; labels=[]
    for direction,col,receiver,sender in [('upper','export',c['regions'][1],c['regions'][0]),('lower','import',c['regions'][0],c['regions'][1])]:
        d,th,n=detector(ic[col]); eligible=(d.index>=start)&(d.index<=end)
        for month,value in th.items():thresholds.append(dict(month=month,direction=direction,threshold_mw=value,positive_falls=int(n[month])))
        labels.append(d.assign(direction=direction).reset_index())
        for t in d.index[d.onset & eligible]:
            pre=ic.loc[t-pd.Timedelta(minutes=30):t,col].dropna()
            bt=pre.index[pre.eq(pre.max())][-1]; base=float(pre.loc[bt])
            window=ic.loc[t:t+pd.Timedelta(hours=2)]
            trough_t,trough,recovery=landmarks(window[col],base)
            post=ic.loc[t:t+pd.Timedelta(hours=1)]
            before=ic.loc[t-pd.Timedelta(hours=1):t-pd.Timedelta(minutes=5)]
            peak=post[f'{receiver}_RRP'].max(); preprice=before[f'{receiver}_RRP'].median()
            spread=post[f'{receiver}_RRP']-post[f'{sender}_RRP']
            rows.append(dict(event_id=f"VNI-{direction}-{t:%Y%m%dT%H%M}",time=t,direction=direction,
                receiver=receiver,sender=sender,month=str(t.to_period('M')),hour=t.hour,
                season=['Summer','Autumn','Winter','Spring'][(t.month%12)//3],year=t.year,
                baseline_time=bt,baseline_capacity_mw=base,trough_time=trough_t,trough_mw=trough,
                recovery_time=recovery,recovery_censored=pd.isna(recovery),
                baseline_to_trough_mw=base-trough,drop_mw=float(d.at[t,'drop_mw']),threshold_mw=float(d.at[t,'threshold_mw']),
                capacity_mw=float(ic.at[t,col]),flow_mw=float(ic.at[t,'flow']),
                headroom_mw=float(ic.at[t,col]-(ic.at[t,'flow'] if direction=='upper' else -ic.at[t,'flow'])),
                reported_setter=ic.at[t,'EXPORTGENCONID' if direction=='upper' else 'IMPORTGENCONID'],
                peak_price=peak,pre_price=preprice,price_jump=peak-preprice,peak_spread=spread.max(),
                mpc_intervals=int(post[f'{receiver}_mpc_hit'].fillna(False).sum()),
                near_mpc_intervals=int(post[f'{receiver}_near_mpc'].fillna(False).sum()),
                price_complete=post[f'{receiver}_RRP'].notna().all() and len(post)==13,
                special_price_regime=not post[f'{receiver}_ordinary'].fillna(False).all(),
                pre_demand=before[f'{receiver}_TOTALDEMAND'].median(),
                pre_wind=before[f'{receiver}_SS_WIND_CLEAREDMW'].median(),
                pre_solar=before[f'{receiver}_SS_SOLAR_CLEAREDMW'].median(),
                pre_available=before[f'{receiver}_AVAILABLEGENERATION'].median()))
    events=pd.DataFrame(rows).sort_values(['direction','time'])
    events['parent_seq']=events.groupby('direction').time.diff().gt(pd.Timedelta(minutes=30)).groupby(events.direction).cumsum()
    events['incident_id']=events.direction+'-'+events.parent_seq.astype(str)
    # Deep dives: every receiving-region near-MPC event; monthly largest per direction;
    # top 12 absolute; and one deterministic ordinary case per season/direction/year.
    events['selection_reason']=''
    selections={'near_MPC':events.index[events.near_mpc_intervals.gt(0)],
        'monthly_largest':events.groupby(['month','direction']).drop_mw.idxmax(),
        'top_absolute':events.nlargest(12,'drop_mw').index,
        'representative':events[events.near_mpc_intervals.eq(0)].groupby(['year','season','direction']).sample(n=1,random_state=741).index}
    for reason,ix in selections.items():events.loc[ix,'selection_reason']+=reason+';'
    events['selected']=events.selection_reason.ne('')
    save(events,root/'event_catalogue.parquet')
    pd.DataFrame(thresholds).to_csv(root/'thresholds.csv',index=False)
    save(pd.concat(labels),root/'interval_labels.parquet')
    price_events=[]
    for region in c['regions']:
        m=ic[f'{region}_near_mpc'].fillna(False).astype(bool)
        for t in m.index[m & ~m.shift(1,fill_value=False)]:
            if t<start or t>end:continue
            linked=events[events.time.between(t-pd.Timedelta(hours=1),t+pd.Timedelta(hours=1))]
            price_events.append(dict(time=t,region=region,rrp=ic.at[t,f'{region}_RRP'],
                contraction_events=';'.join(linked.event_id),linked_events=len(linked)))
    pe=pd.DataFrame(price_events);save(pe,root/'price_event_catalogue.parquet')
    quality={'method_version':VERSION,'start':str(start),'end':str(end),'expected_intervals':int(((idx>=start)&(idx<=end)).sum()),
             'events':len(events),'incidents':events.incident_id.nunique(),'selected_events':int(events.selected.sum()),
             'price_episodes':len(pe),'price_episodes_without_nearby_contraction':int(pe.linked_events.eq(0).sum()),
             'coverage':{col:int(ic.loc[start:end,col].notna().sum()) for col in ['flow','export','import']+[f'{r}_RRP' for r in c['regions']]}}
    dump(root/'screen_quality.json',quality);print(json.dumps(quality,indent=2),flush=True)


def extract_archive(c, path, table, times, ids, columns):
    parts=[]; count=0
    # Chunked native CSV parser; extract directly from ZIP without an expanded disk copy.
    with zipfile.ZipFile(path) as z:
        for member in z.infolist():
            if not member.filename.lower().endswith('.csv'):continue
            with z.open(member) as raw:
                schema=None
                for line in raw:
                    row=next(csv.reader([line.decode('utf-8-sig')]))
                    if row and row[0]=='I':schema=row[4:];break
                if schema is None:raise RuntimeError('Missing archive schema')
                key='DUID' if table=='DISPATCHLOAD' else 'CONSTRAINTID'
                keep=[x for x in columns if x in schema]
                for chunk in pd.read_csv(raw,header=None,names=['_record','_name','_table','_version']+schema,
                        usecols=['_record']+keep,dtype=str,keep_default_na=False,chunksize=100000):
                    valid=chunk._record.eq('D');count+=int(valid.sum())
                    selected=chunk[valid & chunk.SETTLEMENTDATE.isin(times) & chunk[key].isin(ids)]
                    if len(selected):parts.append(selected[keep].copy())
    f=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    if f.empty:raise RuntimeError(f'No selected evidence found in {path.name}')
    print(table,'scanned',count,'retained',len(f),flush=True)
    return f


def recover(c):
    root=c['root']; events=pd.read_parquet(root/'event_catalogue.parquet')
    selected=events[events.selected]; windows=set()
    for t in selected.time:
        windows.update(pd.date_range(t-pd.Timedelta(hours=2),t+pd.Timedelta(hours=2),freq='5min'))
    # Include price-first events with no nearby contraction, to avoid outcome selection bias.
    price_events=pd.read_parquet(root/'price_event_catalogue.parquet')
    for t in price_events.loc[price_events.linked_events.eq(0),'time']:
        windows.update(pd.date_range(t-pd.Timedelta(hours=2),t+pd.Timedelta(hours=2),freq='5min'))
    # Matched controls from the screening stage are added before recovery when available.
    cp=root/'controls.parquet'
    if cp.exists():
        for t in pd.read_parquet(cp).control_time:
            windows.update(pd.date_range(t-pd.Timedelta(hours=2),t+pd.Timedelta(hours=2),freq='5min'))
    dep=json.loads((c['standing']/'dependencies.json').read_text())
    details=pd.read_parquet(c['standing']/'DUDETAILSUMMARY.parquet')
    unit_ids=set(dep['duids'])|set(details.loc[details.REGIONID.isin(c['regions']),'DUID'])
    plan=[]
    for month in sorted({t.to_period('M') for t in windows}):
        times={t.strftime('%Y/%m/%d %H:%M:%S') for t in windows if t.to_period('M')==month}
        for table in ['DISPATCHCONSTRAINT','DISPATCHLOAD']:
            plan.append({'month':str(month),'table':table,'url':archive_url(month,table),'intervals':len(times),
                         'reason':'Selected event, price-only and matched control windows; dependency-filtered rows'})
    dump(root/'download_plan.json',plan)
    cols={'DISPATCHCONSTRAINT':['SETTLEMENTDATE','RUNNO','CONSTRAINTID','RHS','LHS','MARGINALVALUE','VIOLATIONDEGREE','INTERVENTION','LASTCHANGED','GENCONID_EFFECTIVEDATE','GENCONID_VERSIONNO'],
          'DISPATCHLOAD':['SETTLEMENTDATE','RUNNO','DUID','CONNECTIONPOINTID','INITIALMW','TOTALCLEARED','AVAILABILITY','RAMPUPRATE','RAMPDOWNRATE','INTERVENTION','LASTCHANGED','DISPATCHMODE']}
    for item in plan:
        month=item['month'];table=item['table'];out=root/'evidence'/month/f'{table}.parquet'
        marker=out.with_suffix('.json')
        if out.exists() and marker.exists():
            prior=json.loads(marker.read_text())
            if prior['intervals']!=item['intervals']:raise RuntimeError('Selection scope changed: rebuild this evidence partition')
            if digest(out)!=prior['retained_sha256']:raise RuntimeError('Retained evidence checksum mismatch')
            print('RESUME verified',month,table,flush=True);continue
        guard(c,c['file_cap_bytes']+100_000_000)
        rawdir=root/'raw';rawdir.mkdir(exist_ok=True);path=rawdir/f'{month}_{table}.zip'
        print('RECOVER',month,table,flush=True)
        if not path.exists():
            part=path.with_suffix('.partial')
            with session().get(item['url'],stream=True,timeout=(20,180)) as r:
                r.raise_for_status();written=0
                with part.open('wb') as f:
                    for chunk in r.iter_content(1024*1024):
                        written+=len(chunk)
                        if written>c['file_cap_bytes']:raise RuntimeError('Archive file cap exceeded')
                        guard(c,len(chunk));f.write(chunk)
            part.replace(path)
        with zipfile.ZipFile(path) as z:
            expanded=sum(i.file_size for i in z.infolist())
            if expanded>c['expanded_cap_bytes']:raise RuntimeError('Expanded archive cap exceeded')
        times={t.strftime('%Y/%m/%d %H:%M:%S') for t in windows if str(t.to_period('M'))==month}
        ids=unit_ids if table=='DISPATCHLOAD' else set(dep['constraint_ids'])
        frame=extract_archive(c,path,table,times,ids,cols[table])
        save(frame,out)
        record={**item,'source_sha256':digest(path),'compressed_bytes':path.stat().st_size,
                'expanded_bytes':expanded,'retained_rows':len(frame),'retained_bytes':out.stat().st_size,
                'retained_sha256':digest(out),'output':str(out.relative_to(ROOT)),'peak_accounted_bytes':guard(c)}
        dump(marker,record);log(c,{'kind':'download_extract',**record})
        if root.resolve() not in path.resolve().parents:raise RuntimeError('Unsafe cleanup path')
        path.unlink();log(c,{'kind':'cleanup','path':str(path.relative_to(ROOT)),'deleted_bytes':record['compressed_bytes']})
        print('VERIFIED AND CLEANED',month,table,'retained MB',round(out.stat().st_size/1e6,2),flush=True)


def match_controls(c):
    """Descriptive matched comparisons; pre-event covariates, same month/hour band."""
    from scipy.spatial import cKDTree
    root=c['root'];e=pd.read_parquet(root/'event_catalogue.parquet')
    ic=pd.read_parquet(root/'screen_timeseries.parquet').set_index('time')
    labs=pd.read_parquet(root/'interval_labels.parquet')
    result=[]
    for direction,receiver in [('upper',c['regions'][1]),('lower',c['regions'][0])]:
        cap='export' if direction=='upper' else 'import'
        z=ic.copy();z['headroom']=z[cap]-(z.flow if direction=='upper' else -z.flow)
        cols=[f'{receiver}_TOTALDEMAND',f'{receiver}_SS_WIND_CLEAREDMW',f'{receiver}_SS_SOLAR_CLEAREDMW',
              f'{receiver}_AVAILABLEGENERATION',f'{receiver}_RRP','flow','headroom']
        x=z[cols].rolling(12,min_periods=12).median().shift(1)
        # Controls exclude any sharp interval in a surrounding four-hour window.
        sharp=labs[labs.direction.eq(direction)].set_index('time').sharp.reindex(z.index).fillna(False)
        bad=sharp.astype(int).rolling(49,center=True,min_periods=1).max().gt(0)
        candidate=x[~bad & x.notna().all(axis=1) & (x.index.minute==0)]
        for _,ev in e[e.direction.eq(direction)].iterrows():
            if ev.time not in x.index:continue
            control=candidate[(candidate.index.to_period('M')==ev.time.to_period('M')) &
                (np.abs(candidate.index.hour-ev.time.hour)<=1) &
                ((candidate.index.dayofweek<5)==(ev.time.dayofweek<5)) &
                (np.abs((candidate.index-ev.time).total_seconds())>86400)]
            target=x.loc[ev.time]
            if len(control)<5 or target.isna().any():continue
            scale=control.std().replace(0,1).fillna(1)
            dist,ix=cKDTree((control/scale).to_numpy()).query((target/scale).to_numpy())
            if dist>5:continue
            t=control.index[ix];post=z.loc[t:t+pd.Timedelta(hours=1)]
            baseline=z.loc[t-pd.Timedelta(hours=1):t-pd.Timedelta(minutes=5),f'{receiver}_RRP'].median()
            row=dict(event_id=ev.event_id,time=ev.time,control_time=t,direction=direction,selected=ev.selected,
                distance=float(dist),event_price_jump=ev.price_jump,
                control_price_jump=post[f'{receiver}_RRP'].max()-baseline,
                event_mpc=ev.mpc_intervals>0,control_mpc=post[f'{receiver}_mpc_hit'].fillna(False).any(),
                incident_id=ev.incident_id)
            for k in cols:row['balance_'+k]=float((target[k]-control.iloc[ix][k])/scale[k])
            result.append(row)
    controls=pd.DataFrame(result);save(controls,root/'matched_population.parquet')
    # Recover controls only for selected deep dives; full population matching uses local screening series.
    save(controls[controls.selected],root/'controls.parquet')
    print('MATCHED',len(controls),'of',len(e),'selected controls',int(controls.selected.sum()),flush=True)


def recover_coal_registration(c):
    """Small, exact-table monthly snapshots for dated coal capacity; no registry mirror."""
    from .constraint_ingest import _table_rows
    duids={f'BW0{i}' for i in range(1,5)}|{f'ER0{i}' for i in range(1,5)}|{'MP1','MP2','VP5','VP6'}|{f'LYA{i}' for i in range(1,5)}|{'LOYYB1','LOYYB2'}|{f'YWPS{i}' for i in range(1,5)}
    parts=[]
    for month in pd.period_range(pd.Timestamp(c['start']).to_period('M'),pd.Timestamp(c['end']).to_period('M'),freq='M'):
        out=c['root']/'coal_registration'/f'{month}.parquet'
        if out.exists():parts.append(pd.read_parquet(out));continue
        url=archive_url(month,'DUDETAIL');guard(c,10_000_000)
        print('COAL REGISTRATION',month,flush=True)
        with session().get(url,stream=True,timeout=(20,60)) as r:
            if r.status_code==404:
                log(c,{'kind':'optional_source_unavailable','url':url,'http_status':404});continue
            r.raise_for_status();path=c['root']/'raw'/f'{month}_DUDETAIL.zip';written=0
            with path.open('wb') as f:
                for chunk in r.iter_content(1024*1024):
                    written+=len(chunk)
                    if written>10_000_000:raise RuntimeError('Scoped coal registration archive cap')
                    f.write(chunk)
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist())>100_000_000:raise RuntimeError('Coal registration expanded cap')
        df=_table_rows(path,'DUDETAIL',keep=['DUID','EFFECTIVEDATE','VERSIONNO','REGISTEREDCAPACITY','MAXCAPACITY','AUTHORISEDDATE','LASTCHANGED'],
                       value_filter=lambda row:row.get('DUID') in duids)
        if df.empty:raise RuntimeError('No selected coal registration rows')
        save(df,out);parts.append(df)
        log(c,{'kind':'download_extract','table':'DUDETAIL','month':str(month),'url':url,
            'compressed_bytes':written,'source_sha256':digest(path),'retained_rows':len(df),'output':str(out),
            'retained_sha256':digest(out),'scope':'22 named NSW/VIC coal generation DUIDs; effective-dated capacity only'})
        path.unlink();log(c,{'kind':'cleanup','path':str(path),'deleted_bytes':written})
    if parts:
        save(pd.concat(parts,ignore_index=True).drop_duplicates(),c['root']/'coal_registration.parquet')


def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['screen','recover','match','coal']);p.add_argument('--config',default=str(DEFAULT));a=p.parse_args()
    c=settings(a.config)
    {'screen':screen,'recover':recover,'match':match_controls,'coal':recover_coal_registration}[a.stage](c)


if __name__=='__main__':main()
