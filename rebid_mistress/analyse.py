"""Chronology, operational evidence and conservative physical portfolio comparisons."""
import numpy as np
from .core import *

def result(name):return pd.read_parquet(RESULTS/(name+'.parquet'))
def save(name,f):f.to_parquet(RESULTS/(name+'.parquet'),index=False)
def baseline(series):
    eligible=series.reindex(pd.date_range(SPIKE-pd.Timedelta(minutes=35),SPIKE-pd.Timedelta(minutes=10),freq='5min'))
    return float(eligible.median()) if eligible.notna().sum()==6 else np.nan

def first_time(frame,mask,column='delivery'):
    return frame.loc[mask,column].min() if mask.any() else pd.NaT

def replacement(coal_actual,coal_reference,replacement_actual,replacement_reference):
    values=[coal_actual,coal_reference,replacement_actual,replacement_reference]
    if any(pd.isna(x) for x in values):return dict(shortfall_mw=np.nan,incremental_mw=np.nan,matched_mw=np.nan,residual_mw=np.nan)
    short=max(coal_reference-coal_actual,0);inc=max(replacement_actual-replacement_reference,0);matched=min(short,inc)
    return dict(shortfall_mw=short,incremental_mw=inc,matched_mw=matched,residual_mw=short-matched)

def reason_category(text):
    text=str(text).lower()
    if any(s in text for s in ['trip','outage','technical','plant issue','equipment','fault']):return 'plant/availability'
    if any(s in text for s in ['forecast','predispatch','pre-dispatch','pd price','p5']):return 'forecast/expected conditions'
    if any(s in text for s in ['soc','state of charge','charge','energy limit']):return 'storage/energy management'
    if any(s in text for s in ['price','dispatch','market','demand']):return 'market/dispatch conditions'
    return 'other/unclear'

def response_classification(first_bid,first_output,has_cheaper_offer,has_later_output):
    if has_cheaper_offer:
        if pd.notna(first_output) and first_output<first_bid:return 'generation increase preceded cheaper post-signal offer; later positioning is separate'
        if has_later_output:return 'offered more below $300 and generated more in an affected period; motive unresolved'
        return 'offered more below $300 without an observed output increase in affected periods'
    if pd.notna(first_output) and (pd.isna(first_bid) or first_output<first_bid):return 'generation increased before any post-signal energy revision'
    if pd.notna(first_output):return 'generation increased; no qualifying cheaper generation offer established'
    return 'no qualifying offer/output increase, or insufficient coverage'

def run():
    inv=load_table('inventory');ids=set(inv.DUID)
    sc=load_table('scada')
    if (TABLES/'scada_last.parquet').exists():sc=pd.concat([sc,load_table('scada_last')],ignore_index=True)
    times(sc,['SETTLEMENTDATE']);number(sc,['SCADAVALUE'])
    sc=sc[sc.DUID.isin(ids)].drop_duplicates(['DUID','SETTLEMENTDATE']).rename(columns={'SETTLEMENTDATE':'delivery','SCADAVALUE':'actual_mw'})
    sc['native_interval_end']=sc.delivery
    sc['delivery']=sc.delivery-pd.Timedelta(minutes=5)
    ds=load_table('dispatch_UNIT_SOLUTION');times(ds,['SETTLEMENTDATE','LASTCHANGED'])
    numeric=['TOTALCLEARED','INITIALMW','AVAILABILITY','RAMPUPRATE','RAMPDOWNRATE','DISPATCHMODE','DISPATCHMODETIME','INITIAL_ENERGY_STORAGE','ENERGY_STORAGE','INTERVENTION','MIN_AVAILABILITY']
    number(ds,numeric);ds=ds[ds.DUID.isin(ids)&ds.INTERVENTION.eq(0)].sort_values('LASTCHANGED').drop_duplicates(['DUID','SETTLEMENTDATE'],keep='last')
    ds=ds.rename(columns={'SETTLEMENTDATE':'delivery','TOTALCLEARED':'target_mw'})
    grid=pd.MultiIndex.from_product([inv.DUID,intervals()],names=['DUID','delivery']).to_frame(index=False)
    panel=grid.merge(sc[['DUID','delivery','actual_mw']],on=['DUID','delivery'],how='left',validate='one_to_one')
    panel=panel.merge(ds[['DUID','delivery','target_mw']+[c for c in numeric if c not in ['TOTALCLEARED','INTERVENTION']]],on=['DUID','delivery'],how='left',validate='one_to_one')
    panel=panel.merge(inv[['DUID','plant','technology','REGIONID','controller','owner','DISPATCHTYPE','SCHEDULE_TYPE','registered_mw','storage_capacity_native']],on='DUID',validate='many_to_one')
    # Legacy LOAD DUIDs are positive consumption in source; BDU dispatch is already signed.
    loadmask=panel.DISPATCHTYPE.eq('LOAD')
    panel.loc[loadmask,['actual_mw','target_mw','INITIALMW']]*=-1
    baselines=panel.groupby('DUID').apply(lambda g:baseline(g.set_index('delivery').actual_mw),include_groups=False)
    panel['baseline_mw']=panel.DUID.map(baselines);panel['incremental_mw']=panel.actual_mw-panel.baseline_mw
    panel['block']=panel.delivery.map(block)
    panel['initial_soc_pct']=100*panel.INITIAL_ENERGY_STORAGE/panel.storage_capacity_native.replace(0,np.nan)
    panel['projected_soc_pct']=100*panel.ENERGY_STORAGE/panel.storage_capacity_native.replace(0,np.nan)
    # Out-of-range storage ratios are retained in evidence and labelled, never silently clipped.
    panel['soc_quality']=np.where(panel.initial_soc_pct.between(0,100),'capacity-matched',np.where(panel.initial_soc_pct.isna(),'unavailable','outside registered capacity; unresolved'))
    save('panel',panel)
    pdunit=load_table('predispatch_UNIT_SOLUTION');times(pdunit,['DATETIME','LASTCHANGED']);number(pdunit,['TOTALCLEARED','INTERVENTION','AVAILABILITY'])
    pdunit=pdunit[pdunit.DUID.isin(ids)&pdunit.INTERVENTION.eq(0)]
    runs=pdunit.groupby('PREDISPATCHSEQNO').agg(processed_at=('LASTCHANGED','max'),rows=('DUID','size'),units=('DUID','nunique'))
    valid=runs[runs.processed_at<SIGNAL]
    if valid.empty:raise ValueError('No pre-signal forecast vintage')
    chosen=valid.sort_values('processed_at').index[-1]
    forecast=pdunit[pdunit.PREDISPATCHSEQNO.eq(chosen)].copy().rename(columns={'DATETIME':'delivery','TOTALCLEARED':'forecast_mw'})
    forecast=forecast[forecast.delivery.gt(START)&forecast.delivery.le(END)].drop_duplicates(['DUID','delivery'])
    forecast.loc[forecast.DUID.isin(inv.loc[inv.DISPATCHTYPE.eq('LOAD'),'DUID']),'forecast_mw']*=-1
    forecast=forecast[['DUID','delivery','forecast_mw','PREDISPATCHSEQNO','LASTCHANGED','AVAILABILITY']].merge(panel[['DUID','delivery','actual_mw','plant','technology','REGIONID','controller']],on=['DUID','delivery'],how='left')
    save('forecast',forecast)
    write_json(STATE/'forecast.json',dict(run=str(chosen),processing_proxy=str(runs.loc[chosen,'processed_at']),actual_receipt_verified=False,selection='Latest complete archived run processed before signal; dissemination proxy only',rows=len(forecast),units=forecast.DUID.nunique()))
    revisions=result('revisions');segments=result('segments');effective=result('effective');snap=result('snapshots')
    revisions['reason_category']=revisions.reason.map(reason_category);save('revisions',revisions)
    units=[];blocks=[]
    for duid,g in panel.groupby('DUID'):
        g=g.sort_values('delivery');meta=inv[inv.DUID.eq(duid)].iloc[0]
        post=g[g.delivery>=SPIKE];r=revisions[revisions.DUID.eq(duid)];rr=r[r.post_signal&r.future_changed_intervals.gt(0)]
        ss=segments[segments.DUID.eq(duid)&segments.offer_time.ge(SIGNAL)&segments.future_at_offer]
        low=ss[ss.direction.eq('GEN')&(ss.after_le300>ss.before_le300+CONFIG['response_threshold_mw'])]
        first_rebid=rr.offer_time.min();first_lower=low.offer_time.min()
        first_output=first_time(post,post.incremental_mw.ge(CONFIG['response_threshold_mw']))
        first_target=first_time(post,(post.target_mw-post.baseline_mw).ge(CONFIG['response_threshold_mw']))
        linked_output=False
        for lr in low.itertuples():
            observed=post[post.delivery.ge(lr.delivery_from)&post.delivery.le(lr.delivery_to)&post.delivery.gt(lr.offer_time)]
            if observed.incremental_mw.ge(5).any():linked_output=True;break
        labels=[response_classification(first_lower if len(low) else first_rebid,first_output,bool(len(low)),linked_output)]
        for period in ['evening','overnight']:
            if ss.block.eq(period).any():labels.append(period+' offers revised after signal')
        actual=g.actual_mw.dropna();base=baselines.get(duid,np.nan)
        peak=float(post.incremental_mw.max()) if post.incremental_mw.notna().any() else np.nan
        on=g.actual_mw.ge(5);starts=g.loc[on & ~on.shift(1,fill_value=bool(on.iloc[0])),'delivery'].tolist()
        falls=g.loc[g.actual_mw.diff().le(-20),'delivery'].tolist()
        # Public dispatch ramp rates are MW/hour, so rate/12 is a five-minute envelope.
        g['observed_change_mw']=g.actual_mw.diff();envelope=g.RAMPUPRATE/12
        near=(g.observed_change_mw>0)&(envelope>0)&(g.observed_change_mw>=.9*envelope)&(g.observed_change_mw<=1.1*envelope)
        row=dict(DUID=duid,plant=meta.plant,technology=meta.technology,region=meta.REGIONID,controller=meta.controller,owner=meta.owner,
            registered_mw=meta.registered_mw,scada_intervals=int(g.actual_mw.notna().sum()),dispatch_intervals=int(g.target_mw.notna().sum()),baseline_mw=base,
            min_mw=float(actual.min()) if len(actual) else np.nan,max_mw=float(actual.max()) if len(actual) else np.nan,
            peak_incremental_mw=peak,post_signal_revisions=len(rr),all_revisions=len(r),first_rebid=first_rebid,first_lower_offer=first_lower,first_output_increase=first_output,first_target_increase=first_target,
            output_response_minutes=(first_output-SIGNAL).total_seconds()/60 if pd.notna(first_output) else np.nan,
            post_increase_intervals=int(post.incremental_mw.ge(5).sum()),starts=' | '.join(map(str,starts)),large_falls=' | '.join(map(str,falls)),near_documented_ramp_intervals=int(near.sum()),
            peak_stack_shift_mw=float(rr.peak_abs_le300_mw.max()) if len(rr) else 0,classification='; '.join(labels),coverage='complete SCADA' if g.actual_mw.notna().sum()==288 else 'partial/missing SCADA',inference='plausible' if len(low) else 'unresolved')
        for n in [15,30,60]:
            selected=g[g.delivery<=SIGNAL+pd.Timedelta(minutes=n)].tail(1)
            row[f'actual_plus{n}_mw']=float(selected.actual_mw.iloc[0]) if len(selected) else np.nan
        units.append(row)
        for period,gg in g.groupby('block'):
            blocks.append(dict(DUID=duid,block=period,observations=int(gg.actual_mw.notna().sum()),expected_intervals=len(gg),mean_mw=gg.actual_mw.mean(),peak_mw=gg.actual_mw.max(),minimum_mw=gg.actual_mw.min()))
    units=pd.DataFrame(units);save('units',units);save('blocks',pd.DataFrame(blocks))
    # Every plant has an account; auxiliary/non-scheduled duplicates never enter replacement totals.
    usable=inv[inv.SCHEDULE_TYPE.eq('SCHEDULED')&inv.DUID.isin(units.loc[units.scada_intervals.gt(0),'DUID'])]
    portfolios=[]
    for (controller,region),members in usable.groupby(['controller','REGIONID']):
        coal=set(members.loc[members.technology.eq('coal'),'DUID']);other=set(members.loc[members.technology.isin(['gas','battery']),'DUID'])
        if not coal or not other:continue
        scope=coal|other
        for reference,source in [('immediate',panel),('projected',forecast)]:
            source=source[source.DUID.isin(scope)&source.delivery.ge(SPIKE)]
            for t,gg in source.groupby('delivery'):
                c=gg[gg.DUID.isin(coal)];o=gg[gg.DUID.isin(other)];ref='baseline_mw' if reference=='immediate' else 'forecast_mw'
                complete=len(c)==len(coal) and len(o)==len(other) and c[['actual_mw',ref]].notna().all().all() and o[['actual_mw',ref]].notna().all().all()
                values=[c.actual_mw.sum(),c[ref].sum(),o.actual_mw.sum(),o[ref].sum()] if complete else [np.nan]*4
                portfolios.append(dict(controller=controller,region=region,reference=reference,delivery=t,coal_actual_mw=values[0],coal_reference_mw=values[1],replacement_actual_mw=values[2],replacement_reference_mw=values[3],complete=complete,coal_duids='|'.join(sorted(coal)),replacement_duids='|'.join(sorted(other)),**replacement(*values)))
    save('portfolios',pd.DataFrame(portfolios))
    # Existing declared offer gap: an explicit capacity scenario, not an asserted outage.
    gen=effective[effective.direction.eq('GEN')].merge(inv[['DUID','technology','registered_mw','controller','REGIONID','SCHEDULE_TYPE']],on='DUID')
    coal=gen[gen.technology.eq('coal')&gen.SCHEDULE_TYPE.eq('SCHEDULED')].copy()
    coal['declared_gap_mw']=(coal.registered_mw-coal.maxavail).clip(lower=0)
    save('capacity_gaps',coal[['DUID','delivery','controller','REGIONID','registered_mw','maxavail','declared_gap_mw']])
    prices=load_table('prices_prices');times(prices,['SETTLEMENTDATE']);number(prices,['RRP'])
    prices=prices[prices.REGIONID.isin(CONFIG['regions'])].sort_values('_version').drop_duplicates(['REGIONID','SETTLEMENTDATE'],keep='last')
    prices=prices[prices.SETTLEMENTDATE.gt(START)&prices.SETTLEMENTDATE.le(END)];save('prices',prices)
    event=prices[prices.SETTLEMENTDATE.eq(SPIKE)].set_index('REGIONID').RRP.to_dict()
    write_json(STATE/'analysis.json',dict(event=event,units=len(units),plants=units.plant.nunique(),complete_scada_units=int(units.scada_intervals.eq(288).sum()),partial_scada_units=int(units.scada_intervals.between(1,287).sum()),unobserved_units=int(units.scada_intervals.eq(0).sum()),post_signal_revisions=int(units.post_signal_revisions.sum()),forecast_run=str(chosen),fcasscope='Excluded',causal_estimates=False))
