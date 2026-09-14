import json
import numpy as np
import pandas as pd
import pytest
from scripts.build_limit_forecast_report import shift_days,risk_metrics,bundle_prediction,SNAPSHOT


def test_block_shift_preserves_time_of_day():
    x=pd.DataFrame({'x':np.arange(48*9)})
    indices=shift_days(x,7)
    assert np.array_equal(indices%48,np.arange(len(x))%48)
    assert set(indices)==set(range(len(x)))
    with pytest.raises(ValueError):shift_days(x.iloc[:-1],1)


def test_capacity_overstatement_threshold_and_missing_values():
    r=risk_metrics([0,0,0,np.nan],[100,101,-200,999])
    assert r['n']==3
    assert r['over_100_pct']==pytest.approx(100/3)
    assert r['under_100_pct']==pytest.approx(100/3)
    assert r['mae']==pytest.approx(401/3)


def test_persistence_prediction_moves_with_perturbed_history_anchor():
    anchor=np.arange(96,dtype=float);b={'winner':'persistence'}
    shuffled=anchor[shift_days(pd.DataFrame({'x':anchor}),1)]
    assert np.array_equal(bundle_prediction(b,{},shuffled,{}),shuffled)
    assert not np.array_equal(shuffled,anchor)


def test_published_importance_reproduces_original_predictions():
    d=json.loads(SNAPSHOT.read_text(encoding='utf-8'));f=pd.DataFrame(d['importance'])
    assert d['importance_scope']['models']==128
    assert len(f)==128*8
    assert f.groupby(['ic','fold','band','target']).group.nunique().eq(8).all()
    assert f.max_reproduction_error_mw.le(1e-4).all()
    assert f.repeats.eq(3).all()


def test_limit_metric_denominators_match_original_rolling_scores():
    d=json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    for ic in ['VNI','QNI']:
        for t in ['export','import','export_tight','import_tight']:
            rows=[r for r in d['risk'] if r['ic']==ic and r['target']==t and r['model']=='Selected policy' and r['slice']=='All intervals']
            ref=next(r for r in d['overall'] if r['ic']==ic and r['target']==t and r['model']=='selected_policy' and r['protocol']=='rolling')
            assert sum(r['n'] for r in rows)==ref['n']
            assert sum(r['n']*r['mae'] for r in rows)/ref['n']==pytest.approx(ref['mae'])
