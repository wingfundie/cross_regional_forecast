"""Chapters "Constraint mechanics during outages" and "Outage outlook" for the standalone NOS report.

Called by scripts/build_nos_outage_report.py; built only from cached tables in data/nos_binding_v1 (no model or
matching is re-run). Parts whose tables do not exist yet are skipped, so the Phase A release (limit-setters only) and
the full release share one builder. Plan: execution/nos_constraint_binding_v1/PLAN.md §8.
"""
from __future__ import annotations

import json
import sys
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
for p in [ROOT, ROOT / "scripts", ROOT / "scripts" / "report_theme"]:
    sys.path.insert(0, str(p))

import build_all_ic_regime_report as rr  # noqa: E402
from report_theme import figure_html, finding, metric, style_plotly  # noqa: E402

from nemic.experiments.nos_regime.common import DATA  # noqa: E402

BDATA = ROOT / "data" / "nos_binding_v1"
T = BDATA / "tables"
OUTLOOK = BDATA / "outlook"
EXEC2 = ROOT / "execution" / "nos_constraint_binding_v1"
NAMES = rr.IC_NAMES
ORDER = [NAMES[i] for i in rr.IC_ORDER]
DIRL = {"forward": "Forward", "reverse": "Reverse"}
ROWS12 = [f"{n} · {d}" for n in ORDER for d in ("Forward", "Reverse")]
IC_COL = {"QNI": "#5696b9", "Directlink": "#8fb9d3", "VNI": "#ce9a48", "Heywood": "#8370b4", "Murraylink": "#b5a7d8", "Basslink": "#268a87"}
LAYER_LABEL = {"setter": "sets the limit", "binding": "binds"}
LAYER_PLURAL = {"setter": "set the limit", "binding": "bind"}
table = rr.table_html


# --------------------------------------------------------------------------- data
def _cat(pattern: str) -> pd.DataFrame:
    parts = []
    for p in sorted(T.glob(pattern)):
        f = pd.read_parquet(p)
        if "empty" in f.columns and len(f.columns) == 1:
            continue
        parts.append(f)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def load() -> dict:
    d = {}
    for prefix in ["setter", "binding", "near", "system"]:
        for k in ["family", "topk", "by_regime", "transitions", "event_study", "placebo", "keys"]:
            d[f"{prefix}_{k}"] = _cat(f"{prefix}_{k}__*.parquet")
    for k in ["agreement", "footprint", "asknown", "mv"]:
        d[k] = _cat(f"{k}__*.parquet")
    g = T / "genonly_pressure.parquet"
    d["genonly"] = pd.read_parquet(g) if g.exists() else pd.DataFrame()
    if len(d["genonly"]) and "empty" in d["genonly"].columns:
        d["genonly"] = pd.DataFrame()
    rp = BDATA / "binding_reconciliation.parquet"          # shown only with a complete binding layer
    d["recon"] = pd.read_parquet(rp) if rp.exists() and len(d["binding_family"]) else pd.DataFrame()
    for name in ["pairs_gate", "scope", "backfill"]:
        p = BDATA / f"{name}.json"
        d[name] = json.loads(p.read_text()) if p.exists() else {}
    fam = pd.concat([pd.read_parquet(p) for p in sorted((DATA / "tables").glob("family_effects__*.parquet"))], ignore_index=True)
    d["v1_family"] = fam
    keys = pd.concat([pd.read_parquet(p) for p in sorted((DATA / "tables").glob("key_effects__*.parquet"))], ignore_index=True)
    d["v1_keys"] = keys
    for k in ["cells", "reliability", "mw", "family_inference", "thresholds", "scored", "predictions"]:
        p = OUTLOOK / f"backtest_{k}.parquet"
        d[f"bt_{k}"] = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    p = OUTLOOK / "backtest_meta.json"
    d["bt_meta"] = json.loads(p.read_text()) if p.exists() else []
    p = OUTLOOK / "embargo_confirmation.parquet"
    d["embargo"] = pd.read_parquet(p) if p.exists() else pd.DataFrame()
    latest = OUTLOOK / "live" / "latest.json"
    if latest.exists():
        meta = json.loads(latest.read_text())
        folder = BDATA / meta["folder"]
        d["live_meta"] = json.loads((folder / "meta.json").read_text())
        d["live"] = pd.read_parquet(folder / "outlook_outages.parquet")
        d["live_weekly"] = pd.read_csv(folder / "outlook_weekly.csv", parse_dates=["week"])
    else:
        d["live_meta"], d["live"], d["live_weekly"] = {}, pd.DataFrame(), pd.DataFrame()
    p = EXEC2 / "execution_log.jsonl"
    d["log"] = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []
    return d


def rowlab(df: pd.DataFrame) -> pd.Series:
    return df.name + " · " + df.direction.map(DIRL)


def plot(fig) -> str:
    return rr.plot_div(fig)


def fblock(fig, caption, note, href):
    return figure_html(plot(fig), caption, note, f"downloads/{href}" if href else None)


def pct(x, digits=0):
    return "—" if pd.isna(x) else f"{x * 100:.{digits}f}%"


def pp(x, digits=1):
    return "—" if pd.isna(x) else f"{x * 100:+.{digits}f} pp"


def sup(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame.tier.eq("supported")] if len(frame) and "tier" in frame else frame


# --------------------------------------------------------------------------- figures
def svg_layers() -> str:
    boxes = [("1", "Published binding", "AEMO's dispatch solution gives the equation a non-zero marginal value (|MV| > 1e-9).",
              "#5696b9"),
             ("2", "Limit-setter", "Of all equations that contain the link, this one forms the tightest upper or lower bound on its flow.",
              "#8370b4"),
             ("3", "Generator pressure", "Which units' dispatch changes tighten or relax that equation: b × ΔMW over 30 minutes.", "#ce9a48")]
    parts = ['<svg viewBox="0 0 900 250" role="img" aria-labelledby="cm-t cm-d" style="width:100%;height:auto;max-width:900px">'
             '<title id="cm-t">Three constraint layers</title><desc id="cm-d">Binding, limit-setting and generator pressure are separate '
             'observations of the same dispatch interval.</desc>']
    for i, (n, head, text, col) in enumerate(boxes):
        x = 12 + i * 296
        parts.append(f'<rect x="{x}" y="16" width="280" height="200" rx="10" fill="#fff" stroke="{col}" stroke-width="2"/>'
                     f'<circle cx="{x + 30}" cy="48" r="16" fill="{col}"/><text x="{x + 30}" y="54" text-anchor="middle" font-size="16" '
                     f'fill="#fff" font-family="Arial" font-weight="700">{n}</text>'
                     f'<text x="{x + 56}" y="54" font-size="17" font-family="Arial" font-weight="700" fill="#282b30">{escape(head)}</text>')
        words, line, lines = text.split(), "", []
        for w in words:
            if len(line) + len(w) > 34:
                lines.append(line); line = w
            else:
                line = (line + " " + w).strip()
        lines.append(line)
        for j, ln in enumerate(lines):
            parts.append(f'<text x="{x + 20}" y="{94 + j * 22}" font-size="14" font-family="Arial" fill="#444">{escape(ln)}</text>')
    parts.append('<text x="450" y="244" text-anchor="middle" font-size="13" font-family="Arial" fill="#636870">An equation can bind without setting '
                 'the link\'s limit, and set the limit without binding.</text></svg>')
    return '<figure><figcaption><span>Three separate constraint layers</span></figcaption><div class="chart-scroll">' + "".join(parts) + \
        '</div><p class="figure-note">The report keeps the three layers separate, as the base regime report does.</p></figure>'


def fig_own(fam: pd.DataFrame, layer: str) -> go.Figure:
    s = sup(fam).copy()
    s["row"] = rowlab(s)
    y = {r: i for i, r in enumerate(ROWS12)}
    fig = go.Figure()
    for arm, col, off, lab in [("own_control", "#9aa3ad", -0.17, "Matched outage-free periods"), ("own_treated", "#8370b4", 0.17, "Outage family invoked")]:
        fig.add_trace(go.Scatter(x=s[arm], y=s.row.map(y) + off, mode="markers", name=lab, marker=dict(size=8, color=col, opacity=.8),
                                 customdata=np.stack([s.GENCONSETID, s.row, s.own_treated, s.own_control, s.n_units / 2], axis=1),
                                 hovertemplate="%{customdata[1]} · %{customdata[0]}<br>outage %{customdata[2]:.0%} vs normal %{customdata[3]:.0%}"
                                               "<br>%{customdata[4]:.0f} matched hours<extra></extra>"))
    fig.update_yaxes(tickvals=list(y.values()), ticktext=list(y.keys()), autorange="reversed", zeroline=False)
    fig.update_xaxes(tickformat=".0%", range=[-0.02, 1.02])
    style_plotly(fig, f"How often the outage's own constraint set {LAYER_LABEL[layer]} (supported families)", 640)
    fig.update_layout(hovermode="closest", xaxis_title="Share of five-minute intervals")
    return fig


def headline_families(d: dict, n: int = 8) -> pd.DataFrame:
    v = d["v1_family"]
    v = v[v.tier.eq("supported")].assign(a=lambda x: x.effect_capacity.abs()).sort_values("a", ascending=False)
    return v.drop_duplicates(["name", "GENCONSETID"]).head(n)[["ic", "name", "direction", "GENCONSETID", "effect_capacity"]]


def fig_what(d: dict, layer: str) -> go.Figure | None:
    top = d[f"{layer}_topk"]
    if top.empty:
        return None
    heads = headline_families(d)
    titles = [f"{r.name} {DIRL[r.direction].lower()} · {r.GENCONSETID} ({r.effect_capacity:+.0f} MW)" for r in heads.itertuples()]
    fig = make_subplots(rows=4, cols=2, subplot_titles=titles, horizontal_spacing=.28, vertical_spacing=.09)
    for i, r in enumerate(heads.itertuples()):
        t = top[(top.ic == r.ic) & (top.direction == r.direction) & (top.GENCONSETID == r.GENCONSETID)]
        t = t.sort_values("treated_share", ascending=False).head(5).iloc[::-1]
        rr_, cc = i // 2 + 1, i % 2 + 1
        fig.add_trace(go.Bar(y=t.constraint, x=t.control_share, orientation="h", name="Matched normal", marker_color="#9aa3ad",
                             showlegend=i == 0, legendgroup="c", hovertemplate="%{y}: %{x:.0%} normal<extra></extra>"), rr_, cc)
        fig.add_trace(go.Bar(y=t.constraint, x=t.treated_share, orientation="h", name="Outage invoked", marker_color="#8370b4",
                             showlegend=i == 0, legendgroup="t", hovertemplate="%{y}: %{x:.0%} during outage<extra></extra>"), rr_, cc)
    fig.update_xaxes(tickformat=".0%")
    style_plotly(fig, f"Which equations {LAYER_PLURAL[layer]} during the eight largest-effect outage families", 1200)
    fig.update_layout(barmode="group", hovermode="closest", margin=dict(l=150))
    fig.update_annotations(font_size=12)
    return fig


def fig_displacement(d: dict, layer: str) -> go.Figure | None:
    top = sup(d[f"{layer}_topk"])
    if top.empty:
        return None
    sn = top[top["class"].eq("system_normal_other")].copy()
    sn["row"] = sn.name + " " + sn.direction.map({"forward": "fwd", "reverse": "rev"}) + " · " + sn.GENCONSETID
    fams = sn.groupby("row").diff_pp.min().sort_values().head(24).index
    eqs = sn[sn.row.isin(fams)].groupby("constraint").diff_pp.apply(lambda s: s.abs().max()).sort_values(ascending=False).head(14).index
    m = sn[sn.row.isin(fams) & sn.constraint.isin(eqs)].pivot_table(index="row", columns="constraint", values="diff_pp").reindex(index=fams, columns=eqs)
    fig = go.Figure(go.Heatmap(z=m.to_numpy(), x=m.columns, y=m.index, colorscale="RdBu", zmid=0, colorbar=dict(title="pp"),
                               hovertemplate="%{y}<br>%{x}: %{z:+.1f} pp<extra></extra>"))
    style_plotly(fig, f"Displacement: system-normal equations that {LAYER_PLURAL[layer]} less (red) or more (blue) during each outage", 820)
    fig.update_layout(hovermode="closest", margin=dict(l=260, b=150))
    fig.update_xaxes(tickangle=-40)
    return fig


def fig_agreement(d: dict) -> go.Figure | None:
    a = sup(d["agreement"])
    if a.empty:
        return None
    a = a.assign(row=rowlab(a))
    cats = [("treated_binds_and_sets", "Binds and sets the limit", "#8370b4"), ("treated_binds_only", "Binds only", "#5696b9"),
            ("treated_sets_only", "Sets the limit only", "#ce9a48"), ("treated_neither", "Neither", "#dfe3eb")]
    g = a.groupby("row")[[c for c, _, _ in cats]].mean().reindex(ROWS12)
    fig = go.Figure()
    for c, lab, col in cats:
        fig.add_trace(go.Bar(y=g.index, x=g[c], orientation="h", name=lab, marker_color=col, hovertemplate="%{y}: %{x:.0%}<extra>" + lab + "</extra>"))
    fig.update_xaxes(tickformat=".0%", range=[0, 1])
    fig.update_yaxes(autorange="reversed")
    style_plotly(fig, "While an outage family is invoked, does its own set bind, set the limit, both or neither?", 600)
    fig.update_layout(barmode="stack", hovermode="closest")
    return fig


def fig_events(d: dict, layer: str) -> go.Figure | None:
    ev = d[f"{layer}_event_study"]
    if ev.empty:
        return None
    ev = sup(ev)
    ev = ev[ev.clean]
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Around invocation start", "Around invocation end"], shared_yaxes=True)
    for j, anchor in enumerate(["start", "end"], 1):
        g = ev[ev.anchor.eq(anchor)].groupby(["name", "offset_h"]).apply(
            lambda x: np.average(x.own_share.fillna(0), weights=x.n_spells.clip(lower=1)), include_groups=False).rename("v").reset_index()
        for n in ORDER:
            q = g[g.name.eq(n)]
            if q.empty:
                continue
            fig.add_trace(go.Scatter(x=q.offset_h, y=q.v, name=n, line=dict(color=IC_COL[n], width=2), showlegend=j == 1, legendgroup=n,
                                     hovertemplate=n + " %{x:+.1f} h: %{y:.0%}<extra></extra>"), 1, j)
        fig.add_vline(x=0, line_color="#888", line_width=1, col=j)
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(title_text="Hours from the invocation boundary")
    style_plotly(fig, f"How quickly the outage's own set starts and stops being the one that {LAYER_LABEL[layer]} (clean spells)", 520)
    fig.update_layout(hovermode="closest")
    return fig


def fig_regime(d: dict, layer: str) -> go.Figure | None:
    br = sup(d[f"{layer}_by_regime"])
    if br.empty:
        return None
    br = br.assign(row=rowlab(br))
    out = []
    for dim, vals in [("season", ["Summer", "Autumn", "Winter", "Spring"]), ("day_period", ["Overnight", "Morning peak", "Solar period", "Evening peak"])]:
        g = br[br.dimension.eq(dim) & br.value.isin(vals)]
        g = g.groupby(["row", "value"]).apply(lambda x: np.average(x.own_diff, weights=x.n_units), include_groups=False).rename("v").reset_index()
        out.append(g.pivot(index="row", columns="value", values="v").reindex(index=ROWS12, columns=vals))
    m = pd.concat(out, axis=1)
    fig = go.Figure(go.Heatmap(z=m.to_numpy() * 100, x=list(m.columns), y=m.index, colorscale="Purples", colorbar=dict(title="pp"),
                               hovertemplate="%{y} · %{x}: %{z:+.1f} pp<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    style_plotly(fig, f"When the own set {LAYER_LABEL[layer]}: extra share over matched normal, by season and time of day", 600)
    fig.update_layout(hovermode="closest")
    return fig


def fig_weather(d: dict, layer: str) -> go.Figure | None:
    br = sup(d[f"{layer}_by_regime"])
    if br.empty:
        return None
    fig = make_subplots(rows=1, cols=3, subplot_titles=["Temperature", "VRE difference", "Residual-demand difference"], shared_yaxes=True)
    lab = {"0": "Low (≤P20)", "1": "Normal", "2": "High (≥P80)"}
    for j, dim in enumerate(["tbin", "vbin", "rbin"], 1):
        g = br[br.dimension.eq(dim) & br.value.isin(["0", "1", "2"])]
        g = g.groupby(["name", "value"]).apply(lambda x: np.average(x.own_diff, weights=x.n_units), include_groups=False).rename("v").reset_index()
        for n in ORDER:
            q = g[g.name.eq(n)]
            if q.empty:
                continue
            fig.add_trace(go.Bar(x=q.value.map(lab), y=q.v, name=n, marker_color=IC_COL[n], showlegend=j == 1, legendgroup=n,
                                 hovertemplate=n + " %{x}: %{y:+.1%}<extra></extra>"), 1, j)
    fig.update_yaxes(tickformat="+.0%")
    style_plotly(fig, f"Extra own-set share by weather and VRE regime (weighted mean over supported families)", 520)
    fig.update_layout(barmode="group", hovermode="closest")
    return fig


def fig_footprint(d: dict) -> go.Figure | None:
    fp = d["footprint"]
    if fp.empty:
        return None
    fp = fp.assign(col=fp.target_name + " · " + fp.direction.map(DIRL))
    s = fp[fp.tier.eq("supported")]
    fams = s.groupby("GENCONSETID").any_binding_diff.apply(lambda x: x.abs().max()).sort_values(ascending=False).head(30).index
    m = s[s.GENCONSETID.isin(fams)].pivot_table(index="GENCONSETID", columns="col", values="any_binding_diff").reindex(index=fams, columns=ROWS12)
    fig = go.Figure(go.Heatmap(z=m.to_numpy() * 100, x=list(m.columns), y=m.index, colorscale="RdBu_r", zmid=0, colorbar=dict(title="pp"),
                               hovertemplate="%{y} → %{x}: %{z:+.1f} pp<extra></extra>"))
    style_plotly(fig, "Binding footprint: change in the share of intervals with any binding equation on each link (supported cells)", 860)
    fig.update_layout(hovermode="closest", margin=dict(l=190, b=130))
    fig.update_xaxes(tickangle=-35)
    return fig


def fig_mv(d: dict) -> go.Figure | None:
    mv = sup(d["mv"])
    if mv.empty:
        return None
    mv = mv.assign(row=rowlab(mv))
    fig = go.Figure()
    for arm, col, lab in [("control", "#9aa3ad", "Matched normal"), ("treated", "#8370b4", "Outage invoked")]:
        g = mv.groupby("row")[f"{arm}_share_gt_own_p90"].mean().reindex(ROWS12)
        fig.add_trace(go.Bar(y=g.index, x=g, orientation="h", name=lab, marker_color=col, hovertemplate="%{y}: %{x:.0%}<extra>" + lab + "</extra>"))
    fig.update_xaxes(tickformat=".0%")
    fig.update_yaxes(autorange="reversed")
    style_plotly(fig, "How hard own-set equations bind: share of binding intervals above the equation's own outage-free P90 |MV|", 600)
    fig.update_layout(barmode="group", hovermode="closest")
    return fig


def fig_asknown(d: dict) -> go.Figure | None:
    ak = sup(d["asknown"])
    if ak.empty:
        return None
    ak = ak[ak.lag_days.eq(7)]
    g = ak.groupby(["name", "group"]).apply(lambda x: np.average(x.own_treated, weights=x.n_units), include_groups=False).rename("v").reset_index()
    fig = go.Figure()
    for grp, col, lab in [("booked_in_advance", "#8370b4", "Outage already in NOS 7 days before"), ("not_booked_in_advance", "#ce9a48", "Not in NOS 7 days before")]:
        q = g[g.group.eq(grp)].set_index("name").reindex(ORDER)
        fig.add_trace(go.Bar(x=q.index, y=q.v, name=lab, marker_color=col, hovertemplate="%{x}: %{y:.0%}<extra>" + lab + "</extra>"))
    fig.update_yaxes(tickformat=".0%")
    style_plotly(fig, "Own-set binding share in year 2: outages known a week ahead vs not", 480)
    fig.update_layout(barmode="group", hovermode="closest")
    return fig


def fig_skill(d: dict) -> go.Figure | None:
    c = d["bt_cells"]
    if c.empty:
        return None
    c = c[c.layer.eq("binding")].assign(row=lambda x: x.name + " · " + x.direction.map(DIRL))
    bands = ["0-7", "8-30", "31-90", "91-365"]
    m = c.pivot_table(index="row", columns="lead_band", values="skill_vs_normal").reindex(index=ROWS12, columns=bands)
    n = c.pivot_table(index="row", columns="lead_band", values="rows").reindex(index=ROWS12, columns=bands)
    txt = [[("—" if pd.isna(v) else f"{v:+.0%}") + ("" if pd.isna(k) else f"<br>n={int(k)}") for v, k in zip(r1, r2)] for r1, r2 in zip(m.to_numpy(), n.to_numpy())]
    fig = go.Figure(go.Heatmap(z=m.to_numpy(), x=[f"{b} days" for b in bands], y=m.index, colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
                               text=txt, texttemplate="%{text}", colorbar=dict(title="Skill", tickformat="+.0%"),
                               hovertemplate="%{y} · %{x}<br>Brier skill vs normal rate: %{z:+.1%}<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    style_plotly(fig, "Backtest: Brier skill of the binding outlook over the equation's normal rate, by lead time", 640)
    fig.update_layout(hovermode="closest")
    return fig


def fig_reliability(d: dict) -> go.Figure | None:
    r = d["bt_reliability"]
    if r.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#aaa", dash="dot"), name="Perfect calibration", hoverinfo="skip"))
    for layer, col in [("binding", "#5696b9"), ("setter", "#8370b4")]:
        q = r[r.layer.eq(layer)]
        fig.add_trace(go.Scatter(x=q.p_mean, y=q.y_mean, mode="lines+markers", name=f"P({LAYER_LABEL[layer]})", marker=dict(size=np.clip(np.sqrt(q.n), 6, 22), color=col),
                                 customdata=q.n, hovertemplate="predicted %{x:.1%} → realised %{y:.1%}<br>n=%{customdata}<extra></extra>"))
    fig.update_xaxes(tickformat=".0%", title="Predicted share of the outage's intervals", range=[0, .8])
    fig.update_yaxes(tickformat=".0%", title="Realised share", range=[0, .8])
    style_plotly(fig, "Backtest calibration: predicted vs realised binding and limit-setting shares", 560)
    fig.update_layout(hovermode="closest")
    return fig


def fig_calendar(d: dict) -> go.Figure | None:
    lv = d["live"]
    if lv.empty or "binding_p_1" not in lv:
        return None
    q = lv.dropna(subset=["binding_eq_1"]).copy()
    q = q[q.tier.isin(["supported", "indicative"])]
    if q.empty:
        return None
    q["row"] = rowlab(q)
    y = {r: i for i, r in enumerate(ROWS12)}
    q = q.sort_values("family_probability", ascending=False).drop_duplicates(["OUTAGEID", "ic", "direction"])
    fig = go.Figure(go.Scatter(x=q.booked_start, y=q.row.map(y) + np.random.default_rng(1).uniform(-.25, .25, len(q)), mode="markers",
                               marker=dict(size=np.clip(q.limit_change_mw.abs().fillna(20) / 25, 5, 26), color=q.binding_p_1, colorscale="Purples",
                                           cmin=0, cmax=max(.3, float(q.binding_p_1.max())), showscale=True, colorbar=dict(title="P(top eq.)", tickformat=".0%"),
                                           line=dict(width=.5, color="#555")),
                               customdata=np.stack([q.OUTAGEID, q.description.fillna(q.asset), q.family, q.family_source, q.binding_eq_1,
                                                    q.binding_p_1, q.limit_change_mw.fillna(np.nan), q.skill_status, q.row], axis=1),
                               hovertemplate="%{customdata[8]}<br>Outage %{customdata[0]}: %{customdata[1]}<br>%{x|%d %b %Y}<br>Family %{customdata[2]} (%{customdata[3]})"
                                             "<br>Most likely binding: %{customdata[4]} (%{customdata[5]:.0%})<br>Limit change if invoked: %{customdata[6]:+.0f} MW"
                                             "<br>%{customdata[7]}<extra></extra>"))
    fig.update_yaxes(tickvals=list(y.values()), ticktext=list(y.keys()), autorange="reversed")
    style_plotly(fig, "Booked outages over the next 12 months and the constraints they are likely to bring", 700)
    fig.update_layout(hovermode="closest")
    return fig


# --------------------------------------------------------------------------- tables
def lookup_table(d: dict) -> tuple[str, pd.DataFrame]:
    parts = []
    for layer in ["setter", "binding"]:
        k = d[f"{layer}_keys"]
        f = d[f"{layer}_family"]
        if len(k):
            parts.append(k.assign(layer=layer)[["ic", "name", "direction", "level", "key", "families", "layer", "n_units", "own_treated", "own_control", "top3"]])
        if len(f):
            top = d[f"{layer}_topk"]
            t3 = (top.sort_values("treated_share", ascending=False).groupby(["ic", "direction", "GENCONSETID"])
                  .apply(lambda g: "; ".join(f"{r.constraint} ({r.treated_share:.0%} vs {r.control_share:.0%})" for r in g.head(3).itertuples()),
                         include_groups=False).rename("top3").reset_index()) if len(top) else pd.DataFrame(columns=["ic", "direction", "GENCONSETID", "top3"])
            ff = f.merge(t3, on=["ic", "direction", "GENCONSETID"], how="left")
            parts.append(ff.assign(layer=layer, level="K2", key=ff.GENCONSETID)[["ic", "name", "direction", "level", "key", "families", "layer", "n_units",
                                                                               "own_treated", "own_control", "top3"]])
    if not parts:
        return "", pd.DataFrame()
    a = pd.concat(parts, ignore_index=True)
    w = a.pivot_table(index=["ic", "name", "direction", "level", "key", "families"], columns="layer",
                      values=["n_units", "own_treated", "own_control", "top3"], aggfunc="first")
    w.columns = [f"{value}_{layer}" for value, layer in w.columns]
    w = w.reset_index()
    vk = d["v1_keys"][["ic", "direction", "level", "key", "tier", "treated_hours"]]
    vf = d["v1_family"][["ic", "direction", "GENCONSETID", "tier", "treated_hours"]].rename(columns={"GENCONSETID": "key"}).assign(level="K2")
    w = w.merge(pd.concat([vk, vf], ignore_index=True), on=["ic", "direction", "level", "key"], how="left")
    w = w[w.tier.eq("supported") & (w.treated_hours >= 24)]
    # Q8: asset-level binding statements need >= 30 treated five-minute intervals in which the named equation binds
    if "own_treated_binding" in w:
        n5 = pd.to_numeric(w.get("n_units_binding"), errors="coerce") * 6 * pd.to_numeric(w.own_treated_binding, errors="coerce")
        asset = w.level.isin(["K1", "K1xK2"])
        w["binding_gate"] = np.where(asset & (n5 < 30), "below asset gate: see family row", "ok")
    rows = []
    for r in w.sort_values(["name", "level", "key", "direction"]).itertuples():
        def cell(layer):
            t, c = getattr(r, f"own_treated_{layer}", np.nan), getattr(r, f"own_control_{layer}", np.nan)
            top = getattr(r, f"top3_{layer}", "")
            if getattr(r, "binding_gate", "ok") != "ok" and layer == "binding":
                return '<td colspan="2"><small>Too few binding intervals at asset level — use the family row</small></td>'
            return (f'<td>{"—" if pd.isna(t) else f"{t:.0%}"}<br><small>normal {"—" if pd.isna(c) else f"{c:.0%}"}</small></td>'
                    f'<td><small>{escape(str(top if isinstance(top, str) else "—"))}</small></td>')
        rows.append(f'<tr><td>{escape(r.name)}</td><td>{escape(DIRL[r.direction])}</td><td>{escape(r.level)}</td><td><strong>{escape(str(r.key))}</strong>'
                    f'<br><small>{escape(str(r.families or ""))[:160]}</small></td>{cell("setter")}{cell("binding") if "own_treated_binding" in w else ""}'
                    f'<td>{r.treated_hours:,.0f} h</td></tr>')
    head = ('<th>Connector</th><th>Direction</th><th>Level</th><th>Asset or family</th><th>Own set sets limit</th><th>Top-3 limit-setters (outage vs normal)</th>'
            + ('<th>Own set binds</th><th>Top-3 binding equations</th>' if "own_treated_binding" in w else "") + '<th>Evidence</th>')
    html = ('<input id="cl-q" class="lookup-search" type="search" placeholder="Filter by asset, family, equation, connector…" aria-label="Filter the constraint lookup" '
            'oninput="(function(q){q=q.toLowerCase();var n=0;document.querySelectorAll(\'#cl tbody tr\').forEach(function(r){var s=r.textContent.toLowerCase().indexOf(q)>-1;'
            'r.style.display=s?\'\':\'none\';if(s)n++;});document.getElementById(\'cl-n\').textContent=n;})(this.value)">'
            f'<p class="small"><span id="cl-n">{len(rows)}</span> rows · supported entries with at least 24 matched hours</p>'
            f'<div class="table-wrap lookup-wrap" tabindex="0"><table id="cl"><thead><tr>{head}</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>'
            '<style>#cl{min-width:1300px}#cl td{white-space:normal;min-width:80px}#cl td small{color:#667}#cl thead th{position:sticky;top:0;background:#ececf3;z-index:1}</style>')
    return html, w


def next_weeks_table(d: dict) -> str:
    lv = d["live"]
    if lv.empty:
        return ""
    as_of = pd.Timestamp(d["live_meta"]["as_of"])
    q = lv[(lv.booked_start <= as_of + pd.Timedelta(weeks=8)) & lv.tier.isin(["supported", "indicative"])].dropna(subset=["binding_eq_1"]).copy()
    q = q.sort_values(["booked_start", "name"]).drop_duplicates(["OUTAGEID", "ic", "direction"])
    if q.empty:
        return "<p>No booked outages with supported constraint evidence start in the next eight weeks.</p>"
    q["when"] = q.booked_start.dt.strftime("%d %b %H:%M") + " → " + q.booked_end.dt.strftime("%d %b %H:%M")
    q["link"] = rowlab(q)
    q["what"] = q.description.fillna(q.asset)
    q["fam"] = q.family + np.where(q.family_source.eq("inferred"), " (inferred " + q.family_probability.map(lambda x: f"{x:.0%}") + ")", "")
    q["binds"] = q.binding_eq_1.fillna("—") + " · " + q.binding_p_1.map(lambda x: "—" if pd.isna(x) else f"{x:.0%}")
    q["sets"] = q.get("setter_eq_1", pd.Series(index=q.index, dtype=object)).fillna("—")
    q["mw"] = q.limit_change_mw.map(lambda x: "—" if pd.isna(x) else f"{x:+.0f}")
    return table(q, ["when", "link", "what", "fam", "binds", "sets", "mw", "tier", "skill_status"], limit=80)


# --------------------------------------------------------------------------- downloads
def write_downloads(d: dict, dl: Path, lookup: pd.DataFrame) -> list[str]:
    out = {}
    for prefix in ["setter", "binding", "near", "system"]:
        for k, ext in [("family", "csv"), ("topk", "csv.gz"), ("by_regime", "csv"), ("transitions", "csv.gz"), ("event_study", "csv.gz"), ("placebo", "csv")]:
            f = d[f"{prefix}_{k}"]
            if len(f):
                out[f"nos_{prefix}_{k}.{ext}"] = f
    for k, name in [("agreement", "nos_layer_agreement.csv"), ("footprint", "nos_binding_footprint.csv"), ("asknown", "nos_binding_asknown.csv"),
                    ("mv", "nos_binding_marginal_value.csv"), ("genonly", "nos_genonly_pressure.csv"), ("recon", "nos_binding_reconciliation.csv"),
                    ("bt_cells", "nos_outlook_backtest_scores.csv"), ("bt_reliability", "nos_outlook_backtest_reliability.csv"),
                    ("bt_mw", "nos_outlook_backtest_mw_error.csv"), ("bt_family_inference", "nos_outlook_backtest_family_inference.csv"),
                    ("embargo", "nos_outlook_embargo_confirmation.csv"), ("live", "nos_outlook_outages.csv"), ("live_weekly", "nos_outlook_weekly.csv")]:
        f = d.get(k)
        if isinstance(f, pd.DataFrame) and len(f):
            out[name] = f
    if len(lookup):
        out["nos_constraint_lookup.csv"] = lookup
    for name, frame in out.items():
        target = dl / name
        tmp = target.with_name(target.name + ".tmp")
        frame.to_csv(tmp, index=False, compression={"method": "gzip", "mtime": 0} if name.endswith(".gz") else None)
        tmp.replace(target)
    return list(out)


# --------------------------------------------------------------------------- chapters
def build(dl: Path) -> dict:
    d = load()
    sf, bf = d["setter_family"], d["binding_family"]
    have_bind = len(bf) > 0
    lk_html, lookup = lookup_table(d)
    downloads = write_downloads(d, dl, lookup)
    figs = 0
    b = ['<section id="constraints"><div class="section-kicker">CONSTRAINT MECHANICS</div><h2>Which equations bind and set the limit during each outage</h2>']
    s1 = sup(sf)
    b.append('<p>The limit effects above say how far a link\'s limit moves when an outage family is invoked. This chapter asks which constraint equations '
             'are responsible. It uses the same matched half-hours as the limit effects: every outage half-hour is compared with up to five outage-free '
             'half-hours from the same season, day type, weather and VRE bin and the same set of other active outage families. Shares are the fraction of '
             'five-minute intervals in which an equation is active; differences are outage minus matched normal, in percentage points (pp), with day-block '
             'bootstrap 95% intervals.</p>')
    b.append(svg_layers())
    if len(s1):
        fw = s1
        m1 = f"{fw.own_treated.median():.0%}"
        m2 = f"{fw.own_control.median():.0%}"
        mets = [metric("Supported family-directions", f"{len(fw):,}", "matched comparisons with setter evidence"),
                metric("Own set sets the limit", m1, f"median share while invoked (normal {m2})")]
        if have_bind:
            bw = sup(bf)
            mets.append(metric("Own set binds", f"{bw.own_treated.median():.0%}", f"median share while invoked (normal {bw.own_control.median():.0%})"))
            if len(d["recon"]):
                mets.append(metric("Binding intervals reconciled", f"{int(d['recon'].binding_new.sum()):,}",
                                   "equal to the regime report, every connector and month"))
        b.append('<section class="metrics">' + "".join(mets) + '</section>')
        dom = (fw.own_treated >= .5).mean()
        low = (fw.own_treated < .1).mean()
        b.append(f'<p>Across the {len(fw):,} supported family-directions, the outage\'s own set sets the link\'s limit in a median {m1} of intervals while invoked. '
                 f'It is the dominant setter (at least half the time) in {dom:.0%} of cases, and in {low:.0%} it sets the limit less than a tenth of the time. '
                 'In those cases a system-normal equation typically stays in charge and the outage acts by tightening it rather than by replacing it.</p>')
        b.append(fblock(fig_own(sf, "setter"), "Own-set limit-setting share: outage vs matched normal", "Each pair of points is one supported family-direction.",
                        "nos_setter_family.csv")); figs += 1
    if have_bind:
        bw = sup(bf)
        b.append(f'<p>Published binding tells a different story. The own set binds in a median {bw.own_treated.median():.0%} of invoked intervals '
                 f'(matched normal {bw.own_control.median():.0%}); the share of intervals with any binding equation on the link rises by a median '
                 f'{bw.any_diff.median() * 100:+.1f} pp.</p>')
        b.append(fblock(fig_own(bf, "binding"), "Own-set binding share: outage vs matched normal", "Binding = |marginal value| > 1e-9 in the dispatch solution.",
                        "nos_binding_family.csv")); figs += 1
    for layer in (["binding"] if have_bind else []) + ["setter"]:
        f = fig_what(d, layer)
        if f is not None:
            b.append(fblock(f, f"What {LAYER_LABEL[layer]} during the largest-effect outages".replace("What sets the limit", "What sets the limit").replace("What binds", "What binds"), "Top five equations by share during the outage, against matched normal periods.",
                            f"nos_{layer}_topk.csv.gz")); figs += 1
    f = fig_displacement(d, "binding" if have_bind else "setter")
    if f is not None:
        b.append(fblock(f, "Displacement of system-normal equations", "Rows: the 24 family-directions with the largest drop; columns: the 14 most-moved system-normal equations.",
                        f"nos_{'binding' if have_bind else 'setter'}_topk.csv.gz")); figs += 1
    f = fig_agreement(d)
    if f is not None:
        a = sup(d["agreement"])
        b.append(f'<p>The two layers often disagree. Averaged over supported families, the own set both binds and sets the limit in {a.treated_binds_and_sets.mean():.0%} '
                 f'of invoked intervals, binds without setting the limit in {a.treated_binds_only.mean():.0%} and sets it without binding in {a.treated_sets_only.mean():.0%}.</p>')
        b.append(fblock(f, "Layer agreement while invoked", "Mean over supported family-directions of five-minute joint shares.", "nos_layer_agreement.csv")); figs += 1
    for layer in (["binding"] if have_bind else []) + ["setter"]:
        f = fig_events(d, layer)
        if f is not None:
            b.append(fblock(f, f"Onset and release: own set {LAYER_LABEL[layer]}", "Spell-weighted mean over supported families; clean spells have no other relevant family starting or ending within 2 h.",
                            f"nos_{layer}_event_study.csv.gz")); figs += 1
        break
    lay = "binding" if have_bind else "setter"
    for fn, cap, note in [(fig_regime, "Seasonal and daily pattern", "Weighted by matched units; columns are separate breakdowns, not a joint table."),
                          (fig_weather, "Weather and VRE regimes", "Regimes use the base report's P20/P80 bins at the outage half-hour.")]:
        f = fn(d, lay)
        if f is not None:
            b.append(fblock(f, cap, note, f"nos_{lay}_by_regime.csv")); figs += 1
    for fn, cap, note, href in [(fig_footprint, "Binding footprint across links", "Includes families relevant to other links (spillover); only supported cells coloured.", "nos_binding_footprint.csv"),
                                (fig_mv, "Marginal value context", "Descriptive only: marginal values scale with prices and are never summed.", "nos_binding_marginal_value.csv"),
                                (fig_asknown, "Known in advance vs late bookings", "Year 2 only, where half-hourly NOS snapshots exist.", "nos_binding_asknown.csv")]:
        f = fn(d)
        if f is not None:
            b.append(fblock(f, cap, note, href)); figs += 1
    go_ = d["genonly"]
    bf_ = d["backfill"]
    if bf_:
        b.append(f'<p><strong>Equations without a link term.</strong> {bf_.get("undefined_before", 0)} member equations of relevant outage sets had no definition in the '
                 f'study-window archives because they were last versioned earlier; their definitions were read from the archives of their version dates. '
                 f'{bf_.get("with_ic_term_after", 0)} turned out to contain a link term, {bf_.get("gen_only", 0)} are generator-only and '
                 f'{bf_.get("still_undefined", 0)} could not be resolved.</p>')
    if len(go_):
        g = go_.sort_values("excess_tightening", ascending=False).head(25)
        b.append('<p>Generator-only own-set equations and the units that tighten them most while the outage is invoked (slack consumed per half-hour, MW):</p>'
                 + table(g, ["GENCONSETID", "equation", "DUID", "factor", "tightening_per_hh_treated", "tightening_per_hh_base", "excess_tightening"],
                         formats={"factor": lambda x: f"{x:.3f}", "tightening_per_hh_treated": lambda x: f"{x:.1f}", "tightening_per_hh_base": lambda x: f"{x:.1f}",
                                  "excess_tightening": lambda x: f"{x:+.1f}"}, limit=25))
    b.append('<h3>Constraint lookup</h3><p>For a specific asset or family: how often its own constraint set sets the limit and binds while invoked, and which '
             'equations lead. Asset-level binding figures appear only where the named equation binds in at least 30 matched five-minute intervals; otherwise use the family row.</p>')
    b.append(lk_html)
    b.append('</section>')

    # ---------------- outlook
    o = ['<section id="outlook"><div class="section-kicker">OUTAGE OUTLOOK</div><h2>Booked outages over the next 12 months</h2>']
    if d["live_meta"]:
        lm, lv = d["live_meta"], d["live"]
        sk = lv.skill_status.eq("skilful").mean() if len(lv) else np.nan
        o.append(f'<section class="callout scope-note"><strong>Research outlook.</strong> Built from NOS snapshot <code>{escape(lm["report_member"])}</code> generated '
                 f'{escape(lm["generated_nem"])} (NEM time), using only history before that time. Numbers are historical frequencies from matched past outages, '
                 f'weighted by the chance the booking goes ahead and, for bookings without a linked constraint set, by the chance the inferred family is used. '
                 f'{sk:.0%} of rows fall in lead-time and link cells where the backtest showed skill; elsewhere the matched normal rate is shown instead. '
                 'This is not an operational forecast.</section>')
        f = fig_calendar(d)
        if f is not None:
            o.append(fblock(f, "12-month outage calendar", "Marker size: limit change if invoked; colour: chance the most likely equation binds.", "nos_outlook_outages.csv")); figs += 1
        o.append('<h3>Next eight weeks</h3>' + next_weeks_table(d))
        wk = d["live_weekly"]
        if len(wk):
            o.append('<details><summary>Weekly summary by link</summary>' + table(wk.assign(week=wk.week.dt.strftime("%d %b %Y")),
                     ["week", "name", "direction", "outages", "supported_rows", "largest_reduction_mw", "top_binding_eq", "top_binding_p"],
                     formats={"largest_reduction_mw": lambda x: f"{x:+.0f}", "top_binding_p": lambda x: f"{x:.0%}"}, limit=200) + '</details>')
    if len(d["bt_cells"]):
        c = d["bt_cells"]
        cb = c[c.layer.eq("binding")]
        fi = d["bt_family_inference"].iloc[0] if len(d["bt_family_inference"]) else None
        o.append('<h3>Backtest</h3>')
        o.append(f'<p>The outlook procedure was re-run from {len(d["bt_meta"])} monthly NOS snapshots in year 2, each time using only data available before the snapshot '
                 f'(matched outage half-hours embargoed 21 days before it). {int(cb.skilful.sum())} of {len(cb)} lead-time × link-direction cells beat the '
                 'equation\'s normal season × half-hour rate on Brier score with at least 30 scored rows.'
                 + (f' Family inference for bookings without a linked set picked a realised family first {fi.top1_accuracy:.0%} of the time and within its top three '
                    f'{fi.top3_accuracy:.0%} of the time ({int(fi.inferred_bookings):,} bookings).' if fi is not None else '') + '</p>')
        for fn, cap, note, href in [(fig_skill, "Skill by lead time", "Brier skill = 1 − Brier(outlook) / Brier(normal rate); n = scored rows.", "nos_outlook_backtest_scores.csv"),
                                    (fig_reliability, "Calibration", "Bins of predicted share; marker size ∝ √n.", "nos_outlook_backtest_reliability.csv")]:
            f = fn(d)
            if f is not None:
                o.append(fblock(f, cap, note, href)); figs += 1
        if len(d["bt_mw"]):
            o.append('<details><summary>Limit-change error by lead time</summary>' + table(d["bt_mw"], ["lead_band", "name", "direction", "n", "mae_outlook", "mae_zero_change", "mae_lastyear"],
                     formats={k: (lambda x: f"{x:.0f}") for k in ["mae_outlook", "mae_zero_change", "mae_lastyear"]}, limit=60) + '</details>')
        th = d["bt_thresholds"]
        if len(th):
            ev = c[c.layer.eq("binding")]
            o.append(f'<p>Alerts ("the named equation will bind in at least 5% of the outage") use a threshold fitted on the first six origins '
                     f'({", ".join(f"{r.layer} {r.alert_threshold:.2f}" for r in th.itertuples())}) and are scored on the last six: recall '
                     f'{np.nanmean(ev.recall):.0%}, precision {np.nanmean(ev.precision):.0%}, {int(ev.false_alerts.sum()):,} false alerts (cell means).</p>')
        if len(d["embargo"]):
            e = d["embargo"]
            o.append(f'<p><strong>Leakage check.</strong> At two origins the full v1 matched comparison was re-run with data cut at the snapshot. For {len(e)} supported '
                     f'family-directions the re-run and embargoed estimates agree (each inside the other\'s 95% interval) in {e.agree.mean():.0%} of cases.</p>')
    elif not d["live_meta"]:
        o.append('<p>The outlook appears here once the binding layer and its backtest are complete.</p>')
    o.append('</section>')

    # ---------------- robustness add-ons
    r = []
    if d["pairs_gate"]:
        r.append(f'<p><strong>Matched pairs.</strong> The v1 matching was replayed to save the matched pairs; replayed control medians and key-level effects are identical '
                 f'to v1 for all six links ({sum(v["units_v1"] for k, v in d["pairs_gate"].items() if isinstance(v, dict)):,} outage half-hours).</p>')
    for layer in ["setter", "binding"]:
        pl = d[f"{layer}_placebo"]
        if len(pl):
            r.append(f'<p><strong>Placebo ({layer}).</strong> Shifting each outage family\'s invoked windows by ±7 days, the own-set {LAYER_LABEL[layer]} difference '
                     f'is indistinguishable from zero for {pl.placebo_clean.mean():.0%} of {len(pl):,} family-directions.</p>')
    tr = d["setter_transitions"]
    if len(tr):
        ch = tr.groupby(["ic", "direction", "GENCONSETID"]).changed.mean().mean()
        r.append(f'<p><strong>Correction.</strong> The earlier "leader changed" share paired every outage half-hour with one pre-outage value per run and was misaligned. '
                 f'Aligned per run, the setter changes at invocation start in {ch:.0%} of runs on average across families.</p>')
    return {"constraints": "\n".join(b), "outlook": "\n".join(o), "robustness": "\n".join(r), "downloads": downloads, "figures": figs,
            "log": d["log"], "have_binding": have_bind, "have_outlook": bool(d["live_meta"])}
