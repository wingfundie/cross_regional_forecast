import numpy as np
import pandas as pd
from nemic.event_atlas import detector, cap_at, price_regime, landmarks


def test_missing_interval_prevents_false_contraction():
    ix=pd.date_range('2025-01-01',periods=2000,freq='5min')
    x=pd.Series(1000+100*np.sin(np.arange(len(ix))),index=ix)
    x.iloc[999]=np.nan;x.iloc[1000]=0
    d,_,_=detector(x)
    assert not d.iloc[1000].sharp


def test_month_boundary_lags_use_real_history():
    ix=pd.date_range('2025-01-29',periods=2200,freq='5min')
    x=pd.Series(1000+100*np.sin(np.arange(len(ix))),index=ix)
    t=pd.Timestamp('2025-02-01');x.loc[t]=0
    d,_,_=detector(x)
    assert d.loc[t,'drop_mw']==x.loc[t-pd.Timedelta(minutes=30)]
    assert d.loc[t,'sharp']


def test_signed_negative_capacity_is_preserved():
    ix=pd.date_range('2025-01-01',periods=2000,freq='5min')
    x=pd.Series(100+10*np.sin(np.arange(len(ix))),index=ix);x.iloc[900]=-300
    d,_,_=detector(x)
    assert d.iloc[900].sharp and d.iloc[900].drop_mw>380


def test_mpc_effective_dates():
    assert list(cap_at(['2025-06-30 23:55','2025-07-01','2026-07-01']))==[17500,20300,23200]


def test_sparse_reference_not_invented():
    x=pd.Series([1000.]*100,index=pd.date_range('2025-01-01',periods=100,freq='5min'))
    x.iloc[-1]=0
    d,_,_=detector(x)
    assert not d.sharp.any()


def test_market_cap_flag_is_not_administered_price():
    assert price_regime(pd.Series([0,4,1,5,8,16]),pd.Series([0]*6)).tolist()==[True,True,False,False,False,True]


def test_recovery_separates_later_independent_dip():
    s=pd.Series([700,650,975,980,990,200,100],index=pd.date_range('2025-01-01',periods=7,freq='5min'))
    t,value,recovery=landmarks(s,1000)
    assert value==650 and t==s.index[1] and recovery==s.index[2]


def test_recovery_censors_at_missing_observation():
    s=pd.Series([700,650,np.nan,1000,1000,1000],index=pd.date_range('2025-01-01',periods=6,freq='5min'))
    assert pd.isna(landmarks(s,1000)[2])


def test_scoped_archive_parser_filters_ids_times_and_footer(tmp_path):
    import zipfile
    from nemic.event_atlas import extract_archive
    p=tmp_path/'tiny.zip'
    text='C,TEST\nI,DISPATCH,LOAD,1,SETTLEMENTDATE,DUID,TOTALCLEARED\n'
    text+='D,DISPATCH,LOAD,1,"2025/01/01 00:05:00",GEN1,100\n'
    text+='D,DISPATCH,LOAD,1,"2025/01/01 00:05:00",OTHER,200\n'
    text+='D,DISPATCH,LOAD,1,"2025/01/01 00:10:00",GEN1,300\nC,END OF REPORT,5\n'
    with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('DATA.CSV',text)
    f=extract_archive({},p,'DISPATCHLOAD',{'2025/01/01 00:05:00'},{'GEN1'},['SETTLEMENTDATE','DUID','TOTALCLEARED'])
    assert f[['DUID','TOTALCLEARED']].to_dict('records')==[{'DUID':'GEN1','TOTALCLEARED':'100'}]
