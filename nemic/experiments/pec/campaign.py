"""Run the isolated PEC acquisition, replay, and publication checks."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import pandas as pd

from nemic.common import ROOT, session
from nemic.constraint_ingest import _table_rows

from . import network as network_reader
from .constraints import (dispatch_equations, invocation_membership, match_limits,
                          read_standing, reconstruction_summary)
from .episodes import configurations, episodes, setter_summary, transition_table
from .network import acquire_network, notice_records, observed_outages, outage_records
from .observations import REGIONAL, coverage, half_hours, observed_intervals, physical
from .sources import CONNECTOR, DATA_DIR, OUTPUT_DIR, REGIONS, START, acquire_dispatch, last_closed_day, standing_sources


def save(frame, path):
    temporary = path.with_suffix(path.suffix + ".partial")
    if path.suffix == ".csv":
        frame.to_csv(temporary, index=False)
    else:
        frame.to_parquet(temporary, index=False, compression="zstd")
    temporary.replace(path)


def october_reconciliation(five, sources):
    rows = []
    source = next(source for source in sources if source.product == "DISPATCHINTERCONNECTORRES")
    archive = _table_rows(source.path, source.product, value_filter=lambda row: row["INTERCONNECTORID"] == CONNECTOR)
    archive["time"] = pd.to_datetime(archive.SETTLEMENTDATE)
    archive["report_created"] = pd.NaT
    for column in ["INTERVENTION", "RUNNO", "EXPORTLIMIT", "IMPORTLIMIT", "MWFLOW", "METEREDMWFLOW"]:
        archive[column] = pd.to_numeric(archive[column], errors="coerce")
    archive = physical(archive, "INTERCONNECTORID")
    hour_end = pd.Timestamp("2026-11-01")
    columns = ["EXPORTLIMIT", "IMPORTLIMIT", "MWFLOW", "METEREDMWFLOW", "EXPORTGENCONID", "IMPORTGENCONID", "INTERVENTION"]
    observed = five.loc[five.time.gt(START) & five.time.le(hour_end), ["time", *columns]].copy()
    archive = archive.loc[archive.time.gt(START) & archive.time.le(hour_end), ["time", *columns]].copy()
    matched = observed.merge(archive, on="time", how="outer", suffixes=("_original", "_monthly"), indicator=True)
    matched_rows = matched[matched._merge.eq("both")]
    for column in columns:
        original, monthly = matched_rows[f"{column}_original"], matched_rows[f"{column}_monthly"]
        if column in {"EXPORTGENCONID", "IMPORTGENCONID"}:
            same = original.fillna("").eq(monthly.fillna(""))
            max_abs = np.nan
        else:
            difference = pd.to_numeric(original) - pd.to_numeric(monthly)
            same = difference.abs().le(1e-3) | (original.isna() & monthly.isna())
            max_abs = difference.abs().max()
        rows.append(dict(field=column, in_original=len(observed), in_monthly=len(archive), matched=len(matched_rows),
                         equal_rows=same.sum(), differing_rows=(~same).sum(), max_abs_difference=max_abs,
                         source_url=source.url))
    regional_source = next(source for source in sources if source.product == "DISPATCHREGIONSUM")
    regional = _table_rows(regional_source.path, regional_source.product,
                           keep=["REGIONID", "SETTLEMENTDATE", "LASTCHANGED", "RUNNO", "INTERVENTION", *REGIONAL.values()],
                           value_filter=lambda row: row["REGIONID"] in REGIONS)
    regional["time"] = pd.to_datetime(regional.SETTLEMENTDATE)
    regional["report_created"] = pd.NaT
    for column in ["RUNNO", "INTERVENTION", *REGIONAL.values()]:
        regional[column] = pd.to_numeric(regional[column], errors="coerce")
    regional = regional.loc[regional.time.gt(START) & regional.time.le(hour_end)]
    regional = physical(regional, "REGIONID")
    for region, name in REGIONS.items():
        matched = (five.loc[five.time.gt(START) & five.time.le(hour_end)]
                   .merge(regional[regional.REGIONID.eq(region)], on=["time", "RUNNO", "INTERVENTION"]))
        for metric, column in REGIONAL.items():
            label = f"{name}_{metric}"
            difference = matched[label] - matched[column]
            same = difference.abs().le(1e-3) | (matched[label].isna() & matched[column].isna())
            rows.append(dict(field=label, in_original=len(observed), in_monthly=regional.REGIONID.eq(region).sum(),
                             matched=len(matched), equal_rows=same.sum(), differing_rows=(~same).sum(),
                             max_abs_difference=difference.abs().max(), source_url=regional_source.url))
    return pd.DataFrame(rows)


def flow_profile(half):
    path = ROOT / "local_exports" / "energyconnect_20261121" / "flow_assumptions.csv"
    if not path.exists():
        return pd.DataFrame([{"status": "Retained flow-profile reference is unavailable at its documented path"}])
    legacy = pd.read_csv(path)
    rows = []
    for row in legacy.itertuples(index=False):
        period_start = int(row.delivery_block_start_nem.split(":")[0])
        period_end = int(row.delivery_block_end_nem.split(":")[0])
        hours = (half.time - pd.Timedelta(minutes=15)).dt.hour
        sample = half[half.study_day.ge(pd.Timestamp(row.sample_start_nem))
                      & half.study_day.lt(pd.Timestamp(row.sample_end_nem_exclusive))
                      & hours.between(period_start, period_end - 1)].dispatch_flow_mean
        quantile = sample.quantile([.1, .5, .9]).to_numpy()
        rows.append(dict(delivery_period=f"{row.delivery_block_start_nem} to {row.delivery_block_end_nem}",
                         sample_start_nem=row.sample_start_nem, sample_end_nem_exclusive=row.sample_end_nem_exclusive,
                         expected_half_hours=row.half_hours, observed_half_hours=len(sample),
                         legacy_p10_mw=row.p10_mw, p10_mw=quantile[0], legacy_p50_mw=row.p50_mw, p50_mw=quantile[1],
                         legacy_p90_mw=row.p90_mw, p90_mw=quantile[2], positive_direction=row.positive_direction,
                         status="reconciled" if row.half_hours == len(sample) and np.allclose(quantile, [row.p10_mw, row.p50_mw, row.p90_mw], atol=.001, rtol=0)
                         else "differs from earlier profile"))
    return pd.DataFrame(rows)


def analyze(data_dir, output_dir, end_day):
    downloads = output_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    inputs = standing_sources(data_dir)
    sources = pd.read_csv(data_dir / "dispatch_sources.csv")
    network = pd.read_csv(data_dir / "network_sources.csv")
    tables = {name: pd.read_parquet(data_dir / f"dispatch_{name}.parquet")
              for name in ["interconnectorres", "regionsum", "constraint"]}
    five = observed_intervals(tables["interconnectorres"], tables["regionsum"], end_day)
    print(f"Selected {len(five):,} five-minute physical solutions", flush=True)
    notices = notice_records(network)
    definitions, factors, memberships, tracked, invoked = [read_standing(inputs, name) for name in
        ["GENCONDATA", "SPDINTERCONNECTORCONSTRAINT", "GENCONSET", "GENCONSETTRK", "GENCONSETINVOKE"]]
    equations = dispatch_equations(tables["constraint"], five, definitions, factors)
    active = invocation_membership(equations, memberships, tracked, invoked)
    print(f"Matched {len(equations):,} dispatch equations and {len(active):,} dispatched set memberships", flush=True)
    dependency = hashlib.sha256((data_dir / "network_sources.csv").read_bytes()
                                + Path(network_reader.__file__).read_bytes()).hexdigest()[:16]
    nos_cache = data_dir / f"nos_outages_{dependency}.parquet"
    if nos_cache.exists():
        nos = pd.read_parquet(nos_cache)
    else:
        nos = outage_records(network)
        save(nos, nos_cache)
    outage_grid = observed_outages(five, active, nos)
    five = configurations(five, equations, active, outage_grid)
    matches = match_limits(five, equations, active)
    matches = matches.merge(five[["time", "configuration", "outage_ids", "outage_sets", "notice_ids", "notice_supported_set"]],
                            on="time", how="left")
    event_rows = episodes(five, matches)
    half = half_hours(five)
    save(half, data_dir / "half_hour.parquet")
    coverage_rows = coverage(five, half, end_day)
    snapshot_days = pd.to_datetime(network.snapshot.dropna()).dt.normalize()
    coverage_rows["nos_snapshot_available"] = coverage_rows.study_day.isin(snapshot_days)
    expected = pd.date_range(START + pd.Timedelta(minutes=5), end_day + pd.Timedelta(days=1), freq="5min")
    oct_compare = october_reconciliation(five, inputs)
    earlier_profile = flow_profile(half)
    legacy_hash_path = ROOT / "local_exports" / "energyconnect_20261121" / "source_hashes.csv"
    if legacy_hash_path.is_file():
        legacy_hash = pd.read_csv(legacy_hash_path).rename(columns={"Hash": "earlier_sha256"})
        sources = sources.merge(legacy_hash, on="archive", how="left")
        sources["earlier_hash_matches"] = sources.earlier_sha256.str.lower().eq(sources.sha256)
    tables = {
        "coverage": coverage_rows, "source_hashes": pd.concat([sources, network], ignore_index=True),
        "gaps": pd.DataFrame({"missing_interval_end": expected.difference(pd.DatetimeIndex(five.time))}),
        "transitions": transition_table(five), "market_notices": notices,
        "setter_summary": setter_summary(matches), "episodes": event_rows, "constraint_matches": matches,
        "reconstruction_summary": reconstruction_summary(matches), "set_invocations": active,
        "outages": nos[nos.pec_equipment_hint | nos.OUTAGEID.isin(outage_grid.outage_id)],
        "outage_intervals": outage_grid, "october_reconciliation": oct_compare, "november_flow_crosscheck": earlier_profile,
        "five_minute_limits": five, "half_hour_limits": half,
    }
    for name, table in tables.items():
        save(table, downloads / f"{name}.csv")
    print(f"{len(five):,} five-minute rows and {len(half):,} complete half-hours through {end_day.date()}", flush=True)
    return half


def verify(data_dir, output_dir):
    downloads = output_dir / "downloads"
    observed = pd.read_csv(downloads / "five_minute_limits.csv", parse_dates=["time"])
    aggregated = pd.read_csv(downloads / "half_hour_limits.csv", parse_dates=["time"])
    daily = pd.read_csv(downloads / "coverage.csv")
    assert observed.time.is_unique and aggregated.time.is_unique
    assert len(observed) == daily.observed_five_minute.sum()
    assert len(aggregated) + daily.incomplete_half_hours.sum() == daily.expected_half_hours.sum()
    assert np.allclose(-observed.IMPORTLIMIT, observed.sa_nsw_mw, equal_nan=True)
    assert np.allclose(observed.EXPORTLIMIT, observed.nsw_sa_mw, equal_nan=True)
    data = pd.read_parquet(data_dir / "half_hour.parquet")
    for direction in ["nsw_sa", "sa_nsw"]:
        minimum = data.set_index(f"{direction}_minimum_time")[f"{direction}_tight"]
        evidence = observed.set_index("time")[f"{direction}_mw"].reindex(minimum.index)
        assert np.allclose(minimum, evidence, equal_nan=True)
        cohorts = observed.groupby(observed.time.dt.ceil("30min"))[f"{direction}_mw"]
        complete = cohorts.count()[cohorts.count().eq(6)].index
        assert np.allclose(cohorts.mean().reindex(complete), data[f"{direction}_mean"])
        assert np.allclose(cohorts.min().reindex(complete), data[f"{direction}_tight"])
    assert data.n5.eq(6).all()
    sources = pd.read_csv(downloads / "source_hashes.csv")
    for source in sources[sources.status.eq("available")].drop_duplicates("file").itertuples(index=False):
        path = ROOT / Path(source.file)
        assert path.stat().st_size == source.bytes, source.archive
        with path.open("rb") as stream:
            assert hashlib.file_digest(stream, "sha256").hexdigest() == source.sha256, source.archive
    from .forecast import verify_evidence
    from .verify_report import validate
    verify_evidence(data_dir, downloads)
    validate(output_dir, data_dir)
    print("Verified coverage, directions, minimum timestamps, means, source hashes and report links", flush=True)


def package(output_dir, end_day):
    destination = output_dir / f"energyconnect_{end_day:%Y-%m-%d}.zip"
    temporary = destination.with_suffix(".partial")
    manifest = output_dir / "report_manifest.json"
    tracked = json.loads(manifest.read_text(encoding="utf-8"))["artifacts"]
    files = [manifest, *(output_dir / name for name in sorted(tracked))]
    with ZipFile(temporary, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for file in files:
            archive.write(file, file.relative_to(output_dir).as_posix())
    with ZipFile(temporary) as archive:
        assert archive.testzip() is None
    temporary.replace(destination)
    print(f"Verified offline package {destination}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=["all", "acquire", "observations", "issued", "forecast", "scenario", "report", "verify", "package"], default="all")
    parser.add_argument("--end-day", type=pd.Timestamp, default=last_closed_day())
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    end_day = args.end_day.normalize()
    end = end_day + pd.Timedelta(days=1)
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.stage in {"all", "acquire"}:
        session().close()
        with ThreadPoolExecutor(max_workers=2) as workers:
            dispatch = workers.submit(acquire_dispatch, args.data_dir, end_day)
            network = workers.submit(acquire_network, args.data_dir, end_day)
            dispatch.result()
            network.result()
    if args.stage in {"all", "observations"}:
        analyze(args.data_dir, args.output_dir, end_day)
    if args.stage in {"all", "issued"}:
        from .issued import acquire, acquire_proxy, read_sources
        issued = args.data_dir / "issued"
        acquire(issued, START, end)
        acquire_proxy(issued, START, min(end_day, pd.Timestamp("2026-11-10")))
        read_sources(issued, workers=4)
    if args.stage in {"all", "forecast"}:
        from .forecast import run
        run(pd.read_parquet(args.data_dir / "half_hour.parquet"), args.data_dir, args.output_dir / "downloads", end=end)
    if args.stage in {"all", "scenario"}:
        from .scenario import run
        run(pd.read_parquet(args.data_dir / "half_hour.parquet"), args.output_dir)
    if args.stage in {"all", "report"}:
        from .report import build_report
        build_report(args.data_dir, args.output_dir)
    if args.stage in {"all", "verify"}:
        verify(args.data_dir, args.output_dir)
    if args.stage in {"all", "package"}:
        package(args.output_dir, end_day)


if __name__ == "__main__":
    main()
