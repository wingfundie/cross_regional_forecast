"""Audited equipment ledger, native market panel and outcome-blind/empirical cohort."""
from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from .core import BIND, OLD, ROOT, REGIONS, STUDIES, config, grid, interval_mask, json_write, load, merge_events, save, sha
from nemic.experiments.nos_regime.episodes import equipment_at

SOURCES = [
    {"title": "AEMO Congestion Information Resource", "url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource", "use": "Constraint formulation, implementation, security and pricing references"},
    {"title": "AEMO network diagrams", "url": "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-forecasting-and-planning/forecasting-and-planning-data/diagrams-and-previous-maps", "use": "Documented connectivity; historical diagram dates must be checked"},
    {"title": "Transgrid 2025 TAPR", "url": "https://www.transgrid.com.au/media/xgun43m0/2025-transmission-annual-planning-report_update_081025.pdf", "use": "NSW corridors and network configuration context"},
    {"title": "Powerlink 2025 TAPR", "url": "https://www.powerlink.com.au/planning-report/transmission-annual-planning-report-2025", "use": "Queensland corridor context"},
    {"title": "TasNetworks network planning", "url": "https://www.tasnetworks.com.au/planning-and-projects/planning-our-network", "use": "Tasmanian network context"},
    {"title": "AEMO line 8 project assessment", "url": "https://aemo.com.au/consultations/current-and-closed-consultations/transgrid-pacr-managing-the-risk-of-corrosion-on-line-8", "use": "Dapto–Marulan line 8 identity"},
    {"title": "AEMO Capital and Woodlawn incident, 11 July 2012", "url": "https://www.aemo.com.au/-/media/Files/Electricity/NEM/Market_Notices_and_Events/Power_System_Incident_Reports/2012/Trip_of_Capital_and_Woodlawn_Wind_Farms_11_July_2012.pdf", "use": "Capital–Canberra line 6 identity; explanatory historical reference outside estimation window"},
    {"title": "NEMWEB monthly MMSDM archives", "url": "https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/", "use": "Final-state equipment/outage tables, versioned constraints, five-minute outcomes and bids"},
    {"title": "NEMWEB Network archive", "url": "https://www.nemweb.com.au/Reports/ARCHIVE/Network/", "use": "Original booking snapshots and revisions"},
]


def equipment_identity(rows,equipment):
    """Verify the exact NOS equipment key and ELEMENTID throughout the actual window."""
    f=rows.reset_index(drop=True).copy();f["_row"]=np.arange(len(f))
    e=equipment_at(equipment).copy();e["ELEMENTID"]=e.ELEMENTID.astype(str)
    keys=["ELEMENTID","SUBSTATIONID","EQUIPMENTTYPE","EQUIPMENTID"]
    joined=f[["_row","start","end",*keys]].merge(e,on=keys,how="left")
    valid=joined.VALIDFROM.le(joined.start)&joined.VALIDTO.ge(joined.end)&joined.DESCRIPTION.fillna("").str.strip().ne("")
    good=joined[valid].sort_values(["VALIDFROM","LASTCHANGED"]).drop_duplicates("_row",keep="last").set_index("_row")
    f["identity_valid"]=f._row.isin(good.index)
    for name in ["VOLTAGE","DESCRIPTION"]:
        f.loc[f.identity_valid,name]=f.loc[f.identity_valid,"_row"].map(good[name])
    return f.drop(columns="_row")


def audit(c):
    eps = pd.read_parquet(OLD / "episodes.parquet")
    assets = pd.read_parquet(OLD / "episode_assets.parquet")
    keys = pd.read_parquet(OLD / "outage_keys.parquet")
    sub = pd.read_parquet(sorted((OLD / "raw/mmsdm").glob("NETWORK_SUBSTATIONDETAIL_*.parquet"))[-1])
    line = assets[~assets.asset_is_na].copy()
    # Element identity prevents alias pooling from splitting one circuit; separate ELEMENTIDs stay separate.
    line["ELEMENTID"] = line.ELEMENTID.astype(str)
    canon = (line.groupby("ELEMENTID").asset.agg(lambda x: sorted(set(x))[0])).to_dict()
    line["source_asset"] = line.asset
    line["asset"] = line.ELEMENTID.map(canon)
    known = {alias: canon[str(el)] for alias, el in zip(line.source_asset, line.ELEMENTID)}
    x = line.merge(eps.drop(columns=[p for p in eps if p.startswith("primary_")]), on="OUTAGEID", how="inner")
    equipment=pd.read_parquet(sorted((OLD/"raw/mmsdm").glob("NETWORK_EQUIPMENTDETAIL_*.parquet"))[-1])
    x=equipment_identity(x,equipment)
    x["verified"] = ~x.withdrawn & x.ISSECONDARY.eq("0") & x.window_source.eq("actual") & x.status.eq("COMPLETE") & x.identity_valid
    x["exclusion"] = np.select([x.withdrawn, ~x.ISSECONDARY.eq("0"), ~x.window_source.eq("actual"), ~x.status.eq("COMPLETE"),~x.identity_valid],
                                ["withdrawn", "secondary", "scheduled_only", "not_complete","identity_validity_unresolved"], default="eligible")
    x["multi_equipment"] = x.n_assets.gt(1)
    # Substation regional metadata is authoritative for identified assets; element-description keys use the audited crosswalk.
    region_col = next(p for p in ["REGIONID", "REGION"] if p in sub)
    sub = sub.drop_duplicates("SUBSTATIONID", keep="last")
    x["region"] = x.SUBSTATIONID.map(sub.set_index("SUBSTATIONID")[region_col])
    fallback = keys.drop_duplicates("primary_asset").set_index("primary_asset")
    x["region"] = x.region.fillna(x.source_asset.map(fallback.region))
    x["owner"] = x.SUBSTATIONID.map(sub.set_index("SUBSTATIONID")["OWNERID"])
    x["owner"] = x.owner.fillna(x.source_asset.map(fallback.owner))
    x = x.drop_duplicates(["OUTAGEID", "asset"])
    # Co-outage controls cover identified high-voltage lines, transformers, buswork and
    # reactive plant. This broader configuration panel is separate from the line cohort.
    all_events=merge_events(x[x.verified])
    equipment_register=x.sort_values("start").drop_duplicates("asset")[["asset","region","VOLTAGE","equipment_type_used"]].rename(columns={"VOLTAGE":"voltage_kv"})
    save(c,"equipment_events",all_events);save(c,"equipment_register",equipment_register)
    x=x[x.equipment_type_used.eq("LINE")].copy()
    events = merge_events(x[x.verified])
    if len(events):
        events["multi_equipment"] = events.outage_ids.map(lambda v: bool(x[x.OUTAGEID.isin(v.split("|"))].multi_equipment.any()))
    rows = []
    for asset, g in x.groupby("asset", sort=True):
        ev = events[events.asset.eq(asset)]
        first = g.sort_values("start").iloc[0]
        regions = sorted(set(g.region.dropna()))
        rows.append({"asset": asset, "element_id": first.ELEMENTID, "description": first.DESCRIPTION,
                     "aliases": "|".join(sorted(set(g.source_asset))), "voltage_kv": float(first.VOLTAGE),
                     "region": regions[0] if len(regions) == 1 else "unresolved", "owner": str(first.owner),
                     "catalogue_rows": len(g), "withdrawn_rows": int(g.withdrawn.sum()),
                     "secondary_rows": int(g.ISSECONDARY.ne("0").sum()), "verified_rows": int(g.verified.sum()),
                     "events": len(ev), "selection_events": int((ev.end <= pd.Timestamp(c["selection_end"])).sum()),
                     "confirmation_events": int((ev.start >= pd.Timestamp(c["selection_end"])).sum()),
                     "identity_unresolved_rows":int((~g.identity_valid).sum()),
                     "identity_status": "resolved" if len(regions) == 1 and g.identity_valid.any() else "unresolved"})
    register = pd.DataFrame(rows)
    sets = pd.read_parquet(OLD / "episode_sets.parquet").merge(x[["OUTAGEID", "asset", "verified"]], on="OUTAGEID")
    save(c, "asset_register", register); save(c, "outage_ledger", x)
    save(c, "events", events); save(c, "asset_sets", sets)
    json_write(c["_data"] / "aliases.json", known)
    json_write(c["_data"] / "sources.json", {"references": SOURCES, "time_basis": "NEM UTC+10 interval ending",
        "historical_source": "final-state MMSDM; actual equipment windows only in physical treatment",
        "line6_direct_sets": sorted(set(sets.loc[sets.asset.eq(known.get("CANBERRA/LINE/6", "")) & sets.verified, "GENCONSETID"])),
        "line6_old_fallback_rejected": "V-DDSM is not attributed to line 6", "audited_utc": pd.Timestamp.now(tz="UTC").isoformat()})
    return {"resolved_lines": int(register.identity_status.eq("resolved").sum()), "verified_events": len(events),
            "line6_events": int(register.loc[register.aliases.str.contains("CANBERRA/LINE/6", regex=False), "events"].sum())}


def price_features(f, selection_end):
    f = f.sort_values("time").copy()
    f["price_change"] = f.RRP.diff().abs().where(f.time.diff().eq(pd.Timedelta(minutes=5)))
    for name, threshold in [("spike300", 300), ("spike1000", 1000), ("negative", 0), ("negative100", -100)]:
        v = f.RRP.gt(threshold) if threshold > 0 else f.RRP.lt(threshold)
        f[name] = v.astype(float).where(f.RRP.notna())
    f["season"] = f.time.dt.month.map({12:0,1:0,2:0,3:1,4:1,5:1,6:2,7:2,8:2,9:3,10:3,11:3})
    training = f[f.time < pd.Timestamp(selection_end)]
    quant = training.groupby("season").RRP.quantile([.01, .99]).unstack()
    f["tail99"] = f.RRP.gt(f.season.map(quant[.99])).astype(float).where(f.RRP.notna())
    f["tail01"] = f.RRP.lt(f.season.map(quant[.01])).astype(float).where(f.RRP.notna())
    f["nem_day"] = (f.time - pd.Timedelta(nanoseconds=1)).dt.normalize()
    return f, quant.reset_index().rename(columns={.01:"p01", .99:"p99"})


def panel(c):
    times = grid(c)
    price = pd.read_parquet(ROOT / "data/valuation_v2/panel/prices.parquet")
    price = price[(price.time > pd.Timestamp(c["window_start"])) & (price.time <= pd.Timestamp(c["window_end"]))]
    if price.duplicated(["time", "REGIONID"]).any():
        raise ValueError("Duplicate pricing intervals")
    cols = ["SETTLEMENTDATE", "REGIONID", "INTERVENTION", "RUNNO", "TOTALDEMAND", "AVAILABLEGENERATION",
            "SS_WIND_AVAILABILITY", "SS_SOLAR_AVAILABILITY", "SS_WIND_CLEAREDMW", "SS_SOLAR_CLEAREDMW", "LASTCHANGED"]
    pieces = []
    for p in sorted((ROOT / "data/tables/DISPATCHREGIONSUM").glob("*.parquet")):
        if not any(month.strftime("%Y%m") in p.name for month in pd.date_range(c["window_start"], c["window_end"], freq="MS")[:-1]):
            continue
        f = pd.read_parquet(p, columns=cols)
        f["time"] = pd.to_datetime(f.SETTLEMENTDATE)
        for col in cols[2:]:
            if col != "LASTCHANGED":
                f[col] = pd.to_numeric(f[col], errors="coerce")
        pieces.append(f)
    regional = pd.concat(pieces, ignore_index=True)
    regional = regional.sort_values(["time","REGIONID","INTERVENTION","RUNNO","LASTCHANGED"]).drop_duplicates(["time","REGIONID"],keep="last")
    weather = pd.read_parquet(ROOT / "data/processed/weather_30min.parquet")
    if "time" in weather.columns:weather=weather.set_index("time")
    if not isinstance(weather.index,pd.DatetimeIndex):raise ValueError("Weather has no timestamp index")
    events = load(c,"equipment_events"); register = load(c,"equipment_register").set_index("asset")
    daily, thresholds, summary = [], [], []
    for region in REGIONS:
        f = price[price.REGIONID.eq(region)].set_index("time").reindex(times).rename_axis("time").reset_index()
        f["REGIONID"] = region
        f, q = price_features(f,c["selection_end"]); q["region"] = region; thresholds.append(q)
        drivers = regional[regional.REGIONID.eq(region)].set_index("time").reindex(times)
        for source,target in [("TOTALDEMAND","demand"),("AVAILABLEGENERATION","available_generation"),
                              ("SS_WIND_AVAILABILITY","wind_available"),("SS_SOLAR_AVAILABILITY","solar_available"),
                              ("SS_WIND_CLEAREDMW","wind"),("SS_SOLAR_CLEAREDMW","solar"),("INTERVENTION","physical_intervention")]:
            f[target] = drivers[source].to_numpy()
        city = {"NSW1":"NSW_Sydney","QLD1":"QLD_Brisbane","VIC1":"VIC_Melbourne","SA1":"SA_Adelaide","TAS1":"TAS_Hobart"}[region]
        f["temperature"] = weather[city+"__temperature_2m"].reindex(times.ceil("30min")).to_numpy()
        # Two independent XOR signatures make collision extremely unlikely; identical equipment configurations match exactly.
        sig1, sig2 = np.zeros(len(times),dtype="uint64"), np.zeros(len(times),dtype="uint64")
        count = np.zeros(len(times),dtype="int16")
        relevant = register.index[(register.region.eq(region)) & (register.voltage_kv.ge(c["minimum_voltage_kv"]))]
        for asset in relevant:
            mask = interval_mask(times,events[events.asset.eq(asset)])
            h = hashlib.sha256(asset.encode()).digest()
            sig1[mask] ^= np.uint64(int.from_bytes(h[:8],"little")); sig2[mask] ^= np.uint64(int.from_bytes(h[8:16],"little"))
            count[mask] += 1
        f["co_sig1"], f["co_sig2"], f["outage_count"] = sig1,sig2,count
        save(c,"panel_"+region,f)
        d = f.groupby("nem_day").agg(n=("RRP","count"),mean_price=("RRP","mean"),price_sd=("RRP","std"),
              price_range=("RRP",lambda s:s.quantile(.95)-s.quantile(.05)),mean_change=("price_change","mean"),
              spike300=("spike300","mean"),spike1000=("spike1000","mean"),negative=("negative","mean"),negative100=("negative100","mean"))
        d["complete"] = d.n.eq(288); d["region"]=region
        d.loc[~d.complete,["price_sd","price_range"]] = np.nan
        daily.append(d.reset_index())
        summary.append({"region":region,"expected":len(times),"prices":int(f.RRP.notna().sum()),"drivers":int(f.demand.notna().sum()),"complete_days":int(d.complete.sum())})
    save(c,"daily_prices",pd.concat(daily));save(c,"price_thresholds",pd.concat(thresholds))
    ic = pd.read_parquet(ROOT / "data/valuation_v2/panel/interconnectors.parquet")
    ic = ic[(ic.time > pd.Timestamp(c["window_start"])) & (ic.time <= pd.Timestamp(c["window_end"]))]
    for key in STUDIES:
        f = ic[ic.INTERCONNECTORID.eq(key)].sort_values(["time","INTERVENTION","LASTCHANGED"]).drop_duplicates("time",keep="last")
        f["reverse_capacity"] = -pd.to_numeric(f.IMPORTLIMIT,errors="coerce")
        f["forward_capacity"] = pd.to_numeric(f.EXPORTLIMIT,errors="coerce")
        f["flow"] = pd.to_numeric(f.MWFLOW,errors="coerce")
        f["forward_headroom"] = f.forward_capacity-f.flow
        f["reverse_headroom"] = f.reverse_capacity+f.flow
        save(c,"ic_"+key,f)
    json_write(c["_data"] / "coverage.json",summary)
    return {"regions":summary,"interconnectors":len(STUDIES),"native_interval_minutes":5}


IMPORTANT = r"Dumaresq|Sapphire|Armidale.*(330|8C)|Dederang|S_Morang|S Morang|South.Morang|Heywood|South_East|Tumut|Murray.*330|Yass.*330|Marulan.*330|Bannaby|Halys|Calvale|Braemar|Palmerston|GeorgeTown"


def select(c):
    register,events = load(c,"asset_register"),load(c,"events")
    candidates = register[register.identity_status.eq("resolved") & register.region.isin(REGIONS) &
                          register.voltage_kv.ge(c["minimum_voltage_kv"]) & register.events.gt(0)].copy()
    # First-year outcomes only. This is an unadjusted discovery score, not an estimated outage effect.
    scores = {}
    for region in REGIONS:
        f=load(c,"panel_"+region); train=f.time.lt(pd.Timestamp(c["selection_end"]))
        ref=f.loc[train,"price_change"].mean()
        for r in candidates[candidates.region.eq(region)].itertuples():
            ev=events[events.asset.eq(r.asset) & events.end.le(pd.Timestamp(c["selection_end"]))]
            mask=interval_mask(f.time,ev)&train.to_numpy()
            value=f.loc[mask,"price_change"].mean()
            scores[r.asset]=abs(value-ref) if mask.any() else np.nan
    candidates["screen_score"] = candidates.asset.map(scores)
    candidates["importance_candidate"] = candidates.description.str.contains(IMPORTANT,case=False,regex=True,na=False)
    candidates["importance_basis"] = "Corridor endpoint screen; verify against exact constraint descriptions and planning sources"
    candidates["selection_route"] = ""
    aliases=json.loads((c["_data"]/"aliases.json").read_text())
    chosen=[]
    def take(frame,n,route):
        for asset in frame.asset:
            if asset in chosen: continue
            chosen.append(asset);candidates.loc[candidates.asset.eq(asset),"selection_route"]=route
            n-=1
            if n<=0: break
    mandatory=[aliases.get(a,a) for a in c["mandatory_assets"]]
    take(candidates[candidates.asset.isin(mandatory)].assign(order=lambda f:f.asset.map({a:i for i,a in enumerate(mandatory)})).sort_values("order"),2,"mandatory")
    take(candidates[candidates.importance_candidate].sort_values(["selection_events","voltage_kv","asset"],ascending=[False,False,True]),24,"importance")
    take(candidates[candidates.selection_events.ge(3)].sort_values(["screen_score","selection_events","asset"],ascending=[False,False,True]),12,"observed_association")
    for region in ["TAS1","SA1","QLD1","VIC1","NSW1"]:
        if len(chosen)>=c["max_assets"]: break
        take(candidates[candidates.region.eq(region)].sort_values(["selection_events","voltage_kv","asset"],ascending=[False,False,True]),2,"regional_coverage")
    if len(chosen)<c["max_assets"]:
        take(candidates.sort_values(["selection_events","voltage_kv","asset"],ascending=[False,False,True]),c["max_assets"]-len(chosen),"evidence_coverage")
    cohort=candidates.set_index("asset").loc[chosen[:c["max_assets"]]].reset_index()
    deep=list(mandatory)
    for route in ["importance","observed_association"]:
        deep+=list(cohort[cohort.selection_route.eq(route)].sort_values(["events","asset"],ascending=[False,True]).asset.head(4))
    cohort["deep_dive"]=cohort.asset.isin(deep[:c["deep_dives"]])
    save(c,"selection_screen",candidates);save(c,"cohort",cohort)
    json_write(c["_data"]/"selection_freeze.json",{"selection_cutoff":c["selection_end"],"cohort":chosen[:c["max_assets"]],
                "rule":"year-1 discovery; importance screen not yet a verified engineering ranking","cohort_hash":sha(c["_data"]/"cohort.parquet")})
    return {"profiles":len(cohort),"deep_dives":int(cohort.deep_dive.sum()),"regions":cohort.groupby("region").size().to_dict()}
