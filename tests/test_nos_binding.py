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
