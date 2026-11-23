"""Describe observed constraint configurations and contiguous limitation episodes."""

import numpy as np
import pandas as pd

from .constraints import values
from .observations import DIRECTIONS

PROJECT_PAGE = "https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/project-energyconnect-market-integration-project"
DISPATCH_URL = "https://nemweb.com.au/Reports/Archive/DispatchIS_Reports/"
NOTICE_BASE = "https://nemweb.com.au/Reports/CURRENT/Market_Notice/"
NOTICES = {"145435": NOTICE_BASE + "NEMITWEB1_MKTNOTICE_20261001.R145435",
           "146032": NOTICE_BASE + "NEMITWEB1_MKTNOTICE_20261104.R146032",
           "146187": NOTICE_BASE + "NEMITWEB1_MKTNOTICE_20261109.R146187"}


def configurations(five, equations, active, outages):
    frame = five.copy()
    caps = equations.loc[equations.GENCONID.str.fullmatch(r"(?:NS|SN)_(?:ZERO|(?:150|350)(?:_DYN)?_TEST)", na=False),
                         ["time", "GENCONID"]]
    frame["commissioning_equations"] = frame.time.map(caps.groupby("time").GENCONID.agg(values)).fillna("")
    names = frame.commissioning_equations
    has_zero = names.str.contains(r"\bNS_ZERO\b") & names.str.contains(r"\bSN_ZERO\b")
    high = names.str.contains("350")
    low = names.str.contains("150")
    frame["commissioning_state"] = np.select(
        [has_zero, high & low, high, low],
        ["Zero-transfer configuration", "150/350 MW cap transition", "350 MW testing", "150 MW commissioning"],
        default="Commissioning cap unverified",
    )
    frame["nominal_cap_mw"] = np.select([has_zero, high & ~low, low & ~high], [0, 350, 150], default=np.nan)
    equipment = outages.groupby("time").equipment.agg(values)
    frame["outage_equipment"] = frame.time.map(equipment).fillna("")
    frame["outage_ids"] = frame.time.map(outages.groupby("time").outage_id.agg(values)).fillna("")
    frame["outage_sets"] = frame.time.map(outages.groupby("time").outage_set.agg(values)).fillna("")
    sets = active.groupby("time").GENCONSETID.agg(values)
    frame["invoked_sets"] = frame.time.map(sets).fillna("")
    observed_security = equations.loc[equations.GENCONID.str.fullmatch(r"NS_200(?:_DYN)?", na=False), "time"]
    security = frame.time.isin(observed_security) & frame.time.ge(pd.Timestamp("2026-11-09 09:05"))
    frame["notice_ids"] = np.where(security, "146187", "")
    frame["notice_supported_set"] = np.where(security, "I-NS_200", "")
    frame["configuration"] = frame.commissioning_state
    frame.loc[security, "configuration"] += " + I-NS_200 security control"
    known = frame.outage_equipment.ne("")
    frame.loc[known, "configuration"] += " + outage [" + frame.loc[known, "outage_equipment"] + "]"
    return frame


def transition_table(five):
    changes = [
        (pd.Timestamp("2026-08-13"), "Registration release", "AEMO's August market release registered PEC ahead of its October effective date.", PROJECT_PAGE),
        (pd.Timestamp("2026-10-01 00:05"), "Separate dispatch representation", "MN145435 confirms separate registration from midnight and reports line 6F out of service at registration.", NOTICES["145435"]),
        (pd.Timestamp("2026-11-01 00:05"), "New settlements rule", "First dispatch interval after the settlement rule took effect.", PROJECT_PAGE),
        (pd.Timestamp("2026-11-04 12:30"), "Equipment commissioning notice", "MN146032 records commissioning of lines 6C, 6G and 6H and commencement of testing.", NOTICES["146032"]),
        (pd.Timestamp("2026-11-09 09:05"), "NSW security control", "MN146187 identifies invocation of I-NS_200 to maintain NSW system security.", NOTICES["146187"]),
    ]
    prior_state = None
    public_changes = {"150 MW commissioning", "350 MW testing", "Zero-transfer configuration", "150/350 MW cap transition"}
    for row in five.itertuples(index=False):
        state = row.commissioning_state
        if state in public_changes and state != prior_state:
            changes.append((row.time, f"Observed shift to {state.lower()}",
                            f"Original dispatch solution contains {row.commissioning_equations}.", DISPATCH_URL))
        if state in public_changes:
            prior_state = state
    result = pd.DataFrame(changes, columns=["time", "milestone", "evidence", "source_url"]).sort_values("time", kind="stable")
    return result.merge(five[["time", "nsw_sa_mw", "sa_nsw_mw", "nsw_sa_setter", "sa_nsw_setter", "configuration"]],
                        on="time", how="left")


def episodes(five, matches):
    outputs = []
    for direction in DIRECTIONS:
        block = five.copy()
        resolution = matches[matches.direction.eq(direction)].set_index("time")
        block["sets"] = block.time.map(resolution.sets)
        block["description"] = block.time.map(resolution.DESCRIPTION)
        block["setter"] = block[f"{direction}_setter"].fillna("Unresolved")
        block["limit"] = block[f"{direction}_mw"]
        standard = block.setter.str.fullmatch(r"(?:NS|SN)_(?:150|350)(?:_DYN)?_TEST")
        block["episode_type"] = np.select(
            [block.zero_limits, block.fixed_transfer, block.forced_flow, block.setter.str.startswith("NRM_"),
             block.notice_ids.ne(""), standard, block.outage_ids.ne("")],
            ["Zero transfer", "Fixed transfer", "Forced flow", "Negative residue management", "Security control",
             "Commissioning cap", "Outage overlap"], default="Equation restriction",
        )
        consecutive = block.time.diff().eq(pd.Timedelta(minutes=5))
        starting = ~consecutive
        for name in ["configuration", "setter", "episode_type"]:
            starting |= block[name].ne(block[name].shift())
        block["episode_id"] = [f"{direction}-{number:04d}" for number in starting.cumsum()]
        block["previous_setter"] = block.setter.shift().where(consecutive)
        block["previous_limit_mw"] = block.limit.shift().where(consecutive)
        block["shortfall"] = (block.nominal_cap_mw - block.limit).clip(lower=0)
        grouped = block.groupby("episode_id", sort=False)
        starts = block[starting].set_index("episode_id")
        result = grouped.agg(
            end=("time", "last"), intervals=("time", "size"), minimum_limit_mw=("limit", "min"),
            mean_limit_mw=("limit", "mean"), max_shortfall_mw=("shortfall", "max"),
            sets=("sets", values), outage_ids=("outage_ids", values), description=("description", values),
        )
        minimums = block.dropna(subset=["limit"]).sort_values(["limit", "time"]).drop_duplicates("episode_id").set_index("episode_id")
        result["minimum_time"] = minimums.time
        result = result.join(starts[["time", "configuration", "episode_type", "setter", "previous_setter",
                                     "previous_limit_mw", "limit", "notice_ids"]])
        result = result.rename(columns={"time": "start", "limit": "first_limit_mw"})
        result["direction"] = direction
        result["duration_minutes"] = 5 * result.intervals
        result["change_mw"] = result.first_limit_mw - result.previous_limit_mw
        result["sustained_rank"] = result.duration_minutes.rank(method="min", ascending=False).astype("Int64")
        result["severity_rank"] = result.minimum_limit_mw.rank(method="min", ascending=True).astype("Int64")
        outputs.append(result.reset_index())
        five[f"{direction}_episode_id"] = block.episode_id
    return pd.concat(outputs, ignore_index=True)


def setter_summary(matches):
    rows = matches.assign(reconstruction_absolute_error_mw=matches.reconstruction_error_mw.abs(),
                          setter=matches.reported_setter.fillna("Unresolved"))
    return (rows.groupby(["direction", "setter"], as_index=False)
            .agg(intervals=("time", "size"), first_seen=("time", "min"), last_seen=("time", "max"),
                 minimum_mw=("limit_mw", "min"), median_mw=("limit_mw", "median"),
                 binding_rows=("binding", "sum"), near_binding_rows=("near_binding", "sum"),
                 exact_definition_rows=("exact_definition", "sum"), exact_factor_rows=("exact_factor", "sum"),
                 reconstruction_mae_mw=("reconstruction_absolute_error_mw", "mean"),
                 sets=("sets", values), description=("DESCRIPTION", values))
            .sort_values(["direction", "intervals"], ascending=[True, False]))
