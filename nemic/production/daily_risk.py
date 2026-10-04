"""Episode scoring for once-daily next-day research bulletins.

This contract is deliberately separate from the 30--120 minute intraday
warning scorer.  One issued bulletin contributes one exposure day, regardless
of how many half-hour risk windows it contains.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


KEYS = ("connector", "direction", "event_type")


def _times(frame, fields):
    out = frame.copy()
    for field in fields:
        out[field] = pd.to_datetime(out[field], utc=True).dt.tz_convert("Australia/Brisbane")
    return out


def group_windows(windows, gap_minutes=30):
    """Merge adjacent/overlapping half-hour windows for one issued bulletin."""
    required = {*KEYS, "issue", "start", "end", "probability"}
    if required - set(windows):
        raise ValueError(f"Missing warning fields: {sorted(required - set(windows))}")
    frame = _times(windows, ("issue", "start", "end"))
    if (frame.end < frame.start).any() or ((frame.start - frame.issue) < pd.Timedelta(0)).any():
        raise ValueError("Warning windows must start after issue and end after start")
    rows = []
    keys = ["connector", "direction", "issue"]
    for key, group in frame.sort_values("start").groupby(keys, sort=False):
        current = None
        for row in group.to_dict("records"):
            if current is None or row["start"] > current["end"] + pd.Timedelta(minutes=gap_minutes):
                if current is not None:
                    rows.append(current)
                current = dict(zip(keys, key)) | {
                    "start": row["start"], "end": row["end"],
                    "probability": float(row["probability"]),
                    "event_types": {row["event_type"]},
                }
            else:
                current["end"] = max(current["end"], row["end"])
                current["probability"] = max(current["probability"], float(row["probability"]))
                current["event_types"].add(row["event_type"])
        if current is not None:
            rows.append(current)
    result = pd.DataFrame(rows)
    if len(result):
        result["event_types"] = result.event_types.map(lambda value: "+".join(sorted(value)))
    return result


def score_daily_bulletins(windows, actual_events, threshold, eligible_issues=None, budget=3.0):
    """Score forecast episodes one-to-one against observed directional events.

    Low-limit and contraction forecasts that overlap in the same direction are
    merged into one alert episode and therefore share the alert budget.
    """
    grouped = group_windows(windows)
    events_required = {"connector", "direction", "start", "end"}
    if events_required - set(actual_events):
        raise ValueError(f"Missing event fields: {sorted(events_required - set(actual_events))}")
    events = _times(actual_events, ("start", "end")).reset_index(drop=True)
    if eligible_issues is None:
        issues = pd.DatetimeIndex(pd.to_datetime(windows.issue, utc=True).unique())
    else:
        issues = pd.DatetimeIndex(pd.to_datetime(eligible_issues, utc=True).unique())
    if len(issues) == 0:
        raise ValueError("At least one fully observable issued bulletin is required")
    grouped = grouped[grouped.issue.dt.tz_convert("UTC").isin(issues)]
    alerts = grouped[grouped.probability >= float(threshold)].copy()
    matched_events = set()
    tp = 0
    fp = 0
    false_alert_hours = 0.
    lead_minutes = []
    for alert in alerts.sort_values(["issue", "start"]).itertuples():
        candidates = events[
            (events.connector == alert.connector) & (events.direction == alert.direction)
            & (events.start <= alert.end) & (events.end >= alert.start)
            & ~events.index.isin(matched_events)
        ]
        if candidates.empty:
            fp += 1
            false_alert_hours += (alert.end - alert.start).total_seconds() / 3600
            continue
        event_index = int(candidates.sort_values("start").index[0])
        matched_events.add(event_index)
        tp += 1
        lead_minutes.append(max(0., (events.loc[event_index, "start"] - alert.issue).total_seconds() / 60))
    eligible_events = events[
        events.start.dt.normalize().isin(issues.tz_convert("Australia/Brisbane").normalize())
    ]
    # Events may fall on the day after a UTC-date issue. Include any event inside
    # an eligible bulletin's actual target window instead of inferring exposure
    # from a fixed issue frequency.
    if len(windows):
        coverage = []
        for issue, group in _times(windows, ("issue", "start", "end")).groupby("issue"):
            if issue.tz_convert("UTC") in issues:
                coverage.append((group.start.min(), group.end.max()))
        if coverage:
            mask = np.zeros(len(events), dtype=bool)
            for start, end in coverage:
                mask |= events.start.le(end) & events.end.ge(start)
            eligible_events = events[mask]
    fn = max(0, len(eligible_events) - len(matched_events & set(eligible_events.index)))
    return {
        "eligible_bulletins": int(len(issues)),
        "exposure_days": float(len(issues)),
        "alerts": int(len(alerts)),
        "true_positive_episodes": int(tp),
        "false_positive_episodes": int(fp),
        "false_episodes_per_day": float(fp / len(issues)),
        "false_alert_hours": float(false_alert_hours),
        "event_episodes": int(len(eligible_events)),
        "missed_episodes": int(fn),
        "recall": float(tp / (tp + fn)) if tp + fn else None,
        "precision": float(tp / (tp + fp)) if tp + fp else None,
        "mean_warning_lead_minutes": float(np.mean(lead_minutes)) if lead_minutes else None,
        "alert_budget_target": float(budget),
        "alert_budget_met": bool(fp / len(issues) <= budget),
    }


def threshold_for_budget(windows, actual_events, candidate_thresholds, budget=3.0, eligible_issues=None):
    """Select maximum-recall threshold among candidates meeting the alert budget."""
    candidates = sorted(set(float(value) for value in candidate_thresholds))
    if not candidates:
        raise ValueError("At least one candidate threshold is required")
    scored = []
    for threshold in candidates:
        result = score_daily_bulletins(windows, actual_events, threshold, eligible_issues, budget=budget)
        result["threshold"] = threshold
        scored.append(result)
    eligible = [row for row in scored if row["false_episodes_per_day"] <= budget]
    pool = eligible or scored
    return max(pool, key=lambda row: ((row["recall"] if row["recall"] is not None else -1),
                                     (row["precision"] if row["precision"] is not None else -1),
                                     row["threshold"]))
