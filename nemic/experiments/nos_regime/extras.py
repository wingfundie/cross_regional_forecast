"""S5b: derived tables for the standalone report, built from cached S5 outputs (no re-matching).

- duid_pressure: per supported family-direction, which DUIDs apply more leader-level tightening/relief while
  the family is invoked (matched treated half-hours) than in the family-off half-hours of the same months.
- diurnal_48: 48-half-hour profiles of treated/control limits and matched differences for supported families.
- footprint: family × connector-direction effect matrix (relevant = family effects, not relevant = spillover).
- flow_response: per supported family, limit/flow/headroom/at-limit responses and flow pass-through ratio.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nemic.common import IC

from .common import DATA, END, MONTHS, ROOT, START, STUDY, write_parquet
from .state import GRID30, leaders

TABLES = DATA / "tables"
OUT = DATA / "report_tables"


def _load(prefix):
    parts = [pd.read_parquet(p) for p in sorted(TABLES.glob(f"{prefix}__*.parquet"))]
    parts = [p for p in parts if "empty" not in p.columns]
    return pd.concat(parts, ignore_index=True)


def duid_pressure(fam: pd.DataFrame, units: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sup = fam[fam.tier.eq("supported")]
    for ic in IC:
        s = sup[sup.ic.eq(ic)]
        if s.empty:
            continue
        lead = leaders(ic)
        lead["dir"] = lead.direction.map({"forward": "upper", "reverse": "lower"})
        parts = []
        for month in MONTHS:
            p = ROOT / f"data/constraint_{STUDY[ic]}_2y/months/{month}/unit_pressure_5min.parquet"
            u = pd.read_parquet(p, columns=["time", "direction", "constraint", "DUID", "tightening_mw"])
            u = u[u.tightening_mw.notna() & u.tightening_mw.ne(0)]
            parts.append(u)
        u = pd.concat(parts, ignore_index=True)
        u = u.merge(lead[["time", "dir", "constraint"]], left_on=["time", "direction", "constraint"],
                    right_on=["time", "dir", "constraint"])          # leader-only attribution (no duplication)
        u["time30"] = u.time.dt.ceil("30min")
        u["tight"] = u.tightening_mw.clip(lower=0)
        u["relief"] = (-u.tightening_mw).clip(lower=0)
        agg = u.groupby(["direction", "time30", "DUID"])[["tight", "relief"]].sum()
        for r in s.itertuples():
            d = "upper" if r.direction == "forward" else "lower"
            tu = units[(units.ic == ic) & (units.direction == r.direction) & (units.GENCONSETID == r.GENCONSETID) & units.matched]
            treated = pd.DatetimeIndex(tu.time)
            if len(treated) == 0:
                continue
            months = set(treated.to_period("M"))
            off = coverage.index[(coverage[r.GENCONSETID] == 0).to_numpy()]
            base = off[off.to_period("M").isin(months)]
            try:
                a = agg.xs(d, level="direction")
            except KeyError:
                continue
            t_sum = a[a.index.get_level_values("time30").isin(treated)].groupby("DUID").sum() / len(treated)
            b_sum = a[a.index.get_level_values("time30").isin(base)].groupby("DUID").sum() / max(len(base), 1)
            j = t_sum.join(b_sum, how="outer", lsuffix="_treated", rsuffix="_base").fillna(0.0)
            j["excess_tightening"] = j.tight_treated - j.tight_base
            j["excess_relief"] = j.relief_treated - j.relief_base
            j = j.assign(score=j.excess_tightening.abs() + j.excess_relief.abs()).sort_values("score", ascending=False).head(10)
            for duid, x in j.iterrows():
                rows.append({"ic": ic, "name": IC[ic]["name"], "direction": r.direction, "GENCONSETID": r.GENCONSETID, "DUID": duid,
                             "tightening_per_hh_treated": x.tight_treated, "tightening_per_hh_base": x.tight_base,
                             "relief_per_hh_treated": x.relief_treated, "relief_per_hh_base": x.relief_base,
                             "excess_tightening": x.excess_tightening, "excess_relief": x.excess_relief,
                             "treated_half_hours": len(treated), "base_half_hours": len(base)})
        print("duid pressure", IC[ic]["name"], flush=True)
    return pd.DataFrame(rows)


def diurnal_48(fam, units):
    sup = fam[fam.tier.eq("supported")][["ic", "direction", "GENCONSETID"]]
    m = units.merge(sup, on=["ic", "direction", "GENCONSETID"])
    m = m[m.matched]
    m["season"] = m.season.astype(str)
    g = m.groupby(["name", "direction", "season", "half_hour"])
    out = g.agg(units_n=("d_capacity", "size"), treated_capacity=("t_capacity", "median"), control_capacity=("c_capacity", "median"),
                capacity_effect=("d_capacity", "median"), flow_effect=("d_directional_flow", "median"),
                at_limit_effect=("d_at_limit", "mean")).reset_index()
    allseason = (m.groupby(["name", "direction", "half_hour"]).agg(units_n=("d_capacity", "size"), treated_capacity=("t_capacity", "median"),
                                                                   control_capacity=("c_capacity", "median"), capacity_effect=("d_capacity", "median"),
                                                                   flow_effect=("d_directional_flow", "median"), at_limit_effect=("d_at_limit", "mean"))
                 .reset_index().assign(season="All"))
    out = pd.concat([out, allseason], ignore_index=True)
    out["clock"] = out.half_hour.map(lambda h: f"{(int(h) // 2) % 24:02d}:{(int(h) % 2) * 30:02d}")
    return out


def footprint(fam, spill):
    a = fam[["ic", "name", "direction", "GENCONSETID", "effect_capacity", "ci_lo_capacity", "ci_hi_capacity", "tier", "episodes", "treated_hours"]].assign(relation="relevant")
    b = spill.rename(columns={"target_ic": "ic", "target_name": "name"})[["ic", "name", "direction", "GENCONSETID", "effect_capacity", "ci_lo_capacity",
                                                                          "ci_hi_capacity", "tier", "episodes", "treated_hours"]].assign(relation="not relevant (spillover)")
    f = pd.concat([a, b], ignore_index=True)
    f["ci_excludes_zero"] = (f.ci_lo_capacity > 0) | (f.ci_hi_capacity < 0)
    return f


def flow_response(fam):
    s = fam[fam.tier.eq("supported")].copy()
    s["flow_pass_through"] = np.where(s.effect_capacity.abs() > 25, s.effect_directional_flow / s.effect_capacity, np.nan)
    s["headroom_absorbed"] = np.where(s.effect_capacity.abs() > 25, s.effect_headroom / s.effect_capacity, np.nan)
    return s[["ic", "name", "direction", "GENCONSETID", "effect_capacity", "effect_directional_flow", "effect_headroom", "effect_at_limit",
              "treated_at_limit", "control_at_limit", "ci_lo_directional_flow", "ci_hi_directional_flow", "ci_lo_at_limit", "ci_hi_at_limit",
              "flow_pass_through", "headroom_absorbed", "episodes", "treated_hours"]]


def build_extras() -> dict:
    fam = _load("family_effects"); units = _load("units"); spill = _load("spillover")
    coverage = pd.read_parquet(DATA / "family_coverage_30min.parquet").reindex(GRID30)
    out = {"duid_pressure": duid_pressure(fam, units, coverage), "diurnal_48": diurnal_48(fam, units),
           "footprint": footprint(fam, spill), "flow_response": flow_response(fam)}
    for k, v in out.items():
        write_parquet(OUT / f"{k}.parquet", v)
    return {k: len(v) for k, v in out.items()}
