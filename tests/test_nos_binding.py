import numpy as np
import pandas as pd

from nemic.experiments.nos_regime import compare, setters
from nemic.experiments.nos_regime.state import GRID5, GRID30


def _layer(rows):
    frame = pd.DataFrame(rows, columns=["time", "direction", "constraint"])
    return setters.build_layer(frame, "setter")


def test_layer_shares_are_per_half_hour_interval_fractions():
    t0 = GRID30[10]
    five = pd.date_range(t0 - pd.Timedelta("25min"), t0, freq="5min")
    rows = [(t, "forward", "A" if i < 4 else "B") for i, t in enumerate(five)]
    layer = _layer(rows)
    H = layer.H["forward"].toarray()
    a, b = layer.codes.get_loc("A"), layer.codes.get_loc("B")
    assert np.isclose(H[10, a], 4 / 6) and np.isclose(H[10, b], 2 / 6)
    assert np.isclose(H[10].sum(), 1.0) and layer.last["forward"][10] == b
    assert layer.avail["forward"][10] == 6 and layer.avail["forward"][11] == 0


def test_transitions_align_one_before_value_per_run():
    # setter "N" normally, "O" from the run's first half-hour; two runs separated by a gap
    rows = []
    for i in range(0, 40):
        c = "O" if (10 <= i <= 12 or 20 <= i <= 21) else "N"
        rows.append((GRID30[i], "forward", c))
    layer = _layer(rows)
    treated = np.array([10, 11, 12, 20, 21])
    tr = setters.transitions(layer, "forward", treated)
    assert list(tr.run_start) == [GRID30[10], GRID30[20]]
    assert list(tr.before) == ["N", "N"] and list(tr.first_during) == ["O", "O"]
    assert tr.changed.tolist() == [True, True]


def test_boot_mean_brackets_mean_and_is_deterministic():
    rng = np.random.default_rng(1)
    d = rng.normal(0.2, 0.1, 300); days = np.repeat(np.arange(30), 10)
    a = setters.boot_mean(d, days); b = setters.boot_mean(d, days)
    assert a == b and a[0] < d.mean() < a[1]


def test_family_stats_treated_minus_matched_control():
    rows = [(t, "forward", "OWN" if GRID30.get_indexer([t.ceil("30min")])[0] in (5, 6) else "SN") for t in GRID5[:60]]
    layer = _layer(rows)
    pairs = pd.DataFrame({"t_time": [GRID30[5], GRID30[5], GRID30[6]], "c_time": [GRID30[1], GRID30[2], GRID30[3]]})
    own = layer.codes.isin({"OWN"})
    classes = setters.classify(layer.codes, {"OWN"}, set())
    row, top, unit = setters.family_stats(layer, "forward", pairs, own, classes)
    assert row["n_units"] == 2 and np.isclose(row["own_treated"], 1.0) and np.isclose(row["own_control"], 0.0)
    assert set(top.constraint) == {"OWN", "SN"}
    sn = top.set_index("constraint").loc["SN"]
    assert np.isclose(sn.diff_pp, -100.0) and sn["class"] == "system_normal_other"


def test_classify_prefixes_and_membership():
    codes = pd.Index(["#RAMP", "F_Q++NIL_R6", "N>>NIL_33_34", "N^^Q_ARSR_KPP_1", "OTHER_OUT"])
    got = setters.classify(codes, {"N^^Q_ARSR_KPP_1"}, {"OTHER_OUT", "N^^Q_ARSR_KPP_1"})
    assert list(got) == ["ramp_discretionary", "fcas", "system_normal_other", "own_set", "other_outage_set"]


def test_pair_sink_is_opt_in():
    assert compare.PAIR_SINK is None and compare.FAST is False


# ----------------------------------------------------------------------------- outlook (Phase D)
from nemic.experiments.nos_regime import outlook  # noqa: E402


def test_lead_bands_and_resubmission_chain():
    assert [outlook.lead_band(x) for x in (0.1, 7, 7.2, 30, 31, 90, 91, 365)] == ["0-7", "0-7", "8-30", "8-30", "31-90", "31-90", "91-365", "91-365"]
    assert outlook.lead_band(-1) is None
    succ = {"1": "2", "2": "3", "9": "9x", "9x": "9"}
    assert outlook.final_id("1", succ) == "3" and outlook.final_id("5", succ) == "5"
    assert outlook.final_id("9", succ) in {"9", "9x"}           # cycle terminates


def test_infer_families_uses_same_equipment_type_and_backs_off():
    hist = pd.DataFrame({"OUTAGEID": list("abcde"),
                         "primary_asset": ["S/LINE/1", "S/LINE/1", "S/CB/9", "S/LINE/2", "T/LINE/7"],
                         "primary_equipment_type_used": ["LINE", "LINE", "CB", "LINE", "LINE"],
                         "primary_substationid": ["S", "S", "S", "S", "T"], "area_key": ["A", "A", "A", "A", "A"],
                         "families": [["F1"], ["F1", "F2"], ["FCB"], ["F3"], ["F4"]]})
    b = pd.DataFrame({"OUTAGEID": ["x", "y", "z"], "asset": ["S/LINE/1", "S/LINE/5", "S/CB/9"],
                      "equipment_type_used": ["LINE", "LINE", "CB"], "substation": ["S", "S", "S"], "area_key": ["A", "A", "A"],
                      "linked_sets": [[], [], ["F9"]]})
    got = outlook.infer_families(b, hist, {"F1", "F2", "F3", "F4", "FCB", "F9"})
    x = got[got.OUTAGEID.eq("x")].set_index("family")
    assert x.loc["F1"].family_probability == 1.0 and x.loc["F2"].family_probability == 0.5 and set(x.inference_level) == {"K1"}
    y = got[got.OUTAGEID.eq("y")]
    assert set(y.inference_level) == {"K3"} and "FCB" not in set(y.family)          # substation back-off, LINE only
    z = got[got.OUTAGEID.eq("z")]
    assert list(z.family) == ["F9"] and z.family_source.iat[0] == "linked"


def test_apply_skill_falls_back_to_normal_rate():
    out = pd.DataFrame({"lead_days": [3.0, 40.0], "name": ["QNI", "QNI"], "direction": ["forward", "forward"],
                        "family_source": ["linked", "inferred"], "binding_p_1": [0.4, 0.4], "binding_normal_1": [0.1, 0.1]})
    cells = pd.DataFrame({"layer": ["binding", "binding"], "lead_band": ["0-7", "31-90"], "name": ["QNI", "QNI"],
                          "direction": ["forward", "forward"], "skilful": [True, False]})
    got = outlook.apply_skill(out, cells)
    assert list(got.skill_status) == ["skilful", "baseline_shown"]
    assert list(got.binding_p_1) == [0.4, 0.1] and list(got.binding_p_outlook_1) == [0.4, 0.4]


def test_evidence_embargo_excludes_recent_units():
    class L:
        codes = pd.Index(["A"])
    ev = outlook.Evidence.__new__(outlook.Evidence)
    t = GRID30[100:110]
    ev.units = pd.DataFrame({"time": t, "direction": "forward", "GENCONSETID": "F", "matched": True, "d_capacity": -10.0,
                             "nem_date": t.normalize(), "season": "Summer", "day_period": "Overnight"})
    ev.pairs = pd.DataFrame({"level": "K2", "key": "F", "direction": "forward", "kind": "actual", "t_time": t, "c_time": GRID30[0:10]})
    ev.layers, ev.own_of, ev.outage_members, ev.links, ev.capacity, ev.cache, ev.ic = {}, {}, set(), \
        pd.DataFrame(columns=["GENCONSETID", "OUTAGEID", "start", "end"]), {}, {}, "X"
    as_of = t[4] + outlook.EMBARGO                       # only the first five units are >= 21 days old
    got = ev.family("F", "forward", as_of)
    assert got["n_treated"] == 5
    assert ev.family("F", "forward", t[0] + outlook.EMBARGO - pd.Timedelta(minutes=1)) is None


def test_own_share_counts_intervals_not_equations():
    t0 = GRID30[10]
    five = pd.date_range(t0 - pd.Timedelta("25min"), t0, freq="5min")
    rows = [(t, "forward", "A") for t in five[:3]] + [(t, "forward", "B") for t in five[:3]] + [(five[5], "forward", "C")]
    layer = _layer(rows)
    own = layer.codes.isin({"A", "B"})
    assert np.isclose(layer.own_share("forward", own)[10], 3 / 4)      # 4 intervals with data; A and B overlap in 3
    layer.avail["forward"][10] = 6
    assert np.isclose(layer.own_share("forward", own)[10], 3 / 6)
