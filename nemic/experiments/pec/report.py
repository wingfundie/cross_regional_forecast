"""Render the EnergyConnect directional limits report from campaign evidence."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from importlib.metadata import version
from pathlib import Path

import markdown
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.style import context as plot_style

from scripts.report_theme.report_theme import figure_html, hero, matplotlib_style, metric, render_page


TITLE = "EnergyConnect directional limits"
DESCRIPTION = (
    "What dispatch allowed on NSW1-SA1, which equations set the limits, and how much of the "
    "seven-day outlook can be tested with records available at issue time."
)
MARKET_INTEGRATION = (
    "https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/"
    "project-energyconnect-market-integration-project"
)
TEST_PROGRAM = "https://www.aemo.com.au/consultations/current-and-closed-consultations/pec-stage-2-internetwork-test-program"
DISPATCH_ARCHIVE = "https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/"
SOURCES = {
    "AEMO market integration release record": MARKET_INTEGRATION,
    "AEMO Stage 2 inter-network test program": TEST_PROGRAM,
    "NEMWEB five-minute DispatchIS archive": DISPATCH_ARCHIVE,
    "NEMWEB MMSDM historical tables": "https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/",
    "NEMWEB next-day dispatch": "https://www.nemweb.com.au/Reports/CURRENT/Next_Day_Dispatch/",
    "NEMWEB next-day predispatch": "https://www.nemweb.com.au/Reports/CURRENT/Next_Day_PreDispatch/",
    "NEMWEB predispatch vintage archive": "https://www.nemweb.com.au/Reports/ARCHIVE/PredispatchIS_Reports/",
    "AEMO short-term PASA procedures": "https://www.aemo.com.au/-/media/files/electricity/nem/planning_and_forecasting/pasa/st-pasa-procedure.pdf",
    "AEMO market notice 145435": "https://nemweb.com.au/Reports/CURRENT/Market_Notice/NEMITWEB1_MKTNOTICE_20261001.R145435",
    "AEMO market notice 145438": "https://nemweb.com.au/Reports/CURRENT/Market_Notice/NEMITWEB1_MKTNOTICE_20261001.R145438",
    "AEMO market notice 146031": "https://nemweb.com.au/Reports/CURRENT/Market_Notice/NEMITWEB1_MKTNOTICE_20261104.R146031",
    "AEMO market notice 146032": "https://nemweb.com.au/Reports/CURRENT/Market_Notice/NEMITWEB1_MKTNOTICE_20261104.R146032",
    "AEMO market notice 146187": "https://nemweb.com.au/Reports/CURRENT/Market_Notice/NEMITWEB1_MKTNOTICE_20261109.R146187",
}
DIRECTIONS = {"nsw_sa": "NSW → SA", "sa_nsw": "SA → NSW"}
COHORTS = {
    "historical_baselines": "Historical baselines",
    "verified_predispatch": "Verified predispatch",
    "verified_stpasa": "Verified ST PASA",
    "matched_challengers_predispatch": "Matched predispatch challengers",
    "matched_challengers_stpasa": "Matched ST PASA challengers",
    "archive_predispatch_proxy": "Predispatch archive proxy",
}
ARTIFACTS = {
    "coverage.csv": "Daily target coverage and missing intervals",
    "source_hashes.csv": "Original source URLs and content hashes",
    "gaps.csv": "Missing five-minute interval timestamps",
    "transitions.csv": "Observed network configuration transitions",
    "market_notices.csv": "Contemporaneous commissioning, security and residue notices",
    "set_invocations.csv": "Constraint set membership and invocation at dispatch",
    "outages.csv": "Network Outage Scheduler records relevant to the study",
    "outage_intervals.csv": "Five-minute joins between outages and invoked constraints",
    "setter_summary.csv": "Reported setters and their frequency",
    "episodes.csv": "Restriction and setter-switch episodes",
    "constraint_matches.csv": "Five-minute equation, invocation and reconstruction evidence",
    "reconstruction_summary.csv": "Directional constraint reconstruction accuracy and coverage",
    "five_minute_limits.csv": "Five-minute signed limits, flow and setter evidence",
    "half_hour_limits.csv": "Complete half-hour targets and independent directional minima",
    "october_reconciliation.csv": "October monthly extract compared with original dispatch vintages",
    "november_flow_crosscheck.csv": "Earlier November dispatch-flow profile reproduced at half-hour frequency",
    "conditional_limits.csv": "Conditional percentile lookup and day-block uncertainty",
    "conditional_support.csv": "Exact intervals behind the conditional lookup",
    "conditional_relationships.csv": "Regional associations before and within setter groups",
    "forecast_scores.csv": "Forecast scorecards and matched rows",
    "forecast_coverage.csv": "Issue-time forecast and target coverage",
    "forecast_protocol.json": "Forecast model, time and provenance protocol",
    "forecast_sources.csv": "Forecast release times and original archive hashes",
    "forecast_publication_audit.csv": "Original publication timing compared with archived-member timing",
    "forecast_partitions.csv": "Purged training, selection, calibration and evaluation blocks",
    "forecast_vintage_matches.csv": "Issue-time forecast vintages linked to the delivery path",
    "restriction_thresholds.csv": "Frozen restriction thresholds in MW",
}


def file_digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def evidence(directory: Path, name: str) -> pd.DataFrame:
    path = directory / name
    if path.is_file() and path.stat().st_size:
        try:
            return pd.read_csv(path, low_memory=False, keep_default_na=False, na_values=[""])
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    return pd.DataFrame()


def cell(value) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (float, np.floating)):
        value = f"{value:,.2f}".rstrip("0").rstrip(".")
    if isinstance(value, (bool, np.bool_)):
        value = "Yes" if value else "No"
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace("\n", " ").replace("|", "&#124;")


def table(frame: pd.DataFrame, columns: dict[str, str], rows: int) -> str:
    if frame.empty:
        return "The evidence table has no rows."
    columns = {key: label for key, label in columns.items() if key in frame}
    if not columns:
        return "See the complete evidence table in the downloads."
    view = frame[list(columns)].head(rows).copy()
    if "direction" in view:
        view["direction"] = view.direction.replace(DIRECTIONS)
    if "aggregation" in view:
        view["aggregation"] = view.aggregation.replace({"tight": "Tightest", "mean": "Mean"})
    if "cohort" in view:
        view["cohort"] = view.cohort.replace(COHORTS)
    if "schedule" in view:
        view["schedule"] = view.schedule.replace({"daily_0800": "Daily 08:00", "updates": "Half-hour updates"})
    if "model" in view:
        view["model"] = view.model.replace({
            "persistence": "Persistence", "delivery_period": "Delivery period", "aemo": "AEMO",
            "regional_forecast": "Regional forecast", "regional_plus_constraints": "Regional + constraints",
        })
    rendered = ["| " + " | ".join(columns.values()) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    rendered.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in view.itertuples(index=False, name=None))
    return "\n".join(rendered)


def preserve_gaps(frame: pd.DataFrame, freq: str) -> pd.DataFrame:
    indexed = frame.set_index("time").sort_index()
    return indexed.asfreq(freq)


def limit_chart(frame: pd.DataFrame, path: Path) -> None:
    ordered = preserve_gaps(frame, "30min")
    with plot_style(matplotlib_style()):
        figure = Figure(figsize=(11.5, 5.3), layout="constrained")
        FigureCanvasAgg(figure)
        axes = figure.subplots(nrows=2, ncols=1, sharex=True, sharey=True)
        for axis, (direction, label) in zip(axes, DIRECTIONS.items(), strict=True):
            axis.plot(ordered.index, ordered[f"{direction}_mean"], color="#5eaaa7", lw=1.3, label="Mean")
            axis.plot(ordered.index, ordered[f"{direction}_tight"], color="#6649b8", lw=0.8, label="Tightest")
            axis.axhline(0, color="#687586", lw=0.65)
            axis.set_title(label, loc="left", pad=8, fontweight="bold")
            axis.set_ylabel("MW")
            axis.margins(x=0.01)
        settlement = pd.Timestamp("2026-11-01")
        if ordered.index[0] <= settlement <= ordered.index[-1]:
            for axis in axes:
                axis.axvline(settlement, color="#94651d", linestyle="--", lw=1)
            axes[0].text(settlement, 0.97, "Settlement release  ", color="#81581a", fontsize=9,
                         verticalalignment="top", horizontalalignment="right", transform=axes[0].get_xaxis_transform(),
                         bbox={"facecolor": "#ececf3", "edgecolor": "none", "pad": 2})
        axes[0].legend(loc="upper left", ncols=2, bbox_to_anchor=(0.16, 1.15))
        locator = mdates.AutoDateLocator(minticks=4, maxticks=9, interval_multiples=True)
        axes[-1].xaxis.set_major_locator(locator)
        axes[-1].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        axes[-1].set_xlabel("Interval ending in NEM time (UTC+10)")
        figure.savefig(path, dpi=150)


def episode_chart(native: pd.DataFrame, path: Path, security_switch: bool = False) -> tuple[str, pd.Timestamp] | None:
    required = {"time", "nsw_sa_mw", "sa_nsw_mw", "dispatch_flow_mw", "metered_flow_mw"}
    if not required.issubset(native) or native.empty:
        return None
    native = native.assign(time=pd.to_datetime(native.time)).sort_values("time")
    changes = native[["nsw_sa_mw", "sa_nsw_mw"]].diff()
    changes = changes.where(native.time.diff().eq(pd.Timedelta(minutes=5)), axis=0)
    magnitude = changes.abs().max(axis=1)
    if magnitude.isna().all():
        return None
    direction = "nsw_sa"
    if security_switch:
        candidates = native.time.ge(pd.Timestamp("2026-11-09 09:05")) & native.nsw_sa_setter.isin(["NS_200", "NS_200_DYN"])
        candidates &= changes.nsw_sa_mw.notna()
        if not candidates.any():
            return None
        event = native[candidates].index[0]
        event_label = "The first dispatch limit set by the NSW security equations changed by"
    else:
        event = magnitude.idxmax()
        direction = changes.loc[event].abs().idxmax().removesuffix("_mw")
        event_label = "The largest adjacent five-minute movement was"
    time = native.at[event, "time"]
    excerpt = native[native.time.between(time - pd.Timedelta(hours=2), time + pd.Timedelta(hours=2))]
    excerpt = preserve_gaps(excerpt, "5min")
    movement = changes.at[event, f"{direction}_mw"]
    setter = native.at[event, f"{direction}_setter"] if f"{direction}_setter" in native else None
    setter = setter if pd.notna(setter) else "unreported equation"
    prior = native.iloc[native.index.get_loc(event) - 1]
    prior_setter = prior.get(f"{direction}_setter")
    prior_setter = prior_setter if pd.notna(prior_setter) else "unreported equation"
    before = prior[f"{direction}_mw"]
    after = native.at[event, f"{direction}_mw"]
    with plot_style(matplotlib_style()):
        figure = Figure(figsize=(11.5, 4.3), layout="constrained")
        FigureCanvasAgg(figure)
        axis = figure.subplots()
        axis.plot(excerpt.index, excerpt.nsw_sa_mw, color="#6749b9", lw=1.6, label="NSW → SA upper limit")
        axis.plot(excerpt.index, -excerpt.sa_nsw_mw, color="#268a87", lw=1.6, label="SA → NSW lower limit")
        axis.plot(excerpt.index, excerpt.dispatch_flow_mw, color="#33475c", lw=1.2, label="Dispatch flow")
        axis.plot(excerpt.index, excerpt.metered_flow_mw, color="#987128", lw=1.1, linestyle="--", label="Metered flow")
        axis.axhline(0, color="#697383", lw=0.6)
        axis.axvline(time, color="#81581a", lw=1)
        axis.legend(loc="lower left", ncols=2, bbox_to_anchor=(0, 1.025))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        axis.set_xlabel(f"{time:%d %b %Y} · interval ending in NEM time")
        axis.set_ylabel("MW on the NSW → SA flow axis")
        figure.savefig(path, dpi=150)
    note = (
        f"{event_label} {movement:+,.1f} MW for {DIRECTIONS[direction]} at "
        f"{time:%d %b %Y %H:%M} NEM time. The limit moved from {before:,.1f} MW with {prior_setter} to "
        f"{after:,.1f} MW with {setter}. The chart puts both "
        "limits on the signed NSW-to-SA flow axis, so the plotted lower bound equals IMPORTLIMIT. You can "
        "compare dispatch and metered flow with the limits on that same axis."
    )
    return note, time


def embed_chart(path: Path, title: str, note: str, download: str) -> tuple[str, str]:
    relative = f"figures/{path.name}"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    figure = figure_html(f'<img alt="{title}" src="data:image/png;base64,{encoded}">', title, note, download)
    return (
        f"![{title}]({relative})\n\n{note}",
        figure.replace('class="chart-scroll"', 'class="chart-scroll" role="region" aria-label="Plot" tabindex="0"'),
    )


def episode_evidence(matches: pd.DataFrame, time: pd.Timestamp) -> str:
    if "time" not in matches:
        return ""
    nearby = pd.to_datetime(matches.time).between(time - pd.Timedelta(minutes=5), time + pd.Timedelta(minutes=5))
    return table(matches.loc[nearby].sort_values(["time", "direction"]), {
        "time": "Interval ending", "direction": "Direction", "limit_mw": "Reported limit (MW)",
        "reported_setter": "Reported setter", "EFFECTIVEDATE": "Equation effective date", "VERSIONNO": "Version",
        "RHS": "RHS", "LHS": "LHS", "MARGINALVALUE": "Marginal value", "sets": "Joined set IDs", "match_status": "Resolution",
    }, 6)


def minimum_examples(frame: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    example_columns = ["time", "configuration"]
    for direction in DIRECTIONS:
        example_columns.extend(f"{direction}_{key}" for key in ("tight", "minimum_time", "setter"))
    minima = [f"{direction}_minimum_time" for direction in DIRECTIONS]
    if not set(minima).issubset(frame):
        return 0, pd.DataFrame()
    different = frame[minima].notna().all(axis=1) & frame[minima[0]].ne(frame[minima[1]])
    examples = frame.loc[different, frame.columns.intersection(example_columns)].copy()
    return int(different.sum()), examples


def coverage_section(half: pd.DataFrame, native: pd.DataFrame, daily: pd.DataFrame) -> tuple[str, str]:
    different, examples = minimum_examples(half)
    native_counts = ""
    if {"fixed_transfer", "zero_limits", "forced_flow"}.issubset(native):
        zero = int(native.zero_limits.eq(True).sum())
        fixed = int((native.fixed_transfer.eq(True) & native.zero_limits.eq(False)).sum())
        forced = int(native.forced_flow.eq(True).sum())
        native_counts = (f"Among the five-minute records, {zero:,} have two zero limits, {fixed:,} fix a nonzero "
                         f"transfer, and {forced:,} require flow in one direction. Fixed transfers can also require flow. ")
    coverage_totals = ""
    keys = {"expected_five_minute", "observed_five_minute", "incomplete_half_hours", "selected_intervention_intervals"}
    if keys.issubset(daily):
        totals = daily[list(keys)].sum()
        coverage_totals = (
            f"The source panel contains {totals.observed_five_minute:,} of {totals.expected_five_minute:,} expected five-minute "
            f"intervals. It has {totals.incomplete_half_hours:,} incomplete half-hours and "
            f"{totals.selected_intervention_intervals:,} intervals where the physical solution is an intervention run. "
            "When an intervention run exists, the target takes that physical solution. The selected run, raw run counts, "
            "and source timestamps remain in the evidence.\n\n"
        )
    excerpt = daily.sort_values("incomplete_half_hours", ascending=False, kind="stable") if "incomplete_half_hours" in daily else daily
    headers = {
        "study_day": "NEM day",
        "complete_half_hours": "Complete half-hours", "incomplete_half_hours": "Incomplete half-hours",
        "expected_five_minute": "Expected five-minute", "observed_five_minute": "Observed five-minute",
        "missing_five_minute": "Missing five-minute", "missing_directional_values": "Missing directional values",
        "selected_intervention_intervals": "Selected intervention intervals",
        "nos_snapshot_available": "Outage snapshot available",
    }
    overview = (
        "AEMO reports `EXPORTLIMIT` in the NSW-to-SA direction and `IMPORTLIMIT` in the underlying "
        "signed flow coordinate. The SA-to-NSW target is `-IMPORTLIMIT`. Two zero limits form a zero-transfer "
        "state. A zero-width signed range at nonzero MW fixes a transfer. A negative directional limit means "
        "the solution requires flow in the other direction. Dispatch and metered flow describe the operating "
        "state while the signed limits supply the targets.\n\n"
        f"{coverage_totals}{native_counts}A complete half-hour includes the six five-minute intervals ending at its delivery time. "
        "The mean and the minimum use those six measurements. Each direction keeps its own minimum timestamp and "
        f"setter. The directional minima occurred at distinct times in {different:,} complete half-hours. "
        "A combined range from two such minima can imply a restriction that never occurred in the same dispatch interval."
    )
    dates = table(excerpt, headers, 6)
    if not examples.empty:
        pairs = table(examples, {
            "time": "Half-hour ending", "configuration": "Configuration",
            "nsw_sa_tight": "NSW → SA MW", "nsw_sa_minimum_time": "NSW → SA minimum time",
            "nsw_sa_setter": "NSW → SA setter", "sa_nsw_tight": "SA → NSW MW",
            "sa_nsw_minimum_time": "SA → NSW minimum time", "sa_nsw_setter": "SA → NSW setter",
        }, 4)
        dates += f"\n\n### Examples with separate directional restrictions\n\n{pairs}"
    if len(excerpt) > 6:
        dates += "\n\n[Download coverage for every NEM day](downloads/coverage.csv)."
    return overview, dates


def reconciliation_section(downloads: Path) -> str:
    october = evidence(downloads, "october_reconciliation.csv")
    november = evidence(downloads, "november_flow_crosscheck.csv")
    sources = evidence(downloads, "source_hashes.csv")
    sections = []
    if not october.empty:
        equal = int(october.differing_rows.eq(0).sum())
        sections.extend([
            "### October extract reconciliation",
            f"The original five-minute dispatch vintages and the October MMSDM extract match on the selected "
            f"solution for all common timestamps in {equal} of the {len(october)} audited fields. Values match "
            "within 0.001 MW for numeric fields. The counts expose any timestamps present in only one extract.",
            table(october, {"field": "Audited field", "in_original": "Original rows", "in_monthly": "Monthly rows",
                            "matched": "Matched rows", "equal_rows": "Equal rows", "differing_rows": "Differing rows",
                            "max_abs_difference": "Maximum absolute difference"}, 16),
            "[Download October reconciliation](downloads/october_reconciliation.csv)",
        ])
    if not november.empty:
        matched = int(november.status.eq("reconciled").sum())
        hash_copy = ""
        if {"earlier_sha256", "earlier_hash_matches"}.issubset(sources):
            prior_hashes = sources[sources.earlier_sha256.notna()]
            same = prior_hashes.earlier_hash_matches.astype(str).str.lower().eq("true").sum()
            hash_copy = f" {same} of {len(prior_hashes)} retained November archive hashes match the earlier register."
        sections.extend([
            "### Earlier November flow profile",
            f"The half-hour dispatch flow reproduces {matched} of {len(november)} delivery blocks in the retained "
            f"November flow-profile check. Positive flow points from NSW to SA.{hash_copy} Flow remains a separate "
            "series throughout the directional limit study.",
            table(november, {"delivery_period": "NEM time block", "expected_half_hours": "Earlier half-hours",
                             "observed_half_hours": "Observed half-hours", "legacy_p10_mw": "Earlier P10 (MW)",
                             "p10_mw": "Rebuilt P10 (MW)", "legacy_p50_mw": "Earlier median (MW)",
                             "p50_mw": "Rebuilt median (MW)", "legacy_p90_mw": "Earlier P90 (MW)",
                             "p90_mw": "Rebuilt P90 (MW)", "status": "Result"}, 5),
            "[Download the flow comparison](downloads/november_flow_crosscheck.csv)",
        ])
    return "\n\n".join(sections)


def commissioning_section(half: pd.DataFrame, transitions: pd.DataFrame) -> str:
    panel = half.assign(study_day=(half.time - pd.Timedelta(nanoseconds=1)).dt.normalize())
    configs = panel.groupby("configuration", dropna=False).agg(
        first=("time", "min"), last=("time", "max"), count=("time", "size"), days=("study_day", "nunique"),
    ).reset_index().sort_values(["count", "first"], ascending=[False, True])
    singleton = int(configs.days.eq(1).sum())
    return "\n\n".join([
        f"AEMO lists registration and auction changes in August, then the separate `NSW1-SA1` dispatch "
        f"representation on 1 October 2026. The settlement release took effect on 1 November 2026. "
        f"[AEMO market integration release record]({MARKET_INTEGRATION})",
        f"At the October cutover AEMO announced a ±150 MW setting and recorded line 6F out of service. "
        f"The notice planned the return of 6F and the activation of loop set `L-PEC_X_6C_6G_6H` after the return. "
        f"A separate notice records a negative-residue-management application fix effective from the interval "
        f"ending 09:25 that morning. [Registration notice 145435]({SOURCES['AEMO market notice 145435']}) · "
        f"[Application fix notice 145438]({SOURCES['AEMO market notice 145438']})",
        f"At 12:30 on 4 November AEMO commissioned lines 6C, 6G and 6H and marked the start of Stage 2 inter-network "
        f"tests. Earlier that day, a negative settlement residue event had activated its own constraint. At "
        f"09:05 on 9 November AEMO invoked `I-NS_200` for NSW system security. These records distinguish the "
        f"test program from market controls and a later security restriction. "
        f"[Negative residue notice 146031]({SOURCES['AEMO market notice 146031']}) · "
        f"[Commissioning notice 146032]({SOURCES['AEMO market notice 146032']}) · "
        f"[Security notice 146187]({SOURCES['AEMO market notice 146187']})",
        f"AEMO published a staged Stage 2 test program. Test authorization and an observed dispatch limit are "
        f"different kinds of evidence. The configuration timeline uses the operating record, and each entry "
        f"retains the available equation, invocation or outage evidence. [AEMO Stage 2 test program]({TEST_PROGRAM})",
        "The study classifies the commissioning cap from equations present in the dispatch solution, then tags "
        "identified outages and the NSW security control. A within-half-hour change preserves the observed "
        "sequence of configurations in that half-hour's label. The timeline shows first appearances of operating "
        "states. The episode table shows subsequent returns and switches.",
        "### Most frequently observed configurations",
        f"Among the {len(configs):,} complete-half-hour configuration labels, {singleton:,} occur on just one study day. "
        "Even when a label covers multiple intervals, one day provides a single example.",
        table(configs, {"configuration": "Observed configuration", "first": "First half-hour ending", "last": "Last half-hour ending",
                        "count": "Complete half-hours", "days": "Distinct days"}, 18),
        "### Observed configuration transitions",
        table(transitions, {"time": "NEM time", "milestone": "Milestone", "nsw_sa_mw": "NSW → SA (MW)",
                            "sa_nsw_mw": "SA → NSW (MW)", "nsw_sa_setter": "NSW → SA setter",
                            "sa_nsw_setter": "SA → NSW setter", "evidence": "Evidence"}, 18),
        "[Download the configuration transition record](downloads/transitions.csv)",
    ])


def constraint_section(setters: pd.DataFrame, reconstruction: pd.DataFrame, matches: pd.DataFrame, episodes: pd.DataFrame) -> str:
    episode_columns = {"direction": "Direction", "episode_id": "Episode ID", "start": "Start", "end": "End", "episode_type": "Episode type",
                       "configuration": "Configuration", "previous_setter": "Previous equation", "setter": "New equation",
                       "previous_limit_mw": "Prior limit (MW)", "first_limit_mw": "First limit (MW)",
                       "minimum_limit_mw": "Minimum limit (MW)", "minimum_time": "Minimum time", "change_mw": "Change (MW)",
                       "duration_minutes": "Minutes", "sets": "Constraint sets", "outage_ids": "Outage IDs",
                       "notice_ids": "Notice IDs", "description": "Equation description"}
    sustained, severe = episodes, episodes
    by_type = pd.DataFrame()
    frequent = setters.groupby("direction", sort=False).head(6) if "direction" in setters else setters
    reconciliation = []
    statuses = (matches.groupby(["direction", "match_status"]).size().rename("intervals").reset_index()
                if {"direction", "match_status"}.issubset(matches) else pd.DataFrame())
    if {"intervals", "exact_definition_rows"}.issubset(reconstruction):
        reconstruction = reconstruction.assign(
            definition_share_pct=100 * reconstruction.exact_definition_rows.div(reconstruction.intervals.replace(0, np.nan))
        )
    if {"direction", "reconstructable_rows", "within_1_mw", "leader_agrees", "leader_rows", "leader_mae_mw"}.issubset(reconstruction):
        for row in reconstruction.itertuples(index=False):
            if row.reconstructable_rows and row.leader_rows:
                reconciliation.append(
                    f"For {DIRECTIONS[row.direction]}, {row.within_1_mw:,} of {row.reconstructable_rows:,} "
                    f"reconstructed reported setters match within 1 MW. The limiting candidate across available equations "
                    f"matches AEMO's setter in {row.leader_agrees:,} of {row.leader_rows:,} candidate intervals. Its "
                    f"reconstructed limit has {row.leader_mae_mw:,.1f} MW MAE against AEMO's reported limit."
                )
    if {"direction", "sustained_rank", "severity_rank"}.issubset(episodes):
        sustained = episodes[episodes.sustained_rank.gt(0)].sort_values("sustained_rank").groupby("direction", sort=False).head(5)
        severe = episodes[episodes.severity_rank.gt(0)].sort_values("severity_rank").groupby("direction", sort=False).head(5)
        if "episode_type" in episodes:
            by_type = episodes.sort_values("severity_rank").drop_duplicates(["direction", "episode_type"])
    return "\n\n".join([
        "A reported setter is the equation ID on the interconnector record. The dispatch classification flags an "
        "equation as binding if its absolute marginal value or violation exceeds 0.000001. A near-binding equation "
        "has neither flag and has at most 5 MW of PEC-equivalent slack. For an eligible equation, hold the other "
        "solved terms fixed and compute the implied flow as dispatch flow plus `(RHS − LHS) / PEC coefficient`. "
        "The most restrictive reconstructed bound in each direction identifies the limiting equation among "
        "eligible candidates. Equality equations can contribute in both directions. A setter can be reported "
        "when the public data lack an exact equation version or eligible coefficient.",
        *reconciliation,
        "### Equation identity and reconstruction coverage",
        table(reconstruction, {"direction": "Direction", "intervals": "Intervals", "reported_setter_rows": "Reported setter",
                               "dispatch_version_rows": "Reported equation version", "exact_definition_rows": "Exact definition",
                               "definition_share_pct": "Exact definition (%)",
                               "exact_factor_rows": "Exact coefficient", "active_set_rows": "Active set join",
                               "reconstructable_rows": "Reconstructed setter bounds", "within_1_mw": "Within 1 MW",
                               "reconstruction_mae_mw": "MAE (MW)", "reconstruction_bias_mw": "Bias (MW)",
                               "leader_rows": "Reconstructed limiting rows", "leader_agrees": "Reconstructed IDs match setter",
                               "leader_mae_mw": "Limiting bound MAE (MW)"}, 12),
        table(statuses, {"direction": "Direction", "match_status": "Equation resolution", "intervals": "Intervals"}, 16),
        "### Most frequently reported equations",
        table(frequent, {"direction": "Direction", "setter": "Reported equation", "intervals": "Intervals",
                         "first_seen": "First seen", "last_seen": "Last seen", "binding_rows": "Binding rows",
                         "near_binding_rows": "Near-binding rows", "median_mw": "Median limit (MW)",
                         "minimum_mw": "Minimum limit (MW)", "sets": "Joined set IDs"}, 12),
        "### Constraint episodes",
        "Read the change in MW against the preceding dispatch interval. Duration describes the observed run "
        "of the state. Where the equation or invocation cannot be resolved, the interval still contributes "
        "to the observed target and remains visible in the evidence.",
        "#### Sustained restrictions",
        table(sustained, episode_columns, 10),
        "#### Severe restrictions and changes",
        table(severe, episode_columns, 10),
        "#### Representative episodes by state",
        table(by_type, episode_columns, 18),
        "[Download the episode evidence](downloads/episodes.csv)",
    ])


def conditional_section(lookup: pd.DataFrame, relationships: pd.DataFrame) -> str:
    scope = lookup.copy()
    comparison = ""
    if {"configuration", "intervals"}.issubset(scope):
        largest = scope.groupby("configuration").intervals.sum().nlargest(2).index
        scope = scope[scope.configuration.isin(largest)].groupby("configuration", sort=False).head(16)
    reference_columns = {"configuration", "intervals", "distinct_days", "direction", "p10_mw", "aggregation", "delivery_period"}
    if reference_columns.issubset(lookup):
        overnight = lookup[lookup.aggregation.eq("tight") & lookup.delivery_period.eq("overnight")]
        if not overnight.empty:
            name = overnight.loc[overnight.intervals.idxmax(), "configuration"]
            pairs = overnight[overnight.configuration.eq(name)].set_index("direction")
            if set(DIRECTIONS).issubset(pairs.index):
                north, south = pairs.loc["nsw_sa"], pairs.loc["sa_nsw"]
                comparison = (
                    f"In the largest overnight reference, **{name}**, the NSW-to-SA tight-limit P10 is "
                    f"{north.p10_mw:,.1f} MW and the SA-to-NSW P10 is {south.p10_mw:,.1f} MW across "
                    f"{north.intervals:,} half-hours on {north.distinct_days:,} days. The overnight tails depend "
                    "on which direction you are estimating."
                )
    examples = pd.DataFrame()
    keys = ["configuration", "delivery_period", "direction", "aggregation", "feature"]
    columns = {*keys, "population", "spearman_r", "matched_intervals", "setter"}
    if columns.issubset(relationships):
        observed = relationships[relationships.spearman_r.notna() & relationships.aggregation.eq("tight")]
        paired = observed[observed.population.eq("within_setter")].merge(
            observed.loc[observed.population.eq("all_setters"), keys + ["spearman_r"]],
            on=keys, suffixes=("_within", "_pooled"), validate="many_to_one",
        )
        examples = (paired.sort_values("matched_intervals", ascending=False)
                    .drop_duplicates(["direction", "feature"]).sort_values(["feature", "direction"]))
    return "\n\n".join([
        "The lookup estimates the distribution of observed MW within a configuration and delivery period. "
        "Each direction and aggregation has its own P10, median and P90. Each 95% confidence interval uses "
        "500 draws of whole NEM study days with replacement. One observed day provides an example. A "
        "configuration outside the evidence returns **unsupported**. The period follows the half-hour midpoint. "
        "Morning is 06:00 to 09:00, solar is 09:00 to 16:00, evening is 16:00 to 21:00, and overnight covers "
        "the remaining hours.",
        "The reported setter attached to a direction is taken at its actual minimum timestamp. Labels in the "
        "mean-limit lookup refer to those historical directional setters. The means use all six dispatch intervals. "
        "The supporting-interval file connects each directional minimum timestamp to its episode ID and retains "
        "the regional MW fields used for matching.",
        "The scenario tool starts from the same configuration and period. It matches all entered demand, wind "
        "and solar fields jointly within the greater of 100 MW and each field's observed interquartile range. "
        "It declines values outside the observed marginal range. Condition presets take observed rows near the "
        "25th, 50th and 75th percentiles of the combined three-region residual demand. Historical mode uses the "
        "selected day's observed conditions, with that day still eligible as an analogue.",
        "### Conditional limit reference",
        comparison,
        table(scope, {"configuration": "Configuration", "delivery_period": "Delivery period", "direction": "Direction",
                      "aggregation": "Aggregation", "intervals": "Intervals", "distinct_days": "Days",
                      "p10_mw": "P10 (MW)", "p50_mw": "Median (MW)", "p90_mw": "P90 (MW)",
                      "p50_ci_low_mw": "Median 95% lower (MW)", "p50_ci_high_mw": "Median 95% upper (MW)",
                      "support": "Support", "dominant_setter": "Dominant reported setter"}, 32),
        "### Regional demand, wind, solar and residual demand",
        "Regional inputs use AEMO dispatch total demand and cleared semi-scheduled wind and solar. Residual "
        "demand subtracts those two observed generation series from total demand. The half-hour regional "
        "mean requires six values for its metric. The inputs describe the mix visible to dispatch.",
        "Compare regions within common delivery periods and configurations. The pooled results can reflect a "
        "change in the equation mix. The within-setter results hold the reported equation ID fixed and still "
        "reflect dispatch choices, fuel availability and the broader network. Rank correlations and contrasts "
        "between the outer feature quartiles describe conditional associations. A mechanical interpretation "
        "needs support from the actual equation and its applicable terms.",
        "The comparison below selects the most-supported within-setter tight-limit sample per direction and "
        "regional variable among cohorts with correlations for both populations.",
        table(examples, {"feature": "Regional variable", "direction": "Direction", "configuration": "Configuration",
                         "delivery_period": "Delivery period", "setter": "Setter", "matched_intervals": "Within-setter intervals",
                         "distinct_days": "Within-setter days", "spearman_r_pooled": "Pooled r", "spearman_r_within": "Within-setter r",
                         "high_minus_low_mw": "High minus low within setter (MW)"}, 24),
        "[Download conditional percentiles](downloads/conditional_limits.csv) · "
        "[Download their supporting intervals and episodes](downloads/conditional_support.csv) · "
        "[Download the relationship comparisons](downloads/conditional_relationships.csv)",
    ])


def forecast_section(scores: pd.DataFrame, availability: pd.DataFrame, thresholds: pd.DataFrame,
                     sources: pd.DataFrame, protocol: dict, longest_stpasa: float | None) -> str:
    overall = scores.copy()
    if "stratum" in overall:
        overall = overall[overall.stratum.isin(["all", "overall", "pooled"])]
    score_columns = {"schedule": "Schedule", "lead_band": "Lead band", "direction": "Direction",
                     "aggregation": "Aggregation", "model": "Method", "n": "Rows", "days": "Days",
                     "mae_mw": "MAE (MW)", "bias_mw": "Bias (MW)",
                     "skill_vs_persistence": "Skill vs persistence", "skill_vs_delivery_period": "Skill vs delivery period",
                     "skill_vs_aemo": "Skill vs AEMO", "interval_n": "Interval rows", "interval_coverage": "Interval coverage",
                     "interval_width_mw": "Interval width (MW)", "event_n": "Alert-evaluable rows", "precision": "Precision",
                     "recall": "Recall", "misses": "Misses", "false_alerts": "False alerts"}
    score_tables = []
    comparison = ""
    long_scores = pd.DataFrame()
    long_results = []
    if "cohort" in overall:
        for cohort, subset in overall.groupby("cohort", sort=False):
            score_tables.extend([f"#### {COHORTS.get(cohort, cohort)}", table(subset, score_columns, 50)])
        long_scores = overall[overall.schedule.eq("daily_0800") & overall.lead_band.eq("day 4-7") & overall.aggregation.eq("tight")]
        matched_long = long_scores[long_scores.cohort.eq("matched_challengers_stpasa")]
        for direction, detail in matched_long.groupby("direction"):
            model_mae = detail.set_index("model").mae_mw
            if {"regional_forecast", "regional_plus_constraints", "aemo", "delivery_period"}.issubset(model_mae.index):
                constraint_model = detail.set_index("model").loc["regional_plus_constraints"]
                long_results.append(
                    f"For {DIRECTIONS[direction]}, the regional model has {model_mae.regional_forecast:.1f} MW MAE and "
                    f"the model with constraints has {model_mae.regional_plus_constraints:.1f} MW. ST PASA has "
                    f"{model_mae.aemo:.1f} MW MAE and the historical delivery-period reference has "
                    f"{model_mae.delivery_period:.1f} MW on the same {int(detail.n.iloc[0]):,} forecast pairs. "
                    f"The constraint model missed {constraint_model.misses:,.0f} restrictions and produced "
                    f"{constraint_model.false_alerts:,.0f} false alerts."
                )
                if constraint_model.interval_n:
                    long_results[-1] += (
                        f" Its nominal 80% intervals covered {constraint_model.interval_coverage:.1%} of the "
                        f"{constraint_model.interval_n:,.0f} interval-eligible rows, with "
                        f"{constraint_model.interval_width_mw:,.1f} MW mean width."
                    )
        challengers = overall[overall.cohort.str.startswith("matched_challengers_")]
        model_names = {"regional_forecast", "regional_plus_constraints"}
        if model_names.issubset(challengers.model):
            pairs = challengers[challengers.model.isin(model_names)].pivot(
                index=["cohort", "schedule", "lead_band", "direction", "aggregation"], columns="model", values="mae_mw"
            ).dropna()
            better = int(pairs.regional_plus_constraints.lt(pairs.regional_forecast).sum())
            comparison = (
                f"The constraint challenger has lower MAE in {better} of {len(pairs)} matched product, schedule, "
                "lead, direction and aggregation cells. Each pair uses the same rows. The score slices share "
                "delivery intervals, so the cell count is descriptive and supplies no independent significance test."
            )
        else:
            comparison = (
                "The exported scores contain no matched comparison between the two challengers. The partition "
                "and coverage tables record which forecast inputs or chronological history gates prevented scoring."
            )
    if not score_tables:
        score_tables.append(table(overall, score_columns, 32))
    split_copy = ""
    publication_copy = ""
    if "evaluation_start_nem" in protocol:
        evaluation_start = pd.Timestamp(protocol["evaluation_start_nem"])
        cutoff = pd.Timestamp(protocol["delivery_cutoff_nem"])
        split_copy = (
            f"Scoreable origins start at {evaluation_start:%d %b %Y %H:%M} and deliveries end at {cutoff:%d %b %Y %H:%M}, "
            "both in NEM time. Baseline estimates expand with prior published half-hours. The challenger models "
            "use expanding seven-day evaluation folds and a prior four-day origin window to choose tree depth. "
            "When calibration has enough separate prior history, the replay reports the coverage and width of "
            "a nominal 80% interval. The archived predispatch timing proxy uses a separate score cohort because "
            "the archive cannot establish actual publication time for those older issues."
        )
        if longest_stpasa is not None:
            split_copy += (
                f" The longest observed delivery lead with verified ST PASA bounds in both directions is "
                f"{longest_stpasa:g} hours. The requested daily grid extends to 168 hours."
            )
    audit = protocol.get("archive_publication_audit", {})
    if audit.get("overlap") and audit.get("longest_publisher_lag_seconds") is not None:
        publication_copy = (
            f"Of {audit['overlap']:,} predispatch reports checked in both the archive and the original "
            f"publication directory, {audit['exact_byte_matches']:,} match byte for byte. The largest gap "
            f"to verified publication was {audit['longest_publisher_lag_seconds']:,.0f} seconds. The older archive "
            "cohort uses a timing proxy and supplies no issue-time challenger training examples. "
            "[Download the publication timing audit](downloads/forecast_publication_audit.csv)"
        )
    source_counts = pd.DataFrame()
    if {"product", "issued_at", "vintage"}.issubset(sources):
        source_counts = sources.groupby("product", as_index=False).agg(
            issues=("vintage", "nunique"), start=("issued_at", "min"), end=("issued_at", "max"),
        )
    return "\n\n".join([
        "The replay schedules an 08:00 NEM outlook with a 168-hour path and half-hourly updates with six-hour "
        "paths. Lead bands cover intraday, 6 to 24 hours, days 2 to 3, and days 4 to 7. The forecast score compares a "
        "signed prediction with the observed half-hour target in MW. MAE pays the same penalty for overstatement "
        "and understatement. Positive bias means predicted limits are higher than observed limits.",
        "Forecast inputs qualify only when both issue and observed receipt or publication evidence are available by the "
        "origin. The replay keeps regional inputs from one vintage. AEMO comparisons use common forecast and "
        "target rows within the product's supported lead, and the files show gaps where evidence is missing. "
        "Persistence and the expanding delivery-period reference supply the baseline outlooks. Restriction "
        "thresholds freeze before scoring. Blank interval fields indicate a calibration claim lacks support. "
        "ST PASA reflects a lack-of-reserve study case for an importing region. Its limits are a separate "
        "benchmark against observed dispatch targets. Half-hour predictions do not resolve the six five-minute "
        f"values inside the target window. [AEMO short-term PASA procedures]({SOURCES['AEMO short-term PASA procedures']})",
        "The replay freezes restriction thresholds at the pre-evaluation P10 for each direction, aggregation "
        "and delivery period with seven supporting days. Forecasts at or below that MW threshold count as "
        "alerts. The two challengers use prior signed limits and coherent regional forecasts. The second adds "
        "the published constraint predictions available at the same origin. Model selection, calibration and "
        "evaluation use separate chronological blocks, with the earlier target windows purged at each boundary. "
        "Read skill as 1 minus the ratio of MAE to the named baseline MAE on the matched rows. A zero baseline "
        "MAE leaves skill undefined.",
        "For persistence, a complete dispatch half-hour becomes eligible after its report creation mark and at "
        "least 30 minutes after delivery. Historical dispatch availability uses those original DispatchIS marks "
        "as its timing assumption. The direct forecast products have their own publisher evidence. The dispatch "
        "anchor lacks a measured local receipt log.",
        split_copy,
        publication_copy,
        table(source_counts, {"product": "Forecast product", "issues": "Source vintages", "start": "First issue (NEM)",
                              "end": "Last issue (NEM)"}, 6),
        comparison,
        "### Day 4 to day 7 outlook",
        "The tight-limit scores below come from daily 08:00 runs in the longest lead band. Compare methods "
        "inside each matched cohort so the comparison uses the same delivery intervals.",
        *long_results,
        table(long_scores, {"cohort": "Cohort", "direction": "Direction", "model": "Method", "n": "Matched rows",
                            "days": "Delivery days", "mae_mw": "MAE (MW)", "bias_mw": "Bias (MW)",
                            "precision": "Restriction precision", "recall": "Restriction recall"}, 24),
        "### Forecast input availability",
        table(availability, {"schedule": "Schedule", "lead_band": "Lead band", "cohort": "Coverage cohort",
                             "stage": "Availability gate", "n": "Rows", "origins": "Origins", "days": "Days",
                             "scheduled": "Scheduled", "evaluation_due": "Evaluation due", "observed": "Observed"}, 42),
        "### Signed directional forecast error and restriction alerts",
        *score_tables,
        "### Frozen restriction thresholds",
        table(thresholds, {"direction": "Direction", "aggregation": "Aggregation", "delivery_period": "Delivery period",
                           "threshold_mw": "Threshold (MW)", "n": "Training intervals", "days": "Training days",
                           "history_end": "Training cutoff (NEM)"}, 16),
        "The full scorecard retains separate lead, configuration, delivery-period and season slices for each "
        "direction and aggregation. The configuration slices describe the realised delivery state. The forecast "
        "inputs use the state available at origin.",
        "[Download all matched score slices](downloads/forecast_scores.csv) · "
        "[Download issue-time coverage](downloads/forecast_coverage.csv) · "
        "[Download frozen event thresholds](downloads/restriction_thresholds.csv)",
    ])


def build_report(data_dir: Path, output_dir: Path) -> dict:
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    downloads = output_dir / "downloads"
    figures = output_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    panel_path = data_dir / "half_hour.parquet"
    half = pd.read_parquet(panel_path).sort_values("time")
    if half.empty:
        raise ValueError("The report requires observed complete half-hour targets.")
    half["time"] = pd.to_datetime(half.time)
    dates = half.time - pd.Timedelta(nanoseconds=1)
    first = dates.iloc[0].date().isoformat()
    last = dates.iloc[-1].date().isoformat()
    season_names = np.array(["summer", "autumn", "winter", "spring"])
    seasons = ", ".join(pd.unique(season_names[(dates.dt.month % 12) // 3]))
    daily = evidence(downloads, "coverage.csv")
    native = evidence(downloads, "five_minute_limits.csv")
    coverage_copy, coverage_tables = coverage_section(half, native, daily)
    transitions = evidence(downloads, "transitions.csv")
    setters = evidence(downloads, "setter_summary.csv")
    reconstruction = evidence(downloads, "reconstruction_summary.csv")
    matches = evidence(downloads, "constraint_matches.csv")
    episodes = evidence(downloads, "episodes.csv")
    lookup = evidence(downloads, "conditional_limits.csv")
    relationships = evidence(downloads, "conditional_relationships.csv")
    scores = evidence(downloads, "forecast_scores.csv")
    available = evidence(downloads, "forecast_coverage.csv")
    thresholds = evidence(downloads, "restriction_thresholds.csv")
    forecast_sources = evidence(downloads, "forecast_sources.csv")
    protocol_path = downloads / "forecast_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8")) if protocol_path.exists() else {}
    stpasa_path = data_dir / "forecast_rows_stpasa.parquet"
    longest_stpasa = None
    if stpasa_path.exists() and "evaluation_start_nem" in protocol:
        target_columns = ["aemo_nsw_sa_tight", "aemo_sa_nsw_tight", "nsw_sa_tight", "sa_nsw_tight"]
        rows = pd.read_parquet(stpasa_path, columns=["origin", "time", "lead_hours", *target_columns])
        rows = rows[rows.origin.ge(pd.Timestamp(protocol["evaluation_start_nem"]))
                    & rows.time.le(pd.Timestamp(protocol["delivery_cutoff_nem"]))].dropna(subset=target_columns)
        if not rows.empty:
            longest_stpasa = float(rows.lead_hours.max())

    limit_path = figures / "directional_limits.png"
    limit_chart(half, limit_path)
    distinct_minima, _ = minimum_examples(half)
    configs = half.configuration.nunique()
    north_median = half.nsw_sa_tight.median()
    south_median = half.sa_nsw_tight.median()
    overview = (
        f"The complete target panel contains {len(half):,} half-hours across {configs:,} observed configurations "
        f"between {first} and {last}. Across those intervals, the tight-limit median was {north_median:,.1f} MW "
        f"from NSW to SA and {south_median:,.1f} MW from SA to NSW. These pooled medians describe the sampled "
        "commissioning window. Use the configuration lookup for conditional assumptions."
    )
    chart_title = "Paired directional limits across the observed window"
    chart_note = "The panels share a MW scale. The dashed marker gives the settlement release date. Gaps show missing complete half-hours."
    series_chart = embed_chart(limit_path, chart_title, chart_note, "downloads/half_hour_limits.csv")
    charts = [series_chart]
    plot_paths = [limit_path]
    chart_sections = []
    for filename, title, security in [
        ("dispatch_episode.png", "Dispatch and metered flow around the largest five-minute change", False),
        ("security_switch.png", "The 9 November switch to the NSW security equations", True),
    ]:
        path = figures / filename
        outcome = episode_chart(native, path, security_switch=security)
        if outcome:
            note, focus_time = outcome
            caption, html = embed_chart(path, title, note, "downloads/five_minute_limits.csv")
            charts.append((caption, html))
            chart_sections.extend([f"### {title}", caption, episode_evidence(matches, focus_time)])
            plot_paths.append(path)
    evidence_paths = sorted([*downloads.glob("*.csv"), *downloads.glob("*.json")])
    downloads_list = [f"- [{ARTIFACTS.get(path.name, path.stem.replace('_', ' ').capitalize())}](downloads/{path.name})"
                      for path in evidence_paths]
    source_links = [f"- [{name}]({url})" for name, url in SOURCES.items()]
    scenario = "[Open the local scenario tool](scenario.html)." if (output_dir / "scenario.html").exists() else ""
    sections = [
        ("coverage", "Observed limits and flow", "\n\n".join([
            overview, coverage_copy, series_chart[0], coverage_tables, reconciliation_section(downloads)
        ])),
        ("commissioning", "Commissioning and network configurations", commissioning_section(half, transitions)),
        ("equations", "Equations and restriction episodes", "\n\n".join([
            constraint_section(setters, reconstruction, matches, episodes), *chart_sections
        ])),
        ("conditions", "Conditional limit assumptions", "\n\n".join([conditional_section(lookup, relationships), scenario])),
        ("forecast", "Forecasts replayed at issue time",
         forecast_section(scores, available, thresholds, forecast_sources, protocol, longest_stpasa)),
        ("evidence", "Sources, methods and downloads", "\n\n".join([
            "All delivery and issue timestamps in the tables use fixed NEM time (UTC+10). NEM study days include "
            "the interval ending at the following midnight. Half-hour targets require six observations. See daily "
            "coverage and source reconciliation before treating the sample as a full history.",
            "AEMO's reported limits are outcomes of the dispatch solution. The results cover the observed "
            "commissioning and outage states. The report contains no estimate of secure transfer capability "
            f"after a cap is removed. The observed season coverage is {seasons}.",
            "### Research evidence", "\n".join(downloads_list),
            "### AEMO and NEMWEB source references", "\n".join(source_links),
        ])),
    ]
    markdown_body = "\n\n".join(f"## {title}\n\n{copy}" for _, title, copy in sections)
    (output_dir / "report.md").write_text(f"# {TITLE}\n\n{DESCRIPTION}\n\n{markdown_body}\n", encoding="utf-8")
    tags = ["NSW1-SA1", f"{first} to {last}", "NEM time · UTC+10", "Commissioning research"]
    header = hero("INTERFLOW · NEM RESEARCH", "EnergyConnect", "Directional limits", DESCRIPTION, tags)
    nav = '<nav aria-label="Report sections">' + "".join(
        f'<a href="#{key}">{title}</a>' for key, title, _ in sections
    )
    if scenario:
        nav += '<a href="scenario.html">Scenario tool</a>'
    nav += "</nav>"
    stats = '<div class="metrics">' + "".join([
        metric("Complete half-hours", f"{len(half):,}", "Six five-minute observations per target"),
        metric("Observed configurations", f"{configs:,}", "Complete half-hour target panel"),
        metric("Different minima times", f"{distinct_minima:,}", "Half-hours with separate directional restrictions"),
        metric("Tight-limit median", f"{north_median:,.1f} / {south_median:,.1f} MW", "NSW → SA and SA → NSW"),
    ]) + "</div>"
    scope_card = ('<p class="callout">Every limit is an AEMO dispatch-solution outcome for the network state '
                  'that actually occurred. Positive and negative MW retain their directional meaning.</p>')
    html_sections = []
    for key, title, copy in sections:
        for chart_markdown, chart_html in charts:
            copy = copy.replace(chart_markdown, chart_html)
        rendered = markdown.markdown(copy, extensions=["tables"])
        rendered = rendered.replace("<table>", '<div class="table-wrap" role="region" aria-label="Evidence table" tabindex="0"><table>')
        rendered = rendered.replace("</table>", "</table></div>")
        html_sections.append(f'<section id="{key}"><h2>{title}</h2>{rendered}</section>')
    footer = ('<footer><a href="report.md" download>Download the Markdown report</a> · '
              '<a href="report_manifest.json" download>Download the report manifest</a></footer>')
    html = render_page(TITLE, header + nav + stats + scope_card + "".join(html_sections) + footer, plotly=False)
    mobile_style = (".chart-scroll img{min-width:640px;border-top:2px solid var(--blue)}"
                    ".chart-scroll:focus-visible{outline:3px solid var(--blue);outline-offset:-3px}"
                    ".chart-scroll{overscroll-behavior-x:contain}td:last-child{max-width:480px;white-space:normal}"
                    "figcaption span:first-child{min-width:0}nav a{min-height:24px}"
                    "@media(max-width:520px){nav{gap:8px}nav a{display:block;flex:0 0 calc(50% - 4px);line-height:1.35}}")
    html = html.replace("</style>", mobile_style + "</style>")
    (output_dir / "index.html").write_text(html, encoding="utf-8")

    tracked = sorted([*evidence_paths, *plot_paths, output_dir / "index.html", output_dir / "report.md"])
    if (output_dir / "scenario.html").is_file():
        tracked.append(output_dir / "scenario.html")
    manifest = {
        "report": TITLE,
        "first_observed_study_day": first,
        "last_observed_study_day": last,
        "half_hour_rows": len(half),
        "half_hour_sha256": file_digest(panel_path),
        "local_forecast_inputs": {stpasa_path.name: file_digest(stpasa_path)} if longest_stpasa is not None else {},
        "generator_sha256": file_digest(Path(__file__)),
        "dependencies": {name: version(name) for name in ("pandas", "matplotlib", "Markdown")},
        "rebuild": "python -m nemic.experiments.pec.campaign --stage report",
        "theme": {name: file_digest(Path(__file__).resolve().parents[3] / "scripts" / "report_theme" / name)
                  for name in ("report_theme.py", "report.css")},
        "sources": SOURCES,
        "artifacts": {path.relative_to(output_dir).as_posix(): file_digest(path) for path in tracked},
    }
    (output_dir / "report_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--data-dir", type=Path, default=Path("data/pec_limits_v1"))
    cli.add_argument("--out", type=Path, default=Path("local_exports/pec_limits_v1"))
    args = cli.parse_args()
    build_report(args.data_dir, args.out)


if __name__ == "__main__":
    main()
