"""Requested-outage repetition audit layered over the unchanged point estimator."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .core import RegimeBundle as PointBundle, load_bundle as load_point_bundle, NUMERIC_FEATURES, _tokens, weighted_quantiles, _clean


def requested_episode_counts(ids, required_sets, required_assets, links):
    """Background outages and resubmissions cannot inflate a requested family's repeats."""
    found={"set:"+x:set() for x in required_sets}
    found.update({"asset:"+x:set() for x in required_assets})
    for ident in ids:
        record=links.get(str(ident))
        if not record or not record.get("canonical_id"):continue
        canonical=str(record["canonical_id"])
        for key in found:
            kind,value=key.split(":",1)
            if value in record.get("sets" if kind=="set" else "assets",[]):found[key].add(canonical)
    return {key:len(value) for key,value in found.items()}


class EvidenceBundle(PointBundle):
    def select(self,conditions,*,details=True):
        if isinstance(conditions,dict) and conditions.get("method")=="table":
            return self._table(conditions,details=details)
        result=super().select(conditions,details=details)
        if not isinstance(result,dict) or result.get("evidence_audit_version"):return result
        q=result.get("conditions",{})
        required_sets=q.get("required_sets",[]);required_assets=q.get("required_assets",[])
        if not (required_sets or required_assets) or result.get("status") in {"unavailable","modelled_extrapolation","reference"}:return result
        g=self._candidates(q)
        if g is None:return result
        setting=self._settings(q["connector"],q["direction"])
        dist=abs(g.half_hour.to_numpy().astype(int)-q["half_hour"])
        mask=(g.quarter.to_numpy()==q["quarter"]) & (np.minimum(dist,48-dist)<=setting.get("half_hour_radius",2))
        if q.get("daytype"):mask &= g.daytype.to_numpy()==q["daytype"]
        if q.get("outage_state","any")!="any":mask &= g.outage_state.to_numpy()==q["outage_state"]
        if q.get("exact_sets"):mask &= g.active_sets.to_numpy()=="|".join(sorted(required_sets))
        for field,values,excluded in (("active_sets",required_sets,False),("active_sets",q.get("excluded_sets",[]),True),("active_assets",required_assets,False)):
            for value in values:
                hit=g[field].map(lambda s:value in _tokens(s)).to_numpy()
                mask &= ~hit if excluded else hit
        for field,value in q.items():
            if field not in NUMERIC_FEATURES or value is None:continue
            if field not in setting.get("scales",{}):mask[:]=False;continue
            if isinstance(value,dict):mask &= g[field].between(value.get("min",-np.inf),value.get("max",np.inf)).to_numpy()
            else:mask &= (g[field]-float(value)).abs().le(setting["scales"][field]["scale"]).to_numpy()
        ids=set().union(*g.loc[mask,"episode_ids"].map(_tokens)) if mask.any() else set()
        counts=requested_episode_counts(ids,required_sets,required_assets,self.metadata.get("episode_links",{}))
        verified=min(counts.values()) if counts else 0
        result["background_outage_episode_ids"]=result.get("outage_episodes",0)
        result["outage_episodes"]=verified
        result["requested_episode_counts"]=counts
        result["evidence_audit_version"]=1
        result["episode_support_scope"]="Exact-condition candidate history before neighbour-day selection; requested components only; resubmissions collapsed"
        if result["status"]=="supported_analogue" and verified<setting.get("min_episodes",5):
            result["status"]="broader_analogue"
            result["low_support_reason"]="Fewer than required independent episodes of a requested outage; background episodes do not qualify"
        return result

    def _table(self,conditions,details=True):
        q=self._normalise({**conditions,"method":"analogue"})
        reference=super().select({**q,"method":"baseline"},details=False)
        g=self._candidates(q)
        base={"connector":q["connector"],"direction":q["direction"],"quarter":q["quarter"],"half_hour":q["half_hour"],
              "era":q["era"],"target":q["target"],"method":"conditional_table","conditions":{**q,"method":"table"},
              "bundle_id":self.metadata.get("bundle_id"),"baseline":reference.get("baseline"),"relaxed_conditions":[],
              "information_class":"asof_inputs_conditional_research_model" if q["mode"]=="asof" else "user_scenario","scenario_name":q.get("scenario_name"),
              "interpretation":"Conditional AEMO reported dispatch limit; not secure physical capability"}
        if g is None:
            return {**base,"status":"unavailable","reason":"No compatible topology/market-era history","p10_mw":None,"p50_mw":None,"p90_mw":None,"analogues":[],"stress_examples":[]}
        mask=g.quarter.eq(q["quarter"]) & g.half_hour.eq(q["half_hour"])
        if q.get("daytype"):mask &= g.daytype.eq(q["daytype"])
        if q.get("outage_state","any")!="any":mask &= g.outage_state.eq(q["outage_state"])
        if q.get("exact_sets"):mask &= g.active_sets.eq("|".join(sorted(q.get("required_sets",[]))))
        for field,values,excluded in (("active_sets",q.get("required_sets",[]),False),("active_sets",q.get("excluded_sets",[]),True),("active_assets",q.get("required_assets",[]),False)):
            for value in values:
                hit=g[field].map(lambda s:value in _tokens(s));mask &= ~hit if excluded else hit
        setting=self._settings(q["connector"],q["direction"])
        for field,value in q.items():
            if field not in NUMERIC_FEATURES or value is None:continue
            if isinstance(value,dict):mask &= g[field].between(value.get("min",-np.inf),value.get("max",np.inf))
            else:
                scale=setting.get("scales",{}).get(field,{}).get("scale")
                mask &= g[field].notna() & ((g[field]-float(value)).abs()<=scale) if scale is not None else False
        f=g[mask]
        if f.empty:return {**base,"status":"unavailable","reason":"No exact conditional-table observations; choose analogue or explicit extrapolation for a broader reference","p10_mw":None,"p50_mw":None,"p90_mw":None,"analogues":[],"stress_examples":[]}
        target="capacity" if q["target"]=="average" else "tight_capacity"
        quantiles=weighted_quantiles(f[target],np.ones(len(f)))
        ids=set().union(*f.episode_ids.map(_tokens))
        counts=requested_episode_counts(ids,q.get("required_sets",[]),q.get("required_assets",[]),self.metadata.get("episode_links",{}))
        canonical={self.metadata.get("episode_links",{}).get(ident,{}).get("canonical_id") for ident in ids}-{None}
        episodes=min(counts.values()) if counts else len(canonical)
        days=int(f.time.dt.normalize().nunique())
        specific=bool(counts or q.get("outage_state")=="invoked")
        supported=days>=setting.get("min_days",20) and (not specific or episodes>=setting.get("min_episodes",5))
        def records(frame):return frame[["time","capacity","tight_capacity","active_sets","active_assets","episode_ids"]].to_dict("records")
        examples=f.assign(_day=f.time.dt.normalize()).drop_duplicates("_day").head(8)
        stress=f.sort_values(target).assign(_day=lambda s:s.time.dt.normalize()).drop_duplicates("_day").head(5)
        threshold=setting.get("restriction_thresholds",{}).get(str(q["quarter"]))
        return _clean({**base,"status":"supported_table" if supported else "indicative_table","p10_mw":quantiles[0],"p50_mw":quantiles[1],"p90_mw":quantiles[2],
                       "tight_p10_mw":weighted_quantiles(f.tight_capacity,np.ones(len(f)))[0],"analogue_days":days,"exact_days":days,"outage_episodes":episodes,
                       "requested_episode_counts":counts,"observation_hours":len(f)/2,"known_outage_state_share":float(f.outage_state.ne("unknown").mean()),
                       "restricted_share":float(f[target].lt(threshold).mean()) if threshold is not None else None,"forced_flow_share":float(f[target].lt(0).mean()),
                       "analogues":records(examples) if details else [],"stress_examples":records(stress) if details else [],
                       "low_support_reason":None if supported else "Insufficient independent days or requested-outage repetitions"})


def load_bundle(path,verify=True):
    base=load_point_bundle(path,verify=verify)
    return EvidenceBundle(base.panel,base.metadata,base.root)
