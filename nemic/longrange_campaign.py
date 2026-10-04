"""Bounded VNI/QNI forecast-improvement campaign for daily issues through 90 days."""
from __future__ import annotations

import argparse
from html import escape
import json
import shutil
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import psutil
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from nemic.experiments.core import ROOT, digest
from nemic.production.contracts import CONNECTORS
from scripts.report_theme.report_theme import finding, figure_html, hero, metric, render_page


CONFIG = ROOT / "configs/experiments/qni_vni_longrange_v1.json"
DATA = ROOT / "data/forecast_experiments/qni_vni_longrange_v1"
TARGETS = ROOT / "data/processed/targets.parquet"
MT_ROOT = ROOT / "data/forecast_experiments/qni_vni_fundamentals_v3/sources/mtpasa_90d"
CURRENT_MT_ROOT = ROOT / "data/forecast_inputs/qni_vni_longrange/sources/mtpasa_90d"
ID_TO_NAME = {spec[0]: name for name, spec in CONNECTORS.items()}


def _config(path=CONFIG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _atomic_json(path, value):
    def clean(item):
        if isinstance(item, dict): return {str(key): clean(val) for key, val in item.items()}
        if isinstance(item, (list, tuple, np.ndarray)): return [clean(val) for val in item]
        if isinstance(item, (np.integer,)): return int(item)
        if isinstance(item, (np.bool_,)): return bool(item)
        if isinstance(item, (float, np.floating)): return float(item) if np.isfinite(item) else None
        return item
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(clean(value), indent=2, default=str, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _state(stage, status, **detail):
    path = DATA / "status.json"
    state = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"campaign": "qni_vni_longrange_v1", "stages": {}}
    state["stages"][stage] = {"status": status, "updated_at": pd.Timestamp.now(tz="UTC").isoformat(), **detail}
    _atomic_json(path, state)
    return state


def _resource_gate(config):
    """Fail before a model cell can breach the frozen host resource limits."""
    runtime = config.get("runtime", {})
    minimum_memory = int(runtime.get("minimum_available_memory_bytes", 0))
    available_memory = int(psutil.virtual_memory().available)
    storage = config.get("storage", {})
    minimum_free = int(storage.get("minimum_free_bytes", 0))
    free_disk = int(shutil.disk_usage(DATA.parent).free)
    used = sum(path.stat().st_size for root in (DATA, MT_ROOT, CURRENT_MT_ROOT) if root.exists()
               for path in root.rglob("*") if path.is_file())
    maximum = int(storage.get("additional_bytes", 0))
    if available_memory < minimum_memory:
        raise RuntimeError(f"Available memory {available_memory} is below the {minimum_memory} byte campaign floor")
    if free_disk < minimum_free:
        raise RuntimeError(f"Free disk {free_disk} is below the {minimum_free} byte reserve")
    if maximum and used > maximum:
        raise RuntimeError(f"Campaign storage {used} exceeds its {maximum} byte cap")
    return {"available_memory_bytes": available_memory, "free_disk_bytes": free_disk, "campaign_bytes": used}


def _calendar(frame):
    delivery = pd.DatetimeIndex(frame.delivery)
    hour = delivery.hour + delivery.minute / 60
    return pd.DataFrame({
        "hour_sin": np.sin(2*np.pi*hour/24), "hour_cos": np.cos(2*np.pi*hour/24),
        "year_sin": np.sin(2*np.pi*delivery.dayofyear/365.25),
        "year_cos": np.cos(2*np.pi*delivery.dayofyear/365.25),
        "weekend": (delivery.dayofweek >= 5).astype(float),
        "lead": frame.lead.to_numpy(float), "log_lead": np.log1p(frame.lead.to_numpy(float)),
    }, index=frame.index)


def _load_mt():
    paths = sorted([*MT_ROOT.glob("*.parquet"), *CURRENT_MT_ROOT.glob("*.parquet")])
    if not paths:
        raise FileNotFoundError("Run `python -m nemic.longrange extract-mtpasa --horizon-days 90` first")
    columns = ["available_at", "day", "region", "capacity_mw", "unit_count",
               "positive_capacity_fraction", "mean_recall_hours", "source_hash"]
    frames = []
    for path in paths:
        # PyArrow returns no columns for an empty projection; inspect the schema
        # without materialising the compressed regional rows.
        import pyarrow.parquet as pq
        available = set(pq.ParquetFile(path).schema.names)
        frame = pd.read_parquet(path, columns=columns + (["receipt_completed_at"] if "receipt_completed_at" in available else []))
        if "receipt_completed_at" not in frame:
            frame["receipt_completed_at"] = pd.NaT
        frame["availability_evidence"] = "measured_receipt" if path.is_relative_to(CURRENT_MT_ROOT) else "historical_report_generation_proxy"
        frames.append(frame)
    mt = pd.concat(frames, ignore_index=True)
    mt = mt.sort_values("available_at").drop_duplicates(["available_at", "day", "region"], keep="last")
    mt["day"] = pd.to_datetime(mt.day).dt.tz_localize(None).dt.normalize()
    mt["available_at"] = pd.to_datetime(mt.available_at, utc=True).dt.tz_convert("Australia/Brisbane")
    mt["receipt_completed_at"] = pd.to_datetime(mt.receipt_completed_at, utc=True)
    return mt


def prepare(config_path=CONFIG):
    c = _config(config_path); DATA.mkdir(parents=True, exist_ok=True)
    _state("prepare", "running")
    target = pd.read_parquet(TARGETS, columns=["time", "ic", *c["targets"]])
    target["time"] = pd.to_datetime(target.time).dt.tz_localize("Australia/Brisbane")
    target["connector"] = target.ic.map(ID_TO_NAME)
    target = target[target.connector.isin(c["connectors"])]
    mt = _load_mt()
    runs = pd.DatetimeIndex(sorted(mt.available_at.unique()))
    start = max(target.time.min().normalize(), runs.min().normalize())
    last_origin = target.time.max() - pd.Timedelta(minutes=30*max(c["leads_half_hours"]))
    first_origin = start + pd.Timedelta(hours=c["daily_issue_hour_nem"])
    origins = pd.date_range(first_origin, last_origin, freq="D", tz="Australia/Brisbane")
    runs_by_origin = {origin: runs[runs <= origin].max() if (runs <= origin).any() else pd.NaT for origin in origins}
    mt_groups = {key: group.set_index(["day", "region"]) for key, group in mt.groupby("available_at")}
    actual = target.set_index(["connector", "time"])
    rows = []
    for origin in origins:
        run = runs_by_origin[origin]
        if pd.isna(run): continue
        availability = mt_groups.get(run)
        for connector in c["connectors"]:
            source, sink = CONNECTORS[connector][1:]
            for lead in c["leads_half_hours"]:
                delivery = origin + pd.Timedelta(minutes=30*lead)
                key = (connector, delivery)
                if key not in actual.index: continue
                day = delivery.tz_localize(None).normalize()
                record = {"origin": origin, "delivery": delivery, "lead": lead, "connector": connector,
                          "mt_run": run, "mt_age_hours": (origin-run).total_seconds()/3600}
                for side, region in (("source", source), ("sink", sink)):
                    if availability is not None and (day, region) in availability.index:
                        values = availability.loc[(day, region)]
                        if isinstance(values, pd.DataFrame): values = values.iloc[-1]
                        for column in ("capacity_mw", "unit_count", "positive_capacity_fraction", "mean_recall_hours"):
                            record[f"{side}_{column}"] = float(values[column]) if pd.notna(values[column]) else np.nan
                for target_name in c["targets"]:
                    anchor_key = (connector, origin-pd.Timedelta(minutes=30))
                    anchor = float(actual.loc[anchor_key, target_name]) if anchor_key in actual.index else np.nan
                    rows.append({**record, "target": target_name, "actual": float(actual.loc[key, target_name]),
                                 "own_anchor": anchor})
    frame = pd.DataFrame(rows)
    calendar = _calendar(frame)
    for column in calendar: frame[column] = calendar[column]
    frame["capacity_difference"] = frame.get("source_capacity_mw", np.nan) - frame.get("sink_capacity_mw", np.nan)
    frame["positive_capacity_fraction_difference"] = frame.get("source_positive_capacity_fraction", np.nan) - frame.get("sink_positive_capacity_fraction", np.nan)
    path = DATA / "features.parquet"; frame.to_parquet(path, compression="zstd", index=False)
    manifest = {"rows": len(frame), "origins": frame.origin.nunique(), "origin_min": str(frame.origin.min()),
                "origin_max": str(frame.origin.max()), "sha256": digest(path), "source_manifest": digest(MT_ROOT/"manifest.json"),
                "claim": c["claim"]}
    _atomic_json(DATA / "prepare_manifest.json", manifest)
    _state("prepare", "completed", **manifest)
    return path


def _bands(lead):
    return pd.cut(lead, [0, 336, 672, 1440, 2880, 4320], labels=["days_1_7", "days_8_14", "days_15_30", "days_31_60", "days_61_90"])


def _models():
    return {
        "ridge": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=10.)),
        "boosting": HistGradientBoostingRegressor(loss="absolute_error", learning_rate=.05, max_iter=120,
                                                   max_leaf_nodes=15, min_samples_leaf=40,
                                                   l2_regularization=10., random_state=741, early_stopping=False),
    }


def _bootstrap(daily, seed=741):
    daily = pd.Series(daily).dropna().sort_index()
    if len(daily) < 14: return [None, None]
    rng = np.random.default_rng(seed); values = daily.to_numpy(); estimates=[]
    for _ in range(1000):
        starts = rng.integers(0, max(1, len(values)-6), size=int(np.ceil(len(values)/7)))
        sample = np.concatenate([values[start:start+7] for start in starts])[:len(values)]
        estimates.append(float(sample.mean()))
    return np.quantile(estimates, [.025, .975]).tolist()


def _primary_mae(actual, predicted, lead, weights):
    error = np.abs(np.asarray(actual, dtype=float)-np.asarray(predicted, dtype=float))
    lead = np.asarray(lead, dtype=float)
    first, second = lead <= 336, (lead > 336) & (lead <= 672)
    if not first.any() or not second.any():
        raise ValueError("Selection requires support in both primary lead bands")
    return float(weights["days_1_7"]*error[first].mean()+weights["days_8_14"]*error[second].mean())


def _residual_adjustments(actual, predicted, lead):
    residual = np.asarray(actual, dtype=float)-np.asarray(predicted, dtype=float)
    global_values = np.quantile(residual, [.025, .1, .5, .9, .975])
    labels = _bands(pd.Series(lead)).astype("string")
    result = {}
    for band in ("days_1_7", "days_8_14", "days_15_30", "days_31_60", "days_61_90"):
        values = residual[labels.eq(band).fillna(False).to_numpy()]
        result[band] = np.quantile(values, [.025, .1, .5, .9, .975]) if len(values) >= 20 else global_values
    return result


def run(connector, config_path=CONFIG):
    c = _config(config_path)
    if connector not in c["connectors"]: raise ValueError(connector)
    if connector == "QNI" and not (DATA / "results/VNI/summary.json").exists():
        raise RuntimeError("VNI must complete before QNI")
    resources = _resource_gate(c)
    _state(f"run/{connector}", "running", resources=resources)
    frame = pd.read_parquet(DATA / "features.parquet")
    frame = frame[frame.connector.eq(connector)].copy()
    for column in ("origin", "delivery", "mt_run"):
        frame[column] = pd.to_datetime(frame[column], utc=True).dt.tz_convert("Australia/Brisbane")
    origins = pd.DatetimeIndex(sorted(frame.origin.unique()))
    need = c["minimum_train_origins"] + c["selection_origins"] + c["calibration_origins"] + c["evaluation_origins"]
    if len(origins) < need: raise ValueError(f"Only {len(origins)} mature origins; {need} required")
    eval_start = origins[-c["evaluation_origins"]]
    cal_start = origins[-(c["evaluation_origins"]+c["calibration_origins"])]
    select_start = origins[-(c["evaluation_origins"]+c["calibration_origins"]+c["selection_origins"])]
    calendar_features = ["hour_sin", "hour_cos", "year_sin", "year_cos", "weekend", "lead", "log_lead"]
    challenger_features = calendar_features + ["mt_age_hours", "source_capacity_mw", "sink_capacity_mw",
        "source_unit_count", "sink_unit_count", "source_positive_capacity_fraction", "sink_positive_capacity_fraction",
        "source_mean_recall_hours", "sink_mean_recall_hours", "capacity_difference", "positive_capacity_fraction_difference",
        "own_anchor"]
    output = DATA / "results" / connector; output.mkdir(parents=True, exist_ok=True)
    summaries=[]; started=time.monotonic()
    weights = c.get("primary_weighting", {"days_1_7": .75, "days_8_14": .25})
    budget = float(c.get("connector_budgets_seconds", {}).get(connector, c.get("initial_model_budget_seconds", float("inf"))))
    for target in c["targets"]:
        if time.monotonic() - started >= budget:
            summaries.append({"target": target, "status": "deferred", "reason": "connector wall-time budget exhausted"})
            continue
        _resource_gate(c)
        cell=frame[frame.target.eq(target)].reset_index(drop=True)
        train=cell[(cell.delivery < select_start)]
        select=cell[(cell.origin >= select_start)&(cell.delivery < cal_start)]
        fit=cell[(cell.delivery < cal_start)]
        calibrate=cell[(cell.origin >= cal_start)&(cell.delivery < eval_start)]
        refit=cell[(cell.delivery < eval_start)]
        evaluate=cell[cell.origin >= eval_start].copy()
        if min(map(len,(train,select,fit,calibrate,refit,evaluate))) == 0:
            summaries.append({"target":target,"status":"ineligible","reason":"empty chronological partition"});continue
        candidates={"calendar": (calendar_features, _models()["boosting"]), **{name:(challenger_features,model) for name,model in _models().items()}}
        selection={}
        fitted={}
        with threadpool_limits(limits=c["runtime"]["numerical_threads"]):
            for name,(features,model) in candidates.items():
                model.fit(train[features],train.actual)
                selection[name]=_primary_mae(select.actual,model.predict(select[features]),select.lead,weights)
            winner=min(selection,key=selection.get)
            baseline = _models()["boosting"]
            win_features, winning=candidates[winner]
            baseline.fit(fit[calendar_features], fit.actual)
            baseline_adjustments = _residual_adjustments(
                calibrate.actual, baseline.predict(calibrate[calendar_features]), calibrate.lead)
            winning.fit(fit[win_features],fit.actual)
            adjustments = _residual_adjustments(
                calibrate.actual, winning.predict(calibrate[win_features]), calibrate.lead)
            baseline.fit(refit[calendar_features],refit.actual)
            winning.fit(refit[win_features],refit.actual)
            evaluate["forecast_mw"]=winning.predict(evaluate[win_features])
            evaluate["baseline_mw"]=baseline.predict(evaluate[calendar_features])
            evaluate["persistence_mw"] = evaluate.own_anchor
        evaluate["band"]=_bands(evaluate.lead);evaluate["origin_day"]=evaluate.origin.dt.normalize()
        for name in ("p02_5_mw","p10_mw","p50_mw","p90_mw","p97_5_mw"):
            evaluate[name] = np.nan
        for band, adjustment in adjustments.items():
            mask = evaluate.band.astype("string").eq(band)
            for name,value in zip(("p02_5_mw","p10_mw","p50_mw","p90_mw","p97_5_mw"),adjustment):
                evaluate.loc[mask,name]=evaluate.loc[mask,"forecast_mw"]+value
        band_rows=[]
        for band,g in evaluate.groupby("band",observed=True):
            model_error=np.abs(g.actual-g.forecast_mw);base_error=np.abs(g.actual-g.baseline_mw)
            persistence_error=np.abs(g.actual-g.persistence_mw)
            baseline_mae=float(base_error.mean())
            skill=1-float(model_error.mean())/baseline_mae if baseline_mae > 0 else None
            delta=(base_error-model_error).to_frame("delta").assign(origin_day=g.origin_day).groupby("origin_day").delta.mean()
            ci=_bootstrap(delta)
            persistence_mae=float(persistence_error.mean())
            persistence_skill=1-float(model_error.mean())/persistence_mae if persistence_mae > 0 else None
            persistence_delta=(persistence_error-model_error).to_frame("delta").assign(origin_day=g.origin_day).groupby("origin_day").delta.mean()
            persistence_ci=_bootstrap(persistence_delta)
            coverage80=((g.actual>=g.p10_mw)&(g.actual<=g.p90_mw)).mean();coverage95=((g.actual>=g.p02_5_mw)&(g.actual<=g.p97_5_mw)).mean()
            band_rows.append({"band":str(band),"rows":len(g),"origins":g.origin.nunique(),"model_mae":float(model_error.mean()),
                              "baseline_mae":baseline_mae,"skill":skill,"improvement_mw_ci95":ci,
                              "persistence_mae":persistence_mae,"skill_vs_persistence":persistence_skill,
                              "persistence_improvement_mw_ci95":persistence_ci,
                              "coverage_80":float(coverage80),"coverage_95":float(coverage95),
                              "calibrated":bool(coverage80>=c["interval_minimum_coverage"]["80"] and coverage95>=c["interval_minimum_coverage"]["95"])})
        first=next((x for x in band_rows if x["band"]=="days_1_7"),None);second=next((x for x in band_rows if x["band"]=="days_8_14"),None)
        weighted=(weights["days_1_7"]*first["skill"]+weights["days_8_14"]*second["skill"]) if first and second and first["skill"] is not None and second["skill"] is not None else None
        persistence_weighted=(weights["days_1_7"]*first["skill_vs_persistence"]+weights["days_8_14"]*second["skill_vs_persistence"]) if first and second and first["skill_vs_persistence"] is not None and second["skill_vs_persistence"] is not None else None
        positive_bound = bool(first and second and first["improvement_mw_ci95"][0] is not None
                              and second["improvement_mw_ci95"][0] is not None
                              and first["improvement_mw_ci95"][0] > 0
                              and second["improvement_mw_ci95"][0] > 0)
        persistence_positive_bound = bool(first and second and first["persistence_improvement_mw_ci95"][0] is not None
                                          and second["persistence_improvement_mw_ci95"][0] is not None
                                          and first["persistence_improvement_mw_ci95"][0] > 0
                                          and second["persistence_improvement_mw_ci95"][0] > 0)
        decision="improvement_demonstrated" if weighted is not None and persistence_weighted is not None \
            and weighted>=c["point_improvement_threshold"] and persistence_weighted>=c["point_improvement_threshold"] \
            and positive_bound and persistence_positive_bound and winner!="calendar" else "retain_baseline"
        cell_dir=output/target;cell_dir.mkdir(parents=True,exist_ok=True)
        evaluate.to_parquet(cell_dir/"predictions.parquet",compression="zstd",index=False)
        joblib.dump({"model":winning,"features":win_features,"adjustments":adjustments,"winner":winner,
                     "baseline_model":baseline,"baseline_features":calendar_features,
                     "baseline_adjustments":baseline_adjustments,"decision":decision,
                     "trained_through":str(eval_start),"connector":connector,"target":target},cell_dir/"model.joblib")
        result={"target":target,"status":"completed","winner":winner,"selection_mae":selection,"weighted_primary_skill":weighted,
                "primary_improvement_ci_positive": positive_bound,
                "weighted_primary_skill_vs_persistence":persistence_weighted,
                "primary_persistence_improvement_ci_positive":persistence_positive_bound,
                "decision":decision,"bands":band_rows,"partitions":{"select_start":select_start,"calibration_start":cal_start,"evaluation_start":eval_start},
                "artifacts":{"model.joblib":digest(cell_dir/"model.joblib"),"predictions.parquet":digest(cell_dir/"predictions.parquet")}}
        _atomic_json(cell_dir/"result.json",result);summaries.append(result)
    summary_status = "complete" if all(item["status"] in {"completed", "ineligible"} for item in summaries) else "partial"
    summary={"connector":connector,"status":summary_status,"elapsed_seconds":time.monotonic()-started,"budget_seconds":budget,"cells":summaries,
             "claim":c["claim"],"promotion":False}
    summary_path = output / "summary.json"
    _atomic_json(summary_path, summary)
    try:
        display_path = str(summary_path.relative_to(ROOT))
    except ValueError:
        display_path = str(summary_path)
    _state(f"run/{connector}", "completed" if summary_status == "complete" else "partial", summary=display_path)
    return output/"summary.json"


def _skill_svg(rows):
    measured = [row for row in rows if row.get("weighted_primary_skill") is not None]
    if not measured:
        return '<div class="empty">No completed skill estimates.</div>'
    width, left, row_height = 980, 245, 34
    extent = max(.05, max(abs(float(row["weighted_primary_skill"])) for row in measured) * 1.15)
    scale = (width-left-45)/(2*extent); zero = left + extent*scale
    parts = [f'<svg viewBox="0 0 {width} {55+row_height*len(measured)}" role="img" aria-label="Weighted days one to fourteen skill by connector and target">',
             f'<line x1="{zero:.1f}" y1="28" x2="{zero:.1f}" y2="{35+row_height*len(measured)}" stroke="#66717e"/>']
    for index, row in enumerate(measured):
        y = 42 + index*row_height; value = float(row["weighted_primary_skill"])
        x = zero if value >= 0 else zero + value*scale; bar = abs(value)*scale
        colour = "#268a87" if value >= 0 else "#ce6f59"
        label = f"{row['connector']} · {row['target']}"
        parts += [f'<text x="{left-12}" y="{y+12}" text-anchor="end" font-size="13">{escape(label)}</text>',
                  f'<rect x="{x:.1f}" y="{y}" width="{max(bar,1):.1f}" height="17" fill="{colour}" rx="2"/>',
                  f'<text x="{x+bar+7 if value >= 0 else x-7:.1f}" y="{y+13}" text-anchor="{"start" if value >= 0 else "end"}" font-size="12">{value:.1%}</text>']
    parts.append("</svg>")
    return "".join(parts)


def report(config_path=CONFIG):
    c = _config(config_path)
    report_dir = ROOT / "reports/qni_vni_longrange_v1"
    downloads = report_dir / "downloads"; downloads.mkdir(parents=True, exist_ok=True)
    rows, bands = [], []
    for connector in c["connectors"]:
        summary_path = DATA / "results" / connector / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        for cell in summary["cells"]:
            row = {"connector": connector, **cell}; rows.append(row)
            for band in cell.get("bands", []):
                bands.append({"connector": connector, "target": cell["target"], "winner": cell.get("winner"), **band})
    completed = [row for row in rows if row["status"] == "completed"]
    improved = [row for row in completed if row["decision"] == "improvement_demonstrated"]
    retained = [row for row in completed if row["decision"] == "retain_baseline"]
    calibrated = sum(all(b.get("calibrated") for b in row.get("bands", []) if b["band"] in {"days_1_7", "days_8_14"}) for row in completed)
    pd.DataFrame(rows).drop(columns=["bands", "artifacts", "partitions"], errors="ignore").to_csv(downloads / "cell_results.csv", index=False)
    pd.DataFrame(bands).to_csv(downloads / "band_metrics.csv", index=False)
    prepare_manifest = json.loads((DATA / "prepare_manifest.json").read_text(encoding="utf-8")) if (DATA / "prepare_manifest.json").exists() else {}
    lines = ["# QNI/VNI long-range forecast improvement results", "", f"> {c['claim']}", "",
             f"Completed cells: {len(completed)}. Improvement demonstrated: {len(improved)}. Baseline retained: {len(retained)}.", "",
             "| Connector | Target | Winner | Skill vs calendar | Skill vs persistence | Positive bounds vs both | Decision |", "|---|---|---|---:|---:|---|---|"]
    for row in rows:
        if row["status"] != "completed":
            lines.append(f"| {row['connector']} | {row['target']} | — | — | — | — | {row.get('reason', row['status'])} |")
            continue
        value = "—" if row["weighted_primary_skill"] is None else f"{row['weighted_primary_skill']:.2%}"
        persistence_value = "—" if row["weighted_primary_skill_vs_persistence"] is None else f"{row['weighted_primary_skill_vs_persistence']:.2%}"
        both_bounds = row["primary_improvement_ci_positive"] and row["primary_persistence_improvement_ci_positive"]
        lines.append(f"| {row['connector']} | {row['target']} | {row['winner']} | {value} | {persistence_value} | {both_bounds} | {row['decision']} |")
    lines += ["", "## Methods and limitations", "",
              "Daily 08:00 fixed-NEM-time origins use coherent original-vintage MT PASA publication proxies. Training, selection, calibration and evaluation are chronological and delivery-maturity purged. VNI is evaluated before QNI under the same frozen procedure.", "",
              "The primary score weights days 1–7 at 75% and days 8–14 at 25%. A challenger is accepted only with at least 2% weighted MAE skill against both the seasonal calendar model and target persistence, plus positive seven-day moving-block confidence bounds against both baselines in both primary lead bands. Intervals are labelled calibrated only at held-out coverage of at least 77% and 92% for nominal 80% and 95% intervals.", "",
              "These are historical development results using publication-time proxies. They do not establish live issue-time performance, and no model is promoted by this campaign.", ""]
    markdown = "\n".join(lines)
    (DATA / "RESULTS.md").write_text(markdown, encoding="utf-8")
    markdown_path = report_dir / "Long_Range_Research.md"; markdown_path.write_text(markdown, encoding="utf-8")

    best = max(completed, key=lambda row: row.get("weighted_primary_skill") if row.get("weighted_primary_skill") is not None else -np.inf, default=None)
    worst = min(completed, key=lambda row: row.get("weighted_primary_skill") if row.get("weighted_primary_skill") is not None else np.inf, default=None)
    body = hero("INTERFLOW · LONG-RANGE RESEARCH", "Can MT PASA improve", "90-day interconnector forecasts?",
                "A frozen chronological VNI-first, QNI-second comparison against a matched calendar baseline. The primary decision horizon is days 1–14; later bands remain an outlook diagnostic.",
                ["Historical development evidence", "08:00 NEM daily issue", "VNI then QNI", "No production promotion"])
    body += '<nav aria-label="Report sections"><a href="#answer">Answer</a><a href="#skill">Point skill</a><a href="#methods">Methods</a><a href="#downloads">Downloads</a></nav>'
    body += '<div class="metrics">' + "".join([
        metric("Completed cells", len(completed), "Connector × target comparisons"),
        metric("Improvement gates passed", f"{len(improved)}/{len(completed)}" if completed else "—", "Against calendar and persistence"),
        metric("Primary intervals calibrated", f"{calibrated}/{len(completed)}" if completed else "—", "Both held-out coverage gates"),
        metric("Mature daily origins", prepare_manifest.get("origins", "—"), "Available to the prepared campaign"),
    ]) + "</div>"
    body += f'<div class="callout">{escape(c["claim"])}. Reported AEMO interconnector limits are dispatch-solution outputs, not maximum secure physical transfer capability.</div>'
    body += '<section id="answer"><div class="section-kicker">DIRECT ANSWER</div><h2>What the held-out comparison supports</h2><div class="findings">'
    body += finding(1, "Replacement requires measured gain", f"{len(improved)} of {len(completed)} completed cells passed every point-improvement gate; all other cells retain the calendar baseline.")
    body += finding(2, "The strongest cell remains research evidence", (f"{best['connector']} {best['target']} recorded {best['weighted_primary_skill']:.1%} weighted primary skill." if best and best.get("weighted_primary_skill") is not None else "No finite primary skill estimate is available."))
    body += finding(3, "Live validity is still prospective", "Historical report generation is a publication proxy. Measured receipt times, ongoing outcomes and an untouched shadow period remain required before promotion.")
    body += "</div></section>"
    body += '<section id="skill"><div class="section-kicker">01 · POINT FORECASTS</div><h2>Weighted days 1–14 MAE skill</h2>'
    body += figure_html(_skill_svg(completed), "Matched skill versus the calendar baseline", "Positive values reduce MAE. The decision also requires positive dependence-aware confidence bounds in each primary band.", "downloads/cell_results.csv")
    body += '<div class="table-wrap" tabindex="0"><table><thead><tr><th>Connector</th><th>Target</th><th>Winner</th><th>Skill vs calendar</th><th>Skill vs persistence</th><th>Positive bounds vs both</th><th>Decision</th></tr></thead><tbody>'
    for row in completed:
        value = "—" if row.get("weighted_primary_skill") is None else f"{row['weighted_primary_skill']:.2%}"
        persistence_value = "—" if row.get("weighted_primary_skill_vs_persistence") is None else f"{row['weighted_primary_skill_vs_persistence']:.2%}"
        both_bounds = row["primary_improvement_ci_positive"] and row["primary_persistence_improvement_ci_positive"]
        body += f"<tr><td>{escape(row['connector'])}</td><td>{escape(row['target'])}</td><td>{escape(row['winner'])}</td><td>{value}</td><td>{persistence_value}</td><td>{both_bounds}</td><td>{escape(row['decision'])}</td></tr>"
    body += "</tbody></table></div></section>"
    body += '<section id="methods"><div class="section-kicker">02 · METHODS & LIMITATIONS</div><h2>Frozen evaluation contract</h2><div class="method"><p>Daily origins are fixed at 08:00 NEM time. Inputs use one coherent MT PASA run available at the origin. The challenger adds source and sink regional available capacity, positive-capacity unit share, unit count and recall-time summaries to calendar, lead and issue-known target-anchor features.</p><p>Partitions are chronological and purge outcomes that have not matured by the next boundary. Model choice uses selection only; residual intervals use calibration only; all published skill and coverage comes from evaluation. Decisions must beat both the seasonal calendar model and target persistence. Seven-day moving blocks preserve short-run dependence in confidence intervals.</p><p>The dataset is historical and the source timestamp is a report-generation proxy. Weather, demand, VRE, future dispatch, constraint setters and realised availability are excluded. Prospective received-at collection and revised-outcome scoring remain mandatory.</p></div></section>'
    body += '<section id="downloads"><div class="section-kicker">03 · DOWNLOADS & REPRODUCTION</div><h2>Compact evidence</h2><p><a href="downloads/cell_results.csv" download>Cell decisions</a> · <a href="downloads/band_metrics.csv" download>Band metrics</a> · <a href="Long_Range_Research.md" download>Markdown report</a></p><pre>python -m nemic.longrange_campaign report</pre></section>'
    html_path = report_dir / "Long_Range_Research.html"
    html_path.write_text(render_page("QNI/VNI long-range forecast research", body, plotly=False), encoding="utf-8")
    manifest_inputs = [Path(config_path), DATA / "prepare_manifest.json", MT_ROOT / "manifest.json", Path(__file__),
                       ROOT / "scripts/report_theme/report_theme.py", ROOT / "scripts/report_theme/report.css"]
    manifest_inputs += sorted((DATA / "results").glob("*/summary.json"))
    manifest = {"campaign": c["campaign"], "claim": c["claim"], "built_at": pd.Timestamp.now(tz="UTC").isoformat(),
                "data_cutoff": prepare_manifest.get("origin_max"), "rebuild": "python -m nemic.longrange_campaign report",
                "inputs": [{"path": str(path.relative_to(ROOT)), "sha256": digest(path)} for path in manifest_inputs if path.exists()],
                "outputs": [{"path": str(path.relative_to(ROOT)), "sha256": digest(path)} for path in (html_path, markdown_path, downloads / "cell_results.csv", downloads / "band_metrics.csv")]}
    _atomic_json(report_dir / "manifest.json", manifest)
    _state("report", "completed", path=str(html_path.relative_to(ROOT)), sha256=digest(html_path))
    return html_path


def shadow(origin, connector, output, config_path=CONFIG):
    """Create one research-only daily curve from the frozen historical policy."""
    c = _config(config_path)
    if connector not in c["connectors"]:
        raise ValueError(connector)
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Shadow origin must be timezone aware")
    origin = origin.tz_convert("Australia/Brisbane")
    if origin.hour != c["daily_issue_hour_nem"] or origin.minute != 0:
        raise ValueError(f"Shadow origin must be {c['daily_issue_hour_nem']:02d}:00 fixed NEM time")
    mt = _load_mt()
    eligible_source = mt[(mt.availability_evidence == "measured_receipt")
                         & (mt.receipt_completed_at <= origin.tz_convert("UTC"))
                         & (mt.available_at <= origin)]
    eligible_runs = pd.DatetimeIndex(sorted(eligible_source.available_at.unique()))
    run = eligible_runs.max() if len(eligible_runs) else pd.NaT
    fresh = pd.notna(run) and origin-run <= pd.Timedelta(hours=c.get("shadow_max_source_age_hours", 36))
    availability = eligible_source[eligible_source.available_at.eq(run)].set_index(["day", "region"]) if pd.notna(run) else None
    records = []
    for lead in c["leads_half_hours"]:
        delivery = origin + pd.Timedelta(minutes=30*lead)
        record = {"origin": origin, "delivery": delivery, "lead": lead, "connector": connector,
                  "mt_run": run, "mt_age_hours": (origin-run).total_seconds()/3600 if pd.notna(run) else np.nan}
        source, sink = CONNECTORS[connector][1:]
        day = delivery.tz_localize(None).normalize()
        for side, region in (("source", source), ("sink", sink)):
            if availability is not None and (day, region) in availability.index:
                values = availability.loc[(day, region)]
                if isinstance(values, pd.DataFrame): values = values.iloc[-1]
                for column in ("capacity_mw", "unit_count", "positive_capacity_fraction", "mean_recall_hours"):
                    record[f"{side}_{column}"] = float(values[column]) if pd.notna(values[column]) else np.nan
        records.append(record)
    features = pd.DataFrame(records)
    calendar = _calendar(features)
    for column in calendar: features[column] = calendar[column]
    features["capacity_difference"] = features.get("source_capacity_mw", np.nan)-features.get("sink_capacity_mw", np.nan)
    features["positive_capacity_fraction_difference"] = features.get("source_positive_capacity_fraction", np.nan)-features.get("sink_positive_capacity_fraction", np.nan)
    anchors = {}
    if TARGETS.exists():
        history = pd.read_parquet(TARGETS, columns=["time", "ic", *c["targets"]])
        history["time"] = pd.to_datetime(history.time).dt.tz_localize("Australia/Brisbane")
        history["connector"] = history.ic.map(ID_TO_NAME)
        anchor_rows = history[(history.connector == connector) & (history.time == origin-pd.Timedelta(minutes=30))]
        if len(anchor_rows) == 1:
            anchors = {target: float(anchor_rows.iloc[0][target]) for target in c["targets"]}
    rows = []
    quantile_names = ("p02_5_mw", "p10_mw", "p50_mw", "p90_mw", "p97_5_mw")
    for target in c["targets"]:
        target_features = features.copy()
        target_features["own_anchor"] = anchors.get(target, np.nan)
        bundle_path = DATA / "results" / connector / target / "model.joblib"
        result_path = DATA / "results" / connector / target / "result.json"
        if not bundle_path.exists() or not result_path.exists():
            for record in records:
                rows.append({**record, "target": target, "status": "unavailable", "reason": "historical policy not fitted"})
            continue
        bundle = joblib.load(bundle_path); result = json.loads(result_path.read_text(encoding="utf-8"))
        use_challenger = result["decision"] == "improvement_demonstrated"
        required = bundle["features"]
        if use_challenger:
            complete_mt = (target_features[required].notna().all(axis=1) if set(required) <= set(target_features)
                           else pd.Series(False, index=target_features.index))
            complete_mt &= bool(fresh)
        else:
            complete_mt = pd.Series(True, index=features.index)
        for index, record in target_features.iterrows():
            challenger = use_challenger and bool(complete_mt.loc[index])
            model = bundle["model"] if challenger else bundle["baseline_model"]
            names = bundle["features"] if challenger else bundle["baseline_features"]
            adjustment_map = bundle["adjustments"] if challenger else bundle["baseline_adjustments"]
            band = str(_bands(pd.Series([record.lead])).iloc[0])
            adjustments = adjustment_map[band]
            point = float(model.predict(record[names].to_frame().T)[0])
            row = {"origin": origin, "delivery": record.delivery, "lead": int(record.lead), "connector": connector,
                   "target": target, "forecast_mw": point, "status": "complete", "mode": "shadow",
                   "selection": "challenger" if challenger else ("baseline" if not use_challenger else "stale_input_fallback"),
                   "model": bundle["winner"] if challenger else "calendar", "mt_run": run,
                   "mt_age_hours": record.mt_age_hours, "source_fresh": bool(fresh), "promotion": False}
            row.update({name: point+float(value) for name, value in zip(quantile_names, adjustments)})
            rows.append(row)
    result = pd.DataFrame(rows)
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    result.to_parquet(output / "forecasts.parquet", index=False)
    metadata = {"schema": 1, "claim": c["claim"], "origin": str(origin), "connector": connector,
                "rows": len(result), "source_run": str(run), "source_fresh": bool(fresh),
                "forecast_sha256": digest(output / "forecasts.parquet"), "promotion": False,
                "generated_at": pd.Timestamp.now(tz="UTC").isoformat()}
    _atomic_json(output / "manifest.json", metadata)
    return output / "forecasts.parquet"


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("prepare");run_parser=sub.add_parser("run");run_parser.add_argument("--connector",choices=["VNI","QNI"],required=True)
    sub.add_parser("report");sub.add_parser("status")
    shadow_parser=sub.add_parser("shadow");shadow_parser.add_argument("--origin",required=True)
    shadow_parser.add_argument("--connector",choices=["VNI","QNI"],required=True);shadow_parser.add_argument("--output",required=True)
    args=parser.parse_args()
    if args.command=="prepare": print(prepare())
    elif args.command=="run": print(run(args.connector))
    elif args.command=="report": print(report())
    elif args.command=="shadow": print(shadow(args.origin,args.connector,args.output))
    else:
        path=DATA/"status.json";print(path.read_text(encoding="utf-8") if path.exists() else json.dumps({"campaign":"qni_vni_longrange_v1","status":"not_started"},indent=2))


if __name__=="__main__": main()
