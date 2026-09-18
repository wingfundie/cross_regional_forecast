"""Issue-time and restart invariants for the fundamentals upgrade."""
import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nemic.fundamentals.sources import parse_pasa, nem_time, REGIONS
from nemic.fundamentals.features import pasa_at, engineer, coal_at, ForecastFeatures
from nemic.fundamentals.tracking import Ledger


def pasa_fixture():
    rows=[]
    for product,hour,available in [('pdpasa','15:00','14:35'),('stpasa','14:00','14:12')]:
        for region in REGIONS:
            for variable,value in [('demand50',1000),('wind_uigf',200),('solar_uigf',100),('wind_constrained',180),('solar_constrained',80)]:
                rows.append(dict(product=product,region=region,variable=variable,value=value,
                    available_at=nem_time('2026-09-17 '+available),delivery=nem_time('2026-09-19 05:00'),run_id=hour))
    return pd.DataFrame(rows)


def test_nominal_run_can_follow_publication():
    raw=b'C,NEMP,W,AEMO,PUBLIC,2026/09/17,14:35:00\nI,PDPASA,REGIONSOLUTION,7,RUN_DATETIME,INTERVAL_DATETIME,REGIONID,RUNTYPE,DEMAND50,SS_WIND_UIGF,SS_SOLAR_UIGF,SS_WIND_CAPACITY,SS_SOLAR_CAPACITY\nD,PDPASA,REGIONSOLUTION,7,2026/09/17 15:00:00,2026/09/17 15:00:00,NSW1,LOR,1000,200,100,180,80\n'
    f=parse_pasa(io.BytesIO(raw),'pdpasa','abc','2026-09-17T06:00Z')
    assert (f.available_at<f.nominal_run).all()
    assert set(f.variable)=={'demand50','wind_uigf','solar_uigf','wind_constrained','solar_constrained'}


def test_future_vintage_never_changes_earlier_features():
    f=pasa_fixture();origin=nem_time('2026-09-17 14:20');delivery=nem_time('2026-09-19 05:00')
    expected,run=pasa_at(f,origin,delivery)
    future=f.copy();future.available_at=origin+pd.Timedelta(minutes=10);future.value=9999;future.run_id='future'
    got,_=pasa_at(pd.concat([f,future]),origin,delivery)
    assert got==expected and run['product']=='stpasa'


def test_incomplete_regional_run_not_mixed():
    f=pasa_fixture();f=f[~(f['product'].eq('stpasa')&f.region.eq('QLD1'))]
    _,run=pasa_at(f,nem_time('2026-09-17 14:40'),nem_time('2026-09-19 05:00'))
    assert run['product']=='pdpasa'


def test_compact_index_matches_reference_and_rejects_future(tmp_path):
    from nemic.fundamentals.features import PasaIndex
    f=pasa_fixture();future=f.copy();future.available_at+=pd.Timedelta(hours=1);future.run_id='future';future.value=9000
    f=pd.concat([f,future]);path=tmp_path/'pasa.parquet';f.to_parquet(path,index=False)
    index=PasaIndex.from_files([path]);delivery=nem_time('2026-09-19 05:00')
    for origin in ('2026-09-17 14:00','2026-09-17 14:20','2026-09-17 14:40','2026-09-17 15:40'):
        assert pasa_at(index,nem_time(origin),delivery)==pasa_at(f,nem_time(origin),delivery)


def test_date_sharded_store_matches_compact_index(tmp_path):
    from nemic.fundamentals.features import PasaIndex,PasaStore
    f=pasa_fixture();f['feature']=f.region+'__'+f.variable
    keys=['product','run_id','available_at','delivery']
    wide=f.pivot_table(index=keys,columns='feature',values='value',aggfunc='first').reset_index()
    piece=tmp_path/'piece.parquet';wide.to_parquet(piece,index=False)
    day=str(f.delivery.iloc[0].date())
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(dict(contract='test',dates={day:['piece.parquet']},
        available_min=str(f.available_at.min()),available_max=str(f.available_at.max()))))
    store=PasaStore(manifest);direct=PasaIndex(wide);delivery=f.delivery.iloc[0]
    for origin in (nem_time('2026-09-17 14:20'),nem_time('2026-09-17 14:40')):
        assert store.at(origin,delivery)==direct.at(origin,delivery)


def test_package_predictions_reject_crossed_intervals():
    from nemic.fundamentals.packaging import predict
    class Model:
        def predict(self,x):return np.zeros(len(x))
    bundle=dict(columns=['own_anchor'],model=Model(),adjustments=[-2,0,2],levels=[.1,.5,.9])
    x=pd.DataFrame({'own_anchor':[100.,200.]})
    point,intervals=predict(bundle,x)
    np.testing.assert_array_equal(point,x.own_anchor)
    assert (np.diff(intervals,axis=1)>=0).all()
    bundle['adjustments']=[2,0,-2]
    with pytest.raises(ValueError,match='interval contract'):predict(bundle,x)


def test_direction_and_interaction_parent_closure():
    values={f'{r}__{v}':x for r in REGIONS for v,x in [('demand50',1000),('wind_uigf',200),('solar_uigf',100),('wind_constrained',180),('solar_constrained',90),('coal_available',600)]}
    values['QLD1__demand50']=1200
    features,schema=engineer(values,'QNI',{'upper_room':100,'lower_room':200})
    assert features['endpoint__residual_uigf_difference']==200
    assert features['ix__imbalance_upper']==20000
    assert set(schema['parents']['ix__imbalance_upper'])=={'upper_room','endpoint__residual_uigf_difference'}
    assert features['pair__NSW1_QLD1__demand50__difference']==-200


def test_missing_coal_is_unknown_and_daily_semantics_required():
    reg=pd.DataFrame([dict(duid='X',region='NSW1',fuel='black_coal',station='S',registered_mw=500,
                          valid_from=nem_time('2024-01-01'),valid_to=nem_time('2030-01-01'))])
    with pytest.raises(ValueError,match='semantics'):
        coal_at(pd.DataFrame(),reg,nem_time('2026-01-01'),nem_time('2026-01-02'))


def test_registration_supersession_preserves_retirement_gaps():
    from nemic.fundamentals.coal import canonical_intervals
    f=pd.DataFrame([dict(DUID='A',START_DATE=nem_time(a),END_DATE=nem_time(b)) for a,b in
                    [('2024-01-01','2200-01-01'),('2025-01-01','2025-06-01'),('2026-01-01','2200-01-01')]])
    result=canonical_intervals(f)
    assert result.iloc[0].END_DATE==nem_time('2025-01-01')
    assert result.iloc[1].END_DATE==nem_time('2025-06-01')


def test_product_transition_is_not_a_ramp():
    f=pasa_fixture();x,schema=ForecastFeatures(f).build('2026-09-17 14:40','2026-09-19 05:00','QNI')
    assert x['pasa_transition_0.5h']==1
    assert np.isnan(x['NSW1__demand50_ramp_0.5h'])


@pytest.fixture
def ledger(tmp_path,monkeypatch):
    import nemic.fundamentals.tracking as tracking
    import nemic.experiments.core as core
    monkeypatch.setattr(tracking,'ROOT',tmp_path);monkeypatch.setattr(core,'ROOT',tmp_path)
    root=tmp_path/'execution/test';(root/'methodology').mkdir(parents=True)
    (root/'methodology/methodology.md').write_text('Method before implementation')
    c=dict(_run=tmp_path/'data/test',tracking_root='execution/test',campaign='test')
    return Ledger(c)


def test_completed_artifact_invalidated_and_dependents_reopened(ledger):
    p=ledger.data/'source.txt';p.write_text('one')
    ledger.record('methodology','completed','verified',[p])
    ledger.register('child',['methodology'])
    with ledger.job('child') as (artifacts,_):artifacts.append(p)
    assert ledger.valid('child')
    p.write_text('changed');ledger.reconcile()
    with ledger.connection() as con:
        assert con.execute('SELECT status FROM work WHERE id=?',('child',)).fetchone()['status']=='ready'


def test_claim_exclusive_and_completion_requires_artifact(ledger):
    p=ledger.data/'artifact.txt';p.write_text('ok')
    with ledger.job('exclusive') as (artifacts,checkpoint):
        checkpoint({'units':1})
        with pytest.raises(RuntimeError,match='Already running'):
            with ledger.job('exclusive'):pass
        artifacts.append(p)
    with pytest.raises(RuntimeError,match='No verified'):
        with ledger.job('empty'):pass
    assert ledger.valid('exclusive')
    assert json.loads((ledger.root/'status.json').read_text())['jobs']


def test_selector_hierarchy_and_chronology():
    from nemic.fundamentals.selection import parent_closure,chronological_splits,basic_filter
    assert parent_closure(['ix'],{'ix':['a','b']})=={'ix','a','b'}
    idx=pd.date_range('2025-01-01',periods=90*48,freq='30min')
    meta=pd.DataFrame({'origin':idx,'delivery':idx+pd.Timedelta(days=7)})
    for tr,va in chronological_splits(meta):
        assert (meta.loc[tr,'delivery']+pd.Timedelta(minutes=30)).max()<meta.loc[va,'origin'].min()
    x=pd.DataFrame({'a':range(100),'b':range(100),'constant':1,'ix':np.arange(100)**2})
    cols,rejected=basic_filter(x,{'ix':['a','b']})
    assert 'constant' not in cols and 'a' in cols and 'b' in cols


def test_weather_radiation_energy_and_no_extrapolation():
    from nemic.fundamentals.weather import weather_at
    run=pd.Timestamp('2026-08-01T00:00Z');delivery=run+pd.Timedelta(hours=12)
    f=pd.DataFrame([dict(available_at=run+pd.Timedelta(hours=8),nominal_run=run,run_id=str(run),provider='ecmwf_ifs',
                        delivery=t,region='NSW1',role='renewable',variable=v,value=value,provenance='hindcast')
                    for t,value in [(delivery,100.),(delivery+pd.Timedelta(hours=1),200.)]
                    for v in ('shortwave_radiation','temperature_2m')])
    values,_=weather_at(f,run+pd.Timedelta(hours=9),delivery+pd.Timedelta(minutes=30))
    assert values['NSW1__renewable__shortwave_radiation']==200
    assert values['NSW1__renewable__temperature_2m']==150
    values,_=weather_at(f,run+pd.Timedelta(hours=9),delivery+pd.Timedelta(hours=2))
    assert 'NSW1__renewable__temperature_2m' not in values


def test_selector_runs_all_methods_without_outer_labels():
    from nemic.fundamentals.selection import select
    from threadpoolctl import threadpool_limits
    rng=np.random.default_rng(4);idx=pd.date_range('2025-01-01',periods=90*8,freq='3h')
    a=rng.normal(size=len(idx));b=rng.normal(size=len(idx))
    x=pd.DataFrame({'a':a,'b':b,'ix__ab':a*b,'noise':rng.normal(size=len(idx))})
    y=3*a+2*a*b
    meta=pd.DataFrame({'origin':idx,'delivery':idx+pd.Timedelta(hours=1)})
    schema={'groups':{'a':'signal','b':'signal','ix__ab':'interaction','noise':'noise'},'parents':{'ix__ab':['a','b']}}
    with threadpool_limits(limits=2):columns,review=select(x,y,meta,schema)
    assert {'correlation','elastic','permutation'}=={r['method'] for r in review['inner_results']}
    if 'ix__ab' in columns:assert {'a','b'}<=set(columns)
    assert review['selected_count']==len(columns)


def test_holm_and_paired_acceptance_do_not_pass_missing_evidence():
    from nemic.fundamentals.assessment import holm,block_evidence
    np.testing.assert_allclose(holm([.01,.04,.03]),[.03,.06,.06])
    f=pd.DataFrame({'origin':pd.date_range('2025-01-01',periods=2,freq='D'),'actual':[1,2],'point':[1,2],'network':[2,3]})
    assert block_evidence(f,7)['pvalue']==1


def test_portable_research_fit_and_reload(ledger):
    from nemic.fundamentals.modelling import fit_cohort
    from nemic.fundamentals.packaging import export_model,predict
    from nemic.production.registry import validate_package
    import joblib
    ledger.c.update(targets=['flow'],bands=[[1,12]],folds=dict(train_days=60,select_days=14,calibrate_days=14,alert_days=14,evaluate_days=28),
                    limits=dict(batch_hours=1,modelling_hours=1))
    idx=pd.date_range('2025-01-01',periods=144*8,freq='3h');rng=np.random.default_rng(74);signal=rng.normal(size=len(idx))
    frame=pd.DataFrame(dict(origin=idx,delivery=idx+pd.Timedelta(minutes=30),lead=1,connector='QNI',signal=signal,
                            actual_flow=100+signal,anchor_flow=100.,seasonal48_flow=100.,seasonal336_flow=100.))
    path=ledger.data/'table.parquet';frame.to_parquet(path,index=False)
    path.with_suffix('.schema.json').write_text(json.dumps(dict(groups={'signal':'network','lead':'network'},parents={},pilot=False,cohort='synthetic_test')))
    result=fit_cohort(ledger,path)
    assert len(result)==1 and result[0]['promotion'] is False
    modelpath=next((ledger.data/'train').glob('**/model.joblib'));bundle=joblib.load(modelpath)
    package=export_model(modelpath.parent,ledger.data/'package',0)
    assert validate_package(package)['status']=='research'
    x=frame[['signal','lead']].copy();x['own_anchor']=100.
    point,intervals=predict(bundle,x[bundle['columns']])
    assert len(point)==len(frame) and np.isfinite(intervals).all()
