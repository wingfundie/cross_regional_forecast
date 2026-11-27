"""Compare dated static/alternate ratings and a prior-cycle weather model with dispatch ratings."""
from datetime import timedelta
import csv
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
from thermal import OUT, TRAIN, EVAL, RATING, pilot, write

DYNAMIC = 'VRAT15_RCWE'
STANDING = pilot.BASE+'Network/PUBLIC_NETWORK_20260213.zip'
MEMBER = 'PUBLIC_NETWORK_20260213100003_0000000503232313.zip'
WEATHER = 'https://single-runs-api.open-meteo.com/v1/forecast'

def standing():
    z,modified=pilot.onefile(STANDING,MEMBER)
    content=z.read(z.namelist()[0])
    reader=csv.reader(io.TextIOWrapper(io.BytesIO(content),encoding='utf-8-sig'))
    header=next(reader)
    assert header[2]=='NETWORK_RATING' and header[4]=='PUBLIC'
    created=pd.Timestamp(' '.join(header[5:7]))
    assert max(created,modified)<pd.Timestamp('2026-02-18 16:00')
    tables={};rating=[];static=[]
    for row in reader:
        if row[0]=='I':
            tables[row[2]]=row[4:]
        elif row[0]=='D':
            record=dict(zip(tables[row[2]],row[4:]))
            if not record['VALIDFROM']<'2026/02/18'<record['VALIDTO']:continue
            if row[2]=='RATING' and record['SPD_ID'] in [RATING,DYNAMIC]:rating.append(record)
            if row[2]=='STATICRATING' and (record['SUBSTATIONID'],record['EQUIPMENTID'],record['RATINGLEVEL']) in [('BANGOWF','9GL','NORM'),('RCTS','RCTS_WETS_220','LDSH')]:
                static.append(record)
    assert len(rating)==2 and {r['ISDYNAMIC'] for r in rating}=={'0','1'}
    write(pd.DataFrame(rating),'rating_identifiers.csv')
    write(pd.DataFrame(static),'alternate_ratings.csv')
    (OUT/'rating_standing_source.json').write_text(json.dumps({**pilot.log[-1],'csv_sha256':pilot.sha(content),'public_produced':str(created)},indent=2))

def weather(day):
    # All cycles deliberately predate the prior-afternoon predispatch public file by >18 hours.
    d=pd.Timestamp(f'2026-02-{day:02d}')
    run=d-timedelta(days=2)+timedelta(hours=12)
    params={'latitude':-34.45,'longitude':142.42,'models':'ecmwf_ifs','hourly':'temperature_2m,wind_speed_10m','run':run.strftime('%Y-%m-%dT%H:%M'),'timezone':'GMT'}
    with pilot.session().get(WEATHER,params=params,timeout=(10,40)) as response:
        response.raise_for_status();blob=response.content;source=response.url
    data=json.loads(blob)
    assert data['utc_offset_seconds']==0 and data['hourly_units']['wind_speed_10m']=='km/h'
    record=pd.DataFrame(data['hourly']);record['utc']=pd.to_datetime(record.time)
    # Evaluated windows span 00:05-02:00 UTC. Interpolate only predictions from this one earlier run.
    record=record.loc[record.utc.between(d,d+timedelta(hours=2)),['utc','temperature_2m','wind_speed_10m']]
    assert len(record)==3
    normalized_hash=pilot.sha(json.dumps(data['hourly'],sort_keys=True).encode())
    return record.assign(run_utc=run,estimated_prior_publication='no exact receipt archived',model='ecmwf_ifs',grid_lat=data['latitude'],grid_lon=data['longitude'],url=source,response_sha256=pilot.sha(blob),hourly_payload_sha256=normalized_hash)

def capture():
    standing()
    weather_data=pd.concat(ThreadPoolExecutor(3).map(weather,[*TRAIN,*EVAL]))
    write(weather_data,'weather_runs.csv')

def scores():
    t=pd.read_csv(OUT/'rating_panel.csv',parse_dates=['end'])
    train=t[t.end.dt.day.isin(TRAIN)]
    describe=train.select_dtypes('number').describe().T
    eligible=describe[(describe['count']==len(train))&(describe['min']>20)&(describe['max']<2000)]
    spread=(eligible['max']-eligible['min'])/eligible['50%']
    assert DYNAMIC in spread[spread==spread.max()].index
    static=pd.read_csv(OUT/'alternate_ratings.csv')
    bango=static.loc[static.APPLICATIONID.eq('N_SUM_D'),'RATINGVALUE'].item()
    assert (t[RATING]==bango).all()
    curve={int(r.APPLICATIONID.rsplit('_',1)[1]):r.RATINGVALUE for _,r in static[static.SUBSTATIONID.eq('RCTS')].iterrows()}
    assert set(curve)==set(range(5,46,5))
    hourly=pd.read_csv(OUT/'weather_runs.csv',parse_dates=['utc','run_utc'])
    t=t[['end',DYNAMIC]].copy()
    issued=pd.read_csv(OUT/'issued.csv',parse_dates=['created','end'])
    issued=issued[issued['product'].eq('PREDISPATCHIS')]
    for day,g in t.groupby(t.end.dt.day):
        w=hourly[hourly.utc.dt.day.eq(day)].sort_values('utc')
        if day in EVAL:
            origin_utc=issued.loc[issued.end.dt.day.eq(day),'created'].min()-timedelta(hours=10)
            assert (origin_utc-w.run_utc).min()>timedelta(hours=18)
        for feature in ['temperature_2m','wind_speed_10m']:
            t.loc[g.index,feature]=np.interp((g.end-timedelta(hours=10)).astype('int64'),w.utc.astype('int64'),w[feature])
    t['slot']=t.end.dt.ceil('30min');t['clock']=t.slot.dt.time
    a=t.groupby('slot',as_index=False).mean(numeric_only=True);a['clock']=a.slot.dt.time
    train=a[a.slot.dt.day.isin(TRAIN)];test=a[a.slot.dt.day.isin(EVAL)].copy()
    features=['temperature_2m','wind_speed_10m']
    def design(df): return np.column_stack([np.ones(len(df)),df[features].values])
    beta=np.linalg.lstsq(design(train),train[DYNAMIC],rcond=None)[0]
    test['train_median']=train[DYNAMIC].median()
    test['clock_profile']=test.clock.map(train.groupby('clock')[DYNAMIC].mean())
    test['weather_regression']=design(test)@beta
    test['static_25C']=curve[25]
    t['alternate_from_forecast_temperature']=t.temperature_2m.apply(lambda temp: curve[int(np.clip(5*np.ceil(temp/5),5,45))])
    test['weather_static_alternate']=test.slot.map(t.groupby('slot').alternate_from_forecast_temperature.mean())
    test['static_envelope_min']=min(curve.values());test['static_envelope_max']=max(curve.values())
    out=[]
    for k in ['train_median','clock_profile','static_25C','weather_static_alternate','weather_regression']:
        e=test[k]-test[DYNAMIC];out.append(dict(method=k,half_hours=len(e),mae=e.abs().mean(),bias=e.mean(),max_abs=e.abs().max()))
    write(test,'dynamic_rating_predictions.csv');write(pd.DataFrame(out),'dynamic_rating_metrics.csv')
    print(pd.DataFrame(out).to_string(index=False))
    tr=t[t.end.dt.day.isin(TRAIN)];te=t[t.end.dt.day.isin(EVAL)]
    print('train range',tr[DYNAMIC].min(),tr[DYNAMIC].max(),'test',te[DYNAMIC].min(),te[DYNAMIC].max(),'native coverage',te[DYNAMIC].between(min(curve.values()),max(curve.values())).sum(),len(te),'coefficients',beta)
    (OUT/'dynamic_rating_model.json').write_text(json.dumps(dict(coefficients=dict(zip(['intercept',*features],beta)),selected_from_training_only=DYNAMIC,training_cases=len(tr),evaluation_cases=len(te),native_heldout_range=[te[DYNAMIC].min(),te[DYNAMIC].max()],static_bounds=[min(curve.values()),max(curve.values())],train_median=float(train[DYNAMIC].median()),envelope_native_coverage=int(te[DYNAMIC].between(min(curve.values()),max(curve.values())).sum())),indent=2,default=float))

if __name__=='__main__':
    if 'capture' in sys.argv:capture()
    scores()
