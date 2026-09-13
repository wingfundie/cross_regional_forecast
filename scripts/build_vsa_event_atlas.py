"""Build an offline interactive event atlas from retained evidence only."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from html import escape
import numpy as np
import pandas as pd
import plotly.express as px

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts/report_theme'))
from nemic.event_atlas import settings, save, log, digest, DEFAULT, VERSION, coal_duids
from nemic.common import DATA, PROCESSED, dump
from report_theme import hero,metric,finding,figure_html,style_plotly,render_page

CONFIG = ROOT / 'configs/event_vsa_2y.json'


def table(f):
    return '<div class="table-wrap" tabindex="0">'+f.to_html(index=False,border=0,escape=True,float_format=lambda x:f'{x:,.2f}')+'</div>'


def records(f):
    return json.loads(f.to_json(orient='records',date_format='iso'))


def chart(fig,title,note='',height=480):
    style_plotly(fig,title,height)
    return figure_html(fig.to_html(full_html=False,include_plotlyjs=False),title,note)


def context(c,dispatch):
    details=pd.read_parquet(c['standing']/'DUDETAILSUMMARY.parquet')
    # Explicit station subset, not an exhaustive historical registered-capacity reconstruction.
    duids=coal_duids(c)
    units=details[details.DUID.isin(duids)&details.DISPATCHTYPE.eq('GENERATOR')][['DUID','STATIONID','REGIONID']].drop_duplicates()
    f=dispatch.merge(units,on='DUID',how='inner')
    f['online_proxy']=f.INITIALMW.gt(5)&f.INITIALMW.notna()
    f['not_generating_proxy']=f.INITIALMW.le(5)&f.INITIALMW.notna()
    f['unknown']=f.INITIALMW.isna()
    rp=c['root']/'coal_registration.parquet'
    if rp.exists():
        registration=pd.read_parquet(rp)
        registration['EFFECTIVEDATE']=pd.to_datetime(registration.EFFECTIVEDATE)
        registration['AUTHORISEDDATE']=pd.to_datetime(registration.AUTHORISEDDATE,errors='coerce')
        registration['VERSIONNO']=pd.to_numeric(registration.VERSIONNO)
        registration['REGISTEREDCAPACITY']=pd.to_numeric(registration.REGISTEREDCAPACITY,errors='coerce')
        registration=registration[registration.AUTHORISEDDATE.notna()].sort_values(['DUID','EFFECTIVEDATE','VERSIONNO']).drop_duplicates(['DUID','EFFECTIVEDATE'],keep='last')
        f=pd.merge_asof(f.sort_values('time'),registration[['DUID','EFFECTIVEDATE','AUTHORISEDDATE','REGISTEREDCAPACITY']].sort_values('EFFECTIVEDATE'),
                       left_on='time',right_on='EFFECTIVEDATE',by='DUID',direction='backward')
        f.loc[f.AUTHORISEDDATE.gt(f.time),'REGISTEREDCAPACITY']=np.nan
    else:f['REGISTEREDCAPACITY']=np.nan
    f['online_registered_mw_proxy']=f.REGISTEREDCAPACITY.where(f.online_proxy,0)
    f['not_generating_registered_mw_proxy']=f.REGISTEREDCAPACITY.where(f.not_generating_proxy,0)
    agg=f.groupby(['time','REGIONID'],as_index=False).agg(coal_target_mw=('TOTALCLEARED','sum'),coal_initial_mw=('INITIALMW','sum'),
        coal_available_mw=('AVAILABILITY','sum'),online_units_proxy=('online_proxy','sum'),
        not_generating_units_proxy=('not_generating_proxy','sum'),unknown_units=('unknown','sum'),observed_units=('DUID','nunique'))
    capacity=f.groupby(['time','REGIONID'],as_index=False).agg(online_registered_mw_proxy=('online_registered_mw_proxy',lambda x:x.sum(min_count=1)),
        not_generating_registered_mw_proxy=('not_generating_registered_mw_proxy',lambda x:x.sum(min_count=1)),
        capacity_covered_units=('REGISTEREDCAPACITY','count'))
    agg=agg.merge(capacity,on=['time','REGIONID'])
    missing_capacity=agg.capacity_covered_units.lt(agg.observed_units)
    agg.loc[missing_capacity,['online_registered_mw_proxy','not_generating_registered_mw_proxy']]=np.nan
    agg['expected_units']=agg.REGIONID.map(units.groupby('REGIONID').DUID.nunique())
    agg['missing_units']=agg.expected_units-agg.observed_units
    agg['not_generating_is_not_verified_outage']=True
    save(agg,c['root']/'coal_context.parquet');units.to_csv(c['root']/'coal_unit_scope.csv',index=False)
    weatherpath=PROCESSED/'weather_hourly.parquet'
    w=pd.read_parquet(weatherpath).reset_index()
    w=w[['time','VIC_Melbourne__temperature_2m','SA_Adelaide__temperature_2m']]
    w=w[w.time.between(pd.Timestamp(c['start'])-pd.Timedelta(hours=2),pd.Timestamp(c['end'])+pd.Timedelta(hours=2))]
    save(w,c['root']/'weather_context.parquet')
    log(c,{'kind':'weather_reuse','path':str(weatherpath.relative_to(ROOT)),'sha256':digest(weatherpath),
        'product':'Open-Meteo ERA5 reanalysis; hourly; retrospective, not station measurements or forecast vintages',
        'original_manifest':'data/weather_manifest.json'})
    roof_parts=[]
    for p in sorted((DATA/'tables/ROOFTOP_PV_ACTUAL').glob('*.parquet')):
        z=pd.read_parquet(p);z['time']=pd.to_datetime(z.INTERVAL_DATETIME)
        z=z[z.REGIONID.isin(c['regions'])&z.time.between(pd.Timestamp(c['start'])-pd.Timedelta(hours=2),pd.Timestamp(c['end'])+pd.Timedelta(hours=2))]
        if len(z):
            roof_parts.append(z)
            log(c,{'kind':'rooftop_reuse','path':str(p),'sha256':digest(p),'retained_rows':len(z),'cadence':'native source timestamps, typically half-hourly'})
    roof=pd.concat(roof_parts,ignore_index=True)
    roof['LASTCHANGED']=pd.to_datetime(roof.LASTCHANGED)
    roof['POWER']=pd.to_numeric(roof.POWER,errors='coerce');roof['QI']=pd.to_numeric(roof.QI,errors='coerce')
    roof=roof.sort_values('LASTCHANGED').drop_duplicates(['time','REGIONID','TYPE'],keep='last')
    roof['prefer_measurement']=roof.TYPE.eq('MEASUREMENT')
    roof=roof.sort_values(['time','REGIONID','QI','prefer_measurement']).drop_duplicates(['time','REGIONID'],keep='last')
    save(roof,c['root']/'rooftop_context.parquet')
    return agg,w,roof


def report(c):
    root=c['root'];out=ROOT/'docs/html/vsa_event_atlas.html';dd=ROOT/'docs/data';dd.mkdir(exist_ok=True)
    e=pd.read_parquet(root/'event_catalogue.parquet');ic=pd.read_parquet(root/'screen_timeseries.parquet').set_index('time')
    price=pd.read_parquet(root/'prices_5min.parquet');pe=pd.read_parquet(root/'price_event_catalogue.parquet')
    a=pd.read_parquet(root/'event_attribution.parquet');steps=pd.read_parquet(root/'attribution_steps.parquet')
    g=pd.read_parquet(root/'generator_contributions.parquet');eq=pd.read_parquet(root/'event_equations.parquet')
    states=pd.read_parquet(root/'constraint_states.parquet');dispatch=pd.read_parquet(root/'unit_dispatch.parquet')
    matched=pd.read_parquet(root/'matched_population.parquet');quality=json.loads((root/'screen_quality.json').read_text())
    recquality=json.loads((root/'reconstruction_quality.json').read_text())
    coal,weather,roof=context(c,dispatch)
    if set(e.loc[e.selected,'event_id'])!=set(a.event_id):
        raise RuntimeError('Report requires completed reconstruction of every selected contraction case')
    e=e.merge(a,on='event_id',how='left')
    e['physical_intervention']=e.time.map(lambda t:pd.to_numeric(ic.loc[t-pd.Timedelta(hours=2):t+pd.Timedelta(hours=2),'INTERVENTION'],errors='coerce').gt(0).any())
    e['mpc_in_preceding_hour']=False
    for direction,receiver in [('upper',c['regions'][1]),('lower',c['regions'][0])]:
        pre=ic[f'{receiver}_mpc_hit'].fillna(False).astype(int).rolling(12,min_periods=1).max().shift(1).fillna(0).astype(bool)
        mask=e.direction.eq(direction)
        e.loc[mask,'mpc_in_preceding_hour']=e.loc[mask,'time'].map(pre)
    # Output population and compact event evidence; raw archives never enter docs.
    e.to_csv(dd/'vsa_event_catalogue.csv',index=False)
    a.to_csv(dd/'vsa_event_attribution.csv',index=False)
    eq.to_csv(dd/'vsa_event_equations.csv',index=False)
    g.to_csv(dd/'vsa_event_generator_steps.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    coal.to_csv(dd/'vsa_event_coal_context.csv',index=False)
    pe.to_csv(dd/'vsa_price_events.csv',index=False)
    pd.read_csv(root/'thresholds.csv').to_csv(dd/'vsa_event_thresholds.csv',index=False)
    ranked=g.groupby(['event_id','DUID'],as_index=False).agg(net_tightening_mw=('tightening_mw','sum'),
        gross_tightening_mw=('tightening_mw',lambda x:x.clip(lower=0).sum()),gross_relief_mw=('tightening_mw',lambda x:-x.clip(upper=0).sum()))
    ranked.to_csv(dd/'vsa_event_generator_contributions.csv',index=False)
    unique=g.drop_duplicates(['time','DUID','constraint','version_key'])
    grand=unique.groupby('DUID',as_index=False).agg(net_mw=('tightening_mw','sum'),
        tightening_mw=('tightening_mw',lambda x:x.clip(lower=0).sum()),
        relief_mw=('tightening_mw',lambda x:-x.clip(upper=0).sum())).sort_values('tightening_mw',ascending=False)
    grand['events']=grand.DUID.map(ranked.groupby('DUID').event_id.nunique())
    grand.to_csv(dd/'vsa_event_generator_summary.csv',index=False)
    e['season_year']=e.time.dt.year+e.time.dt.month.eq(12).astype(int)
    seasonal=e.groupby(['season_year','season','direction'],as_index=False).agg(events=('event_id','size'),median_drop_mw=('drop_mw','median'),
        near_mpc_events=('near_mpc_intervals',lambda x:x.gt(0).sum()),mpc_events=('mpc_intervals',lambda x:x.gt(0).sum()))
    valid=ic.loc[c['start']:c['end']].copy();valid['season_year']=valid.index.year+(valid.index.month==12).astype(int)
    valid['season']=[['Summer','Autumn','Winter','Spring'][(t.month%12)//3] for t in valid.index]
    exposure=valid.groupby(['season_year','season']).flow.count()/12
    seasonal['valid_hours']=[exposure.loc[(r.season_year,r.season)] for r in seasonal.itertuples()]
    seasonal['events_per_1000h']=1000*seasonal.events/seasonal.valid_hours
    seasonal['season_label']=seasonal.season_year.astype(int).astype(str)+' '+seasonal.season
    seasonal.to_csv(dd/'vsa_event_seasonal.csv',index=False)
    # Paired observational contrasts; block bootstrap by event day to respect shared incidents.
    matched['difference']=matched.event_price_jump-matched.control_price_jump
    day=matched.groupby(pd.to_datetime(matched.time).dt.date).difference.agg(['sum','count'])
    rng=np.random.default_rng(741);boot=[]
    for _ in range(1000):
        z=day.iloc[rng.integers(0,len(day),len(day))];boot.append(z['sum'].sum()/z['count'].sum())
    ci=np.quantile(boot,[.025,.975]);mean=matched.difference.mean()
    matched.to_csv(dd/'vsa_event_matched_controls.csv',index=False)
    balance=matched[[x for x in matched if x.startswith('balance_')]].mean().rename('mean_standardized_difference').reset_index()
    balance['mean_absolute_pair_difference']=matched[[x for x in matched if x.startswith('balance_')]].abs().mean().to_numpy()
    balance.to_csv(dd/'vsa_event_match_balance.csv',index=False)
    # Preserve discrepancy from the legacy detector, which reset 30-min lags each month.
    old=pd.read_csv(dd/'vsa_2y_contraction_events.csv');old['time']=pd.to_datetime(old.time)
    delta=e[['time','direction']].merge(old[['time','direction']],on=['time','direction'],how='outer',indicator=True)
    delta[delta._merge.ne('both')].to_csv(dd/'vsa_event_detector_changes.csv',index=False)
    notes={}
    dump(root/'external_event_evidence.json',notes)
    bundles=[]
    cases=records(e[e.selected].sort_values(['mpc_intervals','drop_mw'],ascending=False))
    for p in pe[pe.linked_events.eq(0)].itertuples():
        cases.append(dict(event_id=f'PRICE-{p.region}-{p.time:%Y%m%dT%H%M}',time=p.time.isoformat(),direction='price-only',
                          receiver=p.region,drop_mw=None,selection_reason='Price episode with no contraction detection within one hour'))
    for ev in cases:
        t=pd.Timestamp(ev['time']);event_id=ev['event_id'];lo=t-pd.Timedelta(hours=2);hi=t+pd.Timedelta(hours=2)
        series=ic.loc[lo:hi].reset_index()
        cols=['time','flow','export','import']+[f'{r}_{v}' for r in c['regions'] for v in ['RRP','mpc','TOTALDEMAND','SS_WIND_CLEAREDMW','SS_SOLAR_CLEAREDMW','AVAILABLEGENERATION']]
        rg=ranked[ranked.event_id.eq(event_id)].sort_values('gross_tightening_mw',ascending=False)
        top=list(rg.head(5).DUID)+list(rg.nlargest(3,'gross_relief_mw').DUID)
        top=list(dict.fromkeys(top))
        if not top:
            # Price-only cases retain measured/target dispatch context but no fabricated attribution.
            local=dispatch[dispatch.time.between(lo,hi)]
            top=local.groupby('DUID').TOTALCLEARED.agg(lambda x:x.max()-x.min()).nlargest(5).index.tolist()
        units=dispatch[dispatch.time.between(lo,hi)&dispatch.DUID.isin(top)]
        st=states[states.time.between(lo,hi)]
        setters=set(series.EXPORTGENCONID.dropna())|set(series.IMPORTGENCONID.dropna())
        popular=st[st.binding].groupby('CONSTRAINTID').size().nlargest(10).index
        keep=set(popular)|setters
        st=st[st.CONSTRAINTID.isin(keep)]
        sets=pd.read_parquet(c['standing']/'GENCONSET.parquet')
        sets['EFFECTIVEDATE']=pd.to_datetime(sets.EFFECTIVEDATE)
        sets['VERSIONNO']=pd.to_numeric(sets.VERSIONNO)
        eligible=sets[sets.EFFECTIVEDATE.le(t)]
        skeys=eligible[['GENCONSETID','EFFECTIVEDATE','VERSIONNO']].drop_duplicates().sort_values(['GENCONSETID','EFFECTIVEDATE','VERSIONNO']).groupby('GENCONSETID').tail(1)
        sets=eligible.merge(skeys,on=['GENCONSETID','EFFECTIVEDATE','VERSIONNO'],how='inner')
        inv=pd.read_parquet(c['standing']/'GENCONSETINVOKE.parquet')
        sets=sets[sets.GENCONID.isin(keep)][['GENCONSETID','GENCONID','EFFECTIVEDATE','VERSIONNO']].drop_duplicates()
        inv['start']=pd.to_datetime(inv.STARTINTERVALDATETIME,errors='coerce');inv['end']=pd.to_datetime(inv.ENDINTERVALDATETIME,errors='coerce')
        inv=inv[inv.GENCONSETID.isin(sets.GENCONSETID)&inv.start.le(hi)&(inv.end.isna()|inv.end.ge(lo))]
        conditions=[]
        for region in c['regions']:
            for field,label in [('TOTALDEMAND','Operational demand'),('SS_WIND_CLEAREDMW','Wind dispatch'),('SS_SOLAR_CLEAREDMW','Utility solar dispatch'),('AVAILABLEGENERATION','Declared available generation')]:
                col=f'{region}_{field}';before=series[(series.time<t)&(series.time>=t-pd.Timedelta(hours=1))][col]
                after=series[(series.time>=t)&(series.time<=t+pd.Timedelta(hours=1))][col]
                reference=ic.loc[(ic.index.month==t.month)&(ic.index.hour==t.hour),col].dropna()
                at=float(ic.at[t,col]) if pd.notna(ic.at[t,col]) else None
                conditions.append({'region':region,'condition':label,'unit':'MW','pre_hour_median':before.median(),
                    'at_detection':at,'next_hour_min':after.min(),'next_hour_max':after.max(),
                    'month_hour_percentile':100*reference.le(at).mean() if at is not None and len(reference) else None,
                    'reference':'same calendar month/hour, both study years; retrospective'})
        bundles.append({'event':ev,'series':records(series[cols]),'units':records(units[['time','DUID','TOTALCLEARED','INITIALMW','AVAILABILITY']]),
            'constraints':records(st[['time','CONSTRAINTID','RHS','LHS','MARGINALVALUE','binding','ic_slack_mw','bound','direction','version_key']]),
            'rankings':records(rg),'equations':records(eq[eq.event_id.eq(event_id)]),
            'sets':records(sets),'invocations':records(inv[['GENCONSETID','start','end','SYSTEMNORMAL']]),
            'coal':records(coal[coal.time.between(lo,hi)]),'weather':records(weather[weather.time.between(lo,hi)]),
            'rooftop':records(roof[roof.time.between(lo,hi)][['time','REGIONID','POWER','TYPE','QI']]),
            'conditions':records(pd.DataFrame(conditions)),'external':notes.get(str(t.date()))})
    dump(root/'event_bundles.json',bundles)
    # Findings are calculated from source outputs, not static example values.
    within=price[price.time.between(pd.Timestamp(c['start']),pd.Timestamp(c['end']))]
    exact_count=int(within.mpc_hit.sum());n_mpc=int(e.mpc_intervals.gt(0).sum())
    summary={'period':[c['start'],c['end']],'events':len(e),'incidents':int(e.incident_id.nunique()),'selected':int(e.selected.sum()),
        'exact_mpc_region_intervals':exact_count,'contractions_with_receiving_region_mpc_next_hour':n_mpc,
        'near_mpc_price_episodes':len(pe),'price_only_cases':int(pe.linked_events.eq(0).sum()),
        'matched_events':len(matched),'matched_mean_peak_price_jump_difference':float(mean),'day_bootstrap_95ci':ci.tolist(),
        'top_selected_case_generator':str(grand.iloc[0].DUID) if len(grand) else None,
        'quality':quality,'reconstruction':recquality}
    dump(root/'summary.json',summary);dump(dd/'vsa_event_summary.json',summary)
    body=hero('VSA • EVENT ATLAS','When transfer limits contract','Equations, generators and prices',
        'Two years of five-minute event screening, with selected-window mechanical reconstruction and supporting market conditions.',
        ['September 2024–August 2026','VIC → SA positive','Fixed UTC+10 NEM time','Observational study'])
    body+='<nav><a href="#events">Event explorer</a> · <a href="#population">Population</a> · <a href="#generators">Generators</a> · <a href="#comparisons">Price comparisons</a> · <a href="#methods">Evidence & downloads</a></nav>'
    body+='<div class="metrics">'+metric('Contraction detections',f'{len(e):,}',f'{e.incident_id.nunique():,} grouped incidents')+metric('Detailed contraction cases',int(e.selected.sum()),'Plus price-only cases and matched control extracts')+metric('Exact MPC observations',exact_count,'Region × five-minute intervals; not all linked to VSA')+metric('Complete screening', '24 months','210,240 intervals per series')+'</div>'
    body+='<div class="callout">Generator movements are mechanical equation contributions, not proof of independent causation. Switches and unrepresented LHS movements remain separate. Prices are observed outcomes; no dispatch counterfactual or forecast model has been fitted.</div>'
    body+='<div class="findings">'+finding(1,'Start with the restriction',f'{int(e.selected.sum())} cases trace reported setters, binding equations, targets and the loss of headroom.')+finding(2,'Price shocks are not interchangeable',f'{n_mpc} contraction detections have receiving-region MPC observations in the following hour (which may continue an earlier price shock); {int(pe.linked_events.eq(0).sum())} near-MPC episodes have no contraction detection within ±1 hour.')+finding(3,'Context comes afterwards','Demand, renewables, coal operating proxies and hourly reanalysis temperatures follow the core event evidence.')+'</div>'
    body+='<section id="events"><h2>01 / Event explorer</h2><p>Select a reconstructed contraction or price-only case. Linked panels share time and zoom. Generator rankings are net stepwise impacts across fixed-equation segments; switch intervals are kept separate.</p><label for="event-search">Search date, generator or equation</label><input id="event-search" type="search" style="width:100%;padding:12px;margin-bottom:10px" placeholder="For example LYA1, 2025-11 or a constraint ID"><label for="event-select">Case</label><select id="event-select" style="width:100%;padding:12px"></select><label for="unit-measure">Generator measure</label><select id="unit-measure"><option value="TOTALCLEARED">Dispatch target MW</option><option value="INITIALMW">Initial metered MW</option><option value="AVAILABILITY">Declared availability MW</option></select><div id="event-description"></div><div id="core-event" style="height:1200px"></div><div id="waterfall" style="height:430px"></div><h3>Generator accounting</h3><div id="event-rankings"></div><h3>Equations and active sets</h3><div id="event-equations"></div><div id="event-sets"></div><h3>Supporting market conditions</h3><p>Coal online status uses initial MW &gt;5 as a proxy; zero output does not establish an outage. Registered capacity is joined by effective date where available; a complete planned/forced outage ledger is unavailable. Weather is hourly ERA5 reanalysis, not site telemetry. Rooftop PV uses native source timestamps and the highest-QI estimate (measurement preferred on ties); it is not added to operational demand.</p><div id="conditions-table"></div><div id="context-event" style="height:900px"></div><div id="external-evidence"></div></section>'
    body+='<section id="population"><h2>02 / Population and seasonal coverage</h2>'
    body+=chart(px.scatter(e,x='drop_mw',y='price_jump',color='direction',hover_data=['event_id','time','reported_setter']),
        'Capacity drop versus receiving-region peak price jump','All detections; next-hour peak minus preceding-hour median. Association, with overlapping detections grouped for inference.')
    body+=chart(px.bar(seasonal,x='season',y='events_per_1000h',color='direction',facet_col='season_year',barmode='group'),
        'Seasonal event rates per 1,000 valid hours','Meteorological seasons; December belongs to the following summer year. The study contains two complete summers, two autumns and two winters; spring is available for September-November 2024 and 2025.')
    hourly=e.groupby(['hour','direction'],as_index=False).size()
    hourly['rate']=hourly['size']/((valid.groupby(valid.index.hour).flow.count()/12).reindex(hourly.hour).to_numpy())*1000
    body+=chart(px.line(hourly,x='hour',y='rate',color='direction',markers=True),'Diurnal contraction rate','Fixed UTC+10 market time; valid-hour denominator.')
    body+='</section><section id="generators"><h2>03 / Generator influence in selected incidents</h2>'
    body+=chart(px.bar(grand.head(20).sort_values('tightening_mw'),x='tightening_mw',y='DUID',orientation='h'),
        'Gross tightening across reconstructed fixed-equation steps','Selected-case total with duplicate physical steps removed, not a two-year causal leaderboard. Relief and event exposures are provided in the table.')
    body+=table(grand.head(25))+'</section><section id="comparisons"><h2>04 / Observational price comparisons</h2>'
    body+=f'<p>{len(matched):,} of {len(e):,} detections found a same-month, similar-hour/weekday control beyond the contraction exclusion window. The mean paired difference in next-hour peak price jump is ${mean:,.2f}/MWh (event-day bootstrap 95% interval ${ci[0]:,.2f} to ${ci[1]:,.2f}). These comparisons are observational and may retain confounding; they are not causal estimates.</p>'
    body+='<p>Matching uses only pre-event demand, wind, solar, available generation, price, flow and headroom. Maximum standardized distance: 5; at least five candidate controls. Balance below reports signed standardized covariate differences; poor balance limits interpretation. Selection and price outcomes use revised historical observations, not forecast vintages.</p>'+table(balance)
    body+=chart(px.scatter(matched,x='control_price_jump',y='event_price_jump',color='direction'),
        'Matched event versus control price jumps','Both outcomes are next-hour peak minus preceding-hour median; axes are AUD/MWh.')+'</section>'
    body+='<section id="methods"><h2>05 / Evidence, limitations and downloads</h2>'
    body+=f'<p>The detector identifies P90 positive 30-minute falls separately by year-month and direction. Exact timestamp grids retain month-boundary history. The revised detector has {len(e):,} events versus {len(old):,} in the earlier report; the change ledger records each difference. Episode grouping uses a 30-minute separation; trough and recovery are observed within two hours and may be censored. Directional capacities remain signed.</p>'
    body+='<p>Full-period screening is complete. Detailed recovery is deliberately selected: monthly largest by direction, top absolute events, all receiving-region near-MPC candidates and a reproducible ordinary-case sample. The separate price-first screen adds episodes with no nearby contraction. Recovered comparison windows support auditability. Complete price-first causal reconstructions, outage inventories and operational forecasting remain outside this observational release.</p>'
    expected_coal=int(coal.expected_units.max()) if len(coal) else 0
    body+=f'<p>Exact standing-equation versions were matched for {recquality["exact_version_share"]:.1%} of retained constraint rows. {int(a.exact_step_share.eq(1).sum())} of {len(a)} selected cases have exact equation matches for every attribution step. This does not imply every LHS component is separately observed. Coal context covers the explicitly scoped {expected_coal} station units where dispatch rows are available.</p>'
    body+='<p>Each waterfall isolates fixed-equation generator changes, RHS changes, an aggregate other-LHS term, equation-switch composites and the observed-versus-reconstructed discrepancy. Algebraic reconciliation does not establish that every physical mechanism is identified. Equality/unknown relation types and missing exact factors remain unsupported. The equations show all retained energy/IC factors and an explicit Z term for unrepresented terms.</p>'
    body+='<p>Exact MPC uses a $0.01 rounding tolerance and effective caps of $17,500, $20,300 and $23,200/MWh across the three financial-year settings. APCFLAG is decoded as a bitmask: bit value 4 is MPC/floor binding and remains eligible; administered/override/manual-price regimes are distinguished. Near-MPC means at least 90% of the applicable cap.</p>'
    body+='<p><a href="https://visualisations.aemo.com.au/aemo/nemweb/mmsdatamodelreport/electricity/mms%20data%20model%20report_files/MMS_130.htm">AEMO price-field definitions</a> · <a href="https://www.aemc.gov.au/news-centre/media-releases/aemc-updates-market-price-cap-2026-27">AEMC cap settings</a> · <a href="../INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md">Full methodology</a></p>'
    downloads=['catalogue','attribution','equations','generator_contributions','generator_summary','thresholds','seasonal','matched_controls','match_balance','detector_changes']
    body+='<ul>'+''.join(f'<li><a href="../data/vsa_event_{x}.csv">{escape(x.replace("_"," "))}</a></li>' for x in downloads)+'<li><a href="../data/vsa_price_events.csv">Price-first event catalogue</a></li><li><a href="../data/vsa_event_generator_steps.csv.gz">Five-minute generator changes, coefficients and impacts (compressed CSV)</a></li><li><a href="../data/vsa_event_coal_context.csv">Coal availability and operating-status context</a></li></ul></section>'
    source_text=(root/'source_manifest.jsonl').read_text(encoding='utf-8')
    source_rows=[json.loads(line) for line in source_text.splitlines() if line.strip()]
    def portable(value):
        if isinstance(value,str):return value.replace(str(ROOT)+chr(92),'').replace(ROOT.as_posix()+'/','')
        if isinstance(value,list):return [portable(x) for x in value]
        if isinstance(value,dict):return {k:portable(v) for k,v in value.items()}
        return value
    (dd/'vsa_event_sources.jsonl').write_text('\n'.join(json.dumps(portable(r)) for r in source_rows)+'\n',encoding='utf-8')
    body+='<p><a href="../data/vsa_event_sources.jsonl">Acquisition, source hashes, filters and cleanup log</a></p>'
    payload=json.dumps(bundles,ensure_ascii=True,separators=(',',':')).replace('</','<\/')
    body+='<script>const REGIONS='+json.dumps(c['regions'])+';const BUNDLES='+payload+';</script>'+JAVASCRIPT
    body+='<style>#event-rankings .table-wrap{max-height:420px}select{max-width:100%;padding:10px;margin-bottom:12px}#core-event,#context-event,#waterfall{min-width:700px}.chart-scroll{overflow-x:auto;max-width:100%}</style>'
    for chart_id in ['core-event','context-event','waterfall']:
        import re
        body=re.sub(r'(<div id="'+chart_id+r'"[^>]*></div>)',r'<div class="chart-scroll">\1</div>',body)
    html=render_page('VSA two-year event atlas',body,accent='blue')
    out.write_text('\n'.join(line.rstrip() for line in html.splitlines()),encoding='utf-8')
    md=f'''# VSA two-year event atlas\n\nPeriod: {c['start']} to {c['end']}, fixed UTC+10. Method version: {VERSION}.\n\n## Results\n\n- {len(e):,} contraction detections; {e.incident_id.nunique():,} grouped incidents.\n- {int(e.selected.sum())} selected detailed contraction cases, plus {int(pe.linked_events.eq(0).sum())} price-only cases.\n- {exact_count} exact MPC region-interval observations; {n_mpc} contraction detections with receiving-region MPC in the following hour.\n- {len(matched):,} matched observational comparisons. Mean paired peak-price-jump difference: ${mean:,.2f}/MWh; day-block bootstrap interval ${ci[0]:,.2f} to ${ci[1]:,.2f}. This is not causal.\n\n[Interactive event atlas](html/vsa_event_atlas.html) · [Methodology](INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md)\n\n## Selected-case generator accounting\n\n{grand.head(20).to_markdown(index=False)}\n\nThese totals cover selected fixed-equation segments, not all two-year movements. Gross tightening and relief can offset. Aggregate totals deduplicate shared physical steps; individual cases may overlap. Switching is not attributed to generators in the new equation.\n\n## Seasonal results\n\n{seasonal.to_markdown(index=False)}\n\nDecember is assigned to the following summer year, preserving two complete December-February summers. Autumn and winter also have two complete observations; spring covers September-November 2024 and 2025. Rates use valid hours.\n\n## Evidence and limitations\n\nThe population IC and regional-price grids are complete. Raw unit/equation archives were recovered only for selected case and control windows, with checksums, row filters and cleanup records in data/event_vsa_2y/source_manifest.jsonl.\n\nThe decomposition preserves aggregate other-LHS movements, switch composites and discrepancies. Full equations may contain an unresolved Z term. No causal dispatch replay, welfare-cost calculation or forecast validation has been performed. Coal status is an initial-MW operating proxy; dated registered capacity is included where recovered, but complete planned/forced outage classifications are unavailable. Temperature is hourly reanalysis, not measured station telemetry. No external outage narrative is assigned automatically to VSA cases.\n\n## Rebuild\n\n```text\npython -m nemic.event_atlas screen --config configs/event_vsa_2y.json\npython -m nemic.event_atlas match --config configs/event_vsa_2y.json\npython -m nemic.event_atlas recover --config configs/event_vsa_2y.json\npython -m nemic.event_atlas coal --config configs/event_vsa_2y.json\npython -m nemic.event_reconstruction --config configs/event_vsa_2y.json\npython scripts/build_vsa_event_atlas.py --config configs/event_vsa_2y.json\n```\n\nRendering uses retained evidence and performs no downloads. The acquisition stage enforces a 10 GB combined base-study/event-study storage guard and a 20 GB free-space reserve.\n'''
    md+='\n## Detailed reconstruction coverage\n\n'+a[['event_id','exact_step_share','complete_terms_share','observed_tightening_mw','generator_tightening_mw','switch_composite_mw','unresolved_mw']].to_markdown(index=False)+'\n\nExact-step coverage measures equation-version matching. Complete-terms coverage only concerns the retained energy factors; other LHS services or terms may remain aggregated. Positive components tighten and negative components relieve the directional bound. These are sums of MW changes across steps, not energy (MWh) or simultaneous capacity.\n\n[Source and cleanup log](data/vsa_event_sources.jsonl)\n'
    (ROOT/'docs/VSA_TWO_YEAR_EVENT_ATLAS.md').write_text(md,encoding='utf-8')
    manifest={'method_version':VERSION,'config':str(CONFIG.relative_to(ROOT)),'config_sha256':digest(CONFIG),
        'report_sha256':digest(out),'data_cutoff':c['end'],'build_time_utc':str(pd.Timestamp.now(tz='UTC')),
        'generator_sha256':digest(Path(__file__)),'outputs':[str(out.relative_to(ROOT))],
        'source_manifest_sha256':digest(root/'source_manifest.jsonl'),'summary':summary}
    dump(ROOT/'docs/html/vsa_event_atlas_manifest.json',manifest)
    print(json.dumps(summary,indent=2),flush=True)


JAVASCRIPT=r'''<script>
const esc=x=>String(x??'—').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function tbl(rows,cols){return '<div class="table-wrap" tabindex="0"><table><thead><tr>'+cols.map(x=>'<th>'+esc(x)+'</th>').join('')+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+cols.map(k=>'<td>'+esc(typeof r[k]==='number'?r[k].toFixed(2):r[k])+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
const sel=document.getElementById('event-select');BUNDLES.forEach((b,i)=>{let o=document.createElement('option');o.value=i;o.textContent=b.event.time.slice(0,16).replace('T',' ')+' · '+b.event.direction+' · '+(b.event.drop_mw==null?'price-only':b.event.drop_mw.toFixed(0)+' MW')+' · '+b.event.event_id;sel.appendChild(o);});
function trace(rows,field,name,row,color){return {x:rows.map(r=>r.time),y:rows.map(r=>r[field]),name,type:'scatter',mode:'lines',xaxis:row===1?'x':'x'+row,yaxis:row===1?'y':'y'+row,line:{color}};}
function layout(rows,height){let z={height,grid:{rows,columns:1,pattern:'independent',roworder:'top to bottom'},margin:{l:80,r:35,t:135,b:60},paper_bgcolor:'white',plot_bgcolor:'#ececf3',hovermode:'x unified',legend:{orientation:'h',y:1.035,font:{size:10}},font:{family:'Arial',color:'#444'}};for(let i=1;i<=rows;i++){let suf=i===1?'':i;z['xaxis'+suf]={type:'date',matches:'x',gridcolor:'white'};z['yaxis'+suf]={gridcolor:'white',automargin:true};}return z;}
function choose(){let b=BUNDLES[Number(sel.value)],e=b.event,s=b.series,t=e.time;document.getElementById('event-description').innerHTML='<p><strong>'+esc(e.event_id)+'</strong> · '+esc(e.selection_reason)+'</p><p>Receiving region: '+esc(e.receiver)+'. Exact-step coverage: '+(e.exact_step_share==null?'not attributed':(100*e.exact_step_share).toFixed(1)+'%')+'. Baseline and trough are retrospective landmarks; switch/other-LHS contributions are explicitly separate.</p>';
if(e.observed_tightening_mw!=null){let top=b.rankings.slice().sort((a,b)=>b.net_tightening_mw-a.net_tightening_mw)[0];document.getElementById('event-description').innerHTML+='<p>The baseline-to-trough loss was <strong>'+e.observed_tightening_mw.toFixed(1)+' MW</strong>. Identified fixed-equation generator terms sum to '+e.generator_tightening_mw.toFixed(1)+' MW net tightening; RHS movement '+e.rhs_tightening_mw.toFixed(1)+' MW; switches '+e.switch_composite_mw.toFixed(1)+' MW. '+(top?'The largest net generator contribution was '+esc(top.DUID)+' ('+top.net_tightening_mw.toFixed(1)+' MW). ':'')+'Other LHS movements and the discrepancy are shown separately below. A zero identified component with missing coverage does not establish zero physical influence.</p>';}if(e.mpc_in_preceding_hour)document.getElementById('event-description').innerHTML+='<p><strong>MPC was already observed in the preceding hour.</strong> This detection is not evidence that the contraction initiated the price shock.</p>';if(e.physical_intervention)document.getElementById('event-description').innerHTML+='<p><strong>Intervention flag present:</strong> physical dispatch and pricing-run quantities may differ; interpret the price association separately.</p>';
let tr=[trace(s,'export','Upper bound',1,'#5696b9'),trace(s.map(r=>({...r,lower:-r.import})),'lower','Lower bound',1,'#8370b4'),trace(s,'flow','Flow',1,'#282b30'),trace(s,e.receiver+'_RRP',e.receiver+' price',2,'#ce9a48'),trace(s,e.sender+'_RRP',e.sender+' price',2,'#268a87'),trace(s,e.receiver+'_mpc','MPC',2,'#aaa')];
for(let id of [...new Set(b.units.map(r=>r.DUID))]){let u=b.units.filter(r=>r.DUID===id);tr.push(trace(u,document.getElementById('unit-measure').value,id,3));}
let ids=[...new Set(b.constraints.map(r=>r.CONSTRAINTID))],times=s.map(r=>r.time);let lookup=new Map(b.constraints.map(r=>[r.CONSTRAINTID+'|'+r.time,r]));tr.push({type:'heatmap',x:times,y:ids,z:ids.map(id=>times.map(tm=>{let r=lookup.get(id+'|'+tm);return !r?null:r.binding?2:r.ic_slack_mw>=0&&r.ic_slack_mw<=50?1:0;})),xaxis:'x4',yaxis:'y4',showscale:true,colorbar:{title:{text:'0 slack<br>1 near<br>2 binding'},len:.15,y:.1},colorscale:[[0,'#f4f4f8'],[.5,'#ce9a48'],[1,'#7658c9']],name:'Constraint state'});
let l=layout(4,1200);l.yaxis.title={text:'Flow / bound MW'};l.yaxis2.title={text:'AUD/MWh'};l.yaxis3.title={text:document.getElementById('unit-measure').selectedOptions[0].textContent};l.yaxis4.tickfont={size:9};l.shapes=[{type:'line',x0:t,x1:t,y0:0,y1:1,xref:'x',yref:'paper',line:{color:'#ce9a48',dash:'dash'}}];for(let [key,color] of [['baseline_time','#268a87'],['trough_time','#7658c9'],['recovery_time','#777']])if(e[key])l.shapes.push({type:'line',x0:e[key],x1:e[key],y0:0,y1:1,xref:'x',yref:'paper',line:{color,dash:'dot',width:1}});Plotly.react('core-event',tr,l,{responsive:true,displaylogo:false});
let keys=['generator_tightening_mw','rhs_tightening_mw','other_lhs_tightening_mw','switch_composite_mw','unresolved_mw'];let vals=keys.map(k=>e[k]);if(vals.some(x=>x!=null)){Plotly.react('waterfall',[{type:'waterfall',x:['Generators','RHS','Other LHS / missing terms','Switch composite','Discrepancy','Observed loss'],y:[...vals,e.observed_tightening_mw],measure:['relative','relative','relative','relative','relative','total'],connector:{line:{color:'#aaa'}}}],{height:430,title:{text:'Stepwise accounting: positive = tightening'},yaxis:{title:{text:'MW'}},margin:{b:100,t:60}},{responsive:true,displaylogo:false});}else{Plotly.purge('waterfall');document.getElementById('waterfall').innerHTML='<p>No contraction waterfall is assigned to a price-only case.</p>';}
document.getElementById('event-rankings').innerHTML=tbl(b.rankings,['DUID','net_tightening_mw','gross_tightening_mw','gross_relief_mw']);document.getElementById('event-equations').innerHTML=b.equations.map(r=>'<details><summary>'+esc(r.constraint)+' · '+esc(r.version_key)+'</summary><p>'+esc(r.description)+'</p><p style="overflow-wrap:anywhere">'+esc(r.equation)+'</p><p>'+esc(r.Z_note)+'</p></details>').join('');document.getElementById('event-sets').innerHTML='<details><summary>Interval equation solutions: RHS, LHS, marginal value and slack</summary>'+tbl(b.constraints,['time','CONSTRAINTID','RHS','LHS','MARGINALVALUE','ic_slack_mw','binding'])+'</details><details><summary>Set-membership snapshot at detection and overlapping invocations</summary>'+tbl(b.sets,['GENCONSETID','GENCONID','EFFECTIVEDATE','VERSIONNO'])+tbl(b.invocations,['GENCONSETID','start','end','SYSTEMNORMAL'])+'</details>';
document.getElementById('conditions-table').innerHTML=tbl(b.conditions,['region','condition','unit','pre_hour_median','at_detection','next_hour_min','next_hour_max','month_hour_percentile']);let ctx=[];for(let r of REGIONS){ctx.push(trace(s,r+'_TOTALDEMAND',r+' demand',1));ctx.push(trace(s,r+'_SS_WIND_CLEAREDMW',r+' wind',1));ctx.push(trace(s,r+'_SS_SOLAR_CLEAREDMW',r+' solar',1));ctx.push(trace(b.rooftop.filter(x=>x.REGIONID===r),'POWER',r+' rooftop estimate (native cadence)',1));let co=b.coal.filter(x=>x.REGIONID===r);ctx.push(trace(co,'coal_initial_mw',r+' coal initial MW',2));ctx.push(trace(co,'coal_available_mw',r+' coal availability',2));}ctx.push(trace(b.weather,'VIC_Melbourne__temperature_2m','Melbourne reanalysis °C',3));ctx.push(trace(b.weather,'SA_Adelaide__temperature_2m','Adelaide reanalysis °C',3));let cl=layout(3,900);cl.yaxis.title={text:'Demand / renewables MW'};cl.yaxis2.title={text:'Coal MW (selected stations)'};cl.yaxis3.title={text:'Hourly temperature °C'};Plotly.react('context-event',ctx,cl,{responsive:true,displaylogo:false});let ex=b.external;document.getElementById('external-evidence').innerHTML=(ex?'<p>'+esc(ex.text)+' <a href="'+esc(ex.url)+'">AEMO published event context</a></p>':'<p>No independently verified outage narrative is attached to this case. Availability changes are not classified as forced outages.</p>')+tbl(b.coal.filter(r=>r.time===t),['REGIONID','online_units_proxy','not_generating_units_proxy','missing_units','coal_initial_mw','coal_available_mw','online_registered_mw_proxy','not_generating_registered_mw_proxy','capacity_covered_units']);history.replaceState(null,'','#event='+encodeURIComponent(e.event_id));}
sel.addEventListener('change',choose);document.getElementById('unit-measure').addEventListener('change',choose);let initial=BUNDLES.findIndex(b=>'#event='+encodeURIComponent(b.event.event_id)===location.hash);if(initial>=0)sel.value=initial;document.getElementById('event-search').addEventListener('input',ev=>{let q=ev.target.value.toLowerCase();[...sel.options].forEach((o,i)=>o.hidden=!JSON.stringify([BUNDLES[i].event,BUNDLES[i].rankings,BUNDLES[i].equations]).toLowerCase().includes(q));});choose();let syncing=false;['core-event','context-event'].forEach(id=>document.getElementById(id).on('plotly_relayout',ev=>{if(syncing)return;let a=ev['xaxis.range[0]'],b=ev['xaxis.range[1]'];if(a&&b){syncing=true;Plotly.relayout(id==='core-event'?'context-event':'core-event',{'xaxis.range':[a,b]}).then(()=>syncing=false);}}));
</script>'''


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(CONFIG));a=p.parse_args();report(settings(a.config))
