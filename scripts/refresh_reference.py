"""Rebuild references without rerunning expensive unchanged dispatch extraction."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from nemic.common import *
from nemic.prepare import TRAIN_END
t=pd.read_parquet(PROCESSED/'targets.parquet')
refs=t[t.time<=TRAIN_END].groupby(['ic','season'])[['export','import']].agg(lambda x:x[x>0].median())
t=t.drop(columns=['export_reference','import_reference']).join(refs.add_suffix('_reference'),on=['ic','season'])
for d in ['export','import']:
    t[d+'_threshold']=.5*t[d+'_reference']
    for suffix in ['', '_tight']:
        t[d+suffix+'_event']=(t[d+suffix]<t[d+'_threshold']).where(t[d+suffix].notna()&t[d+'_threshold'].notna())
tail=['export_reference','import_reference','export_threshold','export_event','export_tight_event','import_threshold','import_event','import_tight_event']
t=t[[c for c in t if c not in tail]+tail]
t.to_parquet(PROCESSED/'targets.parquet',index=False)
refs.to_csv(RESULTS/'seasonal_references.csv')
print(refs)
