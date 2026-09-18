"""Auditable research coal registry and explicit daily-alignment assumption."""
import json
import zipfile
import pandas as pd

from nemic.experiments.core import ROOT,digest
from .sources import nem_time,read_mms
from .tracking import atomic


def standing_table(name):
    paths=list((ROOT/'data/raw').glob('*%23'+name+'%23*.zip'))
    if not paths:raise ValueError('Missing retained AEMO '+name+' fuel/capacity evidence')
    frames=[]
    for path in sorted(paths):
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if member.lower().endswith('.csv'):
                    with archive.open(member) as handle:
                        frames.append(pd.DataFrame([r for d,t,v,r,g in read_mms(handle) if t==name]))
    return pd.concat(frames).drop_duplicates(),paths


def canonical_intervals(frame):
    """New effective records supersede earlier open-ended snapshots."""
    f=frame.copy()
    ordering=['DUID','START_DATE']+(['LASTCHANGED'] if 'LASTCHANGED' in f else [])
    f=f.sort_values(ordering).drop_duplicates(['DUID','START_DATE'],keep='last')
    next_start=f.groupby('DUID').START_DATE.shift(-1)
    f['END_DATE']=f.END_DATE.where(next_start.isna() | f.END_DATE.le(next_start),next_start)
    return f[f.START_DATE.lt(f.END_DATE)]


def prepare(ledger,day_start_hour=4):
    if day_start_hour not in (0,4):raise ValueError('Only documented 00/04 daily-alignment sensitivity supported')
    scope=pd.concat([pd.read_csv(ROOT/'data'/c['atlas']/'coal_unit_scope.csv') for c in ledger.c['connectors']]).drop_duplicates('DUID')
    units,unit_paths=standing_table('GENUNITS');alloc,alloc_paths=standing_table('DUALLOC');details,detail_paths=standing_table('DUDETAIL')
    fuelmap={'Black coal':'black_coal','Brown coal':'brown_coal'}
    units=units.sort_values('LASTCHANGED').drop_duplicates('GENSETID',keep='last')
    alloc=alloc.merge(units[['GENSETID','CO2E_ENERGY_SOURCE']],on='GENSETID',how='left',validate='many_to_one')
    alloc['effective']=pd.to_datetime(alloc.EFFECTIVEDATE).dt.tz_localize('Australia/Brisbane')
    alloc['version']=pd.to_numeric(alloc.VERSIONNO)
    alloc=alloc[alloc.version.eq(alloc.groupby(['DUID','effective']).version.transform('max'))]
    alloc['fuel']=alloc.CO2E_ENERGY_SOURCE.map(fuelmap)
    fuels={}
    for (duid,effective),g in alloc.groupby(['DUID','effective']):
        fuels[(duid,effective)]=g.fuel.iloc[0] if g.fuel.notna().all() and g.fuel.nunique()==1 else None
    eligible_duids={duid for (duid,effective),fuel in fuels.items() if fuel}
    summary=pd.concat([pd.read_parquet(ROOT/'data'/c['study']/'standing/DUDETAILSUMMARY.parquet') for c in ledger.c['connectors']]).drop_duplicates()
    summary=summary[summary.DUID.isin(eligible_duids)].copy()
    for col in ('START_DATE','END_DATE'):
        summary[col]=pd.to_datetime(summary[col].str.replace('2999','2200'),errors='coerce').dt.tz_localize('Australia/Brisbane')
    summary=canonical_intervals(summary)
    summary=summary[summary.DISPATCHTYPE.eq('GENERATOR')&summary.SCHEDULE_TYPE.eq('SCHEDULED')]
    details['effective']=pd.to_datetime(details.EFFECTIVEDATE).dt.tz_localize('Australia/Brisbane')
    details['version']=pd.to_numeric(details.VERSIONNO)
    details['capacity']=pd.to_numeric(details.REGISTEREDCAPACITY,errors='coerce')
    details=details.sort_values(['effective','version']).drop_duplicates(['DUID','effective'],keep='last')
    rows=[]
    for duid,g in summary.groupby('DUID'):
        capacities=details[details.DUID.eq(duid)].sort_values('effective')
        for _,r in g.sort_values('START_DATE').drop_duplicates('START_DATE',keep='last').iterrows():
            fuel_dates=[effective for d,effective in fuels if d==duid]
            cuts=sorted(set([r.START_DATE,r.END_DATE]+[t for t in fuel_dates if r.START_DATE<t<r.END_DATE]+list(capacities.loc[(capacities.effective>r.START_DATE)&(capacities.effective<r.END_DATE),'effective'])))
            for start,end in zip(cuts[:-1],cuts[1:]):
                applicable=[t for t in fuel_dates if t<=start]
                fuel=fuels.get((duid,max(applicable))) if applicable else None
                if fuel is None:continue
                eligible=capacities[capacities.effective<=start]
                if eligible.empty or start>=end:continue
                capacity=float(eligible.iloc[-1].capacity)
                if capacity<=0:continue
                rows.append(dict(duid=duid,region=r.REGIONID,station=r.STATIONID,
                    fuel=fuel,
                    valid_from=start,valid_to=end,registered_mw=capacity,provenance='retrospective_effective_registry'))
    registry=pd.DataFrame(rows).drop_duplicates()
    files=list((ledger.data/'sources/mtpasa').glob('*.parquet'))
    if not files:raise ValueError('No MT PASA source partitions')
    out=ledger.data/'prepared';out.mkdir(exist_ok=True)
    with ledger.job('prepare/coal',acceptance='Effective dates, fleet mapping and day assumption recorded') as (artifacts,checkpoint):
        parts=[]
        for i,p in enumerate(files):
            f=pd.read_parquet(p);f=f[f.duid.isin(registry.duid)].copy()
            f['delivery_start']=f.day+pd.Timedelta(hours=day_start_hour)
            f['delivery_end']=f.delivery_start+pd.Timedelta(days=1)
            f['day_semantics']='assumed_nem_trading_day' if day_start_hour==4 else 'calendar_day_sensitivity'
            parts.append(f);checkpoint(dict(partitions=i+1))
        coal=pd.concat(parts).drop_duplicates()
        rp=out/'coal_registry.parquet';cp=out/'coal.parquet'
        registry.to_parquet(rp,index=False);coal.to_parquet(cp,index=False,compression='zstd')
        audit=out/'coal_audit.json'
        atomic(audit,json.dumps(dict(duids=int(registry.duid.nunique()),rows=len(coal),day_start_hour=day_start_hour,
            added_to_inherited_scope=sorted(set(registry.duid)-set(scope.DUID)),excluded_from_inherited_scope=sorted(set(scope.DUID)-set(registry.duid)),
            standing_source_hashes={str(p.relative_to(ROOT)):digest(p) for p in unit_paths+alloc_paths+detail_paths},
            day_semantics_verified=False,promotion_blockers=['Daily alignment sensitivity and publication-vintage audit required'],
            registry_sha256=digest(rp),coal_sha256=digest(cp)),indent=2))
        artifacts.extend([rp,cp,audit])
    return audit
