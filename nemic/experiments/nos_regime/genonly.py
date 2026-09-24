"""B0b + B7: definitions of set equations versioned before the window, and generator pressure on generator-only
equations (execution/nos_constraint_binding_v1/PLAN.md §5, Q9/Q18).

B0b  Relevant-set member equations with no definition rows in the 2024-09..2026-08 monthly archives were versioned
     earlier. Their version dates come from the binding panel (GENCONID_EFFECTIVEDATE); GENCONDATA,
     SPDINTERCONNECTORCONSTRAINT and SPDCONNECTIONPOINTCONSTRAINT are read from the monthly archives of those dates
     (and the following month), filtered to these equations. An equation is generator-only when no version has a
     term for any of the six connectors.
B7   For generator-only equations with ENERGY connection-point factors: per DUID, slack consumed
     bᵢ × (Pᵢ[t] − Pᵢ[t−30 min]) at five minutes, sign flipped for ≥ constraints, so positive = tightening.
     Treated = half-hours with the owning family invoked (matched units); base = same-month half-hours with the
     family not invoked. Descriptive decomposition, not causal attribution.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from nemic.common import IC
from nemic.constraint_ingest import _table_rows

from .binding import LOAD, RAW, STAND, fetch, panel_all
from .common import DATA, MONTHS, sha256, write_json, write_parquet
from .pairs import BDATA
from .state import GRID30

BACKFILL = STAND / "backfill"


def undefined_equations() -> pd.DataFrame:
    scope = pd.read_parquet(BDATA / "equation_scope.parquet")
    gd = pd.read_parquet(STAND / "GENCONDATA.parquet", columns=["GENCONID"])
    und = scope[scope.set_member & ~scope.CONSTRAINTID.isin(set(gd.GENCONID))]
    return und


def backfill() -> dict:
    und = undefined_equations()
    ids = set(und.CONSTRAINTID)
    p = panel_all()
    v = p[p.CONSTRAINTID.isin(ids)][["CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"]].drop_duplicates()
    months = sorted({m for d in v.EFFECTIVEDATE.dropna() for m in (pd.Period(d, "M"), pd.Period(d, "M") + 1)})
    BACKFILL.mkdir(parents=True, exist_ok=True)
    sources, frames = [], {t: [] for t in ["GENCONDATA", "SPDINTERCONNECTORCONSTRAINT", "SPDCONNECTIONPOINTCONSTRAINT"]}
    for m in months:
        for table in frames:
            try:
                path = fetch(m, table, sources)
            except Exception as exc:                       # archive absent for that month
                sources.append({"month": str(m), "table": table, "error": str(exc)[:200]})
                continue
            frames[table].append(_table_rows(path, table, value_filter=lambda r: r.get("GENCONID") in ids))
            path.unlink()
    for table, parts in frames.items():
        f = pd.concat(parts, ignore_index=True).drop_duplicates() if parts else pd.DataFrame()
        write_parquet(BACKFILL / f"{table}.parquet", f if len(f) else pd.DataFrame({"GENCONID": []}))
    spdic = pd.concat([pd.read_parquet(STAND / "SPDINTERCONNECTORCONSTRAINT.parquet"),
                       pd.read_parquet(BACKFILL / "SPDINTERCONNECTORCONSTRAINT.parquet")], ignore_index=True)
    gd = pd.concat([pd.read_parquet(STAND / "GENCONDATA.parquet"), pd.read_parquet(BACKFILL / "GENCONDATA.parquet")], ignore_index=True)
    ic_term = spdic[spdic.get("INTERCONNECTORID", pd.Series(dtype=str)).isin(IC)].groupby("GENCONID").INTERCONNECTORID \
        .apply(lambda s: "|".join(sorted(set(s))))
    scope = pd.read_parquet(BDATA / "equation_scope.parquet")
    scope["ic_term"] = scope.CONSTRAINTID.map(ic_term).fillna("")
    scope["defined"] = scope.CONSTRAINTID.isin(set(gd.GENCONID))
    scope["gen_only"] = scope.set_member & scope.defined & scope.ic_term.eq("")
    scope["undefined_member"] = scope.set_member & ~scope.defined
    write_parquet(BDATA / "equation_scope.parquet", scope)
    res = {"undefined_before": len(ids), "versions_seen_in_panel": int(v.CONSTRAINTID.nunique()), "archive_months": [str(m) for m in months],
           "defined_after": int(scope[scope.CONSTRAINTID.isin(ids)].defined.sum()),
           "with_ic_term_after": int((scope.CONSTRAINTID.isin(ids) & scope.ic_term.ne("")).sum()),
           "gen_only": int(scope.gen_only.sum()), "still_undefined": int(scope.undefined_member.sum()),
           "never_binding_in_window": sorted(ids - set(v.CONSTRAINTID))[:200], "sources": sources}
    write_json(BDATA / "backfill.json", res)
    return {k: v for k, v in res.items() if k not in ("sources", "never_binding_in_window")}


def _factors() -> pd.DataFrame:
    cp = pd.concat([pd.read_parquet(STAND / "SPDCONNECTIONPOINTCONSTRAINT.parquet"),
                    pd.read_parquet(BACKFILL / "SPDCONNECTIONPOINTCONSTRAINT.parquet")], ignore_index=True)
    if cp.empty or "BIDTYPE" not in cp:
        return pd.DataFrame()
    cp = cp[cp.BIDTYPE.eq("ENERGY")].copy()
    cp["FACTOR"] = pd.to_numeric(cp.FACTOR, errors="coerce")
    cp["EFFECTIVEDATE"] = pd.to_datetime(cp.EFFECTIVEDATE, errors="coerce")
    cp["VERSIONNO"] = pd.to_numeric(cp.VERSIONNO, errors="coerce")
    last = cp.sort_values(["EFFECTIVEDATE", "VERSIONNO"]).groupby("GENCONID")[["EFFECTIVEDATE", "VERSIONNO"]].last().reset_index()
    cp = cp.merge(last, on=["GENCONID", "EFFECTIVEDATE", "VERSIONNO"])
    du = pd.read_parquet(STAND / "DUDETAILSUMMARY.parquet")[["DUID", "CONNECTIONPOINTID"]].drop_duplicates()
    return cp.merge(du, on="CONNECTIONPOINTID")[["GENCONID", "DUID", "FACTOR"]].drop_duplicates()


def pressure() -> dict:
    scope = pd.read_parquet(BDATA / "equation_scope.parquet")
    gen = scope[scope.get("gen_only", False) == True]  # noqa: E712
    fac = _factors()
    fac = fac[fac.GENCONID.isin(set(gen.CONSTRAINTID))] if len(fac) else fac
    if fac.empty:
        write_parquet(BDATA / "tables" / "genonly_pressure.parquet", pd.DataFrame({"empty": []}))
        return {"gen_only_equations": len(gen), "with_energy_factors": 0}
    gd = pd.concat([pd.read_parquet(STAND / "GENCONDATA.parquet"), pd.read_parquet(BACKFILL / "GENCONDATA.parquet")])
    ctype = gd.dropna(subset=["CONSTRAINTTYPE"]).groupby("GENCONID").CONSTRAINTTYPE.last().to_dict()
    duids = sorted(set(fac.DUID))
    parts = [pq.read_table(LOAD / f"{m}.parquet", filters=[("DUID", "in", duids)]).to_pandas() for m in MONTHS
             if (LOAD / f"{m}.parquet").exists()]
    mw = pd.concat(parts).pivot_table(index="time", columns="DUID", values="TOTALCLEARED").sort_index()
    mw = mw.reindex(pd.date_range(mw.index.min(), mw.index.max(), freq="5min"))
    dmw = mw - mw.shift(6)
    cov = pd.read_parquet(DATA / "family_coverage_30min.parquet")
    members = scope[scope.CONSTRAINTID.isin(set(fac.GENCONID))][["CONSTRAINTID", "relevant_sets"]]
    rows = []
    for eq, sets_ in zip(members.CONSTRAINTID, members.relevant_sets):
        f = fac[fac.GENCONID.eq(eq)]
        sign = -1.0 if str(ctype.get(eq, "<=")).strip() == ">=" else 1.0
        contrib = dmw[f.DUID].mul(f.set_index("DUID").FACTOR.reindex(f.DUID).to_numpy() * sign, axis=1)
        hh = contrib.index.ceil("30min")
        tight = contrib.clip(lower=0).groupby(hh).sum(); relief = (-contrib).clip(lower=0).groupby(hh).sum()
        for fam in [s for s in sets_.split("|") if s and s in cov.columns]:
            c = cov[fam].reindex(tight.index)
            on, off = c.eq(6), c.eq(0)
            months_on = set(tight.index[on].to_period("M"))
            base = off & tight.index.to_period("M").isin(months_on)
            if on.sum() == 0:
                continue
            for duid in f.DUID:
                rows.append({"GENCONSETID": fam, "equation": eq, "constraint_type": ctype.get(eq), "DUID": duid,
                             "factor": float(f.loc[f.DUID.eq(duid), "FACTOR"].iat[0]),
                             "tightening_per_hh_treated": float(tight.loc[on, duid].mean()), "tightening_per_hh_base": float(tight.loc[base, duid].mean()),
                             "relief_per_hh_treated": float(relief.loc[on, duid].mean()), "relief_per_hh_base": float(relief.loc[base, duid].mean()),
                             "treated_half_hours": int(on.sum()), "base_half_hours": int(base.sum())})
    out = pd.DataFrame(rows)
    if len(out):
        out["excess_tightening"] = out.tightening_per_hh_treated - out.tightening_per_hh_base
        out["excess_relief"] = out.relief_per_hh_treated - out.relief_per_hh_base
    write_parquet(BDATA / "tables" / "genonly_pressure.parquet", out if len(out) else pd.DataFrame({"empty": []}))
    return {"gen_only_equations": len(gen), "with_energy_factors": int(fac.GENCONID.nunique()), "duids": len(duids), "rows": len(out)}
