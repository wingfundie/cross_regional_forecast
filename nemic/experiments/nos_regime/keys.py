"""S2: specific-outage key K1–K5 (asset, family, substation, area, nearby generators). No guessed locations."""
from __future__ import annotations

import json
import math
import re

import numpy as np
import pandas as pd

from nemic.common import IC

from .common import DATA, EXEC, ROOT, STUDY, write_parquet
from .episodes import _latest
from .state import set_members, standing

# Reference places for descriptive area labels (lat, lon, NEM region).
PLACES = {
    "Sydney": (-33.87, 151.21, "NSW1"), "Newcastle": (-32.93, 151.78, "NSW1"), "Wollongong": (-34.42, 150.89, "NSW1"),
    "Canberra": (-35.28, 149.13, "NSW1"), "Wagga Wagga": (-35.12, 147.37, "NSW1"), "Tamworth": (-31.09, 150.93, "NSW1"),
    "Armidale": (-30.51, 151.67, "NSW1"), "Dubbo": (-32.25, 148.60, "NSW1"), "Orange": (-33.28, 149.10, "NSW1"),
    "Broken Hill": (-31.95, 141.45, "NSW1"), "Coffs Harbour": (-30.30, 153.11, "NSW1"), "Griffith": (-34.29, 146.05, "NSW1"),
    "Lismore": (-28.81, 153.28, "NSW1"), "Albury": (-36.08, 146.92, "NSW1"), "Muswellbrook": (-32.27, 150.89, "NSW1"),
    "Yass": (-34.84, 148.91, "NSW1"), "Cooma": (-36.24, 149.12, "NSW1"), "Port Macquarie": (-31.43, 152.91, "NSW1"),
    "Melbourne": (-37.81, 144.96, "VIC1"), "Geelong": (-38.15, 144.36, "VIC1"), "Ballarat": (-37.56, 143.85, "VIC1"),
    "Bendigo": (-36.76, 144.28, "VIC1"), "Morwell": (-38.24, 146.40, "VIC1"), "Shepparton": (-36.38, 145.40, "VIC1"),
    "Horsham": (-36.71, 142.20, "VIC1"), "Mildura": (-34.19, 142.16, "VIC1"), "Portland": (-38.34, 141.60, "VIC1"),
    "Warrnambool": (-38.38, 142.49, "VIC1"), "Wodonga": (-36.12, 146.89, "VIC1"), "Kerang": (-35.73, 143.92, "VIC1"),
    "Adelaide": (-34.93, 138.60, "SA1"), "Port Augusta": (-32.49, 137.77, "SA1"), "Whyalla": (-33.03, 137.58, "SA1"),
    "Mount Gambier": (-37.83, 140.78, "SA1"), "Murray Bridge": (-35.12, 139.27, "SA1"), "Port Lincoln": (-34.73, 135.86, "SA1"),
    "Robertstown": (-34.07, 139.08, "SA1"),
    "Brisbane": (-27.47, 153.03, "QLD1"), "Toowoomba": (-27.56, 151.95, "QLD1"), "Gold Coast": (-28.02, 153.40, "QLD1"),
    "Nambour": (-26.63, 152.96, "QLD1"), "Gladstone": (-23.84, 151.26, "QLD1"), "Rockhampton": (-23.38, 150.51, "QLD1"),
    "Mackay": (-21.14, 149.19, "QLD1"), "Townsville": (-19.26, 146.82, "QLD1"), "Cairns": (-16.92, 145.77, "QLD1"),
    "Bundaberg": (-24.87, 152.35, "QLD1"), "Chinchilla": (-26.74, 150.63, "QLD1"), "Emerald": (-23.53, 148.16, "QLD1"),
    "Moranbah": (-22.00, 148.05, "QLD1"), "Roma": (-26.57, 148.79, "QLD1"),
    "Hobart": (-42.88, 147.33, "TAS1"), "Launceston": (-41.44, 147.14, "TAS1"), "Burnie": (-41.05, 145.91, "TAS1"),
    "Devonport": (-41.18, 146.35, "TAS1"), "Queenstown": (-42.08, 145.56, "TAS1"),
}
OCTANTS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
STOP = r"\b(substation|sub|terminal|station|switching|switchyard|zone|bulk|supply|point|ts|zs|ss|s/s|kv|power|the|transmission|and)\b"


def haversine(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def norm(name: str) -> str:
    s = str(name).lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\d+(\.\d+)?\s*kv", " ", s)
    s = re.sub(STOP, " ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return " ".join(s.split())


def nearest_place(lat, lon):
    best = min(PLACES.items(), key=lambda kv: haversine(lat, lon, kv[1][0], kv[1][1]))
    name, (plat, plon, region) = best
    d = haversine(lat, lon, plat, plon)
    bearing = (math.degrees(math.atan2((lon - plon) * math.cos(math.radians(plat)), lat - plat)) + 360) % 360
    octant = OCTANTS[int(((bearing + 22.5) % 360) // 45)]
    label = f"central {name}" if d < 15 else f"{octant} of {name} ({d:.0f} km)"
    area = f"{region}:{name}" if d < 15 else f"{region}:{octant} {name}"
    return label, area, region, d


def osm_points() -> pd.DataFrame:
    d = json.loads((DATA / "raw/osm/au_power.json").read_text(encoding="utf-8"))
    rows = []
    for e in d["elements"]:
        tags = e.get("tags", {})
        lat = e.get("lat", e.get("center", {}).get("lat"))
        lon = e.get("lon", e.get("center", {}).get("lon"))
        if lat is None or "name" not in tags:
            continue
        rows.append({"osm_id": f"{e['type']}/{e['id']}", "kind": tags.get("power"), "name": tags["name"], "lat": lat, "lon": lon,
                     "voltage": tags.get("voltage"), "operator": tags.get("operator"), "substation": tags.get("substation"),
                     "plant_source": tags.get("plant:source"), "norm": norm(tags["name"])})
    pts = pd.DataFrame(rows)
    pts["region_guess"] = [nearest_place(a, b)[2] for a, b in zip(pts.lat, pts.lon)]
    return pts


def substation_crosswalk() -> pd.DataFrame:
    sub = _latest("NETWORK_SUBSTATIONDETAIL")
    sub = sub.sort_values("VALIDFROM").drop_duplicates("SUBSTATIONID", keep="last")
    pts = osm_points()
    subs_osm = pts[pts.kind.eq("substation")]
    rank = {"transmission": 0, None: 1, "zone": 2, "distribution": 3}
    rows = []
    for r in sub.itertuples():
        key = norm(r.DESCRIPTION) if r.DESCRIPTION else ""
        method, match = "", None
        if key:
            cand = subs_osm[subs_osm.norm.eq(key)]
            if r.REGIONID:
                same = cand[cand.region_guess.eq(r.REGIONID)]
                cand = same if len(same) else cand.iloc[0:0]
            if len(cand):
                cand = cand.assign(r=cand.substation.map(rank).fillna(2)).sort_values("r")
                spread = max(haversine(cand.lat.iloc[0], cand.lon.iloc[0], a, b) for a, b in zip(cand.lat, cand.lon))
                if spread <= 10:
                    match, method = cand.iloc[0], "name_match"
        rows.append({"SUBSTATIONID": r.SUBSTATIONID, "substation_name": r.DESCRIPTION, "region": r.REGIONID,
                     "owner": r.OWNERID, "osm_id": None if match is None else match.osm_id,
                     "osm_name": None if match is None else match["name"],
                     "lat": None if match is None else match.lat, "lon": None if match is None else match.lon,
                     "method": method or "unmatched", "confidence": "medium" if method else ""})
    xw = pd.DataFrame(rows)
    (EXEC / "reference").mkdir(parents=True, exist_ok=True)
    xw.to_csv(EXEC / "reference/substation_crosswalk.csv", index=False)
    return xw


def electrical_neighbours() -> pd.DataFrame:
    """Per connector and family: DUIDs by max |sensitivity| = |b/a| across the family's equations (latest versions)."""
    members = set_members()
    cp = standing("SPDCONNECTIONPOINTCONSTRAINT")
    ic = standing("SPDINTERCONNECTORCONSTRAINT")
    for f in (cp, ic):
        f["EFFECTIVEDATE"] = pd.to_datetime(f.EFFECTIVEDATE, errors="coerce")
        f["VERSIONNO"] = pd.to_numeric(f.VERSIONNO, errors="coerce")
        f["FACTOR"] = pd.to_numeric(f.FACTOR, errors="coerce")
    latest = lambda f: f.merge(f.groupby("GENCONID")[["EFFECTIVEDATE"]].max().reset_index(), on=["GENCONID", "EFFECTIVEDATE"]) \
        .sort_values("VERSIONNO").drop_duplicates([c for c in f.columns if c in ("GENCONID", "CONNECTIONPOINTID", "INTERCONNECTORID", "BIDTYPE")], keep="last")
    cp, ic = latest(cp), latest(ic)
    du = standing("DUDETAILSUMMARY").sort_values("START_DATE").drop_duplicates(["CONNECTIONPOINTID", "DUID"], keep="last")
    rel = pd.read_parquet(DATA / "set_relevance.parquet")
    rel = rel[rel.relevant]
    rows = []
    for (icid, fam), _ in rel.groupby(["ic", "GENCONSETID"]):
        gens = members[members.GENCONSETID.eq(fam)].GENCONID
        a = ic[ic.GENCONID.isin(gens) & ic.INTERCONNECTORID.eq(icid)][["GENCONID", "FACTOR"]].rename(columns={"FACTOR": "a"})
        b = cp[cp.GENCONID.isin(a.GENCONID)][["GENCONID", "CONNECTIONPOINTID", "FACTOR"]].merge(a, on="GENCONID")
        b = b[b.a.abs() > 1e-9]
        b["sensitivity"] = -b.FACTOR / b.a
        b = b.merge(du[["CONNECTIONPOINTID", "DUID", "REGIONID", "DISPATCHTYPE"]], on="CONNECTIONPOINTID", how="left")
        b = b[b.DUID.notna() & b.sensitivity.abs().ge(0.05)]
        if b.empty:
            continue
        top = (b.assign(abs_s=b.sensitivity.abs()).sort_values("abs_s", ascending=False).drop_duplicates("DUID").head(10))
        for r in top.itertuples():
            rows.append({"ic": icid, "GENCONSETID": fam, "DUID": r.DUID, "duid_region": r.REGIONID, "dispatch_type": r.DISPATCHTYPE,
                         "sensitivity": r.sensitivity, "example_equation": r.GENCONID})
    out = pd.DataFrame(rows)
    write_parquet(DATA / "k5_electrical.parquet", out)
    return out


def build_keys() -> dict:
    xw = substation_crosswalk()
    episodes = pd.read_parquet(DATA / "episodes.parquet")
    labels = {}
    for r in xw[xw.lat.notna()].itertuples():
        label, area, region, d = nearest_place(r.lat, r.lon)
        labels[r.SUBSTATIONID] = (label, area)
    xw["area_label"] = xw.SUBSTATIONID.map(lambda s: labels.get(s, (None, None))[0])
    xw["area_key"] = xw.SUBSTATIONID.map(lambda s: labels.get(s, (None, None))[1])
    pts = osm_points()
    plants = pts[pts.kind.eq("plant")]
    near = {}
    for r in xw[xw.lat.notna()].itertuples():
        d = [(p.name, haversine(r.lat, r.lon, p.lat, p.lon)) for p in plants.itertuples()]
        near[r.SUBSTATIONID] = "; ".join(f"{n} ({km:.0f} km)" for n, km in sorted(d, key=lambda x: x[1]) if km <= 50)[:400]
    xw["plants_within_50km"] = xw.SUBSTATIONID.map(near)
    # Element-described assets (NOS substation N/A): parse the leading substation name from the description.
    by_norm = xw.assign(n=xw.substation_name.fillna("").map(norm)).query("n != ''").groupby("n").SUBSTATIONID.agg(list)
    def parse_sub(desc):
        m = re.match(r"^\s*([A-Za-z][A-Za-z .']*?)(?=\s*\d|\s*-|\s*$)", str(desc or ""))
        cand = by_norm.get(norm(m.group(1)), []) if m else []
        if len(cand) > 1:   # tie-break on the voltage named in the description, e.g. "Wagga 330kV"
            kv = re.findall(r"(\d+)\s*kv", str(desc).lower())
            if kv:
                names = xw.set_index("SUBSTATIONID").substation_name.fillna("").str.lower()
                cand = [c for c in cand if kv[0] + "kv" in names.get(c, "").replace(" ", "")]
        return cand[0] if len(cand) == 1 else None
    episodes = episodes.copy()
    el = episodes.primary_asset_key_source.eq("element_description")
    parsed = episodes.loc[el, "primary_description"].map(parse_sub)
    episodes["substation_method"] = np.where(el, np.where(parsed.reindex(episodes.index).notna(), "description_parse", "unresolved"), "nos_asset")
    episodes.loc[el, "primary_substationid"] = parsed
    keys = episodes[["OUTAGEID", "primary_asset", "primary_substationid", "primary_equipmenttype", "primary_equipmentid",
                     "primary_voltage", "primary_description", "primary_asset_is_na", "primary_asset_key_source",
                     "primary_equipment_type_used", "substation_method"]].merge(
        xw[["SUBSTATIONID", "substation_name", "region", "owner", "lat", "lon", "method", "confidence", "area_label", "area_key",
            "plants_within_50km"]], left_on="primary_substationid", right_on="SUBSTATIONID", how="left")
    keys.loc[keys.substation_method.eq("description_parse"), "confidence"] = "low"
    keys["location_source"] = np.where(keys.primary_asset_is_na, "set_only", np.where(keys.lat.notna(), "asset+coordinates",
                                       np.where(keys.substation_name.notna(), "asset_substation_only", "asset_only")))
    write_parquet(DATA / "outage_keys.parquet", keys)
    k5 = electrical_neighbours()
    subs_used = keys.primary_substationid[~keys.primary_asset_is_na]
    return {"substations": len(xw), "substations_with_coordinates": int(xw.lat.notna().sum()),
            "episodes": len(keys), "k3_resolved_share": float(keys.substation_name.notna()[~keys.primary_asset_is_na].mean()),
            "k4_resolved_share": float(keys.lat.notna()[~keys.primary_asset_is_na].mean()),
            "location_source": keys.location_source.value_counts().to_dict(), "k5_rows": len(k5),
            "k5_families": int(k5[["ic", "GENCONSETID"]].drop_duplicates().shape[0]) if len(k5) else 0,
            "distinct_primary_substations": int(subs_used.nunique())}
