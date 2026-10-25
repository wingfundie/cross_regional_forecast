"""Public inference boundaries, temporal isolation and physical sign semantics."""
from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"packages/nemic-regimes/src"))
from nemic_regimes import RegimeBundle,load_bundle
from nemic_regimes.core import structural_era,weighted_quantiles,sha256
from nemic_regimes.provenance import validate_inputs
from nemic.experiments.conditional_regimes.data import physical
from nemic.experiments.conditional_regimes.research import fit_settings,partitions,folds
from nemic.experiments.conditional_regimes.sources import parse_tables


@pytest.fixture
def panel():
    times=pd.date_range("2025-01-01",periods=90*48,freq="30min")
    f=pd.DataFrame({"time":times,"connector":"VNI","direction":"forward","quarter":1,
                    "half_hour":times.hour*2+times.minute//30,"era":"pre_pec_market",
                    "daytype":np.where(times.dayofweek>=5,"weekend","weekday"),
                    "capacity":np.tile(np.arange(90),48)[:len(times)]*10.-100.,
                    "tight_capacity":-150.,"active_sets":"","active_assets":"","partial_sets":"","episode_ids":"","outage_state":"clear"})
    from nemic_regimes.core import NUMERIC_FEATURES
    for feature in NUMERIC_FEATURES:f[feature]=np.arange(len(f))%100
    return f


@pytest.fixture
def bundle(panel):
    return RegimeBundle(panel,{"as_of":"2026-10-25","bundle_id":"test","settings":{"VNI/forward":fit_settings(panel)}})


def query(**kwargs):
    return {"connector":"VNI","direction":"forward","quarter":1,"half_hour":24,"era":"pre_pec_market",**kwargs}


def test_unknown_structural_era_is_unavailable(bundle):
    assert bundle.select(query(era="current"))["status"]=="unavailable"


def test_never_relaxes_a_required_outage(bundle):
    result=bundle.select(query(required_sets=["NONEXISTENT"]))
    assert result["status"]=="unavailable" and result["p50_mw"] is None


def test_conflicting_outage_specification_rejected(bundle):
    with pytest.raises(ValueError,match="both required"):
        bundle.select(query(required_sets=["A"],excluded_sets=["A"]))


def test_missing_condition_gets_explicit_broader_label(bundle):
    r=bundle.select(query(source_vre=10000))
    assert r["status"]=="broader_analogue"
    assert "source_vre" in r["outside_support"] and "source_vre" in r["relaxed_conditions"]


def test_unseen_quarter_not_silently_exact(bundle):
    r=bundle.select(query(quarter=2))
    assert "quarter" in r["relaxed_conditions"] and r["status"]=="broader_analogue"


def test_baseline_uses_all_quarter_days(bundle,panel):
    r=bundle.select(query(method="baseline"))
    assert r["analogue_days"]==90
    expected=panel[panel.half_hour==24].capacity.median()
    assert r["p50_mw"]==expected


def test_negative_directional_target_is_preserved(bundle):
    r=bundle.select(query(target="tight"))
    assert r["p50_mw"]==-150 and r["forced_flow_share"]==1


def test_full_diurnal_profile_and_batch_agree(bundle):
    p=bundle.profile(1,{"connector":"VNI","era":"pre_pec_market"})
    assert list(p.half_hour)==list(range(48))
    assert p.p50_mw.iloc[24]==bundle.select(query())["p50_mw"]
    assert bundle.select([query(),query(target="tight")])[1]["p50_mw"]==-150


def test_unrecognised_feature_cannot_be_silently_ignored(bundle):
    with pytest.raises(ValueError,match="Unknown condition"):
        bundle.select(query(future_setter="foo"))


@pytest.mark.parametrize("extra",[{"quarter":5},{"half_hour":48},{"source_vre":float("nan")},{"source_vre":{"min":5,"max":1}}])
def test_invalid_condition_rejected(bundle,extra):
    with pytest.raises(ValueError):bundle.select(query(**extra))


def test_weighted_quantile_keeps_signed_tail():
    q=weighted_quantiles([-100,0,100],[1,1,1])
    assert q[0]<0 and q[1]==0


def test_market_eras_are_connector_specific():
    assert structural_era("Basslink","2026-07-01")=="regulated"
    assert structural_era("Heywood","2026-09-30")=="pre_pec_market"
    assert structural_era("Heywood","2026-10-01")=="pec_market"
    assert structural_era("QNI","2026-10-01")=="qni_existing"


def input_row(**overrides):
    return {"source":"AEMO","product":"test","run_id":"r1","issue":"2026-10-24T00:00:00Z",
            "received":"2026-10-24T00:05:00Z","receipt_completed":"2026-10-24T00:06:00Z",
            "delivery":"2026-10-25T00:00:00Z","sha256":"a"*64,"variable":"source_vre","value":100,
            "availability_evidence":"measured_receipt",**overrides}


@pytest.mark.parametrize("override",[{"availability_evidence":"publication_proxy"},{"receipt_completed":"2026-10-25T00:01:00Z"},
                                      {"received":"2026-10-23T00:00:00Z"},{"retrieval_started":"2026-10-24T00:07:00Z"}])
def test_bad_asof_provenance_rejected(override):
    with pytest.raises(ValueError):validate_inputs([input_row(**override)],"2026-10-25T00:00:00Z")


def test_mixed_weather_vintages_rejected():
    a=input_row(coherence_group="same")
    b=input_row(variable="sink_vre",run_id="r2",coherence_group="same")
    with pytest.raises(ValueError,match="Mixed vintages"):
        validate_inputs([a,b],"2026-10-24T01:00:00Z")


def test_asof_value_must_match_provenance():
    with pytest.raises(ValueError,match="differs"):
        validate_inputs([input_row()],"2026-10-24T01:00:00Z",{"source_vre":200})


def test_named_regime_cannot_bypass_asof_inputs(bundle):
    with pytest.raises(ValueError,match="without input provenance"):
        bundle.select(query(mode="asof",origin="2026-01-01T00:00:00+10:00",delivery="2026-01-01T12:00:00+10:00",regime="high_source_vre",inputs=[]))


def test_baseline_compact_and_full_match_even_with_unseen_outage(bundle):
    q=query(method="baseline",required_sets=["NO_HISTORY"],exact_sets=True)
    assert bundle.select(q)["p50_mw"]==bundle.select(q,details=False)["p50_mw"]


def test_one_long_outage_cannot_count_as_many_independent_episodes(bundle):
    bundle.panel["episode_ids"]="one_episode"
    bundle.metadata["episode_links"]={"one_episode":{"canonical_id":"one_episode","sets":["A"],"assets":[]}}
    for g in bundle._groups.values():
        g["active_sets"]="A";g["outage_state"]="invoked";g["episode_ids"]="one_episode"
    r=bundle.select(query(required_sets=["A"],outage_state="invoked"))
    assert r["status"]=="broader_analogue" and r["outage_episodes"]==1


def test_bundle_hash_mismatch_rejected(tmp_path,panel):
    panel.to_parquet(tmp_path/"panel.parquet")
    (tmp_path/"manifest.json").write_text(json.dumps({"schema_version":1,"files":{"panel.parquet":"a"*64}}))
    with pytest.raises(ValueError,match="hash mismatch"):load_bundle(tmp_path)


def test_no_future_rows_in_chronological_partitions(panel):
    f=panel.copy();f["episode_ids"]=""
    fold={"start":pd.Timestamp("2025-01-01"),"train_end":pd.Timestamp("2025-02-01"),"select_end":pd.Timestamp("2025-02-15"),
          "alert_start":pd.Timestamp("2025-03-01"),"cal_end":pd.Timestamp("2025-03-15"),"eval_end":pd.Timestamp("2025-04-01")}
    f.loc[f.time.between("2025-01-30","2025-02-03"),"episode_ids"]="incident"
    parts,audit=partitions(f,fold)
    assert not parts["train"].episode_ids.eq("incident").any()
    assert parts["train"].time.max()<=fold["train_end"]
    assert parts["evaluation"].time.min()>fold["cal_end"]
    assert audit["train"]["purged"]>0


def test_fit_scales_do_not_depend_on_future(panel):
    train=panel.iloc[:1000]
    before=fit_settings(train)
    panel.loc[1000:,"source_vre"]=1e9
    assert before==fit_settings(train)


def test_physical_intervention_selection():
    f=pd.DataFrame({"SETTLEMENTDATE":["2026/10/01 00:05:00"]*2,"INTERCONNECTORID":["V-SA"]*2,
                    "INTERVENTION":["0","1"],"RUNNO":["2","1"],"LASTCHANGED":["2026/10/01 00:05:01"]*2,"EXPORTLIMIT":["100","-50"]})
    result=physical(f,"INTERCONNECTORID")
    assert len(result)==1 and result.EXPORTLIMIT.iat[0]=="-50"


def test_assessment_applies_each_rows_alert_policy():
    from nemic.experiments.conditional_regimes.assessment import assessed_score
    f=pd.DataFrame({"time":pd.to_datetime(["2026-01-01","2026-01-02"]),"actual":[10.,100.],"p10":[0.,0.],"p50":[50.,50.],"p90":[150.,150.],
                    "threshold":[50.,50.],"probability":[.4,.4],"alert_threshold":[.25,.75]})
    m=assessed_score(f)
    assert m["restriction_recall"]==1 and m["restriction_precision"]==1 and m["false_alerts_per_day"]==0


def test_missing_restriction_reference_is_not_a_healthy_non_event():
    from nemic.experiments.conditional_regimes.assessment import assessed_score
    f=pd.DataFrame({"time":pd.to_datetime(["2026-01-01"]),"actual":[-100.],"p10":[-150.],"p50":[-90.],"p90":[0.],
                    "threshold":[np.nan],"probability":[np.nan],"alert_threshold":[.5]})
    m=assessed_score(f)
    assert m["restriction_scored_rows"]==0 and m["restriction_recall"] is None and m["forced_days"]==1


def test_background_outages_do_not_qualify_as_requested_repetitions(panel):
    panel["active_sets"]="A|B";panel["outage_state"]="invoked"
    panel["episode_ids"]=["a1|b"+str(i%10) for i in range(len(panel))]
    links={"a1":{"canonical_id":"a1","sets":["A"],"assets":[]}}
    links.update({"b"+str(i):{"canonical_id":"b"+str(i),"sets":["B"],"assets":[]} for i in range(10)})
    b=RegimeBundle(panel,{"as_of":"2026-10-25","episode_links":links,"settings":{"VNI/forward":fit_settings(panel)}})
    result=b.select(query(required_sets=["A"]))
    assert result["status"]=="broader_analogue" and result["outage_episodes"]==1


def test_resubmission_ids_count_as_one_episode():
    from nemic_regimes.evidence import requested_episode_counts
    links={str(i):{"canonical_id":"final","sets":["A"],"assets":[]} for i in range(5)}
    assert requested_episode_counts(set(links),["A"],[],links)=={"set:A":1}


def test_static_table_matches_reference_quantiles(bundle):
    a=bundle.select(query(method="table"))
    b=bundle.select(query(method="baseline"))
    assert a["status"]=="supported_table"
    assert [a[k] for k in ("p10_mw","p50_mw","p90_mw")]==[b[k] for k in ("p10_mw","p50_mw","p90_mw")]


def test_static_table_does_not_broaden_a_missing_condition(bundle):
    r=bundle.select(query(method="table",source_vre={"min":10000}))
    assert r["status"]=="unavailable" and not r["relaxed_conditions"]


def test_static_table_preserves_negative_tight_limit(bundle):
    assert bundle.select(query(method="table",target="tight"))["p50_mw"]==-150


def test_wrong_region_cannot_be_an_asof_source_condition():
    with pytest.raises(ValueError,match="region"):
        validate_inputs([input_row(region="QLD1",units="MW")],"2026-10-24T01:00:00Z",{"connector":"VNI","direction":"forward","source_vre":100})


def test_noncanonical_weather_unit_is_rejected():
    with pytest.raises(ValueError,match="units"):
        validate_inputs([input_row(variable="temperature_max",value=300,regions=["VIC1","NSW1"],units="K")],
                        "2026-10-24T01:00:00Z",{"connector":"VNI","direction":"forward","temperature_max":300})
