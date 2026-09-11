import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from nemic.common import *
from nemic.ingest import process_url
from nemic.prepare import read_table,START,END
for u in links('https://nemweb.com.au/Reports/ARCHIVE/ROOFTOP_PV/ACTUAL/'):
    if '20260730' in u:process_url(u)
roof=read_table('ROOFTOP_PV_ACTUAL')
roof['time']=pd.to_datetime(roof.INTERVAL_DATETIME,errors='coerce')
roof=roof[(roof.time>START)&(roof.time<=END)&roof.REGIONID.isin(REGIONS)].copy()
roof['POWER']=pd.to_numeric(roof.POWER,errors='coerce')
roof['rank']=(roof.TYPE=='MEASUREMENT').astype(int)
roof=roof.sort_values(['rank','LASTCHANGED']).drop_duplicates(['time','REGIONID'],keep='last')
s=roof.set_index(['time','REGIONID']).POWER;s.index.names=['time','region']
r=pd.read_parquet(PROCESSED/'regional_30min.parquet');r['rooftop']=s
r.to_parquet(PROCESSED/'regional_30min.parquet')
d=pd.read_parquet(PROCESSED/'drivers.parquet')
for reg in REGIONS:d[reg+'__rooftop']=s.xs(reg,level='region').reindex(d.index)
d.to_parquet(PROCESSED/'drivers.parquet')
a=__import__('json').loads((RESULTS/'data_audit.json').read_text());a['driver_missing_fraction']=d.isna().mean().to_dict()
a['seasonal_reference']='Training-only seasonal median of positive reported directional limits; forced-flow/zero observations remain targets and events.'
dump(RESULTS/'data_audit.json',a)
print('Remaining missing rooftop',d.filter(like='__rooftop').isna().sum().to_dict())
