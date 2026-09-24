"""B3–B7: binding-layer tables (execution/nos_constraint_binding_v1/PLAN.md §5).

B3  family tables on the connector binding, near-binding and system (any binding scope equation) layers
B4  layer agreement: own set binds and/or sets the connector limit, five-minute joint shares
B5  cross-link footprint: any-binding lift on each target connector-direction (spillover runs + relevant families)
B6  as-known split: year-2 treated half-hours split by whether a linked outage was already in the NOS snapshot
    1 / 7 / 14 days before
B7  (see genonly.py) generator pressure on generator-only equations
MV  marginal-value summaries of own-set binding (Q10): fixed thresholds and the equation's own outage-free P90
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nemic.common import IC

from . import compare
from .binding import PANEL, binding_layer, panel_all
from .common import DATA, write_parquet
from .outlook import final_id, successor_map, week_dirs
from .pairs import BDATA
from .setters import TABLES, boot_mean, build_connector, classify, family_stats, membership, setter_frame
from .state import GRID5, GRID30

LAGS = [1, 7, 14]


def _pos5(half_hours: np.ndarray) -> np.ndarray:
    return (half_hours[:, None] * 6 + np.arange(6)[None, :]).ravel()


# --------------------------------------------------------------------------- B4
def agreement(ic: str, members: pd.DataFrame, pairs: pd.DataFrame, tiers: dict) -> pd.DataFrame:
    sf = setter_frame(ic)
    sf["pos"] = GRID5.get_indexer(sf.time)
    sf = sf[sf.pos >= 0]
    p = panel_all()
    fac = p[f"factor__{ic}"].astype(float)
    bp = p[p.binding & fac.notna() & fac.abs().gt(1e-8)].assign(direction=lambda d: np.where(d[f"factor__{ic}"] > 0, "forward", "reverse"))
    bp = bp.assign(pos=GRID5.get_indexer(bp.time))
    own_of = members.groupby("GENCONSETID").GENCONID.apply(set).to_dict()
    rows = []
    for (fam, direction), g in pairs[pairs.level.eq("K2") & pairs.kind.eq("actual")].groupby(["key", "direction"]):
        own = own_of.get(fam, set())
        s_pos = set(sf[(sf.direction == direction) & sf.constraint.isin(own)].pos)
        b_pos = set(bp[(bp.direction == direction) & bp.CONSTRAINTID.isin(own)].pos)
        has = set(sf[sf.direction == direction].pos)
        out = {"ic": ic, "name": IC[ic]["name"], "direction": direction, "GENCONSETID": fam, "tier": tiers.get((direction, fam))}
        for arm, col in [("treated", "t_time"), ("control", "c_time")]:
            hh = np.unique(GRID30.get_indexer(g[col]))
            pos = [x for x in _pos5(hh) if x in has]
            n = max(len(pos), 1)
            sset = np.array([x in s_pos for x in pos]); bset = np.array([x in b_pos for x in pos])
            out.update({f"{arm}_intervals": len(pos), f"{arm}_binds_and_sets": float((sset & bset).sum() / n),
                        f"{arm}_binds_only": float((bset & ~sset).sum() / n), f"{arm}_sets_only": float((sset & ~bset).sum() / n),
                        f"{arm}_neither": float((~sset & ~bset).sum() / n)})
        rows.append(out)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- B5
def footprint(ic: str, layer, members, outage_members, pairs: pd.DataFrame, fam_tiers: pd.DataFrame) -> pd.DataFrame:
    rows = []
    rel = pd.read_parquet(DATA / "set_relevance.parquet")
    rel_of = rel[rel.relevant].groupby("GENCONSETID").ic.apply(lambda s: "|".join(sorted(IC[i]["name"] for i in s)))
    spill = pd.concat([pd.read_parquet(DATA / "tables" / f"spillover__{ic}.parquet")]) if (DATA / "tables" / f"spillover__{ic}.parquet").exists() else pd.DataFrame()
    stiers = spill.set_index(["direction", "GENCONSETID"]).tier.to_dict() if len(spill) and "tier" in spill else {}
    own_of = members.groupby("GENCONSETID").GENCONID.apply(set).to_dict()
    for (level, fam, direction), g in pairs[pairs.kind.eq("actual") & pairs.level.isin(["K2", "spill"])].groupby(["level", "key", "direction"]):
        own = own_of.get(fam, set())
        row, _, _ = family_stats(layer, direction, g, layer.codes.isin(own), classify(layer.codes, own, outage_members), top_k=1)
        tier = fam_tiers.get((direction, fam)) if level == "K2" else stiers.get((direction, fam))
        rows.append({"target_ic": ic, "target_name": IC[ic]["name"], "direction": direction, "GENCONSETID": fam,
                     "relation": "relevant" if level == "K2" else "not relevant (spillover)", "relevant_to": rel_of.get(fam, ""),
                     "tier": tier, "n_units": row["n_units"], "any_binding_treated": row["any_treated"],
                     "any_binding_control": row["any_control"], "any_binding_diff": row["any_diff"],
                     "ci_lo": row["any_ci_lo"], "ci_hi": row["any_ci_hi"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- B6
def first_seen() -> pd.Series:
    """Earliest NOS report generation time at which each OUTAGEID (or a predecessor it resubmits) was present."""
    parts = []
    for w in week_dirs().itertuples():
        rows = pd.read_parquet(w.path / "rows.parquet")
        rows = rows[rows.table.eq("OUTAGEDETAIL")]
        oid = rows.fields_json.map(lambda s: json.loads(s).get("OUTAGEID"))
        ch = pd.read_parquet(w.path / "changes.parquet")
        ch = ch[ch.present].merge(pd.DataFrame({"row_id": rows.row_id, "OUTAGEID": oid.astype(str)}), on="row_id")
        parts.append(ch.groupby("OUTAGEID").generated_nem.min())
    fs = pd.concat(parts).groupby(level=0).min()
    succ = successor_map()
    chain = pd.Series({o: final_id(o, succ) for o in fs.index})
    # a resubmitted booking was known from its predecessor's first appearance
    by_final = fs.groupby(chain).min()
    return pd.Series({o: min(fs[o], by_final.get(chain[o], fs[o])) for o in fs.index}), fs.min()


def asknown(ic: str, layer, members, outage_members, pairs: pd.DataFrame, seen: pd.Series, first_report: pd.Timestamp,
            links: pd.DataFrame, tiers: dict) -> pd.DataFrame:
    own_of = members.groupby("GENCONSETID").GENCONID.apply(set).to_dict()
    rows = []
    act = pairs[pairs.level.eq("K2") & pairs.kind.eq("actual") & (pairs.t_time >= pd.Timestamp("2025-09-01"))]
    for (fam, direction), g in act.groupby(["key", "direction"]):
        l = links[links.GENCONSETID.eq(fam)]
        if l.empty:
            continue
        times = pd.DatetimeIndex(g.t_time.unique())
        s, e, o = l.start.to_numpy(), l.end.to_numpy(), l.OUTAGEID.astype(str).to_numpy()
        seen_o = np.array([seen.get(x, pd.NaT) for x in o], dtype="datetime64[ns]")
        for lag in LAGS:
            ref = times - pd.Timedelta(days=lag)
            known = ref >= first_report
            booked = np.zeros(len(times), bool)
            for j, t in enumerate(times.to_numpy()):
                cov = (s <= t) & (e + np.timedelta64(30, "m") >= t)
                booked[j] = bool((seen_o[cov] <= ref[j].to_datetime64()).any()) if cov.any() else False
            for grp, mask in [("booked_in_advance", known & booked), ("not_booked_in_advance", known & ~booked)]:
                sub = g[g.t_time.isin(times[mask])]
                if sub.empty:
                    continue
                own = own_of.get(fam, set())
                row, _, _ = family_stats(layer, direction, sub, layer.codes.isin(own), classify(layer.codes, own, outage_members), top_k=1)
                rows.append({"ic": ic, "name": IC[ic]["name"], "direction": direction, "GENCONSETID": fam, "tier": tiers.get((direction, fam)),
                             "lag_days": lag, "group": grp, "n_units": row["n_units"], "own_treated": row["own_treated"],
                             "own_control": row["own_control"], "own_diff": row["own_diff"], "any_diff": row["any_diff"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- MV
def mv_stats(ic: str, members, pairs: pd.DataFrame, tiers: dict) -> pd.DataFrame:
    p = panel_all()
    fac = p[f"factor__{ic}"].astype(float)
    bp = p[p.binding & fac.notna() & fac.abs().gt(1e-8)][["time", "CONSTRAINTID", "MARGINALVALUE", f"factor__{ic}"]].copy()
    bp["direction"] = np.where(bp[f"factor__{ic}"] > 0, "forward", "reverse")
    bp["absmv"] = bp.MARGINALVALUE.abs()
    bp["hh"] = GRID30.get_indexer(bp.time.dt.ceil("30min"))
    own_of = members.groupby("GENCONSETID").GENCONID.apply(set).to_dict()
    rows = []
    for (fam, direction), g in pairs[pairs.level.eq("K2") & pairs.kind.eq("actual")].groupby(["key", "direction"]):
        own = own_of.get(fam, set())
        b = bp[(bp.direction == direction) & bp.CONSTRAINTID.isin(own)]
        if b.empty:
            continue
        th = set(GRID30.get_indexer(g.t_time)); ch = set(GRID30.get_indexer(g.c_time))
        tb, cb = b[b.hh.isin(th)], b[b.hh.isin(ch)]
        p90 = b[~b.hh.isin(th)].groupby("CONSTRAINTID").absmv.quantile(.9)
        out = {"ic": ic, "name": IC[ic]["name"], "direction": direction, "GENCONSETID": fam, "tier": tiers.get((direction, fam))}
        for arm, x in [("treated", tb), ("control", cb)]:
            out.update({f"{arm}_binding_intervals": len(x), f"{arm}_median_abs_mv": float(x.absmv.median()) if len(x) else np.nan,
                        f"{arm}_share_gt_100": float((x.absmv > 100).mean()) if len(x) else np.nan,
                        f"{arm}_share_gt_1000": float((x.absmv > 1000).mean()) if len(x) else np.nan,
                        f"{arm}_share_gt_own_p90": float((x.absmv > x.CONSTRAINTID.map(p90)).mean()) if len(x) else np.nan})
        rows.append(out)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- orchestration
def build_binding_tables(ics: list[str] | None = None) -> dict:
    from .outlook import successor_map as _s  # noqa: F401  (import check)
    ics = ics or list(IC)
    members, outage_members = membership()
    all_rel = sorted(set(pd.read_parquet(DATA / "set_relevance.parquet").query("relevant").GENCONSETID))
    _, links = compare.spell_linkage(all_rel)
    seen, first_report = first_seen()
    summary = {}
    for ic in ics:
        pairs = pd.read_parquet(BDATA / f"pairs__{ic}.parquet")
        fam_eff = pd.read_parquet(DATA / "tables" / f"family_effects__{ic}.parquet")
        tiers = fam_eff.set_index(["direction", "GENCONSETID"]).tier.to_dict()
        res = {}
        for kind in ["binding", "near", "system"]:
            layer = binding_layer(ic, kind)
            out = build_connector(ic, layer, kind, members, outage_members)
            res[kind] = len(out["family"])
            if kind == "binding":
                fp = footprint(ic, layer, members, outage_members, pairs, tiers)
                write_parquet(TABLES / f"footprint__{ic}.parquet", fp)
                ak = asknown(ic, layer, members, outage_members, pairs, seen, first_report, links, tiers)
                write_parquet(TABLES / f"asknown__{ic}.parquet", ak if len(ak) else pd.DataFrame({"empty": []}))
                res["footprint"], res["asknown"] = len(fp), len(ak)
        ag = agreement(ic, members, pairs, tiers)
        write_parquet(TABLES / f"agreement__{ic}.parquet", ag)
        mv = mv_stats(ic, members, pairs, tiers)
        write_parquet(TABLES / f"mv__{ic}.parquet", mv if len(mv) else pd.DataFrame({"empty": []}))
        res["agreement"], res["mv"] = len(ag), len(mv)
        summary[IC[ic]["name"]] = res
        print(IC[ic]["name"], res, flush=True)
    return summary
