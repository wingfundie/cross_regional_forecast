"""Standalone editorial report: interconnector limits and flow under NOS outage regimes (all six links).

Presentation only — renders cached outputs of execution/nos_outage_regime_v1 (data/nos_regime_v1/tables and
report_tables). No matching or model is re-run.

    python scripts/build_nos_outage_report.py
"""
from __future__ import annotations

import json
import shutil
import sys
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT, ROOT / "scripts", ROOT / "scripts" / "report_theme"]:
    sys.path.insert(0, str(p))

import build_all_ic_regime_report as rr  # noqa: E402
import build_nos_constraint_chapter as cm  # noqa: E402
import build_nos_regime_section as sec  # noqa: E402
from report_theme import VERSION, figure_html, finding, hero, metric, render_page, style_plotly  # noqa: E402

from nemic.experiments.nos_regime.common import DATA, EXEC  # noqa: E402
from nemic.experiments.nos_regime.lookup import build_lookup  # noqa: E402

REPORT_ID = "nos_outage_regime_research_20260924"
OUT = ROOT / "reports" / REPORT_ID
DL = OUT / "downloads"
RT = DATA / "report_tables"
NAMES = rr.IC_NAMES
ORDER = [NAMES[i] for i in rr.IC_ORDER]
ROWS12 = [f"{n} · {d}" for n in ORDER for d in ("Forward", "Reverse")]
DIRL = {"forward": "Forward", "reverse": "Reverse"}
IC_COL = {"QNI": "#5696b9", "Directlink": "#8fb9d3", "VNI": "#ce9a48", "Heywood": "#8370b4", "Murraylink": "#b5a7d8", "Basslink": "#268a87"}
fmt_mw, pct, table = sec.fmt_mw, sec.pct, rr.table_html


def safe_replace(tmp, target, attempts: int = 20) -> None:
    """os.replace with retries: on this host the search indexer briefly locks freshly written report files."""
    import time
    for i in range(attempts):
        try:
            tmp.replace(target)
            return
        except (PermissionError, OSError):
            if i == attempts - 1:
                raise
            time.sleep(1.0)


def plot(fig):
    return rr.plot_div(fig)


def fig_block(fig, caption, note, href):
    return figure_html(plot(fig), caption, note, f"downloads/{href}" if href else None)


def rowlab(df):
    return df.name + " · " + df.direction.map(DIRL)


def pp(x):
    return "—" if pd.isna(x) else f"{x * 100:+.1f} pp"


# ============================================================================ data
def load_all():
    d = {}
    for k in ["family_effects", "key_effects", "states", "spillover", "event_study", "units", "state_panel"]:
        d[k] = sec.load(k)
    d["br"] = pd.concat([pd.read_parquet(p) for p in (DATA / "tables").glob("booking_reliability__*.parquet")]).drop_duplicates(["ic", "study_year"], keep="last")
    for k in ["set_relevance", "k5_electrical", "outage_keys", "episodes", "episode_sets", "invocation_spells"]:
        d[k] = pd.read_parquet(DATA / f"{k}.parquet")
    for k in ["duid_pressure", "diurnal_48", "footprint", "flow_response"]:
        d[k] = pd.read_parquet(RT / f"{k}.parquet")
    d["crosswalk"] = pd.read_csv(EXEC / "reference/substation_crosswalk.csv")
    d["log"] = [json.loads(x) for x in (EXEC / "execution_log.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    return d


def derive(d):
    fam = sec.at_limit_shares(d["family_effects"], d["units"])
    fr = d["flow_response"].drop(columns=["effect_at_limit", "treated_at_limit", "control_at_limit", "ci_lo_at_limit", "ci_hi_at_limit"], errors="ignore")
    d["flow_response"] = fr.merge(fam[["ic", "direction", "GENCONSETID", "effect_at_limit", "treated_at_limit", "control_at_limit"]], on=["ic", "direction", "GENCONSETID"], how="left")
    sup = fam[fam.tier.eq("supported")].copy()
    esets, okeys, eps = d["episode_sets"], d["outage_keys"], d["episodes"]
    link = esets.merge(okeys[["OUTAGEID", "primary_asset", "primary_description", "substation_name", "area_label", "region"]], on="OUTAGEID")
    link = link.merge(eps[["OUTAGEID", "withdrawn"]], on="OUTAGEID")
    link = link[~link.withdrawn]
    top_asset = (link.groupby(["GENCONSETID", "primary_asset"]).OUTAGEID.nunique().rename("n").reset_index()
                 .sort_values(["GENCONSETID", "n"], ascending=[True, False]).drop_duplicates("GENCONSETID")
                 .merge(link.drop_duplicates("primary_asset")[["primary_asset", "primary_description", "substation_name", "area_label", "region"]], on="primary_asset"))
    top_asset["typical_asset"] = np.where(top_asset.primary_asset.str.startswith("EL"), top_asset.primary_description, top_asset.primary_asset)
    fam = fam.merge(top_asset[["GENCONSETID", "typical_asset", "primary_description", "substation_name", "area_label", "region"]], on="GENCONSETID", how="left")
    k5 = d["k5_electrical"]
    near = (k5.assign(a=k5.sensitivity.abs()).sort_values("a", ascending=False).groupby(["ic", "GENCONSETID"])
            .apply(lambda g: "; ".join(f"{u} ({s:+.2f})" for u, s in g.drop_duplicates("DUID")[["DUID", "sensitivity"]].head(4).itertuples(index=False)),
                   include_groups=False).rename("electrically_near").reset_index())
    fam = fam.merge(near, on=["ic", "GENCONSETID"], how="left")
    d["family_effects"] = fam
    d["sup"] = fam[fam.tier.eq("supported")].copy()
    ke = d["key_effects"]
    d["lookup"] = build_lookup(ke[ke.level.ne("K2")], fam, okeys, esets, d["set_relevance"], k5)
    d["lookup"]["name"] = d["lookup"].ic.map(NAMES)
    panel = d["state_panel"]
    cov = panel.groupby(["ic", "direction", "state"]).size().rename("half_hours").reset_index()
    cov["share"] = cov.half_hours / cov.groupby(["ic", "direction"]).half_hours.transform("sum")
    cov["name"] = cov.ic.map(NAMES)
    d["coverage"] = cov
    d["state_summary"] = (panel[panel.state.ne("unknown")].groupby(["ic", "direction", "state"])
                          .agg(half_hours=("capacity", "size"), capacity_p10=("capacity", lambda s: s.quantile(.1)), capacity_median=("capacity", "median"),
                               capacity_p90=("capacity", lambda s: s.quantile(.9)), flow_median=("directional_flow", "median"),
                               headroom_median=("headroom", "median"), at_limit_share=("at_limit", "mean"), restricted_share=("restricted", "mean")).reset_index())
    d["state_summary"]["name"] = d["state_summary"].ic.map(NAMES)
    units_sup = d["units"].merge(d["sup"][["ic", "direction", "GENCONSETID"]], on=["ic", "direction", "GENCONSETID"])
    d["timing"] = sec.timing(units_sup)
    d["interaction"] = sec.interaction(units_sup)
    d["transitions"] = sec.leader_transitions(d["units"], d["sup"])
    rel = d["set_relevance"]
    d["rel_of"] = rel[rel.relevant].groupby("GENCONSETID").name.agg(lambda s: sorted(set(s)))
    elig = fam[(fam.episodes >= 5) & (fam.treated_hours >= 24) & (fam.match_rate >= .6)]
    d["placebo_rate"] = elig.groupby("name").placebo_clean.mean()
    return d


# ============================================================================ figures
def fig_landscape(d):
    eps = d["episodes"].merge(d["outage_keys"][["OUTAGEID", "region"]], on="OUTAGEID", how="left")
    live = eps[~eps.withdrawn].copy()
    live["month"] = live.start.clip(lower=pd.Timestamp("2024-09-01")).dt.to_period("M").dt.to_timestamp()
    live = live[live.month < pd.Timestamp("2026-09-01")]
    m = live.groupby(["month", "region"]).size().rename("episodes").reset_index()
    fig = px.bar(m, x="month", y="episodes", color="region", category_orders={"region": ["QLD1", "NSW1", "VIC1", "SA1", "TAS1"]},
                 color_discrete_sequence=["#5696b9", "#ce9a48", "#8370b4", "#66717e", "#268a87"], labels={"month": "", "episodes": "Live outage episodes starting", "region": "Region"})
    style_plotly(fig, "Network outages starting each month, by region (withdrawn bookings excluded)", 500)
    t = eps.groupby(["primary_equipment_type_used", "withdrawn"]).size().rename("episodes").reset_index()
    t["status"] = np.where(t.withdrawn, "withdrawn", "live")
    fig2 = px.bar(t, y="primary_equipment_type_used", x="episodes", color="status", orientation="h", barmode="stack",
                  color_discrete_map={"live": "#5696b9", "withdrawn": "#d9c7a3"}, labels={"primary_equipment_type_used": "", "episodes": "Episodes"})
    fig2.update_yaxes(categoryorder="total ascending")
    style_plotly(fig2, "Primary outage equipment type", 480); fig2.update_layout(hovermode="closest")
    return fig, fig2


def fig_relevance(d):
    fam = d["family_effects"].drop_duplicates(["ic", "GENCONSETID", "tier"])
    best = fam.assign(r=fam.tier.map({"supported": 0, "indicative": 1, "unsupported": 2})).sort_values("r").drop_duplicates(["ic", "GENCONSETID"])
    c = best.groupby(["name", "tier"]).size().rename("families").reset_index()
    fig = px.bar(c, x="name", y="families", color="tier", category_orders={"name": ORDER, "tier": ["supported", "indicative", "unsupported"]},
                 color_discrete_map={"supported": "#268a87", "indicative": "#ce9a48", "unsupported": "#c5cad3"}, labels={"name": "", "families": "Relevant constraint-set families"})
    style_plotly(fig, "Relevant outage families per connector and how many pass the evidence gates", 480); fig.update_layout(hovermode="closest")
    return fig


def fig_coverage(d):
    c = d["coverage"].copy(); c["row"] = rowlab(c)
    fig = px.bar(c, y="row", x="share", color="state", orientation="h", category_orders={"state": sec.STATE_ORDER, "row": ROWS12},
                 color_discrete_map=sec.STATE_COL, labels={"share": "Share of half-hours", "row": "", "state": "Connector state"})
    fig.update_xaxes(tickformat=".0%")
    style_plotly(fig, "How much of the time is each link operating under an outage configuration?", 620); fig.update_layout(hovermode="closest")
    return fig


def fig_forest(sup, name):
    s = sup[sup.name.eq(name)].sort_values("effect_capacity")
    fig = go.Figure()
    for dname, colr in [("forward", "#5696b9"), ("reverse", "#ce9a48")]:
        q = s[s.direction.eq(dname)]
        if q.empty:
            continue
        fig.add_trace(go.Scatter(x=q.effect_capacity, y=q.GENCONSETID, mode="markers", name=DIRL[dname], marker=dict(size=9, color=colr),
                                 error_x=dict(type="data", symmetric=False, array=q.ci_hi_capacity - q.effect_capacity, arrayminus=q.effect_capacity - q.ci_lo_capacity, thickness=1.2),
                                 customdata=np.stack([q.effect_capacity_pct, q.effect_at_limit, q.episodes, q.treated_hours, q.typical_asset.fillna("—"), q.area_label.fillna("—")], axis=1),
                                 hovertemplate="%{y}<br>limit %{x:+.0f} MW (%{customdata[0]:+.0f}% of seasonal median)<br>at-limit share %{customdata[1]:+.1%}"
                                               "<br>%{customdata[2]} episodes · %{customdata[3]:.0f} h<br>typical asset: %{customdata[4]}<br>%{customdata[5]}<extra></extra>"))
    fig.add_vline(x=0, line_color="#888", line_width=1)
    style_plotly(fig, f"{name}: matched change in directional limit while each supported outage family is invoked", max(440, 26 * s.GENCONSETID.nunique() + 190))
    fig.update_layout(hovermode="closest", xaxis_title="Median matched limit change (MW) with 95% day-block bootstrap CI")
    return fig


def fig_diurnal(d):
    di = d["diurnal_48"]; a = di[di.season.eq("All")].copy(); a["row"] = rowlab(a)
    fig = make_subplots(rows=3, cols=4, subplot_titles=ROWS12, shared_xaxes=True, vertical_spacing=.09, horizontal_spacing=.05)
    for i, r in enumerate(ROWS12):
        q = a[a.row.eq(r)].sort_values("half_hour")
        rr_, cc = i // 4 + 1, i % 4 + 1
        fig.add_trace(go.Scatter(x=q.clock, y=q.control_capacity, name="Matched control limit", line=dict(color="#9aa3ad"), showlegend=i == 0, legendgroup="c"), rr_, cc)
        fig.add_trace(go.Scatter(x=q.clock, y=q.treated_capacity, name="Limit with outage family invoked", line=dict(color="#8370b4"), showlegend=i == 0, legendgroup="t"), rr_, cc)
    fig.update_xaxes(tickvals=["00:00", "06:00", "12:00", "18:00"])
    style_plotly(fig, "Median directional limit by half-hour: outage family invoked vs matched control (supported families pooled)", 900)
    fig.update_layout(hovermode="closest")
    return fig


def fig_period_heat(d):
    t = d["timing"].copy(); t["row"] = rowlab(t)
    piv = t.groupby(["row", "day_period"]).capacity_effect.median().unstack().reindex(columns=rr.DAILY_PERIOD_ORDER).reindex([r for r in ROWS12])
    fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, colorscale="RdBu", zmid=0, colorbar=dict(title="MW"),
                               text=np.vectorize(lambda v: "—" if pd.isna(v) else f"{v:+.0f}")(piv.values), texttemplate="%{text}",
                               hovertemplate="%{y}<br>%{x}<br>median change %{z:+.0f} MW<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    style_plotly(fig, "When do outage effects bite? Median matched limit change by daily period", 600); fig.update_layout(hovermode="closest")
    return fig


def fig_season_heat(d):
    t = d["timing"].copy(); t["row"] = rowlab(t)
    piv = t.groupby(["row", "season"]).capacity_effect.median().unstack().reindex(columns=rr.SEASON_ORDER).reindex(ROWS12)
    fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, colorscale="RdBu", zmid=0, colorbar=dict(title="MW"),
                               text=np.vectorize(lambda v: "—" if pd.isna(v) else f"{v:+.0f}")(piv.values), texttemplate="%{text}",
                               hovertemplate="%{y}<br>%{x}<br>median change %{z:+.0f} MW<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    style_plotly(fig, "Median matched limit change by Australian season", 600); fig.update_layout(hovermode="closest")
    return fig


def fig_interaction(d):
    i2 = d["interaction"].copy(); i2["row"] = rowlab(i2)
    fig = px.bar(i2, x="regime", y="capacity_effect", color="driver", barmode="group", facet_col="row", facet_col_wrap=4,
                 category_orders={"regime": ["low", "normal", "high"], "row": ROWS12}, color_discrete_sequence=["#ce9a48", "#5696b9", "#8370b4"],
                 labels={"capacity_effect": "MW", "regime": "", "driver": "Condition"})
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    style_plotly(fig, "Does temperature, VRE or residual demand change the outage effect?", 880); fig.update_layout(hovermode="closest")
    return fig


def fig_flow(d):
    s = d["sup"]
    fig = px.scatter(s, x="effect_capacity", y="effect_directional_flow", color="name", symbol="direction", hover_name="GENCONSETID",
                     size=s.treated_hours.clip(upper=500), size_max=18, category_orders={"name": ORDER}, color_discrete_map=IC_COL,
                     labels={"effect_capacity": "Limit change (MW)", "effect_directional_flow": "Flow change (MW)", "name": "Connector"})
    lim = float(np.nanmax(np.abs(s[["effect_capacity", "effect_directional_flow"]].to_numpy()))) * 1.1
    fig.add_trace(go.Scatter(x=[-lim, lim], y=[-lim, lim], mode="lines", line=dict(dash="dot", color="#aaa"), name="flow follows limit 1:1", hoverinfo="skip"))
    fig.add_hline(y=0, line_color="#999", line_width=1); fig.add_vline(x=0, line_color="#999", line_width=1)
    fig.update_xaxes(range=[-lim, lim]); fig.update_yaxes(range=[-lim, lim])
    style_plotly(fig, "When the limit moves, does flow follow?", 640); fig.update_layout(hovermode="closest")
    fr = d["flow_response"].dropna(subset=["flow_pass_through"])
    g = fr.groupby("name").agg(pass_through=("flow_pass_through", "median"), headroom=("headroom_absorbed", "median"), n=("flow_pass_through", "size")).reindex(ORDER).dropna(how="all").reset_index()
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=g.name, y=g.pass_through, name="Flow change ÷ limit change", marker_color="#5696b9", customdata=g.n,
                          hovertemplate="%{x}<br>flow pass-through %{y:.2f}<br>%{customdata} family-directions<extra></extra>"))
    fig2.add_trace(go.Bar(x=g.name, y=g.headroom, name="Headroom change ÷ limit change", marker_color="#ce9a48", customdata=g.n,
                          hovertemplate="%{x}<br>headroom share %{y:.2f}<br>%{customdata} family-directions<extra></extra>"))
    style_plotly(fig2, "How a limit change is absorbed (median across supported family-directions, |ΔLimit| > 25 MW)", 480)
    fig2.update_layout(barmode="group", hovermode="closest")
    return fig, fig2


def fig_spill(d):
    figs = []
    fp = d["footprint"]; sp = fp[fp.relation.str.startswith("not") & fp.tier.eq("supported")]
    rows = []
    for r in sp.itertuples():
        for src in d["rel_of"].get(r.GENCONSETID, []):
            rows.append({"source": src, "target": r.name, "direction": r.direction, "GENCONSETID": r.GENCONSETID, "effect": r.effect_capacity, "excl0": r.ci_excludes_zero})
    m = pd.DataFrame(rows)
    for dname in ["forward", "reverse"]:
        q = m[m.direction.eq(dname)]
        z = q.groupby(["source", "target"]).effect.median().unstack().reindex(index=ORDER, columns=ORDER)
        n = q.groupby(["source", "target"]).GENCONSETID.nunique().unstack().reindex(index=ORDER, columns=ORDER)
        e = q.groupby(["source", "target"]).excl0.mean().unstack().reindex(index=ORDER, columns=ORDER)
        fig = go.Figure(go.Heatmap(z=z.values, x=z.columns, y=z.index, colorscale="RdBu", zmid=0, customdata=np.dstack([n.values, e.values]),
                                   text=np.vectorize(lambda v: "" if pd.isna(v) else f"{v:+.0f}")(z.values), texttemplate="%{text}", colorbar=dict(title="MW"),
                                   hovertemplate="families relevant to %{y}<br>measured on %{x}: %{z:+.0f} MW median<br>%{customdata[0]} supported families; %{customdata[1]:.0%} with CI excluding 0<extra></extra>"))
        fig.update_yaxes(title="Outage families relevant to …", autorange="reversed"); fig.update_xaxes(title="… measured on (family not relevant there)")
        style_plotly(fig, f"Spillover matrix — {dname} limit", 560); fig.update_layout(hovermode="closest")
        figs.append(fig)
    return figs, m


def fig_footprint(d):
    fp = d["footprint"].copy(); fp["row"] = rowlab(fp)
    sup_rel = d["sup"].assign(a=d["sup"].effect_capacity.abs()).sort_values("a", ascending=False)
    fams = list(dict.fromkeys(sup_rel.GENCONSETID))[:32]
    q = fp[fp.GENCONSETID.isin(fams)]
    z = q.pivot_table(index="GENCONSETID", columns="row", values="effect_capacity", aggfunc="first").reindex(index=fams, columns=ROWS12)
    tier = q.pivot_table(index="GENCONSETID", columns="row", values="tier", aggfunc="first").reindex(index=fams, columns=ROWS12)
    relation = q.pivot_table(index="GENCONSETID", columns="row", values="relation", aggfunc="first").reindex(index=fams, columns=ROWS12)
    zs = z.where(tier.eq("supported"))
    txt = np.where(tier.eq("supported").values, np.vectorize(lambda v: "" if pd.isna(v) else f"{v:+.0f}")(z.values), "")
    fig = go.Figure(go.Heatmap(z=zs.values, x=zs.columns, y=zs.index, colorscale="RdBu", zmid=0, zmin=-400, zmax=400, colorbar=dict(title="MW"),
                               customdata=np.dstack([z.values, tier.fillna("not measured").values, relation.fillna("—").values]), text=txt, texttemplate="%{text}",
                               hovertemplate="%{y} on %{x}<br>%{customdata[0]:+.0f} MW (%{customdata[1]}; %{customdata[2]})<extra></extra>"))
    fig.update_yaxes(autorange="reversed"); fig.update_xaxes(tickangle=-35)
    style_plotly(fig, "System footprint: each outage family's matched limit change on every link (supported cells shown)", 1000)
    fig.update_layout(hovermode="closest", margin=dict(l=190, r=35, t=120, b=120))
    return fig


def fig_duid(d):
    dp = d["duid_pressure"]
    g = dp.groupby(["name", "DUID"]).excess_tightening.sum().reset_index()
    g = g.sort_values("excess_tightening", ascending=False).groupby("name").head(8)
    fig = px.bar(g, x="excess_tightening", y="DUID", color="name", facet_col="name", facet_col_wrap=3, orientation="h",
                 category_orders={"name": ORDER}, color_discrete_map=IC_COL, labels={"excess_tightening": "Excess tightening MW per half-hour (summed over families)", "DUID": ""})
    fig.update_yaxes(matches=None, showticklabels=True, categoryorder="total ascending")
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    style_plotly(fig, "Which generators push the envelope harder while outage families are invoked?", 820)
    fig.update_layout(hovermode="closest", showlegend=False)
    return fig


def fig_events(d):
    ev = d["event_study"]
    e = ev[ev.scope.eq("pooled_supported") & ev.clean.fillna(False)].copy()
    e["row"] = e.ic.map(NAMES) + " · " + e.direction.map(DIRL)
    fig = px.line(e, x="offset_h", y="median_rel", color="anchor", facet_col="row", facet_col_wrap=4, category_orders={"row": ROWS12},
                  color_discrete_map={"start": "#8370b4", "end": "#ce9a48"}, labels={"offset_h": "Hours from invocation start / end", "median_rel": "MW vs 7-day baseline", "anchor": "Aligned on"})
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    fig.add_vline(x=0, line_color="#999", line_width=1)
    style_plotly(fig, "Onset and recovery around outage-family invocations (clean spells)", 860); fig.update_layout(hovermode="closest")
    return fig


def fig_map(d):
    lk = d["lookup"]; xw = d["crosswalk"]
    s = lk[lk.tier.eq("supported") & lk.published_level.isin(["K1", "K1xK2", "K3"])].copy()
    s = s.merge(d["outage_keys"].drop_duplicates("primary_asset")[["primary_asset", "primary_substationid"]], left_on="asset", right_on="primary_asset", how="left")
    s = s.merge(xw[["SUBSTATIONID", "lat", "lon", "substation_name"]].rename(columns={"substation_name": "sname"}), left_on="primary_substationid", right_on="SUBSTATIONID", how="inner")
    s = s.assign(a=s.effect_capacity.abs()).sort_values("a", ascending=False).drop_duplicates(["SUBSTATIONID", "name"])
    fig = px.scatter(s, x="lon", y="lat", color="name", size=s.a.clip(lower=5, upper=500), size_max=24, hover_name="sname",
                     category_orders={"name": ORDER}, color_discrete_map=IC_COL,
                     hover_data={"asset": True, "direction": True, "effect_capacity": ":+.0f", "published_level": True, "lon": False, "lat": False},
                     labels={"lon": "Longitude", "lat": "Latitude", "name": "Connector affected"})
    fig.update_yaxes(scaleanchor="x", scaleratio=1.2)
    style_plotly(fig, "Where are the outages that move interconnector limits? (supported asset/substation entries)", 760); fig.update_layout(hovermode="closest")
    return fig, len(s)


def fig_booking(d):
    b = d["br"].copy(); b["label"] = b.name + " · Y" + b.study_year.astype(str)
    b = b.set_index("name").loc[[n for n in ORDER if n in set(b.name)]].reset_index()
    fig = go.Figure()
    for col, lab, colr in [("withdrawn_share", "Withdrawn", "#ce9a48"), ("early_return_share", "Returned >1 h early", "#268a87"), ("overrun_share", "Overran >1 h", "#b84444")]:
        fig.add_trace(go.Bar(x=b.label, y=b[col], name=lab, marker_color=colr))
    fig.update_yaxes(tickformat=".0%"); style_plotly(fig, "Booking outcomes for outages that list a relevant family", 500); fig.update_layout(barmode="group", hovermode="closest")
    return fig


def fig_robust(d):
    fam = d["family_effects"]
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=fam.effect_capacity.dropna(), name="Actual outage windows", opacity=.65, marker_color="#8370b4", nbinsx=70))
    fig.add_trace(go.Histogram(x=fam.placebo_effect_capacity.dropna(), name="Placebo windows (±7 days)", opacity=.65, marker_color="#9aa3ad", nbinsx=70))
    fig.update_layout(barmode="overlay"); fig.update_xaxes(title="Median matched limit change (MW)", range=[-800, 600])
    style_plotly(fig, "Actual versus placebo effect distributions (all evaluated family-directions)", 480); fig.update_layout(hovermode="closest")
    m = fam[fam.n_matched > 0].groupby("name")[["share_exact", "share_count", "share_coarse"]].mean().reindex(ORDER).reset_index()
    fig2 = go.Figure()
    for col, lab, colr in [("share_exact", "Exact (same other-outage set)", "#268a87"), ("share_count", "Same other-outage count", "#5696b9"), ("share_coarse", "Coarse cell", "#ce9a48")]:
        fig2.add_trace(go.Bar(x=m.name, y=m[col], name=lab, marker_color=colr))
    fig2.update_yaxes(tickformat=".0%"); style_plotly(fig2, "Which matching rung found the controls? (mean share across families)", 460)
    fig2.update_layout(barmode="stack", hovermode="closest")
    sm = fam[fam.tier.eq("supported")]
    long = pd.concat([pd.DataFrame({"covariate": c.replace("_", " "), "stage": st, "abs_smd": sm[f"smd_{st}_{c}"].abs()})
                      for c in sec_balance() for st in ["before", "after"]])
    fig3 = px.box(long, x="covariate", y="abs_smd", color="stage", color_discrete_map={"before": "#c5cad3", "after": "#268a87"}, points=False,
                  labels={"abs_smd": "|standardised mean difference|", "covariate": ""})
    fig3.add_hline(y=.1, line_dash="dot", line_color="#b84444")
    style_plotly(fig3, "Covariate balance before and after matching (supported families)", 480); fig3.update_layout(hovermode="closest")
    return fig, fig2, fig3


def sec_balance():
    return ["temperature_mean", "vre_difference", "residual_difference", "half_hour", "other_count"]


# ============================================================================ narrative helpers
def connector_chapter(d, name, figs_forest):
    ic = [k for k, v in NAMES.items() if v == name][0]
    fam, sup, cov = d["family_effects"], d["sup"], d["coverage"]
    s = sup[sup.name.eq(name)]
    f_all = fam[fam.name.eq(name)]
    cc = cov[cov.ic.eq(ic)].groupby("state").half_hours.sum(); tot = cc.sum()
    inv = (cc.get("invoked_nonleading", 0) + cc.get("invoked_leading", 0)) / tot
    lead = cc.get("invoked_leading", 0) / tot
    src, snk = rr.IC[ic]["source"], rr.IC[ic]["sink"]
    di = d["diurnal_48"]; a = di[(di.season.eq("All")) & di.name.eq(name)]
    lines = [f'<section class="connector-section" id="c-{name.lower()}"><div class="section-kicker">CONNECTOR CHAPTER · {escape(src)} ↔ {escape(snk)}</div>'
             f'<h2>{escape(name)}</h2>']
    p1 = (f"{name} has {f_all.GENCONSETID.nunique()} relevant outage families, meaning families whose equations set its limit while invoked; "
          f"{s.GENCONSETID.nunique()} pass every evidence gate in at least one direction. At least one relevant family is fully invoked in {inv:.0%} of half-hours, "
          f"and one of them forms the limit in {lead:.0%}. ")
    if len(a):
        for dname in ["forward", "reverse"]:
            q = a[a.direction.eq(dname)]
            if len(q):
                lo = q.loc[q.capacity_effect.idxmin()]
                p1 += (f"Pooled across supported families, the {dname} limit is a median {q.capacity_effect.median():+.0f} MW different from matched controls, "
                       f"with the deepest half-hour at {lo.clock} ({lo.capacity_effect:+.0f} MW). ")
    lines.append(f"<p>{escape(p1)}</p>")
    p2 = ""
    for dname in ["forward", "reverse"]:
        q = s[s.direction.eq(dname)].sort_values("effect_capacity")
        if len(q):
            lo = q.iloc[0]; hi = q.iloc[-1]
            p2 += (f"In the {dname} direction the largest supported reduction comes from {lo.GENCONSETID} ({lo.effect_capacity:+,.0f} MW, 95% CI "
                   f"{lo.ci_lo_capacity:+,.0f} to {lo.ci_hi_capacity:+,.0f}; {int(lo.episodes)} episodes, {lo.treated_hours:,.0f} h)"
                   f"{', typically ' + str(lo.typical_asset) if pd.notna(lo.typical_asset) else ''}{' — ' + str(lo.area_label) if pd.notna(lo.area_label) else ''}. ")
            if hi.effect_capacity > 25:
                p2 += f"The largest increase is {hi.GENCONSETID} ({hi.effect_capacity:+,.0f} MW), consistent with the outage re-orienting which equation binds. "
    fr = d["flow_response"]; q = fr[fr.name.eq(name)].dropna(subset=["flow_pass_through"])
    if len(q):
        p2 += (f"Across {len(q)} supported family-directions with a limit change above 25 MW, the median flow pass-through is {q.flow_pass_through.median():.2f}: "
               f"{'most of the change is absorbed as headroom, so flow was usually not held against the limit' if q.flow_pass_through.median() < .4 else 'flow largely follows the limit, so these outages bind dispatch'}.")
    lines.append(f"<p>{escape(p2)}</p>")
    if name in figs_forest:
        lines.append(fig_block(figs_forest[name], f"{name} — supported outage-family effects", "Median of matched half-hour differences; bars are 95% day-block bootstrap CIs. Hover shows typical asset and area.", "nos_family_effects.csv"))
    top = s.assign(a=s.effect_capacity.abs()).sort_values("a", ascending=False).head(12).copy()
    if len(top):
        top["limit change"] = top.effect_capacity.map(fmt_mw) + top.effect_capacity_pct.map(lambda x: "" if pd.isna(x) else f" ({x:+.0f}%)")
        top["95% CI"] = "[" + top.ci_lo_capacity.map(fmt_mw) + ", " + top.ci_hi_capacity.map(fmt_mw) + "]"
        top = top.rename(columns={"GENCONSETID": "family", "typical_asset": "typical asset", "area_label": "area", "effect_at_limit": "at-limit Δ",
                                  "effect_directional_flow": "flow Δ", "treated_hours": "hours", "lead_share": "family leads", "electrically_near": "electrically near (−b/a)"})
        lines.append(table(top, ["direction", "family", "typical asset", "area", "limit change", "95% CI", "at-limit Δ", "flow Δ", "episodes", "hours", "family leads", "electrically near (−b/a)"],
                           {"at-limit Δ": pp, "flow Δ": fmt_mw, "episodes": lambda x: f"{int(x)}", "hours": lambda x: f"{x:,.0f}", "family leads": pct}, 12))
    dp = d["duid_pressure"]; g = dp[dp.name.eq(name)].groupby("DUID")[["excess_tightening", "excess_relief"]].sum().sort_values("excess_tightening", ascending=False).head(5)
    sp = d["footprint"]; sp = sp[sp.relation.str.startswith("not") & sp.tier.eq("supported")]
    recv = sp[sp.name.eq(name)]
    sent = sp[sp.GENCONSETID.isin(set(s.GENCONSETID)) & sp.name.ne(name)]
    p3 = ""
    if len(g):
        p3 += "Generators applying the most extra tightening while its supported outage families are invoked: " + ", ".join(f"{u} ({r.excess_tightening:+.0f} MW/half-hour)" for u, r in g.iterrows()) + ". "
    if len(recv):
        big = recv.assign(a=recv.effect_capacity.abs()).sort_values("a", ascending=False).iloc[0]
        p3 += (f"It is also exposed to {recv.GENCONSETID.nunique()} supported families that are not relevant to it (spillover); the largest is {big.GENCONSETID} "
               f"({big.effect_capacity:+.0f} MW {big.direction}, {'CI excludes zero' if big.ci_excludes_zero else 'CI includes zero'}). ")
    if len(sent):
        p3 += f"Its own supported families show supported spillover on {sent.name.nunique()} other link(s)."
    if p3:
        lines.append(f"<p>{escape(p3)}</p>")
    lines.append("</section>")
    return "\n".join(lines)


def lookup_html(d):
    lk = d["lookup"]; lk = lk[lk.tier.isin(["supported", "indicative"])].copy()
    lk["effect"] = lk.effect_capacity.map(fmt_mw) + " MW" + lk.effect_capacity_pct.map(lambda x: "" if pd.isna(x) else f" ({x:+.0f}%)")
    lk["ci"] = "[" + lk.ci_lo_capacity.map(fmt_mw) + ", " + lk.ci_hi_capacity.map(fmt_mw) + "]"
    lk = lk.sort_values(["name", "asset", "direction"])
    rows = []
    for r in lk.itertuples():
        rows.append(f'<tr class="{"tier-ind" if r.tier == "indicative" else ""}"><td>{escape(r.name)}</td><td>{escape(DIRL[r.direction])}</td>'
                    f'<td><strong>{escape(str(r.asset_description or r.asset))}</strong><br><small>{escape(r.asset)}{" · " + str(int(r.voltage_kv)) + " kV" if pd.notna(r.voltage_kv) else ""}</small></td>'
                    f'<td>{escape(str(r.substation or "—"))}<br><small>{escape(str(r.area_label or "no coordinates"))}</small></td>'
                    f'<td>{escape(r.published_level)}<br><small>{escape(str(r.published_key))}</small></td><td>{escape(r.effect)}<br><small>{escape(r.ci)}</small></td>'
                    f'<td>{escape(fmt_mw(r.effect_directional_flow))}</td>'
                    f'<td>{"—" if pd.isna(r.episodes) else int(r.episodes)} · {0 if pd.isna(r.treated_hours) else r.treated_hours:,.0f} h</td>'
                    f'<td><small>{escape(str(r.electrically_near or "—"))}</small></td><td><small>{escape(str(r.plants_within_50km or "—"))[:180]}</small></td><td>{escape(r.tier)}</td></tr>')
    return ('<input id="lk-q" class="lookup-search" type="search" placeholder="Filter by line, asset ID, substation, area, connector, DUID…" aria-label="Filter the outage lookup" '
            'oninput="(function(q){q=q.toLowerCase();var n=0;document.querySelectorAll(\'#lk tbody tr\').forEach(function(r){var s=r.textContent.toLowerCase().indexOf(q)>-1;r.style.display=s?\'\':\'none\';if(s)n++;});document.getElementById(\'lk-n\').textContent=n;})(this.value)">'
            f'<p class="small"><span id="lk-n">{len(lk)}</span> rows shown · greyed rows are indicative</p>'
            '<div class="table-wrap lookup-wrap" tabindex="0"><table id="lk"><thead><tr><th>Connector</th><th>Direction</th><th>Outage asset</th><th>Substation · area</th>'
            '<th>Published level</th><th>Limit change · 95% CI</th><th>Flow Δ (MW)</th><th>Evidence</th><th>Electrically near</th><th>Power stations ≤50 km</th><th>Tier</th></tr></thead><tbody>'
            + "".join(rows) + '</tbody></table></div>'
            '<style>.lookup-search{width:100%;max-width:620px;padding:11px 13px;margin:8px 0 6px;border:1px solid #cfd4de;border-radius:8px;font:inherit}'
            '#lk tr.tier-ind{opacity:.55}#lk td small{color:#667;font-weight:400}#lk{min-width:1500px}#lk td{white-space:normal;min-width:90px}#lk td:nth-child(3){min-width:230px}'
            '.lookup-wrap{max-height:78vh;overflow:auto}#lk thead th{position:sticky;top:0;background:#ececf3;z-index:1}@media print{.lookup-search{display:none}}</style>'), len(lk)


# ============================================================================ build
def build():
    OUT.mkdir(parents=True, exist_ok=True); DL.mkdir(parents=True, exist_ok=True)
    d = derive(load_all())
    fam, sup, lookup = d["family_effects"], d["sup"], d["lookup"]
    rel, eps, okeys = d["set_relevance"], d["episodes"], d["outage_keys"]

    # ---------------- downloads
    spill_fp = d["footprint"]
    outputs = {
        "nos_outage_episodes.csv.gz": eps, "nos_outage_keys.csv.gz": okeys, "nos_set_relevance.csv": rel,
        "nos_state_coverage.csv": d["coverage"], "nos_state_regime_summary.csv": d["state_summary"],
        "nos_family_effects.csv": fam, "nos_key_effects.csv.gz": d["key_effects"], "nos_outage_lookup.csv": lookup,
        "nos_diurnal_profiles_48.csv": d["diurnal_48"], "nos_timing_effects.csv": d["timing"], "nos_weather_vre_interaction.csv": d["interaction"],
        "nos_flow_response.csv": d["flow_response"], "nos_leader_transitions.csv": d["transitions"], "nos_duid_pressure.csv": d["duid_pressure"],
        "nos_system_footprint.csv": spill_fp, "nos_spillover.csv": d["spillover"], "nos_booking_reliability.csv": d["br"],
        "nos_booking_states.csv": d["states"], "nos_event_study.csv.gz": d["event_study"],
        "nos_placebo_checks.csv": fam[["name", "direction", "GENCONSETID", "episodes", "treated_hours", "match_rate", "effect_capacity", "placebo_n",
                                       "placebo_effect_capacity", "placebo_ci_lo", "placebo_ci_hi", "placebo_clean", "tier"]],
        "nos_k5_electrical.csv": d["k5_electrical"], "nos_substation_crosswalk.csv": d["crosswalk"],
        "nos_execution_log.csv": pd.DataFrame(d["log"]),
    }
    for name, frame in outputs.items():
        target = DL / name; tmp = target.with_name(target.name + ".tmp")
        frame.to_csv(tmp, index=False, compression={"method": "gzip", "mtime": 0} if name.endswith(".gz") else None)
        safe_replace(tmp, target)
    (OUT / "sources").mkdir(exist_ok=True)
    shutil.copy2(EXEC / "METHODOLOGY.md", OUT / "METHODOLOGY.md")
    for f in ["PLAN.md", "EXECUTION_LOG.md", "RESULTS_SUMMARY.md", "pilot_summary.md"]:
        shutil.copy2(EXEC / f, OUT / "sources" / f)
    # constraint mechanics and outlook chapters (execution/nos_constraint_binding_v1), from cached tables
    ch = cm.build(DL)
    EXEC2 = cm.EXEC2
    (OUT / "sources" / "constraint_mechanics").mkdir(exist_ok=True)
    for f in ["PLAN.md", "METHODOLOGY.md", "EXECUTION_LOG.md", "RESULTS_SUMMARY.md"]:
        if (EXEC2 / f).exists():
            (OUT / "sources" / "constraint_mechanics" / f).unlink(missing_ok=True)
            shutil.copy2(EXEC2 / f, OUT / "sources" / "constraint_mechanics" / f)

    # ---------------- figures
    f_month, f_type = fig_landscape(d)
    f_rel = fig_relevance(d); f_cov = fig_coverage(d)
    forests = {n: fig_forest(sup, n) for n in ORDER if n in set(sup.name)}
    f_diur = fig_diurnal(d); f_per = fig_period_heat(d); f_sea = fig_season_heat(d); f_int = fig_interaction(d)
    f_flow, f_flow2 = fig_flow(d)
    (f_sp_f, f_sp_r), spill_m = fig_spill(d)
    f_foot = fig_footprint(d); f_duid = fig_duid(d); f_ev = fig_events(d); f_map, n_map = fig_map(d)
    f_book = fig_booking(d); f_plac, f_rung, f_bal = fig_robust(d)

    # ---------------- numbers for prose
    n_sup_fam = sup.drop_duplicates(["ic", "GENCONSETID"]).shape[0]
    lk_sup = lookup[lookup.tier.eq("supported")]
    n_lk_assets = lk_sup.asset.nunique()
    n_asset_level = lk_sup[lk_sup.published_level.isin(["K1", "K1xK2"])].asset.nunique()
    biggest = sup.loc[sup.effect_capacity.idxmin()]
    biggest_up = sup.loc[sup.effect_capacity.idxmax()]
    fr = d["flow_response"].dropna(subset=["flow_pass_through"])
    red = fr[fr.effect_capacity < -25]
    pt_all = float(red.flow_pass_through.clip(-2, 2).median())
    hr_all = float(red.headroom_absorbed.clip(-2, 2).median())
    multi = d["rel_of"][d["rel_of"].map(len) > 1]
    sp_sup = spill_fp[spill_fp.relation.str.startswith("not") & spill_fp.tier.eq("supported")]
    sp_excl = float(sp_sup.ci_excludes_zero.mean())
    rel_sup = spill_fp[spill_fp.relation.eq("relevant") & spill_fp.tier.eq("supported")]
    rel_excl = float(rel_sup.ci_excludes_zero.mean())
    di = d["diurnal_48"]; da = di[di.season.eq("All")]
    qni_med = da[da.name.eq("QNI")].capacity_effect.median()
    br2 = d["br"][d["br"].study_year.eq(2)]
    states = d["states"]
    st_off = states[states.state.isin(["booked_only", "withdrawn_booking"])].groupby(["name", "state"]).effect_capacity.median()
    flagged = st_off[st_off.abs() >= 15]
    pr = d["placebo_rate"].reindex(ORDER).dropna()
    first_log, last_log = d["log"][0]["time"][:10], d["log"][-1]["time"][:10]
    n_live = int((~eps.withdrawn).sum())

    # ---------------- body
    b = []
    b.append(hero("NEM · SIX INTERCONNECTORS · NETWORK OUTAGE SCHEDULE · SEP 2024–AUG 2026",
                  "When a network outage is in place —", "what happens to every interconnector",
                  "An end-to-end research pass linking AEMO Network Outage Schedule bookings to the constraint sets they invoke and to five-minute dispatch limits and flows on QNI, "
                  "Directlink, VNI, Heywood, Murraylink and Basslink. Each outage-family effect is estimated against matched outage-free conditions, falsified with placebo windows, "
                  "and resolved down to the specific line, substation and area where the data allows.",
                  ["Window: Sep 2024 – Aug 2026 (NEM time)", "Six links · twelve directions", f"{len(eps):,} NEM outage episodes", "Retrospective · descriptive · no fitted model",
                   f"Built {pd.Timestamp.now(tz='Australia/Brisbane'):%d %b %Y}"]))
    b.append('<nav class="anchor-nav"><a href="#executive">Executive summary</a><a href="#design">Research design</a><a href="#landscape">Outage landscape</a>'
             '<a href="#effects">Limit effects</a><a href="#timing">Timing & weather</a><a href="#flow">Flow response</a><a href="#spillover">Effects on other links</a>'
             '<a href="#mechanics">Constraint & DUID mechanics</a><a href="#constraints">What binds during outages</a><a href="#events">Onset & recovery</a><a href="#connectors">Connector chapters</a>'
             '<a href="#lookup">Specific outage lookup</a><a href="#outlook">12-month outlook</a><a href="#bookings">Bookings</a><a href="#robustness">Robustness</a><a href="#methods">Methods</a><a href="#record">Execution record</a></nav>')
    b.append('<section class="metrics">' + metric("NEM outage episodes", f"{len(eps):,}", f"{n_live:,} live, {len(eps) - n_live:,} withdrawn; MMSDM final state")
             + metric("Relevant outage families", f"{int(rel.relevant.sum())}", f"connector × constraint-set pairs; {len(multi)} families relevant to 2+ links")
             + metric("Supported family effects", f"{n_sup_fam}", "pass episode, hours, match-rate and placebo gates")
             + metric("Specific outage assets", f"{n_lk_assets:,}", f"with a supported lookup entry; {n_asset_level} at asset level") + '</section>')
    b.append('<section class="callout"><strong>What is being measured.</strong> A NOS booking tells us equipment is planned out of service; the constraint-set families linked to the booking '
             'are what change the dispatch envelope. This report therefore measures, for each <em>constraint-set family</em>, how the solved directional interconnector limit, flow, headroom and '
             'time-at-limit differ when that family is invoked compared with matched half-hours when it is not — same connector and direction, season, half-hour (±30 min), day type, '
             'weather/VRE/residual-demand regime, ±21 days, and as far as possible the same other outages. AEMO limits are dispatch-solution outputs, not physical transfer capability.</section>')
    b.append('<section class="callout scope-note"><strong>Interpretation boundary.</strong> Outages are scheduled by network operators where they expect least harm, so every number here is '
             '"typical impact as scheduled", not the impact of an outage at an arbitrary time. Placebo and booked-only checks show residual confounding for some families. '
             'Nothing here is a forecast feature; the analysis uses realised invocation and actual outage times.</section>')

    # executive
    cv = d["coverage"]
    vni_inv = cv[cv.ic.eq("VIC1-NSW1") & cv.state.isin(["invoked_nonleading", "invoked_leading"])].groupby("direction").share.sum().mean()
    b.append('<section id="executive"><div class="section-kicker">EXECUTIVE SUMMARY</div><h2>What the outage evidence says</h2>')
    b.append(f'<p>Outage configurations are the normal state of the network, not the exception. Once constraint sets are filtered to those whose equations actually set a link\'s limit while '
             f'invoked, at least one such family is active in {vni_inv:.0%} '
             f'of VNI half-hours and around four-fifths of Heywood and Murraylink half-hours, against roughly half the time on QNI, Directlink and Basslink. A simple "outage versus no outage" '
             f'comparison is therefore meaningless for the southern links; the report instead compares each family switched on versus off, holding the other outages as constant as the data allow.</p>')
    b.append(f'<p>The effects are concentrated. QNI carries the largest and most consistent outage sensitivity: pooled over its supported families, its limit sits a median {qni_med:+.0f} MW '
             f'below matched controls, and its three largest individual effects — the Dumaresq–Sapphire 8J line, the Tamworth 3 330 kV bus and the Armidale–Dumaresq 8C line — each remove '
             f'500–650 MW. Heywood and VNI show smaller median shifts (tens of MW) with a wide spread of family-specific effects in both directions; Murraylink, Directlink and Basslink '
             f'are close to zero on average, with a handful of material families. Several outage families <em>raise</em> one direction, most prominently {escape(str(biggest_up.GENCONSETID))} on '
             f'{escape(str(biggest_up["name"]))} {escape(str(biggest_up.direction))} ({biggest_up.effect_capacity:+,.0f} MW), because the outage changes which equation binds.</p>')
    b.append(f'<p>Limits and flows are different outcomes. Where a supported family cuts the limit by more than 25 MW, flow moves by a median {pt_all:.0%} of the limit change and headroom '
             f'absorbs about {hr_all:.0%}; QNI in particular often has spare room, so large limit cuts translate into modest flow changes. The cross-link view shows that outage families '
             f'relevant to one link also move others: {len(sp_sup):,} supported spillover estimates exist, though only {sp_excl:.0%} have confidence intervals excluding zero '
             f'(versus {rel_excl:.0%} for relevant-link effects), so spillover is real but mostly smaller and less certain.</p>')
    b.append('<div class="findings">')
    b.append(finding(1, "QNI is the outage-sensitive link", f"Largest supported reduction: {biggest.GENCONSETID} on {biggest['name']} {biggest.direction}, {biggest.effect_capacity:+,.0f} MW "
                        f"({biggest.effect_capacity_pct:+.0f}% of the seasonal median) over {int(biggest.episodes)} episodes and {biggest.treated_hours:,.0f} invoked hours."))
    b.append(finding(2, "Outages re-orient envelopes", f"{(sup.effect_capacity > 25).sum()} supported family-directions raise the limit by more than 25 MW, and {(sup.effect_capacity < -25).sum()} cut it — "
                        "an outage often tightens one direction while a looser equation takes over the other."))
    b.append(finding(3, "Flow only partly follows", f"Median flow pass-through is {pt_all:.2f} for limit cuts above 25 MW; the balance shows up as lost headroom and more time at the limit."))
    b.append(finding(4, "Spillover is common but weaker", f"{len(multi)} families are relevant to two or more links (mostly VNI/Murraylink/Heywood). Of {len(sp_sup)} supported spillover estimates, {sp_excl:.0%} exclude zero."))
    b.append(finding(5, "Specific outages are resolvable", f"{n_lk_assets} outage assets have a supported lookup entry, {n_asset_level} at the individual asset level, each with substation, area and electrically-near generators."))
    b.append(finding(6, "Residual confounding remains", "Placebo tests are clean for " + ", ".join(f"{k} {v:.0%}" for k, v in pr.items())
                        + " of eligible families; some booked-only/withdrawn windows are not near zero. Treat single-family estimates of tens of MW with caution."))
    b.append('</div></section>')

    # design
    b.append('<section id="design"><div class="section-kicker">RESEARCH DESIGN</div><h2>From a booking to a matched limit effect</h2>')
    b.append('<p>The pass was run as a logged, staged campaign (plan, methodology and a 40+-entry execution log are linked below). A pilot on VNI and Heywood tested whether the design '
             'could support individual-family and individual-asset conclusions before the six-link build; it passed (26 and 28 supported families against a gate of 10), and several '
             'method choices were revised on evidence and logged as decisions.</p>')
    steps = pd.DataFrame([
        ["S0 Acquire", "MMSDM NETWORK_OUTAGEDETAIL, OUTAGECONSTRAINTSET (24 monthly archives), EQUIPMENTDETAIL, SUBSTATIONDETAIL; OpenStreetMap substations and power stations", "50 AEMO files, none missing; GA services blocked → OSM"],
        ["S1 Episodes", "Resubmission chains collapsed; actual windows where reported; withdrawn bookings kept but flagged", f"{len(eps):,} episodes; all 26,454 weekly-NOS year-2 IDs reconcile"],
        ["S2 Location keys", "K1 asset · K2 constraint family · K3 substation · K4 area · K5 electrically and geographically near generators", f"K3 {okeys.substation_name.notna().mean():.0%}, K4 {okeys.lat.notna().mean():.0%} of episodes"],
        ["S3 Relevance", "A family is relevant to a link if its equation led that link's reconstructed envelope in ≥12 intervals while invoked", f"{int(rel.relevant.sum())} pairs; 1,678 ramp/discretionary sets excluded"],
        ["S4 State panel", "Half-hour invocation coverage per family; connector state (leading › invoked › partial › booked › clear)", "630,720 connector-direction half-hours"],
        ["S5 Matching", "Three-rung matched on/off comparison, day-block bootstrap CIs, ±7-day placebo, spillover, event study, key-level lookup", f"{len(fam):,} family-direction estimates; {len(d['footprint']):,} incl. spillover"],
        ["S6–S7 Report", "Cached rendering, manifest hashes, validator, desktop/mobile checks, full test suite", "this document"],
    ], columns=["stage", "what was done", "outcome"])
    b.append(table(steps, list(steps.columns), limit=10))
    b.append('<h3>Evidence gates</h3><p>A family-direction is <strong>supported</strong> only if it has at least five distinct live outage episodes with invoked half-hours, at least 24 invoked hours, '
             'at least 60% of treated half-hours matched to controls, and a ±7-day placebo whose 95% interval includes zero. <strong>Indicative</strong> results are shown greyed and never ranked. '
             'The same gate is applied at every lookup level, so an individual asset appears only when that asset itself has enough repeated outages.</p></section>')

    # landscape
    b.append('<section id="landscape"><div class="section-kicker">OUTAGE LANDSCAPE</div><h2>How often, where, and on which links outages matter</h2>')
    b.append(f'<p>Across the two years the NEM saw {len(eps):,} outage episodes overlapping the window, of which {len(eps) - n_live:,} were withdrawn. Queensland and New South Wales account for '
             f'most bookings; lines, circuit breakers and transformers dominate the equipment mix. Only a minority of bookings link to constraint sets at all, and fewer still to sets '
             f'that ever set an interconnector limit.</p>')
    b.append(fig_block(f_month, "Live outage episodes by start month and region", "Region from the primary asset's substation (AEMO SUBSTATIONDETAIL); episodes starting before Sep 2024 are shown in Sep 2024.", "nos_outage_episodes.csv.gz"))
    b.append(fig_block(f_type, "Outage episodes by primary equipment type", "Primary asset chosen by LINE › TRANS › BUS › reactive plant › CB › other; 'OTHER' includes element descriptions without a recognisable type.", "nos_outage_episodes.csv.gz"))
    b.append(fig_block(f_rel, "Relevant families and evidence tiers by connector", "Best tier across the two directions for each family.", "nos_family_effects.csv"))
    b.append(fig_block(f_cov, "Share of time in each connector outage state", "Leading = an invoked relevant family's equation formed the limit. Unknown = incomplete half-hour.", "nos_state_coverage.csv"))
    ss = d["state_summary"]; ss = ss[ss.state.isin(["clear", "invoked_nonleading", "invoked_leading"])].copy(); ss["direction"] = ss.direction.map(DIRL)
    ss["name"] = pd.Categorical(ss.name, ORDER, ordered=True); ss = ss.sort_values(["name", "direction", "state"])
    piv = ss.pivot_table(index=["name", "direction"], columns="state", values=["capacity_median", "at_limit_share"], observed=True)
    lower = int((piv[("capacity_median", "invoked_leading")] < piv[("capacity_median", "clear")]).sum())
    more = int((piv[("at_limit_share", "invoked_leading")] > piv[("at_limit_share", "clear")]).sum())
    b.append('<p>The raw state comparison below is <em>not</em> an effect estimate: outage states coincide with seasons, times of day and other outages. It shows the operating envelope '
             f'each link actually experienced. In {lower} of 12 link-directions the median limit is lower when an outage family leads than in clear time, and in {more} of 12 the at-limit '
             'share is higher. The exceptions (for example Basslink reverse and VNI forward) show why raw state averages mislead: clear time on those links is rare or unrepresentative, '
             'which is what the matched comparison corrects for.</p>')
    ss = ss.rename(columns={"half_hours": "half-hours", "capacity_p10": "limit P10", "capacity_median": "limit median", "capacity_p90": "limit P90", "flow_median": "flow median",
                            "headroom_median": "headroom median", "at_limit_share": "at limit", "restricted_share": "restricted"})
    b.append(table(ss, ["name", "direction", "state", "half-hours", "limit P10", "limit median", "limit P90", "flow median", "headroom median", "at limit", "restricted"],
                   {"half-hours": lambda x: f"{int(x):,}", "limit P10": lambda x: f"{x:,.0f}", "limit median": lambda x: f"{x:,.0f}", "limit P90": lambda x: f"{x:,.0f}",
                    "flow median": lambda x: f"{x:,.0f}", "headroom median": lambda x: f"{x:,.0f}", "at limit": pct, "restricted": pct}, 40))
    b.append('</section>')

    # effects
    b.append('<section id="effects"><div class="section-kicker">LIMIT EFFECTS</div><h2>Which outage families move each link\'s limit, and by how much</h2>')
    b.append('<p>Each point below is one constraint-set family in one direction, placed at the median difference between its invoked half-hours and their matched controls. Only supported '
             'families are plotted; indicative and unsupported estimates, every balance diagnostic and the matching-rung shares are in the family-effects download. Families are named by '
             'AEMO GENCONSETID; hover to see the outage asset that most often invokes the family and its area.</p>')
    for n, f in forests.items():
        b.append(fig_block(f, f"{n} — supported outage-family effects", "95% day-block bootstrap intervals; controls matched on season, half-hour (±30 min), day type, weather/VRE/demand regime, ±21 days and other outages.", "nos_family_effects.csv"))
    top = sup.assign(a=sup.effect_capacity.abs()).sort_values("a", ascending=False).head(30).copy()
    top["limit change"] = top.effect_capacity.map(fmt_mw) + top.effect_capacity_pct.map(lambda x: "" if pd.isna(x) else f" ({x:+.0f}%)")
    top["95% CI"] = "[" + top.ci_lo_capacity.map(fmt_mw) + ", " + top.ci_hi_capacity.map(fmt_mw) + "]"
    b.append('<h3>The 30 largest supported effects across all links</h3>')
    b.append(table(top.rename(columns={"name": "connector", "GENCONSETID": "family", "typical_asset": "typical outage asset", "area_label": "area", "effect_at_limit": "at-limit Δ",
                                       "effect_directional_flow": "flow Δ", "treated_hours": "hours", "match_rate": "matched"}),
                   ["connector", "direction", "family", "typical outage asset", "area", "limit change", "95% CI", "at-limit Δ", "flow Δ", "episodes", "hours", "matched"],
                   {"at-limit Δ": pp, "flow Δ": fmt_mw, "episodes": lambda x: f"{int(x)}", "hours": lambda x: f"{x:,.0f}", "matched": pct}, 30))
    b.append('</section>')

    # timing
    b.append('<section id="timing"><div class="section-kicker">TIMING & WEATHER</div><h2>When outage effects bite</h2>')
    ext = []
    for (n_, dr), g in da.groupby(["name", "direction"]):
        lo_, hi_ = g.loc[g.capacity_effect.idxmin()], g.loc[g.capacity_effect.idxmax()]
        ext.append((n_, dr, lo_.clock, lo_.capacity_effect, hi_.clock, hi_.capacity_effect))
    ext = pd.DataFrame(ext, columns=["name", "direction", "min_clock", "min_mw", "max_clock", "max_mw"]).set_index(["name", "direction"])
    def ex(n_, dr):
        r_ = ext.loc[(n_, dr)]
        return f"{r_.min_mw:+.0f} MW at {r_.min_clock}"
    b.append('<p>Pooling the matched half-hours of supported families gives a within-day profile of the outage effect. For QNI the outage limit sits below the control line in every half-hour; '
             f'the gap is deepest overnight in the forward direction ({ex("QNI", "forward")}) and in the evening peak in reverse ({ex("QNI", "reverse")}). VNI forward is the clearest time-of-day '
             f'pattern: supported families lift the export limit around midday (peak {ext.loc[("VNI", "forward")].max_mw:+.0f} MW at {ext.loc[("VNI", "forward")].max_clock}) but cut it in the evening '
             f'({ex("VNI", "forward")}). Heywood\'s effect is concentrated in the morning ramp (forward {ex("Heywood", "forward")}, reverse {ex("Heywood", "reverse")}). Directlink, Murraylink and Basslink '
             'profiles stay within about ±25 MW.</p>')
    b.append(fig_block(f_diur, "48-half-hour limit profiles, invoked vs matched control", "Medians over matched treated half-hours of supported families, all seasons.", "nos_diurnal_profiles_48.csv"))
    b.append(fig_block(f_per, "Outage effect by daily operating period", "Median of season × period cell medians.", "nos_timing_effects.csv"))
    b.append(fig_block(f_sea, "Outage effect by Australian season", "Two blocks of each season in the window; seasonal differences also reflect which outages ran in each season.", "nos_timing_effects.csv"))
    b.append('<p>Splitting the same matched differences by the weather or renewable regime at the treated half-hour shows whether outages hurt more under stress. These are medians within '
             'regime, not interaction coefficients: the mix of families differs between regimes.</p>')
    b.append(fig_block(f_int, "Outage effect by temperature, VRE and residual-demand regime", "Regimes are within-connector-season P20/P80 bins inherited from the base regime report.", "nos_weather_vre_interaction.csv"))
    b.append('</section>')

    # flow
    b.append('<section id="flow"><div class="section-kicker">FLOW RESPONSE</div><h2>Limit changes are mostly absorbed as headroom</h2>')
    b.append(f'<p>An outage that cuts a limit only changes dispatch if flow was going to use that room. Across supported family-directions with a limit cut above 25 MW, the median flow change is '
             f'{pt_all:.0%} of the limit change and headroom absorbs about {hr_all:.0%}. QNI shows the lowest pass-through — its large outage cuts usually arrive when flow is well inside the envelope — '
             f'while Basslink and Murraylink pass more of a (smaller) change through to flow.</p>')
    b.append(fig_block(f_flow, "Flow change versus limit change, supported families", "Points on the dotted line: flow tracks the limit one-for-one; on the x-axis: limit moved, flow did not.", "nos_flow_response.csv"))
    b.append(fig_block(f_flow2, "Flow pass-through and headroom share by connector", "Ratios computed only where |limit change| > 25 MW; medians across family-directions.", "nos_flow_response.csv"))
    fl = d["flow_response"].assign(a=lambda x: x.effect_capacity.abs()).sort_values("a", ascending=False).head(20)
    b.append(table(fl.rename(columns={"name": "connector", "GENCONSETID": "family"}), ["connector", "direction", "family", "effect_capacity", "effect_directional_flow", "effect_headroom",
                                                                                          "treated_at_limit", "control_at_limit", "flow_pass_through"],
                   {"effect_capacity": fmt_mw, "effect_directional_flow": fmt_mw, "effect_headroom": fmt_mw, "treated_at_limit": pct, "control_at_limit": pct,
                    "flow_pass_through": lambda x: "—" if pd.isna(x) else f"{x:.2f}"}, 20))
    b.append('</section>')

    # spillover
    b.append('<section id="spillover"><div class="section-kicker">EFFECTS ON OTHER LINKS</div><h2>One outage, many interconnectors</h2>')
    mv = multi.map(lambda x: " + ".join(x)).value_counts().head(6)
    b.append(f'<p>{len(multi)} outage families are relevant to two or more links — their equations set more than one interconnector\'s limit. The most common combinations are '
             + "; ".join(f"{escape(k)} ({v})" for k, v in mv.items()) + '. Beyond these shared families, the spillover analysis applies the same matched design to a family on a link where it '
             'is <em>not</em> relevant: none of its equations sets that link\'s limit, so any effect runs through shared network paths, redispatch or co-occurring conditions.</p>')
    b.append(fig_block(f_foot, "System footprint of the largest outage families", "Rows: the 32 families with the largest supported effects. Columns: all twelve link-directions. Only supported cells are coloured; hover shows unsupported values and whether the family is relevant to that link.", "nos_system_footprint.csv"))
    b.append(f'<p>The footprint shows three patterns. Northern NSW and Queensland families (N-/Q- prefixes) concentrate on QNI, with only small effects on Directlink; southern-NSW and Victorian families (N-, V-, I- prefixes) span VNI, '
             f'Murraylink and Heywood, often with opposite signs across directions; South Australian families (S-) mostly affect Heywood and Murraylink. Spillover estimates are more often '
             f'indistinguishable from zero: {sp_excl:.0%} of supported spillover cells exclude zero against {rel_excl:.0%} of supported relevant-link cells.</p>')
    b.append(fig_block(f_sp_f, "Spillover matrix — forward direction", "Median matched effect of supported families that are not relevant to the measured link, grouped by the links they are relevant to.", "nos_system_footprint.csv"))
    b.append(fig_block(f_sp_r, "Spillover matrix — reverse direction", "As above, reverse direction.", "nos_system_footprint.csv"))
    ts = sp_sup.assign(a=sp_sup.effect_capacity.abs()).sort_values("a", ascending=False).head(20).copy()
    ts["relevant to"] = ts.GENCONSETID.map(lambda g: ", ".join(d["rel_of"].get(g, [])))
    ts["95% CI"] = "[" + ts.ci_lo_capacity.map(fmt_mw) + ", " + ts.ci_hi_capacity.map(fmt_mw) + "]"
    b.append('<h3>Largest supported spillover effects</h3>')
    b.append(table(ts.rename(columns={"name": "measured on", "GENCONSETID": "family", "effect_capacity": "limit change"}),
                   ["measured on", "direction", "family", "relevant to", "limit change", "95% CI", "episodes", "treated_hours"],
                   {"limit change": fmt_mw, "episodes": lambda x: f"{int(x)}", "treated_hours": lambda x: f"{x:,.0f}"}, 20))
    b.append('</section>')

    # mechanics
    b.append('<section id="mechanics"><div class="section-kicker">CONSTRAINT & DUID MECHANICS</div><h2>What takes over the envelope, and which generators push it</h2>')
    tr = d["transitions"].merge(sup[["ic", "direction", "GENCONSETID", "effect_capacity"]], on=["ic", "direction", "GENCONSETID"], how="left")
    b.append(f'<p>For supported families, the equation leading the envelope during an invoked run differs from the one leading just before it in a median {tr.leader_changed_share.median():.0%} '
             f'of runs. Families with the largest effects are typically the ones whose own equations take over the envelope (high “family leads” share in the tables), while families with small '
             f'effects are invoked alongside a different binding equation.</p>')
    tr2 = tr.assign(a=tr.effect_capacity.abs()).sort_values("a", ascending=False).head(20)
    b.append(table(tr2.rename(columns={"name": "connector", "GENCONSETID": "family", "effect_capacity": "limit change", "before_top3": "leader before (top 3)", "during_top3": "leader during (top 3)", "leader_changed_share": "leader changed"}),
                   ["connector", "direction", "family", "limit change", "leader before (top 3)", "leader during (top 3)", "leader changed"], {"limit change": fmt_mw, "leader changed": pct}, 20))
    b.append('<p>Generator pressure attributes movement of the leading equation to individual DUIDs (sensitivity × 30-minute dispatch change, leader-only). The chart compares each DUID\'s '
             'mean tightening per half-hour while a supported family is invoked with the family-off half-hours of the same months. Snowy hydro units (TUMUT3, UPPTUMUT, MURRAY) recur across '
             'QNI, VNI, Directlink, Murraylink and Basslink families, alongside large solar farms such as Tailem Bend (TBSF1), Cohuna (CUSF1) and Limondale (LIMOSF11). These are the units whose '
             'output moves the outage equations while they bind. Hydro units also appear with large relief values, because their output swings in both directions.</p>')
    b.append(fig_block(f_duid, "Excess generator tightening during supported outage families", "Summed over supported families per link; relief is in the download. A decomposition of an active equation, not causal attribution.", "nos_duid_pressure.csv"))
    dp = d["duid_pressure"].assign(a=lambda x: x.excess_tightening.abs()).sort_values("a", ascending=False).head(20)
    b.append(table(dp.rename(columns={"name": "connector", "GENCONSETID": "family"}), ["connector", "direction", "family", "DUID", "tightening_per_hh_treated", "tightening_per_hh_base", "excess_tightening", "excess_relief"],
                   {c: lambda x: f"{x:,.1f}" for c in ["tightening_per_hh_treated", "tightening_per_hh_base", "excess_tightening", "excess_relief"]}, 20))
    b.append('</section>')

    b.append(ch["constraints"])

    # events
    b.append('<section id="events"><div class="section-kicker">ONSET & RECOVERY</div><h2>How quickly limits switch into and out of outage configurations</h2>')
    ev = d["event_study"]; ev = ev[ev.scope.eq("pooled_supported") & ev.clean.fillna(False)]
    early = ev[ev.anchor.eq("start") & ev.offset_h.between(0.5, 6)].groupby(["ic", "direction"]).median_rel.median()
    early = early.rename(index=NAMES, level=0)
    big = early[early.abs() >= 10].sort_values()
    pre = ev[ev.anchor.eq("start") & ev.offset_h.between(-24, -2)].groupby(["ic", "direction"]).median_rel.median().rename(index=NAMES, level=0)
    pre_big = pre[pre.abs() >= 10]
    b.append('<p>Aligning supported families on the start and end of each invocation spell, relative to the same half-hour on the previous seven family-off days, gives a more modest picture '
             'than the matched effects. Pooled across many heterogeneous families, the median change in the first six hours after onset is '
             + ", ".join(f"{a} {dr} {v:+.0f} MW" for (a, dr), v in big.items())
             + '; every other link-direction stays within ±10 MW. '
             + (('The pre-onset window is not flat everywhere (' + ", ".join(f"{a} {dr} {v:+.0f} MW" for (a, dr), v in pre_big.items())
                 + ' in the 24 h before onset), which shows the seven-day baseline itself is affected by other outages and scheduling. ') if len(pre_big) else
                'The 24 h before onset is flat (within ±10 MW) on every link-direction. ')
             + 'Pooling also dilutes the large single-family effects, so these curves are timing context rather than effect sizes; the matched estimates above are the primary evidence. '
             'Family-level curves are in the download. Only clean spells (no other relevant family starting or ending within ±2 h) are plotted.</p>')
    b.append(fig_block(f_ev, "Event study around invocation start and end", "Median across clean spells of supported families; per-family curves and P25/P75 in the download.", "nos_event_study.csv.gz"))
    b.append('</section>')

    # connectors
    b.append('<section id="connectors"><div class="section-kicker">CONNECTOR CHAPTERS</div><h2>Link-by-link findings</h2><p>Each chapter restates the evidence for one link: how often it runs under '
             'relevant outages, the pooled and family-level effects, flow pass-through, the generators most involved, and its exposure to other links\' outages.</p></section>')
    for n in ORDER:
        b.append(connector_chapter(d, n, forests))

    # map + lookup
    b.append('<section id="lookup"><div class="section-kicker">SPECIFIC OUTAGE LOOKUP</div><h2>Given this outage — what happens to the limit?</h2>')
    b.append(f'<p>The lookup answers the question at the most specific level the evidence supports. Each outage asset is published at the first supported level in the order '
             f'<em>asset × constraint family → asset → constraint family → substation → area</em>; if none is supported, the first indicative level is shown greyed. The published level is stated '
             f'on every row, so a row published at "K3" describes outages at that substation generally, not the single asset. <em>Electrically near</em> lists the DUIDs whose output moves the '
             f'family\'s equations (−b/a); <em>power stations ≤50 km</em> uses OpenStreetMap locations. {n_map} substations with supported asset- or substation-level entries have coordinates and are mapped below.</p>')
    b.append(fig_block(f_map, "Location of outages with supported effects", "Longitude/latitude of the outage substation (OSM name crosswalk); size = |limit change|; colour = link affected. No basemap is embedded to keep the report offline.", "nos_outage_lookup.csv"))
    lk_html, n_lk = lookup_html(d)
    b.append(lk_html)
    b.append('</section>')

    # bookings
    b.append(ch["outlook"])
    b.append('<section id="bookings"><div class="section-kicker">BOOKINGS</div><h2>How outage bookings play out</h2>')
    b.append(f'<p>In year 2, a median {br2.withdrawn_share.median():.0%} of bookings that list a relevant family were withdrawn. Live outages returned more than an hour early far more often '
             f'({br2.early_return_share.median():.0%}) than they overran ({br2.overrun_share.median():.0%}), and the median booking was submitted about {br2.lead_days_p50.median():.0f} days before its scheduled start. '
             f'The near-100% booked-to-invoked rate is close to built in: final-state MMSDM records link only the constraint sets that were used, so it is not evidence of forecasting reliability.</p>')
    b.append(fig_block(f_book, "Booking outcomes by link and study year", "Final-state MMSDM records; Y1 = Sep 2024–Aug 2025, Y2 = Sep 2025–Aug 2026.", "nos_booking_reliability.csv"))
    brt = d["br"].copy(); brt["name"] = pd.Categorical(brt.name, ORDER, ordered=True); brt = brt.sort_values(["name", "study_year"])
    b.append(table(brt, ["name", "study_year", "episodes", "withdrawn_share", "non_withdrawn", "actual_window_share", "start_shift_h_p50", "end_shift_h_p50", "early_return_share", "overrun_share", "lead_days_p50"],
                   {"withdrawn_share": pct, "actual_window_share": pct, "early_return_share": pct, "overrun_share": pct, "start_shift_h_p50": lambda x: f"{x:+.1f}",
                    "end_shift_h_p50": lambda x: f"{x:+.1f}", "lead_days_p50": lambda x: f"{x:.0f}"}, 20))
    b.append('</section>')

    # robustness
    b.append('<section id="robustness"><div class="section-kicker">ROBUSTNESS & FALSIFICATION</div><h2>How far to trust the estimates</h2>')
    b.append(f'<p>Three checks bound the evidence. First, shifting every treated window by ±7 days into family-off time should produce no effect; the placebo distribution is centred on zero '
             f'and much narrower than the actual one, but among families passing the other gates it is clean for only ' + ", ".join(f"{k} {v:.0%}" for k, v in pr.items()) + '. '
             'Families failing the placebo are never labelled supported. Second, booked-only and withdrawn-booking windows (family not invoked) should show roughly zero effect; most do, '
             + ("but " + "; ".join(f"{a} {b_.replace('_', ' ')} {v:+.0f} MW" for (a, b_), v in flagged.items()) + " do not, so conditions around booking windows still bias some comparisons." if len(flagged) else "and all are within ±15 MW.")
             + ' Third, matching quality: most controls come from the exact or same-count rungs, and post-matching standardised differences are small for weather and time but larger for the count of other outages.</p>')
    b.append(fig_block(f_plac, "Actual vs placebo effect distributions", "All evaluated family-directions; x-axis clipped to ±800/600 MW for legibility.", "nos_placebo_checks.csv"))
    b.append(fig_block(f_rung, "Matching rung shares by link", "Exact = same season/day-type/regime cell and identical set of other relevant outages.", "nos_family_effects.csv"))
    b.append(fig_block(f_bal, "Covariate balance before and after matching", "Dotted line at 0.1, a common balance threshold. Uses the pre-matching pooled SD for both stages.", "nos_family_effects.csv"))
    so = states.groupby(["name", "state"]).agg(families=("GENCONSETID", "nunique"), median_effect=("effect_capacity", "median"), unbooked_share=("share_of_invoked", "median")).reset_index()
    b.append(table(so.rename(columns={"name": "connector", "median_effect": "median limit change", "unbooked_share": "share of invoked time unbooked"}),
                   ["connector", "state", "families", "median limit change", "share of invoked time unbooked"], {"median limit change": fmt_mw, "share of invoked time unbooked": pct}, 30))
    b.append(ch["robustness"])
    b.append('</section>')

    # methods
    b.append('<section id="methods"><div class="section-kicker">METHODS & LIMITATIONS</div><h2>How the results were produced</h2><div class="method">')
    b.append('<p><strong>Data.</strong> AEMO MMSDM NETWORK_OUTAGEDETAIL and NETWORK_OUTAGECONSTRAINTSET (2026-08 cumulative final-state tables, reconciled against 53 weeks of NOS snapshots), '
             'NETWORK_EQUIPMENTDETAIL and NETWORK_SUBSTATIONDETAIL; GENCONSETINVOKE and generic-constraint standing tables for all six links; reconstructed five-minute constraint envelopes, '
             'leaders and DUID pressure from the two-year constraint archive; half-hour flows, limits, regional demand/VRE and endpoint weather from the base regime report. Substation and '
             'power-station coordinates come from OpenStreetMap (ODbL) because Geoscience Australia services were unreachable.</p>')
    b.append('<p><strong>Definitions.</strong> Fixed NEM time (UTC+10), interval-ending; complete half-hours need six five-minute observations. forward capacity = upper bound, reverse = −lower bound; '
             'headroom = capacity − directional flow; at-limit = headroom < max(10 MW, 5% of capacity); restricted = below 50% of the connector-direction-season median positive capacity. '
             'A family is invoked in a half-hour when all six intervals are covered; partial half-hours are excluded from both arms.</p>')
    b.append('<p><strong>Estimator.</strong> Median over treated half-hours of (treated value − median of up to five matched controls), 95% day-block bootstrap (1,000 replicates, resampling treated days). '
             'Matching ladder: (1) same season, day type, temperature/VRE/residual-demand bins, study year and identical set of other relevant invoked families; (2) same other-family count and '
             'leading flag; (3) coarse season/day type/temperature/year cell with the same count. Each rung tries the same half-hour then ±30 min, within ±21 days.</p>')
    b.append('<p><strong>Limitations.</strong> (1) Outages are scheduled for low-impact periods — effects are "as scheduled". (2) Limits are dispatch outputs, not physical capability. '
             '(3) Year-1 outage records are final-state; booking revisions are not modelled. (4) Family-to-link mapping and relevance are retrospective. (5) Two blocks per season cannot separate '
             'seasonal outage effects from network and plant changes between years. (6) Location is limited by the OSM name crosswalk (medium confidence) and description parsing (low). '
             '(7) Flow responds to prices and offers as well as limits. (8) Spillover and DUID pressure are descriptive decompositions, not causal paths.</p>')
    b.append('<p>Full definitions, every deviation from the plan and its log reference: <a href="METHODOLOGY.md">METHODOLOGY.md</a>. Plan, pilot summary and results summary: '
             '<a href="sources/PLAN.md">PLAN.md</a>, <a href="sources/pilot_summary.md">pilot_summary.md</a>, <a href="sources/RESULTS_SUMMARY.md">RESULTS_SUMMARY.md</a>.</p></div></section>')

    b.append('<div class="method"><p><strong>Constraint mechanics and outlook.</strong> The matched pairs behind every limit effect were replayed and saved (identical to the original '
             'matching). For each pair, the share of five-minute intervals in which each equation sets the link’s limit (reconstructed envelope) or binds (published |marginal value| > 1e-9, '
             'physical-run selection as in the base report) is compared between outage and matched control half-hours. Binding data were re-read from the monthly DISPATCHCONSTRAINT archives, '
             'hash-checked against the constraint studies, and reconcile exactly with the base report’s monthly binding counts. The outlook applies the as-of evidence to NOS bookings: '
             'P(equation active) = q × outage share + (1 − q) × matched normal share, where q is the chance the booking proceeds and the family applies. Its backtest re-runs the whole '
             'procedure from 12 monthly year-2 snapshots with a 21-day embargo on history. Limitations: year-1 bookings are final-state only; the outlook assumes past outage behaviour '
             'carries forward; marginal values depend on prices. Plan, methodology and log: <a href="sources/constraint_mechanics/PLAN.md">PLAN.md</a>, '
             '<a href="sources/constraint_mechanics/METHODOLOGY.md">METHODOLOGY.md</a>, <a href="sources/constraint_mechanics/EXECUTION_LOG.md">EXECUTION_LOG.md</a>.</p></div>')

    # record
    log = pd.DataFrame(d["log"])
    log["time"] = log.time.str.slice(0, 16).str.replace("T", " ")
    b.append(f'<section id="record"><div class="section-kicker">EXECUTION RECORD</div><h2>Every execution in this pass</h2><p>The campaign log records {len(log)} entries from {first_log} to {last_log}: '
             f'{(log.kind == "start").sum()} stage runs, {(log.kind == "decision").sum()} method decisions and {(log.kind == "check").sum()} one-off checks. Failed and partial runs are kept.</p>')
    b.append('<details><summary>Show the full execution log</summary>' + table(log, ["id", "time", "kind", "stage", "status", "note"], limit=200) + '</details>')
    if ch["log"]:
        log2 = pd.DataFrame(ch["log"])
        log2["time"] = log2.time.str.slice(0, 16).str.replace("T", " ")
        b.append(f'<p>The constraint-mechanics and outlook campaign (execution/nos_constraint_binding_v1) has its own log: {len(log2)} entries, '
                 f'{(log2.kind == "start").sum()} stage runs, {(log2.kind == "decision").sum()} decisions.</p>'
                 '<details><summary>Show the constraint-mechanics execution log</summary>' + table(log2, ["id", "time", "kind", "stage", "status", "note"], limit=300) + '</details>')
    b.append('<div class="downloads"><h3>Research data</h3><ul>' + "".join(f'<li><a href="downloads/{n}" download>{n}</a></li>' for n in list(outputs) + ch["downloads"]) + '</ul>'
             '<h3>Documents</h3><ul><li><a href="METHODOLOGY.md">METHODOLOGY.md</a></li><li><a href="sources/PLAN.md">PLAN.md</a></li><li><a href="sources/EXECUTION_LOG.md">EXECUTION_LOG.md</a></li>'
             '<li><a href="sources/RESULTS_SUMMARY.md">RESULTS_SUMMARY.md</a></li><li><a href="sources/pilot_summary.md">pilot_summary.md</a></li>'
             '<li><a href="../all_interconnector_regime_research_20260921/index.html">Base regime report</a></li></ul></div></section>')
    b.append('<footer><p>Prepared from cached campaign outputs · NEM market time UTC+10 · Sources: AEMO MMSDM and NEMWEB public data; OpenStreetMap contributors (ODbL). '
             'Descriptive retrospective research; no fitted forecasting model.</p></footer>')

    html = render_page("NOS outage effects on NEM interconnectors", "\n".join(b), plotly=True, accent="purple")
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    target = OUT / "index.html"
    target.unlink(missing_ok=True)          # overwriting in place intermittently fails on this host (Errno 22)
    target.write_text(html, encoding="utf-8")

    # manifest
    man = {"report_id": REPORT_ID, "built_at": pd.Timestamp.now(tz="Asia/Singapore").isoformat(), "theme_version": VERSION,
           "rebuild": "python scripts/build_nos_outage_report.py", "window": "(2024-09-01, 2026-09-01]", "inputs": {}, "outputs": {},
           "generator_sha256": rr.digest(Path(__file__)), "execution": "execution/nos_outage_regime_v1"}
    ins = sorted((DATA / "tables").glob("*.parquet")) + sorted(RT.glob("*.parquet")) + [DATA / f"{k}.parquet" for k in ["set_relevance", "k5_electrical", "outage_keys", "episodes", "episode_sets"]]
    ins += sorted((DATA / "raw" / "mmsdm").glob("*.parquet")) + [DATA / "raw/osm/au_power.json"]
    ins += sorted(cm.T.glob("*.parquet")) + sorted(cm.OUTLOOK.glob("*.parquet"))
    for p in ins:
        man["inputs"][str(p.relative_to(ROOT))] = {"bytes": p.stat().st_size, "sha256": rr.digest(p)}
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p.name != "build_manifest.json":
            man["outputs"][str(p.relative_to(OUT))] = {"bytes": p.stat().st_size, "sha256": rr.digest(p)}
    (OUT / "build_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    return {"report": str(OUT / "index.html"), "downloads": len(outputs), "supported_families": n_sup_fam, "lookup_rows": n_lk, "figures": 23 + len(forests) + ch["figures"], "constraint_downloads": len(ch["downloads"]),
            "binding_layer": ch["have_binding"], "outlook": ch["have_outlook"]}


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, default=str))
