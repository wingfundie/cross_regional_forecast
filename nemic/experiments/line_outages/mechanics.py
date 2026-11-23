"""Direct asset/set audit, exact-version binding evidence and event timelines."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .core import BIND, OLD, ROOT, REGIONS, STUDIES, IC_REGIONS, grid, interval_mask, json_write, load, save


def standing(table, ids=None):
    paths=[BIND/"standing"/(table+".parquet")]
    paths += [ROOT/f"data/constraint_{s}_2y/standing/{table}.parquet" for s in STUDIES.values()]
    parts=[pd.read_parquet(p,filters=[("GENCONID","in",sorted(ids))] if ids is not None else None)
           for p in paths if p.exists()]
    return pd.concat(parts,ignore_index=True).drop_duplicates()


def set_members_at(members,family,at):
    f=members[members.GENCONSETID.eq(family)].copy()
    f["EFFECTIVEDATE"]=pd.to_datetime(f.EFFECTIVEDATE,errors="coerce")
    f["VERSIONNO"]=pd.to_numeric(f.VERSIONNO,errors="coerce")
    f=f[f.EFFECTIVEDATE.le(pd.Timestamp(at))]
    if f.empty:return f
    eff=f.EFFECTIVEDATE.max();f=f[f.EFFECTIVEDATE.eq(eff)]
    return f[f.VERSIONNO.eq(f.VERSIONNO.max())]


def exact_definitions(binding,definitions):
    d=definitions.copy()
    d["EFFECTIVEDATE"]=pd.to_datetime(d.EFFECTIVEDATE,errors="coerce")
    d["VERSIONNO"]=pd.to_numeric(d.VERSIONNO,errors="coerce")
    d=d.drop_duplicates(["GENCONID","EFFECTIVEDATE","VERSIONNO"],keep="last")
    f=binding.copy();f["EFFECTIVEDATE"]=pd.to_datetime(f.EFFECTIVEDATE)
    f["VERSIONNO"]=pd.to_numeric(f.VERSIONNO,errors="coerce")
    return f.merge(d,left_on=["CONSTRAINTID","EFFECTIVEDATE","VERSIONNO"],right_on=["GENCONID","EFFECTIVEDATE","VERSIONNO"],how="left",validate="many_to_one")


def mechanics(c):
    cohort=load(c,"cohort");ledger=load(c,"outage_ledger");sets=load(c,"asset_sets")
    events=load(c,"events")
    direct=sets[sets.verified & sets.asset.isin(cohort.asset)].drop_duplicates(["asset","OUTAGEID","GENCONSETID"])
    families=sorted(set(direct.GENCONSETID))
    members=load(c,"complete_set_members")
    members=members[members.GENCONSETID.isin(families)].copy()
    ids=set(members.GENCONID)
    definitions=standing("GENCONDATA",ids)
    icf=standing("SPDINTERCONNECTORCONSTRAINT",ids);cpf=standing("SPDCONNECTIONPOINTCONSTRAINT",ids)
    definitions=pd.concat([definitions,load(c,"supplement_GENCONDATA")],ignore_index=True).drop_duplicates()
    icf=pd.concat([icf,load(c,"supplement_SPDINTERCONNECTORCONSTRAINT")],ignore_index=True).drop_duplicates()
    cpf=pd.concat([cpf,load(c,"supplement_SPDCONNECTIONPOINTCONSTRAINT")],ignore_index=True).drop_duplicates()
    for f in [definitions,icf,cpf]:
        f["EFFECTIVEDATE"]=pd.to_datetime(f.EFFECTIVEDATE,errors="coerce")
        f["VERSIONNO"]=pd.to_numeric(f.VERSIONNO,errors="coerce")
        if "FACTOR" in f:f["FACTOR"]=pd.to_numeric(f.FACTOR,errors="coerce")
    spans=pd.read_parquet(OLD/"invocation_spells.parquet")
    inv=load(c,"supplement_invocations")
    if len(inv):
        extra=pd.DataFrame({"GENCONSETID":inv.GENCONSETID,"start":pd.to_datetime(inv.STARTINTERVALDATETIME),
          "end":pd.to_datetime(inv.ENDINTERVALDATETIME.astype(str).str.replace(r"^9999.*","2262-04-01",regex=True),errors="coerce").fillna(pd.Timestamp(c["window_end"])),
          "INVOCATION_ID":inv.INVOCATION_ID})
        spans=pd.concat([spans,extra],ignore_index=True).drop_duplicates("INVOCATION_ID",keep="last")
    rows,links,terms=[],[],[]
    for r in direct.itertuples():
        e=ledger[(ledger.OUTAGEID.eq(r.OUTAGEID))&ledger.asset.eq(r.asset)].iloc[0]
        mem=set_members_at(members,r.GENCONSETID,e.start)
        inv=spans[spans.GENCONSETID.eq(r.GENCONSETID)&spans.end.ge(e.start)&spans.start.le(e.end)]
        invoked=interval_mask(grid(c),inv,inclusive_start=True)&interval_mask(grid(c),pd.DataFrame([{"start":e.start,"end":e.end}]))
        links.append({"asset":r.asset,"OUTAGEID":r.OUTAGEID,"family":r.GENCONSETID,"start":e.start,"end":e.end,
                      "membership_equations":len(mem),"invoked_intervals":int(invoked.sum()),"membership_status":"resolved" if len(mem) else "unresolved"})
        for m in mem.itertuples():
            d=definitions[definitions.GENCONID.eq(m.GENCONID)&definitions.EFFECTIVEDATE.le(e.start)].sort_values(["EFFECTIVEDATE","VERSIONNO"])
            latest=d.iloc[-1] if len(d) else None
            rows.append({"asset":r.asset,"family":r.GENCONSETID,"OUTAGEID":r.OUTAGEID,"constraint":m.GENCONID,
                         "set_effective":m.EFFECTIVEDATE,"set_version":m.VERSIONNO,
                         "description":str(latest.DESCRIPTION) if latest is not None else "Unresolved definition",
                         "limit_type":str(latest.LIMITTYPE) if latest is not None else "unresolved",
                         "constraint_type":str(latest.CONSTRAINTTYPE) if latest is not None else "unresolved",
                         "reason":str(latest.REASON) if latest is not None else "unresolved",
                         "definition_status":"resolved" if latest is not None else "unresolved"})
    crosswalk=pd.DataFrame(rows).drop_duplicates()
    save(c,"asset_constraint_crosswalk",crosswalk);save(c,"asset_set_audit",pd.DataFrame(links))
    # Sparse panel covers binding/near-binding only; absence does not establish that an equation was never invoked.
    binding=[]
    for p in sorted((BIND/"binding_panel").glob("[0-9][0-9][0-9][0-9]-[0-9][0-9].parquet")):
        f=pd.read_parquet(p);f=f[f.CONSTRAINTID.isin(ids)]
        if len(f):binding.append(f)
    additional=load(c,"supplement_constraint_observations")
    if len(additional):binding.append(additional)
    bp=pd.concat(binding,ignore_index=True) if binding else pd.DataFrame()
    if len(bp):
        bp=exact_definitions(bp,definitions)
        bp=bp.drop_duplicates(["time","CONSTRAINTID","EFFECTIVEDATE","VERSIONNO"])
    save(c,"constraint_observations",bp)
    # Factors exported with native version identity; never use latest factors for an old dispatch interval.
    ic_terms=icf[icf.GENCONID.isin(ids)].copy();ic_terms["term_kind"]="interconnector"
    cp_terms=cpf[cpf.GENCONID.isin(ids)&cpf.BIDTYPE.eq("ENERGY")].copy();cp_terms["term_kind"]="connection_point"
    save(c,"equation_ic_terms",ic_terms);save(c,"equation_cp_terms",cp_terms)
    summaries=[];observations=[]
    for r in cohort.itertuples():
        ev=events[events.asset.eq(r.asset)]
        linked=direct[direct.asset.eq(r.asset)]
        for event in ev.itertuples():
            event_sets=linked[linked.OUTAGEID.isin(event.outage_ids.split("|"))]
            accepted=[]
            for family in sorted(set(event_sets.GENCONSETID)):
                inv=spans[spans.GENCONSETID.eq(family)&spans.end.ge(event.start)&spans.start.le(event.end)]
                if not len(bp) or inv.empty:continue
                own=bp[bp.time.gt(event.start)&bp.time.le(event.end)].copy()
                own=own[interval_mask(own.time.sort_values().drop_duplicates(),inv,inclusive_start=True)[np.searchsorted(np.sort(own.time.unique()),own.time.to_numpy())]] if len(own) else own
                # Resolve set membership at every observed dispatch timestamp, including changes inside long outages.
                relevant=members[members.GENCONSETID.eq(family)].copy()
                change_dates=sorted(set(pd.to_datetime(relevant.EFFECTIVEDATE,errors="coerce").dropna()))
                if len(own) and change_dates:
                    segments=np.searchsorted(np.array(change_dates,dtype="datetime64[ns]"),own.time.to_numpy(),side="right")-1
                    accepted_mask=np.zeros(len(own),dtype=bool)
                    names=own.CONSTRAINTID.to_numpy()
                    for segment in np.unique(segments):
                        if segment<0:continue
                        ids_at=set(set_members_at(members,family,change_dates[segment]).GENCONID)
                        where=segments==segment
                        accepted_mask[where]=np.isin(names[where],list(ids_at))
                    own=own[accepted_mask]
                    own["asset"]=r.asset;own["event_id"]=event.event_id;own["family"]=family
                    accepted.append(own)
            own=pd.concat(accepted,ignore_index=True).drop_duplicates(["time","CONSTRAINTID"]) if accepted else pd.DataFrame()
            total=int(interval_mask(grid(c),pd.DataFrame([{"start":event.start,"end":event.end}])).sum())
            if len(own):observations.append(own)
            if len(own):
                for constraint,g in own.groupby("CONSTRAINTID"):
                    b=g[g.binding]
                    summaries.append({"asset":r.asset,"event_id":event.event_id,"constraint":constraint,
                        "binding_intervals":b.time.nunique(),"near_or_binding_intervals":g.time.nunique(),"equipment_intervals":total,
                        "binding_share":b.time.nunique()/total if total else np.nan,
                        "median_abs_mv":float(b.MARGINALVALUE.abs().median()) if len(b) else np.nan,
                        "description":g.DESCRIPTION.iloc[0],"limit_type":g.LIMITTYPE.iloc[0],
                        "definition_unresolved":int(g.DESCRIPTION.isna().sum()),"families":"|".join(sorted(set(g.family)))})
    save(c,"mechanism_summary",pd.DataFrame(summaries,columns=["asset","event_id","constraint","binding_intervals","near_or_binding_intervals","equipment_intervals","binding_share","median_abs_mv","description","limit_type","definition_unresolved","families"]))
    save(c,"event_constraint_observations",pd.concat(observations,ignore_index=True) if observations else pd.DataFrame())
    return {"direct_asset_set_links":len(links),"equation_links":len(crosswalk),"binding_event_equations":len(summaries),
            "unresolved_definition_links":int(crosswalk.definition_status.eq("unresolved").sum())}


def events(c):
    cohort=load(c,"cohort");ev=load(c,"events");mechanism=load(c,"mechanism_summary")
    panels={r:load(c,"panel_"+r) for r in REGIONS}
    summaries=[]
    for r in cohort.itertuples():
        f=panels[r.region]
        for e in ev[ev.asset.eq(r.asset)].itertuples():
            g=f[f.time.gt(e.start)&f.time.le(e.end)]
            row={"asset":r.asset,"event_id":e.event_id,"outage_ids":e.outage_ids,"region":r.region,"start":e.start,"end":e.end,
                 "multi_equipment":e.multi_equipment,"hours":len(g)/12,"prices":int(g.RRP.notna().sum()),
                 "mean_price":g.RRP.mean(),"max_price":g.RRP.max(),"min_price":g.RRP.min(),"price_sd":g.RRP.std(),
                 "p95_p05":g.RRP.quantile(.95)-g.RRP.quantile(.05),"mean_abs_change":g.price_change.mean(),
                 "mean_demand":g.demand.mean(),"mean_available_generation":g.available_generation.mean(),
                 "mean_wind":g.wind.mean(),"mean_solar":g.solar.mean(),"mean_co_outages":g.outage_count.mean()-1,
                 "binding_equations":int(mechanism[mechanism.event_id.eq(e.event_id)].binding_intervals.gt(0).sum())}
            for name in ["spike300","spike1000","negative","negative100"]:
                values=g[name].to_numpy();row[name+"_share"]=np.nanmean(values) if len(values) else np.nan
                hit=values==1;groups=np.cumsum(np.r_[True,hit[1:]!=hit[:-1]]) if len(hit) else np.array([])
                lengths=pd.Series(hit).groupby(groups).agg(["first","size"]) if len(hit) else pd.DataFrame()
                row[name+"_longest_minutes"]=int(lengths.loc[lengths["first"],"size"].max()*5) if len(lengths) and lengths["first"].any() else 0
            summaries.append(row)
    s=pd.DataFrame(summaries);selected=[]
    for r in cohort[cohort.deep_dive].itertuples():
        g=s[s.asset.eq(r.asset)].sort_values(["mean_abs_change","event_id"]).copy()
        if g.empty:continue
        picks=[("high_stress",len(g)-1),("typical",len(g)//2),("low_stress",0)]
        seen=set()
        for label,index in picks:
            e=g.iloc[index]
            if e.event_id in seen:continue
            seen.add(e.event_id);d=e.to_dict();d["case_role"]=label;selected.append(d)
    chosen=pd.DataFrame(selected)
    save(c,"event_summary",s);save(c,"case_selection",chosen)
    timeline=[];iclines=[]
    directory=c["_data"]/"timelines";directory.mkdir(exist_ok=True)
    for e in chosen.itertuples():
        for region,f in panels.items():
            g=f[f.time.gt(e.start-pd.Timedelta(hours=48))&f.time.le(e.end+pd.Timedelta(hours=48))].copy()
            g["asset"]=e.asset;g["event_id"]=e.event_id;g["hours_from_start"]=(g.time-e.start).dt.total_seconds()/3600
            g["in_outage"]=g.time.gt(e.start)&g.time.le(e.end)
            g.to_parquet(directory/f"{e.event_id}_{region}.parquet",index=False)
        for ic in STUDIES:
            f=load(c,"ic_"+ic)
            g=f[f.time.gt(e.start-pd.Timedelta(hours=48))&f.time.le(e.end+pd.Timedelta(hours=48))].copy()
            g["asset"]=e.asset;g["event_id"]=e.event_id;g["hours_from_start"]=(g.time-e.start).dt.total_seconds()/3600
            g.to_parquet(directory/f"{e.event_id}_{ic}.parquet",index=False)
            source,sink=IC_REGIONS[ic]
            ps=panels[source].set_index("time").RRP;pk=panels[sink].set_index("time").RRP
            g["price_spread"]=g.time.map(pk)-g.time.map(ps)
            g["state"]=np.where(g.time.le(e.start),"before",np.where(g.time.le(e.end),"during","after"))
            for state,h in g.groupby("state"):
                iclines.append({"asset":e.asset,"event_id":e.event_id,"ic":ic,"state":state,"intervals":len(h),
                                "mean_flow_mw":h.flow.mean(),"mean_forward_limit_mw":h.forward_capacity.mean(),
                                "mean_reverse_capacity_mw":h.reverse_capacity.mean(),
                                "minimum_forward_limit_mw":h.forward_capacity.min(),"minimum_reverse_capacity_mw":h.reverse_capacity.min(),
                                "mean_forward_headroom_mw":h.forward_headroom.mean(),"mean_reverse_headroom_mw":h.reverse_headroom.mean(),
                                "mean_price_spread":h.price_spread.mean(),
                                "interpretation":"observed before/during/after; dispatch limits and spreads, no isolated outage effect"})
    save(c,"interconnector_event_response",pd.DataFrame(iclines))
    # Generator response is observed dispatch, separately from mechanical coefficient sensitivity.
    crosswalk=load(c,"asset_constraint_crosswalk");cp=load(c,"equation_cp_terms")
    details=pd.read_parquet(BIND/"standing/DUDETAILSUMMARY.parquet")
    details["START_DATE"]=pd.to_datetime(details.START_DATE,errors="coerce")
    details["END_DATE"]=pd.to_datetime(details.END_DATE.astype(str).str.replace(r"^9999.*","2262-04-01",regex=True),errors="coerce")
    generation=[]
    for e in chosen.itertuples():
        ids=set(crosswalk.loc[crosswalk.asset.eq(e.asset),"constraint"])
        terms=cp[cp.GENCONID.isin(ids)&cp.EFFECTIVEDATE.le(e.start)]
        version=terms[["GENCONID","EFFECTIVEDATE","VERSIONNO"]].drop_duplicates().sort_values(["EFFECTIVEDATE","VERSIONNO"]).drop_duplicates("GENCONID",keep="last")
        points=set(terms.merge(version,on=["GENCONID","EFFECTIVEDATE","VERSIONNO"]).CONNECTIONPOINTID)
        active=details[details.START_DATE.le(e.end)&(details.END_DATE.isna()|details.END_DATE.ge(e.start))]
        duids=set(active.loc[active.CONNECTIONPOINTID.isin(points),"DUID"])
        if e.asset=="CANBERRA/LINE/6":duids |= set(active.loc[active.DUID.str.contains("CAPTL|WOODL",case=False,regex=True,na=False),"DUID"])
        pieces=[]
        for month in pd.period_range((e.start-pd.Timedelta(hours=48)).to_period("M"),(e.end+pd.Timedelta(hours=48)).to_period("M"),freq="M"):
            p=BIND/"dispatchload"/f"{month}.parquet"
            if not p.exists() or not duids:continue
            f=pd.read_parquet(p,filters=[("DUID","in",sorted(duids)),("time",">",e.start-pd.Timedelta(hours=48)),("time","<=",e.end+pd.Timedelta(hours=48))])
            pieces.append(f)
        if not pieces:continue
        f=pd.concat(pieces,ignore_index=True).drop_duplicates(["time","DUID"])
        f["event_id"]=e.event_id;f["asset"]=e.asset
        f["state"]=np.where(f.time.le(e.start),"before",np.where(f.time.le(e.end),"during","after"))
        f.to_parquet(directory/f"{e.event_id}_generation.parquet",index=False)
        for (unit,state),g in f.groupby(["DUID","state"]):
            generation.append({"asset":e.asset,"event_id":e.event_id,"DUID":unit,"state":state,"intervals":len(g),
                               "mean_dispatch_mw":g.TOTALCLEARED.mean(),"min_dispatch_mw":g.TOTALCLEARED.min(),
                               "max_dispatch_mw":g.TOTALCLEARED.max(),"interpretation":"observed dispatch; available weather/offers also influence output"})
    save(c,"generation_response",pd.DataFrame(generation,columns=["asset","event_id","DUID","state","intervals","mean_dispatch_mw","min_dispatch_mw","max_dispatch_mw","interpretation"]))
    return {"event_summaries":len(s),"selected_cases":len(chosen),"deep_dive_assets":chosen.asset.nunique(),"generation_state_records":len(generation)}


def setters(c):
    """Reconstructed conditional-envelope leaders, kept separate from published binding."""
    co=load(c,"cohort");events=load(c,"events");links=load(c,"asset_sets")
    members=load(c,"complete_set_members");rows=[]
    members["EFFECTIVEDATE"]=pd.to_datetime(members.EFFECTIVEDATE)
    member_cache={}
    windows=events[events.asset.isin(co.asset)]
    for ic,study in STUDIES.items():
        pieces=[]
        for month in pd.period_range(pd.Timestamp(c["window_start"]).to_period("M"),pd.Timestamp(c["window_end"]).to_period("M")-1,freq="M"):
            p=ROOT/f"data/constraint_{study}_2y/months/{month}/constraint_features_5min.parquet"
            pieces.append(pd.read_parquet(p,columns=["time","upper_constraint","lower_constraint","upper_version_key","lower_version_key"]))
        f=pd.concat(pieces,ignore_index=True).drop_duplicates("time").sort_values("time")
        for e in windows.itertuples():
            g=f[f.time.gt(e.start)&f.time.le(e.end)]
            linked=links[links.asset.eq(e.asset)&links.OUTAGEID.isin(e.outage_ids.split("|"))&links.verified]
            families=sorted(set(linked.GENCONSETID));resolved=all(len(set_members_at(members,s,e.start))>0 for s in families) and bool(families)
            # Resolve membership once per effective-date segment, not once per five-minute interval.
            changes=sorted(set(members.loc[members.GENCONSETID.isin(families)&members.EFFECTIVEDATE.le(e.end),"EFFECTIVEDATE"])|{e.start})
            change_values=np.array(changes,dtype="datetime64[ns]")
            segments=np.searchsorted(change_values,g.time.to_numpy(),side="right")-1
            owned={}
            for segment in np.unique(segments):
                at=changes[segment];all_ids=set()
                for family in families:
                    key=(family,at)
                    if key not in member_cache:member_cache[key]=set(set_members_at(members,family,at).GENCONID)
                    all_ids |= member_cache[key]
                owned[segment]=all_ids
            for direction,prefix in [("forward","upper"),("reverse","lower")]:
                names=g[prefix+"_constraint"];versions=g[prefix+"_version_key"]
                values=names.to_numpy()
                hits=sum(int(np.isin(values[segments==s],list(ids)).sum()) for s,ids in owned.items())
                tops=versions.dropna().value_counts().head(3)
                rows.append({"asset":e.asset,"event_id":e.event_id,"ic":ic,"direction":direction,
                             "intervals":len(g),"resolved_leader_intervals":int(names.notna().sum()),
                             "own_member_leader_intervals":hits if resolved else np.nan,
                             "own_member_leader_share":hits/len(g) if resolved and len(g) else np.nan,
                             "top_versioned_leaders":" | ".join(f"{name}: {count/len(g):.1%}" for name,count in tops.items()),
                             "membership_resolved":resolved,
                             "interpretation":"conditional envelope leader; membership does not prove this outage invoked or caused the leader"})
    save(c,"setter_summary",pd.DataFrame(rows))
    return {"event_link_direction_rows":len(rows),"membership_unresolved_rows":sum(not r["membership_resolved"] for r in rows)}
