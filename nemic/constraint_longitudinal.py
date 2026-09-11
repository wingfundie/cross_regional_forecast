"""Resumable, storage-bounded multi-month interconnector constraint study."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import unquote, urlparse

import numpy as np
import pandas as pd
import requests

from .common import DATA, PROCESSED, ROOT, dump, session
from .constraint_features import build as build_features
from .constraint_ingest import _table_rows, download_entry, sha256
from .vni_influence_study import run as run_influence

CONFIG = ROOT / "configs" / "constraint_vni_2y.json"


def load_study(path=CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"experiment_id", "interconnector", "start", "end", "standing_start",
                "output_dir", "standing_tables_dir", "raw_cache_dir", "limits",
                "static_tables", "interval_tables"}
    missing = required - set(config)
    if missing:
        raise ValueError(f"Missing study configuration keys: {sorted(missing)}")
    if int(config["limits"]["study_disk_bytes"]) != 10_000_000_000:
        raise ValueError("The approved VNI study disk budget must be exactly 10 GB")
    if config["interconnector"] != "VIC1-NSW1":
        raise ValueError("This initial longitudinal execution is restricted to VNI")
    if pd.Timestamp(config["standing_start"]) != pd.Timestamp(config["start"]):
        raise ValueError("Standing-data acquisition must use the same two-year start as the study")
    return config


def study_root(config):
    return (DATA / config["output_dir"]).resolve()


def archive_url(month, table):
    stamp = f"{month.year:04d}{month.month:02d}010000"
    return (f"https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{month.year:04d}/"
            f"MMSDM_{month.year:04d}_{month.month:02d}/MMSDM_Historical_Data_SQLLoader/DATA/"
            f"PUBLIC_ARCHIVE%23{table}%23FILE01%23{stamp}.zip")


def months_between(start, end):
    return list(pd.period_range(pd.Timestamp(start).to_period("M"), pd.Timestamp(end).to_period("M"), freq="M"))


def path_bytes(path):
    path = Path(path)
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def assert_storage(config, reserve=0):
    root = study_root(config)
    used = path_bytes(root)
    budget = int(config["limits"]["study_disk_bytes"])
    free = shutil.disk_usage(root.parent).free
    if used + int(reserve) > budget:
        raise RuntimeError(f"Study storage guard: {used:,} used + {reserve:,} reserved > {budget:,}")
    if free - int(reserve) < int(config["limits"]["min_free_bytes"]):
        raise RuntimeError("Study storage guard: insufficient free disk after reservation")
    return used, free


def connect(config):
    root = study_root(config)
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "ledger.sqlite")
    db.execute("""create table if not exists months(
        month text primary key, status text not null, started_at text, completed_at text,
        rows_constraints integer, rows_dispatch integer, output_bytes integer, message text)""")
    db.execute("""create table if not exists files(
        url text primary key, month text, table_name text, phase text, bytes integer,
        sha256 text, status text, removed integer default 0)""")
    db.commit()
    return db


def remote_size(url):
    response = session().head(url, timeout=(20, 90), allow_redirects=True)
    response.raise_for_status()
    value = response.headers.get("Content-Length")
    if value is None:
        raise RuntimeError(f"NEMWEB did not provide Content-Length for {url}")
    return int(value)


def entry(config, month, table, phase):
    url = archive_url(month, table)
    raw = DATA / config["raw_cache_dir"]
    name = unquote(urlparse(url).path.rsplit("/", 1)[-1])
    cached = raw / name
    size = cached.stat().st_size if cached.exists() else remote_size(url)
    if size > int(config["limits"]["file_compressed_bytes"]):
        raise RuntimeError(f"Archive exceeds per-file cap: {name} ({size:,})")
    return {"table": table, "phase": phase, "expected_bytes": size, "url": url}


def fetch(config, month, table, phase, db):
    item = entry(config, month, table, phase)
    assert_storage(config, item["expected_bytes"])
    raw = DATA / config["raw_cache_dir"]
    path = download_entry(item, config["limits"], raw)
    digest = sha256(path)
    db.execute("insert or replace into files(url,month,table_name,phase,bytes,sha256,status,removed) values(?,?,?,?,?,?,?,0)",
               (item["url"], str(month), table, phase, path.stat().st_size, digest, "verified"))
    db.commit()
    assert_storage(config)
    return path, item


def build_standing(config, db):
    root = study_root(config)
    standing = DATA / config["standing_tables_dir"]
    marker = standing / "standing_audit.json"
    if marker.exists():
        return json.loads(marker.read_text(encoding="utf-8"))
    standing.mkdir(parents=True, exist_ok=True)
    months = months_between(config["standing_start"], config["end"])
    raw_paths = {table: [] for table in config["static_tables"]}
    manifest, absent = [], []
    for month in months:
        for table in config["static_tables"]:
            try:
                path, item = fetch(config, month, table, "standing", db)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    absent.append({"month": str(month), "table": table, "url": archive_url(month, table)})
                    continue
                raise
            raw_paths[table].append(path)
            manifest.append({**item, "bytes": path.stat().st_size, "sha256": sha256(path)})

    # First establish every directly linked VNI constraint, then filter large
    # factor tables to that dependency set plus observed setters.
    ic_parts = [_table_rows(path, "SPDINTERCONNECTORCONSTRAINT") for path in raw_paths["SPDINTERCONNECTORCONSTRAINT"]]
    ic = pd.concat(ic_parts, ignore_index=True).drop_duplicates()
    direct = set(ic.loc[ic.INTERCONNECTORID.eq(config["interconnector"]), "GENCONID"].dropna())
    observed = pd.read_parquet(PROCESSED / "ic_5min.parquet", columns=["time", "INTERCONNECTORID", "EXPORTGENCONID", "IMPORTGENCONID"])
    observed = observed[observed.INTERCONNECTORID.eq(config["interconnector"])
                        & observed.time.between(pd.Timestamp(config["start"]), pd.Timestamp(config["end"]))]
    setters = set(observed.EXPORTGENCONID.dropna()) | set(observed.IMPORTGENCONID.dropna())
    ids = sorted(direct | setters)
    ic = ic[ic.GENCONID.isin(ids)].drop_duplicates()
    ic.to_parquet(standing / "SPDINTERCONNECTORCONSTRAINT.parquet", index=False, compression="zstd")

    outputs = {"SPDINTERCONNECTORCONSTRAINT": len(ic)}
    for table in ["GENCONDATA", "GENCONSET", "SPDCONNECTIONPOINTCONSTRAINT"]:
        parts = [_table_rows(path, table, value_filter=lambda row, wanted=set(ids): row.get("GENCONID") in wanted)
                 for path in raw_paths[table]]
        frame = pd.concat(parts, ignore_index=True).drop_duplicates()
        if table == "SPDCONNECTIONPOINTCONSTRAINT":
            frame = frame[frame.BIDTYPE.fillna("ENERGY").eq("ENERGY")]
        frame.to_parquet(standing / f"{table}.parquet", index=False, compression="zstd")
        outputs[table] = len(frame)

    details = pd.concat([_table_rows(path, "DUDETAILSUMMARY") for path in raw_paths["DUDETAILSUMMARY"]],
                        ignore_index=True).drop_duplicates()
    details.to_parquet(standing / "DUDETAILSUMMARY.parquet", index=False, compression="zstd")
    outputs["DUDETAILSUMMARY"] = len(details)
    member = pd.read_parquet(standing / "GENCONSET.parquet")
    set_ids = set(member.GENCONSETID.dropna())
    invokes = pd.concat([_table_rows(path, "GENCONSETINVOKE",
                                     value_filter=lambda row, wanted=set_ids: row.get("GENCONSETID") in wanted)
                         for path in raw_paths["GENCONSETINVOKE"]], ignore_index=True).drop_duplicates()
    invokes.to_parquet(standing / "GENCONSETINVOKE.parquet", index=False, compression="zstd")
    outputs["GENCONSETINVOKE"] = len(invokes)

    cp = pd.read_parquet(standing / "SPDCONNECTIONPOINTCONSTRAINT.parquet")
    points = sorted(cp.CONNECTIONPOINTID.dropna().unique())
    details["START_DATE"] = pd.to_datetime(details.START_DATE, errors="coerce")
    details["END_DATE"] = pd.to_datetime(details.END_DATE, errors="coerce")
    active = details[(details.START_DATE <= pd.Timestamp(config["end"]))
                     & (details.END_DATE.isna() | (details.END_DATE >= pd.Timestamp(config["start"])))]
    duids = sorted(active.loc[active.CONNECTIONPOINTID.isin(points), "DUID"].dropna().unique())
    dependencies = {"constraint_ids": ids, "connection_points": points, "duids": duids,
                    "direct_constraint_count": len(direct), "setter_count": len(setters),
                    "setters_not_direct": sorted(setters - direct)}
    dump(standing / "dependencies.json", dependencies)
    audit = {"standing_months": len(months), "first_month": str(months[0]), "last_month": str(months[-1]),
             "tables": outputs, "manifest": manifest, "absent_monthly_archives": absent,
             "study_bytes": path_bytes(root)}
    dump(marker, audit)
    return audit


def month_config(config, period, files):
    root = study_root(config)
    month_dir = root / "months" / str(period)
    month_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "experiment_id": f"{config['experiment_id']}_{period}", "interconnector": config["interconnector"],
        "start": str(period.start_time), "end": str(period.end_time.floor("5min")),
        "output_dir": str(month_dir.relative_to(DATA)).replace("\\", "/"),
        "standing_tables_dir": config["standing_tables_dir"], "raw_cache_dir": config["raw_cache_dir"],
        "highlight_duids": config.get("highlight_duids", []), "limits": config["limits"], "files": files,
    }
    path = month_dir / "config.json"
    dump(path, result)
    return path, month_dir


def compact_month(config, month_dir):
    equation = pd.read_parquet(month_dir / "equation_state.parquet")
    features = pd.read_parquet(month_dir / "constraint_features_5min.parquet")
    equation["binding"] = pd.to_numeric(equation.MARGINALVALUE, errors="coerce").abs().gt(1e-9)
    slack = (pd.to_numeric(equation.RHS, errors="coerce") - pd.to_numeric(equation.LHS, errors="coerce"))
    equation["ic_slack_mw"] = slack / pd.to_numeric(equation.ic_factor, errors="coerce").abs()
    equation["near_binding"] = equation.ic_slack_mw.between(0, float(config["near_binding_mw"]))
    leaders = pd.concat([
        features[["time", "upper_version_key", "conditional_upper"]].rename(
            columns={"upper_version_key": "version_key", "conditional_upper": "leader_bound"}).assign(direction="upper"),
        features[["time", "lower_version_key", "conditional_lower"]].rename(
            columns={"lower_version_key": "version_key", "conditional_lower": "leader_bound"}).assign(direction="lower")])
    equation = equation.merge(leaders[["time", "direction", "version_key", "leader_bound"]],
                              on=["time", "direction", "version_key"], how="left")
    equation["leading"] = equation.leader_bound.notna()
    direction_leader = pd.concat([
        features[["time", "conditional_upper"]].rename(columns={"conditional_upper": "leader_bound"}).assign(direction="upper"),
        features[["time", "conditional_lower"]].rename(columns={"conditional_lower": "leader_bound"}).assign(direction="lower")])
    equation = equation.drop(columns=["leader_bound"]).merge(direction_leader, on=["time", "direction"], how="left")
    gap = np.where(equation.direction.eq("upper"), equation.bound - equation.leader_bound,
                   equation.leader_bound - equation.bound)
    equation["near_setting"] = pd.Series(gap, index=equation.index).between(0, float(config["near_setting_mw"]))
    group_cols = ["CONSTRAINTID", "version_key", "direction", "EFFECTIVEDATE", "VERSIONNO",
                  "ic_factor", "LIMITTYPE", "DESCRIPTION"]
    summary = equation.groupby(group_cols, dropna=False).agg(
        applicable_intervals=("time", "size"), binding_intervals=("binding", "sum"),
        near_binding_intervals=("near_binding", "sum"), near_setting_intervals=("near_setting", "sum"),
        leading_intervals=("leading", "sum"), mean_abs_marginal_value=("MARGINALVALUE", lambda x: pd.to_numeric(x, errors="coerce").abs().mean()),
        min_ic_slack_mw=("ic_slack_mw", "min"), median_ic_slack_mw=("ic_slack_mw", "median")
    ).reset_index()
    summary.to_parquet(month_dir / "constraint_population_summary.parquet", index=False, compression="zstd")

    contribution = pd.read_parquet(month_dir / "unit_contributions.parquet")
    contribution["half_hour"] = contribution.time.dt.hour * 2 + (contribution.time.dt.minute >= 30).astype(int)
    pressure = contribution[["time", "direction", "constraint", "DUID", "bound_impact_mw",
                             "capacity_impact_mw", "tightening_mw", "reversal", "forced",
                             "contraction", "contraction_onset", "forced_onset"]]
    pressure.to_parquet(month_dir / "unit_pressure_5min.parquet", index=False, compression="zstd")
    by_unit = contribution.groupby(["DUID", "direction", "half_hour"], as_index=False).agg(
        rows=("time", "size"), total_abs_impact=("bound_impact_mw", lambda x: x.abs().sum()),
        mean_abs_impact=("bound_impact_mw", lambda x: x.abs().mean()),
        p95_abs_impact=("bound_impact_mw", lambda x: x.abs().quantile(.95)),
        total_tightening=("tightening_mw", lambda x: x.clip(lower=0).sum()),
        total_relief=("tightening_mw", lambda x: (-x.clip(upper=0)).sum()),
        contraction_rows=("contraction", "sum"), reversal_rows=("reversal", "sum"),
        forced_rows=("forced", "sum"))
    by_unit.to_parquet(month_dir / "unit_diurnal_summary.parquet", index=False, compression="zstd")

    disposable = [month_dir / "equation_state.parquet", month_dir / "unit_contributions.parquet",
                  month_dir / "unit_movements.parquet", month_dir / "pilot_predictions.parquet",
                  month_dir / "tables" / "DISPATCHCONSTRAINT.parquet",
                  month_dir / "tables" / "DISPATCHLOAD.parquet"]
    resolved_root = month_dir.resolve()
    for path in disposable:
        resolved = path.resolve()
        if resolved_root not in resolved.parents:
            raise RuntimeError(f"Refusing cleanup outside month directory: {resolved}")
        if path.exists():
            path.unlink()
    return len(equation), len(contribution)


def run_month(config, period, db):
    existing = db.execute("select status from months where month=?", (str(period),)).fetchone()
    if existing and existing[0] == "complete":
        return
    db.execute("insert or replace into months(month,status,started_at,message) values(?,?,datetime('now'),?)",
               (str(period), "running", "")); db.commit()
    dependencies = json.loads((DATA / config["standing_tables_dir"] / "dependencies.json").read_text())
    files, paths, items = [], {}, {}
    try:
        for table in config["interval_tables"]:
            path, item = fetch(config, period, table, "interval", db)
            paths[table] = path; items[table] = item; files.append(item)
        config_path, month_dir = month_config(config, period, files)
        table_dir = month_dir / "tables"; table_dir.mkdir(parents=True, exist_ok=True)
        keep = {
            "DISPATCHCONSTRAINT": ["SETTLEMENTDATE", "RUNNO", "CONSTRAINTID", "RHS", "LHS", "MARGINALVALUE",
                                   "VIOLATIONDEGREE", "INTERVENTION", "LASTCHANGED", "GENCONID_EFFECTIVEDATE",
                                   "GENCONID_VERSIONNO"],
            "DISPATCHLOAD": ["SETTLEMENTDATE", "RUNNO", "DUID", "CONNECTIONPOINTID", "DISPATCHMODE", "AGCSTATUS",
                             "INITIALMW", "TOTALCLEARED", "RAMPDOWNRATE", "RAMPUPRATE", "AVAILABILITY",
                             "INTERVENTION", "LASTCHANGED"]}
        wanted_constraints = set(dependencies["constraint_ids"])
        wanted_duids, wanted_points = set(dependencies["duids"]), set(dependencies["connection_points"])
        constraint = _table_rows(paths["DISPATCHCONSTRAINT"], "DISPATCHCONSTRAINT", keep=keep["DISPATCHCONSTRAINT"],
                                 value_filter=lambda row: row.get("CONSTRAINTID", row.get("GENCONID")) in wanted_constraints)
        dispatch = _table_rows(paths["DISPATCHLOAD"], "DISPATCHLOAD", keep=keep["DISPATCHLOAD"],
                               value_filter=lambda row: row.get("DUID") in wanted_duids
                               or row.get("CONNECTIONPOINTID") in wanted_points)
        constraint.to_parquet(table_dir / "DISPATCHCONSTRAINT.parquet", index=False, compression="zstd")
        dispatch.to_parquet(table_dir / "DISPATCHLOAD.parquet", index=False, compression="zstd")
        build_features(config_path)
        run_influence(config_path)
        equation_rows, contribution_rows = compact_month(config, month_dir)
        if not (month_dir / "constraint_features_5min.parquet").exists():
            raise RuntimeError("Monthly feature output missing after compaction")
        if not config.get("retain_interval_archives", False):
            raw_root = (DATA / config["raw_cache_dir"]).resolve()
            for table, path in paths.items():
                resolved = path.resolve()
                if raw_root not in resolved.parents:
                    raise RuntimeError(f"Refusing archive cleanup outside study raw directory: {resolved}")
                path.unlink()
                db.execute("update files set removed=1 where url=?", (items[table]["url"],))
        db.execute("update months set status='complete',completed_at=datetime('now'),rows_constraints=?,rows_dispatch=?,output_bytes=?,message=? where month=?",
                   (len(constraint), len(dispatch), path_bytes(month_dir),
                    f"equation rows {equation_rows}; contribution rows {contribution_rows}", str(period)))
        db.commit(); assert_storage(config)
    except Exception as exc:
        db.execute("update months set status='failed',message=? where month=?", (str(exc), str(period))); db.commit()
        raise


def run_all(config_path=CONFIG):
    config = load_study(config_path); db = connect(config)
    build_standing(config, db)
    for period in months_between(config["start"], config["end"]):
        print(f"LONGITUDINAL MONTH {period}", flush=True)
        run_month(config, period, db)
    status(config_path)


def status(config_path=CONFIG):
    config = load_study(config_path); db = connect(config)
    rows = db.execute("select month,status,rows_constraints,rows_dispatch,output_bytes,message from months order by month").fetchall()
    result = {"months": [{"month": a, "status": b, "constraint_rows": c, "dispatch_rows": d,
                           "output_bytes": e, "message": f} for a, b, c, d, e, f in rows],
              "complete": sum(row[1] == "complete" for row in rows),
              "failed": sum(row[1] == "failed" for row in rows),
              "study_bytes": path_bytes(study_root(config)), "budget_bytes": config["limits"]["study_disk_bytes"]}
    print(json.dumps(result, indent=2)); return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["run", "status"])
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    run_all(args.config) if args.command == "run" else status(args.config)
