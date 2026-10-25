"""Audited long panel, effective-dated engineering groups and outage states."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nemic_regimes.core import CONNECTORS, NUMERIC_FEATURES, structural_era
from nemic.weather import SITES, VARS
from nemic.common import session
from .common import DATA, ROOT, config, digest, now, stage, write_json

INITIAL_FIT_END = pd.Timestamp("2025-09-01")


def numeric(f, names):
    for col in names:
        if col in f:
            f[col] = pd.to_numeric(f[col], errors="coerce")
    return f


def physical(f, key):
    f = f.copy()
    f["time"] = pd.to_datetime(f.SETTLEMENTDATE, errors="coerce")
    numeric(f, ["INTERVENTION", "RUNNO"])
    f["LASTCHANGED"] = pd.to_datetime(f.get("LASTCHANGED"), errors="coerce")
    return f.sort_values(["time", key, "INTERVENTION", "RUNNO", "LASTCHANGED"]).drop_duplicates(["time", key], keep="last")


def extension(table):
    paths = sorted((DATA / "extension" / table).glob("*.parquet"))
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True) if paths else pd.DataFrame()


def extend_weather():
    """Retain reanalysis as conditional actuals; no future-weather availability claim."""
    frames, records, gaps = [], [], []
    for name, (lat, lon, region, role) in SITES.items():
        p = DATA / "weather" / (name + ".json")
        try:
            if not p.exists():
                params = dict(latitude=lat, longitude=lon, start_date="2026-09-01", end_date="2026-10-24",
                              hourly=",".join(VARS), timezone="UTC", wind_speed_unit="ms")
                r = session().get("https://archive-api.open-meteo.com/v1/archive", params=params, timeout=(10, 40))
                r.raise_for_status()
                obj = r.json()
                if "hourly" not in obj:
                    raise ValueError("Weather hourly payload missing")
                write_json(p, obj)
            obj = json.loads(p.read_text())
            f = pd.DataFrame(obj["hourly"])
            f["time"] = pd.to_datetime(f.time, utc=True).dt.tz_convert("Australia/Brisbane").dt.tz_localize(None)
            f = f.set_index("time")
            f.columns = [name + "__" + x for x in f.columns]
            frames.append(f)
            records.append({"site": name, "sha256": digest(p), "class": "realised_reanalysis", "source": "https://archive-api.open-meteo.com/v1/archive"})
        except Exception as exc:
            gaps.append({"site": name, "reason": str(exc)})
        print("Weather", name, "available" if frames and name in frames[-1].columns[0] else "gap", flush=True)
    out = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame(index=pd.DatetimeIndex([], name="time"))
    if not out.empty:
        hh = out.resample("30min").interpolate("time", limit=1)
        for col in out:
            if col.endswith("shortwave_radiation"):
                hh[col] = out[col].reindex(hh.index).bfill(limit=1)
        out = hh
    write_json(DATA / "weather_manifest.json", {"records": records, "gaps": gaps, "retrieved": now()})
    return out


def new_targets():
    ic = extension("DISPATCHINTERCONNECTORRES")
    if ic.empty:
        return pd.DataFrame(), pd.DataFrame()
    ic = physical(ic, "INTERCONNECTORID")
    end = pd.Timestamp(config()["requested_data_end"]).tz_localize(None)
    ic = ic[(ic.time > pd.Timestamp("2026-09-01")) & (ic.time <= end)]
    numeric(ic, ["MWFLOW", "EXPORTLIMIT", "IMPORTLIMIT"])
    ic["time30"] = ic.time.dt.ceil("30min")
    ic["import_capacity"] = -ic.IMPORTLIMIT
    known = {v[0]: k for k,v in CONNECTORS.items()}
    extra = ic[~ic.INTERCONNECTORID.isin(known)]
    extra.to_parquet(DATA / "pec_and_unmapped_context_5min.parquet", index=False)
    f = ic[ic.INTERCONNECTORID.isin(known)].groupby(["INTERCONNECTORID", "time30"]).agg(
        export=("EXPORTLIMIT", "mean"), import_capacity=("import_capacity", "mean"),
        export_tight=("EXPORTLIMIT", "min"), import_tight=("import_capacity", "min"),
        flow=("MWFLOW", "mean"), n5=("time", "nunique")).reset_index()
    f = f.rename(columns={"INTERCONNECTORID": "ic", "time30": "time", "import_capacity": "import"})
    f.loc[f.n5 != 6, ["export", "import", "export_tight", "import_tight", "flow"]] = np.nan
    f["name"] = f.ic.map(known)
    reg = physical(extension("DISPATCHREGIONSUM"), "REGIONID")
    numeric(reg, ["TOTALDEMAND", "SS_WIND_CLEAREDMW", "SS_SOLAR_CLEAREDMW", "AVAILABLEGENERATION"])
    reg["time30"] = reg.time.dt.ceil("30min")
    cols = {"TOTALDEMAND": "demand", "SS_WIND_CLEAREDMW": "wind", "SS_SOLAR_CLEAREDMW": "solar", "AVAILABLEGENERATION": "available_generation"}
    wide = reg.groupby(["time30", "REGIONID"])[list(cols)].mean().rename(columns=cols)
    counts = reg.groupby(["time30", "REGIONID"]).time.nunique()
    wide.loc[counts != 6] = np.nan
    wide = wide.unstack("REGIONID")
    wide.columns = [r + "__" + c for c,r in wide.columns]
    wide.index.name = "time"
    return f, wide


def engineering_groups():
    """Freeze topology relationships on the first training end; no future leader selection."""
    folder = ROOT / "data/nos_binding_v1/standing"
    ic = pd.read_parquet(folder / "SPDINTERCONNECTORCONSTRAINT.parquet")
    cp = pd.read_parquet(folder / "SPDCONNECTIONPOINTCONSTRAINT.parquet")
    for f in (ic, cp):
        f["effective"] = pd.to_datetime(f.EFFECTIVEDATE, errors="coerce")
        f["FACTOR"] = pd.to_numeric(f.FACTOR, errors="coerce")
    ic = ic[(ic.effective <= INITIAL_FIT_END) & (ic.FACTOR.abs() >= .07) & ~ic.GENCONID.str.startswith("#")]
    cp = cp[(cp.effective <= INITIAL_FIT_END) & (cp.BIDTYPE == "ENERGY")]
    # Use latest eligible exact equation version on both sides.
    ic = ic.sort_values(["effective", "VERSIONNO"]).drop_duplicates(["INTERCONNECTORID", "GENCONID"], keep="last")
    terms = cp.merge(ic[["INTERCONNECTORID", "GENCONID", "EFFECTIVEDATE", "VERSIONNO", "FACTOR"]],
                     on=["GENCONID", "EFFECTIVEDATE", "VERSIONNO"], suffixes=("_du", "_ic"))
    du = pd.read_parquet(folder / "DUDETAILSUMMARY.parquet")
    du["start"] = pd.to_datetime(du.START_DATE, errors="coerce")
    du["end"] = pd.to_datetime(du.END_DATE.astype(str).str.replace(r"^2999", "2260", regex=True), errors="coerce")
    du = du[(du.start <= INITIAL_FIT_END) & (du.end > INITIAL_FIT_END)].sort_values("start").drop_duplicates("DUID", keep="last")
    terms = terms.merge(du[["DUID", "CONNECTIONPOINTID", "DISPATCHTYPE"]], on="CONNECTIONPOINTID")
    terms["sensitivity"] = -terms.FACTOR_du / terms.FACTOR_ic
    rows = []
    for name, (ident, _, _) in CONNECTORS.items():
        f = terms[terms.INTERCONNECTORID == ident]
        agg = f.groupby("DUID").sensitivity.median()
        for sign, values in (("positive", agg[agg > 0]), ("negative", agg[agg < 0])):
            values = values.reindex(values.abs().sort_values(ascending=False).index[:15])
            for duid, value in values.items():
                rows.append({"connector": name, "group": sign, "DUID": duid,
                             "weight": abs(value) / values.abs().sum(), "sensitivity": value,
                             "frozen_at": str(INITIAL_FIT_END)})
    groups = pd.DataFrame(rows)
    groups.to_csv(DATA / "electrical_groups.csv", index=False)
    paths = sorted((ROOT / "data/nos_binding_v1/dispatchload").glob("*.parquet"))
    output = []
    wanted = set(groups.DUID) if len(groups) else set()
    for p in paths:
        f = pd.read_parquet(p)
        f = f[f.DUID.isin(wanted)].copy()
        f["time"] = pd.to_datetime(f.time).dt.ceil("30min")
        f["TOTALCLEARED"] = pd.to_numeric(f.TOTALCLEARED, errors="coerce")
        unit = f.groupby(["time", "DUID"]).TOTALCLEARED.agg(["mean", "count"]).reset_index()
        unit.loc[unit["count"] != 6, "mean"] = np.nan
        joined = unit.merge(groups, on="DUID")
        joined["contribution"] = joined["mean"] * joined.weight
        sums = joined.groupby(["time", "connector", "group"]).contribution.sum(min_count=1).unstack("group")
        for group in ["positive", "negative"]:
            if group not in sums:
                sums[group] = np.nan
        sums = sums.rename(columns={"positive": "electrical_positive_mw", "negative": "electrical_negative_mw"}).reset_index()
        # Missing units cannot silently contribute zero.
        expected = groups.groupby(["connector", "group"]).DUID.nunique()
        valid = joined[joined["mean"].notna()].groupby(["time", "connector", "group"]).DUID.nunique()
        for group in ("positive", "negative"):
            for connector in sums.connector.unique():
                mask = sums.connector.eq(connector)
                counts = valid.reindex(pd.MultiIndex.from_arrays([sums.loc[mask, "time"], [connector]*mask.sum(), [group]*mask.sum()])).to_numpy()
                sums.loc[mask & ~sums.index.isin(sums.loc[mask].index[np.nan_to_num(counts) == expected.get((connector, group), -1)]), "electrical_" + group + "_mw"] = np.nan
        output.append(sums)
        print("Electrical dispatch", p.stem, flush=True)
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame(columns=["time", "connector"])


def attach_outages(panel):
    """States from observed invocation; booked episodes only supply linked asset context."""
    maps = []
    for study in ("qni", "vni", "directlink", "vsa", "murraylink", "basslink"):
        p = ROOT / f"data/constraint_{study}_2y/standing/GENCONSET.parquet"
        if p.exists():
            maps.append(pd.read_parquet(p))
    members = pd.concat(maps, ignore_index=True).drop_duplicates()
    members = members[pd.to_datetime(members.EFFECTIVEDATE, errors="coerce") <= INITIAL_FIT_END]
    ic = pd.read_parquet(ROOT / "data/nos_binding_v1/standing/SPDINTERCONNECTORCONSTRAINT.parquet")
    ic = ic[pd.to_datetime(ic.EFFECTIVEDATE, errors="coerce") <= INITIAL_FIT_END]
    rel = members[["GENCONSETID", "GENCONID"]].drop_duplicates().merge(ic[["GENCONID", "INTERCONNECTORID"]].drop_duplicates(), on="GENCONID")
    rel = rel[~rel.GENCONSETID.str.startswith("#")]
    known = {v[0]: k for k,v in CONNECTORS.items()}
    rel["connector"] = rel.INTERCONNECTORID.map(known)
    rel = rel.dropna(subset=["connector"])[["connector", "GENCONSETID"]].drop_duplicates()
    rel.to_csv(DATA / "family_mapping.csv", index=False)
    inv = pd.read_parquet(ROOT / "data/nos_regime_v1/invocation_spells.parquet")
    ext = extension("GENCONSETINVOKE")
    if len(ext):
        ext["start"] = pd.to_datetime(ext.STARTINTERVALDATETIME, errors="coerce")
        ext["end"] = pd.to_datetime(ext.ENDINTERVALDATETIME.astype(str).str.replace(r"^9999.*", "2260-01-01", regex=True), errors="coerce")
        # Monthly report open ends are capped at its actual archival coverage, not assumed ongoing forever.
        ext["end"] = ext.end.fillna(pd.Timestamp("2026-10-01")).clip(upper=pd.Timestamp("2026-10-01"))
        inv = pd.concat([inv, ext[["GENCONSETID", "start", "end"]]], ignore_index=True)
    inv = inv.drop_duplicates(["GENCONSETID", "start", "end"])
    episodes = pd.read_parquet(ROOT / "data/nos_regime_v1/episodes.parquet")
    sets = pd.read_parquet(ROOT / "data/nos_regime_v1/episode_sets.parquet")
    links = sets.merge(episodes[["OUTAGEID", "start", "end", "primary_asset", "withdrawn"]], on="OUTAGEID")
    newer = extension("NETWORK_OUTAGEDETAIL")
    newsets = extension("NETWORK_OUTAGECONSTRAINTSET")
    if len(newer) and len(newsets):
        newer["changed"] = pd.to_datetime(newer.LASTCHANGED, errors="coerce")
        newer = newer.sort_values("changed").drop_duplicates("OUTAGEID", keep="last")
        scheduled_start = pd.to_datetime(newer.STARTTIME, errors="coerce")
        scheduled_end = pd.to_datetime(newer.ENDTIME, errors="coerce")
        newer["start"] = pd.to_datetime(newer.ACTUAL_STARTTIME, errors="coerce").fillna(scheduled_start)
        newer["end"] = pd.to_datetime(newer.ACTUAL_ENDTIME, errors="coerce").fillna(scheduled_end)
        newer["withdrawn"] = newer.OUTAGESTATUSCODE.isin(["WDRAWN", "CANCELLED"])
        newer["primary_asset"] = newer.SUBSTATIONID + "/" + newer.EQUIPMENTTYPE + "/" + newer.EQUIPMENTID
        newer.loc[newer.EQUIPMENTID.eq("N/A"), "primary_asset"] = "EL" + newer.loc[newer.EQUIPMENTID.eq("N/A"), "ELEMENTID"]
        update = newsets[["OUTAGEID", "GENCONSETID"]].drop_duplicates().merge(newer[["OUTAGEID", "start", "end", "primary_asset", "withdrawn"]], on="OUTAGEID")
        links = pd.concat([links[~links.OUTAGEID.isin(update.OUTAGEID)], update], ignore_index=True)
    links = links[~links.withdrawn]
    panel["active_sets"], panel["partial_sets"], panel["active_assets"], panel["episode_ids"] = "", "", "", ""
    panel["outage_state"] = "unknown"
    for name, idx in panel.groupby("connector").groups.items():
        sub = panel.loc[idx]
        times = np.sort(sub.time.unique())
        t5 = (times[:, None] - np.arange(5, -1, -1) * np.timedelta64(5, "m")).reshape(-1)
        active = [[] for _ in times]; partial = [[] for _ in times]; assets = [[] for _ in times]; ids = [[] for _ in times]
        families = set(rel.loc[rel.connector == name, "GENCONSETID"])
        for family, spells in inv[inv.GENCONSETID.isin(families)].groupby("GENCONSETID"):
            covered = np.zeros(len(t5), bool)
            for row in spells.itertuples():
                covered |= (t5 >= np.datetime64(row.start)) & (t5 <= np.datetime64(row.end))
            count = covered.reshape(-1, 6).sum(axis=1)
            training_dates = times <= np.datetime64(INITIAL_FIT_END)
            if training_dates.any() and (count[training_dates] == 6).mean() > .95:
                # Always-invoked families describe configuration, not an outage on/off condition.
                continue
            for j in np.flatnonzero(count == 6): active[j].append(family)
            for j in np.flatnonzero((count > 0) & (count < 6)): partial[j].append(family)
            for row in links[links.GENCONSETID == family].itertuples():
                hit = (times >= np.datetime64(row.start)) & (times <= np.datetime64(row.end)) & (count == 6)
                for j in np.flatnonzero(hit):
                    ids[j].append(str(row.OUTAGEID))
                    if pd.notna(row.primary_asset): assets[j].append(str(row.primary_asset))
        lookup = pd.DataFrame({"time": times,
                               "active_sets": ["|".join(sorted(set(x))) for x in active],
                               "partial_sets": ["|".join(sorted(set(x))) for x in partial],
                               "active_assets": ["|".join(sorted(set(x))) for x in assets],
                               "episode_ids": ["|".join(sorted(set(x))) for x in ids]})
        known_dates = lookup.time <= (pd.Timestamp("2026-10-01") if len(ext) else pd.Timestamp("2026-09-01"))
        lookup["outage_state"] = np.where(~known_dates, "unknown", np.where(lookup.active_sets.ne(""), "invoked", np.where(lookup.partial_sets.ne(""), "partial", "clear")))
        for col in ["active_sets", "partial_sets", "active_assets", "episode_ids", "outage_state"]:
            panel.loc[idx, col] = sub.time.map(lookup.set_index("time")[col]).to_numpy()
        print("Outage mapping", name, len(families), "families", flush=True)
    return panel


def prepare():
    with stage("prepare", [DATA / "inventory.json", DATA / "source_manifest.json"]) as artifacts:
        base = pd.read_parquet(ROOT / "data/nos_regime_v1/tables_panel_cache.parquet")
        wanted = ["time", "name", "direction", "ic", "capacity", "tight_capacity", "flow", "n5", "complete", "daytype"] + [x for x in NUMERIC_FEATURES if x in base]
        panel = base[list(dict.fromkeys(wanted))].copy().rename(columns={"name": "connector"})
        panel["daytype"] = np.where(panel.time.dt.dayofweek >= 5, "weekend", "weekday")
        panel = panel[panel.complete & (panel.n5 == 6)]
        targets, regional = new_targets()
        weather = extend_weather() if len(targets) else pd.DataFrame()
        drivers = pd.read_parquet(ROOT / "data/processed/drivers.parquet")
        drivers = pd.concat([drivers, regional.join(weather, how="outer")]).sort_index()
        drivers = drivers[~drivers.index.duplicated(keep="last")]
        if len(targets):
            extra = []
            for direction, col in [("forward", "export"), ("reverse", "import")]:
                f = targets[["time", "name", "ic", "n5", "flow", col, col + "_tight"]].copy()
                f = f.rename(columns={"name": "connector", col: "capacity", col + "_tight": "tight_capacity"})
                f["direction"], f["complete"] = direction, f.n5.eq(6)
                f["daytype"] = np.where(f.time.dt.dayofweek >= 5, "weekend", "weekday")
                extra.append(f[f.complete])
            panel = pd.concat([panel, *extra], ignore_index=True)
        panel = panel.dropna(subset=["capacity", "tight_capacity"]).drop_duplicates(["connector", "direction", "time"], keep="last")
        for name, (_, source, sink) in CONNECTORS.items():
            for direction in ("forward", "reverse"):
                a, b = (source, sink) if direction == "forward" else (sink, source)
                mask = panel.connector.eq(name) & panel.direction.eq(direction)
                t = panel.loc[mask, "time"]
                for side, region in (("source", a), ("sink", b)):
                    for variable in ("demand", "wind", "solar", "available_generation"):
                        col = region + "__" + variable
                        if col in drivers:
                            panel.loc[mask, side + "_" + variable] = t.map(drivers[col]).to_numpy()
                    panel.loc[mask, side + "_vre"] = panel.loc[mask, side + "_wind"] + panel.loc[mask, side + "_solar"]
                    panel.loc[mask, side + "_residual"] = panel.loc[mask, side + "_demand"] - panel.loc[mask, side + "_vre"]
                    sites = [s for s,v in SITES.items() if v[2] == region]
                    cols = [s + "__temperature_2m" for s in sites if s + "__temperature_2m" in drivers]
                    panel.loc[mask, side + "_temperature"] = t.map(drivers[cols].mean(axis=1)).to_numpy()
                sites = [s for s,v in SITES.items() if v[2] in {a,b}]
                for var, dest in (("temperature_2m", "temperature_max"), ("relative_humidity_2m", "humidity_mean"),
                                  ("wind_speed_100m", "corridor_wind_ms"), ("shortwave_radiation", "corridor_radiation_wm2"), ("cloud_cover", "corridor_cloud_pct")):
                    use = [s + "__" + var for s in sites if s + "__" + var in drivers and (var in {"temperature_2m", "relative_humidity_2m"} or SITES[s][3] == "corridor")]
                    if use:
                        agg = drivers[use].max(axis=1) if dest == "temperature_max" else drivers[use].mean(axis=1)
                        panel.loc[mask, dest] = t.map(agg).to_numpy()
        panel["vre_difference"] = panel.source_vre - panel.sink_vre
        panel["residual_difference"] = panel.sink_residual - panel.source_residual
        panel = panel.sort_values(["connector", "direction", "time"]).reset_index(drop=True)
        for col in ("source_vre", "sink_vre", "residual_difference"):
            prior = panel[["connector", "direction", "time", col]].copy()
            prior["time"] += pd.Timedelta(hours=1)
            prior = prior.rename(columns={col: "prior"})
            joined = panel[["connector", "direction", "time", col]].merge(prior, on=["connector", "direction", "time"], how="left", sort=False)
            panel[col + "_ramp_1h"] = joined[col] - joined.prior
        panel["quarter"] = panel.time.dt.quarter.astype("int8")
        panel["half_hour"] = (panel.time.dt.hour * 2 + panel.time.dt.minute // 30).astype("int8")
        panel["era"] = [structural_era(n, t) for n,t in zip(panel.connector, panel.time)]
        panel = attach_outages(panel)
        electrical = engineering_groups()
        panel = panel.merge(electrical, on=["connector", "time"], how="left", suffixes=("_old", ""))
        # Reverse direction reverses the mechanical meaning of signed groups.
        reverse = panel.direction.eq("reverse")
        if "electrical_positive_mw" in panel and "electrical_negative_mw" in panel:
            panel.loc[reverse, ["electrical_positive_mw", "electrical_negative_mw"]] = panel.loc[reverse, ["electrical_negative_mw", "electrical_positive_mw"]].to_numpy()
        for col in NUMERIC_FEATURES:
            if col not in panel:
                panel[col] = np.nan
            panel[col] = pd.to_numeric(panel[col], errors="coerce").astype("float32")
        keep = ["time", "connector", "direction", "ic", "quarter", "half_hour", "era", "daytype", "capacity", "tight_capacity", "outage_state", "active_sets", "partial_sets", "active_assets", "episode_ids"] + NUMERIC_FEATURES
        panel = panel[keep]
        out = DATA / "panel.parquet"
        panel.to_parquet(out, index=False, compression="zstd")
        coverage = panel.groupby(["connector", "direction", "era"]).agg(start=("time", "min"), end=("time", "max"), rows=("time", "size"), days=("time", lambda s: s.dt.normalize().nunique()))
        coverage.to_csv(DATA / "coverage.csv")
        feature_coverage = panel.groupby(["connector", "era"])[NUMERIC_FEATURES].agg(lambda s: float(s.notna().mean()))
        feature_coverage.to_csv(DATA / "feature_coverage.csv")
        write_json(DATA / "data_audit.json", {"rows": len(panel), "end": str(panel.time.max()),
            "requested_end": config()["requested_data_end"], "unknown_outage_rows": int(panel.outage_state.eq("unknown").sum()),
            "negative_capacities": int(panel.capacity.lt(0).sum()), "incomplete_targets_excluded": True,
            "history_claim": "Conditional realised-state research; source archives retrieved today are not historical receipt evidence",
            "engineering_group_freeze": str(INITIAL_FIT_END), "panel_sha256": digest(out)})
        artifacts.extend([out, DATA / "coverage.csv", DATA / "feature_coverage.csv", DATA / "data_audit.json", DATA / "family_mapping.csv", DATA / "electrical_groups.csv", DATA / "weather_manifest.json"])
        print("Prepared", len(panel), "directional half-hours through", panel.time.max(), flush=True)
