"""A1: replay the v1 matched comparison and keep the matched (treated, control) half-hour pairs.

v1 (compare.run_connector) keeps only per-unit control medians. Constraint statistics on the control side need the
pairs, so the same matching is re-run with bootstrap and placebo switched off (compare.FAST) and every run_effect call
captured through compare.PAIR_SINK (actual and ±7-day placebo pairs). Determinism gate: replayed family-level control medians must equal the saved
v1 units, and key-level effects must equal the saved key effects.

Plan: execution/nos_constraint_binding_v1/PLAN.md §5 (A1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nemic.common import IC

from . import compare
from .common import DATA, ROOT, write_json, write_parquet
from .state import GRID30

BDATA = ROOT / "data" / "nos_binding_v1"
GATE_COLS = ["c_capacity", "c_headroom", "c_directional_flow", "c_at_limit", "n_controls"]


def _label(s: dict) -> dict:
    level = s.get("level") or ("state" if s.get("state") else ("spill" if s.get("target_ic") else None))
    return {"level": level, "key": s.get("key") if s.get("key") is not None else s.get("GENCONSETID"),
            "GENCONSETID": s.get("GENCONSETID"), "state": s.get("state"), "target_ic": s.get("target_ic")}


def sink_to_frame(sink: list[dict]) -> pd.DataFrame:
    parts = []
    for i, e in enumerate(sink):
        lab = _label(e["summary"])
        for kind, p in [("actual", e["pairs"]), ("placebo", e.get("placebo_pairs"))]:
            if p is None or len(p) == 0:
                continue
            parts.append(pd.DataFrame({"run": i, "kind": kind, "ic": e["ic"], "direction": e["direction"], **lab,
                                       "t_time": GRID30[p.tp.to_numpy()], "c_time": GRID30[p.cp.to_numpy()],
                                       "match_type": p.match_type.to_numpy()}))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def gate(ic: str, units: pd.DataFrame, keys: pd.DataFrame) -> dict:
    saved = pd.read_parquet(DATA / "tables" / f"units__{ic}.parquet")
    on = ["direction", "GENCONSETID", "time"]
    m = saved[on + GATE_COLS].merge(units[on + GATE_COLS], on=on, how="outer", suffixes=("_v1", "_re"), indicator=True)
    out = {"units_v1": len(saved), "units_replay": len(units), "unit_rows_unmatched": int((m._merge != "both").sum())}
    both = m[m._merge == "both"]
    bad = 0
    for c in GATE_COLS:
        a, b = both[c + "_v1"].to_numpy(float), both[c + "_re"].to_numpy(float)
        bad += int((~(np.isclose(a, b, equal_nan=True))).sum())
    out["unit_value_mismatches"] = bad
    ksaved = pd.read_parquet(DATA / "tables" / f"key_effects__{ic}.parquet")
    kon = ["level", "key", "direction"]
    if len(keys) and "effect_capacity" in ksaved:
        ksaved = ksaved[ksaved.direction.notna()]
        keys = keys[keys.direction.notna()]
        km = ksaved[kon + ["effect_capacity", "n_matched"]].merge(keys[kon + ["effect_capacity", "n_matched"]], on=kon,
                                                                   how="outer", suffixes=("_v1", "_re"), indicator=True)
        kb = km[km._merge == "both"]
        out["key_rows_unmatched"] = int((km._merge != "both").sum())
        out["key_value_mismatches"] = int((~np.isclose(kb.effect_capacity_v1.to_numpy(float), kb.effect_capacity_re.to_numpy(float), equal_nan=True)).sum()
                                          + (~np.isclose(kb.n_matched_v1.to_numpy(float), kb.n_matched_re.to_numpy(float), equal_nan=True)).sum())
    out["pass"] = out["unit_rows_unmatched"] == 0 and out["unit_value_mismatches"] == 0 and out.get("key_rows_unmatched", 0) == 0 \
        and out.get("key_value_mismatches", 0) == 0
    return out


def replay(ics: list[str] | None = None) -> dict:
    ics = ics or list(IC)
    BDATA.mkdir(parents=True, exist_ok=True)
    panel = compare.regime_panel()
    coverage = pd.read_parquet(DATA / "family_coverage_30min.parquet")
    relevance = pd.read_parquet(DATA / "set_relevance.parquet")
    lead30 = pd.read_parquet(DATA / "family_leading_30min.parquet")
    all_relevant = sorted(set(relevance.loc[relevance.relevant, "GENCONSETID"]))
    masks, links = compare.spell_linkage(all_relevant)
    result = {}
    compare.FAST = True
    try:
        for ic in ics:
            compare.PAIR_SINK = []
            r = compare.run_connector(ic, panel, coverage, relevance, lead30, masks, links, all_relevant)
            pairs = sink_to_frame(compare.PAIR_SINK)
            g = gate(ic, r["units"], r["keys"])
            g["pair_rows"] = len(pairs)
            g["runs"] = len(compare.PAIR_SINK)
            write_parquet(BDATA / f"pairs__{ic}.parquet", pairs)
            result[IC[ic]["name"]] = g
            print(IC[ic]["name"], g, flush=True)
    finally:
        compare.FAST = False
        compare.PAIR_SINK = None
    result["pass"] = all(v["pass"] for k, v in result.items() if isinstance(v, dict))
    write_json(BDATA / "pairs_gate.json", result)
    return result
