"""Offline editorial report and embedded forensic explorer; renders cached evidence only."""
from html import escape as e
import base64,gzip,shutil
import numpy as np
import plotly.graph_objects as go
from .core import *
from .analyse import result
from .theme.report_theme import hero,metric,finding,figure_html,style_plotly,render_page
from .cases import ea_case
from .portfolio_digest import render as render_portfolio_digest

def fmt(x):return 'unavailable' if pd.isna(x) else f'{x:,.1f}'
def clock(x):return 'not observed' if pd.isna(x) else pd.Timestamp(x).strftime('%d %b %H:%M:%S')
def table(df,cols=None):
    df=df[cols] if cols else df
    return '<div class="table-wrap" tabindex="0">'+df.to_html(index=False,escape=True,na_rep='—',float_format=lambda x:f'{x:,.1f}',border=0)+'</div>'
def chart(fig,title,note,height=470):
    style_plotly(fig,title,height);return figure_html(fig.to_html(full_html=False,include_plotlyjs=False,config={'responsive':True,'displaylogo':False}),title,note)
def clean(frame):return json.loads(frame.to_json(orient='records',date_format='iso',double_precision=4))

def segment_narrative(r):
    before=np.array(r.before_bands);after=np.array(r.after_bands);delta=after-before
    reductions=[f'{abs(delta[i]):g} MW from ${r.before_prices[i]:,.2f}/MWh ({before[i]:g} to {after[i]:g} MW)' for i in range(10) if delta[i]<-.001]
    additions=[f'{delta[i]:g} MW to ${r.after_prices[i]:,.2f}/MWh ({before[i]:g} to {after[i]:g} MW)' for i in range(10) if delta[i]>.001]
    actions=[]
    if reductions:actions.append('reduced '+', '.join(reductions))
    if additions:actions.append('added '+', '.join(additions))
    if not actions:actions.append('changed operating parameters without moving band MW')
    text=f'At {clock(r.offer_time)}, {r.DUID} ({r.direction}) '+ '; '.join(actions)+f' for interval endings {clock(r.delivery_from)} to {clock(r.delivery_to)}. '
    if r.direction=='GEN':text+=f'The stack then held {r.after_le300:g} MW at or below $300/MWh, versus {r.before_le300:g} MW before. '
    else:text+=f'The charging offer held {r.after_ge300:g} MW willing to buy at $300/MWh or higher, versus {r.before_ge300:g} MW before. '
    text+=f'Maximum offered availability was {r.before_maxavail:g} → {r.after_maxavail:g} MW. '
    text+='Reason: “'+str(r.reason)+'”. '
    return text

def run():
    init();units=result('units');panel=result('panel');seg=result('segments');rev=result('revisions');eff=result('effective');snap=result('snapshots');forecast=result('forecast');port=result('portfolios');prices=result('prices');inv=load_table('inventory')
    audit=json.loads((STATE/'analysis.json').read_text());recon=json.loads((STATE/'reconstruction.json').read_text());fmeta=json.loads((STATE/'forecast.json').read_text())
    headers=load_table('headers').set_index('offer_id')
    local=load_table('signal_LOCAL_PRICE');local=local[local.DUID.isin(inv.DUID)].copy();number(local,['LOCAL_PRICE_ADJUSTMENT','LOCALLY_CONSTRAINED'])
    def parameter_note(offer_id):
        rr=rev[rev.offer_id.eq(offer_id)]
        if rr.empty:return ''
        now=headers.loc[offer_id];before=headers.loc[rr.iloc[0].previous_offer_id]
        changes=[]
        for c in ['MINIMUMLOAD','T1','T2','T3','T4']:
            a=before[c];b=now[c]
            if pd.notna(a) and pd.notna(b) and a!=b:changes.append(f'{c}: {a:g} → {b:g} '+('MW' if c=='MINIMUMLOAD' else 'minutes'))
        return ' Start-profile changes: '+', '.join(changes)+'.' if changes else ''
    seg=seg.merge(units[['DUID','plant','technology','region','controller']],on='DUID',validate='many_to_one')
    gen=seg[seg.direction.eq('GEN')&seg.future_at_offer&seg.offer_time.ge(SIGNAL)].copy();gen['movement']=(gen.after_le300-gen.before_le300).abs()
    winners=set(gen.sort_values('movement',ascending=False).groupby(['region','technology']).head(3).plant)
    winners.update(['Mount Piper','Tallawarra']);winners.update(units.loc[units.starts.ne('')|units.large_falls.ne(''),'plant'])
    downloads=REPORTS/'downloads';downloads.mkdir(exist_ok=True)
    # Full native/derived evidence remains local and ships alongside the single-file explorer.
    exports={'unit_summary':units,'plant_delivery_blocks':result('blocks'),'portfolio_replacement':port,'declared_capacity_gaps':result('capacity_gaps'),'reconstruction_audit':result('reconstruction_audit'),'inventory':inv,'revision_ledger':rev,'forecast_baseline':forecast}
    for name,df in exports.items():df.to_csv(downloads/(name+'.csv'),index=False)
    for name in ['segments','effective','snapshots','panel']:
        source=RESULTS/(name+'.parquet');shutil.copy2(source,downloads/source.name)
    for name in ['headers','offers_BIDOFFERPERIOD_SPARSE','dispatch_UNIT_SOLUTION','dispatch_OFFERTRK','forecast_context','signal_LOCAL_PRICE','signal_INTERCONNECTORRES','dispatch_CONSTRAINT']:
        source=TABLES/(name+'.parquet')
        if source.exists():shutil.copy2(source,downloads/source.name)
    source_records=[json.loads(p.read_text()) for p in RAW.glob('*.json')]
    write_json(downloads/'source_manifest.json',source_records)
    shutil.copy2(STATE/'registry_sources.json',downloads/'registry_sources.json')
    if (RESULTS/'timing_sensitivity.csv').exists():shutil.copy2(RESULTS/'timing_sensitivity.csv',downloads/'timing_sensitivity.csv')
    if (STATE/'market_notices.json').exists():shutil.copy2(STATE/'market_notices.json',downloads/'market_notices.json')
    body=hero('REBID MISTRESS · NEM FORENSICS','After the price spike.','Offers, output and the next risk.',
        'A plant-by-plant reconstruction of energy rebidding, actual generation and physical portfolio cover around the NSW market-cap interval.',
        ['10 October 2026 trading day','04:00–04:00 · fixed NEM time','NSW · QLD · VIC','Coal · gas · batteries','Energy only'])
    body+='<nav><a href="#findings">Findings</a><a href="#portfolio-highlights">Portfolio highlights</a><a href="#event">Event</a><a href="#explorer">Bid explorer</a><a href="#plants">Every plant</a><a href="#portfolios">Portfolios</a><a href="#methods">Methods & coverage</a><a href="#evidence">Evidence</a></nav>'
    body+='<div class="metrics">'+metric('NSW cap price ($/MWh)','$23,200','Interval ending 07:20; report generated 07:15:13')+metric('Plant accounts',audit['plants'],f"{audit['units']} identifiable registered DUIDs")+metric('Post-signal revisions',f"{audit['post_signal_revisions']:,}",'DUID/direction revisions changing future delivery intervals')+metric('Effective-offer reconciliation',f"{recon['volume_mismatches']} mismatches",f"{recon['missing_effective_links']} missing accepted-offer links")+'</div>'
    body+='<aside class="callout">This report separates a change in willingness to generate from an increase in actual generation. A cheaper or larger offer can position a plant for another disruption even if AEMO never dispatches the additional MW. Motive remains an inference unless the reasons and operating evidence support it.</aside>'
    # Findings are generated from measured outputs, not hard-coded expected stories.
    mp=units[units.DUID.isin(['MP1','MP2'])];tal=units[units.DUID.isin(['TALWA1','TALWB1'])]
    top=units.sort_values('peak_stack_shift_mw',ascending=False).iloc[0]
    findings=[('A NSW price shock',f"NSW reached the cap while QLD was ${audit['event'].get('QLD1',float('nan')):.2f}/MWh and VIC was ${audit['event'].get('VIC1',float('nan')):.2f}/MWh. Cross-region responses therefore faced different local prices."),
      ('Physical cover must be timed',f"Mount Piper’s pre-signal reference was {fmt(mp.baseline_mw.sum(min_count=len(mp)))} MW; Tallawarra’s was {fmt(tal.baseline_mw.sum(min_count=len(tal)))} MW. Tallawarra A’s afternoon return was already present in the pre-spike AEMO projection. Its later physical contribution must be distinguished from a newly chosen response to the spike."),
      ('A bid movement is not an output movement',f"{top.DUID} recorded a peak same-delivery shift of {fmt(top.peak_stack_shift_mw)} MW in offers at or below $300/MWh. The explorer shows the exact affected delivery periods and subsequent output; the shift alone does not establish motive.")]
    body+='<section id="findings"><h2>01 · What the evidence establishes</h2><div class="findings">'+''.join(finding(i+1,a,b) for i,(a,b) in enumerate(findings))+'</div></section>'
    md=['# Rebid Mistress — 10 October 2026','', 'Trading day: 04:00 10 October–04:00 11 October, fixed NEM time. Energy only. All reported power quantities are MW.','']
    for a,b in findings:md+=['## '+a,b,'']
    digest_html,digest_md=render_portfolio_digest(inv,units,panel,seg,headers,downloads)
    body+=digest_html;md+=digest_md
    pfig=go.Figure()
    for region,g in prices.groupby('REGIONID'):pfig.add_scatter(x=g.SETTLEMENTDATE,y=g.RRP,name=region,mode='lines')
    pfig.update_yaxes(title='Regional reference price ($/MWh)')
    body+='<section id="event"><h2>02 · Event and information sequence</h2><p>The 07:20 label is the interval end. The candidate information signal is the original dispatch report’s generation time, 07:15:13. Actual historical dissemination or participant receipt is not verified. SCADA is shifted from its native interval-end label to its documented interval-start observation time; it is not interval-average energy.</p>'+chart(pfig,'The trading day in three regions','AEMO Public_Prices; duplicate schema versions removed. All axes use NEM time.')
    if (TABLES/'forecast_context.parquet').exists():
        ctx=load_table('forecast_context');times(ctx,['file_generated_at','INTERVAL_DATETIME','DATETIME']);number(ctx,['RRP'])
        p5=ctx[ctx['_report'].eq('P5MIN')&ctx.REGIONID.eq('NSW1')].copy()
        if len(p5):
            target='INTERVAL_DATETIME' if 'INTERVAL_DATETIME' in p5 and p5.INTERVAL_DATETIME.notna().any() else 'DATETIME'
            warnings=p5[p5[target].eq(SPIKE)].sort_values('file_generated_at')
            if len(warnings):
                body+='<h3>What short-horizon forecasts showed for the spike interval</h3>'+table(warnings,['file_generated_at',target,'RRP'])
                body+='<p>Forecasts generated after 07:15:13 are labelled later evidence, not advance warnings. These prices do not establish which participant saw or acted on a forecast.</p>'
                warnings.to_csv(downloads/'spike_price_forecast_vintages.csv',index=False)
    body+='<h3>Network and local-price context at the spike</h3><p>AEMO reported local-price adjustments for the units below. This is direct evidence that the regional price did not describe every unit’s dispatch incentive. Flag 2 means at least one outage constraint was binding; flag 1 means a system-normal constraint with no outage constraint. The flag does not itself mean constrained-on or constrained-off. This is relevant to interpreting output, but is not a full reconstruction of the binding equations. <a href="https://www.aemo.com.au/-/media/files/electricity/nem/security_and_reliability/dispatch/policy_and_process/guide-to-mis-pricing-information.pdf">AEMO field definitions</a>.</p>'+table(local,['DUID','LOCAL_PRICE_ADJUSTMENT','LOCALLY_CONSTRAINED'])
    inter=load_table('signal_INTERCONNECTORRES')
    inter=inter[inter.INTERCONNECTORID.isin(['NSW1-QLD1','N-Q-MNSP1','VIC1-NSW1'])]
    body+=table(inter,['INTERCONNECTORID','MWFLOW','IMPORTLIMIT','EXPORTLIMIT'])+'<p>Interconnector figures are native signed MW and AEMO dispatch-solution outputs, not maximum secure physical transfer capability. Negative values are preserved. Market notices 145544/145545 were published at 07:20:19/20 for negative-residue constraint operation; their timing alone does not prove the cause of the earlier price calculation. Notice originals are retained in the evidence downloads.</p>'
    body+='</section>'
    # Same delivery, different acceptance snapshots: aggregate only the requested fleet.
    body+='<section id="regional-stacks"><h2>Regional stacks: how the selected fleet moved</h2><p>Each comparison holds delivery time fixed at 18:00. It contrasts the last pre-signal offer with the offers held 30 minutes after the signal. These are nominal-price coal/gas/battery generation stacks; other technologies and network clearing effects are excluded.</p>'
    stack_export=[]
    for region in CONFIG['regions']:
        fig=go.Figure()
        for snapshot,label in [('pre_signal','Pre-signal offers'),('plus30','Offers 30 minutes later')]:
            rr=snap[snap.snapshot.eq(snapshot)&snap.direction.eq('GEN')&snap.delivery.eq(pd.Timestamp('2026-10-10 18:00'))&snap.DUID.isin(inv.loc[inv.REGIONID.eq(region),'DUID'])]
            blocks=[]
            for r in rr.itertuples():
                with np.load(ROOT/'data/arrays'/f'{r.DUID}_GEN.npz') as ar:
                    j=int(np.flatnonzero(ar['offer_ids']==r.offer_id)[0]);k=int((r.delivery-START).total_seconds()/300)-1
                    for price,mw in zip(ar['prices'][j],ar['state'][j,k,:10]):
                        if mw>0:blocks.append((float(price),float(mw),r.DUID))
            blocks.sort();cumulative=0;x=[];y=[]
            for price,mw,duid in blocks:
                x.extend([cumulative,cumulative+mw]);y.extend([price,price]);cumulative+=mw
                stack_export.append(dict(region=region,snapshot=snapshot,delivery='2026-10-10 18:00',DUID=duid,price=price,offered_mw=mw))
            fig.add_scatter(x=x,y=y,name=label,mode='lines')
        fig.update_xaxes(title='Cumulative selected generation offers (MW)');fig.update_yaxes(title='Native offer price ($/MWh)')
        body+=chart(fig,region+' · evening delivery held fixed','Raw offers can exceed maximum availability. This is not a full regional supply curve or a simulated clearing price.',390)
    pd.DataFrame(stack_export).to_csv(downloads/'regional_evening_stacks.csv',index=False)
    body+='</section>'
    body+='<section id="explorer"><h2>03 · Follow the offer and the output</h2><p>Filter the complete revision ledger, then select an offer to inspect its band movements and reasons. The plant chart remains at native observation/dispatch timestamps. Future-period heatmaps compare each selected snapshot with the same delivery interval’s pre-signal offer.</p>'
    body+='''<div class="filters"><label>Region<select id="region"><option value="">All regions</option></select></label><label>Technology<select id="technology"><option value="">All technologies</option></select></label><label>Controller<select id="controller"><option value="">All controllers</option></select></label><label>Plant<select id="plant"><option value="">All plants</option></select></label><label>Direction<select id="direction"><option value="">Both directions</option><option>GEN</option><option>LOAD</option></select></label><label>Delivery block<select id="block"><option value="">All blocks</option><option>morning</option><option>daytime</option><option>evening</option><option>overnight</option></select></label><label>Submitted from (NEM)<input id="from" type="datetime-local" value="2026-10-10T07:15:13" step="1"></label><label>Submitted through (NEM)<input id="to" type="datetime-local" value="2026-10-11T04:00" step="1"></label><label>Reason / DUID<input id="query" placeholder="price, forecast, trip, MP1…"></label></div><p id="count">Loading embedded evidence…</p><div class="table-wrap" tabindex="0"><table><thead><tr><th>Offer</th><th>Submitted</th><th>Plant / unit</th><th>Direction</th><th>Peak shift ≤$300 (MW)</th><th>Reason</th></tr></thead><tbody id="revisions"></tbody></table></div><div class="pager"><button id="previous">Previous 50</button><button id="next">Next 50</button></div><div id="detail" class="callout">Select a revision.</div><div id="stackplot" class="interactive-chart"></div><div id="unitplot" class="interactive-chart"></div><div id="heatplot" class="interactive-chart"></div></section>'''
    body+='<section id="plants"><h2>04 · Every plant</h2><p>All identified plants are included, including those without public bids or complete SCADA. A missing record is not evidence that a plant did nothing. Detailed cases are selected by large stack changes, observed starts/falls and the mandatory Mount Piper/Tallawarra pair.</p>'
    for plant,group in units.groupby('plant',sort=True):
        duids=set(group.DUID);postseg=gen[gen.DUID.isin(duids)].sort_values('movement',ascending=False)
        headline=f'{plant} · {group.region.iloc[0]} · {" / ".join(sorted(group.technology.unique()))}'
        deep=plant in winners
        body+=f'<details class="plant-account" id="plant-{e(str(group.DUID.iloc[0]),quote=True)}"'+(' open' if plant in ['Mount Piper','Tallawarra'] else '')+f'><summary>{e(headline)}'+(' <span class="badge">Deep dive</span>' if deep else '')+'</summary>'
        md+=['## '+headline,'']
        paragraphs=[]
        for _,u in group.iterrows():
            ur=rev[rev.DUID.eq(u.DUID)&rev.post_signal&rev.future_changed_intervals.gt(0)]
            p=(f'{u.DUID}: pre-signal observed reference {fmt(u.baseline_mw)} MW; day range {fmt(u.min_mw)} to {fmt(u.max_mw)} MW; peak post-signal difference {fmt(u.peak_incremental_mw)} MW. '
               f'{u.post_signal_revisions} post-signal energy revisions changed future periods. First such revision: {clock(u.first_rebid)}; first target increase: {clock(u.first_target_increase)}; first observed output increase of at least 5 MW: {clock(u.first_output_increase)}. '
               f'Coverage: {u.scada_intervals}/288 SCADA observations and {u.dispatch_intervals}/288 dispatch targets. Assessment: {u.classification}.')
            paragraphs.append(p)
            lp=local[local.DUID.eq(u.DUID)]
            if len(lp):
                l=lp.iloc[0];flag='at least one outage constraint binding' if l.LOCALLY_CONSTRAINED==2 else 'a system-normal constraint binding' if l.LOCALLY_CONSTRAINED==1 else 'no classified network constraint';paragraphs.append(f'{u.DUID} had an AEMO local-price adjustment of ${l.LOCAL_PRICE_ADJUSTMENT:,.2f}/MWh at the spike, with {flag}. The regional price alone is therefore insufficient to infer its dispatch opportunity. The exact adjustment is in the evidence export; this study does not solve the underlying constraint equations.')
            if u.technology=='gas':paragraphs.append(f'{u.DUID} observed transitions from below 5 MW to at least 5 MW: {u.starts or "none observed"}. These are output transitions, not verified synchronisation times. {u.near_documented_ramp_intervals} positive five-minute output changes were within 10% of the converted public dispatch ramp envelope; this is descriptive and does not establish maximum engineering performance. The projected generation overlay tests whether later output was already forecast before the spike.')
            if u.technology=='battery':paragraphs.append(f'{u.DUID}: charging is negative and discharge positive. Reduced charging, added discharge and retained offered headroom are distinct. Storage percentages are shown only where the registered energy capacity is available; FCAS remains outside this analysis.')
        for p in paragraphs:body+='<p>'+e(p)+'</p>';md += [p,'']
        # Include a quantified example for each delivery block, with exact reasons.
        chosen=postseg.drop_duplicates(['offer_id','block']).groupby('block',sort=False).head(2 if deep else 1).head(8)
        for _,r in chosen.iterrows():
            text=segment_narrative(r)+parameter_note(r.offer_id);body+=f'<p class="rebid-example"><a href="#explorer" data-offer="{e(r.offer_id)}">{e(r.offer_id)}</a> — {e(text)} Interpretation: observed offer movement; strategic motive remains plausible or unresolved.</p>';md += [f'**{r.offer_id}** — '+text,'']
        if chosen.empty:
            sr=seg[seg.DUID.isin(duids)&seg.offer_time.ge(SIGNAL)&seg.future_at_offer].head(1)
            if len(sr):
                text=segment_narrative(sr.iloc[0]);body+='<p>'+e(text)+'</p>';md += [text,'']
            else:body+='<p>No future-period post-signal band/parameter change is retained for this plant; consult its coverage status before interpreting absence.</p>'
        body+='<div class="fourpart"><p><b>Willingness:</b> inspect exact price-band changes above and in the explorer.</p><p><b>Readiness:</b> offered availability, declared ramp and public start evidence; engineering capability and fuel constraints are not fully observed.</p><p><b>Instruction:</b> dispatch target, separately plotted from the offer and SCADA.</p><p><b>Output:</b> signed observed MW, with first increase and full-day coverage stated above.</p></div></details>'
    body+='</section><section id="portfolios"><h2>05 · Portfolio replacement, without inventing a hedge book</h2><p>Only confirmed corporate mappings are combined. Other participants retain their legal participant identity. Comparisons are within each region: existing gas/battery output is separate from additional output above its own reference. The projected comparison uses native half-hour endpoints. Missing members withhold the comparison.</p>'
    for (controller,region),g in port.groupby(['controller','region']):
        body+=f'<h3>{e(controller)} · {e(region)}</h3>'
        fig=go.Figure()
        for ref,gg in g.groupby('reference'):
            for col,label in [('shortfall_mw','Coal shortfall'),('incremental_mw','Additional gas/battery'),('matched_mw','Matched replacement')]:
                fig.add_scatter(x=gg.delivery,y=gg[col],name=f'{label} · {ref}',mode='lines' if ref=='immediate' else 'markers',visible=True if ref=='immediate' else 'legendonly')
        fig.update_yaxes(title='Physical power (MW)')
        body+=chart(fig,controller+' · same-time physical replacement','Immediate reference: six-observation median. Projected reference: frozen AEMO run '+str(fmeta['run'])+'. Curves are descriptive; no financial contracts inferred.')
        rows=[]
        for ref,gg in g.groupby('reference'):
            rows.append(dict(reference=ref,complete_points=int(gg.complete.sum()),peak_shortfall_mw=gg.shortfall_mw.max(),peak_incremental_mw=gg.incremental_mw.max(),peak_matched_mw=gg.matched_mw.max(),peak_residual_mw=gg.residual_mw.max()))
        body+=table(pd.DataFrame(rows))
        text=f'{controller} in {region}: immediate-reference peak matched replacement was {fmt(g.loc[g.reference.eq("immediate"),"matched_mw"].max())} MW. This is an observed physical alignment, not proof of a coordinated strategy or a financial hedge.'
        body+='<p>'+e(text)+'</p>';md+=['## '+controller+' · '+region,text,'']
    # Mandatory EA unit-by-unit overlay and declared capacity scenario.
    ea=panel[panel.DUID.isin(['MP1','MP2','TALWA1','TALWB1'])]
    fig=go.Figure()
    for duid,g in ea.groupby('DUID'):fig.add_scatter(x=g.delivery,y=g.actual_mw,name=duid,mode='lines')
    fig.update_yaxes(title='Observed power (MW)')
    body+='<h3>Mount Piper and Tallawarra: the physical sequence</h3>'+chart(fig,'Coal and gas output on the same clock','SCADA observation time, with native source timestamps retained. Zero output alone does not establish an outage reason.')
    paragraphs=ea_case(units,panel,seg,headers,forecast,port)
    for text in paragraphs:body+='<p>'+e(text)+'</p>';md+=[text,'']
    gaps=result('capacity_gaps');mpgap=gaps[gaps.DUID.isin(['MP1','MP2'])]
    gap_summary=mpgap.groupby('DUID').agg(registered_mw=('registered_mw','first'),minimum_offered_mw=('maxavail','min'),maximum_offered_mw=('maxavail','max'),maximum_declared_gap_mw=('declared_gap_mw','max')).reset_index()
    body+=table(gap_summary)+'<p>The table compares registered capacity with offered maximum availability. It is a declared-capacity-gap scenario, not proof of technically unavailable capacity. A unit already at zero in the frozen forecast has no new forecast shortfall merely because its registered capacity is large. Tallawarra’s total output can cover some of this scenario while its incremental response is assessed separately.</p></section>'
    ea_gap=mpgap.groupby('delivery').declared_gap_mw.sum(min_count=2)
    ea_gas=ea[ea.DUID.isin(['TALWA1','TALWB1'])].groupby('delivery').actual_mw.sum(min_count=2)
    ea_cover=pd.concat([ea_gap.rename('declared_coal_gap_mw'),ea_gas.rename('total_tallawarra_mw')],axis=1)
    ea_cover['scenario_cover_mw']=np.minimum(ea_cover.declared_coal_gap_mw,ea_cover.total_tallawarra_mw.clip(lower=0))
    ea_cover['scenario_residual_mw']=ea_cover.declared_coal_gap_mw-ea_cover.scenario_cover_mw
    ea_cover.reset_index().to_csv(downloads/'mount_piper_tallawarra_existing_cover_scenario.csv',index=False)
    fig=go.Figure()
    for col,label in [('declared_coal_gap_mw','Declared coal capacity gap'),('total_tallawarra_mw','Total Tallawarra output'),('scenario_cover_mw','Simultaneous scenario cover')]:fig.add_scatter(x=ea_cover.index,y=ea_cover[col],name=label,mode='lines')
    fig.update_yaxes(title='Power (MW)')
    body+=chart(fig,'Existing cover scenario · Mount Piper and Tallawarra','Registered coal capacity minus offered availability is a declared gap, not verified technical lost output. Total Tallawarra output is shown separately from the incremental replacement curves.')
    body+='<h3>Ownership and control register</h3>'+table(inv[['plant','controller','owner','control_source']].drop_duplicates())
    body+='<section id="methods"><h2>06 · Methods, coverage and limits</h2>'
    limitations=[
      'The 9 October registration workbook was identified but the website blocked the download. Inventory uses retained July GENUNITS/DUALLOC/DUDETAIL and September-effective DUDETAILSUMMARY, checked against event accepted participants. New or unmapped assets/control changes remain a coverage limitation.',
      f"SCADA: {audit['complete_scada_units']} DUIDs have all 288 observations; {audit['partial_scada_units']} have partial coverage; {audit['unobserved_units']} have no observed SCADA. No missing observations are replaced with zero.",
      'Offer clocks, participant-supplied reason clocks, database processing and public report generation are separate. Publication/receipt is not proven; 07:15:13 is the information proxy and 07:20 is the sensitivity boundary.',
      'All ten native bands are preserved. Dollar thresholds are nominal offer prices; local loss factors mean a unit’s upper bid price can differ from the regional market cap. The explorer displays actual prices, not assumed common band values.',
      'SCADA is instantaneous start-of-interval power. Report timestamps shift it back five minutes from AEMO’s native interval-end identifier. Block means are means of observed MW samples, not energy totals.',
      'Reference output is the median of six complete observations ending 06:45–07:10. A 5 MW change is used to identify output responses; exact smaller bid changes remain in the ledger.',
      f"Later-period reference: AEMO predispatch run {fmeta['run']}, processed by {fmeta['processing_proxy']}. This is a projected dispatch path, not a participant’s internal plan; no interpolation between native half-hour endpoints.",
      'FCAS is excluded. Fuel supply, true engineering limits, bilateral contracts and customer exposure are not observable here. No dispatch simulation or causal effect estimate is provided.',
      'A post-spike offer shift is supported as an observation; contingency readiness or portfolio protection is plausible only where timing and operating evidence align. Explicit reason text may strengthen an inference but remains participant-supplied.',
      'Regional stacks cover selected coal, gas and battery units only. They omit other generation technologies and are not simulated clearing curves.'
    ]
    body+='<ul>'+''.join('<li>'+e(x)+'</li>' for x in limitations)+'</ul>'
    body+=table(units.groupby(['region','technology']).agg(units=('DUID','size'),complete_scada=('scada_intervals',lambda s:int(s.eq(288).sum())),post_signal_revisions=('post_signal_revisions','sum')).reset_index())+'</section>'
    md+=['## Methods and limitations','']+['- '+x for x in limitations]+['']
    body+='<section id="evidence"><h2>07 · Evidence and reproduction</h2><p>The HTML embeds the explorer and chart runtime. Downloads ship in the adjacent downloads folder. Rebuild presentation from cached evidence with <code>python rebid_mistress/run.py --stage report</code>.</p><ul>'
    for p in sorted(downloads.iterdir()):body+=f'<li><a href="downloads/{e(p.name)}" download>{e(p.name)}</a></li>'
    body+='</ul><h3>Primary sources</h3><ul>'
    for title,url in [('AEMO full accepted offers',json.loads((RAW/'offers.zip.json').read_text())['url']),('AEMO dispatch-effective offers',json.loads((RAW/'bidmove.zip.json').read_text())['url']),('AEMO full original-vintage predispatch',json.loads((RAW/'predispatch.zip.json').read_text())['url']),('AEMO dispatch SCADA definition','https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_123.htm'),('EnergyAustralia generation portfolio','https://www.energyaustralia.com.au/about-us/what-we-do/generating-energy'),('Origin generation portfolio','https://www.originenergy.com.au/about/who-we-are/what-we-do/generation/'),('AGL operations','https://www.agl.com.au/about-agl/operations')]:body+=f'<li><a href="{e(url,quote=True)}">{e(title)}</a></li>'
    body+='</ul></section>'
    # Preserve readable chart dimensions in independently scrollable phone panels.
    for chart_id in ['stackplot','unitplot','heatplot']:
        body=body.replace(f'<div id="{chart_id}" class="interactive-chart"></div>',f'<div class="chart-scroll"><div id="{chart_id}" class="interactive-chart plotly-graph-div"></div></div>')
    # Compact positional data reduces the embedded payload substantially.
    r=rev.merge(units[['DUID','plant','technology','region','controller']],on='DUID');r['blocks']=r.offer_id.map(seg.groupby('offer_id').block.agg(lambda s:','.join(sorted(set(s))))).fillna('')
    for c in ['REBID_EVENT_TIME','REBID_AWARE_TIME','REBID_DECISION_TIME','REBID_CATEGORY','REFERENCE_ID']:
        r[c]=r.offer_id.map(headers[c])
    segment_columns=['offer_id','DUID','direction','offer_time','delivery_from','delivery_to','block','future_at_offer','before_bands','after_bands','before_prices','after_prices','before_maxavail','after_maxavail','before_rampup','after_rampup','minimum_redistribution_mw','added_offered_mw','removed_offered_mw']
    payload=dict(revisions=clean(r),segment_columns=segment_columns,panel=clean(panel[['DUID','delivery','actual_mw','target_mw','baseline_mw','initial_soc_pct','soc_quality']]),effective=clean(eff[['DUID','direction','delivery','maxavail','le300']]),forecast=clean(forecast[['DUID','delivery','forecast_mw']]),snapshots=clean(snap[['DUID','direction','snapshot','delivery','le_300']]))
    # Positional segment arrays avoid repeating dozens of field names 450,000 times.
    import io
    out=io.BytesIO()
    with gzip.GzipFile(fileobj=out,mode='wb') as packed_file:
        packed_file.write(json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('utf-8')[:-1])
        packed_file.write(b',"segments":')
        packed_file.write(seg[segment_columns].to_json(orient='values',date_format='iso',double_precision=4).encode('utf-8'))
        packed_file.write(b'}')
    packed=base64.b64encode(out.getvalue()).decode()
    body+='<script id="embedded-data" type="application/octet-stream">'+packed+'</script><script>'+ (ROOT/'explorer.js').read_text(encoding='utf-8')+'</script>'
    body+='<style>'+ (ROOT/'report_extra.css').read_text()+'</style>'
    html=render_page('Rebid Mistress | 10 October 2026',body,accent='blue')
    (REPORTS/'index.html').write_text(html,encoding='utf-8');(REPORTS/'REPORT.md').write_text('\n'.join(md),encoding='utf-8')
    write_json(STATE/'report_manifest.json',dict(html_sha256=sha(REPORTS/'index.html'),markdown_sha256=sha(REPORTS/'REPORT.md'),built_utc=datetime.now(timezone.utc).isoformat(),input_hashes={p.name:sha(p) for p in RESULTS.glob('*.parquet')},downloads={p.name:sha(p) for p in downloads.iterdir()},plant_accounts=units.plant.nunique(),embedded_revisions=len(r),embedded_segments=len(seg)))
    print('Report',REPORTS/'index.html',len(html),'characters',flush=True)
