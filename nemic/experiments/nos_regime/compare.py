"""S5: matched on/off comparisons, placebo, support gate, key-level lookup, spillover, event study, booking reliability.

Definitions follow execution/nos_outage_regime_v1/METHODOLOGY.md §5–§6. Descriptive/retrospective only.
"""
from __future__ import annotations

import sys
import zlib

import holidays
import numpy as np
import pandas as pd

from nemic.common import IC

from .common import DATA, END, ROOT, START, YEAR2, write_parquet
from .state import GRID30, leaders

METRICS = ["capacity", "headroom", "directional_flow", "at_limit", "restricted", "forced_direction", "tight_capacity",
           "tightening", "relief"]
CI_METRICS = ["capacity", "headroom", "directional_flow", "at_limit"]
BALANCE = ["temperature_mean", "vre_difference", "residual_difference", "half_hour", "other_count"]
MAX_CONTROLS, WINDOW_DAYS, REPS, SEED = 5, 21, 1000, 20260924
SUBDIV = {"NSW1": "NSW", "VIC1": "VIC", "QLD1": "QLD", "SA1": "SA", "TAS1": "TAS"}
REGION_OF_IC = {ic: (v["source"], v["sink"]) for ic, v in IC.items()}
OUT = DATA / "tables"


# --------------------------------------------------------------------------- panel
def regime_panel() -> pd.DataFrame:
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_all_ic_regime_report as rr  # noqa: E402
    panel = rr.build_panel()
    bins = {}
    for var, name in [("temperature_mean", "tbin"), ("vre_difference", "vbin"), ("residual_difference", "rbin")]:
        q = panel.groupby(["ic", "direction", "season"])[var].quantile([.2, .8]).unstack()
        q.columns = ["p20", "p80"]
        j = panel[["ic", "direction", "season"]].join(q, on=["ic", "direction", "season"])
        b = np.where(panel[var].isna(), -1, np.where(panel[var] <= j.p20, 0, np.where(panel[var] >= j.p80, 2, 1)))
        panel[name] = b.astype(np.int8)
        bins[var] = q
    panel = panel[(panel.time > START) & (panel.time <= END)].copy()
    panel["day_period"] = rr.daily_period(panel.time)
    years = range(2024, 2027)
    hol = {r: holidays.AU(subdiv=s, years=years) for r, s in SUBDIV.items()}
    dates = panel.time.dt.normalize() - pd.to_timedelta(((panel.time.dt.hour == 0) & (panel.time.dt.minute == 0)).astype(int), unit="D")
    panel["nem_date"] = dates
    weekend = dates.dt.dayofweek >= 5
    src = panel.ic.map(lambda i: REGION_OF_IC[i][0]); snk = panel.ic.map(lambda i: REGION_OF_IC[i][1])
    ud = pd.Series(dates.dt.date.values, index=panel.index)
    is_hol = [(d in hol[a]) or (d in hol[b]) for d, a, b in zip(ud, src, snk)]
    panel["daytype"] = (weekend | np.array(is_hol)).astype(np.int8)
    panel["study_year"] = np.where(panel.time <= YEAR2, 1, 2).astype(np.int8)
    panel["complete"] = panel.n5.eq(6) & panel.capacity.notna() & panel.directional_flow.notna()
    panel["at_limit"] = ((panel.capacity > 0) & (panel.headroom < np.maximum(10, .05 * panel.capacity))).astype(float)
    panel["restricted"] = panel.restricted.astype(float)
    panel["forced_direction"] = panel.forced_direction.astype(float)
    return panel


def pressure_30min(ic: str) -> pd.DataFrame:
    from .common import MONTHS, STUDY
    parts = []
    for month in MONTHS:
        p = ROOT / f"data/constraint_{STUDY[ic]}_2y/months/{month}/constraint_features_5min.parquet"
        parts.append(pd.read_parquet(p, columns=["time", "upper_gen_tightening", "upper_gen_relief",
                                                 "lower_gen_tightening", "lower_gen_relief"]))
    f = pd.concat(parts).drop_duplicates("time")
    f["time"] = f.time.dt.ceil("30min")
    g = f.groupby("time").sum(min_count=1)
    return g


# --------------------------------------------------------------------------- context per connector
class Context:
    def __init__(self, ic: str, panel: pd.DataFrame, coverage: pd.DataFrame, relevance: pd.DataFrame,
                 lead30: pd.DataFrame, linked: dict, families: list[str]):
        self.ic = ic
        self.families = families                       # relevant families for this connector (signature members)
        self.fidx = {f: i for i, f in enumerate(families)}
        cov = coverage.reindex(GRID30)
        self.cov_all = cov
        full = (cov[families] == 6).to_numpy() if families else np.zeros((len(GRID30), 0), bool)
        self.full = full
        rng = np.random.default_rng(zlib.crc32(ic.encode()))
        self.w = rng.integers(1, 2 ** 63 - 1, size=len(families), dtype=np.uint64)
        self.sig = (full.astype(np.uint64) * self.w).sum(axis=1, dtype=np.uint64) if families else np.zeros(len(GRID30), np.uint64)
        self.count = full.sum(axis=1)
        self.linked = linked
        self.pressure = pressure_30min(ic).reindex(GRID30)
        self.dirs = {}
        for direction in ["forward", "reverse"]:
            p = panel[(panel.ic == ic) & (panel.direction == direction)].set_index("time").reindex(GRID30)
            col = "upper" if direction == "forward" else "lower"
            p["tightening"] = self.pressure[f"{col}_gen_tightening"].to_numpy()
            p["relief"] = self.pressure[f"{col}_gen_relief"].to_numpy()
            p["complete"] = p.complete.fillna(False).astype(bool)
            def code(c):
                return p[c].astype("category").cat.codes.to_numpy().astype(np.int64) if c == "season" else p[c].fillna(-1).to_numpy().astype(np.int64) + 1
            full_key = np.zeros(len(p), np.int64); coarse_key = np.zeros(len(p), np.int64)
            for c in ["season", "daytype", "tbin", "vbin", "rbin", "study_year"]:
                full_key = full_key * 64 + code(c)
            for c in ["season", "daytype", "tbin", "study_year"]:
                coarse_key = coarse_key * 64 + code(c)
            p["key"] = full_key
            p["ckey"] = coarse_key
            p["hh"] = p.half_hour.fillna(-99).to_numpy().astype(np.int64)
            lead = np.zeros((len(GRID30), len(families)), bool)
            l = lead30[(lead30.ic == ic) & (lead30.direction == direction) & lead30.GENCONSETID.isin(self.fidx)]
            ti = GRID30.get_indexer(l.time30)
            ok = ti >= 0
            lead[ti[ok], l.GENCONSETID[ok].map(self.fidx).to_numpy()] = True
            self.dirs[direction] = {"p": p, "lead": lead, "lead_count": lead.sum(axis=1)}
        self.t_ns = GRID30.asi8

    # ---------------------------------------------------------------- matching
    def match(self, direction: str, treat: np.ndarray, removed: list[str], ctrl_ok: np.ndarray) -> pd.DataFrame:
        d = self.dirs[direction]
        p = d["p"]
        comp = p.complete.to_numpy()
        tpos = np.flatnonzero(treat & comp)
        if len(tpos) == 0:
            return pd.DataFrame()
        ridx = [self.fidx[f] for f in removed if f in self.fidx]
        rem_full = self.full[:, ridx] if ridx else np.zeros((len(GRID30), 0), bool)
        rem_sig = (rem_full.astype(np.uint64) * self.w[ridx]).sum(axis=1, dtype=np.uint64) if ridx else np.zeros(len(GRID30), np.uint64)
        rem_lead = d["lead"][:, ridx].sum(axis=1) if ridx else np.zeros(len(GRID30), int)
        sig_adj = self.sig - rem_sig
        cnt_adj = self.count - rem_full.sum(axis=1)
        olead = (d["lead_count"] - rem_lead) > 0
        cpos = np.flatnonzero(ctrl_ok & comp & ~treat)
        key, ckey, hh = p.key.to_numpy(), p.ckey.to_numpy(), p.hh.to_numpy()
        T = pd.DataFrame({"tp": tpos, "key": key[tpos], "ckey": ckey[tpos], "hh": hh[tpos], "sig": sig_adj[tpos],
                          "cnt": cnt_adj[tpos], "ol": olead[tpos], "tt": self.t_ns[tpos]})
        C = pd.DataFrame({"cp": cpos, "key": key[cpos], "ckey": ckey[cpos], "hh": hh[cpos], "sig": sig_adj[cpos],
                          "cnt": cnt_adj[cpos], "ol": olead[cpos], "ct": self.t_ns[cpos]})
        win = WINDOW_DAYS * 86400 * 10 ** 9
        empty = pd.DataFrame(columns=["tp", "cp", "match_type"])

        def pick(T_, on, kind):
            if T_.empty:
                return empty
            parts = []
            for off in (0, -1, 1):   # same half-hour first, then neighbours (circular)
                Tx = T_.assign(hh=(T_.hh + off) % 48)
                parts.append(Tx.merge(C[["cp", "hh", "ct"] + on], on=["hh"] + on).assign(hh_off=abs(off)))
            m = pd.concat(parts, ignore_index=True)
            m = m[np.abs(m.tt - m.ct) <= win]
            if m.empty:
                return empty
            m = m.assign(score=((m.tt // 10 ** 9) * 1000003 + (m.ct // 10 ** 9)) % 2147483647, match_type=kind)
            m = m.sort_values(["tp", "hh_off", "score"])
            return m[m.groupby("tp").cumcount() < MAX_CONTROLS]

        chosen, rest = [], T
        for on, kind in [(["key", "sig"], "exact"), (["key", "cnt", "ol"], "count"), (["ckey", "cnt"], "coarse")]:
            got = pick(rest, on, kind)
            chosen.append(got[["tp", "cp", "match_type"]])
            rest = rest[~rest.tp.isin(got.tp)]
        pairs = pd.concat(chosen, ignore_index=True)
        pairs = pairs.astype({"tp": np.int64, "cp": np.int64})
        units = pd.DataFrame({"tp": tpos})
        vals = p[METRICS].to_numpy(dtype=float)
        if len(pairs):
            cv = pd.DataFrame(vals[pairs.cp.to_numpy()], columns=METRICS)
            cv["tp"] = pairs.tp.to_numpy()
            cmed = cv.groupby("tp")[METRICS].median()
            info = pairs.groupby("tp").agg(n_controls=("cp", "size"), match_type=("match_type", "first"))
            units = units.join(cmed.add_prefix("c_"), on="tp").join(info, on="tp")
            cov_vals = p[["temperature_mean", "vre_difference", "residual_difference", "half_hour"]].to_numpy(dtype=float)
            cc = pd.DataFrame(cov_vals[pairs.cp.to_numpy()], columns=["temperature_mean", "vre_difference", "residual_difference", "half_hour"])
            cc["other_count"] = cnt_adj[pairs.cp.to_numpy()]
            cc["tp"] = pairs.tp.to_numpy()
            units = units.join(cc.groupby("tp").mean().add_prefix("cb_"), on="tp")
        else:
            for m in METRICS:
                units["c_" + m] = np.nan
            units["n_controls"] = 0; units["match_type"] = None
        tv = pd.DataFrame(vals[tpos], columns=METRICS)
        for m in METRICS:
            units["t_" + m] = tv[m].to_numpy()
            units["d_" + m] = units["t_" + m] - units["c_" + m]
        for c in ["temperature_mean", "vre_difference", "residual_difference", "half_hour", "season", "day_period",
                  "tbin", "vbin", "rbin", "season_reference", "nem_date", "study_year"]:
            units[c] = p[c].to_numpy()[tpos]
        units["other_count"] = cnt_adj[tpos]
        units["time"] = GRID30[tpos]
        units["matched"] = units.n_controls.fillna(0) > 0
        # pool for "before" balance: all eligible controls
        units.attrs["pool"] = pd.DataFrame({c: p[c].to_numpy()[cpos] for c in ["temperature_mean", "vre_difference", "residual_difference", "half_hour"]}
                                           ).assign(other_count=cnt_adj[cpos])
        return units


# --------------------------------------------------------------------------- statistics
def boot_ci(diffs: np.ndarray, days: np.ndarray, reps=REPS, seed=SEED):
    ok = np.isfinite(diffs)
    diffs, days = diffs[ok], days[ok]
    if len(diffs) < 2:
        return np.nan, np.nan
    order = np.argsort(diffs)
    diffs, days = diffs[order], days[order]
    uniq, day_idx = np.unique(days, return_inverse=True)
    n = len(uniq)
    rng = np.random.default_rng(seed)
    counts = rng.multinomial(n, np.full(n, 1 / n), size=reps)
    W = counts[:, day_idx].astype(float)
    cum = W.cumsum(axis=1)
    half = cum[:, -1:] / 2
    pos = (cum >= half).argmax(axis=1)
    meds = diffs[pos]
    return float(np.quantile(meds, .025)), float(np.quantile(meds, .975))


def smd(a, b, scale=None):
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 1 or len(b) < 1:
        return np.nan
    s = scale if scale is not None else np.sqrt((a.var() + b.var()) / 2)
    return float((a.mean() - b.mean()) / s) if s > 0 else 0.0


def summarize(units: pd.DataFrame, ci=True) -> dict:
    if units is None or units.empty:
        return {"n_treated": 0, "n_matched": 0, "match_rate": np.nan}
    m = units[units.matched]
    out = {"n_treated": len(units), "n_matched": len(m), "match_rate": len(m) / len(units),
           "treated_hours": len(units) / 2, "treated_days": units.nem_date.nunique(),
           "exact_share": float((m.match_type == "exact").mean()) if len(m) else np.nan}
    for k in METRICS:
        out[f"effect_{k}"] = float(m["d_" + k].median()) if len(m) else np.nan
        out[f"treated_{k}"] = float(m["t_" + k].median()) if len(m) else np.nan
        out[f"control_{k}"] = float(m["c_" + k].median()) if len(m) else np.nan
    out["effect_capacity_pct"] = float((m.d_capacity / m.season_reference * 100).median()) if len(m) else np.nan
    if ci and len(m) >= 2:
        days = m.nem_date.to_numpy().astype("datetime64[D]").astype(np.int64)
        for k in CI_METRICS:
            lo, hi = boot_ci(m["d_" + k].to_numpy(float), days)
            out[f"ci_lo_{k}"], out[f"ci_hi_{k}"] = lo, hi
    pool = units.attrs.get("pool")
    if pool is not None and len(m):
        for c in BALANCE:
            ref = np.asarray(pool[c], float); tv = np.asarray(units[c], float)
            scale = np.sqrt((np.nanvar(tv) + np.nanvar(ref)) / 2) if len(ref) else np.nan
            out[f"smd_before_{c}"] = smd(units[c], pool[c], scale)
            out[f"smd_after_{c}"] = smd(m[c], m["cb_" + c], scale)
        vals = [abs(out[f"smd_after_{c}"]) for c in BALANCE if np.isfinite(out[f"smd_after_{c}"])]
        out["max_abs_smd_after"] = float(max(vals)) if vals else np.nan
        out["share_exact"] = float((m.match_type == "exact").mean())
        out["share_count"] = float((m.match_type == "count").mean())
        out["share_coarse"] = float((m.match_type == "coarse").mean())
    return out


def tier(row) -> str:
    pc = row.get("placebo_clean")
    pc = isinstance(pc, (bool, np.bool_)) and bool(pc)
    mr = row.get("match_rate")
    ok_other = (mr is not None and np.isfinite(mr) and mr >= .6) and pc
    num = lambda v: float(v) if v is not None and np.isfinite(v) else 0.0
    ep, hrs = num(row.get("episodes")), num(row.get("treated_hours"))
    if ep >= 5 and hrs >= 24 and ok_other:
        return "supported"
    if (ep >= 5 and ok_other) or (3 <= ep <= 4 and num(row.get("n_matched")) > 0):
        return "indicative"
    return "unsupported"


# --------------------------------------------------------------------------- linkage
def spell_linkage(families: list[str]) -> tuple[dict, pd.DataFrame]:
    """Per family: half-hour mask of invocations linked to a non-withdrawn episode listing the family (±24 h)."""
    spells = pd.read_parquet(DATA / "invocation_spells.parquet")
    spells = spells[spells.GENCONSETID.isin(families)]
    eps = pd.read_parquet(DATA / "episodes.parquet")
    sets = pd.read_parquet(DATA / "episode_sets.parquet")
    es = sets.merge(eps[["OUTAGEID", "start", "end", "withdrawn"]], on="OUTAGEID")
    es = es[~es.withdrawn & es.GENCONSETID.isin(families)]
    m = spells.merge(es[["GENCONSETID", "OUTAGEID", "start", "end"]].rename(columns={"start": "es", "end": "ee"}), on="GENCONSETID")
    day = pd.Timedelta(hours=24)
    m = m[(m.es <= m.end + day) & (m.ee >= m.start - day)]
    links = m[["GENCONSETID", "INVOCATION_ID", "OUTAGEID", "start", "end"]].drop_duplicates()
    linked_spells = links.drop_duplicates("INVOCATION_ID")
    t = GRID30.to_numpy()
    masks = {}
    for f in families:
        mask = np.zeros(len(t), bool)
        for s, e in zip(linked_spells.loc[linked_spells.GENCONSETID.eq(f), "start"], linked_spells.loc[linked_spells.GENCONSETID.eq(f), "end"]):
            i0 = np.searchsorted(t, np.datetime64(s) + np.timedelta64(25, "m"), side="left")
            i1 = np.searchsorted(t, np.datetime64(e), side="right")
            mask[i0:i1] = True
        masks[f] = mask
    return masks, links


def episodes_touching(links: pd.DataFrame, family: str, times: pd.DatetimeIndex) -> int:
    l = links[links.GENCONSETID.eq(family)]
    if l.empty or len(times) == 0:
        return 0
    t = times.to_numpy()
    hit = set()
    for r in l.itertuples():
        if ((t >= np.datetime64(r.start)) & (t <= np.datetime64(r.end) + np.timedelta64(30, "m"))).any():
            hit.add(r.OUTAGEID)
    return len(hit)


# --------------------------------------------------------------------------- runs
def run_effect(ctx: Context, direction: str, treat, removed, ctrl_ok, placebo=True):
    units = ctx.match(direction, treat, removed, ctrl_ok)
    s = summarize(units)
    if placebo and len(units):
        shifted = np.zeros(len(GRID30), bool)
        tp = np.flatnonzero(treat)
        for k in (-336, 336):
            q = tp + k
            q = q[(q >= 0) & (q < len(GRID30))]
            shifted[q] = True
        shifted &= ctrl_ok & ~treat
        pu = ctx.match(direction, shifted, removed, ctrl_ok & ~shifted)
        ps = summarize(pu)
        s["placebo_n"] = ps.get("n_matched", 0)
        s["placebo_effect_capacity"] = ps.get("effect_capacity", np.nan)
        s["placebo_ci_lo"], s["placebo_ci_hi"] = ps.get("ci_lo_capacity", np.nan), ps.get("ci_hi_capacity", np.nan)
        s["placebo_clean"] = bool(ps.get("n_matched", 0) >= 2 and ps["ci_lo_capacity"] <= 0 <= ps["ci_hi_capacity"])
    if len(units):
        units.attrs.clear()
    return units, s


def window_mask(windows: pd.DataFrame) -> np.ndarray:
    t = GRID30.to_numpy()
    mask = np.zeros(len(t), bool)
    for s, e in zip(windows.start, windows.end):
        i0 = np.searchsorted(t, np.datetime64(s) + np.timedelta64(25, "m"), side="left")
        i1 = np.searchsorted(t, np.datetime64(e), side="right")
        mask[i0:i1] = True
    return mask


def run_connector(ic: str, panel, coverage, relevance, lead30, masks, links, all_relevant) -> dict:
    fams = sorted(relevance.loc[relevance.relevant & relevance.ic.eq(ic), "GENCONSETID"])
    ctx = Context(ic, panel, coverage, relevance, lead30, masks, fams)
    name = IC[ic]["name"]
    fam_rows, unit_parts, unbooked_rows, key_rows, spill_rows = [], [], [], [], []
    cov = coverage.reindex(GRID30)
    # ---- K2 family effects (linked invocations), unbooked, booked-only
    eps = pd.read_parquet(DATA / "episodes.parquet")
    sets = pd.read_parquet(DATA / "episode_sets.parquet")
    for f in fams:
        full = (cov[f] == 6).to_numpy(); off = (cov[f] == 0).to_numpy()
        linked = masks.get(f, np.zeros(len(GRID30), bool))
        for direction in ["forward", "reverse"]:
            units, s = run_effect(ctx, direction, full & linked, [f], off)
            s.update(ic=ic, name=name, direction=direction, level="K2", key=f, GENCONSETID=f,
                     episodes=episodes_touching(links, f, pd.DatetimeIndex(units.time) if len(units) else pd.DatetimeIndex([])),
                     lead_share=float(ctx.dirs[direction]["lead"][full & linked, ctx.fidx[f]].mean()) if (full & linked).any() else np.nan)
            fam_rows.append(s)
            if len(units):
                unit_parts.append(units.drop(columns=[c for c in units.columns if c.startswith("cb_")]).assign(ic=ic, name=name, direction=direction, GENCONSETID=f))
            ub = full & ~linked
            if ub.any():
                uu, us = run_effect(ctx, direction, ub, [f], off, placebo=False)
                us.update(ic=ic, name=name, direction=direction, GENCONSETID=f, state="invoked_unbooked",
                          share_of_invoked=float(ub.sum() / max(full.sum(), 1)))
                unbooked_rows.append(us)
            bw = sets[sets.GENCONSETID.eq(f)].merge(eps[["OUTAGEID", "start", "end", "withdrawn"]], on="OUTAGEID")
            for state, sub in [("booked_only", bw[~bw.withdrawn]), ("withdrawn_booking", bw[bw.withdrawn])]:
                if sub.empty:
                    continue
                bo = window_mask(sub) & off
                if bo.any():
                    bu, bs = run_effect(ctx, direction, bo, [f], off & ~window_mask(sub), placebo=False)
                    bs.update(ic=ic, name=name, direction=direction, GENCONSETID=f, state=state)
                    unbooked_rows.append(bs)
    fam_df = pd.DataFrame(fam_rows)
    # ---- key levels K1 (primary asset), K1xK2, K3 (substation), K4 (area)
    keys = pd.read_parquet(DATA / "outage_keys.parquet")
    es = sets[sets.GENCONSETID.isin(fams)].merge(eps[["OUTAGEID", "start", "end", "withdrawn"]], on="OUTAGEID")
    es = es[~es.withdrawn].merge(keys[["OUTAGEID", "primary_asset", "primary_substationid", "area_key", "primary_asset_is_na"]], on="OUTAGEID")
    for level, col in [("K1", "primary_asset"), ("K3", "primary_substationid"), ("K4", "area_key")]:
        g = es[es[col].notna() & ~es.primary_asset_is_na]
        for key, sub in g.groupby(col):
            n_ep = sub.OUTAGEID.nunique()
            if n_ep < 3:
                key_rows.append({"ic": ic, "name": name, "level": level, "key": key, "episodes_listed": n_ep, "tier": "unsupported"})
                continue
            fset = sorted(set(sub.GENCONSETID))
            win = window_mask(sub.drop_duplicates("OUTAGEID"))
            anyfull = (cov[fset] == 6).any(axis=1).to_numpy(); alloff = (cov[fset] == 0).all(axis=1).to_numpy()
            for direction in ["forward", "reverse"]:
                units, s = run_effect(ctx, direction, win & anyfull, fset, alloff & ~win)
                times = pd.DatetimeIndex(units.time) if len(units) else pd.DatetimeIndex([])
                ep_hit = sum(1 for r in sub.drop_duplicates("OUTAGEID").itertuples()
                             if ((times >= r.start) & (times <= r.end + pd.Timedelta(minutes=30))).any())
                s.update(ic=ic, name=name, direction=direction, level=level, key=key, families="|".join(fset), episodes=ep_hit,
                         episodes_listed=n_ep)
                key_rows.append(s)
                if level == "K1":
                    for f in fset:
                        fsub = sub[sub.GENCONSETID.eq(f)]
                        if fsub.OUTAGEID.nunique() < 3:
                            continue
                        full = (cov[f] == 6).to_numpy(); off = (cov[f] == 0).to_numpy()
                        w2 = window_mask(fsub.drop_duplicates("OUTAGEID"))
                        u2, s2 = run_effect(ctx, direction, w2 & full, [f], off)
                        t2 = pd.DatetimeIndex(u2.time) if len(u2) else pd.DatetimeIndex([])
                        s2.update(ic=ic, name=name, direction=direction, level="K1xK2", key=f"{key} × {f}", families=f,
                                  episodes=sum(1 for r in fsub.drop_duplicates("OUTAGEID").itertuples()
                                               if ((t2 >= r.start) & (t2 <= r.end + pd.Timedelta(minutes=30))).any()),
                                  episodes_listed=fsub.OUTAGEID.nunique(), asset=key, GENCONSETID=f)
                        key_rows.append(s2)
    # ---- spillover (RQ6): families relevant elsewhere but not here
    others = sorted(set(all_relevant) - set(fams))
    for f in others:
        if f not in cov.columns:
            continue
        full = (cov[f] == 6).to_numpy(); off = (cov[f] == 0).to_numpy()
        linked = masks.get(f, np.zeros(len(GRID30), bool))
        if (full & linked).sum() < 4:
            continue
        for direction in ["forward", "reverse"]:
            units, s = run_effect(ctx, direction, full & linked, [f], off)
            s.update(target_ic=ic, target_name=name, direction=direction, GENCONSETID=f,
                     episodes=episodes_touching(links, f, pd.DatetimeIndex(units.time) if len(units) else pd.DatetimeIndex([])))
            spill_rows.append(s)
    return {"families": fam_df, "units": pd.concat(unit_parts, ignore_index=True) if unit_parts else pd.DataFrame(),
            "states": pd.DataFrame(unbooked_rows), "keys": pd.DataFrame(key_rows), "spill": pd.DataFrame(spill_rows), "ctx": ctx}


# --------------------------------------------------------------------------- event study (RQ8)
def event_study(ctx: Context, supported: set[str], merged: pd.DataFrame) -> pd.DataFrame:
    rows = []
    cov = ctx.cov_all
    t = GRID30
    for f in ctx.families:
        off = (cov[f] == 0).to_numpy()
        sp = merged[merged.GENCONSETID.eq(f)]
        sp = sp[(sp.end - sp.start) >= pd.Timedelta(hours=1)]
        if sp.empty:
            continue
        others = [g for g in ctx.families if g != f]
        oth = merged[merged.GENCONSETID.isin(others)]
        for direction in ["forward", "reverse"]:
            cap = ctx.dirs[direction]["p"].capacity.to_numpy(float)
            comp = ctx.dirs[direction]["p"].complete.to_numpy()
            capx = np.where(comp, cap, np.nan)
            for anchor in ["start", "end"]:
                for r in sp.itertuples():
                    a = getattr(r, anchor)
                    i = t.searchsorted(a.ceil("30min"))
                    if i - 96 < 336 or i + 96 >= len(t):
                        continue
                    idx = np.arange(i - 96, i + 97)
                    lags = idx[:, None] - 48 * np.arange(1, 8)[None, :]
                    base_vals = np.where(off[lags], capx[lags], np.nan)
                    with np.errstate(all="ignore"):
                        base = np.nanmedian(base_vals, axis=1)
                    rel = capx[idx] - base
                    clean = not (((oth.start - a).abs() <= pd.Timedelta(hours=2)) | ((oth.end - a).abs() <= pd.Timedelta(hours=2))).any()
                    rows.append(pd.DataFrame({"ic": ctx.ic, "direction": direction, "GENCONSETID": f, "anchor": anchor,
                                              "spell_start": r.start, "offset_h": np.arange(-96, 97) / 2, "rel_capacity": rel,
                                              "clean": clean, "supported": f in supported}))
    if not rows:
        return pd.DataFrame()
    ev = pd.concat(rows, ignore_index=True)
    return ev


def summarize_events(ev: pd.DataFrame) -> pd.DataFrame:
    if ev.empty:
        return ev
    fam = (ev.groupby(["ic", "direction", "GENCONSETID", "anchor", "offset_h"])
           .agg(median_rel=("rel_capacity", "median"), n_spells=("rel_capacity", "count")).reset_index().assign(scope="family"))
    pooled = (ev[ev.supported].groupby(["ic", "direction", "anchor", "clean", "offset_h"])
              .agg(median_rel=("rel_capacity", "median"), p25=("rel_capacity", lambda s: s.quantile(.25)),
                   p75=("rel_capacity", lambda s: s.quantile(.75)), n_spells=("rel_capacity", "count")).reset_index().assign(scope="pooled_supported"))
    return pd.concat([fam, pooled], ignore_index=True)


# --------------------------------------------------------------------------- booking reliability (RQ7)
def booking_reliability(relevance: pd.DataFrame) -> pd.DataFrame:
    eps = pd.read_parquet(DATA / "episodes.parquet")
    sets = pd.read_parquet(DATA / "episode_sets.parquet")
    merged = pd.read_parquet(DATA / "invocation_merged.parquet")
    rows = []
    for ic, rel in relevance[relevance.relevant].groupby("ic"):
        fams = set(rel.GENCONSETID)
        es = sets[sets.GENCONSETID.isin(fams)].merge(eps, on="OUTAGEID")
        for year, g in es.groupby("study_year"):
            ep = g.drop_duplicates("OUTAGEID")
            live = g[~g.withdrawn]
            mm = live.merge(merged, on="GENCONSETID", suffixes=("", "_inv"))
            day = pd.Timedelta(hours=24)
            conv = mm[(mm.start_inv <= mm.end + day) & (mm.end_inv >= mm.start - day)].OUTAGEID.nunique()
            n_live = live.OUTAGEID.nunique()
            act = ep[ep.actual_start.notna() & ~ep.withdrawn]
            rows.append({"ic": ic, "name": IC[ic]["name"], "study_year": int(year), "episodes": len(ep),
                         "withdrawn_share": float(ep.withdrawn.mean()), "non_withdrawn": n_live,
                         "invoked_share": conv / n_live if n_live else np.nan,
                         "actual_window_share": float(ep[~ep.withdrawn].actual_start.notna().mean()) if n_live else np.nan,
                         "start_shift_h_p50": float(((act.actual_start - act.scheduled_start).dt.total_seconds() / 3600).median()) if len(act) else np.nan,
                         "end_shift_h_p50": float(((act.actual_end - act.scheduled_end).dt.total_seconds() / 3600).median()) if len(act) else np.nan,
                         "early_return_share": float((act.actual_end < act.scheduled_end - pd.Timedelta(hours=1)).mean()) if len(act) else np.nan,
                         "overrun_share": float((act.actual_end > act.scheduled_end + pd.Timedelta(hours=1)).mean()) if len(act) else np.nan,
                         "lead_days_p50": float(((ep.scheduled_start - ep.submitted).dt.total_seconds() / 86400).median())})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- descriptive state coverage
def state_coverage(ctx: Context, window_any: np.ndarray) -> pd.DataFrame:
    cov = ctx.cov_all[ctx.families] if ctx.families else pd.DataFrame(index=GRID30)
    anyfull = (cov == 6).any(axis=1).to_numpy()
    anypart = ((cov > 0) & (cov < 6)).any(axis=1).to_numpy()
    rows = []
    for direction, d in ctx.dirs.items():
        p = d["p"]
        leading = d["lead_count"] > 0
        state = np.where(~p.complete.to_numpy(), "unknown", np.where(leading, "invoked_leading", np.where(anyfull, "invoked_nonleading",
                         np.where(anypart, "partial", np.where(window_any, "booked_only", "clear")))))
        frame = p[["capacity", "headroom", "directional_flow", "at_limit", "restricted", "forced_direction", "season", "day_period", "half_hour"]].copy()
        frame["state"] = state
        frame["time"] = GRID30
        frame["ic"], frame["direction"] = ctx.ic, direction
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def build_compare(ics: list[str], tag: str) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = regime_panel()
    coverage = pd.read_parquet(DATA / "family_coverage_30min.parquet")
    relevance = pd.read_parquet(DATA / "set_relevance.parquet")
    lead30 = pd.read_parquet(DATA / "family_leading_30min.parquet")
    all_relevant = sorted(set(relevance.loc[relevance.relevant, "GENCONSETID"]))
    masks, links = spell_linkage(all_relevant)
    merged = pd.read_parquet(DATA / "invocation_merged.parquet")
    eps = pd.read_parquet(DATA / "episodes.parquet"); sets = pd.read_parquet(DATA / "episode_sets.parquet")
    summary = {}
    for ic in ics:
        name = IC[ic]["name"]
        print("connector", name, flush=True)
        r = run_connector(ic, panel, coverage, relevance, lead30, masks, links, all_relevant)
        fam = r["families"]
        if len(fam):
            fam["tier"] = [tier(x) for x in fam.to_dict("records")]
        keys = r["keys"]
        if len(keys):
            keys["tier"] = [x["tier"] if pd.isna(x.get("n_treated")) else tier(x) for x in keys.to_dict("records")]
        spill = r["spill"]
        if len(spill):
            spill["tier"] = [tier(x) for x in spill.to_dict("records")]
        supported = set(fam.loc[fam.tier.eq("supported"), "GENCONSETID"]) if len(fam) else set()
        ev = event_study(r["ctx"], supported, merged[merged.GENCONSETID.isin(r["ctx"].families)])
        rel_eps = sets[sets.GENCONSETID.isin(r["ctx"].families)].merge(eps[["OUTAGEID", "start", "end", "withdrawn"]], on="OUTAGEID")
        cov_state = state_coverage(r["ctx"], window_mask(rel_eps[~rel_eps.withdrawn]))
        for label, frame in [("family_effects", fam), ("units", r["units"]), ("states", r["states"]), ("key_effects", keys),
                             ("spillover", spill), ("event_study", summarize_events(ev)), ("state_panel", cov_state)]:
            write_parquet(OUT / f"{label}__{ic}.parquet", frame if len(frame) else pd.DataFrame({"empty": []}))
        summary[name] = {"families": int(len(fam) / 2) if len(fam) else 0,
                         "family_tiers": fam.drop_duplicates(["GENCONSETID", "tier"]).tier.value_counts().to_dict() if len(fam) else {},
                         "supported_families_any_direction": len(supported),
                         "median_match_rate": float(fam.match_rate.median()) if len(fam) else None,
                         "placebo_clean_share": float(fam.placebo_clean.mean()) if len(fam) and "placebo_clean" in fam else None,
                         "key_tiers": keys.groupby("level").tier.value_counts().unstack(fill_value=0).to_dict("index") if len(keys) else {},
                         "spill_rows": len(spill)}
        print(name, summary[name], flush=True)
    br = booking_reliability(relevance[relevance.ic.isin(ics)])
    write_parquet(OUT / f"booking_reliability__{tag}.parquet", br)
    return summary
