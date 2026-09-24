"""Build the 'Outage regimes' section of the all-interconnector regime report from cached NOS regime tables.

Presentation only: reads data/nos_regime_v1/tables (no model or matching is re-run). In place, versioned (G10):
the v1 manifest is archived once, existing v1 outputs are hash-checked as unchanged, and a v2 manifest is written.

    python scripts/build_nos_regime_section.py
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "scripts" / "report_theme"))

import build_all_ic_regime_report as rr  # noqa: E402
from report_theme import figure_html, finding, metric, style_plotly  # noqa: E402

from nemic.experiments.nos_regime.common import DATA, EXEC  # noqa: E402
from nemic.experiments.nos_regime.lookup import build_lookup  # noqa: E402
from nemic.experiments.nos_regime.state import leaders  # noqa: E402

REPORT = rr.OUT
DL = REPORT / "downloads"
TABLES = DATA / "tables"
FRAGMENT = REPORT / "sources" / "nos_outage_regime_section.html"
MD_FRAGMENT = REPORT / "sources" / "nos_outage_regime_methodology.md"
START, END = "<!--NOS-OUTAGE-REGIME:START-->", "<!--NOS-OUTAGE-REGIME:END-->"
NAV = '<a href="#outages" data-nos="1">Outage regimes</a>'
NAMES = rr.IC_NAMES
ORDER = [NAMES[i] for i in rr.IC_ORDER]
STATE_ORDER = ["clear", "booked_only", "partial", "invoked_nonleading", "invoked_leading", "unknown"]
STATE_COL = {"clear": "#9aa3ad", "booked_only": "#ce9a48", "partial": "#d9c7a3", "invoked_nonleading": "#5696b9",
             "invoked_leading": "#8370b4", "unknown": "#e3e3ea"}
DIR_LABEL = {"forward": "Forward", "reverse": "Reverse"}


def load(prefix: str) -> pd.DataFrame:
    parts = []
    for ic in rr.IC_ORDER:
        p = TABLES / f"{prefix}__{ic}.parquet"
        if p.exists():
            f = pd.read_parquet(p)
            if "empty" not in f.columns:
                parts.append(f)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def fmt_mw(x):
    return "—" if pd.isna(x) else f"{x:+,.0f}"


def pct(x):
    return "—" if pd.isna(x) else f"{x:.0%}"


def plot(fig):
    return rr.plot_div(fig)


# ------------------------------------------------------------------------------------------ tables
def leader_transitions(units: pd.DataFrame, supported: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ic in units.ic.unique():
        lead = leaders(ic)
        lead["time30"] = lead.time.dt.ceil("30min")
        last = lead.sort_values("time").groupby(["direction", "time30"]).constraint.last()
        for direction in ["forward", "reverse"]:
            ser = last.xs(direction, level="direction") if direction in last.index.get_level_values(0) else pd.Series(dtype=object)
            fams = supported[(supported.ic == ic) & (supported.direction == direction)].GENCONSETID
            u = units[(units.ic == ic) & (units.direction == direction) & units.GENCONSETID.isin(fams) & units.matched]
            for f, g in u.groupby("GENCONSETID"):
                times = pd.DatetimeIndex(g.time).sort_values()
                during = ser.reindex(times).dropna()
                treated = set(times)
                before = []
                for t in times[~pd.Series(times).diff().le(pd.Timedelta("30min")).to_numpy()]:   # first half-hour of each run
                    prev = t - pd.Timedelta("30min")
                    steps = 0
                    while prev in treated and steps < 48:
                        prev -= pd.Timedelta("30min"); steps += 1
                    if prev in ser.index:
                        before.append(ser[prev])
                top_during = during.value_counts(normalize=True).head(3)
                top_before = pd.Series(before).value_counts(normalize=True).head(3) if before else pd.Series(dtype=float)
                rows.append({"ic": ic, "name": NAMES[ic], "direction": direction, "GENCONSETID": f,
                             "during_leader_1": top_during.index[0] if len(top_during) else None,
                             "during_share_1": top_during.iloc[0] if len(top_during) else np.nan,
                             "during_top3": "; ".join(f"{k} ({v:.0%})" for k, v in top_during.items()),
                             "before_top3": "; ".join(f"{k} ({v:.0%})" for k, v in top_before.items()),
                             "leader_changed_share": float(np.mean([b != during.get(t) for t, b in zip(times, before)])) if before else np.nan})
    return pd.DataFrame(rows)


def interaction(units: pd.DataFrame) -> pd.DataFrame:
    rows = []
    m = units[units.matched]
    for var, col in [("Temperature", "tbin"), ("VRE difference", "vbin"), ("Residual-demand difference", "rbin")]:
        g = m[m[col] >= 0].groupby(["name", "direction", col])
        t = g.agg(units_n=("d_capacity", "size"), capacity_effect=("d_capacity", "median"),
                  at_limit_effect=("d_at_limit", "mean"), flow_effect=("d_directional_flow", "median")).reset_index()
        t["regime"] = t[col].map({0: "low", 1: "normal", 2: "high"})
        t["driver"] = var
        rows.append(t.drop(columns=[col]))
    return pd.concat(rows, ignore_index=True)


def timing(units: pd.DataFrame) -> pd.DataFrame:
    m = units[units.matched]
    return (m.groupby(["name", "direction", "season", "day_period"])
            .agg(units_n=("d_capacity", "size"), capacity_effect=("d_capacity", "median"),
                 at_limit_effect=("d_at_limit", "mean"), flow_effect=("d_directional_flow", "median")).reset_index())


def at_limit_shares(fam: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """Replace degenerate medians of 0/1 at-limit flags with share differences over matched units:
    treated share = mean(at-limit flag), control share = mean(per-unit control median), effect = difference."""
    m = units[units.matched]
    g = m.groupby(["ic", "direction", "GENCONSETID"]).agg(treated_at_limit=("t_at_limit", "mean"), control_at_limit=("c_at_limit", "mean")).reset_index()
    g["effect_at_limit"] = g.treated_at_limit - g.control_at_limit
    fam = fam.drop(columns=["treated_at_limit", "control_at_limit", "effect_at_limit", "ci_lo_at_limit", "ci_hi_at_limit"], errors="ignore")
    return fam.merge(g, on=["ic", "direction", "GENCONSETID"], how="left")


# ------------------------------------------------------------------------------------------ build
def build() -> dict:
    fam = load("family_effects"); keys_eff = load("key_effects"); states = load("states"); spill = load("spillover")
    ev = load("event_study"); units = load("units"); panel = load("state_panel")
    br = pd.concat([pd.read_parquet(p) for p in TABLES.glob("booking_reliability__*.parquet")]).drop_duplicates(["ic", "study_year"], keep="last")
    relevance = pd.read_parquet(DATA / "set_relevance.parquet")
    k5 = pd.read_parquet(DATA / "k5_electrical.parquet")
    okeys = pd.read_parquet(DATA / "outage_keys.parquet")
    episodes = pd.read_parquet(DATA / "episodes.parquet")
    esets = pd.read_parquet(DATA / "episode_sets.parquet")
    connectors = [n for n in ORDER if n in set(fam.name)]
    fam = at_limit_shares(fam, units)
    sup = fam[fam.tier.eq("supported")].copy()
    units_sup = units.merge(sup[["ic", "direction", "GENCONSETID"]], on=["ic", "direction", "GENCONSETID"])

    # ---- derived tables
    cov = (panel.groupby(["ic", "direction", "state"]).size().rename("half_hours").reset_index())
    cov["share"] = cov.half_hours / cov.groupby(["ic", "direction"]).half_hours.transform("sum")
    cov["name"] = cov.ic.map(NAMES)
    state_summary = (panel[panel.state.ne("unknown")].groupby(["ic", "direction", "state", "season"])
                     .agg(half_hours=("capacity", "size"), capacity_p10=("capacity", lambda s: s.quantile(.1)),
                          capacity_median=("capacity", "median"), capacity_p90=("capacity", lambda s: s.quantile(.9)),
                          flow_median=("directional_flow", "median"), headroom_median=("headroom", "median"),
                          at_limit_share=("at_limit", "mean"), restricted_share=("restricted", "mean")).reset_index())
    state_summary["name"] = state_summary.ic.map(NAMES)
    tim = timing(units_sup); inter = interaction(units_sup)
    trans = leader_transitions(units, sup)
    lookup = build_lookup(keys_eff[keys_eff.level.ne("K2")] if len(keys_eff) else keys_eff, fam, okeys, esets, relevance, k5)
    lookup["name"] = lookup.ic.map(NAMES)
    rel_of = relevance[relevance.relevant].groupby("GENCONSETID").ic.apply(list)
    spill_rows = []
    if len(spill):
        for r in spill[spill.tier.eq("supported")].itertuples():
            for src in rel_of.get(r.GENCONSETID, []):
                spill_rows.append({"source": NAMES[src], "target": r.target_name, "direction": r.direction, "GENCONSETID": r.GENCONSETID,
                                   "effect_capacity": r.effect_capacity, "ci_lo": r.ci_lo_capacity, "ci_hi": r.ci_hi_capacity})
    spill_sup = pd.DataFrame(spill_rows)
    spill_matrix = (spill_sup.assign(excl0=lambda d: (d.ci_lo > 0) | (d.ci_hi < 0))
                    .groupby(["source", "target", "direction"]).agg(families=("GENCONSETID", "nunique"),
                                                                    median_effect=("effect_capacity", "median"),
                                                                    share_ci_excludes_zero=("excl0", "mean")).reset_index()) if len(spill_sup) else pd.DataFrame()
    placebo = fam[["name", "direction", "GENCONSETID", "episodes", "treated_hours", "match_rate", "effect_capacity",
                   "placebo_effect_capacity", "placebo_ci_lo", "placebo_ci_hi", "placebo_clean", "tier"]]
    eligible = fam[(fam.episodes >= 5) & (fam.treated_hours >= 24) & (fam.match_rate >= .6)]
    placebo_rate = eligible.groupby("name").placebo_clean.mean()

    # family annotations: mechanism-free context — typical asset/substation/area and electrical neighbours
    link = esets.merge(okeys[["OUTAGEID", "primary_asset", "primary_description", "substation_name", "area_label"]], on="OUTAGEID")
    link = link.merge(episodes[["OUTAGEID", "withdrawn"]], on="OUTAGEID")
    link = link[~link.withdrawn]
    top_asset = (link.groupby(["GENCONSETID", "primary_asset"]).OUTAGEID.nunique().rename("n").reset_index()
                 .sort_values(["GENCONSETID", "n"], ascending=[True, False]).drop_duplicates("GENCONSETID")
                 .merge(link.drop_duplicates("primary_asset")[["primary_asset", "primary_description", "substation_name", "area_label"]], on="primary_asset"))
    sup = sup.merge(top_asset.rename(columns={"primary_asset": "typical_asset", "n": "typical_asset_episodes"}), on="GENCONSETID", how="left")
    sup["typical_asset"] = np.where(sup.typical_asset.fillna("").str.startswith("EL"), sup.primary_description, sup.typical_asset)
    near = (k5.assign(a=k5.sensitivity.abs()).sort_values("a", ascending=False).groupby(["ic", "GENCONSETID"])
            .apply(lambda g: "; ".join(f"{d} ({s:+.2f})" for d, s in g.drop_duplicates("DUID")[["DUID", "sensitivity"]].head(4).itertuples(index=False)),
                   include_groups=False).rename("electrically_near").reset_index())
    sup = sup.merge(near, on=["ic", "GENCONSETID"], how="left")

    # ---- downloads
    DL.mkdir(parents=True, exist_ok=True)
    outputs = {
        "nos_outage_episodes.csv.gz": episodes.merge(okeys[["OUTAGEID", "substation_name", "region", "area_label", "location_source", "method", "confidence"]], on="OUTAGEID", how="left"),
        "nos_set_relevance.csv": relevance,
        "nos_state_coverage.csv": cov, "nos_state_regime_summary.csv": state_summary,
        "nos_family_effects.csv": fam, "nos_key_effects.csv.gz": keys_eff, "nos_outage_lookup.csv": lookup,
        "nos_timing_effects.csv": tim, "nos_weather_vre_interaction.csv": inter,
        "nos_leader_transitions.csv": trans, "nos_spillover_supported.csv": spill_sup, "nos_spillover_matrix.csv": spill_matrix,
        "nos_booking_reliability.csv": br, "nos_event_study.csv.gz": ev, "nos_placebo_checks.csv": placebo,
        "nos_booking_states.csv": states, "nos_k5_electrical.csv": k5,
        "nos_substation_crosswalk.csv": pd.read_csv(EXEC / "reference/substation_crosswalk.csv"),
    }
    # derived report tables (S5b extras), shared with the standalone report
    if (DATA / "report_tables").exists():
        rt = {k: pd.read_parquet(DATA / "report_tables" / f"{k}.parquet") for k in ["duid_pressure", "diurnal_48", "footprint", "flow_response"]}
        fr = rt["flow_response"].drop(columns=["effect_at_limit", "treated_at_limit", "control_at_limit", "ci_lo_at_limit", "ci_hi_at_limit"], errors="ignore")
        fr = fr.merge(fam[["ic", "direction", "GENCONSETID", "effect_at_limit", "treated_at_limit", "control_at_limit"]], on=["ic", "direction", "GENCONSETID"], how="left")
        outputs.update({"nos_outage_keys.csv.gz": okeys, "nos_diurnal_profiles_48.csv": rt["diurnal_48"], "nos_flow_response.csv": fr,
                        "nos_duid_pressure.csv": rt["duid_pressure"], "nos_system_footprint.csv": rt["footprint"]})
    for name, frame in outputs.items():
        target = DL / name
        tmp = target.with_name(target.name + ".tmp")
        frame.to_csv(tmp, index=False, compression={"method": "gzip", "mtime": 0} if name.endswith(".gz") else None)
        tmp.replace(target)

    # ---- figures
    figs = []
    c = cov.copy(); c["row"] = c.name + " · " + c.direction.map(DIR_LABEL)
    fig = px.bar(c, y="row", x="share", color="state", orientation="h", category_orders={"state": STATE_ORDER, "row": [f"{n} · {d}" for n in ORDER for d in DIR_LABEL.values()]},
                 color_discrete_map=STATE_COL, labels={"share": "Share of half-hours", "row": "", "state": "Outage state"})
    fig.update_xaxes(tickformat=".0%")
    style_plotly(fig, "How much of the time is each connector in an outage state?", 600); fig.update_layout(hovermode="closest")
    figs.append((fig, "Outage-state coverage by connector direction", "Connector-level state: any relevant family leading > invoked > partially invoked > within a live booking > clear. Unknown = incomplete half-hour.", "nos_state_coverage.csv"))

    for name in connectors:
        s = sup[sup.name.eq(name)].copy()
        if s.empty:
            continue
        s = s.sort_values("effect_capacity")
        s["label"] = s.GENCONSETID
        fig = go.Figure()
        for d, colr in [("forward", "#5696b9"), ("reverse", "#ce9a48")]:
            q = s[s.direction.eq(d)]
            fig.add_trace(go.Scatter(x=q.effect_capacity, y=q.label, mode="markers", name=DIR_LABEL[d], marker=dict(size=9, color=colr),
                                     error_x=dict(type="data", symmetric=False, array=q.ci_hi_capacity - q.effect_capacity,
                                                  arrayminus=q.effect_capacity - q.ci_lo_capacity, thickness=1.2),
                                     customdata=np.stack([q.effect_capacity_pct.fillna(np.nan), q.effect_at_limit, q.episodes, q.treated_hours,
                                                          q.typical_asset.fillna("—"), q.area_label.fillna("—")], axis=1),
                                     hovertemplate="%{y}<br>capacity %{x:+.0f} MW (%{customdata[0]:+.0f}% of seasonal median)<br>at-limit share %{customdata[1]:+.1%}"
                                                   "<br>%{customdata[2]} episodes · %{customdata[3]:.0f} h<br>typical asset %{customdata[4]}<br>%{customdata[5]}<extra></extra>"))
        fig.add_vline(x=0, line_color="#888", line_width=1)
        style_plotly(fig, f"{name}: matched change in directional limit while each supported outage family is invoked", max(420, 26 * s.label.nunique() + 180))
        fig.update_layout(hovermode="closest", xaxis_title="Median matched change in directional limit (MW), 95% day-block bootstrap CI")
        figs.append((fig, f"{name} — supported outage-family effects", "Each point is one constraint-set family in one direction; controls are matched outage-free half-hours (METHODOLOGY §5.2).", "nos_family_effects.csv"))

    t = tim.copy(); t["row"] = t.name + " · " + t.direction.map(DIR_LABEL)
    piv = t.groupby(["row", "day_period"]).capacity_effect.median().unstack().reindex(columns=rr.DAILY_PERIOD_ORDER)
    piv = piv.reindex([r for r in [f"{n} · {d}" for n in ORDER for d in DIR_LABEL.values()] if r in piv.index])
    fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, colorscale="RdBu", zmid=0,
                               text=np.vectorize(lambda v: "—" if pd.isna(v) else f"{v:+.0f}")(piv.values), texttemplate="%{text}",
                               colorbar=dict(title="MW"), hovertemplate="%{y}<br>%{x}<br>median change %{z:+.0f} MW<extra></extra>"))
    style_plotly(fig, "When do outage effects bite? Median matched limit change by daily period", 560); fig.update_layout(hovermode="closest")
    fig.update_yaxes(autorange="reversed")
    figs.append((fig, "Outage effect by daily period (pooled supported families)", "Median of seasonal-period cell medians of matched unit differences.", "nos_timing_effects.csv"))

    i2 = inter.copy(); i2["row"] = i2.name + " · " + i2.direction.map(DIR_LABEL)
    fig = px.bar(i2, x="regime", y="capacity_effect", color="driver", barmode="group", facet_col="row", facet_col_wrap=4,
                 category_orders={"regime": ["low", "normal", "high"], "row": [f"{n} · {d}" for n in ORDER for d in DIR_LABEL.values()]},
                 color_discrete_sequence=["#ce9a48", "#5696b9", "#8370b4"], labels={"capacity_effect": "MW", "regime": "", "driver": "Condition"})
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    style_plotly(fig, "Does weather, VRE or residual demand change the outage effect?", 860); fig.update_layout(hovermode="closest")
    figs.append((fig, "Outage effect by weather / VRE / residual-demand regime", "Regimes are the report's within-connector-season P20/P80 bins at the treated half-hour.", "nos_weather_vre_interaction.csv"))

    fig = px.scatter(sup, x="effect_capacity", y="effect_directional_flow", color="name", symbol="direction", hover_name="GENCONSETID",
                     size=sup.treated_hours.clip(upper=500), size_max=18, category_orders={"name": ORDER},
                     labels={"effect_capacity": "Limit change (MW)", "effect_directional_flow": "Flow change (MW)", "name": "Connector"})
    fig.add_hline(y=0, line_color="#999", line_width=1); fig.add_vline(x=0, line_color="#999", line_width=1)
    fig.add_trace(go.Scatter(x=[-1500, 1500], y=[-1500, 1500], mode="lines", line=dict(dash="dot", color="#aaa"), name="flow follows limit 1:1", hoverinfo="skip"))
    lim = float(np.nanmax(np.abs(sup[["effect_capacity", "effect_directional_flow"]].to_numpy()))) * 1.1 if len(sup) else 100
    fig.update_xaxes(range=[-lim, lim]); fig.update_yaxes(range=[-lim, lim])
    style_plotly(fig, "When the limit moves, does flow follow?", 620); fig.update_layout(hovermode="closest")
    figs.append((fig, "Flow response versus limit response (supported families)", "Points near the dotted line: flow tracks the limit; points on the x-axis: the limit moved but flow did not.", "nos_family_effects.csv"))

    if len(spill_matrix):
        for d in ["forward", "reverse"]:
            m = spill_matrix[spill_matrix.direction.eq(d)].pivot(index="source", columns="target", values="median_effect").reindex(index=ORDER, columns=ORDER)
            n = spill_matrix[spill_matrix.direction.eq(d)].pivot(index="source", columns="target", values="families").reindex(index=ORDER, columns=ORDER)
            fig = go.Figure(go.Heatmap(z=m.values, x=m.columns, y=m.index, colorscale="RdBu", zmid=0, customdata=n.values,
                                       text=np.vectorize(lambda v: "" if pd.isna(v) else f"{v:+.0f}")(m.values), texttemplate="%{text}",
                                       hovertemplate="families relevant to %{y}<br>effect on %{x}: %{z:+.0f} MW<br>%{customdata} supported families<extra></extra>",
                                       colorbar=dict(title="MW")))
            fig.update_yaxes(title="Outage families relevant to …", autorange="reversed"); fig.update_xaxes(title="… measured on (not relevant there)")
            style_plotly(fig, f"Spillover: {DIR_LABEL[d].lower()} limit change on other connectors", 560); fig.update_layout(hovermode="closest")
            figs.append((fig, f"Cross-connector spillover — {DIR_LABEL[d].lower()} direction", "Median matched effect of supported families that are not relevant to the target connector.", "nos_spillover_matrix.csv"))

    e = ev[(ev.scope.eq("pooled_supported")) & ev.clean.fillna(False)].copy() if len(ev) else pd.DataFrame()
    if len(e):
        e["row"] = e.ic.map(NAMES) + " · " + e.direction.map(DIR_LABEL)
        fig = px.line(e, x="offset_h", y="median_rel", color="anchor", facet_col="row", facet_col_wrap=4,
                      labels={"offset_h": "Hours from invocation start / end", "median_rel": "MW vs 7-day baseline", "anchor": "Aligned on"})
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        fig.add_vline(x=0, line_color="#999", line_width=1)
        style_plotly(fig, "Event study: limit relative to same-time 7-day baseline around outage invocations", 820); fig.update_layout(hovermode="closest")
        figs.append((fig, "Invocation start/end event study (supported families, clean spells)", "Clean spells: no other relevant family starts or ends within ±2 h.", "nos_event_study.csv.gz"))

    if len(br):
        b = br.copy(); b["label"] = b.name + " · year " + b.study_year.astype(str)
        fig = go.Figure()
        for col, lab, colr in [("withdrawn_share", "Withdrawn", "#ce9a48"), ("invoked_share", "Live booking → set invoked", "#5696b9"),
                               ("early_return_share", "Returned >1 h early", "#268a87"), ("overrun_share", "Overran >1 h", "#b84444")]:
            fig.add_trace(go.Bar(x=b.label, y=b[col], name=lab, marker_color=colr))
        fig.update_yaxes(tickformat=".0%"); style_plotly(fig, "How reliable are relevant outage bookings?", 520); fig.update_layout(barmode="group", hovermode="closest")
        figs.append((fig, "Booking reliability (bookings listing a relevant family)", "Final-state MMSDM records; both study years shown.", "nos_booking_reliability.csv"))

    pl = placebo[placebo.tier.ne("unsupported") | placebo.placebo_clean.fillna(False)].dropna(subset=["effect_capacity"])
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=fam.effect_capacity.dropna(), name="Actual outage windows", opacity=.65, marker_color="#8370b4", nbinsx=60))
    fig.add_trace(go.Histogram(x=fam.placebo_effect_capacity.dropna(), name="Placebo windows (±7 days)", opacity=.65, marker_color="#9aa3ad", nbinsx=60))
    fig.update_layout(barmode="overlay"); style_plotly(fig, "Falsification: actual versus placebo effect distributions (all families)", 480)
    fig.update_xaxes(title="Median matched limit change (MW)"); fig.update_layout(hovermode="closest")
    figs.append((fig, "Actual vs placebo effects", "A placebo distribution centred on zero and narrower than the actual one indicates the matching removes most timing confounding.", "nos_placebo_checks.csv"))

    # ---- narrative
    n_sup = sup.groupby("name").GENCONSETID.nunique()
    n_rel = relevance[relevance.relevant].groupby("ic").size().rename(index=NAMES)
    body = [START, '<section id="outages"><div class="section-kicker">OUTAGE REGIMES · NOS · SEP 2024–AUG 2026</div>'
            '<h2>What happens to limits and flow when a specific network outage is in place</h2>'
            '<p>This section adds a network-outage dimension to the regime report. AEMO Network Outage Schedule (NOS) bookings are linked to the constraint-set '
            'families they invoke and to the actual invocation record. The equations in those families are checked against the reconstructed envelope '
            'to decide which families are <em>relevant</em> to each connector: a family is relevant only if one of its equations actually set that connector\'s limit while invoked. '
            'Each invoked half-hour is then compared with matched half-hours on the same connector and direction, in the same season, half-hour, day type and weather/VRE/demand regime, '
            'within ±21 days, with the family off and, where possible, the same other outage families in place. Treated half-hours are therefore compared with similar '
            'conditions rather than with an unconditional average. Outages are scheduled for quiet periods, and a raw average would mostly measure that timing.</p>'
            '<p>The window is two years (two blocks of each Australian season), which is shorter than the three-year flow window above. The analysis is retrospective and descriptive: realised '
            'invocations and actual outage times are used, and no forecast feature or fitted model is produced. Limits are dispatch-solution outputs, so an "effect" means a change in the '
            'solved envelope, not in physical transfer capability.</p>']
    body.append('<section class="metrics">' + metric("Outage episodes", f"{len(episodes):,}", "NEM-wide bookings overlapping the window (MMSDM final state)")
                + metric("Relevant families", f"{int(relevance.relevant.sum())}", "connector × constraint-set pairs that set a limit while invoked")
                + metric("Supported families", f"{int(sup.drop_duplicates(['ic','GENCONSETID']).shape[0])}", "pass episodes, hours, match and placebo gates")
                + metric("Lookup assets", f"{lookup[lookup.tier.eq('supported')].asset.nunique():,}", "outage assets with a supported published level") + '</section>')
    # findings
    biggest = sup.loc[sup.effect_capacity.idxmin()] if len(sup) else None
    biggest_up = sup.loc[sup.effect_capacity.idxmax()] if len(sup) else None
    body.append('<div class="findings">')
    if biggest is not None:
        body.append(finding(1, "The largest supported reduction", f"{biggest['GENCONSETID']} on {biggest['name']} {biggest['direction']}: {biggest['effect_capacity']:+,.0f} MW "
                                f"({biggest['effect_capacity_pct']:+.0f}% of the seasonal median) across {int(biggest['episodes'])} episodes and {biggest['treated_hours']:.0f} invoked hours."))
    if biggest_up is not None and biggest_up["effect_capacity"] > 0:
        body.append(finding(2, "Some outage families raise one direction", f"{biggest_up['GENCONSETID']} on {biggest_up['name']} {biggest_up['direction']}: {biggest_up['effect_capacity']:+,.0f} MW. "
                                "Outage sets often re-orient the envelope, tightening one direction while the other is set by a looser equation."))
    fl = sup.dropna(subset=["effect_capacity", "effect_directional_flow"])
    red = fl[fl.effect_capacity < -25]
    if len(red):
        ratio = float((red.effect_directional_flow / red.effect_capacity).clip(-2, 2).median())
        body.append(finding(3, "Flow only partly follows the limit", f"Across {len(red)} supported family-directions whose limit falls by more than 25 MW, the median flow change is {ratio:.0%} of the limit change. "
                                "The rest shows up as lost headroom and more time at the limit."))
    if len(placebo_rate):
        body.append(finding(4, "Placebo test is mostly clean, not perfectly", "Among families that pass the other gates, the ±7-day placebo is clean for "
                                + ", ".join(f"{k} {v:.0%}" for k, v in placebo_rate.reindex(ORDER).dropna().items())
                                + ". Families that fail the placebo are never labelled supported; residual timing confounding remains possible."))
    body.append(finding(5, "Location is specific where the data allows", f"{okeys.substation_name.notna()[~okeys.primary_asset_is_na].mean():.0%} of outage assets resolve to a named substation and "
                            f"{okeys.lat.notna()[~okeys.primary_asset_is_na].mean():.0%} to coordinates and an area label. Nearby generators are listed electrically (equation sensitivity) and geographically (≤50 km)."))
    if len(br):
        y2 = br[br.study_year.eq(2)]
        body.append(finding(6, "Many bookings are withdrawn; live ones return early", f"In year 2, {y2.withdrawn_share.median():.0%} of relevant bookings were withdrawn (median across connectors). "
                                f"Early returns (>1 h, {y2.early_return_share.median():.0%}) are far more common than overruns ({y2.overrun_share.median():.0%}). "
                                f"The {y2.invoked_share.median():.0%} booked-to-invoked rate is close to built in, because final-state records link only the sets that were used."))
    body.append('</div>')

    body.append('<h3>Outage landscape</h3><p>Share of half-hours in each connector-level state. "Leading" means an invoked relevant family\'s equation formed the limit. '
                'VNI and the South Australian links are almost never outage-free by this definition, so the analysis compares individual families (on vs off) rather than '
                'treating "no outage" as the baseline.</p>')
    body.append(figure_html(plot(figs[0][0]), figs[0][1], figs[0][2], "downloads/" + figs[0][3]))
    land = []
    for ic in rr.IC_ORDER:
        if NAMES[ic] not in connectors:
            continue
        cc = cov[cov.ic.eq(ic)].groupby("state").half_hours.sum(); tot = cc.sum()
        land.append({"connector": NAMES[ic], "relevant families": int(n_rel.get(NAMES[ic], 0)), "supported families": int(n_sup.get(NAMES[ic], 0)),
                     "invoked (any relevant)": (cc.get("invoked_nonleading", 0) + cc.get("invoked_leading", 0)) / tot,
                     "outage family leading": cc.get("invoked_leading", 0) / tot, "clear": cc.get("clear", 0) / tot,
                     "placebo clean (eligible)": placebo_rate.get(NAMES[ic], np.nan)})
    land = pd.DataFrame(land)
    body.append(rr.table_html(land, list(land.columns), {c: pct for c in ["invoked (any relevant)", "outage family leading", "clear", "placebo clean (eligible)"]}, 10))

    body.append('<h3>Which outage families move the limit, and by how much?</h3><p>Only supported families are plotted. Each has at least five linked episodes and 24 invoked hours, at least 60% of half-hours matched, '
                'and a ±7-day placebo whose confidence interval includes zero. Hover to see the typical outage asset and its area. The full table, including indicative and unsupported '
                'families and every balance diagnostic, is in the download.</p>')
    for f in figs[1:1 + sum(1 for n in connectors if n in set(sup.name))]:
        body.append(figure_html(plot(f[0]), f[1], f[2], "downloads/" + f[3]))
    top = sup.assign(a=sup.effect_capacity.abs()).sort_values("a", ascending=False).head(40).copy()
    top["limit change (MW)"] = top.effect_capacity.map(fmt_mw) + top.effect_capacity_pct.map(lambda x: "" if pd.isna(x) else f" ({x:+.0f}%)")
    top["95% CI"] = "[" + top.ci_lo_capacity.map(fmt_mw) + ", " + top.ci_hi_capacity.map(fmt_mw) + "]"
    top = top.rename(columns={"name": "connector", "GENCONSETID": "constraint family", "primary_description": "typical outage asset",
                              "area_label": "area", "effect_at_limit": "at-limit share Δ", "effect_directional_flow": "flow Δ (MW)",
                              "treated_hours": "invoked hours", "match_rate": "matched", "lead_share": "family leads", "electrically_near": "electrically near (−b/a)"})
    body.append(rr.table_html(top, ["connector", "direction", "constraint family", "typical outage asset", "area", "limit change (MW)", "95% CI",
                                    "at-limit share Δ", "flow Δ (MW)", "episodes", "invoked hours", "matched", "family leads", "electrically near (−b/a)"],
                              {"at-limit share Δ": lambda x: f"{x:+.1%}", "flow Δ (MW)": fmt_mw, "episodes": lambda x: f"{int(x)}",
                               "invoked hours": lambda x: f"{x:,.0f}", "matched": pct, "family leads": pct}, 40))

    rest = figs[1 + sum(1 for n in connectors if n in set(sup.name)):]
    lookup_by = {f[1]: f for f in rest}

    def fig_by(prefix):
        for k, f in lookup_by.items():
            if k.startswith(prefix):
                return figure_html(plot(f[0]), f[1], f[2], "downloads/" + f[3])
        return ""

    body.append('<h3>Timing and weather</h3><p>Pooling the matched half-hours of supported families shows when outages matter most in the day, and whether they matter more in hot, '
                'high-VRE or high-residual-demand conditions. These are medians of matched differences, split by the condition at the treated half-hour. They are not interaction coefficients.</p>')
    body.append(fig_by("Outage effect by daily period")); body.append(fig_by("Outage effect by weather"))
    body.append('<h3>Flow response and constraint mechanics</h3><p>The limit and the flow are separate outcomes. Flow also depends on regional prices and offers. When an outage cuts '
                'the limit but flow barely changes, the connector simply had spare headroom. When flow falls almost one-for-one, the outage bound dispatch.</p>')
    body.append(fig_by("Flow response"))
    body.append('<p>The table below shows which equation led the envelope before each supported outage run began, and which led during it. The leader-changed share is the fraction of runs in which the outage '
                'replaced the previous leader.</p>')
    tr = trans.merge(sup[["ic", "direction", "GENCONSETID", "effect_capacity"]], on=["ic", "direction", "GENCONSETID"], how="left")
    tr = tr.assign(a=tr.effect_capacity.abs()).sort_values("a", ascending=False).head(25)
    tr["limit change (MW)"] = tr.effect_capacity.map(fmt_mw)
    tr = tr.rename(columns={"name": "connector", "GENCONSETID": "constraint family", "before_top3": "leader before the run (top 3)",
                            "during_top3": "leader during the run (top 3)", "leader_changed_share": "leader changed"})
    body.append(rr.table_html(tr, ["connector", "direction", "constraint family", "limit change (MW)", "leader before the run (top 3)",
                                   "leader during the run (top 3)", "leader changed"], {"leader changed": pct}, 25))
    body.append('<p>The 25 families with the largest limit changes are shown; all supported families are in <code>nos_leader_transitions.csv</code>.</p>')
    body.append('<h3>Spillover to other connectors</h3><p>A family that is relevant to one connector can still move another connector\'s limit through shared network paths, even when none of its equations leads there. '
                'Rows are the connectors where the family is relevant; columns are connectors where it is not relevant but was measured.</p>')
    body.append(fig_by("Cross-connector spillover — forward")); body.append(fig_by("Cross-connector spillover — reverse"))
    body.append('<h3>Onset and recovery</h3><p>Limits are aligned on the start and end of invocation spells and expressed relative to the median at the same half-hour over the previous seven days on which the family was off. '
                'Symmetric start and end curves show a clean switch into and out of the outage configuration.</p>')
    body.append(fig_by("Invocation start/end event study"))
    body.append('<h3>Bookings, unbooked invocations and falsification</h3>')
    body.append(fig_by("Booking reliability"))
    if len(states):
        st = states.groupby(["name", "state"]).agg(families=("GENCONSETID", "nunique"), median_effect=("effect_capacity", "median"),
                                                    median_share_of_invoked=("share_of_invoked", "median")).reset_index()
        off = st[st.state.isin(["booked_only", "withdrawn_booking"]) & st.median_effect.abs().ge(15)]
        flagged = "; ".join(f"{r.name} {r.state.replace('_', ' ')} {r.median_effect:+.0f} MW" for r in off.itertuples())
        body.append('<p>Booked-only and withdrawn-booking windows (family not invoked) should show roughly zero effect, and they act as a second falsification check. '
                    'Unbooked invocations (the family invoked with no live booking within 24 h) are reported separately and are excluded from the family effects above. '
                    + (f'Most booked-only and withdrawn medians are within ±15 MW, but not all: {escape(flagged)}. Other network conditions around booking windows '
                       'therefore still influence some comparisons, so single-family effects of similar size should be read with caution.' if len(off) else
                       'All booked-only and withdrawn medians are within ±15 MW.') + '</p>')
        st = st.rename(columns={"name": "connector", "families": "families", "median_effect": "median limit change (MW)",
                                "median_share_of_invoked": "share of invoked time unbooked"})
        body.append(rr.table_html(st, list(st.columns), {"median limit change (MW)": fmt_mw, "share of invoked time unbooked": pct}, 30))
    body.append(fig_by("Actual vs placebo"))

    # ---- lookup
    lk = lookup[lookup.tier.isin(["supported", "indicative"])].copy()
    lk["effect"] = lk.effect_capacity.map(fmt_mw) + " MW" + lk.effect_capacity_pct.map(lambda x: "" if pd.isna(x) else f" ({x:+.0f}%)")
    lk["ci"] = "[" + lk.ci_lo_capacity.map(fmt_mw) + ", " + lk.ci_hi_capacity.map(fmt_mw) + "]"
    lk["at_limit"] = "—"   # key-level at-limit shares are not stored per unit; see family effects
    lk["flow"] = lk.effect_directional_flow.map(fmt_mw)
    lk["dir"] = lk.direction.map(DIR_LABEL)
    lk = lk.sort_values(["name", "asset", "dir"])
    rows_html = []
    for r in lk.itertuples():
        cls = "tier-ind" if r.tier == "indicative" else ""
        rows_html.append(f'<tr class="{cls}"><td>{escape(r.name)}</td><td>{escape(r.dir)}</td><td><strong>{escape(r.asset)}</strong><br><small>{escape(str(r.asset_description or ""))}'
                         f'{" · " + str(int(r.voltage_kv)) + " kV" if pd.notna(r.voltage_kv) else ""}</small></td>'
                         f'<td>{escape(str(r.substation or "—"))}<br><small>{escape(str(r.area_label or "no coordinates"))}</small></td>'
                         f'<td>{escape(r.published_level)}<br><small>{escape(str(r.published_key))}</small></td><td>{escape(r.effect)}<br><small>{escape(r.ci)}</small></td>'
                         f'<td>{escape(r.at_limit)}</td><td>{escape(r.flow)}</td><td>{int(r.episodes) if pd.notna(r.episodes) else "—"} · {r.treated_hours:,.0f} h</td>'
                         f'<td><small>{escape(str(r.electrically_near or "—"))}</small></td><td><small>{escape(str(r.plants_within_50km or "—"))[:160]}</small></td><td>{escape(r.tier)}</td></tr>')
    body.append('<h3 id="outage-lookup">Specific outage lookup</h3><p>Search by asset (e.g. a line number), substation, area, connector or generator. Each outage asset is published at the most specific level '
                'that passes the support gate, in this order: asset × constraint family, then asset, then constraint family, then substation, then area. The published level is shown with each row, so a row published at '
                '"K3" describes outages at that substation generally, not that single asset. <em>Electrically near</em> lists DUIDs whose output moves the family\'s equations '
                '(sensitivity −b/a). <em>Within 50 km</em> lists named power stations near the substation (OpenStreetMap). Indicative rows are greyed.</p>'
                '<input id="nos-lookup-q" class="lookup-search" type="search" placeholder="Filter: asset, substation, area, connector, DUID…" aria-label="Filter outage lookup" '
                'oninput="(function(q){q=q.toLowerCase();document.querySelectorAll(\'#nos-lookup tbody tr\').forEach(function(r){r.style.display=r.textContent.toLowerCase().indexOf(q)>-1?\'\':\'none\';});})(this.value)">'
                '<div class="table-wrap lookup-wrap" tabindex="0"><table id="nos-lookup" class="data-table"><thead><tr><th>Connector</th><th>Direction</th><th>Asset</th><th>Substation · area</th>'
                '<th>Published level</th><th>Limit change · 95% CI</th><th>At-limit share Δ</th><th>Flow Δ (MW)</th><th>Evidence</th><th>Electrically near</th><th>Within 50 km</th><th>Tier</th></tr></thead><tbody>'
                + "".join(rows_html) + '</tbody></table></div>'
                '<style>.lookup-search{width:100%;max-width:560px;padding:10px 12px;margin:8px 0 12px;border:1px solid #ccd;border-radius:8px;font:inherit}'
                '#nos-lookup tr.tier-ind{opacity:.6}#nos-lookup td small{color:#667}.lookup-wrap{max-height:75vh;overflow:auto}'
                '#nos-lookup thead th{position:sticky;top:0;background:#ececf3;z-index:1}</style>')

    # ---- per-connector stories
    body.append('<h3>Connector notes</h3>')
    for name in connectors:
        s = sup[sup.name.eq(name)]
        ic = [k for k, v in NAMES.items() if v == name][0]
        cc = cov[cov.ic.eq(ic)].groupby("state").half_hours.sum(); tot = cc.sum()
        txt = (f"{name} has {int(n_rel.get(name, 0))} relevant outage families; {int(n_sup.get(name, 0))} pass the support gate. A relevant family is invoked in "
               f"{(cc.get('invoked_nonleading', 0) + cc.get('invoked_leading', 0)) / tot:.0%} of half-hours and leads the limit in {cc.get('invoked_leading', 0) / tot:.0%}. ")
        for d in ["forward", "reverse"]:
            q = s[s.direction.eq(d)].sort_values("effect_capacity")
            if len(q):
                lo = q.iloc[0]
                txt += (f"In the {d} direction the largest supported reduction is {lo.GENCONSETID} ({lo.effect_capacity:+,.0f} MW"
                        f"{', typically ' + str(lo.typical_asset) if pd.notna(lo.typical_asset) else ''}"
                        f"{', ' + str(lo.area_label) if pd.notna(lo.area_label) else ''}). ")
        la = lookup[(lookup.name.eq(name)) & lookup.tier.eq("supported") & lookup.published_level.isin(["K1", "K1xK2"])]
        txt += f"{la.asset.nunique()} individual outage assets have supported asset-level entries in the lookup."
        body.append(f'<p><strong>{escape(name)}.</strong> {escape(txt)}</p>')

    body.append('<p class="callout scope-note"><strong>Limitations.</strong> Outages are scheduled where network operators expect low impact, so these are typical impacts as scheduled. '
                'The set-to-connector mapping and relevance filter are retrospective. Year-1 outage records are final-state only. Substation coordinates come from an OpenStreetMap name crosswalk (medium confidence), and unmatched '
                'substations are left blank. Matching falls back to coarser cells when exact matches are unavailable; the rung shares and balance diagnostics are in the download. '
                'Full definitions are in <a href="METHODOLOGY.md#outage-regimes">METHODOLOGY.md</a> and the '
                'execution record is <code>execution/nos_outage_regime_v1/</code>.</p>')
    body.append('<div class="downloads"><h3>Outage-regime data</h3><ul>' + "".join(f'<li><a href="downloads/{n}" download>{n}</a></li>' for n in outputs) + '</ul></div></section>' + END)
    fragment = "\n".join(body)
    FRAGMENT.parent.mkdir(parents=True, exist_ok=True)
    FRAGMENT.write_text(fragment, encoding="utf-8")
    MD_FRAGMENT.write_text(methodology_md(), encoding="utf-8")
    inject()
    return {"supported_families": int(sup.drop_duplicates(["ic", "GENCONSETID"]).shape[0]), "lookup_rows": len(lk),
            "downloads": list(outputs), "figures": len(figs)}


def methodology_md() -> str:
    return (EXEC / "METHODOLOGY.md").read_text(encoding="utf-8").replace(
        "# Methodology — interconnector limits and flow under NOS outage regimes (v1)",
        '<a id="outage-regimes"></a>\n\n## Outage regimes (NOS) — added 2026-09-24')


def inject(out: Path = REPORT) -> None:
    """Insert (or replace) the cached outage section, nav link and methodology; idempotent."""
    index = out / "index.html"
    html = index.read_text(encoding="utf-8")
    html = re.sub(re.escape(START) + ".*?" + re.escape(END), "", html, flags=re.S)
    html = html.replace(NAV, "")
    frag = FRAGMENT.read_text(encoding="utf-8")
    html = html.replace('<section id="methods">', frag + '<section id="methods">', 1)
    html = html.replace('<a href="#methods">Methods</a>', NAV + '<a href="#methods">Methods</a>', 1)
    index.write_text(html, encoding="utf-8")
    md = out / "METHODOLOGY.md"
    text = md.read_text(encoding="utf-8")
    text = re.sub(re.escape(START) + ".*?" + re.escape(END), "", text, flags=re.S).rstrip() + "\n\n"
    text += START + "\n" + MD_FRAGMENT.read_text(encoding="utf-8") + "\n" + END + "\n"
    md.write_text(text, encoding="utf-8")


def manifest() -> dict:
    v1 = REPORT / "build_manifest_v1.json"
    cur = REPORT / "build_manifest.json"
    if not v1.exists():
        shutil.copy2(cur, v1)
    base = json.loads(v1.read_text(encoding="utf-8"))
    changed, unchanged = [], 0
    for rel, meta in base["outputs"].items():
        p = REPORT / rel
        if rel in ("index.html", "METHODOLOGY.md"):
            continue
        if not p.exists() or rr.digest(p) != meta["sha256"]:
            changed.append(rel)
        else:
            unchanged += 1
    new = dict(base)
    new["version"] = 2
    new["built_at"] = pd.Timestamp.now(tz="Asia/Singapore").isoformat()
    new["previous_manifest"] = "build_manifest_v1.json"
    new["v1_outputs_unchanged"] = unchanged
    new["v1_outputs_changed"] = changed
    inputs = dict(base["inputs"])
    for p in sorted((DATA / "raw" / "mmsdm").glob("*.parquet")) + [DATA / "raw/osm/au_power.json"]:
        inputs[str(p.relative_to(ROOT))] = {"bytes": p.stat().st_size, "sha256": rr.digest(p)}
    for p in sorted(TABLES.glob("*.parquet")) + [DATA / f for f in ["episodes.parquet", "episode_sets.parquet", "outage_keys.parquet", "set_relevance.parquet",
                                                                       "family_coverage_30min.parquet", "k5_electrical.parquet", "invocation_spells.parquet"]]:
        inputs[str(p.relative_to(ROOT))] = {"bytes": p.stat().st_size, "sha256": rr.digest(p)}
    new["inputs"] = inputs
    outputs = {}
    excluded = {"build_manifest.json", "build_manifest_v1.json", "finalization_status.json", "constraint_duid_regime_matrix.csv",
                "constraint_family_summary.csv", "regime_scatter_sample.csv"}
    for p in sorted(REPORT.rglob("*")):
        if p.is_file() and p.name not in excluded:
            outputs[str(p.relative_to(REPORT))] = {"bytes": p.stat().st_size, "sha256": rr.digest(p)}
    new["outputs"] = outputs
    new["nos_outage_regime"] = {"execution": "execution/nos_outage_regime_v1", "section_builder": "python scripts/build_nos_regime_section.py",
                                "window": "(2024-09-01, 2026-09-01]", "osm_snapshot": json.loads((DATA / "raw/osm/au_power.json").read_text(encoding="utf-8"))["osm3s"]["timestamp_osm_base"]}
    new["rebuild"] = "python scripts/build_all_ic_regime_report.py && python scripts/build_nos_regime_section.py"
    cur.write_text(json.dumps(new, indent=2, default=str), encoding="utf-8")
    return {"v1_unchanged": unchanged, "v1_changed": changed, "outputs": len(outputs)}


if __name__ == "__main__":
    result = build()
    result["manifest"] = manifest()
    print(json.dumps(result, indent=1, default=str))
