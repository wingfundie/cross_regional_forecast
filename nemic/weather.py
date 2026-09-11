"""Open-Meteo ERA5 reanalysis; explicitly conditional, never issue-time forecasts."""
import json, hashlib, time
import numpy as np
import pandas as pd
from .common import *

SITES = {
 'NSW_Sydney':(-33.87,151.21,'NSW1','demand'),
 'NSW_Armidale':(-30.51,151.67,'NSW1','corridor'),
 'NSW_Dubbo':(-32.25,148.60,'NSW1','renewable'),
 'QLD_Brisbane':(-27.47,153.03,'QLD1','demand'),
 'QLD_Millmerran':(-27.88,151.27,'QLD1','corridor'),
 'QLD_Rockhampton':(-23.38,150.51,'QLD1','renewable'),
 'VIC_Melbourne':(-37.81,144.96,'VIC1','demand'),
 'VIC_Heywood':(-38.13,141.63,'VIC1','corridor'),
 'VIC_Horsham':(-36.71,142.20,'VIC1','renewable'),
 'SA_Adelaide':(-34.93,138.60,'SA1','demand'),
 'SA_Robertstown':(-34.00,139.08,'SA1','corridor'),
 'SA_Jamestown':(-33.20,138.61,'SA1','renewable'),
 'TAS_Hobart':(-42.88,147.33,'TAS1','demand'),
 'TAS_GeorgeTown':(-41.10,146.83,'TAS1','corridor'),
 'TAS_Woolnorth':(-40.68,144.75,'TAS1','renewable'),
}
VARS=['temperature_2m','wind_speed_100m','shortwave_radiation','cloud_cover','relative_humidity_2m']

def run():
    frames=[]; records=[]
    for name,(lat,lon,region,role) in SITES.items():
        path=RAW/f'weather_{name}_202309_202608.json'
        params=dict(latitude=lat,longitude=lon,start_date='2023-08-31',end_date='2026-09-01',
                    hourly=','.join(VARS),models='era5',timezone='UTC',wind_speed_unit='ms')
        url='https://archive-api.open-meteo.com/v1/archive'
        if not path.exists():
            r=get(url,params=params)
            obj=r.json()
            if 'hourly' not in obj: raise ValueError(obj)
            dump(path,obj)
            time.sleep(1)
        obj=json.loads(path.read_text())
        df=pd.DataFrame(obj['hourly'])
        df['time']=pd.to_datetime(df['time'])+pd.Timedelta(hours=10)
        df=df.set_index('time')
        df.columns=[name+'__'+c for c in df.columns]
        frames.append(df)
        records.append(dict(site=name,latitude=lat,longitude=lon,region=region,role=role,
                            url=url,params=params,rows=len(df),missing=int(df.isna().sum().sum()),
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        print('WEATHER',name,len(df),'hours',flush=True)
    hourly=pd.concat(frames,axis=1).sort_index()
    halfhour=hourly.resample('30min').interpolate('time',limit=1)
    # Radiation is the mean of the preceding hour. Assign it to both contained
    # half-hours, preserving the source hour's energy rather than inventing ramps.
    for col in hourly:
        if col.endswith('shortwave_radiation'):
            halfhour[col]=hourly[col].reindex(halfhour.index).bfill(limit=1)
    hourly.to_parquet(PROCESSED/'weather_hourly.parquet')
    halfhour.to_parquet(PROCESSED/'weather_30min.parquet')
    dump(DATA/'weather_manifest.json',records)
    print('WEATHER COMPLETE',halfhour.shape,flush=True)

if __name__=='__main__':run()
