"""Rebuild the offline RHS feasibility report from the extracted evidence."""
import base64
import json
import sys
from html import escape
from pathlib import Path

import markdown
import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.report_theme.report_theme import figure_html, hero, matplotlib_style, metric, render_page

OUT = ROOT / "reports/rhs_replay"
CASE = "N::Q_NIL_KC"
MONITOR = "DATASNAP_DFS_NSYD"
SITE = "https://tapr.transgrid.com.au/transgrid_bsp_data/Sydney%20West%20132%20kV%20historical%20BSP%20load.xlsx"
ARCHIVE = "https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/"
GUIDE = "https://www.aemo.com.au/-/media/files/electricity/nem/it-systems-and-change/nemde-queue/nemde_queue_users_guide.pdf"


def charts(results, final):
    outputs = []
    figdir = OUT / "figures"
    figdir.mkdir(exist_ok=True)
    with plt.rc_context(matplotlib_style()):
        for eq, field, reference, title, axis in [
            (MONITOR, "proxy_input", "demand_mw", "Sydney-area effective load", "MW"),
            (CASE, "proxy_headroom", "official_headroom", "Terranora-sensitive equation headroom", "MW of headroom"),
        ]:
            frame = results[(results.equation == eq) & (results.window == final)]
            one = frame[frame.method == "Prior public snapshot"]
            if eq == CASE:
                fig, (ax, zoom) = plt.subplots(2, 1, figsize=(8.8, 5.4), sharex=True,
                    height_ratios=[2.1, 1], constrained_layout=True)
            else:
                fig, ax = plt.subplots(figsize=(8.8, 3.6), constrained_layout=True)
            for group, color in [("NSW demand share", "#b06d0b"), ("Prior public snapshot", "#336bba")]:
                piece = frame[frame.method == group]
                ax.plot(piece.interval_end, piece[field], label=group, color=color, linewidth=1.8, marker=".", ms=4)
            ax.plot(one.interval_end, one[reference], color="#153e3c", label="Archived reference",
                    linewidth=1.8, ls="--")
            if eq == CASE:
                marked = one[one.marginal_value.abs() > 1e-5]
                ax.scatter(marked.interval_end, marked[reference], marker="D", color="#942c58", s=20,
                           label="Economic bind", zorder=5)
                ax.axhline(0, color="#777", lw=.8)
                near = one.official_headroom.abs() < 10
                zoom.axhline(0, color="#555", linewidth=.9)
                zoom.errorbar(one.loc[near,"interval_end"],one.loc[near,"proxy_headroom"],
                              yerr=one.loc[near,"band_mw"],color="#336bba",fmt="o",capsize=3,ms=4)
                zoom.scatter(marked.interval_end,marked.official_headroom,color="#942c58",marker="D",s=16,zorder=4)
                zoom.set_ylabel("Headroom (MW)")
                zoom.set_title("Near zero · prior snapshot estimate and empirical error band",fontsize=10,loc="left")
            ax.set_ylabel(axis)
            (zoom if eq == CASE else ax).set_xlabel("19 February 2026 · interval ending, NEM time")
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
            ax.legend(ncol=2, loc="lower left", bbox_to_anchor=(0, 1), fontsize=9)
            path = figdir / ("sydney_load.png" if eq == MONITOR else "network_headroom.png")
            fig.savefig(path, dpi=140)
            plt.close(fig)
            outputs.append((title, path))
    return outputs


def txt_table(rows, columns):
    return pd.DataFrame(rows, columns=columns).to_markdown(index=False, disable_numparse=True)


def inventory_search():
    data = pd.read_csv(OUT / "inventory/inputs.csv", keep_default_na=False)
    deps = pd.read_csv(OUT / "inventory/dependencies.csv", keep_default_na=False)
    cols = ["spd_type", "spd_id", "meaning", "historical_status", "dispatch_time_status",
            "alternate_public_source"]
    leaf = data[cols].values.tolist()
    eqs = deps.groupby(["spd_type", "spd_id"]).equation.apply(lambda g: " | ".join(sorted(set(g))))
    for r in leaf:
        r.append(eqs.get(tuple(r[:2]), ""))
    payload = json.dumps(leaf, ensure_ascii=True).replace("<", r"\u003c")
    return ("""<label for="lookup"><strong>Find an input or equation</strong></label>
<input id="lookup" type="search" placeholder="Try TERRANORA_LOAD, a rating ID or a constraint ID">
<p id="matches" role="status"></p><div class="table-wrap" tabindex="0"><table><thead><tr>
<th>Type</th><th>Input ID</th><th>Meaning</th><th>Historical evidence</th><th>Dispatch cutoff</th>
<th>Public source lead</th></tr></thead><tbody id="leaves"></tbody></table></div>
<script type="application/json" id="input-data">""" + payload + """</script><script>
const leaves=JSON.parse(document.getElementById('input-data').textContent);
const lookup=document.getElementById('lookup');
function showInputs(){
 const query=lookup.value.toLowerCase().trim();
 const hits=leaves.filter(row=>row.some(value=>String(value).toLowerCase().includes(query)));
 document.getElementById('matches').textContent=hits.length+' matches · showing '+Math.min(hits.length,20);
 const body=document.getElementById('leaves'); body.replaceChildren();
 for(const row of hits.slice(0,20)){const tr=body.insertRow();
 for(const value of row.slice(0,6)){tr.insertCell().textContent=value||'—';}}
}lookup.addEventListener('input',showInputs);showInputs();</script>""")


def build():
    summary = json.loads((OUT / "inventory/summary.json").read_text())
    cases = pd.read_csv(OUT / "cases/replay.csv")
    results = pd.read_csv(OUT / "proxies/interval_results.csv", parse_dates=["interval_end"])
    scores = pd.read_csv(OUT / "proxies/metrics.csv")
    final = results.sort_values("interval_end").window.iloc[-1]
    held = scores[scores.window.eq(final)].set_index(["equation", "method"])
    lag, share = (held.loc[(CASE, label)] for label in ("Prior public snapshot", "NSW demand share"))
    scans = pd.read_csv(OUT / "proxies/source_checks.csv")
    averages = pd.read_csv(OUT / "proxies/halfhour_diagnostic.csv")
    counts = summary["historical_equation_status"]
    sections = []
    def add(key, title, body):
        sections.append((key, title, body.strip()))
    n_valid = cases[["rhs_reference", "rhs_replay"]].notna().all(axis=1).sum()
    worst = (cases.rhs_replay - cases.rhs_reference).abs().max()
    deck = (f"Archived case inputs reproduced {n_valid} equation outcomes. In the held-out network case, "
            f"the previous public Terranora reading gave {lag.rhs_mae:.2f} MW mean RHS error. "
            f"All {int(lag.uncertain_economic)} economically binding intervals still fell in the uncertain category.")
    add("answer", "What you can inject", f"""
For a historical replay, open the interval’s loaded NEMDE case and use the input side of the case. Select the exact constraint version, expand its shared equations, and apply its signed coefficients, branches and input-quality rules. Match the resulting number to the published RHS for the same run. The three sampled equations had a maximum absolute difference of **{worst:.8f} MW**. They cover a load monitor, a network equation and an equipment-status equation. [AEMO guide to NEMDE files]({GUIDE})

For some inputs there is a simpler public route. Read the five-minute DispatchIS report, select the correct version of a reporting equation, and invert its formula. In the versions tested, `DATASNAP_DFS_NSYD.RHS − 10000` yields `N_SYDNEY_LOAD`. Likewise, `DATASNAP_TE_967_1.RHS − 10000` yields `TERRANORA_LOAD`. Across the two points, the largest discrepancy against their independent archived case values was **{scans.snapshot_max_abs_mw.max():.8f} MW**. These are effective inputs that can include EMS substitutions. [AEMO public DispatchIS archive]({ARCHIVE})

For use at the interval start, take the last eligible **earlier** public report. Keep the source interval, report creation time, publication or receipt evidence, and equation version alongside the value. Same-interval snapshots were used solely to verify the sensor decoding. For example, the 4 February monitor for the interval ending 04:05 reported 13,705.96655 MW, implying 3,705.96655 MW for the Sydney-area signal. The file was generated at 04:00:11, eleven seconds after that interval started. The proxy experiment changes one demand input and holds all other inputs and the solved LHS fixed. A full live bind call also needs an independently available LHS and the remaining current inputs.
""")
    section = f"""The dated inventory covers **{summary['active_in_period']:,} equations active in the NEM dispatch period ending 04:05 on 4 February**, from {summary['loaded_formulations']:,} loaded formulations. The denominator consists of the equations in this case. Equations reserved for other outages and other dispatch periods can introduce additional inputs.

The case contained **{summary['external_input_count']:,} distinct typed external inputs**, {summary['shared_used']} referenced shared equations and {summary['program_terms']:,} program terms. Static constants accounted for {counts['case_static_constant']:,} equations. All candidate historical leaves were located for {counts['case_inputs_located']:,} dynamic equations. Another {counts['some_inputs_unresolved']:,} had at least one unresolved input or input-selection rule. Leaf coverage is a screening result. Only the three sampled programs underwent numerical replay.

| Access question | What the evidence supports |
|---|---|
| Are the dispatch formulations public? | The public case supplies the versioned program, its operations, defaults and shared terms for this period. |
| Are historical values present? | The input register identifies values and quality flags for this case. Regional selection, switch runs and missing trader inputs can require additional work. |
| Are live equivalents public? | DispatchIS exposes selected monitors after the run. Equipment ratings also have a public AEMO product. Matching the exact sensor, rating level, run and timestamp is necessary before assuming equivalence. |
| How much does the snapshot route cover? | {summary['datasnap'].get('verified_after_run',0)} monitor inversions agreed within half a published increment and {summary['datasnap'].get('within_one_published_increment',0)} more within one increment. The register also identifies multi-input and nonlinear monitors. |

[Offline equation and point lookup](inventory/lookup.html) · [Typed inputs](inventory/inputs.csv) · [Equation coverage](inventory/equations.csv) · [Equation-to-input mapping](inventory/dependencies.csv) · [Ordered terms, branches and defaults](inventory/terms.csv) · [Public snapshot decoding](inventory/datasnap.csv) · [AEMO transmission equipment ratings](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/transmission-equipment-ratings)"""
    add("inventory", "Which inputs are public?", section)
    add("sydney", "Three meanings of Sydney demand", f"""
**AEMO’s Sydney-area input.** `N_SYDNEY_LOAD` covers Sydney, Wollongong and Newcastle. The dated EMSMASTER search found no verified Western Sydney-only demand term. The case shows a single monitor consuming this broad point. Its substantial headroom makes it a useful arithmetic control and a poor test of binding risk.

**Sydney West substation.** Transgrid publishes `Avg.TOT_TX` in its Sydney West 132 kV historical bulk-supply-point workbook. The workbook has 1,344 half-hour values in February 2026. June and July 2025 medians moved from approximately −689 MW to +15 MW. The cause, sign convention and interval labelling across that change remain unresolved. The published workbook examined here postdates the study windows. A separate Sydney West line-end series measures flow on one line. [Sydney West transformer workbook]({SITE})

**A Western Sydney demand footprint.** An exact reconstruction needs a documented set of metering boundaries, directions and treatments for transfers and embedded generation. None of the audited sources established that definition. Summing geographically nearby substations risks double-counting power moving between them. The study therefore scores the two timestamped public proxies against the verified Sydney-area and Terranora points. Accuracy for a Western Sydney-only quantity remains undetermined. [Source audit](sydney_sources.md) · [Public payload checks](sydney_sources.csv)
""")
    bycase = []
    for name, g in cases.groupby("equation"):
        delta = (g.rhs_replay-g.rhs_reference).abs()
        bycase.append((name, len(g), g.rhs_replay.notna().sum(), f"{delta.mean():.8f}", f"{delta.max():.8f}",
                       int((g.marginal_value.abs()>1e-5).sum())))
    add("replay", "The three independent replays", """
The windows were chosen using historical dispatch outcomes before looking at proxy errors. Window 1 covers 1 February 04:05–06:00, window 2 covers 15 February 12:05–14:00 and the held-out window covers 19 February 10:05–12:00. All timestamps are interval endings in fixed NEM time. The latter two windows deliberately include congestion. They do not estimate how frequently it occurs.

""" + txt_table(bycase, ["Equation","Rows","Calculated","Mean |error| MW".replace("|",""),"Max error MW","Economic bind intervals"]) + """

The independent control adds 10,000 to Sydney-area demand. The network case uses Terranora load inside both a linear and a squared term, alongside interconnector flow and NSW/Queensland demand inputs. The equipment equation `T^V_NIL_9` uses `594 − 244 × GTOWN_FL_TIMER`. Its timer read 1 throughout the sample and all 72 RHS values were 350 MW. The alternate status remains untested. For calculator comparison, select an interval in the replay CSV and use the term rows for that equation, version and run. Preserve input signs and EMS quality flags. Compare your result with the archived reference only after finishing the calculation. [Five-minute replay](cases/replay.csv) · [Term values and intermediate arithmetic](cases/terms.csv)

**The regional-demand trap.** Simply injecting the XML solution's `FixedDemand` field into the network equation would have passed the ordinary window and missed the RHS by up to 25.71 MW under stress. For these cases, reconstructing the regional constraint term requires the regional initial demand, demand change, adjustment and allocated losses at initial flows, with the scheduled-load treatment used by the constraint. WDR initial values were zero in the sample. The component export records each signed contribution and the underlying loss segments. [Regional demand components](cases/regional_demand_components.csv)
""")
    table = []
    for (eq, method), row in held.iterrows():
        table.append((eq,method,int(row.n),f"{row.input_mae:.2f}",f"{row.rhs_bias:+.2f}", f"{row.rhs_mae:.2f}",
                      f"{row.rhs_max:.2f}",f"{row.band_mw:.2f}",f"{int(row.covered)}/{int(row.n)}"))
    add("proxy", "How much error reaches the RHS?", """
Both proxies use the same intervals and inputs from earlier public files. The first carries forward the effective local measurement recovered from its reporting equation. The second scales the most recent NSW total demand by a constant fitted separately to each local point in window 1. The share equals the sum of local observations divided by the sum of regional observations. Window 2 supplies an error band equal to the largest absolute RHS proxy error in that window. Window 3 tests both without refitting.

""" + txt_table(table, ["Equation","Public proxy","Rows","Input MAE MW","RHS bias MW","RHS MAE MW","Max MW","Band ±MW","In band"]) + f"""

On the held-out network equation, the prior snapshot produced **{lag.rhs_mae:.2f} MW** mean absolute RHS error versus **{share.rhs_mae:.2f} MW** for the regional share. The equations respond differently to a MW of input error. The Sydney monitor passes it through directly. For the network case, the public CSV contains the period-specific coefficients for evaluating the exact quadratic at any alternative Terranora load.

A separate cadence check uses the true average of each complete six-interval block in place of each five-minute value. Across {len(averages)} equation/half-hour blocks the largest resulting RHS discrepancy was {averages.rhs_max.max():.2f} MW. That calculation gives an averaging-only diagnostic, even with a perfect meter and no geographic mismatch. A completed block includes later observations and cannot supply a dispatch-start estimate for its earlier intervals. [Half-hour diagnostics](proxies/halfhour_diagnostic.csv) · [Interval-level proxy evidence](proxies/interval_results.csv)
""")
    call_table = []
    for method, row in [("Prior public snapshot",lag),("NSW demand share",share)]:
        call_table.append((method, int(row.clear), int(row.at_risk), int(row.uncertain), int(row.missed_economic),
                           int(row.false_alerts), int(row.uncertain_economic), int(row.unbanded_flips)))
    add("binding","Does the proxy change a binding decision?", f"""
The held-out network window contains **{int(lag.official_economic)} economically binding intervals in {int(lag.economic_episodes)} observed episode(s)**. Economic binding uses nonzero absolute published marginal value above 0.00001. Physical tightness uses signed headroom at or below 0.0001 MW. Violation degree is reported separately. Positive headroom means available room in the permitted direction.

With the solved LHS held fixed, a proxy call is **clear** if the whole empirical band is above the tightness threshold, **at risk** if the whole band is at or below the threshold, and **uncertain** if it straddles the threshold. The last column counts interval decisions that flip if the uncertainty band is ignored, using physical tightness as the reference.

""" + txt_table(call_table, ["Proxy","Clear","At risk","Uncertain","Missed bind intervals","False alerts","Binds uncertain","Unbanded flips"]) + f"""

The prior-snapshot method definitively flagged {int(lag.confirmed_episodes)} of {int(lag.economic_episodes)} observed economic episodes, with {int(lag.missed_episodes)} wholly missed and {int(lag.entirely_uncertain_episodes)} entirely uncertain. Episodes are consecutive five-minute economic binds inside the sampled window. A low average MW error can still leave the decision unresolved when true headroom is near zero. **Evidence for reliable near-binding calls is inconclusive.** These counts measure substitution against the historical dispatch solution. Set invocation determines which equations apply. [All windows and decision counts](proxies/metrics.csv)
""")
    issued = pd.read_csv(OUT / "proxies/dispatchis_extract.csv",parse_dates=["source_interval_end","producer_time"])
    same_time = issued[issued.source_interval_end.isin(results.interval_end)]
    delay = (same_time.producer_time - (same_time.source_interval_end-pd.Timedelta(minutes=5))).dt.total_seconds()
    add("method", "Timing, limits and reproducibility", f"""
Historical case archives are released after dispatch. Public DispatchIS files carry AEMO creation times and archive member modification times. For the tested lagged proxies, both timestamps had to precede or equal interval start, and the source interval had to be earlier than the target. The rows and hashes identify the actual historical files. Archive timestamps corroborate producer-side timing. Original client receipt times are unavailable, so the study does not certify end-to-end delivery latency. [Timestamped proxy inputs](proxies/prior_public_reports.csv) · [Source archive hashes](proxies/regional_sources.json) · [AEMO release guide]({GUIDE})

Across all {len(delay)} target intervals, same-run public files were generated {delay.min():.0f}–{delay.max():.0f} seconds after interval start (median {delay.median():.0f} seconds). That difference matters if your calculator can run after dispatch has started. The snapshot then exposes the effective value for the current run as soon as the file has actually arrived. In the Sydney case, all 72 archived load values carried the EMS replacement flag.

| Sampled equation | Historical replay | Exact inputs by interval start |
|---|---|---|
| Sydney demand monitor | Direct analog plus constant | Prior monitor is available on the producer timeline. Same-run monitor arrives after the cutoff. |
| NSW–Queensland stability | Exact local load, initial flow and derived regional inputs | Prior local load is measurable. The full current flow and regional input bundle has no demonstrated public receipt by the cutoff. |
| George Town status | Exact effective timer state from case XML | Current timer and changes of state have no verified independent public source at the cutoff. |

An absent open source is recorded as unresolved. Access through a participant portal or a commercial service does not establish anonymous public access. Historical operator substitutions, quality flags, missing status values, branch-specific defaults and intervention runs can change the effective input. Match them before interpreting any numerical discrepancy. Three windows in one month give limited event and seasonal coverage. The 5 GB allowance applies to additional disk use including temporary extraction. The acquisition code reads existing February caches in place, bounds each archive slice, and expands selected XML in memory. The verification manifest records the retained sizes.

From the project root, rebuild the inventory with `python scripts/rhs_inventory.py`, the cases with `python scripts/rhs_cases.py`, the proxies with `python scripts/rhs_proxy_study.py`, and the report with `python scripts/build_rhs_report.py`. Add `--refresh-feed` to the proxy command to reread the original public files. The HTML includes its charts and search data. Keep the evidence folder alongside it for local CSV downloads. [Evidence manifest](manifest.json)
""")
    plots = charts(results, final)
    md = "# Can public inputs reproduce a NEM constraint RHS?\n\n" + deck + "\n"
    blocks = []
    for key,title,body in sections:
        text = markdown.markdown(body, extensions=["tables","fenced_code"]).replace(
            "<table>", '<div class="table-wrap" tabindex="0"><table>').replace("</table>", "</table></div>")
        md += f"\n## {title}\n\n{body}\n"
        if key == "inventory":
            text += inventory_search()
        if key in {"proxy","binding"}:
            name,path = plots[0 if key=="proxy" else 1]
            encoded = base64.b64encode(path.read_bytes()).decode()
            text += figure_html(f'<img alt="{escape(name)}" src="data:image/png;base64,{encoded}">',
                                name, "Five-minute observations, held-out window.", "proxies/interval_results.csv")
            md += f"\n![{name}]({path.relative_to(OUT).as_posix()})\n"
        blocks.append(f'<section id="{key}"><h2>{escape(title)}</h2>{text}</section>')
    extra = [(p.relative_to(OUT).as_posix(), p.stem.replace("_"," ")) for folder in ["inventory","cases","proxies"]
             for p in sorted((OUT/folder).glob("*")) if p.suffix in {".csv",".json",".md"}]
    md += "\n## Evidence files\n\n" + "\n".join(f"- [{label}]({href})" for href,label in extra) + "\n"
    blocks.append("<details><summary>All evidence files</summary><ul>" +
                  "".join(f'<li><a href="{href}">{href}</a></li>' for href,label in extra) + "</ul></details>")
    heading = hero("NEM constraint research","Reconstructing the RHS","from public inputs",deck,
                   ["February 2026","Five-minute dispatch","NSW demand case studies"])
    nav = "<nav>"+"".join(f'<a href="#{k}">{s}</a>' for k,s in
        [("answer","Verdict"),("inventory","Input lookup"),("sydney","Western Sydney"),("replay","Replays"),
         ("proxy","Proxy error"),("binding","Binding"),("method","Methods")])+"</nav>"
    cards = '<div class="metrics">' + "".join([
        metric("Active in snapshot", f"{summary['active_in_period']:,}", "Dispatch equations"),
        metric("Distinct external inputs", f"{summary['external_input_count']:,}", "Typed identifiers"),
        metric("RHS comparisons", f"{n_valid}", "Three equations and three windows"),
        metric("Held-out economic binds", str(int(lag.official_economic)), "Network equation · 24 intervals")]) + "</div>"
    page = render_page("Reconstructing constraint RHS from public inputs", heading+nav+cards+"".join(blocks), plotly=False)
    page = page.replace("</style>", """
input[type=search]{box-sizing:border-box;display:block;width:min(100%,620px);padding:12px 14px;margin:8px 0;
border:1px solid #abb4c4;border-radius:6px;font:inherit}#inventory td{white-space:normal;min-width:85px}
#inventory td:nth-child(3){min-width:220px}p,li{overflow-wrap:anywhere}figure img{min-width:480px}
</style>""")
    (OUT / "index.html").write_text(page, encoding="utf-8")
    (OUT / "study.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    build()
