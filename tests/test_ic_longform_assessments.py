"""Small, source-independent checks for the cached diagnostic renderer."""
import numpy as np
import pandas as pd

from scripts.build_ic_longform_assessments import HOURS, Report, statistics


def test_literal_hour_mapping():
    assert HOURS == {48: 24, 96: 48, 336: 168}
    assert 336 not in HOURS.values()


def test_error_statistics_use_prediction_minus_actual():
    result = statistics(pd.DataFrame({'actual': [0., 2., 4.], 'point': [1., 0., 7.]}))
    assert result['n'] == 3
    assert result['mae'] == 2
    np.testing.assert_allclose(result['bias'], 2 / 3)
    np.testing.assert_allclose(result['rmse'], np.sqrt(14 / 3))
    assert result['median_ae'] == 2
    assert result['max_ae'] == 3
    assert result['r2'] == -0.75


def test_finite_pairs_and_constant_target():
    result = statistics(pd.DataFrame({'actual': [1., 1., np.nan, 1.], 'point': [2., 3., 4., np.inf]}))
    assert result['n'] == 2
    assert result['mae'] == 1.5
    assert result['r2'] is None
    assert statistics(pd.DataFrame({'actual': [np.nan], 'point': [2.]})) == {'n': 0}


def test_alternative_output_is_explicit():
    frame = pd.DataFrame({'actual': [1., 2.], 'point': [3., 4.], 'q0.5': [1., 2.]})
    assert statistics(frame)['mae'] == 2
    assert statistics(frame, 'q0.5')['mae'] == 0


def test_sources_are_hashed_before_use(tmp_path):
    source = tmp_path / 'source.txt'
    source.write_text('frozen evidence', encoding='utf-8')
    report = object.__new__(Report)
    report.inputs = set()
    report.initial_hashes = {}
    assert report.source(source) == source
    initial = report.initial_hashes.copy()
    source.write_text('changed evidence', encoding='utf-8')
    report.source(source)
    assert report.initial_hashes == initial


def test_narrative_is_escaped():
    report = object.__new__(Report)
    report.parts, report.prose = [], []
    report.discuss('A < B & C')
    assert report.prose == ['A < B & C']
    assert report.parts == ['<p>A &lt; B &amp; C</p>']
