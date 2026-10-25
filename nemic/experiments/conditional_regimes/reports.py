"""Three substantive offline reports and workbook payload, rebuilt from cached evidence."""
from __future__ import annotations
import base64
from html import escape
import io
import json
from pathlib import Path
import shutil
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import markdown
import numpy as np
import pandas as pd

from nemic_regimes.core import load_bundle, NUMERIC_FEATURES, _clean
from .common import DATA, REPORT, ROOT, EXECUTION, config, digest, now, stage, write_json, dependency_snapshot

sys.path.insert(0,str(ROOT/"scripts/report_theme"))
from report_theme import render_page,hero,metric,matplotlib_style

OUTPUT=ROOT/"outputs/conditional_regimes_v1_20261025"


def table(frame,columns=None,limit=30):
    if columns:frame=frame[columns]
    f=frame.head(limit).copy()
    for col in f:
        if pd.api.types.is_float_dtype(f[col]):f[col]=f[col].map(lambda x:"—" if pd.isna(x) else f"{x:,.2f}")
    return f.to_markdown(index=False)


def figure(fig,name,caption):
    p=REPORT/"figures"/(name+".png");p.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(p,dpi=150,bbox_inches="tight");plt.close(fig)
    encoded=base64.b64encode(p.read_bytes()).decode()
    return f'<figure><figcaption>{escape(caption)}</figcaption><img src="data:image/png;base64,{encoded}" alt="{escape(caption)}" style="width:100%;height:auto"><p class="figure-note">Source: campaign cached evidence. Fixed UTC+10, interval-ending; MW unless labelled otherwise.</p></figure>'


def save_report(filename,title,accent,dek,body,metrics):
    md="\n\n".join(body)
    # Markdown companions reference shipped figure files rather than embedding binary data.
    import re
    figures=list((REPORT/"figures").glob("*.png"))
    def md_image(match):
        data=base64.b64decode(match[1]);h=__import__("hashlib").sha256(data).hexdigest()
        path=next((p for p in figures if digest(p)==h),None)
        return f"![Research figure](figures/{path.name})" if path else ""
    plain=re.sub(r'<figure>.*?<img src="data:image/png;base64,([^\"]+)".*?</figure>',md_image,md,flags=re.S)
    (REPORT/(filename+".md")).write_text("# "+title+"\n\n"+dek+"\n\n"+plain,encoding="utf-8")
    content=markdown.markdown(md,extensions=["tables","fenced_code","toc"])
    content=content.replace("<table>",'<div class="table-wrap" tabindex="0"><table>').replace("</table>","</table></div>")
    nav='<nav class="section-nav"><a href="index.html">Research centre</a><a href="conditions.html">Conditions & events</a><a href="limits.html">Limits & analogues</a><a href="validation.html">Validation</a></nav>'
    head=hero("INTERFLOW · Conditional regimes",title,accent,dek,["Research only", "Q1–Q4", "Six links · both directions", "Built "+config()["as_of"]])
    cards='<div class="metrics">'+"".join(metric(a,b,c) for a,b,c in metrics)+'</div>'
    (REPORT/(filename+".html")).write_text(render_page(title,head+nav+cards+content,plotly=False),encoding="utf-8")


def event_statistics(panel,events):
    rows=[]
    for e in events:
        for name in e["connectors"]:
            for direction in ("forward","reverse"):
                f=panel[(panel.connector==name)&(panel.direction==direction)&panel.time.ge(e["start"])&panel.time.lt(e["end"])]
                if f.empty:continue
                rows.append({"event_id":e["id"],"connector":name,"direction":direction,"rows":len(f),
                             "median_mw":float(f.capacity.median()),"p10_mw":float(f.capacity.quantile(.1)),"minimum_mw":float(f.capacity.min()),
                             "forced_share":float(f.capacity.lt(0).mean()),"unknown_invocation_share":float(f.outage_state.eq("unknown").mean()),
                             "matched_article_sets":"|".join(x for x in e.get("sets",[]) if f.active_sets.str.split("|").map(lambda a:x in a).any())})
    return pd.DataFrame(rows)


def build():
    with stage("report",[DATA/"bundle/manifest.json",DATA/"assessed_scores.csv",DATA/"event_review.json"]) as artifacts:
        REPORT.mkdir(parents=True,exist_ok=True);downloads=REPORT/"downloads";downloads.mkdir(exist_ok=True)
        plt.rcParams.update(matplotlib_style())
        bundle=load_bundle(DATA/"bundle");panel=bundle.panel
        cat=pd.read_csv(DATA/"quarterly_catalogue.csv");scores=pd.read_csv(DATA/"assessed_scores.csv")
        overall=scores[scores["slice"]=="overall"].copy()
        gates=pd.read_csv(DATA/"assessed_method_gates.csv");paired=pd.read_csv(DATA/"assessed_paired_comparisons.csv")
        events=json.loads((DATA/"event_review.json").read_text())["events"]
        event_stats=event_statistics(panel,events);event_stats.to_csv(DATA/"event_statistics.csv",index=False)
        review=json.loads((DATA/"event_review.json").read_text())
        web_verified=set()
        for p in DATA.glob("web_evidence_*.json"):
            value=json.loads(p.read_text(encoding="utf-8"));web_verified.update(value.get("urls",[]))
            if not value.get("urls"):
                import re
                web_verified.update(re.findall(r"https://wattclarity\.com\.au/articles/[^\s)\"]+",str(value.get("result",""))))
        for e in events:e["article_review"]="reviewed via web research; direct download blocked" if e["url"] in web_verified else e["access"]
        # Compact audit matrix distinguishes what is selectable from source-only hypotheses.
        feature_rows=[]
        for f in NUMERIC_FEATURES:
            source="AEMO regional dispatch" if any(x in f for x in ("vre","demand","residual","generation")) else "AEMO equation factors and DUID dispatch" if f.startswith("electrical") else "Public weather; retained reanalysis and explicit issued runs"
            units="C" if "temperature" in f else "%" if "humidity" in f or "cloud" in f else "m/s" if f.endswith("wind_ms") else "W/m2" if "radiation" in f else "MW"
            feature_rows.append({"condition":f,"units":units,"source":source,"historical_coverage":float(panel[f].notna().mean()),
                                 "availability":"Realised conditional history; dated inputs need separate issue and receipt evidence"})
        pd.DataFrame(feature_rows).to_csv(DATA/"condition_dictionary.csv",index=False)
        for file in ("quarterly_catalogue.csv","scores.csv","paired_comparisons.csv","method_gates.csv","coverage.csv","feature_coverage.csv",
                     "condition_dictionary.csv","electrical_groups.csv","family_mapping.csv","event_statistics.csv","evaluation_availability.csv",
                     "example_profile.csv","example_profile.json","asof_scorecard.json","data_audit.json","source_manifest.json","event_review.json","canonical_partition_audit.json"):
            shutil.copy2(DATA/file,downloads/file)
        shutil.copy2(EXECUTION/"event_catalogue.json",downloads/"event_catalogue.json")
        for source,destination in (("assessed_scores.csv","scores.csv"),("assessed_paired_comparisons.csv","paired_comparisons.csv"),("assessed_method_gates.csv","method_gates.csv")):
            shutil.copy2(DATA/source,downloads/destination)
        # The bundle and wheel are separate downloads; reports themselves have no remote rendering dependencies.
        shutil.copy2(DATA/"nemic_regimes_bundle_v1.zip",downloads/"nemic_regimes_bundle_v1.zip")
        for p in (ROOT/"packages/nemic-regimes/dist").glob("*.whl"):shutil.copy2(p,downloads/p.name)
        for p in EXECUTION.glob("RUNBOOK_*.md"):shutil.copy2(p,downloads/p.name)
        shutil.copy2(EXECUTION/"METHODOLOGY.md",downloads/"METHODOLOGY.md")
        shutil.copy2(EXECUTION/"ASSESSMENT.md",downloads/"ASSESSMENT.md")
        shutil.copy2(ROOT/"packages/nemic-regimes/examples/integration.py",downloads/"integration.py")
        shutil.copy2(ROOT/"packages/nemic-regimes/requirements-bundle-v1.txt",downloads/"requirements-bundle-v1.txt")
        if (OUTPUT/"conditional_limits.xlsx").exists():shutil.copy2(OUTPUT/"conditional_limits.xlsx",downloads/"conditional_limits.xlsx")
        end=str(panel.time.max());supported=int(cat.status.eq("supported").sum())

        # Report one: mechanisms and data limitations.
        body=["## 1. Why the earlier tables can miss the day\n\nThe earlier low/normal/high tables condition on one driver at a time. A broad normal bucket can contain a corridor outage, an intact circuit with high local renewable output, and a low-renewable evening with different available generators. Their median may describe none of these well. This campaign keeps the diurnal reference, then asks which joint conditions change the distribution and whether enough independent history supports that distinction.",
              "AEMO reported limits are outcomes of dispatch constraints and controllable dispatch choices. They are not equipment ratings or maximum secure transfer capability. Geographic generation and charging can change the feasible dispatch envelope without any change to regional total wind or demand. [AEMO constraint explanation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq).",
              "## 2. What is actually measured\n\nThe data retain complete six-observation half-hours and signed directional values. Reverse capacity is minus raw IMPORTLIMIT. The primary target is the average; the minimum is retained to reveal restrictions hidden within that average. Missing data are never zero-filled. Calendar quarters use the delivery timestamp in fixed NEM time.",
              table(pd.DataFrame(feature_rows),limit=30),
              "Electrical generation groups are constructed from eligible signed equation terms and effective-dated unit mappings at the first training boundary. They are not rankings chosen from evaluation outcomes. Missing unit dispatch makes the aggregate unavailable rather than silently zero. Their current coverage is limited; the data matrix below makes that visible."]
        coverage=pd.read_csv(DATA/"feature_coverage.csv")
        fig,ax=plt.subplots(figsize=(11,5));matrix=coverage.set_index(["connector","era"])[["source_vre","sink_residual","temperature_max","electrical_positive_mw","electrical_negative_mw"]]
        im=ax.imshow(matrix.to_numpy(),aspect="auto",vmin=0,vmax=1,cmap="Blues");ax.set_yticks(range(len(matrix)),[" · ".join(x) for x in matrix.index],fontsize=9);ax.set_xticks(range(len(matrix.columns)),[c.replace("_","\n") for c in matrix.columns],fontsize=9);fig.colorbar(im,ax=ax,label="Nonmissing share");body.append(figure(fig,"feature_coverage","Condition coverage varies by connector and structural era"))
        body.append(f"## 3. Twelve-month event review\n\nThe review window is 25 October 2025–25 October 2026. The {len(events)} registered cases include mechanism candidates, structural breaks, a negative control, forecast quality checks and a data-quality quarantine. Monthly and theme searches are recorded. Direct site downloads were blocked, so article review used the web research tool; cached research responses have separate hashes. This is a bounded public-source review, not a census of every incident. Several articles quote market notices; an original notice not independently retrieved remains a verification gap. Additional September–October examples were added for explanation without changing the frozen evaluated feature set.")
        for e in events:
            source=f"[WattClarity event source]({e['url']})";primary=f" [AEMO corroboration/context]({e['primary']})." if e.get("primary") else " Original quoted notice reconciliation remains explicit in the evidence register."
            body.append(f"### {e['start']} — {e['title']}\n\n{e['interpretation']} The measurable candidate conditions are {', '.join(e['conditions'])}. Classification: **{e['classification'].replace('_',' ')}**. {source}.{primary}\n\nPublication date: {e['published']}. Later commentary supplies research labels and never masquerades as information known before the event.")
            sample=event_stats[event_stats.event_id==e["id"]]
            if len(sample):body.append(table(sample,["connector","direction","rows","median_mw","p10_mw","minimum_mw","forced_share","unknown_invocation_share"],limit=10))
        body.extend(["## 4. Distinguish mechanisms from coincident stress\n\nLow wind and high prices do not by themselves identify a transfer restriction. The June SA case motivates the combination of equipment status and electrically relevant flexibility. The January lightning case guards against coding weather as a confirmed reclassification. The August DC-control case motivates explicit control availability. The August metering anomaly is quarantined from the primary panel rather than learned as a recurring physical state.",
                     "The PEC market representation change and Basslink transition are compatibility boundaries. Market registration, physical commissioning and individual outage states remain distinct. A binding loop equation is coupling context and is not automatically the reported limit setter. [AEMO PEC FAQ](https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/project-energyconnect-market-integration-project/frequently-asked-questions).",
                     "## 5. Limits of automatic condition selection\n\nThe local collector can retrieve current observed AEMO regional conditions and an explicit coherent public weather run. Applying current dispatch to another delivery period is a scenario assumption. Historical source files retrieved now do not provide historical measured receipts. Battery stored energy, complete current-month invocation and unverified protection status remain unavailable. The historical as-of scorecard therefore contains zero eligible rows; it does not inherit accuracy from the conditional experiment.",
                     "## Evidence and reproduction\n\n[Condition dictionary](downloads/condition_dictionary.csv) · [Feature coverage](downloads/feature_coverage.csv) · [Event register](downloads/event_review.json) · [Source manifest](downloads/source_manifest.json) · [Methodology](downloads/METHODOLOGY.md)"])
        save_report("conditions","The grid behind the range","Conditions, mechanisms and evidence",f"Measured conditions and a twelve-month event review. Historical limit observations through {end} NEM time.",body,[("Event cases",len(events),"Includes negative controls and structural changes"),("Public conditions",len(feature_rows),"Missing quantities remain unavailable"),("Directional rows",f"{len(panel):,}","Complete half-hours in the inference panel"),("Current invocation","Unknown","October dispatch is not an invocation feed")])

        # Report two: each connector and full quarterly reference shapes.
        body=["## 1. How to use these limits\n\nStart with the quarter and delivery half-hour. Then specify the relevant network configuration and measurable conditions. The selector returns a conditional distribution, the historical examples behind it and any conditions relaxed for a broader reference. The P50 is one point in that distribution; the P10 and restrictive cases are essential when assessing downside transfer availability.",
              "The catalogue is an overlapping set of interpretable conditions, not a claim that the grid occupies one mutually exclusive bucket. Thresholds in the final descriptive catalogue use its stated history. During evaluation every threshold was fitted afresh on eligible pre-evaluation history. Numeric user inputs remain numeric; named cases expose the threshold used. The serving evidence layer separately checks repetitions of each requested outage and collapses resubmission chains; unrelated background outage IDs cannot qualify that case as supported. This refines confidence labels without changing the evaluated point/quantile estimator.",
              "## 2. Structural compatibility and sparse quarters\n\nThe current PEC-market history covers only part of Q4, and regulated Basslink has a short history. The selector does not borrow an incompatible old configuration as though it were the same grid. Asking for another quarter can return a broader within-era reference with quarter explicitly relaxed, or a separately labelled modelled extrapolation. A year of historical seasonal shape in an older configuration does not prove a new configuration has the same shape."]
        for name in config()["connectors"]:
            body.append(f"## {name}: quarterly and conditional profiles")
            g=cat[(cat.connector==name)&(cat.regime=="reference")]
            eras=sorted(g.era.unique());chosen=max(eras,key=lambda e:panel[(panel.connector==name)&(panel.era==e)].time.max())
            # Main figure uses the long historical era; current sparse-era profile is a separate comparison.
            historic=max(eras,key=lambda e:len(panel[(panel.connector==name)&(panel.era==e)]))
            fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
            for quarter,ax in zip(range(1,5),axes.flat):
                for direction,color in (("forward","#5696b9"),("reverse","#8370b4")):
                    s=g[(g.era==historic)&(g.quarter==quarter)&(g.direction==direction)].sort_values("half_hour")
                    if len(s):
                        x=s.half_hour.to_numpy()/2;ax.plot(x,s.p50_mw,label=direction,color=color);ax.fill_between(x,s.p10_mw,s.p90_mw,color=color,alpha=.16)
                ax.set_title(f"Q{quarter}");ax.set_ylabel("Reported limit MW");ax.set_xticks([0,6,12,18,23]);ax.set_xlabel("Interval-ending hour (NEM)")
            axes[0,0].legend();fig.tight_layout();body.append(figure(fig,name+"_quarterly",f"{name}: {historic}, median and P10–P90 by calendar quarter"))
            p=panel[panel.connector==name]
            forced=float(p.capacity.lt(0).mean());coverage_count=int(len(p))
            body.append(f"The retained {name} panel contains {coverage_count:,} directional half-hours. Across that pooled history, {forced:.1%} of directional observations are negative; this is a descriptive exposure frequency, not the probability of a future event. The figure keeps each direction separate and shows how the median can conceal a much wider lower tail. The longest era is **{historic}**; the latest observed era is **{chosen}**.")
            s=cat[(cat.connector==name)&(cat.era==historic)&(cat.regime!="reference")]
            ref=g[g.era==historic][["direction","quarter","half_hour","p50_mw"]].rename(columns={"p50_mw":"reference_p50"})
            joined=s.merge(ref,on=["direction","quarter","half_hour"]);joined["difference_mw"]=joined.p50_mw-joined.reference_p50
            ranking=joined[joined.status=="supported"].groupby(["direction","quarter","regime"]).agg(mean_median_difference_mw=("difference_mw","mean"),min_p10_mw=("p10_mw","min"),median_days=("days","median"),supported_half_hours=("half_hour","nunique")).reset_index()
            if len(ranking):
                ranking=ranking.assign(_rank=ranking.mean_median_difference_mw.abs()).sort_values("_rank",ascending=False).drop(columns="_rank")
                body.append("The following supported associations have the largest average median differences from the same quarter/half-hour reference. They reflect overlapping conditional samples and must not be added together as independent outage effects.")
                body.append(table(ranking,limit=10))
            else:body.append("No conditional cell passes the declared support convention in this slice; the downloadable catalogue retains the indicative observations without presenting them as supported limits.")
            if chosen!=historic:
                latest=g[g.era==chosen]
                body.append("Current-era support is short and quarter coverage is incomplete. Its available reference cells are shown below rather than filling missing quarters from the earlier era.")
                summary=latest.groupby(["direction","quarter"]).agg(half_hours=("half_hour","nunique"),median_p50=("p50_mw","median"),lowest_p10=("p10_mw","min"),median_days=("days","median")).reset_index()
                body.append(table(summary,limit=8))
        body.extend(["## Stress examples and extrapolation\n\nEach Python query returns nearby historical days and restrictive observations from its compatible candidate set. Those examples are not assigned occurrence probabilities. Sparse exact conditions can produce a broader analogue range with an explicit list of relaxed conditions. Additive and boosted estimates require explicit extrapolation selection; their missing inputs are training-imputed assumptions and their tail calibration is not established for an arbitrary new combination.",
                     "## Downloads and use\n\n[Full conditional catalogue](downloads/quarterly_catalogue.csv) · [Example 48-half-hour profile](downloads/example_profile.csv) · [Evidence-rich example](downloads/example_profile.json) · [Versioned Python bundle](downloads/nemic_regimes_bundle_v1.zip) · [Selector and workbook runbook](downloads/RUNBOOK_SELECTOR.md)"])
        save_report("limits","Four quarters of conditional limits","Diurnal shapes, ranges and restrictive cases","Six interconnectors, both directions, with explicit support and configuration boundaries.",body,[("Catalogue cells",f"{len(cat):,}","Overlapping named conditions"),("Supported cells",f"{supported:,}","20 days; outage-specific cases also need 5 episodes"),("Delivery periods",48,"Half-hour average is the primary target"),("Calendar quarters",4,"General conditioning categories")])

        # Report three: all scores are from saved out-of-sample predictions.
        body=["## 1. What this evaluation can establish\n\nThe conditional experiment supplies known historical operating conditions to estimate the reported limit distribution. It answers whether the conditioner explains outcomes on later rows; it does not establish how well those future conditions can themselves be forecast. The event review informed feature development, so even chronological results are retrospective development evidence.",
              "The separate as-of track has zero eligible historical rows because retained sources do not establish measured receipt for the complete six-link feature contract. No synthetic receipt times or realised future substitutions are used. Automatic collection now records actual receipts for future confirmation.",
              "## 2. Chronology and comparisons\n\nThe expanding protocol starts with twelve months of training, eight weeks of selection, a four-week calibration/alert block and four-week evaluation blocks. The last two weeks of that pre-evaluation block are reserved for alert tuning, disjoint from quantile calibration. Earlier rows of boundary-crossing outage incidents are purged. Analogue neighbourhoods are tuned on a deterministic pre-evaluation sample; all 48 half-hours are eligible in evaluation. Source or method failures are reported separately, and comparisons use identical available rows.",
              "The models are a piecewise additive regularised quantile regression and shallow quantile boosting. The former uses up to 1,800 deterministic training rows, L2 shrinkage and a convergence-checked smooth-pinball optimiser; boosting uses up to 6,000. The additive smoothing width is 0.005 of its training target IQR. Medians, scaling and imputation are training-fitted. Quantile ordering is repaired without clamping signed values.",
              table(overall,["connector","direction","method","n","mae","pinball","coverage80","width80","p95_overstatement"],limit=100)]
        fig,axes=plt.subplots(1,2,figsize=(12,5))
        for method,g in overall.groupby("method"):
            axes[0].scatter(g.mae,g.coverage80,label=method,alpha=.75)
            axes[1].scatter(g.mae,g.p95_overstatement,label=method,alpha=.75)
        axes[0].axhline(.8,color="#66717e",ls="--");axes[0].set(xlabel="MAE MW",ylabel="P10–P90 coverage",title="Accuracy and calibration")
        axes[1].set(xlabel="MAE MW",ylabel="P95 overstatement MW",title="Average error does not describe the tail")
        axes[1].legend(fontsize=8);fig.tight_layout();body.append(figure(fig,"accuracy_risk","Each point is a connector-direction method on matched held-out rows"))
        body.append("A separate [canonical incident audit](downloads/canonical_partition_audit.json) collapses outage resubmission chains and checks every pair of chronological partitions in all 132 connector-direction folds. No shared incident was found across partition boundaries. This establishes incident separation, not model accuracy.")
        body.extend(["## 3. Paired uncertainty and risk gates\n\nPaired seven-day block resampling compares point errors on identical timestamps. The historical gates require a positive lower improvement bound, lower quantile loss, acceptable interval coverage, no material worsening in overstatement or restriction/forced-flow recall, and sufficient extreme-event support. Passing a historical gate is not production promotion. Where a method fails, the reason remains part of the deliverable.",
                     table(gates,limit=80),table(paired,limit=80),
                     "## 4. Restrictive regimes and forced flow\n\nRestriction thresholds are fitted from positive pre-evaluation directional limits, while zero and negative observations remain outcomes. An alert is judged with recall, precision and false alerts per half-hour exposure day. Forced flow is evaluated separately. Low incident counts can prevent a risk conclusion even when average errors are favourable."])
        extreme=overall[["connector","direction","method","restriction_events","restriction_recall","restriction_precision","false_alerts_per_day","forced_events","forced_recall"]]
        body.append(table(extreme,limit=100))
        perq=scores[scores["slice"].str.startswith("quarter:")]
        fig,ax=plt.subplots(figsize=(11,5))
        pivot=perq.groupby(["slice","method"]).mae.mean().unstack("method")
        pivot.plot.bar(ax=ax);ax.set(xlabel="Evaluation delivery quarter",ylabel="Mean cell MAE MW",title="Quarterly error composition; pooled MW scales differ across links");ax.tick_params(axis="x",rotation=0);ax.legend(fontsize=8);fig.tight_layout();body.append(figure(fig,"quarter_errors","Quarter slices preserve the calendar structure"))
        body.extend(["## 5. Availability, failure modes and interpretation\n\nExact network combinations are often scarce after incident purging. The matched score table excludes rows where any required comparator is unavailable; the availability download shows the resulting selection. It must not be read as an all-conditions success rate. New market eras can lack a trained comparator even when descriptive dispatch observations exist. Current PEC-era history is especially short.",
                     "Electrical group coverage is incomplete because missing or transitioned DUIDs are not converted to zero. The latest month lacks a verified complete invocation feed. Reanalysis and final-state outage histories support conditional explanations, while retrospective revisions and later article descriptions prevent a live-forecast claim. The quarantined August anomaly is documented separately and is not treated as a physical regime.",
                     "Final bundle models are fitted for inference and are not scored on their own training rows. Their arbitrary-query extrapolation intervals remain unverified. Retain the empirical range and stress evidence when choosing assumptions; a better average score does not override failed calibration or risk gates.",
                     "## Reproduce and inspect\n\n[Full slice scorecard](downloads/scores.csv) · [Method availability](downloads/evaluation_availability.csv) · [Paired comparisons](downloads/paired_comparisons.csv) · [Method gates](downloads/method_gates.csv) · [As-of eligibility](downloads/asof_scorecard.json) · [Research runbook](downloads/RUNBOOK_RESEARCH.md)"])
        save_report("validation","Does conditioning improve the estimate?","Chronological accuracy and risk evidence","Measured comparisons, calibration, availability and extreme-regime limitations.",body,[("Scored methods",overall.method.nunique(),"Same-row comparisons"),("Historical gate passes",int(gates.historical_gate_pass.sum()),"No production promotion"),("As-of scored rows",0,"Receipt evidence insufficient"),("Evaluation cells",len(overall),"Connector × direction × method")])

        # Landing page, sources, runbooks and workbook payload.
        workbook_link=' · <a href="downloads/conditional_limits.xlsx">Excel companion</a>' if (downloads/"conditional_limits.xlsx").exists() else ""
        links='<section><h2>Read the research</h2><p><a href="conditions.html">1. Grid conditions and event evidence</a></p><p><a href="limits.html">2. Conditional limits and analogue results</a></p><p><a href="validation.html">3. Method comparison and validation</a></p></section>'
        links+='<section><h2>Use the results</h2><p><a href="downloads/nemic_regimes_bundle_v1.zip">Versioned inference bundle</a>'+workbook_link+'</p><p>The full selector runs locally through the Python package. These reports work offline.</p>'
        for p in downloads.glob("*.whl"):links+=f'<p><a href="downloads/{escape(p.name)}">Installable Python wheel</a></p>'
        for p in sorted(downloads.glob("RUNBOOK_*.md")):links+=f'<p><a href="downloads/{escape(p.name)}">{escape(p.stem.replace("RUNBOOK_",""))} runbook</a></p>'
        links+='</section><section><h2>Evidence boundaries</h2><p>Conditional reported-limit research. Current network eras have incomplete seasonal history. Historical measured-receipt evaluation is unavailable. Neither fitted complexity nor a historical gate pass changes production routing.</p></section>'
        (REPORT/"index.html").write_text(render_page("Conditional interconnector limits",hero("INTERFLOW · Research centre","Four quarters.","Conditions that change the range.","Research, tools and reproducible evidence for six interconnectors.",["Q1–Q4",end+" NEM",bundle.metadata["bundle_id"]])+links,plotly=False),encoding="utf-8")
        # Spreadsheet is a typed results export; modelling stays in Python.
        reference=cat[cat.regime=="reference"].copy()
        payload={"as_of":config()["as_of"],"data_end":end,"bundle_id":bundle.metadata["bundle_id"],
                 "reference":reference.to_dict("records"),"conditional":cat[cat.regime!="reference"].to_dict("records"),
                 "selected":pd.read_csv(DATA/"example_profile.csv").drop(columns=["conditions","analogues","stress_examples","baseline"],errors="ignore").to_dict("records"),
                 "validation":overall.to_dict("records"),"events":events,"conditions":feature_rows}
        write_json(DATA/"workbook_payload.json",_clean(payload))
        manifest={"schema":1,"built":now(),"data_cutoff":end,"bundle_id":bundle.metadata["bundle_id"],
                  "inputs":{key:value for key,value in dependency_snapshot("report",[DATA/"bundle/manifest.json",DATA/"canonical_partition_audit.json",ROOT/"packages/nemic-regimes/examples/integration.py",ROOT/"packages/nemic-regimes/requirements-bundle-v1.txt"]).items() if not key.startswith("@") and value is not None},
                  "files":{str(p.relative_to(REPORT)).replace("\\","/"):digest(p) for p in REPORT.rglob("*") if p.is_file() and p.name not in {"build_manifest.json","verification.json"} and "qa" not in p.parts}}
        write_json(REPORT/"build_manifest.json",manifest)
        artifacts.extend([REPORT/(n+e) for n in ("index","conditions","limits","validation") for e in ([".html"] if n=="index" else [".html",".md"])])
        artifacts.extend([REPORT/"build_manifest.json",DATA/"workbook_payload.json",DATA/"event_statistics.csv"])
        print("Built three offline reports, research centre and workbook payload",flush=True)
