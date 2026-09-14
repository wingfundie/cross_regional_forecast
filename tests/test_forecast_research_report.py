import json
import numpy as np
import pandas as pd
import pytest
from scripts.build_forecast_research_report import aggregate, SNAPSHOT


def test_pooled_errors_preserve_sample_weights_and_squared_rmse():
    f=pd.DataFrame([{'ic':'VNI','n':10,'mae':2.,'rmse':3.},
                    {'ic':'VNI','n':30,'mae':6.,'rmse':7.}])
    r=aggregate(f,['ic'],['mae','rmse'])[0]
    assert r['ic']=='VNI'
    assert r['n']==40 and r['mae']==5
    assert r['rmse']==pytest.approx(np.sqrt(39))


def test_missing_scores_are_not_zero_errors():
    f=pd.DataFrame([{'ic':'VNI','n':10,'mae':np.nan},{'ic':'VNI','n':30,'mae':4.}])
    assert aggregate(f,['ic'],['mae'])[0]['mae']==4


def test_published_snapshot_matches_band_and_event_denominators():
    d=json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    for ic in ['VNI','QNI']:
        overall=next(r for r in d['overall'] if r['ic']==ic and r['protocol']=='rolling' and r['model']=='selected_policy' and r['target']=='flow')
        bands=[r for r in d['paired_gain_ci'] if r['ic']==ic]
        assert sum(r['n'] for r in bands)==overall['n']
        assert sum(r['n']*r['mae'] for r in bands)/overall['n']==pytest.approx(overall['mae'])
        event=next(r for r in d['events'] if r['ic']==ic and r['protocol']=='rolling' and r['model']=='selected_policy')
        assert event['days']==365  # Both directions share the same 365 calendar days.
        assert event['tp']+event['fn']==event['incidents']
        assert event['false_per_day']==pytest.approx(event['fp']/365)


def test_aemo_comparisons_use_identical_pair_counts():
    d=json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    a=pd.DataFrame(d['aemo_matched'])
    assert (a.groupby(['ic','target','band']).n.nunique()==1).all()
    assert (a[a.band.eq(2)].max_lead_hours==36).all()
    assert not a.band.eq(3).any()
