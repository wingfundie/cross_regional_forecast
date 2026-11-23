"""Offline editorial atlas and independently verifiable evidence exports."""
from __future__ import annotations

import json
import importlib.metadata
import re
import shutil
import sys
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from bs4 import BeautifulSoup
from plotly.subplots import make_subplots

from .core import ROOT, REGIONS, STUDIES, IC_REGIONS, grid, json_write, load, sha

sys.path.insert(0,str(ROOT/"scripts/report_theme"))
from report_theme import figure_html, finding, hero, metric, render_page, style_plotly

REGION_COLORS={"NSW1":"#5696b9","QLD1":"#ce9a48","SA1":"#8370b4","TAS1":"#66717e","VIC1":"#268a87"}
IC_COLORS=dict(zip(STUDIES,["#5696b9","#ce9a48","#8370b4","#66717e","#268a87","#b75c70"]))

def table(frame,columns=None):
    f=frame[columns].copy() if columns else frame.copy()
    for col in f.select_dtypes(include=["float"]):f[col]=f[col].round(3)
    parsed=BeautifulSoup(f.to_html(index=False,escape=True,na_rep="—",border=0),'html.parser')
    long_columns=[i for i,col in enumerate(f) if f[col].astype(str).str.len().max()>120]
    for row in parsed.select('tr'):
        cells=row.find_all(['th','td'],recursive=False)
        for index in long_columns:
            if index<len(cells):cells[index]['style']='min-width:340px'
    return '<div class="table-scroll" tabindex="0">'+str(parsed)+'</div>'


def markdown_table(frame):
    f=frame.copy()
    for col in f.select_dtypes(include=['object','string']):
        f[col]=f[col].map(lambda value:escape(value).replace('\\','\\\\').replace('|','\\|').replace('\r','').replace('\n','<br>') if isinstance(value,str) else value)
    return f.to_markdown(index=False)


def chart(fig,title,height=520):
    style_plotly(fig,title,height=height)
    if fig.layout.annotations:
        fig.update_layout(margin=dict(l=76,r=35,t=170,b=55),legend=dict(y=1.08,yanchor="bottom"))
    return fig.to_html(full_html=False,include_plotlyjs=False,config={"displaylogo":False,"responsive":True})


def slug(asset):
    return "line-"+re.sub(r"[^a-zA-Z0-9]+","-",asset).strip("-")


def clean_records(frame):
    return json.loads(frame.to_json(orient="records",date_format="iso"))


MECHANISM_PROSE = [
 ("Why removing one line affects other equipment", "In an AC network, power shares available paths according to their electrical properties and the network operating state. Opening a circuit changes that sharing. A remaining line or transformer can carry more load even if the total regional demand has not changed. Conversely, a topology change can relieve a previously limiting element. Actual branch loading requires measurements or a validated network model; this study does not manufacture it from interconnector flows."),
 ("The outage and the contingency are different", "A line already unavailable is part of the operating configuration. Operators must also protect against credible subsequent disturbances. The relevant constraint may therefore limit loading on a different element after loss of another circuit, generator or transformer. The outaged line, monitored element and protected contingency must be read separately in the equation description and limit advice."),
 ("How a security requirement enters dispatch", "AEMO represents requirements using equations over controllable generation, loads and interconnectors. A simplified form is a·F + Σbᵢ·Pᵢ + other terms ≤ RHS. For a nonzero interconnector coefficient, the conditional bound is Fobserved + (RHS − LHS)/a: positive a gives an upper bound and negative a gives a lower bound for this ≤ form. A generator’s local bound sensitivity is −bᵢ/a when the other terms are held fixed. The inequality operator and direction must be checked in the native definition. This is a conditional dispatch relationship; coefficients do not establish secure physical capacity or the full response after all dispatch variables move."),
 ("Invoked, binding and limit-setting describe different things", "A booked outage can exist without its set being invoked. An invoked equation can have slack and create no immediate dispatch change. This report flags observed binding using a nonzero marginal value, which measures a marginal effect on the optimisation objective. An equation can also sit at its bound with zero marginal value. The equation determining a reported interconnector bound need not bind because dispatch may sit away from that bound. Sets can also displace the usual limiting equation rather than become the dominant limiter themselves."),
 ("How congestion reaches regional prices", "Dispatch balances regional demand while respecting offers, ramping, availability, losses, FCAS requirements and security equations. If congestion removes access to a cheaper feasible combination of generation and transfers, a more expensive combination may be required. Prices can separate between regions and move sharply as constraints activate or the offer stack steepens. Regional reference prices do not reveal every local congestion effect within a region. The observed response is jointly determined by network restrictions and the available offers."),
 ("Price separation and volatility are different outcomes", "A persistent restriction can produce a sustained regional price spread with little five-minute movement. Volatility can increase when changing demand, renewable output, generator availability or offers repeatedly activates and releases a restriction, or moves the feasible dispatch solution between very different offer bands. A line outage changes the feasible network state; whether that becomes a steady spread, a brief spike, negative prices or little visible regional response depends on those conditions. Restoration can relax the restriction, but simultaneous changes elsewhere can obscure or reverse the observed before/after difference."),
 ("Why an outage can accompany negative prices", "When exports or local evacuation are restricted in a surplus area, generation may be constrained down or compete for the remaining feasible dispatch. Renewable conditions, inflexible generation, offers and demand determine whether the regional reference price falls below zero. A negative price during an outage is therefore evidence to investigate, not automatic proof of an outage-induced effect."),
 ("When the effect is small or reverses", "The restriction may remain nonbinding; alternative paths or generators may absorb it; scheduled demand may be low; or another constraint may dominate. Different flow directions and generator combinations can change the sign of an effect. The low-stress cases and failed statistical gates are part of the findings, not discarded exceptions."),
 ("What the evidence can establish", "The report combines verified equipment windows, direct set links, effective-version equations, observed dispatch and controlled comparisons. It does not run an AC security model or a full NEMDE counterfactual. Outages are scheduled selectively, concurrent work is common, and public records do not resolve every switching configuration. Controlled estimates remain retrospective and do not establish an isolated causal price contribution.")
]


def profile_text(asset,register,links,mechanisms,effects,cp,icterms,crosswalk):
    families=sorted(set(links.loc[links.asset.eq(asset),"family"]))
    m=mechanisms[mechanisms.asset.eq(asset)]
    bound=m[m.binding_intervals.gt(0)].sort_values("binding_intervals",ascending=False)
    eq=sorted(set(crosswalk.loc[crosswalk.asset.eq(asset),"constraint"]))
    term=icterms[icterms.GENCONID.isin(eq)]
    affected=sorted(set(term.INTERCONNECTORID))
    good=effects[effects.asset.eq(asset)&effects.period.eq("confirmation")&effects.confirmed]
    text=f"{register.description} is recorded at {register.voltage_kv:g} kV in {register.region}. The audit identifies {register.events} merged asset-level primary-equipment events with actual start and restoration times. "
    text+=("Directly linked outage sets are "+", ".join(families)+". ") if families else "No verified direct outage-set link is available for these events. "
    if len(bound):
        top=bound.iloc[0]
        text+=f"Observed own-set binding includes {top.constraint}; its description is reproduced below to identify the protected network condition. "
    else:text+="No own-set binding was found in the available sparse constraint panel; this does not establish that the outage was harmless or that no other equation tightened. "
    if affected:text+="Resolved member equations include terms for "+", ".join(affected)+". Those terms establish conditional dispatch sensitivity, rather than a measured change in every link. "
    else:text+="Interconnector transmission through the linked equations is unresolved in the retained factor archive. "
    if len(good):text+="At least one regional price-movement comparison passes both chronological phases and the declared evidence gates. Its controlled estimate is shown separately. "
    else:text+="A confirmed asset-specific price-movement effect is not supported by the declared gates; numerical headline attribution is withheld. "
    text+="Higher demand, reduced alternative generation, adverse flow direction and concurrent outages are conditions to inspect. A binding restriction can displace feasible generation and create congestion; a slack restriction can leave prices and flows largely unchanged."
    return text


def build(c):
    out=c["_report"];out.mkdir(parents=True,exist_ok=True);dl=out/"downloads";dl.mkdir(exist_ok=True)
    names=["cohort","asset_register","outage_ledger","events","asset_set_audit","asset_constraint_crosswalk",
           "price_effects","network_effects","falsification","event_summary","case_selection","generation_response","interconnector_event_response","mechanism_summary","setter_summary",
           "equation_ic_terms","equation_cp_terms","daily_prices","price_thresholds","outlook_bookings","outlook_replay","outlook_backtest_scores","outlook_price_backtest","offer_summary","event_constraint_observations"]
    d={n:load(c,n) for n in names}
    # Raw interval rows stay local. Ship compact evidence and detailed offer counts, not full bid or fitted-model data.
    export_names=[n for n in names if n not in ["outage_ledger","equation_cp_terms","equation_ic_terms","event_constraint_observations"]]
    for n in export_names:
        frame=d[n]
        if n=="price_effects":
            frame=frame.copy()
            for col in ["effect","ci_lo","ci_hi","treated_mean","control_mean"]:
                frame.loc[~frame.display_estimate,col]=np.nan
        if n=="network_effects":
            frame=frame.copy()
            gate=(frame.episodes.ge(c["minimum_episodes"])&frame.matched.ge(c["minimum_treated_hours"]*12)&frame.match_rate.ge(c["minimum_match_rate"]))
            for col in ["effect","ci_lo","ci_hi","treated_mean","control_mean"]:
                frame.loc[~gate,col]=np.nan
            frame["minimum_support_pass"]=gate
        frame.to_csv(dl/(n+".csv"),index=False)
    for name in ["sources.json","coverage.json","outlook_provenance.json","offer_sources.json","supplement_sources.json"]:
        shutil.copyfile(c["_data"]/name,dl/name)
    provenance=json.loads((c["_data"]/"outlook_provenance.json").read_text(encoding="utf-8"))
    source=json.loads((c["_data"]/"sources.json").read_text(encoding="utf-8"))
    references=json.loads((ROOT/"execution/line_outage_risk_v1/reference_notes.json").read_text(encoding="utf-8"))
    offers=json.loads((c["_data"]/"offer_sources.json").read_text(encoding="utf-8"))
    co=d["cohort"];effects=d["price_effects"];events=d["event_summary"]
    confirmed=int(effects.confirmed.sum());physical=d["events"][d["events"].asset.isin(co.asset)]
    md=["# NEM transmission-line outages: congestion, interconnectors and price risk", "",
        f"Historical window: September 2024–August 2026. {len(co)} line profiles; {int(co.deep_dive.sum())} deep dives; {len(physical)} merged asset-level equipment events.","",
        "Events are merged within each asset. Counts across assets can include the same multi-equipment outage and are not globally independent.","",
        "The study uses final-state outage truth for historical research and a separately frozen booking snapshot for its outlook. Reported interconnector limits are dispatch outputs, not maximum secure physical transfer capability.","",
        f"Confirmed regional movement tests: {confirmed}. Failed gates withhold numerical attribution. Sparse equipment events, concurrent work and configuration uncertainty remain consequential limits.",""]
    body=hero("NEM · TRANSMISSION RESEARCH","When a line goes out,","where does the risk move?",
      "An asset-specific atlas of grid mechanisms, congestion, interconnector response and regional price volatility.",
      ["Sep 2024–Aug 2026",f"{len(co)} lines · {int(co.deep_dive.sum())} deep dives","NEM UTC+10 · five-minute observations","Retrospective research"])
    body+='<nav><a href="#findings">Findings</a> · <a href="#mechanisms">Grid mechanics</a> · <a href="#atlas">Line atlas</a> · <a href="#deep-dives">Deep dives</a> · <a href="#outlook">Outlook</a> · <a href="#methods">Methods</a> · <a href="#sources">Sources</a></nav>'
    body+='<p class="mobile-hint">Scroll horizontally inside charts, diagrams and tables to see the full view.</p>'
    body+='<div class="metrics">'+metric("Selected lines",len(co),"Identity and region resolved")+metric("Asset-level events",len(physical),"Merged within each asset")+metric("Deep-dive lines",int(co.deep_dive.sum()),f"{len(d['case_selection'])} high/typical/low cases")+metric("Confirmed price tests",confirmed,"Both phases and evidence gates")+'</div>'
    body+='<div class="callout">Physical outages, booked work and invoked sets are separate observations. The old line-6 V-DDSM family fallback is excluded. Unsupported asset effects and uncalibrated future probabilities are withheld.</div>'
    body+='<section id="findings"><h2>01 · What the evidence says</h2><div class="findings">'
    body+=finding(1,"Start with the actual equipment",f"The selected cohort contains {len(physical)} merged asset-level events. Events across different lines can share the same multi-equipment outage. Secondary work and withdrawn bookings are excluded from physical treatment.")
    requested=events[events.asset.isin(c['mandatory_assets'])]
    requested_peak=requested.max_price.max()
    body+=finding(2,"Lines 6 and 8 show security mechanisms",f"Own-set binding is recorded for {d['mechanism_summary'].loc[d['mechanism_summary'].binding_intervals.gt(0),'asset'].nunique()} selected assets. The requested lines include voltage protection, plus line 6 stability and line 8 thermal contingency limits. Across their retained events, NSW RRP peaked at A${requested_peak:,.2f}/MWh. Binding security limits do not automatically create a price spike.")
    body+=finding(3,"Statistical gates matter",f"{confirmed} regional movement tests pass chronological confirmation. Exact matching often has limited overlap because other outages change the network configuration. The report retains failed and null tests.")
    body+='</div>'
    movement=effects[effects.outcome.eq('price_change')]
    gates=movement.groupby('period').agg(tests=('asset','size'),
      five_matched_episodes=('episodes',lambda s:int(s.ge(c['minimum_episodes']).sum())),
      matched_hours_24=('matched',lambda s:int(s.ge(c['minimum_treated_hours']*12).sum())),
      matching_60_percent=('match_rate',lambda s:int(s.ge(c['minimum_match_rate']).sum())),
      balance_pass=('max_smd',lambda s:int(s.le(c['maximum_smd']).sum())),
      combined_support=('support','sum'),displayable=('display_estimate','sum')).reset_index()
    gate_note='Counts apply to the 50 × 5 regional primary movement tests in each phase. Each condition is counted separately, not as a waterfall. Combined support requires all support conditions; displayability adds placebo, pretrend, leave-one-event-out and sensitivity gates. ' + f' Confirmation tests meeting combined support: {int(gates.loc[gates.period.eq("confirmation"),"combined_support"].sum())}.'
    body+='<h3>Why numerical price attribution is withheld</h3>'+table(gates)+'<p>'+gate_note+'</p>'
    md+=['## Findings and evidence gates','',f'Requested lines: observed own-set voltage protection, line 6 stability and line 8 thermal contingency limits. Highest NSW RRP across their retained events: A${requested_peak:,.2f}/MWh. These are observations, not an isolated outage contribution.','',markdown_table(gates),'',gate_note,'']
    daily=d["daily_prices"];complete=daily[daily.complete]
    regional_context=complete.groupby("region").agg(days=("nem_day","count"),mean_abs_change=("mean_change","mean"),
      median_daily_sd=("price_sd","median"),median_daily_p95_p05=("price_range","median"),
      spike1000_share=("spike1000","mean"),negative_share=("negative","mean")).reset_index()
    body+='<h3>Regional volatility context</h3><p>These are whole-window market measurements, not effects attributable to the selected outages. Daily dispersion uses complete 288-interval NEM days.</p>'+table(regional_context)
    md+=['### Regional volatility context','',markdown_table(regional_context),'','Whole-window measurements on complete NEM days; no outage attribution is implied.','']
    fig=go.Figure()
    for region,g in complete.groupby("region"):
        monthly=g.assign(month=g.nem_day.dt.to_period("M").astype(str)).groupby("month").mean_change.mean()
        fig.add_trace(go.Scatter(x=monthly.index,y=monthly.values,name=region,mode="lines+markers",line=dict(color=REGION_COLORS[region])))
    fig.update_yaxes(title="Mean absolute five-minute price change (A$/MWh)")
    body+=figure_html(chart(fig,"Regional price movement through the study window"),"Figure · Whole-market volatility context","No outage attribution is implied. Extremes and dispersion are reported separately.","downloads/daily_prices.csv")
    fig=go.Figure(go.Bar(y=co.description,x=co.events,orientation="h",marker_color="#5696b9"))
    fig.update_yaxes(categoryorder="array",categoryarray=list(co.description)[::-1]);fig.update_xaxes(title="Merged verified asset-level events")
    body+=figure_html(chart(fig,"Physical outage evidence by selected line",1450),"Figure 1 · Evidence is uneven across assets","Actual-window primary-equipment events only. Administrative overlap does not multiply sample size.","downloads/cohort.csv")
    match=effects[effects.outcome.eq("price_change")&effects.period.eq("confirmation")]
    pivot=match.pivot(index="asset",columns="region",values="match_rate").reindex(co.asset)
    fig=go.Figure(go.Heatmap(z=pivot.to_numpy()*100,x=pivot.columns,y=co.description,colorscale="Blues",zmin=0,zmax=100,colorbar_title="Match %"))
    body+=figure_html(chart(fig,"Exact-control availability in the confirmation year",1200),"Figure 2 · Matching coverage, not an effect ranking","Same time, season, day type, demand/temperature bins and other-outage signatures. No fallback to relaxed controls for headlines.","downloads/falsification.csv")
    body+='</section><section id="mechanisms"><h2>02 · The grid-to-price mechanism</h2>'
    body+='<div class="mechanism-chain"><span>Line unavailable</span><b>→</b><span>Network configuration</span><b>→</b><span>Security equations</span><b>→</b><span>Feasible dispatch</span><b>→</b><span>Flows and regional prices</span></div>'
    md+=['## Grid mechanics','']
    for title,text in MECHANISM_PROSE:
        body+=f'<h3>{escape(title)}</h3><p>{escape(text)}</p>';md+=["### "+title,"",text,""]
    labels={"NSW1-QLD1":"QNI","N-Q-MNSP1":"Directlink","VIC1-NSW1":"VNI","V-SA":"Heywood","V-S-MNSP1":"Murraylink","T-V-MNSP1":"Basslink"}
    orientation=pd.DataFrame([{"link":labels[ic],"interconnector_id":ic,"positive_flow":source+" → "+sink} for ic,(source,sink) in IC_REGIONS.items()])
    body+='<h3>Flow directions used in this report</h3>'+table(orientation)+'<p>A negative flow uses the opposite direction. Forward and reverse capacity are shown separately, without clipping signed values.</p>'
    md+=['### Interconnector orientation','',markdown_table(orientation),'']
    body+='<p>Sources: AEMO Congestion Information Resource and network diagrams; exact MMSDM equation versions and dispatch observations. These explanations describe possible transmission paths. Each asset chapter states what was actually observed.</p></section>'
    body+='<section id="atlas"><h2>03 · Fifty-line atlas</h2><p>Filter by line, substation, region or set. Importance selections use a recorded corridor screen and direct equation evidence; they are not a validated ranking of physical network criticality.</p><label for="line-search">Find a line</label> <input id="line-search" type="search" placeholder="Try Canberra, Dapto, Dederang…"><p id="search-count" aria-live="polite"></p>'
    md+=['## Line atlas','']
    for r in co.itertuples():
        p=profile_text(r.asset,r,d["asset_set_audit"],d["mechanism_summary"],effects,d["equation_cp_terms"],d["equation_ic_terms"],d["asset_constraint_crosswalk"])
        own=d["asset_set_audit"][d["asset_set_audit"].asset.eq(r.asset)]
        cw=d["asset_constraint_crosswalk"][d["asset_constraint_crosswalk"].asset.eq(r.asset)].drop_duplicates(["family","constraint","description"])
        eq=cw.constraint.head(15)
        bound=d["mechanism_summary"][d["mechanism_summary"].asset.eq(r.asset)].groupby(["constraint","description","limit_type"],dropna=False).agg(binding_intervals=("binding_intervals","sum"),events=("event_id","nunique")).reset_index().sort_values("binding_intervals",ascending=False)
        available=effects[effects.asset.eq(r.asset)&effects.display_estimate]
        diag=effects[effects.asset.eq(r.asset)&effects.period.eq("confirmation")&effects.outcome.eq("price_change")]
        body+=f'<article class="line-profile" id="{slug(r.asset)}"><h3>{escape(r.description)}</h3><p class="tags"><span>{escape(r.asset)}</span><span>{escape(r.region)}</span><span>{escape(r.selection_route)}</span><span>{r.events} events</span></p><p>{escape(p)}</p>'
        notes=[n for n in references["notes"] if n["asset"]==r.asset]
        for n in notes:
            body+=f'<p>{escape(n["text"])} <a href="{escape(n["url"],quote=True)}">{escape(n["title"])}</a></p><p class="figure-note">{escape(n["claim_boundary"])}</p>'
        if r.asset=="CANBERRA/LINE/6":
            body+=f'<div class="callout">Line 6: {r.events} verified primary-equipment events. Direct sets: {escape(", ".join(sorted(set(own.family))))}. The previous V-DDSM fallback is an unrelated family context and is not used for this asset.</div>'
            body+='''<figure><figcaption>Documented historical route · conceptual outage interpretation</figcaption><div class="chart-scroll"><svg viewBox="0 0 900 190" role="img" aria-label="Historical Canberra to Capital to Kangaroo Valley route, with line 6 between Canberra and Capital" style="width:100%;min-width:900px;height:auto"><rect x="30" y="55" width="180" height="60" rx="8" fill="#ececf3"/><rect x="355" y="55" width="180" height="60" rx="8" fill="#ececf3"/><rect x="685" y="55" width="180" height="60" rx="8" fill="#ececf3"/><path d="M210 85H355 M535 85H685" stroke="#5696b9" stroke-width="5"/><path d="M275 65l20 40m0-40l-20 40" stroke="#c55858" stroke-width="5"/><text x="120" y="92" text-anchor="middle" font-size="18">Canberra</text><text x="445" y="92" text-anchor="middle" font-size="18">Capital</text><text x="775" y="92" text-anchor="middle" font-size="18">Kangaroo Valley</text><text x="280" y="42" text-anchor="middle" font-size="17">Line 6 · outage</text><text x="610" y="42" text-anchor="middle" font-size="17">Line 3W</text><text x="445" y="158" text-anchor="middle" font-size="15">Remaining supplies, generation and switching determine the consequence.</text></svg></div><p class="figure-note">Connectivity from the Transgrid 3W assessment. This is a historical route illustration, not a current switching diagram or power-flow simulation.</p></figure>'''
        if len(cw):
            body+='<h4>What the directly linked equations protect</h4>'+table(cw.head(12),["family","constraint","limit_type","description","definition_status"])
        if len(bound):body+='<h4>Observed own-set binding</h4>'+table(bound.head(8))
        setters=d["setter_summary"][d["setter_summary"].asset.eq(r.asset)]
        body+='<details><summary>Which equations set conditional interconnector bounds</summary>'+table(setters.head(24),["event_id","ic","direction","intervals","own_member_leader_share","top_versioned_leaders","membership_resolved"])+ '<p>Limit setting is distinct from binding. An equation can belong to several sets; membership alone does not attribute the leader to this equipment outage.</p></details>'
        if len(available):body+='<h4>Supported controlled estimates</h4>'+table(available,["region","period","outcome","effect","ci_lo","ci_hi","episodes","matched","q_value"])
        else:body+='<p><strong>Asset-specific numerical price effect withheld.</strong> See the matching diagnostics and event measurements below.</p>'
        body+='<details><summary>Confirmation-year evidence gates</summary>'+table(diag,["region","episodes","matched","match_rate","max_smd","support","placebo_pass","pretrend_pass","leave_one_out_stable"])+ '</details>'
        ev=events[events.asset.eq(r.asset)]
        body+='<details><summary>Verified event catalogue and observed prices</summary>'+table(ev,["event_id","start","end","hours","max_price","min_price","price_sd","p95_p05","mean_abs_change","spike1000_share","spike1000_longest_minutes","negative_share","negative_longest_minutes","multi_equipment"])+ '<p>Price dispersion and ranges are A$/MWh; tail shares are fractions and longest runs are minutes within the observed event window.</p></details>'
        # Native factor terms: show one version associated with an observed binding equation, preserve identity visibly.
        obs=d["event_constraint_observations"]
        obs=obs[obs.asset.eq(r.asset)&obs.binding] if len(obs) else obs
        if len(obs):
            peak=obs.sort_values("MARGINALVALUE",key=lambda s:s.abs(),ascending=False).iloc[0]
            t=d["equation_ic_terms"]
            t=t[t.GENCONID.eq(peak.CONSTRAINTID)&t.EFFECTIVEDATE.eq(peak.EFFECTIVEDATE)&t.VERSIONNO.eq(peak.VERSIONNO)]
            cp=d["equation_cp_terms"]
            cp=cp[cp.GENCONID.eq(peak.CONSTRAINTID)&cp.EFFECTIVEDATE.eq(peak.EFFECTIVEDATE)&cp.VERSIONNO.eq(peak.VERSIONNO)]
            body+=f'<details><summary>Exact-version example: {escape(str(peak.CONSTRAINTID))}</summary><p>Observed at {escape(str(peak.time))}; effective {escape(str(peak.EFFECTIVEDATE))}, version {peak.VERSIONNO:g}. LHS {peak.LHS:.3f}; RHS {peak.RHS:.3f}; marginal value {peak.MARGINALVALUE:.3f}. The marginal value is an optimisation sensitivity, not the asset’s regional price effect.</p>'
            body+='<p>Selected interconnector and energy connection-point terms are shown below, with the exact observed version. This compact view omits FCAS, regional and dynamic RHS formulations; it is not the complete native equation.</p>'+table(t,["INTERCONNECTORID","FACTOR"])+table(cp.reindex(columns=["CONNECTIONPOINTID","FACTOR"]).head(15))+ '</details>'
        body+='</article>'
        md+=["### "+r.description,"",p,"",f"Canonical asset: `{r.asset}`. Selection route: {r.selection_route}.","",markdown_table(cw.head(12)) if len(cw) else "Direct equation mapping unresolved.","",markdown_table(ev[["start","end","max_price","min_price","price_sd","p95_p05","mean_abs_change","spike1000_longest_minutes","negative_longest_minutes"]]),"","Observed own-set binding:","",markdown_table(bound.head(8)) if len(bound) else "Unresolved or no observed own-set binding.","","Confirmation-year evidence gates:","",markdown_table(diag[["region","episodes","matched","match_rate","max_smd","support"]]),""]
        for n in notes:md+=[n["text"]+f' [{n["title"]}]({n["url"]})',"",n["claim_boundary"],""]
    body+='</section><section id="deep-dives"><h2>04 · Deep-dive event reconstructions</h2><p>High, median and low observed price-movement events are selected by a declared descriptive rule. The timelines do not isolate the outage’s causal contribution. All six interconnectors and five regional price series are retained in local native-resolution evidence.</p>'
    offer_sources=offers.get("sources",[])
    parsed=sum(s.get("status")=="parsed" for s in offer_sources)
    unavailable=sum(s.get("status")!="parsed" for s in offer_sources)
    sampled_cases=d['offer_summary'].event_id.nunique()
    no_units=sum(not units for units in offers.get('case_duids',{}).values())
    offer_note=f'Offer acquisition: {parsed} required monthly table archives parsed; {unavailable} unavailable. {sampled_cases} of {len(d["case_selection"])} cases have retained unit-case samples; {no_units} cases have no mapped sampled DUID. The sample retains native offer revisions and participant rebid text for up to 20 equation-sensitive units per case. Line 6 also uses documented Capital/Woodlawn candidates; the same top-20 cap applies. Missing samples do not establish an absence of rebidding.'
    body+='<p>'+offer_note+' Full unit/date coverage and source hashes are in <a href="downloads/offer_sources.json">offer_sources.json</a>.</p>'
    md+=['## Deep-dive event reconstructions','']
    md+=[offer_note,'']
    for r in co[co.deep_dive].itertuples():
        cases=d["case_selection"][d["case_selection"].asset.eq(r.asset)]
        body+=f'<h3>{escape(r.description)}</h3>'+table(cases,["case_role","event_id","start","end","hours","max_price","min_price","mean_abs_change","binding_equations"])
        md+=["### "+r.description,"",markdown_table(cases[["case_role","start","end","max_price","min_price","binding_equations"]]),""]
        for e in cases.itertuples():
            response=d["interconnector_event_response"]
            response=response[response.event_id.eq(e.event_id)]
            means=response.pivot(index="ic",columns="state",values="mean_flow_mw")
            if {"before","during"}.issubset(means.columns):
                movement=(means.during-means.before).dropna()
                largest=movement.abs().idxmax() if len(movement) else None
            else:largest=None
            wording=f"The {e.case_role.replace('_',' ')} case runs from {e.start} to {e.end} ({e.hours:.1f} observed hours). {e.region} prices ranged from A${e.min_price:,.2f} to A${e.max_price:,.2f}/MWh; mean absolute five-minute movement was A${e.mean_abs_change:,.2f}/MWh. "
            if largest:wording+=f"The largest before-to-during change in mean interconnector flow was {largest}: {movement[largest]:+,.1f} MW in its native orientation. "
            wording+=f"The event had {e.mean_co_outages:.1f} other identified high-voltage equipment outages on average in its region and {e.binding_equations} own-set equations with observed binding. These measurements describe the joint operating state; they do not isolate this line's contribution."
            body+='<p>'+escape(wording)+'</p>'
            md+=[wording,'']
            md+=['Interconnector response (dispatch outputs; reverse capacity = −IMPORTLIMIT; spreads are sink minus source RRP):','',markdown_table(response[["ic","state","intervals","mean_flow_mw","mean_forward_limit_mw","mean_reverse_capacity_mw","minimum_forward_limit_mw","minimum_reverse_capacity_mw","mean_price_spread"]]),'']
            body+='<details><summary>'+escape(e.case_role.replace('_',' ').title())+' · interconnector limits, flow and price spreads</summary>'+table(response,["ic","state","intervals","mean_flow_mw","mean_forward_limit_mw","mean_reverse_capacity_mw","minimum_forward_limit_mw","minimum_reverse_capacity_mw","mean_price_spread"])+ '<p>Before and after windows are 48 hours. Spreads are sink minus source regional RRP in the connector’s native orientation; values are A$/MWh. Reverse capacity is −IMPORTLIMIT. Signed negative limits can represent forced flow. These are dispatch outputs.</p></details>'
            if e.case_role!="high_stress":continue
            fig=make_subplots(rows=2,cols=1,shared_xaxes=True,vertical_spacing=.12,subplot_titles=["Regional reference prices","Interconnector flows"])
            for region in REGIONS:
                f=pd.read_parquet(c["_data"]/"timelines"/f"{e.event_id}_{region}.parquet")
                # Chart sampling is regular, while extreme intervals are retained. Evidence remains native resolution.
                idx=np.unique(np.r_[np.arange(0,len(f),max(1,len(f)//1600)),np.flatnonzero((f.RRP>1000)|(f.RRP<-100))])
                g=f.iloc[idx]
                fig.add_trace(go.Scatter(x=g.time,y=g.RRP,name=region,mode="lines",line=dict(color=REGION_COLORS[region])),row=1,col=1)
            for ic in STUDIES:
                f=pd.read_parquet(c["_data"]/"timelines"/f"{e.event_id}_{ic}.parquet")
                g=f.iloc[::max(1,len(f)//1600)]
                fig.add_trace(go.Scatter(x=g.time,y=g.flow,name=ic,mode="lines",line=dict(color=IC_COLORS[ic])),row=2,col=1)
            for row in [1,2]:
                fig.add_vrect(x0=e.start,x1=e.end,fillcolor="#ce9a48",opacity=.1,line_width=0,row=row,col=1)
            fig.update_yaxes(title="A$/MWh",row=1,col=1);fig.update_yaxes(title="MW (native orientation)",row=2,col=1)
            body+=figure_html(chart(fig,f"{r.description} · {e.event_id}",780),"Price and flow timeline · shaded equipment window","Chart sampling retains extreme price intervals. Other outages, offers and market conditions can contribute to every response.","downloads/case_selection.csv")
        offer=d["offer_summary"][d["offer_summary"].asset.eq(r.asset)]
        gen=d["generation_response"][d["generation_response"].asset.eq(r.asset)]
        body+='<details><summary>Generation dispatch before, during and after the cases</summary>'+table(gen.head(45),["event_id","DUID","state","intervals","mean_dispatch_mw","min_dispatch_mw","max_dispatch_mw"])+ '<p>These are observed dispatch levels, not an isolated outage contribution. Native DUID timelines remain in the local evidence cache.</p></details>'
        body+='<details><summary>Offers and rebids in the selected event sample</summary>'+table(offer.head(30),["event_id","DUID","daily_revisions","period_records","changed_price_bands","rebid_reasons"])+ '<p>Revisions are descriptive. A dispatch-stack counterfactual is withheld until exact native offer pairing and historical timing pass validation. Reasons are participant text and do not establish strategic intent.</p></details>'
        md+=["Offer/rebid unit-case records: "+str(len(offer))+". See downloads/offer_summary.csv; no strategic-intent or dispatch-stack attribution is claimed.",""]
        md+=['Observed generation dispatch (compact sample; full evidence in downloads):','',markdown_table(gen.head(18)[["event_id","DUID","state","mean_dispatch_mw","min_dispatch_mw","max_dispatch_mw"]]),'','Offers and rebids (compact sample):','',markdown_table(offer.head(10)[["event_id","DUID","daily_revisions","period_records","changed_price_bands","rebid_reasons"]]),'']
    body+='</section><section id="outlook"><h2>05 · Booked outages: 90-day outlook and annual watchlist</h2>'
    body+=f'<p>Snapshot generated {escape(str(provenance.get("generated_nem")))} NEM time. Source: {escape(str(provenance.get("source")))}. Receipt UTC: {escape(str(provenance.get("received_utc")))}. Snapshot age at retrieval: {provenance.get("age_hours",0):.2f} hours.</p>'
    body+='<div class="callout">Numerical future price-risk probabilities are withheld. Historical receipt provenance and independent calibration are not verified. Use the booking list as a conditional mechanism assessment. Effects of overlapping work are not additive.</div>'
    bookings=d["outlook_bookings"]
    bookings=bookings.copy()
    history_context={}
    for asset in co.asset:
        equations=set(d["asset_constraint_crosswalk"].loc[d["asset_constraint_crosswalk"].asset.eq(asset),"constraint"])
        links=d["equation_ic_terms"];ics=sorted(set(links.loc[links.GENCONID.isin(equations),"INTERCONNECTORID"]))
        types=sorted(set(d["asset_constraint_crosswalk"].loc[d["asset_constraint_crosswalk"].asset.eq(asset),"limit_type"]))
        history_context[asset]="Historical channels: "+(", ".join(types) if types else "unresolved")+"; IC terms: "+(", ".join(ics) if ics else "unresolved")
    bookings["historical_mechanism_context"]=bookings.asset.map(history_context)
    body+='<p>Mechanism context comes from resolved historical equations for the asset. It is a screening guide: verify the booked configuration, current set membership, actual invocation, demand and generator availability near the work. It is not a claim that the same equations will apply to the future booking.</p>'
    for label,mask in [("Next 90 days",bookings.lead_days.le(90)),("Annual structural watchlist",bookings.lead_days.gt(90))]:
        body+='<h3>'+label+'</h3>'+table(bookings[mask].sort_values(["start","region"]),["description","region","start","end","lead_band","linked_sets","historical_mechanism_context","historical_events","overlap_ids"])
    replay=d["outlook_replay"]
    body+='<h3>Historical booking replay</h3>'+table(replay.groupby(["lead_band","truth"]).size().rename("bookings").reset_index())
    body+='<h3>Chronological conditional price-risk probe</h3>'+table(d["outlook_backtest_scores"])
    body+='<p>The probe compares a shrunk pre-origin asset spike rate with the trailing regional rate, using only earlier observed prices. Alert thresholds use the first six available origins; evaluation uses subsequent origins. Final-state asset history and missing receipt provenance limit this to conditional research. Brier scores are interval-event scores. This does not pass a live forecasting gate, and numerical probabilities remain withheld from current bookings.</p></section>'
    supplement=json.loads((c["_data"]/"supplement_sources.json").read_text(encoding="utf-8"))
    missing=supplement.get("families_without_membership",[])
    unresolved_at_start=int(d['asset_set_audit'].membership_equations.eq(0).sum())
    unresolved_setters=int((~d['setter_summary'].membership_resolved).sum())
    membership_note=f'Constraint membership was supplemented with all study-month changes and a two-year pre-window lookback. {len(missing)} linked families have no recovered membership anywhere in that archive. This is not complete historical coverage: {unresolved_at_start} of {len(d["asset_set_audit"])} direct asset-set links lack recovered membership at their start, and {unresolved_setters} of {len(d["setter_summary"])} event/interconnector/direction rows have unresolved own-set membership (including events with no verified direct set). Unresolved equation definitions are retained separately; none is treated as zero effect.'
    body+='<p>'+membership_note+'</p>'
    md+=['## Booking outlook','',f"Snapshot: {provenance.get('snapshot_id')}; generated {provenance.get('generated_nem')} NEM time; receipt {provenance.get('received_utc')} UTC.","",
         "Numerical probabilities withheld: historical receipt and independent calibration gates have not passed. Overlapping effects are not additive.","",markdown_table(bookings[["description","region","start","end","lead_band","linked_sets"]]),""]
    md+=[membership_note,'','### Historical booking replay','',markdown_table(replay.groupby(["lead_band","truth"]).size().rename('bookings').reset_index()),'','### Conditional price-risk probe','',markdown_table(d['outlook_backtest_scores']),'','Conditional final-state-history research; historical receipt provenance and independent calibration remain unverified.','']
    body+='<section id="methods"><h2>06 · Methods, limitations and reproducibility</h2>'
    methods=(ROOT/"execution/line_outage_risk_v1/METHODOLOGY.md").read_text(encoding="utf-8")
    import markdown
    body+=markdown.markdown(methods,extensions=["tables"])
    body+='<h3>Outstanding evidence boundaries</h3><ul><li>Historical final-state records do not prove issue-time availability.</li><li>Corridor screening and dispatch equations do not replace a physical network-security study.</li><li>Some linked equations are absent from the retained sparse archive; no zero effect is imputed.</li><li>Independent price effects are withheld when support, balance, placebo or stability gates fail.</li><li>Offer sample dates and DUIDs are limited and disclosed in offer_sources.json.</li><li>Current outlook uses conditional mechanisms; no calibrated asset price-risk model is promoted.</li></ul>'
    body+='<p>Rebuild: <code>python scripts/run_line_outage_research.py --stage report</code>. Full campaign: <code>python scripts/run_line_outage_research.py --stage all</code>. Generated intervals and raw bids remain local.</p></section>'
    md+=['## Methods and limitations','',methods,'','## Rebuild','', '`python scripts/run_line_outage_research.py --stage all`', '']
    body+='<section id="sources"><h2>07 · Sources and downloadable evidence</h2><ul>'
    md+=['## Sources','']
    for s in source["references"]:
        body+=f'<li><a href="{escape(s["url"],quote=True)}">{escape(s["title"])}</a> — {escape(s["use"])}</li>'
        md += [f'- [{s["title"]}]({s["url"]}): {s["use"]}']
    body+='</ul><h3>Evidence package</h3><ul>'
    md+=['','### Downloadable evidence','']
    for p in sorted(dl.iterdir()):
        body+=f'<li><a download href="downloads/{escape(p.name)}">{escape(p.name)}</a></li>'
        md+=[f'- [{p.name}](downloads/{p.name})']
    body+='</ul><p>Charts and styles are embedded and work offline. Download links require the accompanying downloads directory.</p></section>'
    body+='''<style>.mobile-hint{display:none}@media(max-width:900px){.mobile-hint{display:block;font-size:13px;color:#636870}}.table-scroll th,.table-scroll td{min-width:130px}.table-scroll{max-width:100%;overflow-x:auto}table{white-space:normal}td{max-width:600px;overflow-wrap:anywhere}.line-profile{border-top:1px solid #dfe3eb;padding:28px 0}.line-profile h3{font-size:24px}.mechanism-chain{display:flex;flex-wrap:wrap;gap:12px;align-items:center;padding:24px;background:#ececf3}.mechanism-chain span{background:white;border:1px solid #dfe3eb;padding:12px;border-radius:8px}input{padding:12px;width:min(100%,440px);border:1px solid #dfe3eb;border-radius:6px}.chart-scroll{overflow-x:auto}details{margin:16px 0}summary{cursor:pointer;font-weight:650}.tags{display:flex;flex-wrap:wrap;gap:8px}.tags span{overflow-wrap:anywhere}nav{display:flex;flex-wrap:wrap;gap:9px}article[hidden]{display:none}h4{font-size:17px}</style>
<script>const search=document.getElementById('line-search');const profiles=[...document.querySelectorAll('.line-profile')];function filter(){const q=search.value.toLowerCase();let n=0;profiles.forEach(p=>{p.hidden=!p.textContent.toLowerCase().includes(q);if(!p.hidden)n++;});document.getElementById('search-count').textContent=n+' lines shown';}search.addEventListener('input',filter);filter();</script>'''
    html=render_page("NEM line-outage congestion and price-risk atlas",body,plotly=True,accent="blue")
    (out/"index.html").write_text(html,encoding="utf-8");(out/"REPORT.md").write_text("\n".join(md),encoding="utf-8")
    inputs={str(p.relative_to(ROOT)):sha(p) for p in c["_data"].glob("*.parquet")}
    inputs.update({str(p.relative_to(ROOT)):sha(p) for p in Path(__file__).parent.glob("*.py")})
    inputs.update({str(p.relative_to(ROOT)):sha(p) for p in (c['_data']/'timelines').glob('*.parquet')})
    inputs.update({str((c['_data']/name).relative_to(ROOT)):sha(c['_data']/name) for name in ['sources.json','coverage.json','outlook_provenance.json','offer_sources.json','supplement_sources.json']})
    inputs["execution/line_outage_risk_v1/reference_notes.json"]=sha(ROOT/"execution/line_outage_risk_v1/reference_notes.json")
    for p in [c['_config'],ROOT/'execution/line_outage_risk_v1/METHODOLOGY.md',ROOT/'scripts/report_theme/report_theme.py',ROOT/'scripts/report_theme/report.css',ROOT/'requirements-line-outages.txt',ROOT/'requirements.txt']:
        inputs[str(p.relative_to(ROOT))]=sha(p)
    json_write(out/"manifest.json",{"report_id":c["experiment_id"],"data_cutoff_nem":c["window_end"],"build_utc":pd.Timestamp.now(tz="UTC").isoformat(),
       "inputs":inputs,"outputs":{str(p.relative_to(out)):sha(p) for p in [out/"index.html",out/"REPORT.md",*dl.iterdir()]},
       "profiles":len(co),"deep_dives":int(co.deep_dive.sum()),"confirmed_price_tests":confirmed,
       "dependencies":{"python":sys.version,**{package:importlib.metadata.version(package) for package in ['pandas','numpy','plotly','polars','beautifulsoup4','markdown','tabulate']}},
       "outlook_probability_gate":"withheld","visual_qa":{"record":"../../execution/line_outage_risk_v1/report_qa.json","requires_matching_html_sha256":True}})
    return {"profiles":len(co),"deep_dives":int(co.deep_dive.sum()),"report_bytes":(out/"index.html").stat().st_size,"confirmed_price_tests":confirmed}


def validate(c):
    out=c["_report"];m=json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    failures=[]
    for name,h in m["outputs"].items():
        if not (out/name).exists() or sha(out/name)!=h:failures.append("output hash: "+name)
    for name,h in m["inputs"].items():
        if not (ROOT/name).exists() or sha(ROOT/name)!=h:failures.append("input hash: "+name)
    soup=BeautifulSoup((out/"index.html").read_text(encoding="utf-8"),"html.parser")
    ids=[tag["id"] for tag in soup.find_all(id=True)]
    if len(ids)!=len(set(ids)):failures.append("duplicate anchors")
    for tag in soup.find_all("a",href=True):
        href=tag["href"]
        if href.startswith("#") and href[1:] not in ids:failures.append("missing anchor "+href)
        elif not href.startswith(("#","https://","http://","data:")) and not (out/href).exists():failures.append("missing download "+href)
    for tag in soup.find_all(["script","link","img"]):
        link=tag.get("src",tag.get("href",""))
        if link.startswith(("https://","http://","//")):failures.append("external rendering dependency "+link)
    co=load(c,"cohort");profiles=soup.select(".line-profile")
    if len(profiles)!=len(co):failures.append("profile count mismatch")
    if not co.deep_dive.sum()==c["deep_dives"]:failures.append("deep dive count mismatch")
    expected=grid(c)
    for region in REGIONS:
        panel=pd.read_parquet(c["_data"]/("panel_"+region+".parquet"),columns=["time","RRP"])
        if not pd.DatetimeIndex(panel.time).equals(expected):failures.append("native price time grid: "+region)
        if panel.RRP.isna().any():failures.append("missing native prices: "+region)
    for ic in STUDIES:
        panel=pd.read_parquet(c["_data"]/("ic_"+ic+".parquet"),columns=["time","IMPORTLIMIT","reverse_capacity"])
        if not pd.DatetimeIndex(panel.time).equals(expected):failures.append("native interconnector time grid: "+ic)
        if not np.allclose(panel.reverse_capacity,-pd.to_numeric(panel.IMPORTLIMIT),equal_nan=True):failures.append("signed reverse capacity: "+ic)
    prices=pd.read_csv(out/"downloads/price_effects.csv")
    if prices.loc[~prices.display_estimate,["effect","ci_lo","ci_hi"]].notna().any().any():failures.append("unsupported displayed price estimate")
    booking=load(c,"outlook_bookings")
    if booking.probability.notna().any():failures.append("unvalidated current probability published")
    qa_path=c["_execution"]/"report_qa.json"
    qa=json.loads(qa_path.read_text(encoding="utf-8")) if qa_path.exists() else {}
    visual=qa.get("html_sha256")==sha(out/"index.html") and qa.get("passed") is True and qa.get("visual_inspection") is True
    result={"passed":not failures,"failures":failures,"profile_count":len(profiles),"anchors":len(ids),"offline_dependencies":True,
            "visual_browser_verification":"passed" if visual else "pending desktop/mobile screenshot inspection","checked_utc":pd.Timestamp.now(tz="UTC").isoformat()}
    json_write(c["_data"]/"validation.json",result)
    if failures:raise RuntimeError("Report validation failed: "+"; ".join(failures))
    return result
