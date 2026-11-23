"""Curated, reproducible portfolio highlights from cached native event evidence.

Selections are editorial case-study choices, not a new ranking or causal model.
Corporate/contract links expand the reading guide, not the replacement pools.
"""
from html import escape
import numpy as np
import pandas as pd
from .core import SIGNAL, SPIKE, write_json

FAMILIES = {
    'AGL': ('AGL', ['AGLLBESS', 'AGLWBESS']),
    'EnergyAustralia': ('EnergyAustralia', ['BALBESS', 'GANNBESS']),
    'Origin': ('Origin', ['OEBESS', 'SNODE1']),
    'Alinta': ('', ['NEWGEN', 'ALNTARES', 'EDISON']),
    'Delta': ('', ['DELTA']),
    'CleanCo': ('CleanCo', []),
    'Stanwell': ('Stanwell', []),
    'Snowy': ('Snowy Hydro', []),
    'CS Energy': ('CS Energy', []),
    'Callide Trading': ('', ['CAPTPL']),
}
SELECTIONS = {
    'AGL': [('O021099', None), ('O011285', 'overnight')],
    'EnergyAustralia': [('O024405', None), ('O024419', 'evening')],
    'Origin': [('O021221', None), ('O012458', 'evening'), ('O005293', 'overnight')],
    'Alinta': [('O011779', 'overnight'), ('O011477', 'evening')],
    'Delta': [('O025588', None), ('O025590', 'evening')],
    'CleanCo': [('O021163', 'overnight')],
    'Stanwell': [('O007457', 'evening'), ('O025560', 'evening')],
    'Snowy': [('O024444', None), ('O008402', 'overnight')],
    'CS Energy': [('O010877', None), ('O002467', 'overnight')],
    'Callide Trading': [('O007355', None), ('O009498', None), ('O007359', 'evening')],
}
SOURCES = {
    'AGL': [
        ('AGL operating assets', 'https://www.agl.com.au/about-agl/operations'),
        ('Liddell commissioning, 20 March 2026', 'https://www.agl.com.au/about-agl/news-centre/2026/march/agl-celebrates-commissioning-milestone-for-the-liddell-battery'),
        ('AGL FY2020: Wandoan operational dispatch rights', 'https://www.asx.com.au/asxpdf/20200813/pdf/44lg6jyrj1qf5t.pdf')],
    'EnergyAustralia': [('Generating portfolio', 'https://www.energyaustralia.com.au/about-us/what-we-do/generating-energy'), ('Ballarat and Gannawarra dispatch rights, December 2019', 'https://www.energyaustralia.com.au/sites/default/files/2019-12/Clean%20energy%20fact%20sheet_0.pdf')],
    'Origin': [('Generation portfolio', 'https://www.originenergy.com.au/about/who-we-are/what-we-do/generation/'), ('Mortlake battery completion, 3 September 2026', 'https://www.originenergy.com.au/about/investors-media/origin-marks-mortlake-big-battery-milestone/'), ('Supernode stage 1 tolling, 17 February 2026', 'https://www.quinbrook.com/news-insights/supernode-stage-1-commences-commercial-operations/'), ('Supernode stage 2 operations, 28 July 2026', 'https://www.quinbrook.com/news-insights/supernode-stage-2-completes-construction-and-commences-operations/')],
    'Alinta': [('Alinta generation assets', 'https://www.alintaenergy.com.au/about-us/power-generation'), ('Separate Loy Yang B operation and capacity agreement, FY2021', 'https://www.alintaenergy.com.au/content/dam/alinta/documents/sustainability-reports/Alinta%20Energy%20Sustainability%20Report%20FY21.pdf')],
    'Delta': [('AER: Delta legal identity, updated February 2025', 'https://www.aer.gov.au/industry/registers/authorisations/delta-power-energy-vales-point-pty-ltd-trading-delta-electricity-authorised-electricity-retailer')],
    'CleanCo': [('CleanCo portfolio', 'https://cleancoqueensland.com.au/our-portfolio/')],
    'Stanwell': [('Stanwell energy assets', 'https://www.stanwell.com/our-energy-assets')],
    'Snowy': [('Snowy generation portfolio', 'https://www.snowyhydro.com.au/our-energy/generation/')],
    'CS Energy': [('CS Energy thermal generation', 'https://www.csenergy.com.au/what-we-do/power-generation')],
    'Callide Trading': [('Callide Power Trading is the registered trader for Callide C', 'https://www.csenergy.com.au/news/cs-energy-committed-to-market-compliance')],
}

def members(inv, name):
    controller, participants = FAMILIES[name]
    return inv[inv.controller.eq(controller) | inv.PARTICIPANTID.isin(participants)].copy()

def select_segment(segments, offer_id, delivery_block=None):
    rows=segments[segments.offer_id.eq(offer_id) & segments.future_at_offer & segments.direction.eq('GEN') & segments.offer_time.ge(SIGNAL)].copy()
    if delivery_block: rows=rows[rows.block.eq(delivery_block)]
    if rows.empty: raise ValueError('Missing curated portfolio evidence: '+offer_id)
    rows['score']=(rows.after_le300-rows.before_le300).abs()+rows.minimum_redistribution_mw+(rows.after_maxavail-rows.before_maxavail).abs()
    return rows.sort_values(['score','delivery_from'],ascending=[False,True]).iloc[0]

def complete_sum(values, expected):
    return values.sum(min_count=expected) if len(values)==expected else np.nan

def render(inv, units, panel, segments, headers, downloads):
    u=units.set_index('DUID'); evidence=[]; membership=[]; observations=[]
    def n(x): return 'unavailable' if pd.isna(x) else f'{x:,.1f}'
    def unit(duid, col): return n(u.loc[duid,col])
    def total(ids, when=None):
        if when is None: return n(complete_sum(u.loc[ids,'baseline_mw'],len(ids)))
        g=panel[panel.DUID.isin(ids)&panel.delivery.eq(pd.Timestamp('2026-10-10 '+when))]
        return n(complete_sum(g.actual_mw,len(ids)))
    def peak(duid):
        g=panel[panel.DUID.eq(duid)&panel.delivery.ge(SPIKE)].dropna(subset=['actual_mw'])
        if g.empty:return 'unavailable'
        r=g.loc[g.actual_mw.idxmax()];return f'{n(r.actual_mw)} MW at {r.delivery:%d %b %H:%M}'
    headlines={
        'AGL':'Bayswater held high output; battery offers were repositioned later.',
        'EnergyAustralia':'Mount Piper cited VOLL; Tallawarra’s afternoon return was already projected.',
        'Origin':'Uranquinty supplied the immediate gas response; later battery and gas positioning differed.',
        'Alinta':'Braemar offered overnight flexibility but did not generate; Loy Yang B stayed steady.',
        'Delta':'Feed-pump limits governed VP5; VP6 initially lifted output through its existing offer.',
        'CleanCo':'Swanbank battery supplied the later physical response; overnight availability was reduced.',
        'Stanwell':'Coal output fell after the NSW spike, then recovered into the evening.',
        'Snowy':'Colongra started before its first post-signal energy rebid.',
        'CS Energy':'Gladstone rebids cited southbound QNI constraints; batteries later managed charge state.',
        'Callide Trading':'Callide C made operating and network adjustments, without an immediate rebid.',
    }
    physical={
        'AGL':f'Bayswater 2+4 supplied {total(["BW02","BW04"])} MW at the frozen reference and {total(["BW02","BW04"],"07:30")} MW at 07:30. Bayswater 1+3 and Somerton stayed at zero observed output. Liddell battery’s post-signal peak was {peak("LDBESS1")}; its 07:30 output was {unit("LDBESS1","actual_plus15_mw")} MW.',
        'EnergyAustralia':f'MP1 was {unit("MP1","actual_plus15_mw")} MW at 07:30 versus a {unit("MP1","baseline_mw")} MW reference. MP2 and Tallawarra B stayed at zero. Tallawarra A crossed 5 MW at 16:05 and reached {peak("TALWA1")}; its afternoon return already appeared in the frozen AEMO projection.',
        'Origin':f'Uranquinty 13+14 rose from a {total(["URANQ13","URANQ14"])} MW reference to {total(["URANQ13","URANQ14"],"07:30")} MW at 07:30 and {total(["URANQ13","URANQ14"],"08:15")} MW at 08:15. The frozen forecast had both at zero at 07:30 and 08:00. Eraring battery 1 was already discharging at a {unit("ERB01","baseline_mw")} MW reference and supplied {unit("ERB01","actual_plus15_mw")} MW at 07:30. Darling Downs later peaked at {peak("DDPS1")}.',
        'Alinta':f'Braemar A and Bairnsdale remained at zero observed output throughout the trading day. Loy Yang B’s two units supplied {total(["LOYYB1","LOYYB2"])} MW at the reference and {total(["LOYYB1","LOYYB2"],"07:30")} MW at 07:30. The Braemar offer change therefore represents willingness without realised generation.',
        'Delta':f'VP5 was {unit("VP5","actual_plus15_mw")} MW at 07:30 against a {unit("VP5","baseline_mw")} MW reference. VP6 rose from {unit("VP6","baseline_mw")} to {unit("VP6","actual_plus15_mw")} MW at 07:30; its first future-period post-signal revision was only at 09:16:21. VP6 was down to {unit("VP6","actual_plus60_mw")} MW by 08:15.',
        'CleanCo':f'Swanbank E stayed below 5 MW all day (maximum {unit("SWAN_E","max_mw")} MW). Swanbank battery was charging at {unit("SWANBBF1","actual_plus15_mw")} MW net at 07:30, then peaked at {peak("SWANBBF1")}. This was later battery discharge rather than an immediate gas ramp.',
        'Stanwell':f'The nine scheduled coal units totalled {total(["STAN-1","STAN-2","STAN-3","STAN-4","TARONG#1","TARONG#2","TARONG#3","TARONG#4","TNPS1"])} MW at the reference, {total(["STAN-1","STAN-2","STAN-3","STAN-4","TARONG#1","TARONG#2","TARONG#3","TARONG#4","TNPS1"],"08:15")} MW at 08:15 and {total(["STAN-1","STAN-2","STAN-3","STAN-4","TARONG#1","TARONG#2","TARONG#3","TARONG#4","TNPS1"],"18:00")} MW at 18:00. Tarong battery peaked at {peak("TARBESS1")}; Tarong 3 stayed at zero.',
        'Snowy':f'Colongra 1+3 crossed 5 MW at 07:30, supplying {total(["CG1","CG3"],"07:30")} MW combined, then {total(["CG1","CG3"],"08:15")} MW at 08:15. Their first post-signal rebids arrived at 07:39:42. The pre-signal forecast had both at zero at 07:30 and 08:00. Hunter, Laverton North and Valley Power remained at zero observed output.',
        'CS Energy':f'Gladstone 2–6 fell from {total(["GSTONE2","GSTONE3","GSTONE4","GSTONE5","GSTONE6"])} MW at the reference to {total(["GSTONE2","GSTONE3","GSTONE4","GSTONE5","GSTONE6"],"08:15")} MW at 08:15, then supplied {total(["GSTONE2","GSTONE3","GSTONE4","GSTONE5","GSTONE6"],"18:00")} MW at 18:00. Kogan Creek and Gladstone 1 stayed at zero. Chinchilla and Greenbank were charging at {unit("CHBESS1","actual_plus60_mw")} and {unit("GREENB1","actual_plus60_mw")} MW net at 08:15.',
        'Callide Trading':f'Callide C3+C4 rose from a {total(["CPP_3","CPP_4"])} MW reference to {total(["CPP_3","CPP_4"],"07:30")} MW at 07:30 without an intervening post-signal rebid. They supplied {total(["CPP_3","CPP_4"],"08:15")} MW at 08:15 and {total(["CPP_3","CPP_4"],"18:00")} MW at 18:00. First revisions were 08:15:28 and 08:16:28.',
    }
    implications={
        'AGL':'Supported: steady NSW coal output and later battery repositioning. This is not evidence that an immediate gas/battery ramp replaced the inactive Bayswater units. Liddell and Wandoan are included as separately registered battery links; NSW, QLD and VIC output is not pooled as equivalent protection.',
        'EnergyAustralia':'The direct VOLL explanation supports MP1’s bidding response. Tallawarra’s later physical cover is real, but its whole run cannot be attributed to the spike. MP1’s later evening reduction also prevents a blanket “all capacity moved cheaper to protect the peak” conclusion. Ballarat and Gannawarra dispatch-rights assets are included in the membership export.',
        'Origin':'The observed NSW response was gas starting, not a uniform increase across every coal and battery unit. The overnight Darling Downs example raises declared availability while reducing raw low-priced volume: readiness and willingness can move in opposite directions. Eraring/Mortlake batteries and Origin-contracted Supernode stages are linked explicitly; QLD gas and storage are not counted as automatic NSW cover.',
        'Alinta':'Supported: overnight gas offer repositioning without output. Loy Yang B is shown as a commercially related asset, with its own registered participant EDISON. Alinta disclosures describe separate management and a capacity agreement, so these observations are not a verified common-control coal/gas replacement pool.',
        'Delta':'Operational limits and unchanged-offer generation are the stronger explanations. The identified in-scope Delta fleet contains no gas/battery replacement pool; a Vales Point output change cannot establish an internal cross-technology hedge.',
        'CleanCo':'The observed sequence supports storage-state management and later discharge. The 10:53 overnight availability withdrawal does not support claiming additional overnight contingency cover at that revision. Hydro is excluded from this study, so this is only the gas/battery portion of CleanCo’s portfolio.',
        'Stanwell':'This QLD fleet did not simply chase the NSW price cap. Later coal repositioning and battery SOC management must be read against QLD conditions. Coal recovery and battery discharge can coexist without proving that battery MW were scheduled to replace a particular unavailable coal unit.',
        'Snowy':'The immediate gas response used offers already in place; later rebidding cited a hydro-dispatch shortfall. The hydro unit appears only in the verbatim reason and is not analysed or included in replacement MW. This is Snowy’s in-scope gas fleet, not its whole hydro-backed portfolio.',
        'CS Energy':'The early coal response is consistent with the stated QNI constraint, rather than a uniform ramp towards NSW VOLL. Battery charging then later SOC changes require separate interpretation. Callide C belongs to the separate Callide Trading account below and is not double-counted here.',
        'Callide Trading':'Supported: a small initial output rise through existing offers, followed by valve-stroking and network-management changes. No gas or battery is assigned to CAPTPL in this study. CS Energy’s ownership/operating link does not merge Callide C into its separate trading account.',
    }
    intro=('Ten condensed accounts, separating the selected rebids, physical output and portfolio implication. '
           'All clocks are fixed NEM time. These are curated material examples, not an exhaustive rebid list. '
           'The 07:30 observation is the last five-minute point within 15 minutes of the signal. '
           'Raw band MW can exceed declared availability; a dated revision is not assumed to persist all day. '
           'Linked assets extend this reading guide; the replacement calculations later in the report retain their explicitly listed control pools.')
    html='<section id="portfolio-highlights"><h2>Portfolio highlights · ten accounts</h2><p>'+escape(intro)+'</p><nav class="digest-nav">'
    for name in FAMILIES:html+=f'<a href="#digest-{name.lower().replace(" ","-")}">{escape(name)}</a>'
    html+='</nav><div class="portfolio-digest">'
    md=['## Condensed portfolio highlights','',intro,'']
    for name in FAMILIES:
        group=members(inv,name);ids=set(group.DUID)
        if not ids:raise ValueError('Empty requested portfolio: '+name)
        group=group.assign(digest_portfolio=name)
        membership.append(group[['digest_portfolio','DUID','plant','technology','REGIONID','PARTICIPANTID','controller']])
        observations.append(panel[panel.DUID.isin(ids)].assign(digest_portfolio=name))
        slug=name.lower().replace(' ','-')
        html+=f'<article class="digest-card" id="digest-{slug}"><h3>{escape(name)}</h3><p class="digest-headline">{escape(headlines[name])}</p>'
        md+=['### '+name,'',headlines[name],'']
        for offer_id,delivery_block in SELECTIONS[name]:
            r=select_segment(segments,offer_id,delivery_block)
            if r.DUID not in ids:raise ValueError('Selected offer outside portfolio: '+offer_id)
            before=np.asarray(r.before_bands);after=np.asarray(r.after_bands);delta=after-before
            down=[f'{abs(v):g} MW at ${r.before_prices[i]:,.2f}' for i,v in enumerate(delta) if v<-.001]
            up=[f'{v:g} MW at ${r.after_prices[i]:,.2f}' for i,v in enumerate(delta) if v>.001]
            actions=[]
            if down:actions.append('removed '+', '.join(down))
            if up:actions.append('added '+', '.join(up))
            if not actions:actions.append('left band volumes unchanged')
            text=f'{r.offer_time:%H:%M:%S} · {r.DUID}, delivery {r.delivery_from:%d %b %H:%M}–{r.delivery_to:%d %b %H:%M}: '+ '; '.join(actions)+f' ($/MWh). Raw MW ≤$300: {r.before_le300:g} → {r.after_le300:g}; availability: {r.before_maxavail:g} → {r.after_maxavail:g} MW.'
            rr=str(r.reason) if pd.notna(r.reason) and str(r.reason).strip() else '[missing reason]'
            html+=f'<p class="digest-rebid"><b>Key rebid.</b> {escape(text)} <b>Reason:</b> “{escape(rr)}” <a href="#explorer" data-offer="{escape(offer_id)}">{escape(offer_id)}</a></p>'
            md+=['**Key rebid.** '+text+' Reason: “'+rr+'” (`'+offer_id+'`).','']
            evidence.append(dict(portfolio=name,offer_id=offer_id,DUID=r.DUID,offer_time=r.offer_time,delivery_from=r.delivery_from,delivery_to=r.delivery_to,reason=rr,narrative=text,before_le300=r.before_le300,after_le300=r.after_le300,before_maxavail=r.before_maxavail,after_maxavail=r.after_maxavail))
        for label,text in [('Physical highlight',physical[name]),('Portfolio implication',implications[name])]:
            html+=f'<p><b>{label}.</b> {escape(text)}</p>';md+=['**'+label+'.** '+text,'']
        plant_links=[]
        for plant,gg in group.groupby('plant'):
            # Every-plant anchors use the first DUID in units' existing ordering.
            anchor=units[units.plant.eq(plant)].iloc[0].DUID
            plant_links.append(f'<a href="#plant-{escape(anchor)}">{escape(plant)}</a>')
        html+='<details><summary>Assets and portfolio sources</summary><p>'+', '.join(plant_links)+'</p><ul>'
        for title,url in SOURCES[name]:html+=f'<li><a href="{escape(url,quote=True)}">{escape(title)}</a></li>';md+=['- ['+title+']('+url+')']
        html+='</ul><p>Company sources establish the stated asset relationship, not historical receipt of a signal or a private hedge volume. Public contract terms do not establish every operational restriction.</p></details></article>'
        md+=['']
    html+='</div><p class="note">Trace the summaries through the offer links, every-plant accounts and downloads: portfolio_digest_rebids.csv, portfolio_digest_members.csv and portfolio_digest_observations.parquet. Observations are instantaneous MW, not energy sums.</p></section>'
    pd.DataFrame(evidence).to_csv(downloads/'portfolio_digest_rebids.csv',index=False)
    pd.concat(membership).to_csv(downloads/'portfolio_digest_members.csv',index=False)
    pd.concat(observations).to_parquet(downloads/'portfolio_digest_observations.parquet',index=False)
    write_json(downloads/'portfolio_digest_sources.json',SOURCES)
    return html,md
