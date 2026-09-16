"""Daily 336-step finalist curves and boundary-jump diagnostics."""
import json
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .core import Store,digest,fingerprint,load_config
from .data import connector_data,base_frame,design
from .diurnal import metrics,periods
from .diurnal_runner import CONFIG
from .validation import folds


def _predict(bundle,x,target_values,origin_positions,leads):
    anchor=x.own_anchor.to_numpy();winner=bundle['winner']
    if winner=='persistence':return anchor
    if winner=='seasonal_daily':period=48
    elif winner=='seasonal_weekly':period=336
    else:return anchor+bundle['models'][winner].predict(x)
    previous=origin_positions+leads-np.ceil((leads+1)/period).astype(int)*period
    value=np.full(len(leads),np.nan);good=previous>=0;value[good]=target_values[previous[good]]
    return np.where(np.isfinite(value),value,anchor)


def run_curves(config_path=CONFIG):
    c=load_config(config_path);store=Store(c);d=connector_data(c,c['connectors'][0]);d['base']=base_frame(d)
    idx=d['y'].index
    with threadpool_limits(limits=2):
        for fold in folds(c):
            for target in ('export_tight','import_tight'):
                sources=[store.root/'diurnal'/fold.name/f'band{band}'/target/'policy.joblib' for band in range(len(c['bands']))]
                if not all(p.exists() for p in sources):raise ValueError(f'Full horizon policies missing: {fold.name} {target}')
                folder=store.root/'curves'/fold.name/target;ident=str(folder.relative_to(store.root))
                fp=fingerprint([fold.dict(),target,[(str(p),digest(p)) for p in sources],digest(__file__)])
                if store.valid(ident,fp):continue
                policies=[joblib.load(p) for p in sources];values=d['y'][target].to_numpy()
                days=pd.date_range(pd.Timestamp(fold.alert_end),pd.Timestamp(fold.evaluate_end)-pd.Timedelta(days=1),freq='D')
                origins=idx.get_indexer(days);origins=origins[origins>0]
                rows=[]
                for origin in origins:
                    leads=np.arange(1,337);delivery_position=origin+leads
                    good=(delivery_position<len(idx))&(idx[origin]+pd.to_timedelta(leads*30,unit='min')+pd.Timedelta(minutes=30)<pd.Timestamp(fold.evaluate_end))
                    leads=leads[good];delivery_position=delivery_position[good]
                    if not len(leads):continue
                    band=np.array([next(j for j,(lo,hi) in enumerate(c['bands']) if lo<=h<=hi) for h in leads])
                    prediction=np.full(len(leads),np.nan);lower=np.full(len(leads),np.nan);upper=np.full(len(leads),np.nan);reference=np.full(len(leads),np.nan)
                    actual=values[delivery_position];anchor=np.repeat(values[origin-1],len(leads))
                    for j,policy in enumerate(policies):
                        m=band==j
                        if not m.any():
                            continue
                        x=design(d,np.repeat(origin,m.sum()),leads[m],'full').astype(float);x['own_anchor']=anchor[m]
                        if list(x.columns)!=policy['input_columns']:raise ValueError('Curve feature schema mismatch')
                        p=_predict(policy,x,values,np.repeat(origin,m.sum()),leads[m]);prediction[m]=p
                        reference[m]=policy['reference'].predict(anchor[m])
                        group=periods(idx[delivery_position[m]])
                        adj=np.stack([policy['period_adjustments'][int(k)] for k in group])
                        lower[m]=p+adj[:,0];upper[m]=p+adj[:,-1]
                    valid=np.isfinite(actual)&np.isfinite(anchor)&np.isfinite(prediction)
                    for k in np.flatnonzero(valid):
                        rows.append({'origin':idx[origin],'delivery':idx[delivery_position[k]],'lead':int(leads[k]),'band':int(band[k]),
                            'actual':float(actual[k]),'forecast':float(prediction[k]),'lower95':float(lower[k]),'upper95':float(upper[k]),
                            'reference':float(reference[k]),'period':int(periods([idx[delivery_position[k]]])[0])})
                frame=pd.DataFrame(rows);store.parquet(folder/'predictions.parquet',frame)
                score=metrics(frame.actual.to_numpy(),frame.forecast.to_numpy(),frame.reference.to_numpy())
                jumps=[]
                for origin,f in frame.groupby('origin'):
                    f=f.set_index('lead')
                    for boundary in (13,49,145):
                        if boundary in f.index and boundary-1 in f.index:
                            jumps.append({'origin':origin,'kind':'horizon band','boundary':str(boundary),
                                'forecast_jump_mw':float(f.loc[boundary,'forecast']-f.loc[boundary-1,'forecast']),
                                'actual_jump_mw':float(f.loc[boundary,'actual']-f.loc[boundary-1,'actual'])})
                    ordered=f.reset_index().sort_values('delivery');changed=ordered.period.ne(ordered.period.shift())
                    for r in ordered[changed&ordered.index.to_series().gt(ordered.index.min())].itertuples():
                        previous=ordered.loc[ordered.delivery.lt(r.delivery)].iloc[-1]
                        jumps.append({'origin':origin,'kind':'delivery period','boundary':str(r.delivery),
                            'forecast_jump_mw':float(r.forecast-previous.forecast),'actual_jump_mw':float(r.actual-previous.actual)})
                jump_frame=pd.DataFrame(jumps)
                if len(jump_frame):store.parquet(folder/'boundary_jumps.parquet',jump_frame)
                result={'fold':fold.dict(),'target':target,'score':score,'origins':int(frame.origin.nunique()),'rows':len(frame),
                    'boundary_summary':(jump_frame.assign(excess=lambda z:abs(z.forecast_jump_mw-z.actual_jump_mw)).groupby('kind').excess.agg(['count','mean','max']).reset_index().to_dict('records') if len(jump_frame) else []),
                    'claim':'First issue of each evaluation day; all 336 half-hour leads where the matured target fits inside the fold'}
                store.json(folder/'result.json',result);store.complete(ident,fp,folder/'result.json')
                print('CURVES',fold.name,target,len(frame),flush=True)


if __name__=='__main__':run_curves()
