import copy
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from nemic.experiments.core import load_config,Store,fingerprint
from nemic.experiments.validation import folds,pairs,regression_score
from nemic.experiments.events import detect,window_label,incidents,match,tune_joint
from nemic.experiments.models import Transform


def test_rolling_folds_and_boundary_purge():
    c=load_config();ff=folds(c)
    assert len(ff)==13
    assert ff[1].train_end=='2025-06-01'
    assert ff[-1].evaluate_end=='2026-09-01'
    idx=pd.date_range('2025-05-31','2025-06-02',freq='30min')
    masks=ff[1].masks(idx,120)
    assert not masks['train'][idx.get_loc('2025-05-31 22:00')]
    assert sum(masks.values()).max()<=1


def test_future_mutation_does_not_change_threshold():
    idx=pd.date_range('2024-01-01',periods=3000,freq='5min')
    c=pd.Series(500+np.random.default_rng(1).normal(size=len(idx)).cumsum(),idx)
    cutoff=idx[1600]
    _,a=detect(c,idx[0],cutoff,minimum=100)
    c.loc[cutoff:]*=100
    _,b=detect(c,idx[0],cutoff,minimum=100)
    assert a==b


def test_missing_intervals_are_unknown_not_negative():
    idx=pd.date_range('2025-01-01',periods=100,freq='5min')
    c=pd.Series(500.,idx);c.iloc[30:]=200;c.iloc[33]=np.nan
    d,_=detect(c,idx[0],idx[-1],absolute=100)
    y=window_label(d.onset,d.valid,pd.DatetimeIndex([idx[10]]),30,120)
    assert np.isnan(y[0])


def test_warning_matches_once_and_requires_advance():
    origins=pd.date_range('2025-01-01',periods=12,freq='30min')
    p=np.ones(12)
    ev=pd.DataFrame({'time':[origins[0]+pd.Timedelta(minutes=90)]})
    result=match(origins,p,.5,ev)
    assert result['tp']==1
    assert result['leads']==[90.]
    assert len(result['alarms'])==3
    assert result['fp']==2
    late=match(pd.DatetimeIndex([origins[0]+pd.Timedelta(minutes=80)]),[1.],.5,ev)
    assert late['tp']==0


def test_joint_alert_budget():
    origins=pd.date_range('2025-01-01',periods=96,freq='30min')
    p=np.linspace(0,1,len(origins));ev=pd.DataFrame({'time':[]})
    cut=tune_joint([(origins,p,ev),(origins,p,ev)],3)
    assert sum(match(origins,p,t,ev)['false_alarms_per_day'] for t in cut)<=3


def test_transform_does_not_refit_on_evaluation():
    train=pd.DataFrame({'x':[1,2,3,np.nan],'z':[5,6,7,8]})
    model=Transform().fit(train);before=model.scaler.mean_.copy()
    model.apply(pd.DataFrame({'x':[1e9],'z':[-1e9]}))
    assert np.array_equal(model.scaler.mean_,before)
    with pytest.raises(ValueError):model.apply(train[['z','x']])


def test_storage_guard_and_safe_cleanup(tmp_path):
    c=load_config();c['_run']=tmp_path/'campaign';c['limits']['additional_bytes']=1_000_000;c['limits']['min_free_bytes']=0
    s=Store(c)
    with pytest.raises(RuntimeError):
        with s.reserve(2_000_000):pass
    with pytest.raises(ValueError):s.scratch_delete(tmp_path/'protected.parquet')
    scratch=s.root/'scratch'/'test.csv';scratch.parent.mkdir();scratch.write_text('test')
    s.scratch_delete(scratch);assert not scratch.exists()


def test_cache_invalidates_configuration_and_content(tmp_path):
    c=load_config();c['_run']=tmp_path/'campaign';c['limits']['min_free_bytes']=0
    s=Store(c);path=s.json(s.root/'result.json',{'a':1});fp=fingerprint({'model':'ridge'})
    s.complete('trial',fp,path);assert s.valid('trial',fp)
    assert not s.valid('trial',fingerprint({'model':'boost'}))
    path.write_text('{}');assert not s.valid('trial',fp)


def test_incident_grouping_matches_atlas_gap_rule():
    idx=pd.date_range('2025-01-01',periods=20,freq='5min')
    d=pd.DataFrame({'onset':False,'drop_mw':100.},index=idx)
    d.loc[idx[[0,5,13]],'onset']=True
    e=incidents(d);assert len(e)==2;assert e.time.iloc[0]==idx[0]
