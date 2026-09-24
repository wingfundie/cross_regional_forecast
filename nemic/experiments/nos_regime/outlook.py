"""Phase D: forward outlook of constraint behaviour for booked NOS outages, and its walk-forward backtest.

Plan: execution/nos_constraint_binding_v1/PLAN.md §6–§7. This is a research outlook, not a deployed forecast service.

Every statistic is computed "as of" a snapshot: matched units and pairs are embargoed to treated half-hours ending at
least 21 days before ``as_of`` (controls lie within ±21 days, so none can follow the snapshot), and relevance, evidence
tiers, family inference, booking reliability and baselines use pre-``as_of`` data only. Bookings come from the NOS
state as generated at ``as_of`` (weekly archives of half-hourly reports; change log in ``changes.parquet``).

Prediction for a booking b, candidate family f (probability p_f; 1 when the snapshot links the set), connector-direction
and equation e:  q = p_f × (1 − withdrawal_rate_f);  P(e active) = q × s_treated(e) + (1 − q) × s_control(e), where the
shares come from the matched comparison. Limit change is the as-of family effect (median matched difference), reported
conditional on invocation and as q × effect.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from nemic.common import IC

from . import compare
from .common import DATA, END, NOS_WEEKS, ROOT, START, nem_time, write_json, write_parquet
from .episodes import TYPE_ORDER, WITHDRAWN, equipment_at, infer_type
from .pairs import BDATA
from .setters import Layer, boot_mean, classify, family_stats, membership
from .state import GRID30, set_members, standing

OUT = BDATA / "outlook"
LOCAL_WEEKS = BDATA / "nos_weeks"
EMBARGO = pd.Timedelta(days=21)
HORIZON = pd.Timedelta(days=365)
EXCLUDE_STATUS = WITHDRAWN | {"COMPLETE", "INFO"}
LEAD_BANDS = [(0, 7, "0-7"), (8, 30, "8-30"), (31, 90, "31-90"), (91, 365, "91-365")]
MIN_INFER_EPISODES = 2
EVENT_SHARE = 0.05          # event: equation active in >= 5% of the outage's half-hour intervals
DIRECTIONS = ["forward", "reverse"]
SEASON = {12: "Summer", 1: "Summer", 2: "Summer", 3: "Autumn", 4: "Autumn", 5: "Autumn", 6: "Winter", 7: "Winter",
          8: "Winter", 9: "Spring", 10: "Spring", 11: "Spring"}


# --------------------------------------------------------------------------- snapshots
def week_dirs() -> pd.DataFrame:
    rows = []
    for base in [NOS_WEEKS, LOCAL_WEEKS]:
        for p in sorted(base.glob("PUBLIC_NETWORK_*")) if base.exists() else []:
            if (p / "changes.parquet").exists():
                rows.append({"name": p.name, "path": p, "date": pd.Timestamp(p.name[-8:])})
    w = pd.DataFrame(rows)
    return w.sort_values("date").drop_duplicates("name", keep="last").reset_index(drop=True) if len(w) else w


def snapshot(week: Path, at: pd.Timestamp | None = None) -> tuple[pd.Timestamp, str, pd.DataFrame, pd.DataFrame, dict]:
    """NOS state at the last complete report generated at or before ``at`` inside one weekly archive."""
    reports = pd.read_parquet(week / "reports.parquet").sort_values("generated_nem")
    if at is not None:
        reports = reports[reports.generated_nem <= at]
    if reports.empty:
        raise ValueError(f"No complete report at or before {at} in {week.name}")
    last = reports.iloc[-1]
    ch = pd.read_parquet(week / "changes.parquet")
    ch = ch[ch.generated_nem <= last.generated_nem].sort_values("generated_nem").drop_duplicates("row_id", keep="last")
    present = set(ch.loc[ch.present, "row_id"])
    rows = pd.read_parquet(week / "rows.parquet")
    rows = rows[rows.row_id.isin(present)]
    recs = [dict(json.loads(f), _table=t) for f, t in zip(rows.fields_json, rows.table)]
    frame = pd.DataFrame(recs)
    detail = frame[frame._table.eq("OUTAGEDETAIL")].drop(columns="_table").reset_index(drop=True)
    sets = frame[frame._table.eq("OUTAGECONSTRAINTSET")].drop(columns="_table").dropna(axis=1, how="all").reset_index(drop=True)
    manifest = json.loads((week / "manifest.json").read_text()) if (week / "manifest.json").exists() else {}
    meta = {"week_file": week.name, "report_member": last.member, "generated_nem": str(last.generated_nem),
            "week_raw_sha256": manifest.get("raw_sha256"), "week_url": manifest.get("url"), "rows_present": len(present)}
    return last.generated_nem, last.member, detail, sets, meta


# --------------------------------------------------------------------------- bookings and keys
_EQUIP: pd.DataFrame | None = None
_KEYS: pd.DataFrame | None = None


def _equipment() -> pd.DataFrame:
    global _EQUIP
    if _EQUIP is None:
        raw = sorted((DATA / "raw" / "mmsdm").glob("NETWORK_EQUIPMENTDETAIL_*.parquet"))[-1]
        _EQUIP = equipment_at(pd.read_parquet(raw))[["ELEMENTID", "VALIDFROM", "VALIDTO", "VOLTAGE", "DESCRIPTION"]]
    return _EQUIP


def _keys() -> pd.DataFrame:
    global _KEYS
    if _KEYS is None:
        _KEYS = pd.read_parquet(DATA / "outage_keys.parquet")
    return _KEYS


def area_of_substation() -> tuple[dict, dict]:
    k = _keys()
    k = k[k.SUBSTATIONID.notna()]
    area = k.dropna(subset=["area_key"]).groupby("SUBSTATIONID").area_key.agg(lambda s: s.mode().iat[0]).to_dict()
    label = k.dropna(subset=["area_label"]).groupby("SUBSTATIONID").area_label.agg(lambda s: s.mode().iat[0]).to_dict()
    return area, label


def bookings(detail: pd.DataFrame, sets: pd.DataFrame, as_of: pd.Timestamp, horizon: pd.Timedelta = HORIZON) -> pd.DataFrame:
    """Live bookings at as_of with primary asset (episodes.py rules), K3 substation, K4 area and linked sets."""
    d = detail.copy()
    for c in ["STARTTIME", "ENDTIME", "SUBMITTEDDATE"]:
        d[c] = nem_time(d[c])
    d["status"] = d.OUTAGESTATUSCODE.str.upper().str.strip()
    known = set(d.OUTAGEID.astype(str))
    d = d[~d.RESUBMITOUTAGEID.astype(str).str.strip().isin(known)]
    d = d[~d.status.isin(EXCLUDE_STATUS) & d.STARTTIME.notna() & d.ENDTIME.notna() & (d.ENDTIME > d.STARTTIME)]
    d = d[(d.ENDTIME > as_of) & (d.STARTTIME <= as_of + horizon)].reset_index(drop=True)
    if d.empty:
        return pd.DataFrame()
    eq = _equipment()
    fb = eq.sort_values("VALIDFROM").drop_duplicates("ELEMENTID", keep="last").set_index("ELEMENTID")
    d["DESCRIPTION"] = d.ELEMENTID.map(fb.DESCRIPTION); d["VOLTAGE"] = d.ELEMENTID.map(fb.VOLTAGE)
    na = d.SUBSTATIONID.isin(["N/A", ""]) | d.EQUIPMENTTYPE.isin(["N/A", ""])
    described = d.DESCRIPTION.fillna("").str.strip().ne("")
    d["equipment_type_used"] = d.EQUIPMENTTYPE.where(~na, d.DESCRIPTION.fillna("").str.upper().map(infer_type))
    d["equipment_rank"] = d.equipment_type_used.map(TYPE_ORDER).fillna(5)
    d["asset"] = (d.SUBSTATIONID + "/" + d.EQUIPMENTTYPE + "/" + d.EQUIPMENTID).where(~na, "EL" + d.ELEMENTID.astype(str))
    d["asset_is_na"] = na & ~described
    prim = (d.assign(v=-d.VOLTAGE.fillna(0), n=d.asset_is_na.astype(int)).sort_values(["OUTAGEID", "n", "equipment_rank", "v"])
            .drop_duplicates("OUTAGEID"))
    agg = d.groupby("OUTAGEID").agg(start=("STARTTIME", "min"), end=("ENDTIME", "max"), status=("status", "first"),
                                    submitted=("SUBMITTEDDATE", "min"), n_assets=("ELEMENTID", "nunique")).reset_index()
    b = agg.merge(prim[["OUTAGEID", "asset", "SUBSTATIONID", "equipment_type_used", "DESCRIPTION", "VOLTAGE", "asset_is_na"]],
                  on="OUTAGEID", how="left")
    k = _keys().drop_duplicates("primary_asset").set_index("primary_asset")
    b["substation"] = b.SUBSTATIONID.where(~b.SUBSTATIONID.isin(["N/A", ""]) & b.SUBSTATIONID.notna(),
                                           b.asset.map(k.primary_substationid))
    area, label = area_of_substation()
    b["area_key"] = b.substation.map(area); b["area_label"] = b.substation.map(label)
    b["lead_days"] = (b.start - as_of).dt.total_seconds() / 86400
    ls = sets.copy()
    if len(ls):
        ls = ls[ls.OUTAGEID.isin(set(b.OUTAGEID))]
        linked = ls.groupby("OUTAGEID").GENCONSETID.apply(lambda s: sorted(set(s)))
    else:
        linked = pd.Series(dtype=object)
    b["linked_sets"] = b.OUTAGEID.map(linked).apply(lambda v: v if isinstance(v, list) else [])
    return b


# --------------------------------------------------------------------------- history as of
def history(as_of: pd.Timestamp) -> pd.DataFrame:
    """Past non-withdrawn episodes (ended before as_of) with keys and linked families."""
    eps = pd.read_parquet(DATA / "episodes.parquet")
    sets = pd.read_parquet(DATA / "episode_sets.parquet")
    eps = eps[(eps.end <= as_of) & ~eps.withdrawn & eps.n_sets.gt(0)]
    k = _keys()[["OUTAGEID", "primary_substationid", "area_key"]]
    h = eps[["OUTAGEID", "primary_asset", "primary_equipment_type_used"]].merge(k, on="OUTAGEID", how="left")
    fams = sets[sets.OUTAGEID.isin(set(h.OUTAGEID))].groupby("OUTAGEID").GENCONSETID.apply(lambda s: sorted(set(s)))
    h["families"] = h.OUTAGEID.map(fams)
    return h.dropna(subset=["families"])


def infer_families(b: pd.DataFrame, hist: pd.DataFrame, candidates: set) -> pd.DataFrame:
    """Q14: empirical family distribution by K1 asset, then K3 substation, then K4 area, same equipment type."""
    out = []
    by = {"K1": hist.groupby(["primary_asset", "primary_equipment_type_used"]),
          "K3": hist.groupby(["primary_substationid", "primary_equipment_type_used"]),
          "K4": hist.groupby(["area_key", "primary_equipment_type_used"])}
    groups = {lv: {k: g for k, g in grp} for lv, grp in by.items()}
    for r in b.itertuples():
        linked = [f for f in r.linked_sets if f in candidates]
        if linked:
            out += [{"OUTAGEID": r.OUTAGEID, "family": f, "family_source": "linked", "family_probability": 1.0,
                     "inference_level": "linked", "inference_episodes": np.nan} for f in linked]
            continue
        for lv, key in [("K1", (r.asset, r.equipment_type_used)), ("K3", (r.substation, r.equipment_type_used)),
                        ("K4", (r.area_key, r.equipment_type_used))]:
            if any(pd.isna(x) for x in key) or key not in groups[lv]:
                continue
            g = groups[lv][key]
            if len(g) < MIN_INFER_EPISODES:
                continue
            counts = pd.Series([f for fs in g.families for f in fs if f in candidates]).value_counts()
            if counts.empty:
                continue
            for f, n in counts.head(3).items():
                out.append({"OUTAGEID": r.OUTAGEID, "family": f, "family_source": "inferred", "family_probability": n / len(g),
                            "inference_level": lv, "inference_episodes": len(g)})
            break
    return pd.DataFrame(out)


def relevance_asof(as_of: pd.Timestamp) -> pd.DataFrame:
    """v1 relevance rule on pre-as_of data (METHODOLOGY 3.3): not '#', >= 12 leading intervals, invoked <= 95% of time."""
    lead = pd.read_parquet(DATA / "leading_5min.parquet", columns=["time", "direction", "GENCONSETID", "ic"])
    lead = lead[lead.time <= as_of]
    counts = lead.groupby(["ic", "GENCONSETID", "direction"]).size().unstack(fill_value=0)
    cov = pd.read_parquet(DATA / "family_coverage_30min.parquet")
    cov = cov[cov.index <= as_of]
    share = (cov.sum() / (6 * max(len(cov), 1))).to_dict()
    rows = []
    for (ic, fam), r in counts.iterrows():
        ok = (not fam.startswith("#")) and max(r.get("forward", 0), r.get("reverse", 0)) >= 12 and share.get(fam, 1.0) <= 0.95
        rows.append({"ic": ic, "GENCONSETID": fam, "relevant": ok})
    return pd.DataFrame(rows)


def booking_reliability_asof(as_of: pd.Timestamp) -> pd.DataFrame:
    eps = pd.read_parquet(DATA / "episodes.parquet")
    sets = pd.read_parquet(DATA / "episode_sets.parquet")
    e = sets.merge(eps, on="OUTAGEID")
    e = e[e.end <= as_of]
    act = e.actual_end.notna() & ~e.withdrawn
    e["early"] = np.where(act, e.actual_end < e.scheduled_end - pd.Timedelta(hours=1), np.nan)
    return (e.drop_duplicates(["GENCONSETID", "OUTAGEID"]).groupby("GENCONSETID")
            .agg(bookings=("OUTAGEID", "nunique"), withdrawal_rate=("withdrawn", "mean"), early_return_rate=("early", "mean"))
            .reset_index())


# --------------------------------------------------------------------------- evidence as of
def capacity_arrays() -> dict:
    """Directional capacity and completeness on GRID30 per connector-direction (from the v1 regime panel), cached."""
    path = BDATA / "capacity_30min.parquet"
    if not path.exists():
        panel = compare.regime_panel()
        frames = []
        for (ic, d), g in panel.groupby(["ic", "direction"]):
            g = g.set_index("time").reindex(GRID30)
            frames.append(pd.DataFrame({"time": GRID30, "ic": ic, "direction": d, "capacity": g.capacity.to_numpy(float),
                                        "complete": g.complete.fillna(False).astype(bool).to_numpy()}))
        write_parquet(path, pd.concat(frames, ignore_index=True))
    c = pd.read_parquet(path)
    return {(ic, d): (g.capacity.to_numpy(float), g.complete.to_numpy(bool)) for (ic, d), g in c.groupby(["ic", "direction"])}


def pair_effects(pairs: pd.DataFrame, cap: np.ndarray) -> pd.DataFrame:
    """Per treated unit: capacity minus the median of its controls (v1 d_capacity)."""
    t = GRID30.get_indexer(pairs.t_time); c = GRID30.get_indexer(pairs.c_time)
    f = pd.DataFrame({"t": t, "cv": cap[c]})
    med = f.groupby("t").cv.median()
    return pd.DataFrame({"t": med.index, "d": cap[med.index.to_numpy()] - med.to_numpy()})


class Evidence:
    """Per connector: layers, embargoed pairs and units, and family-level as-of statistics."""

    def __init__(self, ic: str, layers: dict[str, Layer], members: pd.DataFrame, outage_members: set, links: pd.DataFrame,
                 capacity: dict | None = None):
        self.ic = ic
        self.capacity = capacity or {}
        self.layers = layers
        self.pairs = pd.read_parquet(BDATA / f"pairs__{ic}.parquet", columns=["level", "key", "direction", "kind", "t_time", "c_time"])
        self.pairs = self.pairs[self.pairs.level.eq("K2")]
        self.units = pd.read_parquet(DATA / "tables" / f"units__{ic}.parquet",
                                     columns=["time", "direction", "GENCONSETID", "matched", "d_capacity", "nem_date", "season", "day_period"])
        self.own_of = members.groupby("GENCONSETID").GENCONID.apply(set).to_dict()
        self.outage_members = outage_members
        self.links = links
        self.cache: dict = {}

    def family(self, fam: str, direction: str, as_of: pd.Timestamp, since: pd.Timestamp | None = None) -> dict | None:
        key = (fam, direction, as_of, since)
        if key in self.cache:
            return self.cache[key]
        cut = as_of - EMBARGO
        u = self.units[(self.units.GENCONSETID == fam) & (self.units.direction == direction) & (self.units.time <= cut)]
        if since is not None:
            u = u[u.time > since]
        p = self.pairs[(self.pairs.key == fam) & (self.pairs.direction == direction) & (self.pairs.t_time <= cut)]
        if since is not None:
            p = p[p.t_time > since]
        pa, pp = p[p.kind.eq("actual")], p[p.kind.eq("placebo")]
        m = u[u.matched]
        if len(u) == 0 or len(pa) == 0:
            self.cache[key] = None
            return None
        days = m.nem_date.to_numpy().astype("datetime64[D]").astype(np.int64)
        lo, hi = compare.boot_ci(m.d_capacity.to_numpy(float), days) if len(m) >= 2 else (np.nan, np.nan)
        out = {"n_treated": len(u), "n_matched": len(m), "match_rate": len(m) / len(u), "treated_hours": len(u) / 2,
               "effect_capacity": float(m.d_capacity.median()) if len(m) else np.nan, "ci_lo_capacity": lo, "ci_hi_capacity": hi,
               "episodes": compare.episodes_touching(self.links, fam, pd.DatetimeIndex(u.time))}
        own = self.own_of.get(fam, set())
        for lname, layer in self.layers.items():
            own_mask = layer.codes.isin(own)
            classes = classify(layer.codes, own, self.outage_members)
            row, top, unit = family_stats(layer, direction, pa, own_mask, classes, top_k=5)
            out[f"{lname}_own_t"], out[f"{lname}_own_c"] = row["own_treated"], row["own_control"]
            top = top.sort_values("treated_share", ascending=False).head(5) if len(top) else top
            out[f"{lname}_top"] = top[["constraint", "treated_share", "control_share", "diff_pp", "class"]].to_dict("records") if len(top) else []
            if len(unit):
                uv = u[["time", "season", "day_period"]].merge(unit, on="time")
                out[f"{lname}_own_by_cell"] = uv.groupby(["season", "day_period"]).agg(n=("t_own", "size"), t=("t_own", "mean")).reset_index().to_dict("records")
            if len(pp):
                prow, _, _ = family_stats(layer, direction, pp, own_mask, classes, top_k=1)
                out[f"{lname}_placebo_own_diff"] = prow["own_diff"]
        # v1 placebo gate: +-7-day shifted windows, capacity effect CI must contain zero (compare.run_effect)
        cap = self.capacity.get((self.ic, direction))
        if cap is not None and len(pp):
            pe = pair_effects(pp, cap[0])
            pdays = (GRID30[pe.t.to_numpy()] - pd.Timedelta(minutes=1)).floor("D").to_numpy().astype("datetime64[D]").astype(np.int64)  # v1 nem_date
            plo, phi = compare.boot_ci(pe.d.to_numpy(float), pdays) if len(pe) >= 2 else (np.nan, np.nan)
            out["placebo_clean"] = bool(len(pe) >= 2 and plo <= 0 <= phi)
        else:
            out["placebo_clean"] = False
        out["tier"] = compare.tier(out)
        self.cache[key] = out
        return out


def normal_rate(layer: Layer, direction: str, code: int, as_of: pd.Timestamp) -> pd.Series:
    """Baseline (i): equation share by season x half-hour over all pre-as_of half-hours."""
    col = np.asarray(layer.H[direction][:, code].todense()).ravel()
    ok = (GRID30 <= as_of) & (layer.avail[direction] > 0)
    t = GRID30[ok]
    hh = ((t - pd.Timedelta(minutes=30)).hour * 2 + (t - pd.Timedelta(minutes=30)).minute // 30)
    season = pd.Index([SEASON[m] for m in (t - pd.Timedelta(minutes=30)).month])
    return pd.Series(col[ok]).groupby([season, hh]).mean()


def window_index(start: pd.Timestamp, end: pd.Timestamp) -> np.ndarray:
    i0 = GRID30.searchsorted(start + pd.Timedelta(minutes=25), side="left")
    i1 = GRID30.searchsorted(end, side="right")
    return np.arange(i0, i1)


_RR = None


def _rr():
    global _RR
    if _RR is None:
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_all_ic_regime_report as rr  # noqa: E402
        _RR = rr
    return _RR


def cell_weights(idx: np.ndarray) -> pd.Series:
    t = GRID30[idx] - pd.Timedelta(minutes=30)
    season = [SEASON[m] for m in t.month]
    period = _rr().daily_period(pd.Series(GRID30[idx]))
    return pd.Series(1.0, index=pd.MultiIndex.from_arrays([season, list(period)])).groupby(level=[0, 1]).sum() / max(len(idx), 1)


# --------------------------------------------------------------------------- outlook rows
def build_outlook(as_of: pd.Timestamp, detail: pd.DataFrame, sets: pd.DataFrame, evidence: dict[str, Evidence],
                  meta: dict, horizon: pd.Timedelta = HORIZON, future: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    b = bookings(detail, sets, as_of, horizon)
    if b.empty:
        return pd.DataFrame(), b
    if future:
        b = b[b.start > as_of]
    rel = relevance_asof(as_of)
    relevant = rel[rel.relevant]
    rel_by_fam = relevant.groupby("GENCONSETID").ic.apply(set).to_dict()
    hist = history(as_of)
    cand = infer_families(b, hist, set(rel_by_fam))
    if cand.empty:
        return pd.DataFrame(), b
    rb = booking_reliability_asof(as_of).set_index("GENCONSETID")
    latest_members = members_asof(as_of)
    rows = []
    bmap = b.set_index("OUTAGEID")
    for c in cand.itertuples():
        bk = bmap.loc[c.OUTAGEID]
        idx = window_index(bk.start, bk.end)
        wts = cell_weights(idx) if len(idx) else pd.Series(dtype=float)
        wr = rb.withdrawal_rate.get(c.family, np.nan)
        er = rb.early_return_rate.get(c.family, np.nan)
        q = c.family_probability * (1 - (wr if np.isfinite(wr) else 0.0))
        for ic in sorted(rel_by_fam.get(c.family, set()) & set(evidence)):
            for direction in DIRECTIONS:
                ev = evidence[ic].family(c.family, direction, as_of)
                base = {"snapshot_id": meta.get("report_member"), "snapshot_published": meta.get("generated_nem"),
                        "snapshot_sha256": meta.get("week_raw_sha256"), "as_of": as_of, "OUTAGEID": c.OUTAGEID,
                        "asset": bk.asset, "equipment_type": bk.equipment_type_used, "description": bk.DESCRIPTION,
                        "substation": bk.substation, "area": bk.area_label, "area_key": bk.area_key,
                        "booked_start": bk.start, "booked_end": bk.end, "lead_days": bk.lead_days, "booking_status": bk.status,
                        "family": c.family, "family_source": c.family_source, "family_probability": c.family_probability,
                        "inference_level": c.inference_level, "ic": ic, "name": IC[ic]["name"], "direction": direction,
                        "withdrawal_rate": wr, "early_return_rate": er, "occurrence_weight": q, "window_half_hours": len(idx)}
                if ev is None:
                    rows.append({**base, "tier": "no_history"})
                    continue
                keep = latest_members.get(c.family)
                r = {**base, "tier": ev["tier"], "evidence_episodes": ev["episodes"], "evidence_hours": ev["treated_hours"],
                     "limit_change_mw": ev["effect_capacity"], "limit_change_ci_lo": ev["ci_lo_capacity"],
                     "limit_change_ci_hi": ev["ci_hi_capacity"], "expected_limit_change_mw": q * ev["effect_capacity"]}
                for lname in ["binding", "setter"]:
                    if f"{lname}_top" not in ev:
                        continue
                    tops = [t for t in ev[f"{lname}_top"] if keep is None or t["class"] != "own_set" or t["constraint"] in keep]
                    retired = [t["constraint"] for t in ev[f"{lname}_top"] if t not in tops]
                    for i, t in enumerate(tops[:3], 1):
                        r[f"{lname}_eq_{i}"] = t["constraint"]
                        r[f"{lname}_freq_{i}"] = t["treated_share"]
                        r[f"{lname}_normal_{i}"] = t["control_share"]
                        r[f"{lname}_lift_pp_{i}"] = t["diff_pp"]
                        r[f"{lname}_p_{i}"] = q * t["treated_share"] + (1 - q) * t["control_share"]
                    r[f"{lname}_own_rate"] = ev[f"{lname}_own_t"]
                    r[f"{lname}_own_normal"] = ev[f"{lname}_own_c"]
                    cells = pd.DataFrame(ev.get(f"{lname}_own_by_cell", []))
                    if len(cells) and len(wts):
                        cm = cells[cells.n >= 20].set_index(["season", "day_period"]).t
                        w = wts[wts.index.isin(cm.index)]
                        adj = float((w * cm.reindex(w.index)).sum() / w.sum()) if w.sum() > 0 else np.nan
                        r[f"{lname}_own_rate_timing"] = adj if np.isfinite(adj) else ev[f"{lname}_own_t"]
                    if retired:
                        r[f"{lname}_retired_excluded"] = "|".join(retired)
                rows.append(r)
    out = pd.DataFrame(rows)
    if len(out):
        out = add_overlaps(out, as_of, evidence)
        out = add_network_flags(out, as_of)
    return out, b


def members_asof(as_of: pd.Timestamp) -> dict:
    """Latest GENCONSET version effective at or before as_of: equations still in each set (Q23 retirement)."""
    g = standing("GENCONSET").copy()
    g["EFFECTIVEDATE"] = pd.to_datetime(g.EFFECTIVEDATE, errors="coerce")
    g["VERSIONNO"] = pd.to_numeric(g.VERSIONNO, errors="coerce")
    g = g[g.EFFECTIVEDATE <= as_of]
    last = g.sort_values(["EFFECTIVEDATE", "VERSIONNO"]).groupby("GENCONSETID")[["EFFECTIVEDATE", "VERSIONNO"]].last().reset_index()
    cur = g.merge(last, on=["GENCONSETID", "EFFECTIVEDATE", "VERSIONNO"])
    return cur.groupby("GENCONSETID").GENCONID.apply(set).to_dict()


def add_overlaps(out: pd.DataFrame, as_of: pd.Timestamp | None = None, evidence: dict | None = None) -> pd.DataFrame:
    """Q17: flag bookings that overlap another booking on the same connector-direction and, where the two most likely
    families were invoked together for at least 48 half-hours before the embargo, give their joint historical own-set
    binding share (union of both sets; share of intervals with any member binding)."""
    ids = []
    cov = pd.read_parquet(DATA / "family_coverage_30min.parquet") if evidence is not None else None
    joint_cache: dict = {}
    top = out.sort_values("family_probability", ascending=False).drop_duplicates(["OUTAGEID", "ic", "direction"])
    fam_of = top.set_index(["OUTAGEID", "ic", "direction"]).family.to_dict()
    for (ic, d), g in top.groupby(["ic", "direction"]):
        g = g[["OUTAGEID", "booked_start", "booked_end"]].sort_values("booked_start")
        s, e, o = g.booked_start.to_numpy(), g.booked_end.to_numpy(), g.OUTAGEID.to_numpy()
        for i in range(len(g)):
            ov = o[(s < e[i]) & (e > s[i]) & (o != o[i])]
            row = {"ic": ic, "direction": d, "OUTAGEID": o[i], "overlap_ids": "|".join(map(str, ov[:20])), "overlap_count": len(ov),
                   "overlap_joint": False}
            if len(ov) and cov is not None and ic in evidence and "binding" in evidence[ic].layers:
                fa = fam_of[(o[i], ic, d)]
                best = None
                for other in ov[:20]:
                    fb = fam_of.get((other, ic, d))
                    if fb is None or fb == fa or fa not in cov or fb not in cov:
                        continue
                    key = (ic, d, *sorted([fa, fb]), as_of)
                    if key not in joint_cache:
                        c = cov[cov.index <= as_of - EMBARGO]
                        idx = np.flatnonzero(((c[fa] == 6) & (c[fb] == 6)).to_numpy())
                        layer = evidence[ic].layers["binding"]
                        own = layer.codes.isin(evidence[ic].own_of.get(fa, set()) | evidence[ic].own_of.get(fb, set()))
                        share = float(layer.own_share(d, own)[GRID30.get_indexer(c.index[idx])].mean()) if len(idx) >= 48 else np.nan
                        joint_cache[key] = (len(idx), share)
                    n, share = joint_cache[key]
                    if n >= 48 and (best is None or share > best[2]):
                        best = (other, n, share)
                if best:
                    row.update(overlap_joint=True, overlap_joint_with=str(best[0]), overlap_joint_half_hours=best[1],
                               overlap_joint_own_binding=best[2])
            ids.append(row)
    return out.merge(pd.DataFrame(ids), on=["ic", "direction", "OUTAGEID"], how="left")


def add_network_flags(out: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Q23: flag rows whose named equations are new to the history (first seen in the 180 days before as_of) or were
    re-versioned in the 30 days before as_of, i.e. after nearly all of the embargoed evidence."""
    first, rever = equation_versions()
    new = set(first[(first > as_of - pd.Timedelta(days=180)) & (first <= as_of)].index)
    changed = set(rever[(rever.first_seen > as_of - pd.Timedelta(days=30)) & (rever.first_seen <= as_of)].CONSTRAINTID) if len(rever) else set()
    eqcols = [c for c in out.columns if re.match(r"(binding|setter)_eq_\d", c)]
    isnew = out[eqcols].isin(new).any(axis=1) if eqcols else False
    ischg = out[eqcols].isin(changed).any(axis=1) if eqcols else False
    out["network_change_flag"] = np.where(isnew, "new equation", np.where(ischg, "re-versioned in last 30 days", ""))
    return out


_VERS: tuple | None = None


def equation_versions() -> tuple:
    """First appearance of each equation in dispatch (presence files, all scope equations) and the first binding or
    near-binding interval of each later version (binding panel)."""
    global _VERS
    if _VERS is None:
        from .binding import PANEL
        pres = [pd.read_parquet(p, columns=["CONSTRAINTID", "first"]) for p in sorted(PANEL.glob("presence__*.parquet"))]
        first = pd.concat(pres).groupby("CONSTRAINTID")["first"].min() if pres else pd.Series(dtype="datetime64[ns]")
        parts = [pd.read_parquet(p, columns=["time", "CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"]) for p in sorted(PANEL.glob("20*.parquet"))]
        if parts:
            v = pd.concat(parts)
            v = v.groupby(["CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"]).time.min().rename("first_seen").reset_index()
            first_version = v.groupby("CONSTRAINTID").first_seen.transform("min")
            rever = v[v.first_seen > first_version]          # re-versions only (not the first appearance in the window)
        else:
            rever = pd.DataFrame(columns=["CONSTRAINTID", "first_seen"])
        first = first[first > pd.Timestamp("2024-09-08")]  # present from the window start: not "new"
        _VERS = (first, rever)
    return _VERS


def weekly(out: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    if out.empty:
        return out
    o = out.copy()
    o["week"] = o.booked_start.dt.to_period("W-SUN").dt.start_time
    g = o.groupby(["week", "ic", "name", "direction"])
    w = g.agg(outages=("OUTAGEID", "nunique"), supported_rows=("tier", lambda s: (s == "supported").sum()),
              largest_reduction_mw=("limit_change_mw", "min"), overlap_max=("overlap_count", "max")).reset_index()
    top = (o.dropna(subset=["binding_eq_1"]).sort_values("binding_p_1", ascending=False).groupby(["week", "ic", "direction"])
           .head(1)[["week", "ic", "direction", "binding_eq_1", "binding_p_1"]])
    return w.merge(top.rename(columns={"binding_eq_1": "top_binding_eq", "binding_p_1": "top_binding_p"}), on=["week", "ic", "direction"], how="left")


# --------------------------------------------------------------------------- backtest (Q16, Q21, Q22, Q28)
def origins() -> pd.DataFrame:
    """First weekly NOS file dated in each month of year 2 (2025-09 .. 2026-08)."""
    w = week_dirs()
    w = w[(w.date >= pd.Timestamp("2025-09-01")) & (w.date < pd.Timestamp("2026-09-01"))]
    return w.assign(month=w.date.dt.to_period("M")).groupby("month").head(1).reset_index(drop=True)


def successor_map() -> dict:
    raw = sorted((DATA / "raw" / "mmsdm").glob("NETWORK_OUTAGEDETAIL_*.parquet"))[-1]
    d = pd.read_parquet(raw, columns=["OUTAGEID", "RESUBMITOUTAGEID"]).drop_duplicates()
    d["OUTAGEID"] = d.OUTAGEID.astype(str)
    d["RESUBMITOUTAGEID"] = d.RESUBMITOUTAGEID.astype(str).str.strip()
    known = set(d.OUTAGEID)
    d = d[d.RESUBMITOUTAGEID.isin(known) & d.RESUBMITOUTAGEID.ne(d.OUTAGEID)]
    return dict(zip(d.OUTAGEID, d.RESUBMITOUTAGEID))


def final_id(o: str, succ: dict) -> str:
    seen = set()
    while o in succ and o not in seen:
        seen.add(o)
        o = succ[o]
    return o


def lead_band(days: float) -> str | None:
    if not np.isfinite(days) or days < 0:
        return None
    d = int(np.ceil(days))
    for lo, hi, lab in LEAD_BANDS:
        if (lo <= d <= hi) or (lab == "0-7" and d <= 7):
            return lab
    return None


def score_origin(pred: pd.DataFrame, as_of: pd.Timestamp, evidence: dict, succ: dict,
                 eps: pd.DataFrame, fam_final: pd.Series, normal_cache: dict) -> pd.DataFrame:
    """Long table: one row per (booking, family, connector-direction, layer, equation rank) with prediction and truth."""
    rows = []
    epi = eps.assign(OUTAGEID=eps.OUTAGEID.astype(str)).drop_duplicates("OUTAGEID").set_index("OUTAGEID")
    for r in pred.itertuples():
        if r.tier == "no_history":
            continue
        fid = final_id(str(r.OUTAGEID), succ)
        if fid not in epi.index:
            continue
        ep = epi.loc[fid]
        occurred = not bool(ep.withdrawn)
        start, end = (ep.start, ep.end) if occurred else (r.booked_start, r.booked_end)
        if end > END or start < START:
            continue
        idx = window_index(start, end)
        if len(idx) == 0:
            continue
        ev = evidence[r.ic]
        final_sets = fam_final.get(fid, [])
        ly = ev.family(r.family, r.direction, as_of, since=as_of - HORIZON)
        base = {"as_of": as_of, "OUTAGEID": r.OUTAGEID, "final_id": fid, "family": r.family, "family_source": r.family_source,
                "family_probability": r.family_probability, "family_realised": r.family in final_sets, "occurred": occurred,
                "ic": r.ic, "name": r.name, "direction": r.direction, "lead_days": r.lead_days, "lead_band": lead_band(r.lead_days),
                "tier": r.tier, "q": r.occurrence_weight}
        u = ev.units[(ev.units.GENCONSETID == r.family) & (ev.units.direction == r.direction) & ev.units.matched
                     & ev.units.time.isin(GRID30[idx])]
        base["mw_pred"] = getattr(r, "limit_change_mw", np.nan)
        base["mw_realised"] = float(u.d_capacity.median()) if len(u) else np.nan
        base["mw_lastyear"] = ly["effect_capacity"] if ly else np.nan
        for lname in ["binding", "setter"]:
            layer = ev.layers.get(lname)
            if layer is None:
                continue
            H = layer.H[r.direction]
            ok = layer.avail[r.direction][idx] > 0
            if not ok.any():
                continue
            ly_top = {t["constraint"]: t for t in (ly or {}).get(f"{lname}_top", [])}
            t = GRID30[idx[ok]] - pd.Timedelta(minutes=30)
            cells = pd.MultiIndex.from_arrays([[SEASON[m] for m in t.month], t.hour * 2 + t.minute // 30])
            for i in (1, 2, 3):
                eq = getattr(r, f"{lname}_eq_{i}", None)
                if not isinstance(eq, str) or eq not in layer.codes:
                    continue
                code = layer.codes.get_loc(eq)
                y = float(np.asarray(H[idx[ok], code].todense()).ravel().mean())
                key = (r.ic, lname, r.direction, code, as_of)
                if key not in normal_cache:
                    normal_cache[key] = normal_rate(layer, r.direction, code, as_of)
                nr = normal_cache[key]
                b1 = float(nr.reindex(cells).fillna(nr.mean() if len(nr) else 0.0).mean())
                q = r.occurrence_weight
                b2 = (q * ly_top[eq]["treated_share"] + (1 - q) * ly_top[eq]["control_share"]) if eq in ly_top else b1
                rows.append({**base, "layer": lname, "rank": i, "equation": eq, "p_outlook": getattr(r, f"{lname}_p_{i}"),
                             "p_normal": b1, "p_lastyear": b2, "y": y, "event": y >= EVENT_SHARE})
    return pd.DataFrame(rows)


def skill_tables(sc: pd.DataFrame, fit_origins: int = 6) -> dict:
    if sc.empty:
        return {}
    sc = sc[sc.tier.isin(["supported", "indicative"])].copy()      # the rows the outlook displays
    for k in ["outlook", "normal", "lastyear"]:
        sc[f"se_{k}"] = (sc[f"p_{k}"] - sc.y) ** 2
    ords = sorted(sc.as_of.unique())
    fit, test = set(ords[:fit_origins]), set(ords[fit_origins:])
    taus = {}
    for lname, g in sc[sc.as_of.isin(fit)].groupby("layer"):
        best = (0.5, -1.0)
        for tau in np.round(np.arange(0.01, 0.6, 0.01), 2):
            a = g.p_outlook >= tau
            tp = int((a & g.event).sum()); fp = int((a & ~g.event).sum()); fn = int((~a & g.event).sum())
            f1 = 2 * tp / max(2 * tp + fp + fn, 1)
            if f1 > best[1]:
                best = (float(tau), f1)
        taus[lname] = best[0]
    cells = []
    for (lname, band, name, d), g in sc.groupby(["layer", "lead_band", "name", "direction"]):
        te = g[g.as_of.isin(test)]
        a = te.p_outlook >= taus.get(lname, 0.5)
        bn, bo, bl = g.se_normal.mean(), g.se_outlook.mean(), g.se_lastyear.mean()
        row = {"layer": lname, "lead_band": band, "name": name, "direction": d, "rows": len(g), "bookings": g.OUTAGEID.nunique(),
               "origins": g.as_of.nunique(), "brier_outlook": bo, "brier_normal": bn, "brier_lastyear": bl,
               "skill_vs_normal": 1 - bo / bn if bn > 0 else np.nan, "skill_vs_lastyear": 1 - bo / bl if bl > 0 else np.nan,
               "events": int(g.event.sum()), "test_rows": len(te), "test_events": int(te.event.sum()),
               "alert_threshold": taus.get(lname),
               "recall": float((a & te.event).sum() / te.event.sum()) if len(te) and te.event.sum() else np.nan,
               "precision": float((a & te.event).sum() / a.sum()) if len(te) and a.sum() else np.nan,
               "false_alerts": int((a & ~te.event).sum())}
        row["skilful"] = bool(row["rows"] >= 30 and bo < bn)
        cells.append(row)
    cells = pd.DataFrame(cells)
    rel = sc.assign(bin=pd.cut(sc.p_outlook, [0, .02, .05, .1, .2, .3, .5, .7, 1.0], include_lowest=True))
    reliability = rel.groupby(["layer", "bin"], observed=True).agg(n=("y", "size"), p_mean=("p_outlook", "mean"),
                                                                   y_mean=("y", "mean")).reset_index()
    reliability["bin"] = reliability["bin"].astype(str)
    mw = sc.drop_duplicates(["as_of", "OUTAGEID", "family", "ic", "direction"]).dropna(subset=["mw_realised", "mw_pred"])
    mwt = (mw.assign(ae_outlook=(mw.mw_pred - mw.mw_realised).abs(), ae_zero=mw.mw_realised.abs(),
                     ae_lastyear=(mw.mw_lastyear - mw.mw_realised).abs())
           .groupby(["lead_band", "name", "direction"]).agg(n=("ae_outlook", "size"), mae_outlook=("ae_outlook", "mean"),
                                                             mae_zero_change=("ae_zero", "mean"),
                                                             mae_lastyear=("ae_lastyear", "mean")).reset_index())
    inf = sc.drop_duplicates(["as_of", "OUTAGEID", "family"])
    inf = inf[inf.family_source.eq("inferred")]
    top1 = inf.sort_values("family_probability", ascending=False).drop_duplicates(["as_of", "OUTAGEID"])
    has_sets = set(pd.read_parquet(DATA / "episode_sets.parquet").OUTAGEID.astype(str))
    g = inf[inf.final_id.astype(str).isin(has_sets)]
    t1g = g.sort_values("family_probability", ascending=False).drop_duplicates(["as_of", "OUTAGEID"])
    fam_acc = pd.DataFrame([{"inferred_bookings": int(inf[["as_of", "OUTAGEID"]].drop_duplicates().shape[0]),
                             "top1_accuracy": float(top1.family_realised.mean()) if len(top1) else np.nan,
                             "top3_accuracy": float(inf.groupby(["as_of", "OUTAGEID"]).family_realised.any().mean()) if len(inf) else np.nan,
                             "bookings_with_any_final_set": int(g[["as_of", "OUTAGEID"]].drop_duplicates().shape[0]),
                             "top1_accuracy_given_set": float(t1g.family_realised.mean()) if len(t1g) else np.nan,
                             "top3_accuracy_given_set": float(g.groupby(["as_of", "OUTAGEID"]).family_realised.any().mean()) if len(g) else np.nan}])
    return {"cells": cells, "reliability": reliability, "mw": mwt, "family_inference": fam_acc,
            "thresholds": pd.DataFrame([{"layer": k, "alert_threshold": v} for k, v in taus.items()])}


def load_evidence(ics=None) -> dict:
    from .binding import binding_layer
    from .setters import setter_layer
    ics = ics or list(IC)
    members, outage_members = membership()
    all_rel = sorted(set(pd.read_parquet(DATA / "set_relevance.parquet").query("relevant").GENCONSETID))
    _, links = compare.spell_linkage(all_rel)
    cap = capacity_arrays()
    ev = {}
    for ic in ics:
        layers = {"setter": setter_layer(ic)}
        try:
            layers["binding"] = binding_layer(ic)
        except FileNotFoundError:
            pass
        ev[ic] = Evidence(ic, layers, members, outage_members, links, cap)
    return ev


def backtest(ics=None, only: list[int] | None = None) -> dict:
    """Score every origin (or the ``only`` indices, for parallel workers), then combine all per-origin files."""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "origins").mkdir(exist_ok=True)
    if only is not None:
        evidence = load_evidence(ics)
        succ = successor_map()
        eps = pd.read_parquet(DATA / "episodes.parquet")
        fam_final = pd.read_parquet(DATA / "episode_sets.parquet").assign(OUTAGEID=lambda d: d.OUTAGEID.astype(str))             .groupby("OUTAGEID").GENCONSETID.apply(lambda s: sorted(set(s)))
        ors = origins()
        for i in only:
            o = ors.iloc[i]
            as_of, member, detail, sets, meta = snapshot(o.path)
            pred, b = build_outlook(as_of, detail, sets, evidence, meta)
            sc = score_origin(pred, as_of, evidence, succ, eps, fam_final, {}) if len(pred) else pd.DataFrame()
            m = {**meta, "as_of": str(as_of), "bookings": len(b), "prediction_rows": len(pred), "scored_rows": len(sc)}
            write_parquet(OUT / "origins" / f"pred_{i:02d}.parquet", pred.assign(origin=str(as_of)))
            write_parquet(OUT / "origins" / f"scored_{i:02d}.parquet", sc if len(sc) else pd.DataFrame({"empty": []}))
            write_json(OUT / "origins" / f"meta_{i:02d}.json", m)
            print(json.dumps(m, default=str), flush=True)
        return {"origins_done": list(only)}
    return combine_backtest()


def combine_backtest() -> dict:
    n = len(origins())
    missing = [i for i in range(n) if not (OUT / "origins" / f"meta_{i:02d}.json").exists()]
    if missing:
        raise RuntimeError(f"origins not scored yet: {missing}")
    meta_rows = [json.loads((OUT / "origins" / f"meta_{i:02d}.json").read_text()) for i in range(n)]
    pred = pd.concat([pd.read_parquet(OUT / "origins" / f"pred_{i:02d}.parquet") for i in range(n)], ignore_index=True)
    parts = [pd.read_parquet(OUT / "origins" / f"scored_{i:02d}.parquet") for i in range(n)]
    sc = pd.concat([p for p in parts if "empty" not in p.columns], ignore_index=True)
    write_parquet(OUT / "backtest_predictions.parquet", pred)
    write_parquet(OUT / "backtest_scored.parquet", sc)
    tabs = skill_tables(sc)
    for k, v in tabs.items():
        write_parquet(OUT / f"backtest_{k}.parquet", v)
    write_json(OUT / "backtest_meta.json", meta_rows)
    cells = tabs.get("cells", pd.DataFrame())
    return {"origins": len(meta_rows), "prediction_rows": len(pred), "scored_rows": len(sc),
            "skilful_cells": int(cells.skilful.sum()) if len(cells) else 0, "cells": len(cells),
            "family_inference": tabs.get("family_inference", pd.DataFrame()).to_dict("records")}


def _backtest_sequential_unused(ics=None) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    evidence = load_evidence(ics)
    succ = successor_map()
    eps = pd.read_parquet(DATA / "episodes.parquet")
    fam_final = pd.read_parquet(DATA / "episode_sets.parquet").assign(OUTAGEID=lambda d: d.OUTAGEID.astype(str)) \
        .groupby("OUTAGEID").GENCONSETID.apply(lambda s: sorted(set(s)))
    normal_cache: dict = {}
    scored, preds, meta_rows = [], [], []
    for o in origins().itertuples():
        as_of, member, detail, sets, meta = snapshot(o.path)
        pred, b = build_outlook(as_of, detail, sets, evidence, meta)
        sc = score_origin(pred, as_of, evidence, succ, eps, fam_final, normal_cache) if len(pred) else pd.DataFrame()
        meta_rows.append({**meta, "as_of": str(as_of), "bookings": len(b), "prediction_rows": len(pred), "scored_rows": len(sc)})
        print(json.dumps(meta_rows[-1], default=str), flush=True)
        preds.append(pred.assign(origin=str(as_of)))
        scored.append(sc)
    pred = pd.concat(preds, ignore_index=True)
    sc = pd.concat(scored, ignore_index=True)
    write_parquet(OUT / "backtest_predictions.parquet", pred)
    write_parquet(OUT / "backtest_scored.parquet", sc)
    tabs = skill_tables(sc)
    for k, v in tabs.items():
        write_parquet(OUT / f"backtest_{k}.parquet", v)
    write_json(OUT / "backtest_meta.json", meta_rows)
    cells = tabs.get("cells", pd.DataFrame())
    return {"origins": len(meta_rows), "prediction_rows": len(pred), "scored_rows": len(sc),
            "skilful_cells": int(cells.skilful.sum()) if len(cells) else 0, "cells": len(cells),
            "family_inference": tabs.get("family_inference", pd.DataFrame()).to_dict("records")}


def confirm_embargo(which=(1, -2), ics=None) -> dict:
    """Q28: full v1 comparison re-run with data cut at two origins vs the embargoed full-window estimates."""
    ics = ics or list(IC)
    ors = origins()
    panel = compare.regime_panel()
    coverage = pd.read_parquet(DATA / "family_coverage_30min.parquet")
    lead30 = pd.read_parquet(DATA / "family_leading_30min.parquet")
    cap = capacity_arrays()
    evidence = {ic: Evidence(ic, {}, set_members(), set(), None, cap) for ic in ics}
    out = []
    for i in which:
        o = ors.iloc[i]
        as_of = snapshot(o.path)[0]
        cut = as_of - EMBARGO
        rel = relevance_asof(as_of)
        all_rel = sorted(set(rel.loc[rel.relevant, "GENCONSETID"]) & set(coverage.columns))
        rel = rel[rel.GENCONSETID.isin(all_rel) | ~rel.relevant]
        masks, links = compare.spell_linkage(all_rel)
        cov = coverage.copy()
        cov.loc[cov.index > as_of] = -1
        compare.FAST = True
        try:
            for ic in ics:
                evidence[ic].links = links
                r = compare.run_connector(ic, panel, cov, rel, lead30, masks, links, all_rel)
                units = r["units"]
                if units.empty:
                    continue
                units = units[units.time <= cut]
                for (fam, d), g in units.groupby(["GENCONSETID", "direction"]):
                    m = g[g.matched]
                    e = evidence[ic].family(fam, d, as_of)
                    if e is None or e["tier"] != "supported" or len(m) < 2:
                        continue
                    days = m.nem_date.to_numpy().astype("datetime64[D]").astype(np.int64)
                    lo, hi = compare.boot_ci(m.d_capacity.to_numpy(float), days)
                    rerun = float(m.d_capacity.median())
                    out.append({"as_of": as_of, "ic": ic, "direction": d, "GENCONSETID": fam, "embargo_effect": e["effect_capacity"],
                                "embargo_ci_lo": e["ci_lo_capacity"], "embargo_ci_hi": e["ci_hi_capacity"], "rerun_effect": rerun,
                                "rerun_ci_lo": lo, "rerun_ci_hi": hi, "rerun_units": len(m), "embargo_units": e["n_matched"],
                                "agree": bool((e["ci_lo_capacity"] <= rerun <= e["ci_hi_capacity"]) or (lo <= e["effect_capacity"] <= hi))})
        finally:
            compare.FAST = False
    res = pd.DataFrame(out)
    write_parquet(OUT / "embargo_confirmation.parquet", res)
    return {"families": len(res), "agree_share": float(res.agree.mean()) if len(res) else None,
            "by_origin": {str(k): float(v) for k, v in res.groupby("as_of").agree.mean().items()} if len(res) else {}}


# --------------------------------------------------------------------------- live outlook (D3)
def fetch_latest_week() -> Path:
    """Newest weekly NOS archive; downloaded and parsed (nemic.experiments.nos rules) only if not already local."""
    import hashlib
    import zipfile
    from nemic.common import session
    from nemic.experiments.nos import ARCHIVE, parse_snapshot
    text = session().get(ARCHIVE, timeout=(20, 90)).text
    names = sorted(set(re.findall(r"PUBLIC_NETWORK_\d{8}\.zip", text)))
    name = names[-1]
    stem = name.removesuffix(".zip")
    local = week_dirs()
    if len(local) and stem in set(local.name):
        return local.loc[local.name.eq(stem), "path"].iat[0]
    folder = LOCAL_WEEKS / stem
    folder.mkdir(parents=True, exist_ok=True)
    scratch = folder / name
    url = ARCHIVE + name
    with session().get(url, stream=True, timeout=(20, 180)) as resp:
        resp.raise_for_status()
        with scratch.open("wb") as f:
            for chunk in resp.iter_content(1 << 20):
                f.write(chunk)
    raw_sha = hashlib.sha256(scratch.read_bytes()).hexdigest()
    previous, catalogue, events, reports, rejected, cache = set(), {}, [], [], [], {}
    with zipfile.ZipFile(scratch) as outer:
        for m in sorted(outer.infolist(), key=lambda x: x.filename):
            if not m.filename.lower().endswith(".zip"):
                continue
            try:
                gen, rows = parse_snapshot(outer.read(m), m.filename, cache)
            except (ValueError, KeyError, IndexError) as exc:
                rejected.append({"member": m.filename, "reason": str(exc)})
                continue
            cur = set(rows)
            events += [(gen, rid, True) for rid in sorted(cur - previous)] + [(gen, rid, False) for rid in sorted(previous - cur)]
            for rid in cur - previous:
                catalogue[rid] = rows[rid]
            previous = cur
            reports.append((gen, m.filename, len(cur)))
    write_parquet(folder / "changes.parquet", pd.DataFrame(events, columns=["generated_nem", "row_id", "present"]))
    write_parquet(folder / "rows.parquet", pd.DataFrame([{"row_id": k, "table": v["table"], "version": v["version"],
                                                          "fields_json": json.dumps(v["fields"], sort_keys=True)}
                                                         for k, v in catalogue.items()]))
    write_parquet(folder / "reports.parquet", pd.DataFrame(reports, columns=["generated_nem", "member", "distinct_rows"]))
    write_json(folder / "manifest.json", {"url": url, "raw_sha256": raw_sha, "raw_bytes": scratch.stat().st_size,
                                          "reports": len(reports), "rejected": rejected,
                                          "parser": "nemic.experiments.nos.parse_snapshot"})
    scratch.unlink()
    return folder


def apply_skill(out: pd.DataFrame, cells: pd.DataFrame) -> pd.DataFrame:
    """Q22: where the backtest shows no skill for a lead band x connector-direction, show the normal-rate baseline."""
    out = out.copy()
    out["lead_band"] = out.lead_days.map(lead_band)
    sk = cells[cells.layer.eq("binding")].set_index(["lead_band", "name", "direction"]).skilful.to_dict() if len(cells) else {}
    out["skill_status"] = [("skilful" if sk.get((b, n, d), False) else "baseline_shown")
                           for b, n, d in zip(out.lead_band, out.name, out.direction)]
    base = out.skill_status.eq("baseline_shown")
    for i in (1, 2, 3):
        if f"binding_p_{i}" in out:
            out[f"binding_p_outlook_{i}"] = out[f"binding_p_{i}"]
            out.loc[base, f"binding_p_{i}"] = out.loc[base, f"binding_normal_{i}"]
    out["confidence_note"] = np.where(base, "No measured skill in this lead band and link-direction: matched normal rate shown",
                                      np.where(out.family_source.eq("inferred"), "Family inferred from asset history",
                                               "Linked constraint set"))
    return out


def live(latest: bool = True, week: str | None = None) -> dict:
    cells_path = OUT / "backtest_cells.parquet"
    if not cells_path.exists():
        raise RuntimeError("Backtest must be complete before the live outlook (Q27)")
    path = fetch_latest_week() if latest and week is None else week_dirs().set_index("name").path[week]
    as_of, member, detail, sets, meta = snapshot(path)
    evidence = load_evidence()
    out, b = build_outlook(as_of, detail, sets, evidence, meta)
    out = apply_skill(out, pd.read_parquet(cells_path))
    folder = OUT / "live" / member.removesuffix(".zip")
    folder.mkdir(parents=True, exist_ok=True)
    write_parquet(folder / "outlook_outages.parquet", out)
    out.to_csv(folder / "outlook_outages.csv", index=False)
    wk = weekly(out, as_of)
    wk.to_csv(folder / "outlook_weekly.csv", index=False)
    write_json(folder / "meta.json", {**meta, "as_of": str(as_of), "bookings": len(b), "rows": len(out)})
    write_json(OUT / "live" / "latest.json", {"folder": str(folder.relative_to(BDATA)), **meta})
    return {"snapshot": member, "as_of": str(as_of), "bookings": len(b), "rows": len(out),
            "skilful_rows": int(out.skill_status.eq("skilful").sum()) if len(out) else 0}
