"""Match original AEMO predispatch vintages to the same test origin and target."""
from collections import defaultdict
import numpy as np
import pandas as pd
from .common import *
from .model import Design,IDS,band
from .prepare import TEST_START,END,read_table

def run():
    cols=['ISSUED_AT','PREDISPATCHSEQNO','DATETIME','INTERCONNECTORID','INTERVENTION','MWFLOW','EXPORTLIMIT','IMPORTLIMIT','LASTCHANGED']
    a=read_table('PREDISPATCHINTERCONNECTORRES',cols)
    original=len(a)
    a['issued']=pd.to_datetime(a.ISSUED_AT,errors='coerce')
    a['time']=pd.to_datetime(a.DATETIME,errors='coerce')
    # Allow a one-minute ingestion buffer, then first eligible half-hour origin.
    a['origin']=(a.issued+pd.Timedelta(minutes=1)).dt.ceil('30min')
    a=a[(a.origin>=TEST_START)&(a.time>a.origin)&(a.time<=END)&a.issued.notna()].copy()
    a['INTERVENTION']=pd.to_numeric(a.INTERVENTION,errors='coerce')
    a=a.sort_values(['issued','INTERVENTION']).drop_duplicates(['origin','time','INTERCONNECTORID'],keep='last')
    d=Design();a['origin_idx']=d.time.get_indexer(a.origin);a['valid_idx']=d.time.get_indexer(a.time)
    a=a[(a.origin_idx>=0)&(a.valid_idx>=0)].copy();a['h']=a.valid_idx-a.origin_idx
    a=a[a.h.between(1,336)].copy();a['band']=band(a.h.to_numpy())
    for name,col,sign in [('flow','MWFLOW',1),('export','EXPORTLIMIT',1),('import','IMPORTLIMIT',-1)]:a['aemo_'+name]=sign*pd.to_numeric(a[col],errors='coerce')
    a[['origin','time','issued','INTERCONNECTORID','origin_idx','valid_idx','h','aemo_flow','aemo_export','aemo_import']].to_parquet(RESULTS/'aemo_vintages.parquet',index=False,compression='zstd')
    stats=defaultdict(lambda:defaultdict(float));outdir=RESULTS/'aemo_matched';outdir.mkdir(exist_ok=True)
    matches=0
    for k in IDS:
      subset=a[a.INTERCONNECTORID==k]
      for path in sorted((RESULTS/'predictions').glob(k+'_*.parquet')):
        cols=['origin_idx','valid_idx','band']+[t+'_'+q for t in ['flow','export','import'] for q in ['actual','p50']]
        p=pd.read_parquet(path,columns=cols)
        aa=subset[(subset.origin_idx>=p.origin_idx.min())&(subset.origin_idx<=p.origin_idx.max())]
        matched=p.merge(aa[['origin_idx','valid_idx','issued','aemo_flow','aemo_export','aemo_import']],on=['origin_idx','valid_idx'],validate='one_to_one')
        if matched.empty:continue
        matched.to_parquet(outdir/path.name,index=False,compression='zstd');matches+=len(matched)
        for t in ['flow','export','import']:
          for b,g in matched.groupby('band'):
            good=np.isfinite(g[t+'_actual'])&np.isfinite(g[t+'_p50'])&np.isfinite(g['aemo_'+t])
            g=g[good];s=stats[(k,t,int(b))]
            s['n']+=len(g);s['aemo_ae']+=float((g['aemo_'+t]-g[t+'_actual']).abs().sum());s['selected_ae']+=float((g[t+'_p50']-g[t+'_actual']).abs().sum())
            s['aemo_se']+=float(((g['aemo_'+t]-g[t+'_actual'])**2).sum());s['selected_se']+=float(((g[t+'_p50']-g[t+'_actual'])**2).sum())
    rows=[dict(ic=k,target=t,band=b,n=int(s['n']),aemo_mae=s['aemo_ae']/s['n'],selected_mae=s['selected_ae']/s['n'],aemo_rmse=np.sqrt(s['aemo_se']/s['n']),selected_rmse=np.sqrt(s['selected_se']/s['n'])) for (k,t,b),s in stats.items() if s['n']]
    pd.DataFrame(rows).to_csv(RESULTS/'aemo_scores.csv',index=False)
    dump(RESULTS/'aemo_audit.json',dict(original_rows=original,eligible_rows=len(a),matched_pairs=matches,
      issue_start=a.issued.min(),issue_end=a.issued.max(),min_lead_hours=float(a.h.min()/2),max_lead_hours=float(a.h.max()/2),
      max_issue_after_origin_seconds=float((a.issued-a.origin).dt.total_seconds().max()),
      connectors=a.INTERCONNECTORID.unique().tolist(),
      timing='Original file creation time + 1 minute ingestion buffer; rounded upward to half-hour origin.',
      comparison='Original AEMO forecast inputs vs our realised-input conditional experiment, on identical origin/delivery pairs. Not a like-for-like operational skill claim.',
      limits='Standard predispatch horizon only; no fabricated seven-day AEMO forecasts. Tight five-minute limits have no directly comparable predispatch target.'))
    assert matches>0 and (a.issued<a.origin).all()
    print('AEMO BENCHMARK COMPLETE',matches,'matched origin/lead pairs',flush=True)

if __name__=='__main__':run()
