import json
import numpy as np
import pandas as pd
import pytest
from nemic.experiments.core import load_config
from nemic.experiments.shadow import record
from nemic.experiments.reports import table


def config(tmp_path):
    c=load_config();c['_run']=tmp_path/'campaign'
    c['limits']['free_reserve_bytes']=0
    return c


def observation(time='2026-09-14 10:00'):
    return pd.DataFrame([dict(SETTLEMENTDATE=time,INTERCONNECTORID='VIC1-NSW1',
        MWFLOW=123,EXPORTLIMIT=900,IMPORTLIMIT=700,INTERVENTION=0,RUNNO=1)])


def test_shadow_rejects_future_and_stale_observations(tmp_path):
    c=config(tmp_path)
    with pytest.raises(ValueError,match='available'):
        record(c,observation(),pd.Timestamp('2026-09-13 23:59Z'),{})
    with pytest.raises(ValueError,match='30 minutes'):
        record(c,observation(),pd.Timestamp('2026-09-14 01:00Z'),{})


def test_shadow_immutable_origins_precede_outcomes(tmp_path):
    c=config(tmp_path);received=pd.Timestamp('2026-09-14 00:02Z')
    first=record(c,observation(),received,{'sha256':'test'})
    second=record(c,observation(),received,{'sha256':'test'})
    assert first!=second and first.exists()
    f=pd.read_parquet(first)
    assert len(f)==336*3
    assert (f.delivery>f.origin).all()
    assert (f.observed_at<f.origin).all()
    assert f.origin.iloc[0]==pd.Timestamp('2026-09-14 10:30')
    assert json.loads(first.with_suffix('.json').read_text())['operational_model']=='baseline only'


def test_report_escapes_external_labels_and_keeps_missing_missing():
    result=table([{'label':'<script>bad</script>','value':np.nan}])
    assert '<script>bad' not in result and '&lt;script&gt;' in result
    assert '—' in result
