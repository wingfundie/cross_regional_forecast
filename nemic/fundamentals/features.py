"""Versioned regional, cross-region and hierarchical interaction feature blocks."""
from __future__ import annotations
from itertools import combinations
from collections import OrderedDict
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nemic.production.contracts import CONNECTORS, connector
from .sources import REGIONS, nem_time
from .weather import weather_at,WeatherIndex


def pasa_at(frame, origin, delivery):
    """Choose a single complete regional run: ST first, PD where ST is absent."""
    if isinstance(frame,(PasaIndex,PasaStore)):return frame.at(origin,delivery)
    required={'demand50','wind_uigf','solar_uigf','wind_constrained','solar_constrained'}
    eligible=frame[frame.available_at.le(origin)&frame.delivery.eq(delivery)]
    for product in ('stpasa','pdpasa'):
        f=eligible[eligible['product'].eq(product)]
        for run_id in f.sort_values('available_at',ascending=False).run_id.drop_duplicates():
            run=f[f.run_id.eq(run_id)]
            pivot=run.pivot_table(index='region',columns='variable',values='value',aggfunc='first')
            if not set(REGIONS)<=set(pivot.index) or not required<=set(pivot.columns):continue
            if pivot.loc[list(REGIONS),list(required)].isna().any().any():continue
            values={f'{r}__{v}':float(pivot.loc[r,v]) for r in REGIONS for v in pivot.columns}
            values['pasa_age_hours']=(origin-run.available_at.max()).total_seconds()/3600
            values['pasa_is_pd']=float(product=='pdpasa')
            return values,dict(product=product,run_id=run_id,available_at=run.available_at.max())
    return {},None


class PasaIndex:
    """Compact coherent runs indexed by delivery, with availability-sorted search."""
    def __init__(self,wide):
        self.frame=wide.sort_values('available_at').reset_index(drop=True)
        required=[r+'__'+v for r in REGIONS for v in ('demand50','wind_uigf','solar_uigf','wind_constrained','solar_constrained')]
        self.frame=self.frame.dropna(subset=required).reset_index(drop=True)
        self.groups=self.frame.groupby(['product','delivery'],sort=False).indices
        self.columns=[c for c in self.frame if '__' in c]
        self.available_at=self.frame.available_at

    @classmethod
    def from_files(cls,files):
        parts=[]
        for path in files:
            f=pd.read_parquet(path,columns=['product','run_id','available_at','delivery','region','variable','value'])
            f['feature']=f.region+'__'+f.variable
            keys=['product','run_id','available_at','delivery']
            wide=f.pivot_table(index=keys,columns='feature',values='value',aggfunc='first').reset_index()
            parts.append(wide)
        return cls(pd.concat(parts,ignore_index=True).drop_duplicates())

    def at(self,origin,delivery):
        for product in ('stpasa','pdpasa'):
            ix=self.groups.get((product,delivery))
            if ix is None:continue
            candidates=self.frame.iloc[ix]
            pos=candidates.available_at.searchsorted(origin,side='right')-1
            if pos<0:continue
            row=candidates.iloc[pos]
            values={c:float(row[c]) for c in self.columns}
            values['pasa_age_hours']=(origin-row.available_at).total_seconds()/3600
            values['pasa_is_pd']=float(product=='pdpasa')
            return values,dict(product=product,run_id=row.run_id,available_at=row.available_at)
        return {},None


class PasaStore:
    """LRU reader for immutable delivery-date PASA shards."""
    def __init__(self,manifest,cache_dates=20):
        self.manifest_path=Path(manifest);self.root=self.manifest_path.parent
        self.manifest=json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.dates=self.manifest['dates'];self.cache=OrderedDict();self.cache_dates=cache_dates
        self.available_at=pd.Series([pd.Timestamp(self.manifest['available_min']),pd.Timestamp(self.manifest['available_max'])])

    def _index(self,delivery):
        day=pd.Timestamp(delivery).strftime('%Y-%m-%d')
        if day in self.cache:
            self.cache.move_to_end(day);return self.cache[day]
        pieces=self.dates.get(day,[])
        if not pieces:return None
        frame=pd.concat([pd.read_parquet(self.root/p) for p in pieces],ignore_index=True).drop_duplicates()
        index=PasaIndex(frame);self.cache[day]=index
        while len(self.cache)>self.cache_dates:self.cache.popitem(last=False)
        return index

    def at(self,origin,delivery):
        index=self._index(delivery)
        return index.at(origin,delivery) if index is not None else ({},None)


def coal_at(frame, registry, origin, delivery):
    """Daily boundaries must be supplied explicitly by the audited MT adapter."""
    if isinstance(frame,CoalIndex):return frame.at(origin,delivery)
    needed={'duid','region','fuel','valid_from','valid_to','registered_mw','station'}
    if not needed<=set(registry):raise ValueError('Effective-dated coal registry required')
    if not {'delivery_start','delivery_end'}<=set(frame):
        raise ValueError('MT PASA daily interval semantics have not been audited')
    reg=registry[(registry.valid_from<=delivery)&(registry.valid_to>delivery)&registry.fuel.isin(['black_coal','brown_coal'])]
    if reg.duid.duplicated().any():raise ValueError('Overlapping coal registry versions')
    f=frame[(frame.available_at<=origin)&(frame.delivery_start<delivery)&(frame.delivery_end>=delivery)]
    f=f.sort_values('available_at').drop_duplicates('duid',keep='last')
    extra=[c for c in ('recall_hours','unit_state','latest_offer') if c in f]
    joined=reg.merge(f[['duid','capacity_mw']+extra],on='duid',how='left',validate='one_to_one')
    result={}
    for region in REGIONS:
        g=joined[joined.region.eq(region)]
        if g.empty:
            result[region+'__coal_available']=0.;result[region+'__coal_coverage']=1.;continue
        known=g.capacity_mw.notna();coverage=float(known.mean())
        result[region+'__coal_coverage']=coverage
        result[region+'__coal_available']=float(g.capacity_mw.sum()) if known.all() else np.nan
        result[region+'__coal_known_mw']=float(g.capacity_mw.sum()) if known.any() else np.nan
        result[region+'__coal_fraction']=result[region+'__coal_available']/max(float(g.registered_mw.sum()),25)
        stations=g.groupby('station').capacity_mw.sum(min_count=1)
        total=stations.sum()
        result[region+'__coal_station_hhi']=float(((stations/total)**2).sum()) if known.all() and total>0 else np.nan
        result[region+'__coal_unavailable_mw']=float((g.registered_mw-g.capacity_mw).clip(lower=0).sum()) if known.all() else np.nan
        if 'recall_hours' in g:
            result[region+'__coal_recall_max_hours']=float(g.recall_hours.max())
            result[region+'__coal_recall_known_fraction']=float(g.recall_hours.notna().mean())
        for fuel in ('black_coal','brown_coal'):
            part=g[g.fuel.eq(fuel)]
            result[region+'__'+fuel+'_available']=float(part.capacity_mw.sum()) if part.capacity_mw.notna().all() else np.nan
    return result


class CoalIndex:
    """Delivery-interval partitioned MT PASA lookup; avoids full-frame scans."""
    def __init__(self,frame,registry):
        if not {'delivery_start','delivery_end'}<=set(frame):raise ValueError('Audited coal delivery bounds required')
        self.registry=registry
        self.groups={pd.Timestamp(start):group.sort_values('available_at').reset_index(drop=True)
                     for start,group in frame.groupby('delivery_start',sort=True)}
        self.starts=sorted(self.groups)
        self.start_values=np.asarray([x.value for x in self.starts],dtype=np.int64)
        self.empty=frame.iloc[:0].copy()

    def at(self,origin,delivery):
        delivery=pd.Timestamp(delivery)
        pos=int(np.searchsorted(self.start_values,delivery.value,side='left')-1)
        if pos<0:return coal_at(self.empty,self.registry,pd.Timestamp(origin),delivery)
        group=self.groups[self.starts[pos]]
        if group.delivery_end.max()<delivery:return coal_at(self.empty,self.registry,pd.Timestamp(origin),delivery)
        return coal_at(group,self.registry,pd.Timestamp(origin),delivery)


def engineer(values, name, network=None, interactions=True):
    """Pure function; unavailable ingredients propagate as missing, never zero."""
    source,sink=CONNECTORS[connector(name)][1:]
    x=dict(values);groups={k:('weather' if any(v in k for v in ('temperature','humidity','wind_speed','radiation','cloud','weather_')) else 'coal' if 'coal' in k else 'demand' if 'demand' in k else 'renewables' if 'wind_' in k or 'solar_' in k else 'quality') for k in x}
    parents={}
    def add(k,v,g,ps=()):x[k]=v;groups[k]=g;parents[k]=list(ps)
    for region in REGIONS:
        def get(v):return x.get(region+'__'+v,np.nan)
        for mode in ('uigf','constrained'):
            w,s=get('wind_'+mode),get('solar_'+mode)
            add(region+'__renewables_'+mode,w+s,'balance')
            add(region+'__residual_'+mode,get('demand50')-w-s,'balance')
        for fuel in ('wind','solar'):
            pressure=get(fuel+'_uigf')-get(fuel+'_constrained')
            add(region+'__'+fuel+'_suppression',pressure,'suppression')
            add(region+'__'+fuel+'_suppression_fraction',pressure/max(abs(get(fuel+'_uigf')),25),'suppression')
            add(region+'__'+fuel+'_negative_suppression',float(pressure<0) if np.isfinite(pressure) else np.nan,'quality')
        add(region+'__coal_balance',get('residual_uigf')-get('coal_available'),'coal')
        add(region+'__positive_coal_balance',max(get('coal_balance'),0),'coal')
        add(region+'__demand_poe_spread',get('demand10')-get('demand90'),'pasa')
        add(region+'__renewable_surplus',max(-get('residual_uigf'),0),'balance')
        add(region+'__positive_residual',max(get('residual_uigf'),0),'balance')
        for hours in (.5,1,3,6):
            add(region+f'__solar_decline_{hours}h',max(-get(f'solar_uigf_ramp_{hours}h'),0),'ramp')
            add(region+f'__demand_rise_{hours}h',max(get(f'demand50_ramp_{hours}h'),0),'ramp')
    pair_vars=['demand50','renewables_uigf','renewables_constrained','residual_uigf','residual_constrained','coal_available','coal_balance','wind_suppression','solar_suppression']
    for a,b in combinations(REGIONS,2):
        for variable in pair_vars:
            av,bv=x.get(a+'__'+variable,np.nan),x.get(b+'__'+variable,np.nan)
            prefix=f'pair__{a}_{b}__{variable}'
            add(prefix+'__sum',av+bv,'cross_region')
            add(prefix+'__difference',av-bv,'cross_region')
            add(prefix+'__abs_difference',abs(av-bv),'cross_region')
            add(prefix+'__normalized_difference',(av-bv)/max(abs(av)+abs(bv),25),'cross_region')
        for role in ('demand','corridor','renewable'):
            for variable in ('temperature_2m','relative_humidity_2m','wind_speed_10m'):
                av=x.get(f'{a}__{role}__{variable}',np.nan);bv=x.get(f'{b}__{role}__{variable}',np.nan)
                add(f'pair__{a}_{b}__{role}_{variable}_difference',av-bv,'weather_cross')
    for variable in pair_vars:
        all_values=[x.get(r+'__'+variable,np.nan) for r in REGIONS]
        add('nem__'+variable,float(np.sum(all_values)),'nem_context')
        add('rest__'+variable,float(np.sum([x.get(r+'__'+variable,np.nan) for r in REGIONS if r not in (source,sink)])),'nem_context')
        add('endpoint__'+variable+'_difference',x.get(sink+'__'+variable,np.nan)-x.get(source+'__'+variable,np.nan),'endpoint')
        add('endpoint__'+variable+'_sum',x.get(sink+'__'+variable,np.nan)+x.get(source+'__'+variable,np.nan),'endpoint')
    if network:
        for k,v in network.items():add(k,v,'nos' if k.startswith('nos_') else 'network')
    if interactions:
        def product(k,a,b):
            if a in x and b in x:add(k,x[a]*x[b],'interaction',[a,b])
        for side in ('upper','lower'):
            product('ix__imbalance_'+side,'endpoint__residual_uigf_difference',side+'_room')
            product('ix__suppression_'+side,'endpoint__solar_suppression_sum',side+'_switch_gap')
            product('ix__coal_'+side,'endpoint__coal_balance_difference',side+'_gen_tightening')
            product('ix__regime_'+side,'endpoint__residual_uigf_difference',side+'_setter_age')
        product('ix__coal_demand','endpoint__coal_available_difference','endpoint__residual_uigf_difference')
        product('ix__coincident_coal_stress',source+'__positive_coal_balance',sink+'__positive_coal_balance')
        product('ix__source_surplus_sink_deficit',source+'__renewable_surplus',sink+'__positive_residual')
        product('ix__sink_surplus_source_deficit',sink+'__renewable_surplus',source+'__positive_residual')
        for region in REGIONS:
            product('ix__humidity_'+region,f'{region}__demand__temperature_2m',f'{region}__demand__relative_humidity_2m')
            for hours in (.5,1,3,6):
                product(f'ix__evening_ramp_{region}_{hours}h',region+f'__solar_decline_{hours}h',region+f'__demand_rise_{hours}h')
        for field in ('nos_count','nos_overlap','nos_upper_sets','nos_lower_sets'):
            for balance in ('residual_uigf_difference','coal_available_sum','renewables_uigf_sum'):
                product('ix__'+field+'_'+balance,field,'endpoint__'+balance)
    return x,dict(groups=groups,parents={k:v for k,v in parents.items() if v},feature_version='fundamentals-v3.0')


class ForecastFeatures:
    def __init__(self,pasa,weather=None,coal=None,registry=None):
        self.pasa=pasa;self.weather=weather;self.coal=coal;self.registry=registry

    def build(self,origin,delivery,name,network=None):
        origin,delivery=nem_time(origin),nem_time(delivery)
        if delivery<=origin:raise ValueError('Positive delivery lead required')
        values,run=pasa_at(self.pasa,origin,delivery)
        if not values:raise ValueError('No admissible complete PASA regional vintage')
        for hours in (.5,1,3,6):
            prev,previous_run=pasa_at(self.pasa,origin,delivery-pd.Timedelta(hours=hours))
            same=previous_run is not None and previous_run['run_id']==run['run_id'] and previous_run['product']==run['product']
            values[f'pasa_transition_{hours}h']=float(not same)
            for region in REGIONS:
                for variable in ('demand50','wind_uigf','solar_uigf','wind_constrained','solar_constrained'):
                    k=f'{region}__{variable}'
                    values[k+f'_ramp_{hours}h']=values[k]-prev.get(k,np.nan) if same else np.nan
        if self.weather is not None:
            weather,provenance=weather_at(self.weather,origin,delivery);values.update(weather)
        if self.coal is not None:values.update(coal_at(self.coal,self.registry,origin,delivery))
        return engineer(values,name,network)
