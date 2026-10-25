"""Final descriptive catalogue and inference packaging, separate from fold fitting."""
from __future__ import annotations
import hashlib
import json
import zipfile
import joblib
import pandas as pd
import numpy as np
from threadpoolctl import threadpool_limits
from nemic_regimes.core import RegimeBundle, structural_era, weighted_quantiles
from nemic_regimes.models import fit_quantiles
from .common import DATA, ROOT, config, digest, stage, write_json
from .research import usable_panel, fit_settings
from .data import extension
from nemic_regimes.evidence import EvidenceBundle,requested_episode_counts


def enrich_regimes(group, setting):
    """Exploratory full-history display cases; never selection/evaluation inputs."""
    for quarter in range(1,5):
        f=group[group.quarter==quarter]
        definitions=setting["regimes"][str(quarter)]
        configurations=f.loc[f.active_sets.ne(""),"active_sets"].value_counts()
        joint=[x for x in configurations.index if len(x.split("|"))>=2][:3]
        for i,value in enumerate(joint,1):
            definitions[f"joint_outage_configuration_{i}"]={"required_sets":value.split("|")}
        for feature,side,label in (("electrical_positive_mw","max","outage_low_positive_group_output"),
                                    ("electrical_negative_mw","min","outage_high_negative_group_output")):
            values=f[feature].dropna()
            if len(values)>=48*20:
                definitions[label]={"outage_state":"invoked",feature:{side:float(values.quantile(.2 if side=="max" else .8))}}
    return setting


def build_bundle():
    with stage("bundle",[DATA/"panel.parquet",DATA/"assessed_scores.csv"]) as artifacts, threadpool_limits(limits=2):
        panel=usable_panel();settings={};models={}
        root=DATA/"bundle";root.mkdir(parents=True,exist_ok=True)
        for (name,direction),g in panel.groupby(["connector","direction"]):
            p=DATA/"tuning"/f"{name}_{direction}.json"
            best=json.loads(p.read_text())["best"] if p.exists() else {"days":60,"radius":2}
            settings[f"{name}/{direction}"]=enrich_regimes(g,fit_settings(g,best["days"],best["radius"]))
            for era,e in g.groupby("era"):
                if e.time.dt.normalize().nunique()<20:continue
                for target,col in (("average","capacity"),("tight","tight_capacity")):
                    for method in ("additive","boosting"):
                        relative=f"models/{name}_{direction}_{era}_{target}_{method}.joblib"
                        path=root/relative;path.parent.mkdir(exist_ok=True)
                        model=fit_or_reuse(e,col,method,path)
                        models[f"{name}/{direction}/{era}/{target}/{method}"]={"file":relative,"sha256":digest(path),
                            "features":model["features"],"families":model["families"],"training_rows":model["training_rows"],
                            "calibration":"Full-history inference fit; arbitrary-query extrapolation intervals unverified"}
            print("Bundled",name,direction,flush=True)
        episode_links=build_episode_links(panel)
        cat=build_catalogue(panel,settings,episode_links)
        cat.to_csv(DATA/"quarterly_catalogue.csv",index=False)
        panel.to_parquet(root/"panel.parquet",index=False,compression="zstd")
        keys=pd.read_parquet(ROOT/"data/nos_regime_v1/outage_keys.parquet")
        used={x for text in panel.active_assets for x in text.split("|") if x}
        asset=keys[keys.primary_asset.isin(used)][["primary_asset","primary_description","region","primary_voltage"]].drop_duplicates("primary_asset")
        assets=[{"asset":str(r.primary_asset),"description":str(r.primary_description) if pd.notna(r.primary_description) else str(r.primary_asset),
                 "region":str(r.region) if pd.notna(r.region) else "unresolved","voltage_kv":float(r.primary_voltage) if pd.notna(r.primary_voltage) else None} for r in asset.itertuples()]
        write_json(root/"asset_dictionary.json",assets)
        import importlib.metadata
        import platform
        versions={package:importlib.metadata.version(package) for package in ("numpy","pandas","pyarrow","scikit-learn","lightgbm","scipy")}
        versions["python"]=platform.python_version()
        write_json(root/"runtime_versions.json",versions)
        files={str(p.relative_to(root)).replace("\\","/"):digest(p) for p in root.rglob("*") if p.is_file() and p.name!="manifest.json"}
        manifest={"schema_version":1,"as_of":config()["as_of"],"training_cutoff":str(panel.time.max()),"settings":settings,"models":models,"files":files,"episode_links":episode_links,
                  "claim":"conditional research; no live forecast promotion", "assets":assets,"runtime_versions":versions,
                  "clear_definition":"No mapped relevant invoked family; not proof all equipment is in service",
                  "current_eras":{n:structural_era(n,config()["as_of"]) for n in config()["connectors"]},
                  "catalogue_extension":"Joint-outage and electrical-group display cases are exploratory full-history descriptions, not added evaluation features",
                  "unsupported_measurements":["battery stored energy","unverified SIPS armed status","unverified lightning reclassification","complete current-month invocation"]}
        identity=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
        manifest["bundle_id"]="conditional-regimes-v1-"+identity[:16]
        write_json(root/"manifest.json",manifest)
        chosen=EvidenceBundle(panel,manifest,root)
        example={"connector":"VNI","direction":"forward","era":"pre_pec_market","outage_state":"invoked","scenario_name":"historical_vni_conditioned"}
        result=chosen.profile(1,example)
        chosen.export(result,DATA/"example_profile.json");chosen.export(result,DATA/"example_profile.csv")
        archive=DATA/"nemic_regimes_bundle_v1.zip"
        with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED) as z:
            for p in root.rglob("*"):
                if p.is_file():z.write(p,p.relative_to(root))
        artifacts.extend([root/"manifest.json",DATA/"quarterly_catalogue.csv",DATA/"example_profile.json",DATA/"example_profile.csv",archive])


def fit_or_reuse(frame,target,method,path):
    from .common import PACKAGE,CONFIG
    columns=[c for c in frame if c not in {"ic"}]
    fingerprint=hashlib.sha256(pd.util.hash_pandas_object(frame[columns],index=True).values.tobytes()+
                (digest(PACKAGE/"src/nemic_regimes/models.py")+digest(CONFIG)+target+method).encode()).hexdigest()
    receipt=path.with_suffix(".json")
    old=json.loads(receipt.read_text(encoding="utf-8")) if receipt.exists() else None
    if path.exists() and old and old.get("signature")==fingerprint and old.get("sha256")==digest(path):
        return joblib.load(path)
    # Adopt a completed fit from this campaign's immediately preceding packaging failure.
    ledger=json.loads((DATA/"ledger.json").read_text(encoding="utf-8"))
    previous=[]
    for line in (DATA/"events.jsonl").read_text(encoding="utf-8").splitlines():
        entry=json.loads(line)
        if entry.get("stage")=="bundle" and entry.get("status")=="failed":previous.append(entry)
    adopted=False
    if path.exists() and not old and previous:
        run=previous[-1]
        start=pd.Timestamp(run["started"]).timestamp();end=pd.Timestamp(run["finished"]).timestamp()
        if start<=path.stat().st_mtime<=end and (PACKAGE/"src/nemic_regimes/models.py").stat().st_mtime<=start and (DATA/"panel.parquet").stat().st_mtime<=start:
            candidate=joblib.load(path)
            if candidate.get("training_end")==str(frame.time.max()) and candidate.get("method")==method:
                model=candidate;adopted=True
    if not adopted:
        model=fit_quantiles(frame,target=target,method=method,max_rows=config()["model_training_max_rows"])
        joblib.dump(model,path,compress=3)
    write_json(receipt,{"signature":fingerprint,"sha256":digest(path),"adopted_completed_fit":adopted,
                        "note":"Completed campaign fit retained after catalogue-only failure" if adopted else "Fresh deterministic fit"})
    return model


def build_catalogue(panel,settings,links):
    rows=[]
    for (name,direction,era,quarter),group in panel.groupby(["connector","direction","era","quarter"],sort=False):
        setting=settings[f"{name}/{direction}"]
        for label,conditions in setting["regimes"][str(quarter)].items():
            mask=np.ones(len(group),dtype=bool)
            for field,value in conditions.items():
                if field=="outage_state":mask &= group.outage_state.eq(value).to_numpy(dtype=bool)
                elif field=="required_sets":
                    for family in value:mask &= group.active_sets.map(lambda text:family in text.split("|")).to_numpy(dtype=bool)
                elif isinstance(value,dict):mask &= group[field].between(value.get("min",-np.inf),value.get("max",np.inf)).to_numpy(dtype=bool)
            for hh,s in group.loc[mask].groupby("half_hour",sort=False):
                qs=weighted_quantiles(s.capacity,np.ones(len(s)))
                ids={x for text in s.episode_ids for x in text.split("|") if x}
                counts=requested_episode_counts(ids,conditions.get("required_sets",[]),[],links)
                canonical={links.get(ident,{}).get("canonical_id") for ident in ids}-{None}
                episodes=min(counts.values()) if counts else len(canonical)
                days=int(s.time.dt.normalize().nunique());specific=bool(counts or conditions.get("outage_state")=="invoked")
                supported=days>=config()["min_days"] and (not specific or episodes>=config()["min_episodes"])
                threshold=setting["restriction_thresholds"].get(str(quarter))
                rows.append({"connector":name,"direction":direction,"era":era,"quarter":int(quarter),"half_hour":int(hh),"regime":label,
                             "p10_mw":qs[0],"p50_mw":qs[1],"p90_mw":qs[2],"tight_p10_mw":weighted_quantiles(s.tight_capacity,np.ones(len(s)))[0],
                             "forced_share":float(s.capacity.lt(0).mean()),"restricted_share":float(s.capacity.lt(threshold).mean()) if threshold is not None else None,
                             "days":days,"episodes":episodes,"hours":len(s)/2,"status":"supported" if supported else "indicative","conditions":json.dumps(conditions)})
    return pd.DataFrame(rows)


def build_episode_links(panel):
    used={x for value in panel.episode_ids for x in value.split("|") if x}
    raw=extension("NETWORK_OUTAGEDETAIL")
    sets=extension("NETWORK_OUTAGECONSTRAINTSET")
    old=pd.read_parquet(ROOT/"data/nos_regime_v1/episode_sets.parquet")
    sets=pd.concat([old[["OUTAGEID","GENCONSETID"]],sets[["OUTAGEID","GENCONSETID"]]],ignore_index=True).drop_duplicates()
    families=sets.groupby("OUTAGEID").GENCONSETID.agg(lambda s:sorted(set(s))).to_dict()
    successors={str(r.OUTAGEID):str(r.RESUBMITOUTAGEID) for r in raw[["OUTAGEID","RESUBMITOUTAGEID"]].drop_duplicates().itertuples() if str(r.RESUBMITOUTAGEID).strip()}
    known=set(raw.OUTAGEID.astype(str))
    raw["asset_key"]=raw.SUBSTATIONID+"/"+raw.EQUIPMENTTYPE+"/"+raw.EQUIPMENTID
    raw.loc[raw.EQUIPMENTID.eq("N/A"),"asset_key"]="EL"+raw.loc[raw.EQUIPMENTID.eq("N/A"),"ELEMENTID"]
    assets=raw[raw.OUTAGEID.isin(used)].groupby("OUTAGEID").asset_key.agg(lambda s:sorted(set(s))).to_dict()
    def canonical(ident):
        seen=set()
        while ident in successors and successors[ident] in known:
            if ident in seen:return None
            seen.add(ident);ident=successors[ident]
        return ident
    return {ident:{"canonical_id":canonical(ident),"sets":families.get(ident,[]),"assets":assets.get(ident,[])} for ident in sorted(used)}
