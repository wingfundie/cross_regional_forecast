"""Exact accepted-offer arrays, same-delivery deltas and effective-offer reconciliation."""
import numpy as np
from .core import *

BANDS=[f'BANDAVAIL{i}' for i in range(1,11)]
PRICES=[f'PRICEBAND{i}' for i in range(1,11)]
PARAMS=['MAXAVAIL','RAMPUPRATE','RAMPDOWNRATE','FIXEDLOAD','PASAAVAILABILITY','ENERGYLIMIT','RECALL_PERIOD']
FIELDS=BANDS+PARAMS

def expand_offer(frame):
    out=np.full((288,len(FIELDS)),np.nan);coverage=np.zeros(288,dtype=np.int16)
    for r in frame.itertuples(index=False):
        lo=int(r.PERIODID)-1;hi=int(r.PERIODIDTO)
        if not (0<=lo<hi<=288):raise ValueError('Invalid sparse period range')
        coverage[lo:hi]+=1
        out[lo:hi]=[getattr(r,c,np.nan) for c in FIELDS]
    if not np.all(coverage==1):raise ValueError('Sparse offer has gaps or overlapping ranges')
    if np.isnan(out[:,:11]).any():raise ValueError('Missing band volume or maximum availability')
    return out

def volume_metrics(before,after):
    delta=np.asarray(after)-np.asarray(before)
    plus=float(np.maximum(delta,0).sum());minus=float(np.maximum(-delta,0).sum())
    return dict(minimum_redistribution_mw=min(plus,minus),added_offered_mw=max(plus-minus,0),removed_offered_mw=max(minus-plus,0))

def curve_metrics(state,prices,direction):
    volumes=state[:,:10]
    result={f'le_{p}':volumes[:,prices<=p].sum(axis=1) for p in CONFIG['thresholds']}
    # LOAD: willingness to consume is evaluated above a purchase price, not below.
    result.update({f'ge_{p}':volumes[:,prices>=p].sum(axis=1) for p in CONFIG['thresholds']})
    result['total']=volumes.sum(axis=1)
    result['availability_limited_total']=np.minimum(result['total'],state[:,10])
    return result

def run():
    init();inv=load_table('inventory').set_index('DUID');allowed=set(inv.index)
    h=load_table('offers_BIDDAYOFFER');s=load_table('offers_BIDOFFERPERIOD_SPARSE')
    h=h[h.DUID.isin(allowed)&h.BIDTYPE.eq('ENERGY')].copy();s=s[s.DUID.isin(allowed)&s.BIDTYPE.eq('ENERGY')].copy()
    times(h,['OFFERDATE','SETTLEMENTDATE']);times(s,['OFFERDATETIME','TRADINGDATE'])
    number(h,PRICES+['VERSIONNO','MINIMUMLOAD','T1','T2','T3','T4','DAILYENERGYCONSTRAINT']);number(s,FIELDS+['PERIODID','PERIODIDTO'])
    h=h[h.SETTLEMENTDATE.eq(START.normalize())&h.OFFERDATE.le(END)]
    s=s[s.TRADINGDATE.eq(START.normalize())&s.OFFERDATETIME.le(END)]
    keys=['DUID','DIRECTION','OFFERDATE']
    if h.duplicated(keys).any():raise ValueError('Ambiguous header offer identity')
    h['offer_id']=['O'+str(i).zfill(6) for i in range(len(h))]
    save_table('headers',h)
    b=load_table('bidmove_BIDPEROFFER_D');b=b[b.DUID.isin(allowed)].copy()
    times(b,['OFFERDATE','INTERVAL_DATETIME']);number(b,BANDS+['MAXAVAIL','PERIODID'])
    segment_rows=[];revision_rows=[];snapshots=[];effective_rows=[];audit=[]
    array_dir=ROOT/'data/arrays';array_dir.mkdir(exist_ok=True)
    timeline=intervals()
    for (duid,direction),headers in h.groupby(['DUID','DIRECTION'],sort=True):
        headers=headers.sort_values(['OFFERDATE','VERSIONNO'])
        periods=s[s.DUID.eq(duid)&s.DIRECTION.eq(direction)]
        grouped={t:f for t,f in periods.groupby('OFFERDATETIME')}
        arrays=[];prices=[];valid_headers=[]
        for _,r in headers.iterrows():
            if r.OFFERDATE not in grouped:raise ValueError(f'Unpaired header {r.offer_id}')
            arrays.append(expand_offer(grouped[r.OFFERDATE]));prices.append(r[PRICES].to_numpy(dtype=float));valid_headers.append(r)
        cube=np.stack(arrays);price=np.stack(prices);heads=pd.DataFrame(valid_headers).reset_index(drop=True)
        offer_times=heads.OFFERDATE.to_numpy(dtype='datetime64[ns]');ids=heads.offer_id.to_numpy(dtype=str)
        np.savez_compressed(array_dir/f'{duid}_{direction}.npz',state=cube.astype('float32'),prices=price,offer_times=offer_times.astype('int64'),offer_ids=ids)
        pre=np.flatnonzero(offer_times<np.datetime64(SIGNAL));base=pre[-1] if len(pre) else None
        bm=curve_metrics(cube[base],price[base],direction) if base is not None else None
        blocks=np.array([block(t) for t in timeline])
        for j in range(1,len(heads)):
            r=heads.iloc[j];prev=heads.iloc[j-1];old=cube[j-1];new=cube[j]
            metrics=curve_metrics(new,price[j],direction);oldmetrics=curve_metrics(old,price[j-1],direction)
            changed=~np.isclose(old,new,equal_nan=True).all(axis=1)
            ladder_changed=not np.allclose(price[j],price[j-1])
            header_changed=any(not ((pd.isna(r[c]) and pd.isna(prev[c])) or r[c]==prev[c]) for c in ['MINIMUMLOAD','T1','T2','T3','T4','DAILYENERGYCONSTRAINT'])
            if ladder_changed or header_changed:changed[:]=True
            future=(timeline-pd.Timedelta(minutes=5))>=r.OFFERDATE
            eligible=changed & future
            x=metrics['le_300']-oldmetrics['le_300']
            rv=dict(offer_id=r.offer_id,previous_offer_id=prev.offer_id,DUID=duid,direction=direction,offer_time=r.OFFERDATE,
                post_signal=bool(r.OFFERDATE>=SIGNAL),post_interval_end=bool(r.OFFERDATE>=SPIKE),reason=r.REBIDEXPLANATION or 'Missing rebid reason',
                changed_intervals=int(changed.sum()),future_changed_intervals=int(eligible.sum()),past_changed_intervals=int((changed&~future).sum()),
                peak_abs_le300_mw=float(np.max(np.abs(x[eligible]))) if eligible.any() else 0,
                max_increase_le300_mw=float(max(0,x[eligible].max())) if eligible.any() else 0,
                max_decrease_le300_mw=float(min(0,x[eligible].min())) if eligible.any() else 0,
                max_availability_increase_mw=float(max(0,(new[:,10]-old[:,10])[eligible].max())) if eligible.any() else 0,
                price_ladder_changed=ladder_changed,header_changed=header_changed)
            revision_rows.append(rv)
            # Group identical contiguous before/after states, split at delivery-block boundaries.
            cuts=(changed[1:]!=changed[:-1])|(future[1:]!=future[:-1])|(blocks[1:]!=blocks[:-1])|(~np.isclose(old[1:],old[:-1],equal_nan=True).all(axis=1))|(~np.isclose(new[1:],new[:-1],equal_nan=True).all(axis=1))
            starts=[0]+(np.flatnonzero(cuts)+1).tolist()+[288]
            for lo,hi in zip(starts[:-1],starts[1:]):
                if not changed[lo]:continue
                row=dict(segment_id=f'{r.offer_id}-{lo+1}',offer_id=r.offer_id,previous_offer_id=prev.offer_id,DUID=duid,direction=direction,offer_time=r.OFFERDATE,
                    period_from=lo+1,period_to=hi,delivery_from=timeline[lo],delivery_to=timeline[hi-1],block=block(timeline[lo]),future_at_offer=bool(future[lo]),
                    before_bands=old[lo,:10].tolist(),after_bands=new[lo,:10].tolist(),before_prices=price[j-1].tolist(),after_prices=price[j].tolist(),
                    before_maxavail=old[lo,10],after_maxavail=new[lo,10],before_rampup=old[lo,11],after_rampup=new[lo,11],
                    before_fixedload=old[lo,13],after_fixedload=new[lo,13],reason=rv['reason'],**volume_metrics(old[lo,:10],new[lo,:10]))
                for p in CONFIG['thresholds']:
                    for prefix in ['le','ge']:
                        row[f'before_{prefix}{p}']=oldmetrics[f'{prefix}_{p}'][lo];row[f'after_{prefix}{p}']=metrics[f'{prefix}_{p}'][lo]
                if base is not None:
                    row['net_from_presignal_le300_mw']=metrics['le_300'][lo]-bm['le_300'][lo]
                segment_rows.append(row)
        for label,t in [('pre_signal',SIGNAL-pd.Timedelta(nanoseconds=1)),('plus15',SIGNAL+pd.Timedelta(minutes=15)),('plus30',SIGNAL+pd.Timedelta(minutes=30)),('plus60',SIGNAL+pd.Timedelta(minutes=60)),('evening_entry',START.normalize()+pd.Timedelta(hours=16)),('overnight_entry',START.normalize()+pd.Timedelta(hours=22))]:
            eligible_idx=np.flatnonzero(offer_times<=np.datetime64(t))
            if not len(eligible_idx):continue
            j=eligible_idx[-1];cm=curve_metrics(cube[j],price[j],direction)
            for k,delivery in enumerate(timeline):
                row=dict(DUID=duid,direction=direction,snapshot=label,asof=t,delivery=delivery,offer_id=ids[j],maxavail=cube[j,k,10],rampup=cube[j,k,11],total_bands=cm['total'][k],limited_total=cm['availability_limited_total'][k])
                row.update({key:float(v[k]) for key,v in cm.items() if key.startswith(('le_','ge_'))});snapshots.append(row)
        actual=b[b.DUID.eq(duid)&b.DIRECTION.eq(direction)]
        look={pd.Timestamp(t):i for i,t in enumerate(offer_times)};mismatch=0;missing=0
        for _,r in actual.iterrows():
            k=int(r.PERIODID)-1;j=look.get(r.OFFERDATE)
            if j is None:missing+=1;continue
            expected=cube[j,k,:11];observed=r[BANDS+['MAXAVAIL']].to_numpy(dtype=float)
            mismatch+=int(not np.allclose(expected,observed,equal_nan=True,atol=.001))
            cm=curve_metrics(cube[j],price[j],direction)
            row=dict(DUID=duid,direction=direction,delivery=r.INTERVAL_DATETIME,offer_id=ids[j],offer_time=heads.iloc[j].OFFERDATE,
                maxavail=cube[j,k,10],rampup=cube[j,k,11],rampdown=cube[j,k,12],total_bands=cm['total'][k],le300=cm['le_300'][k],bands=cube[j,k,:10].tolist(),prices=price[j].tolist())
            if base is not None:row['presignal_le300']=bm['le_300'][k]
            effective_rows.append(row)
        audit.append(dict(DUID=duid,direction=direction,accepted_offers=len(heads),effective_rows=len(actual),missing_offer_links=missing,volume_mismatches=mismatch,has_presignal=base is not None))
        print('Reconstructed',duid,direction,len(heads),'offers',flush=True)
    for name,rows in [('revisions',revision_rows),('segments',segment_rows),('snapshots',snapshots),('effective',effective_rows),('reconstruction_audit',audit)]:
        pd.DataFrame(rows).to_parquet(RESULTS/(name+'.parquet'),index=False)
    a=pd.DataFrame(audit)
    write_json(STATE/'reconstruction.json',dict(accepted_headers=len(h),revisions=len(revision_rows),segments=len(segment_rows),missing_effective_links=int(a.missing_offer_links.sum()),volume_mismatches=int(a.volume_mismatches.sum())))
    if a.missing_offer_links.sum() or a.volume_mismatches.sum():raise ValueError('Effective-offer reconciliation failed; inspect audit')
