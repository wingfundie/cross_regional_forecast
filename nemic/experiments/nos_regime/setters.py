"""A2–A7 (reused by B3): constraint-layer statistics on the matched outage/control pairs from A1.

A *layer* gives, for every connector-direction and half-hour, the share of the half-hour's five-minute intervals in
which each constraint equation is active:

* setter layer (Phase A): the reconstructed limit-setting equation (one per interval, from the constraint studies);
* binding layer (Phase B): equations with |MARGINALVALUE| > 1e-9 (several per interval possible).

For a family-direction with treated half-hours T and matched controls C(t), the treated share of equation e is the
mean over matched units of H[t, e]; the control share is the mean over units of the mean of H[c, e] over that unit's
controls. Differences are unit-level (treated − control) with day-block bootstrap CIs of the mean. Classes:
own set (member of the family), other outage set (member of any NOS-linked set), FCAS (F_ prefix), ramp/discretionary
(# prefix), system-normal/other (everything else).

Plan: execution/nos_constraint_binding_v1/PLAN.md §5. Descriptive and retrospective only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import sparse

from nemic.common import IC

from .common import DATA, END, MONTHS, ROOT, START, STUDY, write_parquet
from .pairs import BDATA
from .state import GRID5, GRID30, covered, invocation_spells, merge_spells, set_members

TABLES = BDATA / "tables"
REPS, SEED, TOP_K = 1000, 20260924, 10
N30 = len(GRID30)
CLASSES = ["own_set", "other_outage_set", "system_normal_other", "fcas", "ramp_discretionary"]


# --------------------------------------------------------------------------- layers
@dataclass
class Layer:
    name: str
    codes: pd.Index
    H: dict = field(default_factory=dict)        # direction -> csr (N30 x len(codes)) active share
    last: dict = field(default_factory=dict)     # direction -> int array (N30): code active at the half-hour's last interval
    avail: dict = field(default_factory=dict)    # direction -> float array (N30): intervals with data (0..6)
    any: dict = field(default_factory=dict)      # direction -> float array (N30): share of intervals with >= 1 active equation
    pos: dict = field(default_factory=dict)      # direction -> (five-minute position, code) arrays of active equations

    def own_share(self, direction: str, own_mask: np.ndarray) -> np.ndarray:
        """Per half-hour: share of intervals with at least one active equation from ``own_mask`` (not a sum)."""
        pos, code = self.pos[direction]
        hit = np.unique(pos[own_mask[code]]) if own_mask.any() else np.array([], dtype=np.int64)
        avail = self.avail[direction]
        inv = np.divide(1.0, avail, out=np.zeros_like(avail), where=avail > 0)
        return np.bincount(hit // 6, minlength=N30) * inv
    eq_type: dict = field(default_factory=dict)  # constraint -> equation type (Thermal, Voltage Stability, ...)


def setter_frame(ic: str) -> pd.DataFrame:
    parts = []
    for month in MONTHS:
        p = ROOT / f"data/constraint_{STUDY[ic]}_2y/months/{month}/constraint_features_5min.parquet"
        parts.append(pd.read_parquet(p, columns=["time", "upper_constraint", "lower_constraint", "upper_family", "lower_family"]))
    f = pd.concat(parts, ignore_index=True)
    f = f[(f.time > START) & (f.time <= END)].drop_duplicates("time")      # as state.leaders()
    long = pd.concat([
        f[["time", "upper_constraint", "upper_family"]].set_axis(["time", "constraint", "eq_type"], axis=1).assign(direction="forward"),
        f[["time", "lower_constraint", "lower_family"]].set_axis(["time", "constraint", "eq_type"], axis=1).assign(direction="reverse")])
    return long.dropna(subset=["constraint"])


def build_layer(frame: pd.DataFrame, name: str, avail5: dict | None = None) -> Layer:
    """frame: time (five-minute, interval ending), direction, constraint[, eq_type]. avail5: direction -> bool array over GRID5."""
    frame = frame.assign(pos=GRID5.get_indexer(frame.time))
    frame = frame[frame.pos >= 0]
    codes = pd.Index(sorted(frame.constraint.unique()))
    layer = Layer(name, codes)
    if "eq_type" in frame:
        layer.eq_type = frame.dropna(subset=["eq_type"]).groupby("constraint").eq_type.agg(lambda s: s.mode().iat[0]).to_dict()
    for direction in ["forward", "reverse"]:
        d = frame[frame.direction.eq(direction)].drop_duplicates(["pos", "constraint"])
        row = d.pos.to_numpy() // 6
        col = codes.get_indexer(d.constraint)
        if avail5 is None:
            avail = np.bincount(d.drop_duplicates("pos").pos.to_numpy() // 6, minlength=N30).astype(float)
        else:
            avail = avail5[direction].reshape(-1, 6).sum(axis=1).astype(float)
        counts = sparse.coo_matrix((np.ones(len(d)), (row, col)), shape=(N30, len(codes))).tocsr()
        inv = np.divide(1.0, avail, out=np.zeros_like(avail), where=avail > 0)
        layer.H[direction] = sparse.diags(inv) @ counts
        layer.avail[direction] = avail
        layer.any[direction] = np.bincount(d.drop_duplicates("pos").pos.to_numpy() // 6, minlength=N30) * inv
        layer.pos[direction] = (d.pos.to_numpy(), col)
        last = np.full(N30, -1, np.int64)
        s = d.sort_values("pos")
        lastpos = s.groupby(s.pos // 6).tail(1)
        last[lastpos.pos.to_numpy() // 6] = codes.get_indexer(lastpos.constraint)
        layer.last[direction] = last
    return layer


def setter_layer(ic: str) -> Layer:
    return build_layer(setter_frame(ic), "setter")


# --------------------------------------------------------------------------- classes
def membership() -> tuple[pd.DataFrame, set]:
    members = set_members()
    esets = pd.read_parquet(DATA / "episode_sets.parquet")
    outage_members = set(members.loc[members.GENCONSETID.isin(set(esets.GENCONSETID)), "GENCONID"])
    return members, outage_members


def classify(codes: pd.Index, own: set, outage_members: set) -> np.ndarray:
    out = []
    for c in codes:
        if c in own:
            out.append("own_set")
        elif c.startswith("#"):
            out.append("ramp_discretionary")
        elif c.startswith("F_"):
            out.append("fcas")
        elif c in outage_members:
            out.append("other_outage_set")
        else:
            out.append("system_normal_other")
    return np.array(out)


# --------------------------------------------------------------------------- statistics
def boot_mean(diffs: np.ndarray, days: np.ndarray, reps=REPS, seed=SEED) -> tuple[float, float]:
    ok = np.isfinite(diffs)
    diffs, days = diffs[ok], days[ok]
    if len(diffs) < 2:
        return np.nan, np.nan
    uniq, idx = np.unique(days, return_inverse=True)
    S = np.bincount(idx, weights=diffs, minlength=len(uniq)); N = np.bincount(idx, minlength=len(uniq)).astype(float)
    counts = np.random.default_rng(seed).multinomial(len(uniq), np.full(len(uniq), 1 / len(uniq)), size=reps).astype(float)
    means = (counts @ S) / np.maximum(counts @ N, 1)
    return float(np.quantile(means, .025)), float(np.quantile(means, .975))


def unit_matrices(H: sparse.csr_matrix, pairs: pd.DataFrame, any_share: np.ndarray | None = None):
    """pairs: t_time, c_time. Returns treated half-hour index per unit, Ht (units x codes), Hc (units x codes)
    and, when ``any_share`` is given, per-unit treated and control any-active shares."""
    t = GRID30.get_indexer(pairs.t_time); c = GRID30.get_indexer(pairs.c_time)
    units, u = np.unique(t, return_inverse=True)
    n = np.bincount(u).astype(float)
    W = sparse.coo_matrix((1.0 / n[u], (u, c)), shape=(len(units), N30)).tocsr()
    if any_share is None:
        return units, H[units], W @ H
    return units, H[units], W @ H, any_share[units], W @ any_share


def unit_weights(pairs: pd.DataFrame, units: np.ndarray) -> sparse.csr_matrix:
    t = GRID30.get_indexer(pairs.t_time); c = GRID30.get_indexer(pairs.c_time)
    u = np.searchsorted(units, t)
    n = np.bincount(u, minlength=len(units)).astype(float)
    return sparse.coo_matrix((1.0 / n[u], (u, c)), shape=(len(units), N30)).tocsr()


def family_stats(layer: Layer, direction: str, pairs: pd.DataFrame, own_mask: np.ndarray, classes: np.ndarray,
                 top_k: int = TOP_K) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    units, Ht, Hc, at, ac = unit_matrices(layer.H[direction], pairs, layer.any[direction])
    days = (GRID30[units] - pd.Timedelta(minutes=1)).floor("D").asi8 // 86_400_000_000_000   # NEM date of the interval
    ts = np.asarray(Ht.mean(axis=0)).ravel(); cs = np.asarray(Hc.mean(axis=0)).ravel()
    own_vec = layer.own_share(direction, own_mask)
    t_own = own_vec[units]
    c_own = np.asarray(unit_weights(pairs, units) @ own_vec).ravel()
    d_own = t_own - c_own
    lo, hi = boot_mean(d_own, days)
    row = {"n_units": len(units), "treated_hours": len(units) / 2, "own_treated": float(t_own.mean()),
           "own_control": float(c_own.mean()), "own_diff": float(d_own.mean()), "own_ci_lo": lo, "own_ci_hi": hi,
           "treated_coverage": float((layer.avail[direction][units] > 0).mean()),
           "any_treated": float(at.mean()), "any_control": float(ac.mean()), "any_diff": float((at - ac).mean())}
    row["any_ci_lo"], row["any_ci_hi"] = boot_mean(at - ac, days)
    for k in CLASSES:
        m = classes == k
        row[f"class_{k}_treated"] = float(ts[m].sum()); row[f"class_{k}_control"] = float(cs[m].sum())
    order = np.argsort(-np.maximum(ts, cs))[:top_k]
    moved = np.argsort(-np.abs(ts - cs))[:top_k]
    pick = list(dict.fromkeys(list(order) + list(moved)))
    Htd = Ht[:, pick].toarray(); Hcd = Hc[:, pick].toarray()
    top = []
    for j, e in enumerate(pick):
        d = Htd[:, j] - Hcd[:, j]
        lo_e, hi_e = boot_mean(d, days)
        top.append({"constraint": layer.codes[e], "class": classes[e], "eq_type": layer.eq_type.get(layer.codes[e]),
                    "treated_share": float(ts[e]), "control_share": float(cs[e]), "diff_pp": float((ts[e] - cs[e]) * 100),
                    "ratio": float(ts[e] / cs[e]) if cs[e] > 0 else np.nan, "ci_lo_pp": lo_e * 100, "ci_hi_pp": hi_e * 100,
                    "in_top_share": e in set(order), "in_top_moved": e in set(moved)})
    top = pd.DataFrame(top)
    if len(top):
        top["rank_share"] = top[["treated_share", "control_share"]].max(axis=1).rank(ascending=False, method="first")
        best = top.sort_values("treated_share", ascending=False).iloc[0]
        row.update(top1_treated=best.constraint, top1_treated_share=best.treated_share, top1_control_share=best.control_share)
        ctrl = top.sort_values("control_share", ascending=False).iloc[0]
        row.update(top1_control=ctrl.constraint, top1_control_share_c=ctrl.control_share, top1_control_share_t=ctrl.treated_share)
    unit = pd.DataFrame({"time": GRID30[units], "t_own": t_own, "c_own": c_own})
    if len(top):
        j = pick.index(layer.codes.get_loc(row["top1_control"]))
        unit["t_top_control"] = Htd[:, j]; unit["c_top_control"] = Hcd[:, j]
    return row, top, unit


def transitions(layer: Layer, direction: str, treated_idx: np.ndarray) -> pd.DataFrame:
    """Setter at the last interval before each invocation run (skipping treated half-hours) vs the run's first half-hour."""
    last = layer.last[direction]
    t = np.sort(np.unique(treated_idx))
    if len(t) == 0:
        return pd.DataFrame()
    starts = t[np.r_[True, np.diff(t) > 1]]
    tset = set(t.tolist())
    rows = []
    for s in starts:
        prev, steps = s - 1, 0
        while prev in tset and steps < 48:
            prev -= 1; steps += 1
        b = last[prev] if prev >= 0 else -1
        a = last[s]
        rows.append({"run_start": GRID30[s], "before": layer.codes[b] if b >= 0 else None,
                     "first_during": layer.codes[a] if a >= 0 else None})
    out = pd.DataFrame(rows)
    ok = out.before.notna() & out.first_during.notna()
    out["changed"] = np.where(ok, out.before != out.first_during, np.nan)
    return out


def event_profile(layer: Layer, direction: str, spells: pd.DataFrame, own_mask: np.ndarray, code: int | None,
                  lo_h: float = -6, hi_h: float = 12) -> pd.DataFrame:
    H = layer.H[direction]
    own = layer.own_share(direction, own_mask)
    top = np.asarray(H[:, code].todense()).ravel() if code is not None else np.full(N30, np.nan)
    avail = layer.avail[direction] > 0
    offs = np.arange(int(lo_h * 2), int(hi_h * 2) + 1)
    rows = []
    for anchor in ["start", "end"]:
        for r in spells.itertuples():
            i = GRID30.searchsorted(getattr(r, anchor).ceil("30min"))
            idx = i + offs
            if idx[0] < 0 or idx[-1] >= N30:
                continue
            ok = avail[idx]
            rows.append(pd.DataFrame({"anchor": anchor, "spell_start": r.start, "clean": r.clean, "offset_h": offs / 2,
                                      "own_share": np.where(ok, own[idx], np.nan), "top_control_share": np.where(ok, top[idx], np.nan)}))
    if not rows:
        return pd.DataFrame()
    ev = pd.concat(rows, ignore_index=True)
    return (ev.groupby(["anchor", "clean", "offset_h"]).agg(own_share=("own_share", "mean"), top_control_share=("top_control_share", "mean"),
                                                            n_spells=("own_share", "count")).reset_index())


# --------------------------------------------------------------------------- A2 gate
def lead_gate(ic: str, layer: Layer, members: pd.DataFrame) -> dict:
    """Reproduce v1 set_relevance lead counts (five-minute intervals led by a member while the family is invoked)."""
    relevance = pd.read_parquet(DATA / "set_relevance.parquet")
    rel = relevance[relevance.ic.eq(ic)]
    spells = invocation_spells(); merged = merge_spells(spells)
    by_family = {f: g.reset_index(drop=True) for f, g in merged.groupby("GENCONSETID")}
    frame = setter_frame(ic)
    ex = frame.merge(members, left_on="constraint", right_on="GENCONID", how="inner")
    bad, checked = 0, 0
    for r in rel.itertuples():
        g = ex[ex.GENCONSETID.eq(r.GENCONSETID)]
        if r.GENCONSETID not in by_family or g.empty:
            n = {"forward": 0, "reverse": 0}
        else:
            ok = covered(by_family[r.GENCONSETID], g.time.to_numpy())
            n = g[ok].groupby("direction").size().to_dict()
        checked += 1
        bad += int(n.get("forward", 0) != r.lead_forward) + int(n.get("reverse", 0) != r.lead_reverse)
    return {"families_checked": checked, "count_mismatches": bad, "pass": bad == 0}


# --------------------------------------------------------------------------- per-connector build
def build_connector(ic: str, layer: Layer, prefix: str, members: pd.DataFrame, outage_members: set,
                    as_of: pd.Timestamp | None = None) -> dict[str, pd.DataFrame]:
    """All family-level tables for one connector and layer. as_of limits treated units to those ending >= 21 days before it."""
    name = IC[ic]["name"]
    pairs = pd.read_parquet(BDATA / f"pairs__{ic}.parquet")
    fam_eff = pd.read_parquet(DATA / "tables" / f"family_effects__{ic}.parquet")
    tiers = fam_eff.set_index(["direction", "GENCONSETID"]).tier.to_dict()
    units_v1 = pd.read_parquet(DATA / "tables" / f"units__{ic}.parquet")
    keys_v1 = pd.read_parquet(DATA / "tables" / f"key_effects__{ic}.parquet")
    if as_of is not None:
        cut = as_of - pd.Timedelta(days=21)
        pairs = pairs[pairs.t_time <= cut]
    own_of = members.groupby("GENCONSETID").GENCONID.apply(set).to_dict()
    merged = pd.read_parquet(DATA / "invocation_merged.parquet")
    fams_ic = sorted(set(pairs.loc[pairs.level.eq("K2"), "GENCONSETID"]))
    fam_rows, top_rows, reg_rows, tr_rows, ev_rows, pl_rows, key_rows = [], [], [], [], [], [], []
    regime_cols = ["season", "day_period", "tbin", "vbin", "rbin"]
    for (level, key, direction, kind), g in pairs.groupby(["level", "key", "direction", "kind"], dropna=False):
        if level not in ("K2", "K1", "K3", "K4", "K1xK2"):
            continue
        if level == "K2":
            fset = [key]
        elif level == "K1xK2":
            fset = [g.GENCONSETID.iat[0]]
        else:
            kr = keys_v1[(keys_v1.level == level) & (keys_v1.key == key) & (keys_v1.direction == direction)]
            fset = kr.families.iat[0].split("|") if len(kr) and isinstance(kr.families.iat[0], str) else []
        own = set().union(*[own_of.get(f, set()) for f in fset]) if fset else set()
        own_mask = layer.codes.isin(own)
        classes = classify(layer.codes, own, outage_members)
        row, top, unit = family_stats(layer, direction, g, own_mask, classes)
        base = {"ic": ic, "name": name, "direction": direction, "level": level, "key": key,
                "families": "|".join(fset), "layer": layer.name}
        if kind == "placebo":
            if level == "K2":
                pl_rows.append({**base, **{k: row[k] for k in ["n_units", "own_diff", "own_ci_lo", "own_ci_hi"]},
                                "placebo_clean": bool(np.isfinite(row["own_ci_lo"]) and row["own_ci_lo"] <= 0 <= row["own_ci_hi"])})
            continue
        if level != "K2":
            key_rows.append({**base, **row, "top3": "; ".join(f"{r.constraint} ({r.treated_share:.0%} vs {r.control_share:.0%})"
                                                             for r in top.sort_values("treated_share", ascending=False).head(3).itertuples()) if len(top) else ""})
            continue
        base["GENCONSETID"] = key
        base["tier"] = tiers.get((direction, key), "unsupported")
        fam_rows.append({**base, **row})
        if len(top):
            top_rows.append(top.assign(**base))
        # regimes
        uv = units_v1[(units_v1.direction == direction) & (units_v1.GENCONSETID == key)][["time"] + regime_cols]
        u = unit.merge(uv, on="time", how="left")
        for dim in regime_cols:
            for val, h in u.groupby(dim, dropna=False):
                reg_rows.append({**base, "dimension": dim, "value": str(int(val)) if isinstance(val, (int, float, np.integer, np.floating)) and pd.notna(val) else str(val), "n_units": len(h), "own_treated": h.t_own.mean(),
                                 "own_control": h.c_own.mean(), "own_diff": (h.t_own - h.c_own).mean(),
                                 "top_control_treated": h.get("t_top_control", pd.Series(dtype=float)).mean(),
                                 "top_control_control": h.get("c_top_control", pd.Series(dtype=float)).mean()})
        # transitions
        tr = transitions(layer, direction, GRID30.get_indexer(g.t_time.unique()))
        if len(tr):
            tr_rows.append(tr.assign(**base))
        # event study around invocation spells
        sp = merged[merged.GENCONSETID.eq(key)]
        sp = sp[(sp.end - sp.start) >= pd.Timedelta(hours=1)].copy()
        if as_of is not None:
            sp = sp[sp.end <= as_of - pd.Timedelta(days=21)]
        if len(sp):
            oth = merged[merged.GENCONSETID.isin(set(fams_ic) - {key})]
            os_, oe = oth.start.to_numpy(), oth.end.to_numpy()
            two = np.timedelta64(2, "h")
            sp["clean"] = [not ((np.abs(os_ - np.datetime64(r.start)) <= two).any() or (np.abs(oe - np.datetime64(r.start)) <= two).any()
                                or (np.abs(os_ - np.datetime64(r.end)) <= two).any() or (np.abs(oe - np.datetime64(r.end)) <= two).any())
                           for r in sp.itertuples()]
            code = layer.codes.get_loc(row["top1_control"]) if "top1_control" in row else None
            ev = event_profile(layer, direction, sp, own_mask, code)
            if len(ev):
                ev_rows.append(ev.assign(**base, top_control=row.get("top1_control")))
    out = {"family": pd.DataFrame(fam_rows), "topk": pd.concat(top_rows, ignore_index=True) if top_rows else pd.DataFrame(),
           "by_regime": pd.DataFrame(reg_rows), "transitions": pd.concat(tr_rows, ignore_index=True) if tr_rows else pd.DataFrame(),
           "event_study": pd.concat(ev_rows, ignore_index=True) if ev_rows else pd.DataFrame(),
           "placebo": pd.DataFrame(pl_rows), "keys": pd.DataFrame(key_rows)}
    if as_of is None:
        TABLES.mkdir(parents=True, exist_ok=True)
        for k, v in out.items():
            write_parquet(TABLES / f"{prefix}_{k}__{ic}.parquet", v if len(v) else pd.DataFrame({"empty": []}))
    return out


def build_setters(ics: list[str] | None = None) -> dict:
    ics = ics or list(IC)
    members, outage_members = membership()
    summary = {}
    for ic in ics:
        layer = setter_layer(ic)
        g = lead_gate(ic, layer, members)
        out = build_connector(ic, layer, "setter", members, outage_members)
        fam = out["family"]
        sup = fam[fam.tier.eq("supported")]
        summary[IC[ic]["name"]] = {"lead_gate": g, "family_directions": len(fam), "supported": len(sup),
                                   "median_own_treated_supported": float(sup.own_treated.median()) if len(sup) else None,
                                   "median_own_control_supported": float(sup.own_control.median()) if len(sup) else None,
                                   "key_rows": len(out["keys"]), "placebo_rows": len(out["placebo"]),
                                   "placebo_clean_share": float(out["placebo"].placebo_clean.mean()) if len(out["placebo"]) else None}
        print(IC[ic]["name"], summary[IC[ic]["name"]], flush=True)
    summary["pass"] = all(v["lead_gate"]["pass"] for v in summary.values() if isinstance(v, dict))
    return summary
