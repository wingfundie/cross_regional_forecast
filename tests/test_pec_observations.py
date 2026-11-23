import numpy as np
import pandas as pd

from nemic.experiments.pec.constraints import dispatch_equations, invocation_times, match_limits
from nemic.experiments.pec.observations import REGIONS, coverage, half_hours, observed_intervals


def sample():
    times = pd.date_range("2026-10-01 00:05", periods=12, freq="5min")
    connectors = pd.DataFrame({
        "SETTLEMENTDATE": times, "INTERCONNECTORID": "NSW1-SA1", "RUNNO": 1, "INTERVENTION": 0,
        "LASTCHANGED": times, "report_created": times, "MWFLOW": [0, -20, 40] + [0] * 9,
        "METEREDMWFLOW": -75, "EXPORTLIMIT": [0, -20, 40, 100, 100, 100] + [100] * 6,
        "IMPORTLIMIT": [0, -70, 40, -120, -120, -120] + [-120] * 6,
        "EXPORTGENCONID": ["zero", "upper", "fixed"] + ["cap"] * 9,
        "IMPORTGENCONID": ["zero", "lower", "fixed"] + ["cap"] * 9,
    })
    regions = pd.concat([connectors[["SETTLEMENTDATE", "RUNNO", "INTERVENTION", "LASTCHANGED", "report_created"]]
                        .assign(REGIONID=region, TOTALDEMAND=5000, SS_WIND_CLEAREDMW=1000, SS_SOLAR_CLEAREDMW=500)
                         for region in REGIONS], ignore_index=True)
    return connectors, regions


def test_five_minute_signs_fixed_flow_and_directional_minimum_times():
    connectors, regions = sample()
    five = observed_intervals(connectors.drop(index=9), regions, pd.Timestamp("2026-10-01"))
    five["configuration"] = "observed"
    half = half_hours(five)
    assert five.loc[0, "zero_limits"]
    assert five.loc[1, "forced_flow"] and not five.loc[1, "fixed_transfer"]
    assert five.loc[2, "forced_flow"] and five.loc[2, "fixed_transfer"]
    assert five.loc[2, "metered_flow_mw"] == -75
    assert len(half) == 1
    row = half.iloc[0]
    assert row.nsw_sa_tight == -20 and row.sa_nsw_tight == -40
    assert row.nsw_sa_mean == (0 - 20 + 40 + 300) / 6
    assert row.sa_nsw_mean == (0 + 70 - 40 + 360) / 6
    assert row.nsw_sa_minimum_time == pd.Timestamp("2026-10-01 00:10")
    assert row.sa_nsw_minimum_time == pd.Timestamp("2026-10-01 00:15")
    assert row.nsw_sa_setter == "upper" and row.sa_nsw_setter == "fixed"
    assert row.nsw_residual == 3500
    audit = coverage(five, half, pd.Timestamp("2026-10-01")).iloc[0]
    assert audit.missing_five_minute == 277 and audit.incomplete_half_hours == 47


def test_intervention_solution_and_context_are_from_same_run():
    connectors, regions = sample()
    rerun = connectors.iloc[[0]].assign(INTERVENTION=1, RUNNO=2, EXPORTLIMIT=25)
    selected = observed_intervals(pd.concat([connectors, rerun]), regions, pd.Timestamp("2026-10-01"))
    first = selected.iloc[0]
    assert first.nsw_sa_mw == 25 and first.observed_run_rows == 2
    assert pd.isna(first.nsw_demand)


def test_equation_reconstruction_uses_exact_effective_version_and_operator():
    connectors, regions = sample()
    connectors = connectors.iloc[:3].copy()
    connectors["EXPORTGENCONID"] = "same"
    connectors["IMPORTGENCONID"] = "same"
    five = observed_intervals(connectors, regions, pd.Timestamp("2026-10-01"))
    raw = connectors[["SETTLEMENTDATE", "RUNNO", "INTERVENTION", "LASTCHANGED", "report_created"]].assign(
        CONSTRAINTID="same", GENCONID_EFFECTIVEDATE="2026-10-01", GENCONID_VERSIONNO=[1, 2, 3],
        RHS=[0, 40, 40], LHS=[0, 40, 40], MARGINALVALUE=[1, 0, 0], VIOLATIONDEGREE=0,
        report_vintage="original", source_archive="original.zip",
    )
    definitions = pd.DataFrame({"GENCONID": "same", "EFFECTIVEDATE": "2026-10-01", "VERSIONNO": [1, 2],
                                "LASTCHANGED": "2026-10-01", "CONSTRAINTTYPE": ["<=", ">="],
                                "DESCRIPTION": ["first", "second"], "LIMITTYPE": "test", "IMPACT": "PEC",
                                "SOURCE": "AEMO", "REASON": "version update"})
    factors = definitions[["GENCONID", "EFFECTIVEDATE", "VERSIONNO", "LASTCHANGED"]].assign(
        INTERCONNECTORID="NSW1-SA1", FACTOR=[1, -2])
    solved = dispatch_equations(raw, five, definitions, factors)
    active = pd.DataFrame(columns=["time", "RUNNO", "INTERVENTION", "GENCONID", "GENCONSETID", "INVOCATION_ID"])
    matched = match_limits(five, solved, active)
    assert matched.loc[matched.direction.eq("nsw_sa"), "reconstructed_mw"].iloc[:2].tolist() == [0, -20]
    assert matched.loc[matched.direction.eq("sa_nsw"), "reconstructed_mw"].isna().all()
    assert matched.loc[matched.VERSIONNO.eq(3), "match_status"].eq("exact equation definition unavailable").all()
    assert solved.binding.tolist() == [True, False, False]
    assert solved.near_binding.tolist() == [False, True, False]


def test_fallback_invocation_period_one_ends_at_four_oh_five():
    records = pd.DataFrame({"STARTINTERVALDATETIME": [None, "2026-10-01 00:05", None],
                            "STARTDATE": ["2026-10-01", "2026-10-01", "2026-10-01"],
                            "STARTPERIOD": [1, 1, np.nan]})
    times = invocation_times(records, "start")
    assert times.iloc[0] == pd.Timestamp("2026-10-01 04:05")
    assert times.iloc[1] == pd.Timestamp("2026-10-01 00:05")
    assert pd.isna(times.iloc[2])
