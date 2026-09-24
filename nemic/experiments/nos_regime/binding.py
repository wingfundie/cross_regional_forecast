"""Phase B: published binding during NOS outages (execution/nos_constraint_binding_v1/PLAN.md §5, B0–B2, B7 inputs).

B0  standing tables (SPDINTERCONNECTORCONSTRAINT, SPDCONNECTIONPOINTCONSTRAINT, GENCONDATA) re-read from the MMSDM
    monthly archives and filtered to the equation scope: the six connectors' dependency constraint IDs plus every member
    equation of a relevant outage set. DUDETAILSUMMARY comes from the QNI study's retained archives.
B1  per month: DISPATCHCONSTRAINT and DISPATCHLOAD archives (the same NEM-wide archives the constraint studies used),
    SHA-256 checked against the QNI study ledger, filtered, reduced, then deleted.
B2  sparse binding panel: rows that bind (|MARGINALVALUE| > 1e-9) or near-bind (IC-normalised slack 0–50 MW on any of
    the six connectors). Run selection follows nemic/constraint_features._physical (last of INTERVENTION, RUNNO,
    LASTCHANGED per interval and constraint), exactly as the regime report, so monthly counts reconcile with each
    study's constraint_population_summary.
"""
from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd

from nemic.common import IC
from nemic.constraint_ingest import _table_rows, download_entry

from .common import DATA, MONTHS, ROOT, STUDY, sha256, write_json, write_parquet
from .pairs import BDATA
from .state import set_members

RAW = BDATA / "raw"
STAND = BDATA / "standing"
PANEL = BDATA / "binding_panel"
LOAD = BDATA / "dispatchload"
LEDGER = ROOT / "data" / "constraint_qni_2y" / "ledger.sqlite"
LIMITS = {"file_compressed_bytes": 600_000_000, "batch_decompressed_bytes": 6_000_000_000}
NEAR_MW = 50.0
DC_KEEP = ["SETTLEMENTDATE", "RUNNO", "CONSTRAINTID", "RHS", "LHS", "MARGINALVALUE", "VIOLATIONDEGREE", "INTERVENTION",
           "LASTCHANGED", "GENCONID_EFFECTIVEDATE", "GENCONID_VERSIONNO"]
DL_KEEP = ["SETTLEMENTDATE", "RUNNO", "DUID", "INTERVENTION", "INITIALMW", "TOTALCLEARED", "LASTCHANGED"]
STANDING_TABLES = ["SPDINTERCONNECTORCONSTRAINT", "SPDCONNECTIONPOINTCONSTRAINT", "GENCONDATA"]


def archive_url(month: pd.Period, table: str) -> str:
    y, m = month.year, f"{month.month:02d}"
    return (f"https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{y}/MMSDM_{y}_{m}/MMSDM_Historical_Data_SQLLoader/"
            f"DATA/PUBLIC_ARCHIVE%23{table}%23FILE01%23{y}{m}010000.zip")


def expected_sha(url: str) -> str | None:
    with sqlite3.connect(LEDGER) as db:
        r = db.execute("select sha256 from files where url=?", (url,)).fetchone()
    return r[0] if r else None


def fetch(month: pd.Period, table: str, sources: list):
    url = archive_url(month, table)
    path = download_entry({"url": url}, LIMITS, RAW)
    digest = sha256(path)
    exp = expected_sha(url)
    sources.append({"month": str(month), "table": table, "url": url, "bytes": path.stat().st_size, "sha256": digest,
                    "ledger_sha256": exp, "hash_match": exp == digest if exp else None})
    if exp and exp != digest:
        raise RuntimeError(f"SHA-256 mismatch against constraint-study ledger: {url}")
    return path


def _num(frame: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in frame:
            frame[c] = pd.to_numeric(frame[c], errors="coerce")
    return frame


def physical(frame: pd.DataFrame, key: str) -> pd.DataFrame:
    """Same run selection as nemic.constraint_features._physical."""
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame.SETTLEMENTDATE, errors="coerce")
    _num(frame, ["INTERVENTION", "RUNNO"])
    frame["LASTCHANGED"] = pd.to_datetime(frame.LASTCHANGED, errors="coerce")
    return (frame.sort_values(["time", key, "INTERVENTION", "RUNNO", "LASTCHANGED"])
            .drop_duplicates(["time", key], keep="last"))


# --------------------------------------------------------------------------- B0
def dependency_ids() -> dict[str, set]:
    out = {}
    for ic, study in STUDY.items():
        d = json.loads((ROOT / f"data/constraint_{study}_2y/standing/dependencies.json").read_text())
        out[ic] = set(d["constraint_ids"])
    return out


def relevant_members() -> pd.DataFrame:
    rel = pd.read_parquet(DATA / "set_relevance.parquet")
    fams = set(rel.loc[rel.relevant, "GENCONSETID"])
    m = set_members()
    return m[m.GENCONSETID.isin(fams)]


def build_scope() -> dict:
    STAND.mkdir(parents=True, exist_ok=True)
    deps = dependency_ids()
    members = relevant_members()
    scope_ids = set().union(*deps.values()) | set(members.GENCONID)
    sources = []
    frames = {t: [] for t in STANDING_TABLES}
    for month in MONTHS:
        for table in STANDING_TABLES:
            path = fetch(month, table, sources)
            f = _table_rows(path, table, value_filter=lambda r: r.get("GENCONID") in scope_ids)
            frames[table].append(f)
            path.unlink()
    for table, parts in frames.items():
        write_parquet(STAND / f"{table}.parquet", pd.concat(parts, ignore_index=True).drop_duplicates())
    # DUDETAILSUMMARY: retained unfiltered archives of the QNI study
    du = []
    for p in sorted((ROOT / "data/constraint_qni_2y/raw").glob("PUBLIC_ARCHIVE#DUDETAILSUMMARY#*.zip")):
        du.append(_table_rows(p, "DUDETAILSUMMARY", keep=["DUID", "START_DATE", "END_DATE", "CONNECTIONPOINTID", "REGIONID",
                                                            "DISPATCHTYPE"]))
    write_parquet(STAND / "DUDETAILSUMMARY.parquet", pd.concat(du, ignore_index=True).drop_duplicates())
    spdic = pd.read_parquet(STAND / "SPDINTERCONNECTORCONSTRAINT.parquet")
    ic_term = spdic[spdic.INTERCONNECTORID.isin(IC)].groupby("GENCONID").INTERCONNECTORID.apply(lambda s: "|".join(sorted(set(s))))
    rows = []
    member_of = members.groupby("GENCONID").GENCONSETID.apply(lambda s: "|".join(sorted(set(s))))
    for c in sorted(scope_ids):
        rows.append({"CONSTRAINTID": c, "dependency_of": "|".join(sorted(i for i, s in deps.items() if c in s)),
                     "ic_term": ic_term.get(c, ""), "relevant_sets": member_of.get(c, "")})
    scope = pd.DataFrame(rows)
    scope["set_member"] = scope.relevant_sets.ne("")
    scope["gen_only"] = scope.set_member & scope.ic_term.eq("")
    write_parquet(BDATA / "equation_scope.parquet", scope)
    cp = pd.read_parquet(STAND / "SPDCONNECTIONPOINTCONSTRAINT.parquet")
    du = pd.read_parquet(STAND / "DUDETAILSUMMARY.parquet")
    gen = set(scope.loc[scope.gen_only, "CONSTRAINTID"])
    gen_cp = cp[cp.GENCONID.isin(gen)]
    duids = sorted(set(du[du.CONNECTIONPOINTID.isin(set(gen_cp.CONNECTIONPOINTID))].DUID))
    write_json(BDATA / "scope.json", {"scope_equations": len(scope), "dependency_equations": int(scope.dependency_of.ne("").sum()),
                                      "set_member_equations": int(scope.set_member.sum()), "gen_only_equations": len(gen),
                                      "gen_only_with_factors": int(gen_cp.GENCONID.nunique()), "gen_only_duids": duids,
                                      "sources": sources})
    return {"scope": len(scope), "gen_only": len(gen), "gen_only_duids": len(duids),
            "hash_matches": sum(bool(s["hash_match"]) for s in sources), "files": len(sources)}


# --------------------------------------------------------------------------- B1/B2
def ic_factors() -> pd.DataFrame:
    f = pd.read_parquet(STAND / "SPDINTERCONNECTORCONSTRAINT.parquet")
    f = _num(f[f.INTERCONNECTORID.isin(IC)].copy(), ["FACTOR", "VERSIONNO"])
    f["EFFECTIVEDATE"] = pd.to_datetime(f.EFFECTIVEDATE, errors="coerce")
    return (f[["INTERCONNECTORID", "GENCONID", "EFFECTIVEDATE", "VERSIONNO", "FACTOR"]].drop_duplicates()
            .rename(columns={"GENCONID": "CONSTRAINTID"}))


def month_panel(dc: pd.DataFrame, month: pd.Period, factors: pd.DataFrame, deps: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start, end = month.start_time, month.end_time.floor("5min")
    s = physical(dc, "CONSTRAINTID")
    s = s[s.time.between(start, end)].copy()
    _num(s, ["RHS", "LHS", "MARGINALVALUE", "VIOLATIONDEGREE", "GENCONID_VERSIONNO"])
    s["EFFECTIVEDATE"] = pd.to_datetime(s.GENCONID_EFFECTIVEDATE, errors="coerce")
    s["VERSIONNO"] = s.GENCONID_VERSIONNO
    s["binding"] = s.MARGINALVALUE.abs().gt(1e-9)
    near_any = np.zeros(len(s), bool)
    recon = []
    for ic in IC:
        fac = factors[factors.INTERCONNECTORID.eq(ic)].drop(columns="INTERCONNECTORID")
        j = s[["CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"]].merge(fac, on=["CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"], how="left")
        a = j.FACTOR.to_numpy(float)
        slack = (s.RHS.to_numpy(float) - s.LHS.to_numpy(float)) / np.abs(a)
        s[f"factor__{ic}"] = a.astype("float32")
        s[f"slack__{ic}"] = slack.astype("float32")
        near = (slack >= 0) & (slack <= NEAR_MW)
        near_any |= near
        dep = s.CONSTRAINTID.isin(deps[ic]).to_numpy()
        g = pd.DataFrame({"CONSTRAINTID": s.CONSTRAINTID[dep], "binding": s.binding[dep], "near": near[dep]})
        r = g.groupby("CONSTRAINTID").agg(binding_intervals=("binding", "sum"), near_binding_intervals=("near", "sum"),
                                          applicable_intervals=("binding", "size")).reset_index()
        recon.append(r.assign(ic=ic, month=str(month)))
    keep = s.binding.to_numpy() | near_any
    cols = ["time", "CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO", "RHS", "LHS", "MARGINALVALUE", "VIOLATIONDEGREE", "INTERVENTION",
            "binding"] + [c for c in s.columns if c.startswith(("factor__", "slack__"))]
    panel = s.loc[keep, cols].reset_index(drop=True)
    # interval availability (any scope row at that interval) for layer denominators, and equation presence
    avail = pd.DataFrame({"time": s.time.drop_duplicates().sort_values().to_numpy()})
    presence = s.groupby("CONSTRAINTID").agg(intervals=("time", "size"), first=("time", "min"), last=("time", "max"),
                                             binding_intervals=("binding", "sum")).reset_index()
    write_parquet(PANEL / f"presence__{month}.parquet", presence.assign(month=str(month)))
    return panel, pd.concat(recon, ignore_index=True), avail


def acquire_month(month: pd.Period, scope_ids: set, gen_duids: set, factors, deps) -> dict:
    out = PANEL / f"{month}.parquet"
    if out.exists() and (LOAD / f"{month}.parquet").exists():
        return {"month": str(month), "status": "cached"}
    sources = []
    PANEL.mkdir(parents=True, exist_ok=True)
    dc_path = fetch(month, "DISPATCHCONSTRAINT", sources)
    dc = _table_rows(dc_path, "DISPATCHCONSTRAINT", keep=DC_KEEP,
                     value_filter=lambda r: r.get("CONSTRAINTID", r.get("GENCONID")) in scope_ids)
    panel, recon, avail = month_panel(dc, month, factors, deps)
    dl_path = fetch(month, "DISPATCHLOAD", sources)
    # All DUIDs are kept (MW only): generator-only equations are classified after definitions are back-filled (B0b)
    dl = _table_rows(dl_path, "DISPATCHLOAD", keep=DL_KEEP)
    if len(dl):
        dl = physical(dl, "DUID")
        dl = _num(dl, ["INITIALMW", "TOTALCLEARED"])
        dl = dl[dl.time.between(month.start_time, month.end_time.floor("5min"))][["time", "DUID", "TOTALCLEARED"]]
        dl["TOTALCLEARED"] = dl.TOTALCLEARED.astype("float32")
    PANEL.mkdir(parents=True, exist_ok=True); LOAD.mkdir(parents=True, exist_ok=True)
    write_parquet(PANEL / f"recon__{month}.parquet", recon)
    write_parquet(PANEL / f"avail__{month}.parquet", avail)
    write_parquet(LOAD / f"{month}.parquet", dl)
    write_parquet(out, panel)
    for p in (dc_path, dl_path):
        p.unlink()
    info = {"month": str(month), "status": "complete", "dc_rows_scope": len(dc), "panel_rows": len(panel),
            "binding_rows": int(panel.binding.sum()), "dl_rows": len(dl), "sources": sources}
    write_json(PANEL / f"meta__{month}.json", info)
    return info


def acquire(months: list[str] | None = None) -> dict:
    scope = pd.read_parquet(BDATA / "equation_scope.parquet")
    meta = json.loads((BDATA / "scope.json").read_text())
    scope_ids, gen_duids = set(scope.CONSTRAINTID), set(meta["gen_only_duids"])
    factors, deps = ic_factors(), dependency_ids()
    todo = [pd.Period(m, "M") for m in months] if months else list(MONTHS)
    res = []
    for m in todo:
        r = acquire_month(m, scope_ids, gen_duids, factors, deps)
        print(json.dumps({k: v for k, v in r.items() if k != "sources"}), flush=True)
        res.append(r)
    return {"months": len(res), "complete": sum(r["status"] in ("complete", "cached") for r in res)}


def reconcile() -> dict:
    """B2 gate: binding / near-binding counts per connector, month and CONSTRAINTID equal the constraint studies'."""
    rows = []
    for ic, study in STUDY.items():
        for month in MONTHS:
            p = PANEL / f"recon__{month}.parquet"
            if not p.exists():
                continue
            mine = pd.read_parquet(p)
            mine = mine[mine.ic.eq(ic)]
            ref = pd.read_parquet(ROOT / f"data/constraint_{study}_2y/months/{month}/constraint_population_summary.parquet")
            ref = ref.groupby("CONSTRAINTID")[["binding_intervals", "near_binding_intervals", "applicable_intervals"]].sum().reset_index()
            m = ref.merge(mine, on="CONSTRAINTID", how="outer", suffixes=("_ref", "_new")).fillna(0)
            rows.append({"ic": ic, "month": str(month),
                         "binding_ref": int(m.binding_intervals_ref.sum()), "binding_new": int(m.binding_intervals_new.sum()),
                         "near_ref": int(m.near_binding_intervals_ref.sum()), "near_new": int(m.near_binding_intervals_new.sum()),
                         "applicable_ref": int(m.applicable_intervals_ref.sum()), "applicable_new": int(m.applicable_intervals_new.sum()),
                         "constraint_binding_mismatches": int((m.binding_intervals_ref != m.binding_intervals_new).sum()),
                         "constraint_near_mismatches": int((m.near_binding_intervals_ref != m.near_binding_intervals_new).sum())})
    r = pd.DataFrame(rows)
    write_parquet(BDATA / "binding_reconciliation.parquet", r)
    ok = bool(len(r) and (r.constraint_binding_mismatches == 0).all() and (r.constraint_near_mismatches == 0).all())
    return {"rows": len(r), "binding_exact": bool((r.constraint_binding_mismatches == 0).all()) if len(r) else None,
            "near_exact": bool((r.constraint_near_mismatches == 0).all()) if len(r) else None, "pass": ok,
            "binding_total_ref": int(r.binding_ref.sum()) if len(r) else 0, "binding_total_new": int(r.binding_new.sum()) if len(r) else 0}


# --------------------------------------------------------------------------- layers for B3+
_PANEL_CACHE: pd.DataFrame | None = None


def panel_months() -> list:
    return sorted(p.stem for p in PANEL.glob("20*.parquet"))


def panel_all() -> pd.DataFrame:
    global _PANEL_CACHE
    if _PANEL_CACHE is None:
        months = panel_months()
        if len(months) < len(MONTHS):
            raise FileNotFoundError(f"binding panel incomplete: {len(months)}/{len(MONTHS)} months")
        _PANEL_CACHE = pd.concat([pd.read_parquet(PANEL / f"{m}.parquet") for m in months], ignore_index=True)
    return _PANEL_CACHE


def avail5() -> np.ndarray:
    from .state import GRID5
    t = pd.concat([pd.read_parquet(PANEL / f"avail__{m}.parquet") for m in panel_months()]).time
    a = np.zeros(len(GRID5), bool)
    pos = GRID5.get_indexer(t)
    a[pos[pos >= 0]] = True
    return a


def eq_types() -> dict:
    g = pd.read_parquet(STAND / "GENCONDATA.parquet", columns=["GENCONID", "LIMITTYPE"]).dropna()
    return g.groupby("GENCONID").LIMITTYPE.agg(lambda s: s.mode().iat[0]).to_dict()


def binding_layer(ic: str, kind: str = "binding"):
    """Connector-direction layer: equations with an IC term for ``ic`` (direction by factor sign) that bind
    (kind='binding') or near-bind (kind='near'). kind='system' keeps every binding scope equation for both directions."""
    from .setters import build_layer
    p = panel_all()
    a = avail5()
    if kind == "system":
        f = p[p.binding][["time", "CONSTRAINTID"]]
        frame = pd.concat([f.assign(direction=d) for d in ("forward", "reverse")]).rename(columns={"CONSTRAINTID": "constraint"})
    else:
        fac = p[f"factor__{ic}"].astype(float)
        has = fac.notna() & fac.abs().gt(1e-8)
        if kind == "binding":
            sel = has & p.binding
        else:
            sl = p[f"slack__{ic}"].astype(float)
            sel = has & sl.between(0, NEAR_MW)
        f = p.loc[sel, ["time", "CONSTRAINTID"]].assign(direction=np.where(fac[sel] > 0, "forward", "reverse"))
        frame = f.rename(columns={"CONSTRAINTID": "constraint"})
    types = eq_types()
    frame["eq_type"] = frame.constraint.map(types)
    return build_layer(frame, kind, avail5={"forward": a, "reverse": a})
