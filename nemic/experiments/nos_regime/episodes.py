"""S1: NEM-wide outage episodes, assets and linked constraint sets from MMSDM final-state tables."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .common import DATA, END, START, YEAR2, nem_time, write_parquet

RAW = DATA / "raw" / "mmsdm"
WITHDRAWN = {"WDRAWN", "WD REQ", "CANCELLED", "CANCEL"}
TYPE_ORDER = {"LINE": 0, "TRANS": 1, "BUS": 2, "REAC": 3, "REACT": 3, "CAP": 3, "SVC": 3, "CB": 4}


def infer_type(description: str) -> str:
    words = description.replace("-", " ").split()
    for w in reversed(words):
        if w in ("LINE", "FEEDER"):
            return "LINE"
        if w in ("CB", "BREAKER"):
            return "CB"
        if w in ("BUS", "BUSBAR"):
            return "BUS"
        if w in ("TRANSFORMER", "TX", "TRANS", "XFMR", "TFMR"):
            return "TRANS"
        if w in ("REACTOR", "REAC", "REACT", "CAPACITOR", "CAP", "SVC", "STATCOM"):
            return "REAC"
    return "OTHER"


def _latest(table: str) -> pd.DataFrame:
    paths = sorted(RAW.glob(f"{table}_*.parquet"))
    return pd.read_parquet(paths[-1])


def equipment_at(equipment: pd.DataFrame) -> pd.DataFrame:
    e = equipment.copy()
    e["VALIDFROM"] = nem_time(e.VALIDFROM)
    e["VALIDTO"] = nem_time(e.VALIDTO.str.replace("9999/12/31", "2262/04/01", regex=False))
    e["VOLTAGE"] = pd.to_numeric(e.VOLTAGE, errors="coerce")
    return e


def build_episodes() -> dict:
    detail = _latest("NETWORK_OUTAGEDETAIL")
    for col in ["STARTTIME", "ENDTIME", "ACTUAL_STARTTIME", "ACTUAL_ENDTIME", "SUBMITTEDDATE", "LASTCHANGED"]:
        detail[col] = nem_time(detail[col])
    detail["status"] = detail.OUTAGESTATUSCODE.str.upper().str.strip()
    # Collapse resubmission chains: RESUBMITOUTAGEID names the successor (as in nemic/experiments/nos.py);
    # a record whose successor exists is superseded by it.
    known = set(detail.OUTAGEID.astype(str))
    detail["superseded"] = detail.RESUBMITOUTAGEID.astype(str).str.strip().isin(known)
    has_actual = detail.ACTUAL_STARTTIME.notna() & detail.ACTUAL_ENDTIME.notna() & (detail.ACTUAL_ENDTIME > detail.ACTUAL_STARTTIME)
    detail["window_source"] = np.where(has_actual, "actual", "scheduled")
    detail["start"] = detail.ACTUAL_STARTTIME.where(has_actual, detail.STARTTIME)
    detail["end"] = detail.ACTUAL_ENDTIME.where(has_actual, detail.ENDTIME)
    valid = detail.start.notna() & detail.end.notna() & (detail.end > detail.start)
    inwin = valid & (detail.end > START) & (detail.start < END)
    rows = detail[inwin & ~detail.superseded].copy()
    rows["withdrawn"] = rows.status.isin(WITHDRAWN)

    equipment = equipment_at(_latest("NETWORK_EQUIPMENTDETAIL"))
    eq = equipment[["ELEMENTID", "VALIDFROM", "VALIDTO", "VOLTAGE", "DESCRIPTION"]].copy()
    rows = rows.reset_index(drop=True)
    rows["row"] = np.arange(len(rows))
    joined = rows[["row", "ELEMENTID", "start"]].merge(eq, on="ELEMENTID", how="left")
    joined = joined[joined.VALIDFROM.isna() | ((joined.VALIDFROM <= joined.start) & (joined.VALIDTO > joined.start))]
    joined = joined.sort_values("VALIDFROM").drop_duplicates("row", keep="last")
    rows = rows.merge(joined[["row", "VOLTAGE", "DESCRIPTION"]], on="row", how="left")
    # Fallback: latest description for the element regardless of validity
    fallback = eq.sort_values("VALIDFROM").drop_duplicates("ELEMENTID", keep="last").set_index("ELEMENTID")
    miss = rows.DESCRIPTION.isna()
    rows.loc[miss, "DESCRIPTION"] = rows.loc[miss, "ELEMENTID"].map(fallback.DESCRIPTION)
    rows.loc[miss, "VOLTAGE"] = rows.loc[miss, "ELEMENTID"].map(fallback.VOLTAGE)
    na = rows.SUBSTATIONID.isin(["N/A", ""]) | rows.EQUIPMENTTYPE.isin(["N/A", ""])
    described = rows.DESCRIPTION.fillna("").str.strip().ne("")
    # N/A NOS assets are still specific when EQUIPMENTDETAIL describes the element (e.g. "Dumaresq330-Sapphire 8J 330kV LINE")
    inferred = rows.DESCRIPTION.fillna("").str.upper().map(infer_type)
    rows["equipment_type_used"] = rows.EQUIPMENTTYPE.where(~na, inferred)
    rows["equipment_rank"] = rows.equipment_type_used.map(TYPE_ORDER).fillna(5)
    rows["asset"] = (rows.SUBSTATIONID + "/" + rows.EQUIPMENTTYPE + "/" + rows.EQUIPMENTID).where(~na, "EL" + rows.ELEMENTID.astype(str))
    rows["asset_key_source"] = np.where(~na, "nos_asset", np.where(described, "element_description", "none"))
    rows["asset_is_na"] = na & ~described
    assets = rows[["OUTAGEID", "asset", "SUBSTATIONID", "EQUIPMENTTYPE", "EQUIPMENTID", "ELEMENTID", "VOLTAGE",
                   "DESCRIPTION", "equipment_rank", "equipment_type_used", "asset_key_source", "asset_is_na", "ISSECONDARY", "REASON"]].drop_duplicates(["OUTAGEID", "ELEMENTID"])
    primary = (assets.assign(v=-assets.VOLTAGE.fillna(0), na=assets.asset_is_na.astype(int))
               .sort_values(["OUTAGEID", "na", "equipment_rank", "v"]).drop_duplicates("OUTAGEID"))
    episodes = (rows.groupby("OUTAGEID").agg(start=("start", "min"), end=("end", "max"), status=("status", "first"),
                                             withdrawn=("withdrawn", "all"), window_source=("window_source", "first"),
                                             scheduled_start=("STARTTIME", "min"), scheduled_end=("ENDTIME", "max"),
                                             actual_start=("ACTUAL_STARTTIME", "min"), actual_end=("ACTUAL_ENDTIME", "max"),
                                             submitted=("SUBMITTEDDATE", "min"), secondary=("ISSECONDARY", lambda s: (s == "1").all()),
                                             resubmit_of=("RESUBMITOUTAGEID", "first"), n_assets=("ELEMENTID", "nunique"))
                .reset_index())
    episodes = episodes.merge(primary[["OUTAGEID", "asset", "SUBSTATIONID", "EQUIPMENTTYPE", "EQUIPMENTID", "ELEMENTID",
                                       "VOLTAGE", "DESCRIPTION", "asset_is_na", "asset_key_source", "equipment_type_used"]].rename(columns=lambda c: c if c == "OUTAGEID" else "primary_" + c.lower()),
                              on="OUTAGEID", how="left")
    episodes["study_year"] = np.where(episodes.start >= YEAR2, 2, 1)
    episodes["source"] = "mmsdm_final"

    ocs = _latest("NETWORK_OUTAGECONSTRAINTSET")
    ocs["set_start"] = nem_time(ocs.STARTINTERVAL)
    ocs["set_end"] = nem_time(ocs.ENDINTERVAL)
    sets = ocs[ocs.OUTAGEID.isin(episodes.OUTAGEID)][["OUTAGEID", "GENCONSETID", "set_start", "set_end"]].drop_duplicates()
    episodes["n_sets"] = episodes.OUTAGEID.map(sets.groupby("OUTAGEID").GENCONSETID.nunique()).fillna(0).astype(int)

    write_parquet(DATA / "episodes.parquet", episodes)
    write_parquet(DATA / "episode_assets.parquet", assets)
    write_parquet(DATA / "episode_sets.parquet", sets)
    return {"episodes": len(episodes), "withdrawn": int(episodes.withdrawn.sum()),
            "with_sets": int((episodes.n_sets > 0).sum()), "assets": len(assets),
            "actual_window": int(episodes.window_source.eq("actual").sum()),
            "by_year": episodes.study_year.value_counts().to_dict(),
            "status": episodes.status.value_counts().head(10).to_dict()}
