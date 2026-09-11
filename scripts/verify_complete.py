"""Completion requires evidence for every connector, target, origin and lead."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np,pandas as pd,pyarrow.parquet as pq
from nemic.common import *
from nemic.model import Design,IDS,TARGETS
from nemic.prepare import TEST_START,END

d=Design();lo=d.time.searchsorted(TEST_START);hi=d.time.searchsorted(END,side='right')
expected=sum(min(336,hi-1-o) for o in range(lo,hi-1))
coverage={};quantiles=True;rows_total=0
for k in IDS:
    rows=0;origin_counts={};h_counts={};seen_origins=set()
    for p in sorted((RESULTS/'predictions').glob(k+'_*.parquet')):
        cols=['origin_idx','valid_idx','h']+[t+'_'+q for t in TARGETS for q in ['actual','p10','p50','p90']]
        f=pd.read_parquet(p,columns=cols);rows+=len(f)
        assert (f.valid_idx==f.origin_idx+f.h).all()
        assert f.valid_idx.max()<hi and f.origin_idx.min()>=lo
        assert not f.duplicated(['origin_idx','h']).any()
        assert f.h.between(1,336).all()
        these=set(f.origin_idx.unique());assert not seen_origins.intersection(these);seen_origins.update(these)
        assert np.isfinite(f.iloc[:,3:].to_numpy()).all()
        for t in TARGETS:
            assert (f[t+'_p10']<=f[t+'_p50']).all() and (f[t+'_p50']<=f[t+'_p90']).all()
        for o,n in f.groupby('origin_idx').size().items():origin_counts[o]=origin_counts.get(o,0)+int(n)
        for h,n in f.groupby('h').size().items():h_counts[h]=h_counts.get(h,0)+int(n)
    assert rows==expected,(k,rows,expected)
    assert set(h_counts)==set(range(1,337))
    assert all(h_counts[h]==hi-lo-h for h in range(1,337))
    assert all(origin_counts.get(o)==min(336,hi-1-o) for o in range(lo,hi-1))
    coverage[k]=dict(pairs=rows,origins=len(origin_counts),leads=len(h_counts));rows_total+=rows
scores=pd.read_csv(RESULTS/'scores.csv')
for k in IDS:
 for t in TARGETS:
  for b in range(4):
   f=scores[(scores.ic==k)&(scores.target==t)&(scores.band==b)&(scores['slice']=='all')]
   assert set(f.model)=={'persistence','seasonal','fundamentals','weather','availability','network','selected'}
   assert np.isfinite(f.mae).all()
scenario=pd.read_csv(RESULTS/'scenario_example.csv')
assert len(scenario)==6*336 and set(scenario.ic)==set(IDS)
for filename in ['data_audit.json','training_proof.json','test_proof.json','aemo_audit.json','aemo_scores.csv','skill_confidence.csv','validation_leaderboard.csv']:
    assert (RESULTS/filename).exists(),filename
dump(RESULTS/'completion_audit.json',dict(status='passed',connectors=coverage,total_origin_lead_pairs=rows_total,
    target_forecasts=rows_total*5,scenario_rows=len(scenario),finite_ordered_quantiles=True,all_models_scored=True))
print('COMPLETION AUDIT PASSED',rows_total,'origin/lead pairs',rows_total*5,'target forecasts')
