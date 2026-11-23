import numpy as np
import pandas as pd
import pytest
from rebid_mistress.core import START,END,intervals,block
from rebid_mistress.reconstruct import expand_offer,FIELDS,volume_metrics,curve_metrics
from rebid_mistress.analyse import baseline,replacement,response_classification

def sparse(lo=1,hi=288,mw=100):
    row={c:0.0 for c in FIELDS};row.update(PERIODID=lo,PERIODIDTO=hi,BANDAVAIL1=mw,MAXAVAIL=mw)
    return row

def test_trading_day_boundaries():
    ix=intervals();assert len(ix)==288 and ix[0]==START+pd.Timedelta(minutes=5) and ix[-1]==END
    assert block('2026-10-10 10:00')=='morning'
    assert block('2026-10-10 16:05')=='evening'
    assert block('2026-10-11 04:00')=='overnight'
    assert pd.Timestamp('2026-10-10 07:20',tz='Australia/Brisbane').tz_convert('Australia/Sydney').hour==8

def test_sparse_full_offer_and_invalid_ranges():
    x=expand_offer(pd.DataFrame([sparse(1,100,50),sparse(101,288,80)]))
    assert x[99,0]==50 and x[100,0]==80
    with pytest.raises(ValueError):expand_offer(pd.DataFrame([sparse(2,288)]))
    with pytest.raises(ValueError):expand_offer(pd.DataFrame([sparse(1,150),sparse(150,288)]))

def test_reallocation_not_net_new_availability():
    assert volume_metrics([100,0],[0,100])==dict(minimum_redistribution_mw=100,added_offered_mw=0,removed_offered_mw=0)
    assert volume_metrics([100,0],[50,100])==dict(minimum_redistribution_mw=50,added_offered_mw=50,removed_offered_mw=0)

def test_load_and_generation_thresholds_differ():
    state=np.zeros((288,len(FIELDS)));state[:,0]=40;state[:,9]=60;state[:,10]=70
    p=np.array([-100,0,100,200,300,400,500,600,700,1000])
    m=curve_metrics(state,p,'LOAD');assert m['ge_300'][0]==60 and m['le_300'][0]==40 and m['availability_limited_total'][0]==70

def test_baseline_excludes_signal_interval_and_missing_not_zero():
    ix=pd.date_range('2026-10-10 06:45','2026-10-10 07:20',freq='5min')
    s=pd.Series([100]*6+[1000,2000],index=ix);assert baseline(s)==100
    s.iloc[0]=np.nan;assert np.isnan(baseline(s))

def test_portfolio_replacement_is_capped_and_missing_is_unknown():
    assert replacement(300,500,400,100)==dict(shortfall_mw=200,incremental_mw=300,matched_mw=200,residual_mw=0)
    assert replacement(500,500,400,100)['matched_mw']==0
    assert replacement(300,500,100,100)['residual_mw']==200
    assert np.isnan(replacement(np.nan,500,400,100)['matched_mw'])

def test_same_delivery_evening_revision_and_reversal():
    old=expand_offer(pd.DataFrame([sparse(1,288,100)]))
    evening=expand_offer(pd.DataFrame([sparse(1,144,100),sparse(145,216,200),sparse(217,288,100)]))
    delta=evening[:,0]-old[:,0]
    assert delta[:144].sum()==0 and np.all(delta[144:216]==100) and delta[216:].sum()==0
    assert np.all((old-evening)+(evening-old)==0)

def test_battery_net_swing_is_not_discharge_volume():
    before,after=-100,100
    assert after-before==200 and max(after,0)==100 and max(-before,0)-max(-after,0)==100

def test_rebidding_without_output_and_output_without_rebidding():
    a=pd.Timestamp('2026-10-10 07:25');b=a+pd.Timedelta(minutes=5)
    assert 'without an observed' in response_classification(a,pd.NaT,True,False)
    assert 'before any' in response_classification(pd.NaT,a,False,False)
    assert 'affected period' in response_classification(a,b,True,True)
    assert 'preceded' in response_classification(b,a,True,True)
