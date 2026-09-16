import io
import zipfile

import numpy as np
import pandas as pd
import pytest

from nemic.experiments.diurnal import (CapacityReference, metrics, origin_weights,
                                       mature_masks, periods, DiurnalModel)
from nemic.experiments.nos import parse_snapshot
from nemic.experiments.validation import Fold


def test_origin_weights_do_not_multiply_evidence():
    values = np.array([1, 1, 1, 2, 2, 3])
    weights = origin_weights(values)
    assert all(weights[values == v].sum() == pytest.approx(1) for v in np.unique(values))


def test_metrics_keep_zero_and_signed_capacity():
    y = np.array([0., -10., 100.]); p = np.array([100., 10., 200.])
    result = metrics(y, p, np.repeat(100., 3))
    assert result['mae'] == pytest.approx(220 / 3)
    assert result['dr_nmae'] == pytest.approx(result['mae'])
    assert result['mape_full'] is None
    assert result['mape_50_coverage'] == pytest.approx(1 / 3)
    assert result['mape_50'] == 100


def test_capacity_reference_frozen_and_no_zero_division():
    ref = CapacityReference().fit([0, 100, 200, np.nan, -300])
    before = ref.predict([0, -100, np.nan])
    assert np.all(np.isfinite(before) & (before > 0))
    assert before[-1] == ref.median
    ref.predict([1e9])
    np.testing.assert_array_equal(before, ref.predict([0, -100, np.nan]))


def test_maturity_is_strict_at_partition_boundary():
    fold = Fold('test', 'rolling', '2025-01-01', '2025-02-01', '2025-03-01',
                '2025-04-01', '2025-05-01', '2025-06-01')
    origin = pd.DatetimeIndex(['2025-01-31 22:30', '2025-01-31 23:00'])
    delivery = origin + pd.Timedelta(minutes=30)
    masks = mature_masks(origin, delivery, fold)
    np.testing.assert_array_equal(masks['train'], [True, False])
    assert periods(pd.DatetimeIndex(['2025-01-01 06:00']))[0] == 1


def test_period_interactions_route_float32_clock_boundaries():
    from nemic.experiments.diurnal import expansion
    hours=np.array([6.,10.,16.,21.])
    x=pd.DataFrame({'hour_sin':np.sin(hours*2*np.pi/24).astype('float32'),
                    'hour_cos':np.cos(hours*2*np.pi/24).astype('float32'),'upper_room':np.ones(4)})
    z=expansion(x,'T2',2)
    for i in range(4):
        assert z.iloc[i][f'period_{i+1}']==1


def snapshot(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, 'w') as z:
        z.writestr('report.csv', text)
    return b.getvalue()


def test_snapshot_schema_and_clock_fail_closed():
    text = ('C,OPDP.WORLD,NETWORK_OUTAGE,AEMO,PUBLIC,2026/03/01,00:30:00,x\n'
            'I,NETWORK,OUTAGEDETAIL,4,OUTAGEID,STARTTIME\n'
            'D,NETWORK,OUTAGEDETAIL,4,1,2026/03/01 01:00:00\n'
            'I,NETWORK,OUTAGECONSTRAINTSET,1,OUTAGEID,GENCONSETID\n'
            'D,NETWORK,OUTAGECONSTRAINTSET,1,1,S1\n')
    timestamp, rows = parse_snapshot(snapshot(text), 'PUBLIC_NETWORK_20260301003000_1.zip')
    assert len(rows) == 2 and timestamp == pd.Timestamp('2026-03-01 00:30')
    with pytest.raises(ValueError):
        parse_snapshot(snapshot(text), 'PUBLIC_NETWORK_20260301010000_1.zip')
    with pytest.raises(ValueError):
        parse_snapshot(snapshot(text.split('I,NETWORK,OUTAGECONSTRAINTSET')[0]),
                       'PUBLIC_NETWORK_20260301003000_1.zip')


def test_snapshot_cache_preserves_multiline_fields_and_revisions():
    text = ('C,OPDP.WORLD,NETWORK_OUTAGE,AEMO,PUBLIC,2026/03/01,00:30:00,x\n'
            'I,NETWORK,OUTAGEDETAIL,4,OUTAGEID,REASON\n'
            'D,NETWORK,OUTAGEDETAIL,4,1,"first line\nsecond line"\n'
            'I,NETWORK,OUTAGECONSTRAINTSET,1,OUTAGEID,GENCONSETID\n'
            'D,NETWORK,OUTAGECONSTRAINTSET,1,1,S1\n')
    cache={}
    _, first=parse_snapshot(snapshot(text),'PUBLIC_NETWORK_20260301003000_1.zip',cache)
    _, again=parse_snapshot(snapshot(text),'PUBLIC_NETWORK_20260301003000_1.zip',cache)
    assert first == again
    _, revised=parse_snapshot(snapshot(text.replace('second line','changed line')),'PUBLIC_NETWORK_20260301003000_1.zip',cache)
    assert len(set(first)-set(revised)) == 1


def test_joint_warning_budget_uses_exposure_days():
    from nemic.experiments.diurnal_risk import score_events,joint_threshold
    origin=pd.date_range('2026-01-01',periods=12,freq='30min')
    events=pd.DataFrame({'time':pd.DatetimeIndex([])})
    probability=np.linspace(.1,.9,len(origin))
    scored=score_events(origin,probability,.1,events)
    assert scored['exposure_days']==.25
    assert scored['false_alarms_per_day']==scored['fp']/.25
    chosen=joint_threshold([(origin,probability,events),(origin,probability,events)],3)
    total=sum(score_events(origin,probability,t,events)['false_alarms_per_day'] for t in chosen)
    assert total<=3


def test_single_class_risk_fit_and_calibration_are_explicit_constants():
    from nemic.experiments.diurnal_risk import RiskModel,ProbabilityCalibrator
    x=pd.DataFrame({'hour_sin':np.sin(np.arange(50)),'hour_cos':np.cos(np.arange(50))})
    model=RiskModel('boost').fit(x,np.zeros(50))
    assert model.is_constant and np.allclose(model.predict(x),1e-6)
    logits=np.zeros((10,1));cal=ProbabilityCalibrator().fit(logits,np.ones(10))
    assert np.allclose(cal.predict_proba(logits)[:,1],1-1e-6)


def test_holm_and_block_sampling_preserve_contiguous_days():
    from nemic.experiments.diurnal_statistics import holm,block_indices
    np.testing.assert_allclose(holm([.01,.04,.03]),[.03,.06,.06])
    indices=block_indices(30,block=7,replicates=5)
    assert indices.shape==(5,30)
    np.testing.assert_array_equal(np.diff(indices[:,:7]),np.ones((5,6)))


def test_model_confidence_set_retains_best_forecast():
    from nemic.experiments.diurnal_statistics import model_confidence_set
    origin=pd.date_range('2026-01-01',periods=48*40,freq='30min')
    actual=np.sin(np.arange(len(origin))/48)
    frame=pd.DataFrame({'origin':origin,'actual':actual,'good':actual+.01,'bad':actual+10})
    result=model_confidence_set(frame,['good','bad'],replicates=200)
    assert 'good' in result['members'] and 'bad' not in result['members']


def test_paired_power_uses_data_support():
    from nemic.experiments.nos_feasibility import paired_power
    small=paired_power(30,.4,.1,.5,replicates=1000)
    large=paired_power(1000,.4,.1,.5,replicates=1000)
    assert 0<=small<=1 and large>small


def test_nos_features_have_distinct_explanation_group():
    from nemic.experiments.diurnal_explain import groups
    assert groups(['nos_count','hour_sin'])['scheduled_outage']==['nos_count']


def test_restricted_nos_interactions_use_declared_inputs_only():
    from nemic.experiments.nos_runner import add_interactions
    x=pd.DataFrame({'nos_count':[2.],'nos_overlap':[.5],'nos_upper_sets':[1.],
                    'nos_lower_sets':[0.],'upper_room':[100.],'lower_room':[50.],
                    'upper_gen_tightening':[3.],'lower_gen_tightening':[4.],
                    'hour_sin':[1.],'hour_cos':[0.]})
    out=add_interactions(x.copy())
    assert out['nos_count:upper_room'].iloc[0]==200
    assert all('actual' not in col for col in out)


def test_model_roundtrip_schema_and_singular_design(tmp_path):
    import joblib
    x = pd.DataFrame({'hour_sin': np.sin(np.arange(100)), 'hour_cos': np.cos(np.arange(100)),
                      'constant': np.ones(100), 'missing': np.repeat(np.nan, 100)})
    model = DiurnalModel('T3').fit(x, np.arange(100), np.ones(100), pd.date_range('2025-01-01', periods=100, freq='30min'))
    path = tmp_path / 'model.joblib'; joblib.dump(model, path)
    np.testing.assert_allclose(model.predict(x), joblib.load(path).predict(x))
    with pytest.raises(ValueError):
        model.predict(x.iloc[:, ::-1])


def test_nos_late_actual_end_cannot_rewrite_earlier_exposure(tmp_path,monkeypatch):
    import json
    from nemic.experiments import nos_analysis as module
    from nemic.experiments.core import load_config
    c=load_config('configs/experiments/vni_diurnal_nos_v2.json');c['_run']=tmp_path/'campaign'
    c['leads']=[1];c['end']='2026-03-02'
    root=c['_run'];folder=root/'nos/weeks/test';folder.mkdir(parents=True)
    (folder/'manifest.json').write_text('{}')
    monkeypatch.setattr(module,'mapping',lambda c:(pd.DataFrame({'GENCONSETID':['S1']}),{'track':'test'}))
    class Mapping:
        def __init__(self,c):pass
        def at(self,origin):return {'S1':{'thermal':True,'voltage':False,'stability':False,'upper':True,'lower':False}}
    monkeypatch.setattr(module,'MappingHistory',Mapping)
    t0=pd.Timestamp('2026-03-01 00:00');t1=t0+pd.Timedelta(hours=1)
    detail={'OUTAGEID':'1','STARTTIME':'2026-03-01 00:00','ENDTIME':'2026-03-01 06:00',
        'OUTAGESTATUSCODE':'PTP','SUBSTATIONID':'A','EQUIPMENTTYPE':'LINE','EQUIPMENTID':'1','ISSECONDARY':'0'}
    late={**detail,'ACTUAL_ENDTIME':'2026-03-01 00:45'}
    link={'OUTAGEID':'1','GENCONSETID':'S1','STARTINTERVAL':'2026-03-01 01:00','ENDINTERVAL':'2026-03-01 01:00'}
    pd.DataFrame([{'row_id':k,'table':table,'fields_json':json.dumps(f)} for k,table,f in
        [('early','OUTAGEDETAIL',detail),('late','OUTAGEDETAIL',late),('link','OUTAGECONSTRAINTSET',link)]]).to_parquet(folder/'rows.parquet')
    pd.DataFrame({'generated_nem':[t0,t1]}).to_parquet(folder/'reports.parquet')
    pd.DataFrame({'generated_nem':[t0,t0,t1,t1],'row_id':['early','link','early','late'],
                  'present':[True,True,False,True]}).to_parquet(folder/'changes.parquet')
    pd.DataFrame({'origin':[t0,t1],'fresh':[True,True]}).to_parquet(root/'nos/coverage.parquet')
    out=module.build_exposure(c)
    assert out.iloc[0].nos_count==1
    assert out.iloc[0].nos_overlap==pytest.approx(1/6)
    assert out.iloc[1].nos_count==0
