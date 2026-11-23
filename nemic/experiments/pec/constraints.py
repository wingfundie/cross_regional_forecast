"""Resolve reported setters using dispatch-version keys and AEMO operating records."""

import numpy as np
import pandas as pd

from nemic.constraint_features import bound_from_solution
from nemic.constraint_ingest import _table_rows

from .observations import DIRECTIONS, prepare

VERSION = ["GENCONID", "EFFECTIVEDATE", "VERSIONNO"]
KEY = ["time", "RUNNO", "INTERVENTION"]
OPERATOR = {"<=": 1, "LE": 1, ">=": -1, "GE": -1, "=": 0, "EQ": 0}


def values(frame):
    return " | ".join(sorted(set(str(value) for value in frame.dropna() if str(value))))


def read_standing(sources, table):
    paths = [source.path for source in sources if source.product == table]
    return pd.concat([_table_rows(path, table) for path in paths], ignore_index=True).drop_duplicates()


def versioned(raw):
    frame = raw.copy()
    frame["EFFECTIVEDATE"] = pd.to_datetime(frame.EFFECTIVEDATE, errors="coerce")
    frame["VERSIONNO"] = pd.to_numeric(frame.VERSIONNO, errors="coerce")
    return frame.dropna(subset=["EFFECTIVEDATE", "VERSIONNO"])


def last_update(frame, key):
    return frame.sort_values("LASTCHANGED").drop_duplicates(key, keep="last")


def dispatch_equations(raw, five, definitions, factors):
    runs = prepare(raw).rename(columns={"CONSTRAINTID": "GENCONID", "GENCONID_EFFECTIVEDATE": "EFFECTIVEDATE",
                                        "GENCONID_VERSIONNO": "VERSIONNO"})
    runs["EFFECTIVEDATE"] = pd.to_datetime(runs.EFFECTIVEDATE, errors="coerce")
    runs["VERSIONNO"] = pd.to_numeric(runs.VERSIONNO, errors="coerce")
    runs = last_update(runs, [*KEY, "GENCONID"])
    runs = runs.merge(five[[*KEY, "dispatch_flow_mw"]], on=KEY, validate="many_to_one")
    keep = ["CONSTRAINTTYPE", "DESCRIPTION", "LIMITTYPE", "IMPACT", "SOURCE", "REASON"]
    definitions = last_update(versioned(definitions), VERSION)
    factors = last_update(versioned(factors[factors.INTERCONNECTORID.eq("NSW1-SA1")]), VERSION)
    runs = runs.merge(definitions[VERSION + keep], on=VERSION, how="left", indicator="definition_match")
    runs = runs.merge(factors[VERSION + ["FACTOR"]], on=VERSION, how="left", indicator="factor_match")
    for column in ["RHS", "LHS", "MARGINALVALUE", "VIOLATIONDEGREE", "FACTOR"]:
        runs[column] = pd.to_numeric(runs[column], errors="coerce")
    runs["operator"] = runs.CONSTRAINTTYPE.map(OPERATOR)
    runs["valid_version"] = runs.VERSIONNO.notna() & runs.EFFECTIVEDATE.le(runs.time)
    runs["binding"] = runs.MARGINALVALUE.abs().gt(1e-6) | runs.VIOLATIONDEGREE.abs().gt(1e-6)
    slack = (runs.RHS - runs.LHS).abs() / runs.FACTOR.abs().where(runs.FACTOR.abs().gt(1e-8))
    runs["slack_pec_mw"] = slack
    runs["near_binding"] = ~runs.binding & slack.le(5)
    eligible = runs.valid_version & runs.operator.notna() & runs.FACTOR.abs().gt(1e-8)
    runs["physical_bound_mw"] = np.nan
    runs.loc[eligible, "physical_bound_mw"] = bound_from_solution(
        runs.loc[eligible, "dispatch_flow_mw"], runs.loc[eligible, "RHS"],
        runs.loc[eligible, "LHS"], runs.loc[eligible, "FACTOR"])
    return runs


def invocation_times(invokes, prefix):
    label = prefix.upper()
    interval = pd.to_datetime(invokes[f"{label}INTERVALDATETIME"], errors="coerce")
    market_date = pd.to_datetime(invokes[f"{label}DATE"], errors="coerce").dt.normalize()
    period = pd.to_numeric(invokes[f"{label}PERIOD"], errors="coerce")
    fallback = market_date + pd.Timedelta(hours=4) + pd.to_timedelta(period.fillna(0) * 5, unit="min")
    return interval.fillna(fallback.where(period.between(1, 288)))


def invocation_membership(solution, memberships, tracked, invokes):
    set_key = ["GENCONSETID", "EFFECTIVEDATE", "VERSIONNO"]
    tracked = last_update(versioned(tracked), set_key)
    memberships = versioned(memberships)
    candidate_sets = memberships.loc[memberships.GENCONID.isin(solution.GENCONID), "GENCONSETID"].unique()
    invokes = last_update(invokes, ["INVOCATION_ID"])
    invokes = invokes[invokes.GENCONSETID.isin(candidate_sets) & invokes.STARTAUTHORISEDBY.ne("")].copy()
    invokes["start"] = invocation_times(invokes, "start")
    invokes["end"] = invocation_times(invokes, "end")
    invokes["set_intervention"] = pd.to_numeric(invokes.INTERVENTION, errors="coerce").fillna(0)
    # Join membership at dispatch, with set version governed by its tracking table.
    active = []
    solution_keys = solution[[*KEY, "GENCONID"]]
    for set_id, group in invokes.groupby("GENCONSETID"):
        declared = memberships[memberships.GENCONSETID.eq(set_id)]
        versions = tracked[tracked.GENCONSETID.eq(set_id)].sort_values(["EFFECTIVEDATE", "VERSIONNO"])
        versions = versions[versions.AUTHORISEDBY.ne("")].drop_duplicates("EFFECTIVEDATE", keep="last")
        if versions.empty:
            continue
        relevant = solution_keys[solution_keys.GENCONID.isin(declared.GENCONID)].sort_values("time")
        relevant = pd.merge_asof(relevant, versions[set_key + ["DESCRIPTION", "OUTAGE"]],
                                 left_on="time", right_on="EFFECTIVEDATE")
        relevant = relevant.merge(declared[set_key + ["GENCONID"]].drop_duplicates(), on=set_key + ["GENCONID"])
        for invoke in group.itertuples(index=False):
            rows = relevant.loc[relevant.time.ge(invoke.start) & (pd.isna(invoke.end) | relevant.time.le(invoke.end))
                                & relevant.INTERVENTION.ge(invoke.set_intervention)].copy()
            if not rows.empty:
                rows["INVOCATION_ID"] = invoke.INVOCATION_ID
                rows["set_system_normal"] = invoke.SYSTEMNORMAL
                rows["invocation_start"] = invoke.start
                rows["invocation_end"] = invoke.end
                active.append(rows)
    columns = [*KEY, "GENCONID", *set_key, "DESCRIPTION", "OUTAGE", "INVOCATION_ID", "set_system_normal",
               "invocation_start", "invocation_end"]
    return pd.concat(active, ignore_index=True) if active else pd.DataFrame(columns=columns)


def match_limits(five, equations, active):
    keys = [*KEY, "GENCONID"]
    active_sets = active.groupby(keys).agg(sets=("GENCONSETID", values), invocation_ids=("INVOCATION_ID", values)).reset_index()
    candidate_rows = equations.dropna(subset=["physical_bound_mw"])[[*keys, "operator", "FACTOR", "physical_bound_mw"]]
    indexed_columns = [*keys, "EFFECTIVEDATE", "VERSIONNO", "definition_match", "factor_match",
                       "DESCRIPTION", "LIMITTYPE", "REASON", "CONSTRAINTTYPE", "FACTOR", "RHS", "LHS",
                       "MARGINALVALUE", "VIOLATIONDEGREE", "binding", "near_binding", "slack_pec_mw",
                       "report_vintage", "source_archive", "valid_version"]
    indexed = equations.set_index(keys, drop=False)[indexed_columns]
    blocks = []
    for direction, (_, _, sign) in DIRECTIONS.items():
        reported = five[[*KEY, f"{direction}_mw", f"{direction}_setter"]].rename(
            columns={f"{direction}_mw": "limit_mw", f"{direction}_setter": "reported_setter"})
        candidates = candidate_rows[candidate_rows.operator.eq(0) | candidate_rows.FACTOR.mul(candidate_rows.operator).mul(sign).gt(0)].copy()
        candidates["reconstructed_mw"] = sign * candidates.physical_bound_mw
        leaders = (candidates.dropna(subset=["reconstructed_mw"]).sort_values(["reconstructed_mw", "GENCONID"])
                   .drop_duplicates(KEY)[[*KEY, "GENCONID", "reconstructed_mw"]]
                   .rename(columns={"GENCONID": "reconstructed_leader", "reconstructed_mw": "leader_limit_mw"}))
        matches = indexed.reindex(pd.MultiIndex.from_frame(reported[[*KEY, "reported_setter"]])).reset_index(drop=True)
        combined = pd.concat([reported.reset_index(drop=True), matches.drop(columns=KEY)], axis=1)
        combined = combined.merge(active_sets, on=keys, how="left", validate="one_to_one")
        combined = combined.merge(candidates[[*KEY, "GENCONID", "reconstructed_mw"]], on=[*KEY, "GENCONID"], how="left")
        combined = combined.merge(leaders, on=KEY, how="left", validate="one_to_one")
        combined["direction"] = direction
        combined["reconstruction_error_mw"] = combined.reconstructed_mw - combined.limit_mw
        combined["leader_error_mw"] = combined.leader_limit_mw - combined.limit_mw
        combined["exact_definition"] = combined.definition_match.eq("both") & combined.valid_version.eq(True)
        combined["exact_factor"] = combined.factor_match.eq("both") & combined.valid_version.eq(True)
        combined["match_status"] = np.select(
            [combined.reported_setter.isna(), combined.GENCONID.isna(), ~combined.valid_version.eq(True),
             ~combined.exact_definition, ~combined.exact_factor, combined.reconstructed_mw.isna()],
            ["no reported setter", "setter missing from public dispatch equations", "version unavailable or future-dated",
             "exact equation definition unavailable", "exact PEC coefficient unavailable", "direction or terms unresolved"],
            default="reconstructed reported setter",
        )
        blocks.append(combined)
    return pd.concat(blocks, ignore_index=True)


def reconstruction_summary(matches):
    rows = []
    for direction, group in matches.groupby("direction", sort=False):
        error = group.reconstruction_error_mw
        rows.append(dict(
            direction=direction, intervals=len(group), reported_setter_rows=group.reported_setter.notna().sum(),
            dispatch_version_rows=group.valid_version.eq(True).sum(), exact_definition_rows=group.exact_definition.sum(),
            exact_factor_rows=group.exact_factor.sum(), active_set_rows=group.sets.notna().sum(),
            reconstructable_rows=error.notna().sum(), within_1_mw=error.abs().le(1).sum(),
            reconstruction_mae_mw=error.abs().mean(), reconstruction_bias_mw=error.mean(),
            leader_rows=group.reconstructed_leader.notna().sum(),
            leader_agrees=group.reconstructed_leader.eq(group.reported_setter).sum(),
            leader_mae_mw=group.leader_error_mw.abs().mean(),
        ))
    return pd.DataFrame(rows)
