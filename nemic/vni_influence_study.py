"""Event-based generator influence study for the corrected VNI pilot."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from .common import PROCESSED, dump
from .constraint_ingest import PILOT


def _corr(group, left, right):
    pair = group[[left, right]].dropna()
    if len(pair) < 20 or pair[left].nunique() < 2 or pair[right].nunique() < 2:
        return np.nan
    return pair[left].corr(pair[right], method="spearman")


def _episode_onset(mask: pd.Series) -> pd.Series:
    """Mark the first interval in each contiguous True episode."""
    mask = mask.fillna(False).astype(bool)
    return mask & ~mask.shift(1, fill_value=False)


def run():
    features = pd.read_parquet(PILOT / "constraint_features_5min.parquet")
    sensitivities = pd.read_parquet(PILOT / "unit_sensitivities.parquet")
    movement = pd.read_parquet(PILOT / "unit_movements.parquet")
    observed = pd.read_parquet(PROCESSED / "ic_5min.parquet")
    observed = observed[observed.INTERCONNECTORID.eq("VIC1-NSW1")].copy()
    observed = observed[(observed.time >= features.time.min()) & (observed.time <= features.time.max())]
    observed = observed.set_index("time").reindex(features.time)

    # A reversal is a single change in the last observed non-zero flow sign.
    # Comparing against t-30 minutes counts one physical crossing up to six times.
    flow_sign = np.sign(observed.flow).replace(0, np.nan).ffill()
    reversal = flow_sign.ne(flow_sign.shift(1)) & flow_sign.notna() & flow_sign.shift(1).notna()

    states = []
    for direction, q, limit_col in [("upper", -1.0, "export"), ("lower", 1.0, "import")]:
        state = pd.DataFrame({
            "time": features.time,
            "direction": direction,
            "q": q,
            "version_key": features[f"{direction}_version_key"],
            "constraint": features[f"{direction}_constraint"],
            "bound": features[f"conditional_{direction}"],
            "limit": observed[limit_col].to_numpy(),
            "flow": observed.flow.to_numpy(),
        })
        state["limit_change_30m"] = state.limit.diff(6)
        state["flow_change_30m"] = state.flow.diff(6)
        state["reversal"] = reversal.to_numpy()
        state["forced"] = state.limit.lt(0)
        state["forced_onset"] = _episode_onset(state.forced)
        drop = -state.limit_change_30m
        threshold = drop[drop > 0].quantile(.90)
        state["contraction"] = drop.ge(threshold) if np.isfinite(threshold) else False
        state["contraction_onset"] = _episode_onset(state.contraction)
        state["contraction_threshold_mw"] = threshold
        states.append(state)
    states = pd.concat(states, ignore_index=True)
    events = states[states[["contraction_onset", "reversal", "forced_onset"]].any(axis=1)].copy()
    events.to_parquet(PILOT / "influence_events.parquet", index=False, compression="zstd")

    contributions = states.merge(sensitivities[["version_key", "DUID", "sensitivity"]],
                                 on="version_key", how="inner")
    contributions = contributions.merge(movement[["time", "DUID", "delta_30m"]],
                                        on=["time", "DUID"], how="left")
    contributions["bound_impact_mw"] = contributions.sensitivity * contributions.delta_30m
    contributions["capacity_impact_mw"] = np.where(
        contributions.direction.eq("upper"), contributions.bound_impact_mw, -contributions.bound_impact_mw)
    contributions["tightening_mw"] = -contributions.capacity_impact_mw
    contributions["abs_impact_mw"] = contributions.bound_impact_mw.abs()
    contributions["aligned_with_limit_move"] = np.sign(contributions.capacity_impact_mw).eq(
        np.sign(contributions.limit_change_30m))
    contributions["aligned_with_flow_move"] = np.sign(contributions.bound_impact_mw).eq(
        np.sign(contributions.flow_change_30m))
    valid = contributions.dropna(subset=["bound_impact_mw"])
    nonzero = valid[valid.abs_impact_mw.gt(1e-9)]
    top = (nonzero.sort_values("abs_impact_mw").groupby(["time", "direction"], as_index=False).tail(1)
           .DUID.value_counts())

    rows = []
    for duid, group in valid.groupby("DUID"):
        contraction = group[group.contraction]
        reversal = group[group.reversal]
        forced = group[group.forced]
        rows.append({
            "DUID": duid,
            "contribution_rows": len(group),
            "active_constraint_versions": int(group.version_key.nunique()),
            "active_state_intervals": int(group[["time", "direction"]].drop_duplicates().shape[0]),
            "total_abs_impact_mw_observations": group.abs_impact_mw.sum(),
            "mean_abs_bound_impact_mw": group.abs_impact_mw.mean(),
            "p95_abs_bound_impact_mw": group.abs_impact_mw.quantile(.95),
            "total_tightening_mw_observations": group.tightening_mw.clip(lower=0).sum(),
            "total_relief_mw_observations": (-group.tightening_mw.clip(upper=0)).sum(),
            "top_contributor_intervals": int(top.get(duid, 0)),
            "limit_move_spearman": _corr(group, "capacity_impact_mw", "limit_change_30m"),
            "flow_move_spearman": _corr(group, "bound_impact_mw", "flow_change_30m"),
            "contraction_contribution_rows": len(contraction),
            "contraction_mean_tightening_mw": contraction.tightening_mw.mean() if len(contraction) else np.nan,
            "contraction_positive_share": contraction.tightening_mw.gt(0).mean() if len(contraction) else np.nan,
            "reversal_contribution_rows": len(reversal),
            "reversal_mean_abs_impact_mw": reversal.abs_impact_mw.mean() if len(reversal) else np.nan,
            "reversal_flow_alignment": reversal.aligned_with_flow_move.mean() if len(reversal) else np.nan,
            "forced_contribution_rows": len(forced),
            "forced_mean_abs_impact_mw": forced.abs_impact_mw.mean() if len(forced) else np.nan,
        })
    influence = pd.DataFrame(rows)
    # Total absolute impact is the persistence-weighted mechanical influence over
    # the study month; mean impact is retained as the intensity measure.
    influence["overall_rank"] = influence.total_abs_impact_mw_observations.rank(ascending=False, method="min")
    influence["intensity_rank"] = influence.mean_abs_bound_impact_mw.rank(ascending=False, method="min")
    # Do not promote a unit to an event leaderboard from a handful of coincident
    # observations. Twenty contribution rows is the declared descriptive minimum.
    influence["contraction_rank"] = influence.contraction_mean_tightening_mw.where(
        influence.contraction_contribution_rows.ge(20)).rank(ascending=False, method="min")
    influence["reversal_rank"] = influence.reversal_mean_abs_impact_mw.where(
        influence.reversal_contribution_rows.ge(20)).rank(ascending=False, method="min")
    influence["forced_rank"] = influence.forced_mean_abs_impact_mw.where(
        influence.forced_contribution_rows.ge(20)).rank(ascending=False, method="min")
    influence.sort_values("overall_rank").to_csv(PILOT / "generator_influence.csv", index=False)

    constraint = (states.groupby(["direction", "constraint"], dropna=False)
                  .agg(leading_intervals=("time", "size"), contraction_intervals=("contraction", "sum"),
                       contraction_episodes=("contraction_onset", "sum"),
                       reversal_events=("reversal", "sum"), forced_intervals=("forced", "sum"),
                       min_limit=("limit", "min"), mean_bound=("bound", "mean"))
                  .reset_index().sort_values("leading_intervals", ascending=False))
    constraint.to_csv(PILOT / "constraint_influence.csv", index=False)

    summary = {
        "study_start": str(features.time.min()), "study_end": str(features.time.max()),
        "five_minute_intervals": int(features.time.nunique()),
        "generator_count": int(influence.DUID.nunique()),
        "leading_constraint_count": int(states.constraint.nunique()),
        "upper_contraction_threshold_mw": float(states.loc[states.direction.eq("upper"), "contraction_threshold_mw"].dropna().iloc[0]),
        "lower_contraction_threshold_mw": float(states.loc[states.direction.eq("lower"), "contraction_threshold_mw"].dropna().iloc[0]),
        "flow_reversal_events": int(states.drop_duplicates("time").reversal.sum()),
        "upper_contraction_intervals": int(states.loc[states.direction.eq("upper"), "contraction"].sum()),
        "lower_contraction_intervals": int(states.loc[states.direction.eq("lower"), "contraction"].sum()),
        "upper_contraction_episodes": int(states.loc[states.direction.eq("upper"), "contraction_onset"].sum()),
        "lower_contraction_episodes": int(states.loc[states.direction.eq("lower"), "contraction_onset"].sum()),
        "upper_forced_intervals": int(states.loc[states.direction.eq("upper"), "forced"].sum()),
        "lower_forced_intervals": int(states.loc[states.direction.eq("lower"), "forced"].sum()),
        "upper_forced_onsets": int(states.loc[states.direction.eq("upper"), "forced_onset"].sum()),
        "lower_forced_onsets": int(states.loc[states.direction.eq("lower"), "forced_onset"].sum()),
        "tumut3": influence[influence.DUID.eq("TUMUT3")].to_dict("records"),
    }
    dump(PILOT / "influence_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return influence, constraint, summary


if __name__ == "__main__":
    run()
