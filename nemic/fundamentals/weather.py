"""BOM-first coherent single-run weather; ECMWF fallback and explicit provenance."""
import json
import time
from requests import RequestException

import numpy as np
import pandas as pd

from nemic.common import session
from nemic.weather import SITES
from nemic.experiments.core import digest, fingerprint
from .tracking import atomic, now

ENDPOINT='https://single-runs-api.open-meteo.com/v1/forecast'
WEATHER_CONTRACT='coherent-15-sites-v3.2'
_DISABLED_PROVIDERS={}


def _payloads(provider,run,settings,checkpoint,group_size=5,retries=3,read_timeout=120):
    """Fetch one coherent provider/run in bounded deterministic site groups."""
    sites=list(SITES.items());payloads=[]
    for start in range(0,len(sites),group_size):
        group=sites[start:start+group_size]
        params=dict(latitude=','.join(str(x[1][0]) for x in group),longitude=','.join(str(x[1][1]) for x in group),
            hourly=','.join(settings['variables']),models=provider,run=run.strftime('%Y-%m-%dT%H:%M'),
            forecast_days=settings['forecast_days'],timezone='UTC',wind_speed_unit='ms')
        error=None
        for attempt in range(1,retries+1):
            checkpoint(dict(provider=provider,run=run.strftime('%Y%m%dT%H%M'),site_group=start//group_size+1,
                            site_groups=int(np.ceil(len(sites)/group_size)),attempt=attempt))
            try:
                response=session().get(ENDPOINT,params=params,timeout=(20,read_timeout))
                if response.status_code==429 or 500<=response.status_code<600:
                    wait=min(30,int(response.headers.get('Retry-After',0) or 5*attempt))
                    error=RuntimeError(f'HTTP {response.status_code}; retry after {wait}s')
                    if attempt<retries:time.sleep(wait);continue
                response.raise_for_status();value=response.json()
                batch=value if isinstance(value,list) else [value]
                if len(batch)!=len(group):raise ValueError('Incomplete weather site group')
                payloads.extend(batch);break
            except (RequestException,ValueError,json.JSONDecodeError) as exc:
                error=exc
                if attempt<retries:time.sleep(min(30,5*attempt))
        else:raise RuntimeError(f'Weather group {start//group_size+1} failed after {retries} attempts: {error}')
    if len(payloads)!=len(sites):raise ValueError('Incomplete coherent weather site set')
    return payloads


def normalize(payloads, run, provider, retrieved, variables, delay_hours=8):
    if not isinstance(payloads,list):payloads=[payloads]
    if len(payloads)!=len(SITES):raise ValueError('Incomplete coherent weather site set')
    run=pd.Timestamp(run)
    run=run.tz_localize('UTC') if run.tzinfo is None else run.tz_convert('UTC')
    rows=[]
    for (site,(lat,lon,region,role)),payload in zip(SITES.items(),payloads):
        hourly=payload.get('hourly',{})
        if any(v not in hourly for v in variables):raise ValueError('Required weather variable unavailable')
        units=payload.get('hourly_units',{})
        expected={'temperature_2m':'°C','relative_humidity_2m':'%','wind_speed_10m':'m/s','shortwave_radiation':'W/m²','cloud_cover':'%'}
        for v in variables:
            if units.get(v)!=expected[v]:raise ValueError(f'Weather unit mismatch {v}: {units.get(v)}')
        times=pd.to_datetime(hourly['time'],utc=True)
        for v in variables:
            for delivery,value in zip(times,hourly[v]):
                rows.append(dict(product='weather',provider=provider,run_id=run.isoformat(),nominal_run=run,
                    available_at=run+pd.Timedelta(hours=delay_hours),retrieved_at=pd.Timestamp(retrieved),
                    delivery=delivery,region=region,site=site,role=role,variable=v,value=value,
                    units=units[v],latitude=lat,longitude=lon,provenance='hindcast_or_unverified' if provider=='ecmwf_ifs' else 'original_run_publication_assumed'))
    frame=pd.DataFrame(rows)
    for c in ('nominal_run','available_at','retrieved_at','delivery'):
        frame[c]=pd.to_datetime(frame[c],utc=True).dt.tz_convert('Australia/Brisbane')
    frame['value']=pd.to_numeric(frame.value,errors='coerce')
    return frame


def acquire_weather(ledger, run):
    run=pd.Timestamp(run);run=run.tz_localize('UTC') if run.tzinfo is None else run.tz_convert('UTC')
    key=run.strftime('%Y%m%dT%H%M');ident='weather/'+key
    out=ledger.data/'sources/weather'/f'{key}.parquet';meta=out.with_suffix('.json')
    if out.exists() and meta.exists():
        cached=json.loads(meta.read_text())
        raw=ledger.data/'raw/weather'/f"{key}_{cached.get('provider','')}.json"
        try:
            frame=pd.read_parquet(out,columns=['provider','nominal_run','site','variable','units'])
            expected_rows=len(SITES)*len(ledger.c['weather']['variables'])*ledger.c['weather']['forecast_days']*24
            expected_units={'temperature_2m':'°C','relative_humidity_2m':'%','wind_speed_10m':'m/s',
                            'shortwave_radiation':'W/m²','cloud_cover':'%'}
            units_valid=all(set(frame.loc[frame.variable.eq(variable),'units'])=={unit}
                            for variable,unit in expected_units.items())
            reusable=(cached.get('run')==key and cached.get('parsed_sha256')==digest(out) and raw.exists() and
                      cached.get('raw_sha256')==digest(raw) and len(frame)==expected_rows and
                      set(frame.site)==set(SITES) and set(frame.variable)==set(ledger.c['weather']['variables']) and
                      units_valid and
                      frame.provider.nunique()==1 and frame.provider.iloc[0]==cached.get('provider') and
                      pd.to_datetime(frame.nominal_run,utc=True).nunique()==1 and
                      pd.to_datetime(frame.nominal_run,utc=True).iloc[0]==run)
            if reusable:
                ledger.record(ident,'completed','Verified reusable complete weather source contract',[raw,out,meta])
                return out
        except (KeyError,ValueError,OSError):
            pass
    if ledger.valid(ident):return out
    failures=[];settings=ledger.c['weather']
    with ledger.job(ident,acceptance='Coherent weather provider/site run and provenance verified') as (artifacts,checkpoint):
        for provider in settings['providers']:
            if provider in _DISABLED_PROVIDERS:
                failures.append(dict(provider=provider,error='Skipped after campaign-process capability failure: '+_DISABLED_PROVIDERS[provider]))
                continue
            ledger.quota('open-meteo',len(SITES),settings['daily_call_budget'])
            checkpoint(dict(provider=provider,run=key))
            try:
                payload=_payloads(provider,run,settings,checkpoint,
                                  retries=1 if provider=='bom_access_global' else 3,
                                  read_timeout=30 if provider=='bom_access_global' else 120);retrieved=now()
                frame=normalize(payload,run,provider,retrieved,settings['variables'],settings['assumed_delay_hours'])
                if frame.groupby('site').value.count().min()==0:raise ValueError('Entire weather site missing')
                raw=ledger.data/'raw/weather'/f'{key}_{provider}.json'
                atomic(raw,json.dumps(dict(provider=provider,run=run.isoformat(),variables=settings['variables'],
                                            forecast_days=settings['forecast_days'],site_group_size=5,retrieved_at=retrieved,payload=payload)))
                out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');frame.to_parquet(tmp,index=False,compression='zstd');tmp.replace(out)
                atomic(meta,json.dumps(dict(provider=provider,fallback_reasons=failures,raw_sha256=digest(raw),parsed_sha256=digest(out),
                    run=key,rows=len(frame),contract=WEATHER_CONTRACT,provenance=sorted(frame.provenance.unique()),
                    publication_delay_assumed_hours=settings['assumed_delay_hours']),indent=2))
                artifacts.extend([raw,out,meta]);break
            except Exception as exc:
                failures.append(dict(provider=provider,error=str(exc)))
                if provider=='bom_access_global':_DISABLED_PROVIDERS[provider]=str(exc)
            finally:time.sleep(1)
        else:raise RuntimeError('No coherent weather provider: '+json.dumps(failures))
    return out


def weather_at(frame, origin, delivery):
    """Within-run time interpolation; no cross-provider or height substitution."""
    if isinstance(frame,WeatherIndex):return frame.at(origin,delivery)
    eligible=frame[frame.available_at.le(origin)]
    if eligible.empty:return {},'no weather vintage'
    latest=eligible.sort_values('available_at').iloc[-1]
    run=eligible[(eligible.run_id==latest.run_id)&(eligible.provider==latest.provider)]
    output={}
    for (region,role,variable),g in run.groupby(['region','role','variable']):
        g=g.sort_values('delivery').drop_duplicates('delivery')
        if delivery<g.delivery.min() or delivery>g.delivery.max():continue
        series=g.set_index('delivery').value
        if variable=='shortwave_radiation':
            after=series[series.index>=delivery];value=after.iloc[0] if len(after) else np.nan
        else:
            idx=series.index.union(pd.DatetimeIndex([delivery])).sort_values()
            value=series.reindex(idx).interpolate('time',limit_area='inside').loc[delivery]
        output[f'{region}__{role}__{variable}']=float(value)
    output['weather_age_hours']=(origin-latest.nominal_run).total_seconds()/3600
    output['weather_ecmwf']=float(latest.provider=='ecmwf_ifs')
    return output,str(latest.provenance)


class WeatherIndex:
    """Wide half-hour weather runs with O(log runs) / O(1 delivery) lookup."""
    def __init__(self,runs):
        self.runs=sorted(runs,key=lambda x:x['available_at'])
        self.available=np.asarray([r['available_at'].value for r in self.runs],dtype=np.int64)

    @classmethod
    def from_files(cls,files):
        runs=[]
        radiation_suffix='__shortwave_radiation'
        for path in sorted(files):
            f=pd.read_parquet(path)
            if f.empty:continue
            identity=['provider','run_id','nominal_run','available_at','provenance']
            if f[identity].drop_duplicates().shape[0]!=1:raise ValueError('Weather partition mixes run identities')
            f['feature']=f.region+'__'+f.role+'__'+f.variable
            wide=f.pivot_table(index='delivery',columns='feature',values='value',aggfunc='first').sort_index()
            halfhours=pd.date_range(wide.index.min(),wide.index.max(),freq='30min')
            expanded=pd.DataFrame(index=halfhours)
            for col in wide:
                series=wide[col].reindex(halfhours)
                expanded[col]=series.bfill() if col.endswith(radiation_suffix) else series.interpolate('time',limit_area='inside')
            meta=f.iloc[0]
            runs.append(dict(provider=meta.provider,run_id=meta.run_id,nominal_run=pd.Timestamp(meta.nominal_run),
                             available_at=pd.Timestamp(meta.available_at),provenance=meta.provenance,values=expanded))
        return cls(runs)

    def at(self,origin,delivery):
        if not len(self.available):return {},'no weather vintage'
        pos=int(np.searchsorted(self.available,pd.Timestamp(origin).value,side='right')-1)
        if pos<0:return {},'no weather vintage'
        run=self.runs[pos];delivery=pd.Timestamp(delivery)
        if delivery not in run['values'].index:return {},str(run['provenance'])
        row=run['values'].loc[delivery]
        output={k:float(v) for k,v in row.items()}
        output['weather_age_hours']=(pd.Timestamp(origin)-run['nominal_run']).total_seconds()/3600
        output['weather_ecmwf']=float(run['provider']=='ecmwf_ifs')
        return output,str(run['provenance'])
