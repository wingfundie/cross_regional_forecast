"""Pilot, chronological six-link comparisons, conditional catalogue and bundles."""
from __future__ import annotations
import json
from pathlib import Path
import re
import time
from contextlib import contextmanager, nullcontext
from concurrent.futures import ProcessPoolExecutor
import os
import psutil

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from nemic_regimes.core import RegimeBundle, NUMERIC_FEATURES, QUANTILES, _clean, structural_era
from nemic_regimes.models import fit_quantiles, predict_quantiles, calibrate
from .common import DATA, REPORT, ROOT, config, digest, now, stage, write_json
from .metrics import score, loss, block_improvement

PRIMARY = ["temperature_max", "source_vre", "sink_residual", "residual_difference", "source_vre_ramp_1h",
           "electrical_positive_mw", "electrical_negative_mw", "corridor_wind_ms", "corridor_radiation_wm2"]


def research_signature(inputs):
    import hashlib
    paths=[Path(__file__),Path(__file__).with_name("metrics.py"),ROOT/"packages/nemic-regimes/src/nemic_regimes/core.py",
           ROOT/"packages/nemic-regimes/src/nemic_regimes/models.py",ROOT/"execution/conditional_regimes_v1/METHODOLOGY.md",
           ROOT/"configs/experiments/conditional_regimes_v1.json",*inputs]
    return hashlib.sha256("".join(digest(p) for p in paths).encode()).hexdigest()


def fit_settings(train, neighbour_days=60, radius=2):
    scales = {}
    for col in NUMERIC_FEATURES:
        s = train[col].dropna()
        if len(s) and s.nunique() > 1:
            scales[col] = {"median": float(s.median()), "scale": max(float(s.quantile(.75)-s.quantile(.25)), 1e-3),
                           "min": float(s.min()), "max": float(s.max())}
    features = [c for c in PRIMARY if c in scales and train[c].notna().mean() >= .2]
    corr = train[features].corr().abs()
    retained = []
    for f in features:
        if all(corr.loc[f, old] < .98 or pd.isna(corr.loc[f,old]) for old in retained):
            retained.append(f)
    thresholds, regimes = {}, {}
    for q in range(1,5):
        f = train[train.quarter == q]
        positive = f.loc[f.capacity > 0,"capacity"]
        if len(positive): thresholds[str(q)] = float(.5*positive.median())
        def bound(col, percentile, side):
            s = f[col].dropna()
            return {col: {side: float(s.quantile(percentile))}} if len(s) else {}
        regimes[str(q)] = {
            "reference": {}, "no_mapped_outage": {"outage_state": "clear"},
            "high_source_vre": bound("source_vre", .8, "min"),
            "high_sink_residual": bound("sink_residual", .8, "min"),
            "hot_high_sink_residual": {**bound("temperature_max", .8, "min"), **bound("sink_residual", .8, "min")},
            "low_source_vre_high_sink_residual": {**bound("source_vre", .2, "max"), **bound("sink_residual", .8, "min")},
            "outage_high_sink_residual": {"outage_state":"invoked", **bound("sink_residual", .8,"min")},
            "falling_source_vre": bound("source_vre_ramp_1h", .2, "max")}
        top = f.active_sets.str.split("|").explode().value_counts()
        for family in [x for x in top.index if x][:3]:
            regimes[str(q)]["set_"+family] = {"required_sets": [family]}
    return {"scales": scales, "features": retained, "neighbour_days": neighbour_days,
            "half_hour_radius": radius, "min_days": config()["min_days"], "min_episodes": config()["min_episodes"],
            "restriction_thresholds": thresholds, "regimes": regimes, "policy": "analogue"}


def metadata_for(train, settings):
    return {"schema_version":1,"as_of":config()["as_of"],"bundle_id":"development_fold", "training_cutoff":str(train.time.max()), "settings":settings}


def row_query(row, settings, method="analogue"):
    out = {"connector":row.connector,"direction":row.direction,"quarter":int(row.quarter),"half_hour":int(row.half_hour),
           "era":row.era,"daytype":row.daytype,"method":method,"outage_state":row.outage_state if row.outage_state != "unknown" else "any"}
    # Exact active configuration for known-state comparisons; missing invocation is never inferred clear.
    if row.outage_state != "unknown":
        out["required_sets"] = [x for x in row.active_sets.split("|") if x]
        out["exact_sets"] = True
    for col in settings["features"]:
        value = getattr(row,col)
        if pd.notna(value): out[col] = float(value)
    return out


def analogue_predictions(bundle, frame, setting, method="analogue"):
    predictions, probs, support = [], [], []
    for row in frame.itertuples():
        query = row_query(row, setting, "analogue" if method in {"no_network","no_weather"} else method)
        if method == "no_network":
            query.pop("required_sets",None);query.pop("exact_sets",None);query["outage_state"]="any"
        if method == "no_weather":
            for feature in list(query):
                if any(word in feature for word in ("temperature","humidity","corridor_")):query.pop(feature)
        result = bundle.select(query, details=False)
        predictions.append([result.get(k) for k in ("p10_mw","p50_mw","p90_mw")])
        probs.append(result.get("restricted_share"))
        support.append(result["status"])
    return np.asarray(predictions,float), np.asarray(probs,float), support


def usable_panel():
    panel = pd.read_parquet(DATA / "panel.parquet")
    bad = panel.connector.isin(["QNI","VNI"]) & panel.time.dt.normalize().eq(pd.Timestamp("2026-08-05"))
    return panel[~bad].copy()


def folds(panel):
    c = config(); start = panel.time.min().normalize()
    train_end = start + pd.DateOffset(months=c["train_months"])
    end = panel.time.max() + pd.Timedelta(minutes=30)
    n = 0
    while True:
        select_end = train_end + pd.Timedelta(weeks=c["selection_weeks"])
        cal_end = select_end + pd.Timedelta(weeks=c["calibration_weeks"])
        eval_end = cal_end + pd.Timedelta(weeks=c["evaluation_weeks"])
        if eval_end > end: break
        yield {"id":f"fold_{n:02d}_{cal_end:%Y%m%d}","start":start,"train_end":train_end,
               "select_end":select_end,"alert_start":cal_end-pd.Timedelta(weeks=c["alert_tuning_weeks"]),"cal_end":cal_end,"eval_end":eval_end}
        train_end += pd.Timedelta(weeks=c["evaluation_weeks"]); n += 1


def partitions(frame, fold):
    bounds = {"train":(fold["start"],fold["train_end"]), "selection":(fold["train_end"],fold["select_end"]),
              "calibration":(fold["select_end"],fold["alert_start"]), "alert":(fold["alert_start"],fold["cal_end"]),
              "evaluation":(fold["cal_end"],fold["eval_end"])}
    # Identify complete incident spans. Only earlier portions of a boundary-crossing incident are purged.
    exploded = frame[["time","episode_ids"]].assign(episode_ids=frame.episode_ids.str.split("|")).explode("episode_ids")
    spans = exploded[exploded.episode_ids.ne("")].groupby("episode_ids").time.agg(["min","max"])
    output, audit = {}, {}
    for name, (a,b) in bounds.items():
        f = frame[(frame.time > a) & (frame.time <= b)].copy()
        before = len(f)
        if name != "evaluation":
            crossing = list(spans.index[(spans["min"] <= b) & (spans["max"] > b)])
            if crossing:
                pattern = r"(?:^|\|)(?:" + "|".join(re.escape(x) for x in crossing) + r")(?=\||$)"
                f = f[~f.episode_ids.str.contains(pattern,regex=True,na=False)]
        output[name] = f
        audit[name] = {"rows":len(f),"purged":before-len(f),"start":str(a),"end":str(b)}
    return output,audit


def tune_analogue(train, selection):
    key = f"{train.connector.iat[0]}/{train.direction.iat[0]}"
    # Stratified pre-evaluation subset for tuning; all 48 half-hours remain in final evaluation.
    sample = selection.iloc[::max(1,len(selection)//192)].head(192)
    scores = []
    for radius in config()["half_hour_radius"]:
        for days in config()["neighbour_days"]:
            setting = fit_settings(train, days, radius)
            bundle = RegimeBundle(train, metadata_for(train,{key:setting}))
            p,_,_ = analogue_predictions(bundle,sample,setting)
            ok = np.isfinite(p).all(axis=1)
            scores.append({"radius":radius,"days":days,"pinball":loss(sample.capacity.to_numpy()[ok],p[ok]) if ok.any() else 1e30,"n":int(ok.sum())})
    best = min(scores,key=lambda s:s["pinball"])
    return best,scores


def pilot():
    with stage("pilot", [DATA / "panel.parquet"]) as artifacts:
        panel = usable_panel()
        first = next(folds(panel))
        results = []
        start = time.monotonic()
        for name in ("VNI","Heywood"):
            for direction in ("forward","reverse"):
                frame = panel[(panel.connector==name)&(panel.direction==direction)]
                split,audit = partitions(frame,first)
                best,trials = tune_analogue(split["train"],split["selection"])
                out = DATA / "tuning" / f"{name}_{direction}.json"
                write_json(out,{"best":best,"trials":trials,"training_end":str(first["train_end"]),"audit":audit})
                results.append({"connector":name,"direction":direction,**best})
                artifacts.append(out)
                print("Pilot", name,direction,best,flush=True)
        write_json(DATA / "pilot.json",{"results":results,"seconds":round(time.monotonic()-start,2),"protocol_frozen":True,
                   "decision":"Proceed with the same bounded grid on six links; no test-informed tuning"})
        artifacts.append(DATA / "pilot.json")


def _predict_method(method, train, frame, setting, model=None):
    if method in {"baseline","analogue","unweighted","no_network","no_weather"}:
        key = f"{train.connector.iat[0]}/{train.direction.iat[0]}"
        return analogue_predictions(RegimeBundle(train,metadata_for(train,{key:setting})),frame,setting,method)
    return predict_quantiles(model,frame),None,["modelled_conditional"]*len(frame)


@contextmanager
def worker_owner(cell):
    folder=DATA/"worker_owners";folder.mkdir(exist_ok=True)
    path=folder/f"{os.getpid()}.json"
    write_json(path,{"pid":os.getpid(),"process_started":psutil.Process().create_time(),"cell":cell,"stage":"evaluate"})
    try:yield []
    finally:path.unlink(missing_ok=True)


def evaluate(_cell=None,_deadline=None):
    context=worker_owner(_cell) if _cell else stage("evaluate",[DATA / "panel.parquet",DATA / "pilot.json"])
    with context as artifacts, threadpool_limits(limits=2):
        panel=usable_panel(); all_predictions=[]; audits=[]; started=time.monotonic()
        foldlist=list(folds(panel))
        if _cell is None:
            deadline=time.time()+config()["modelling_hours"]*3600
            with ProcessPoolExecutor(max_workers=config()["workers"]) as pool:
                jobs=[pool.submit(evaluate,_cell=(name,direction),_deadline=deadline) for name in config()["connectors"] for direction in ("forward","reverse")]
                for job in jobs:
                    paths,entries=job.result();all_predictions.extend(Path(p) for p in paths);audits.extend(entries)
        for name in ([_cell[0]] if _cell else []):
            for direction in ([_cell[1]] if _cell else []):
                frame=panel[(panel.connector==name)&(panel.direction==direction)]
                tune_path=DATA/"tuning"/f"{name}_{direction}.json"
                if tune_path.exists():
                    best=json.loads(tune_path.read_text())["best"]
                else:
                    splits,_=partitions(frame,foldlist[0]);best,trials=tune_analogue(splits["train"],splits["selection"])
                    write_json(tune_path,{"best":best,"trials":trials,"training_end":str(foldlist[0]["train_end"])})
                for fold in foldlist:
                    checkpoint=DATA/"evaluation"/f"{name}_{direction}_{fold['id']}.parquet"
                    meta=checkpoint.with_suffix(".json")
                    signature=research_signature([DATA/"panel.parquet",tune_path])
                    if checkpoint.exists() and meta.exists():
                        old=json.loads(meta.read_text())
                        if old.get("signature")==signature and old.get("sha256")==digest(checkpoint):
                            all_predictions.append(checkpoint);audits.append(old);continue
                    if (_deadline is not None and time.time()>_deadline) or time.monotonic()-started>config()["modelling_hours"]*3600:
                        raise RuntimeError("Modelling cap reached; remaining folds remain incomplete")
                    split,audit=partitions(frame,fold)
                    train=split["train"]; evaluation=split["evaluation"]
                    setting=fit_settings(train,best["days"],best["radius"])
                    rows=[]; selections=[]
                    # Each model is independently fitted within an eligible structural era.
                    models={}
                    for era in train.era.unique():
                        eligible=train[train.era==era]
                        if eligible.time.dt.normalize().nunique()<30: continue
                        for method in ("additive","boosting"):
                            model=fit_quantiles(eligible,method=method,max_rows=config()["model_training_max_rows"])
                            models[(era,method)]=model
                    # Model selection diagnostics use selection rows, not evaluation outcomes.
                    for method in ("additive","boosting"):
                        ss=split["selection"]
                        pp=np.full((len(ss),3),np.nan)
                        for era in ss.era.unique():
                            mask=ss.era.eq(era).to_numpy()
                            if (era,method) in models: pp[mask]=predict_quantiles(models[(era,method)],ss.loc[mask])
                        ok=np.isfinite(pp).all(axis=1)
                        selections.append({"method":method,"pinball":loss(ss.capacity.to_numpy()[ok],pp[ok]) if ok.any() else None,"rows":int(ok.sum())})
                    for (era,method),model in models.items():
                        cal=split["calibration"][split["calibration"].era==era]
                        if len(cal)>=48:calibrate(model,cal)
                    for method in ("baseline","unweighted","analogue","no_network","no_weather","additive","boosting"):
                        if method in {"additive","boosting"}:
                            pred=np.full((len(evaluation),3),np.nan)
                            for era in evaluation.era.unique():
                                mask=evaluation.era.eq(era).to_numpy()
                                if (era,method) in models: pred[mask]=predict_quantiles(models[(era,method)],evaluation.loc[mask])
                            probability=None;support=["modelled_conditional"]*len(evaluation)
                        else:
                            pred,probability,support=_predict_method(method,train,evaluation,setting)
                        # Alert probability thresholds selected on a separate pre-evaluation partition.
                        alert=split["alert"]
                        alert_threshold=.5
                        if len(alert):
                            if method in {"additive","boosting"}:
                                ap=np.full((len(alert),3),np.nan)
                                for era in alert.era.unique():
                                    am=alert.era.eq(era).to_numpy()
                                    if (era,method) in models:ap[am]=predict_quantiles(models[(era,method)],alert.loc[am])
                                apr=None
                            else:
                                # Half-hour-stratified alert sample; never uses evaluation incidents.
                                alert=alert.iloc[::4]
                                ap,apr,_=_predict_method(method,train,alert,setting)
                            thresholds=np.array([setting["restriction_thresholds"].get(str(q),np.nan) for q in alert.quarter])
                            best_alert=None
                            for value in (.1,.25,.5,.75):
                                m=score(alert.capacity,ap,thresholds,apr,value)
                                if m.get("false_alerts_per_day",1e9)<=1:
                                    rank=m.get("restriction_recall") or 0
                                    if best_alert is None or rank>best_alert[0]:best_alert=(rank,value)
                            if best_alert:alert_threshold=best_alert[1]
                        f=evaluation[["time","connector","direction","era","quarter","half_hour","outage_state","capacity","tight_capacity"]].copy()
                        f=f.rename(columns={"capacity":"actual"})
                        f["fold"]=fold["id"];f["method"]=method
                        f[["p10","p50","p90"]]=pred
                        f["threshold"]=[setting["restriction_thresholds"].get(str(q),np.nan) for q in f.quarter]
                        f["probability"]=probability if probability is not None else (pred[:,0]<f.threshold.to_numpy()).astype(float)
                        f["alert_threshold"]=alert_threshold;f["support"]=support
                        rows.append(f)
                    result=pd.concat(rows,ignore_index=True)
                    checkpoint.parent.mkdir(parents=True,exist_ok=True);result.to_parquet(checkpoint,index=False)
                    entry={"connector":name,"direction":direction,"fold":fold["id"],"audit":audit,"selection":selections,
                           "signature":signature,"sha256":digest(checkpoint),"claim":"conditional known-state development; not live forecasts"}
                    write_json(meta,entry);audits.append(entry);all_predictions.append(checkpoint)
                    print("Evaluated",name,direction,fold["id"],len(evaluation),"half-hours",flush=True)
        if _cell is not None:
            return [str(p) for p in all_predictions],audits
        predictions=pd.concat([pd.read_parquet(p) for p in all_predictions],ignore_index=True)
        predictions.to_parquet(DATA/"predictions.parquet",index=False)
        scores=[];comparisons=[]
        for (name,direction),g in predictions.groupby(["connector","direction"]):
            # Common availability across all five candidates; era-specific absent models get their own availability table.
            available=g.assign(valid=np.isfinite(g[["p10","p50","p90"]]).all(axis=1)).pivot_table(index="time",columns="method",values="valid",aggfunc="min")
            common=available.index[available.fillna(False).all(axis=1)]
            matched=g[g.time.isin(common)]
            for method,f in matched.groupby("method"):
                metric=score(f.actual,f[["p10","p50","p90"]],f.threshold,f.probability,float(f.alert_threshold.median()))
                scores.append({"connector":name,"direction":direction,"method":method,"slice":"overall",**metric})
                f=f.copy()
                f["delivery_period"]=np.select([f.half_hour<12,f.half_hour<18,f.half_hour<32,f.half_hour<42],["overnight","morning","solar","evening"],default="overnight")
                for field in ("quarter","outage_state","delivery_period","support","era"):
                    for value,s in f.groupby(field):
                        scores.append({"connector":name,"direction":direction,"method":method,"slice":f"{field}:{value}",**score(s.actual,s[["p10","p50","p90"]],s.threshold,s.probability,float(s.alert_threshold.median()))})
                for label,mask in (("restricted",f.actual<f.threshold),("forced",f.actual<0)):
                    s=f[mask]
                    scores.append({"connector":name,"direction":direction,"method":method,"slice":label,**score(s.actual,s[["p10","p50","p90"]],s.threshold,s.probability,float(s.alert_threshold.median()))})
                if method!="baseline":
                    for control in (["baseline","analogue"] if method in {"additive","boosting"} else ["baseline"]):
                        comparisons.append({"connector":name,"direction":direction,"method":method,"control":control,**block_improvement(matched,method,control=control,repeats=config()["bootstrap_repeats"])})
        pd.DataFrame(scores).to_csv(DATA/"scores.csv",index=False)
        pd.DataFrame(comparisons).to_csv(DATA/"paired_comparisons.csv",index=False)
        availability=predictions.assign(valid=np.isfinite(predictions[["p10","p50","p90"]]).all(axis=1)).groupby(["connector","direction","era","method"]).valid.agg(["sum","size","mean"])
        availability.to_csv(DATA/"evaluation_availability.csv")
        overall=pd.DataFrame(scores);overall=overall[overall["slice"]=="overall"]
        gates=[]
        for row in comparisons:
            if row["control"]!=("analogue" if row["method"] in {"additive","boosting"} else "baseline"):continue
            subset=overall[(overall.connector==row["connector"])&(overall.direction==row["direction"])]
            a=subset[subset.method==row["method"]].iloc[0];b=subset[subset.method==row["control"]].iloc[0]
            reasons=[]
            if row["ci_lo"] is None or row["ci_lo"]<=0:reasons.append("paired point improvement not established")
            if a.pinball>=b.pinball:reasons.append("distributional loss not improved")
            if abs(a.coverage80-.8)>.05:reasons.append("80% interval coverage outside 75–85% convention")
            if a.p95_overstatement>b.p95_overstatement*1.05+1:reasons.append("overstatement tail worsened")
            for metric in ("restriction_recall","forced_recall"):
                if pd.notna(a[metric]) and pd.notna(b[metric]) and a[metric]<b[metric]-.02:reasons.append(metric+" worsened")
            if a.forced_events<30 or a.restriction_events<30:reasons.append("insufficient extreme-event support")
            gates.append({"connector":row["connector"],"direction":row["direction"],"method":row["method"],"control":row["control"],
                          "historical_gate_pass":not reasons,"reasons":"; ".join(reasons),"production_promotion":False})
        pd.DataFrame(gates).to_csv(DATA/"method_gates.csv",index=False)
        write_json(DATA/"fold_audit.json",audits)
        write_json(DATA/"asof_scorecard.json",{"eligible_rows":0,"status":"unavailable_historical_receipt_evidence",
                   "reason":"Retained histories have publication proxies/final-state inputs; no verified six-link historical receipt replay",
                   "collector":"On-demand collection records measured receipt for new requests; future confirmation is a separate evidence gate"})
        artifacts.extend([DATA/x for x in ("predictions.parquet","scores.csv","paired_comparisons.csv","fold_audit.json","asof_scorecard.json","method_gates.csv","evaluation_availability.csv")])


def condition_mask(frame,conditions):
    mask=np.ones(len(frame),bool)
    for key,value in conditions.items():
        if key=="outage_state":mask &= frame.outage_state.eq(value).to_numpy()
        elif key=="required_sets":
            for family in value:mask &= frame.active_sets.str.split("|").map(lambda a:family in a).to_numpy()
        elif isinstance(value,dict):
            mask &= frame[key].between(value.get("min",-np.inf),value.get("max",np.inf)).to_numpy()
    return mask


def catalogue(panel,settings):
    rows=[]
    for (name,direction,era),g in panel.groupby(["connector","direction","era"]):
        setting=settings[f"{name}/{direction}"]
        for quarter in range(1,5):
            q=g[g.quarter==quarter]
            for label,conditions in setting["regimes"][str(quarter)].items():
                matched=q[condition_mask(q,conditions)]
                for hh,s in matched.groupby("half_hour"):
                    quant=s.capacity.quantile([.1,.5,.9]).to_numpy()
                    eps=set(x for text in s.episode_ids for x in text.split("|") if x)
                    days=s.time.dt.normalize().nunique()
                    supported=days>=config()["min_days"] and (not (conditions.get("required_sets") or conditions.get("outage_state")=="invoked") or len(eps)>=config()["min_episodes"])
                    threshold=setting["restriction_thresholds"].get(str(quarter))
                    rows.append({"connector":name,"direction":direction,"era":era,"quarter":quarter,"half_hour":int(hh),"regime":label,
                                 "p10_mw":quant[0],"p50_mw":quant[1],"p90_mw":quant[2],"tight_p10_mw":float(s.tight_capacity.quantile(.1)),
                                 "forced_share":float(s.capacity.lt(0).mean()),"restricted_share":float(s.capacity.lt(threshold).mean()) if threshold else None,
                                 "days":int(days),"episodes":len(eps),"hours":len(s)/2,"status":"supported" if supported else "indicative",
                                 "conditions":json.dumps(conditions)})
    return pd.DataFrame(rows)


def bundle():
    with stage("bundle",[DATA/"panel.parquet",DATA/"scores.csv"]) as artifacts, threadpool_limits(limits=2):
        panel=usable_panel();settings={};models={}
        root=DATA/"bundle";root.mkdir(parents=True,exist_ok=True)
        for (name,direction),g in panel.groupby(["connector","direction"]):
            p=DATA/"tuning"/f"{name}_{direction}.json"
            best=json.loads(p.read_text())["best"] if p.exists() else {"days":60,"radius":2}
            settings[f"{name}/{direction}"]=fit_settings(g,best["days"],best["radius"])
            # Final fitted models are inference-only; their training rows never contribute reported scores.
            for era,e in g.groupby("era"):
                if e.time.dt.normalize().nunique()<20:continue
                for target,col in (("average","capacity"),("tight","tight_capacity")):
                    for method in ("additive","boosting"):
                        model=fit_quantiles(e,target=col,method=method,max_rows=config()["model_training_max_rows"])
                        relative=f"models/{name}_{direction}_{era}_{target}_{method}.joblib"
                        path=root/relative;path.parent.mkdir(exist_ok=True)
                        joblib.dump(model,path,compress=3)
                        models[f"{name}/{direction}/{era}/{target}/{method}"]={"file":relative,"sha256":digest(path),"calibration":"Final full-history fit; extrapolation intervals unverified"}
            print("Bundled",name,direction,flush=True)
        cat=catalogue(panel,settings);cat.to_csv(DATA/"quarterly_catalogue.csv",index=False)
        panel.to_parquet(root/"panel.parquet",index=False,compression="zstd")
        files={str(p.relative_to(root)).replace("\\","/"):digest(p) for p in root.rglob("*") if p.is_file() and p.name!="manifest.json"}
        manifest={"schema_version":1,"as_of":config()["as_of"],"training_cutoff":str(panel.time.max()),"settings":settings,"models":models,"files":files,
                  "bundle_id":"conditional-regimes-v1-"+digest(root/"panel.parquet")[:12],"claim":"conditional research; no live forecast promotion",
                  "clear_definition":"No mapped relevant invoked family; not proof all equipment is in service",
                  "current_eras":{n:structural_era(n,config()["as_of"]) for n in config()["connectors"]},
                  "unsupported_measurements":["battery stored energy","unverified SIPS armed status","unverified lightning reclassification","complete current-month invocation"]}
        write_json(root/"manifest.json",manifest)
        chosen=RegimeBundle(panel,manifest,root)
        example={"connector":"VNI","direction":"forward","era":"pre_pec_market","outage_state":"invoked","scenario_name":"historical_vni_conditioned"}
        result=chosen.profile(1,example)
        chosen.export(result,DATA/"example_profile.json")
        chosen.export(result,DATA/"example_profile.csv")
        import zipfile
        archive=DATA/"nemic_regimes_bundle_v1.zip"
        with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for p in root.rglob("*"):
                if p.is_file():z.write(p,p.relative_to(root))
        artifacts.extend([root/"manifest.json",DATA/"quarterly_catalogue.csv",DATA/"example_profile.json",DATA/"example_profile.csv",archive])
