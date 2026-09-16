"""Render the pre-model NOS impact audit from frozen cached outputs."""
import html,json,sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nemic.experiments.core import load_config,digest,clean
from report_theme.report_theme import hero,metric,figure_html,style_plotly,render_page


def table(rows):
    return '<div class="table-wrap" tabindex="0">'+pd.DataFrame(rows).to_html(index=False,escape=True,float_format=lambda x:f'{x:,.2f}')+'</div>' if rows else '<p>No supported rows.</p>'


def build():
    c=load_config('configs/experiments/vni_diurnal_nos_v2.json');root=c['_run'];folder=root/'nos/impact/full_development'
    status=json.loads((folder/'status.json').read_text());rankings=json.loads((folder/'rankings.json').read_text())
    body=hero('VNI network-outage research','Which scheduled outages coincide with','the largest directional-limit reductions',
        'Pre-model evidence distinguishes scheduled exposure, expected sets and adjusted limit associations. Results are exploratory development evidence.',
        ['VNI · VIC1-NSW1','NOS snapshots · Aug 2025–Aug 2026','MW effects','No causal claim'])
    body+='<section class="metrics">'+metric('Candidate bookings',status['candidate_bookings'],'Known before scheduled start')+metric('Matched direction episodes',status['matched_direction_episodes'],'Isolated episodes with controls')+metric('Supported recurring entities',status['supported_recurring_entities'],'≥10 episodes across ≥3 months')+metric('O5 feature gate','Closed' if not status['O5_gate'] else 'Open',status['reason'])+'</section>'
    body+='<section><h2>Usually highest observed impact</h2><p>Ranked by median episode-level adjusted MW reduction. Positive values mean lower transfer capability. A shortlist entry requires recurring support, acceptable pre-trend balance and an effect larger than its matched pseudo-start placebo magnitude; leave-one-episode-out ranks show stability.</p>'+table(status['highest_impact'])
    supported=pd.DataFrame([r for r in rankings if r['supported_recurring']])
    if len(supported):
        supported=supported.sort_values('median_reduction_mw').tail(20)
        fig=go.Figure(go.Bar(y=supported.entity,x=supported.median_reduction_mw,orientation='h',error_x=dict(type='data',
            symmetric=False,array=supported.ci_high-supported.median_reduction_mw,arrayminus=supported.median_reduction_mw-supported.ci_low),
            marker_color='#5696b9'))
        style_plotly(fig,'Supported recurring outage/set associations',height=max(520,25*len(supported)));fig.update_xaxes(title='Adjusted directional-limit reduction (MW)')
        body+=figure_html(fig.to_html(full_html=False,include_plotlyjs=False),'Median adjusted reduction with episode-bootstrap interval','Exploratory association; overlapping and unmatched episodes are excluded.')
    body+='</section><section><h2>All asset and expected-set evidence</h2>'+table(rankings)+'</section>'
    curves=folder/'event_curves.parquet'
    if curves.exists():
        f=pd.read_parquet(curves);g=f.groupby(['direction','hours'])[['actual_limit','reference_limit']].mean().reset_index()
        fig=go.Figure()
        for direction,d in g.groupby('direction'):
            fig.add_trace(go.Scatter(x=d.hours,y=d.actual_limit,name=direction+' exposed'))
            fig.add_trace(go.Scatter(x=d.hours,y=d.reference_limit,name=direction+' matched reference',line=dict(dash='dash')))
        style_plotly(fig,'Average event-time directional limits',height=540);fig.update_xaxes(title='Hours from scheduled start');fig.update_yaxes(title='Directional limit (MW)')
        body+=figure_html(fig.to_html(full_html=False,include_plotlyjs=False),'Matched event-time profiles','Averages do not replace episode-level adjusted estimates or uncertainty.')
    exclusions=json.loads((folder/'exclusions.json').read_text())
    reasons=(pd.DataFrame(exclusions).reason.value_counts().rename_axis('reason').reset_index(name='records').to_dict('records')
             if exclusions else [])
    body+='<section><h2>Identification and exclusions</h2><p>Controls are earlier same-clock, same-weekday windows with comparable pre-limit level/trend and operating state, and no mapped outage exposure. Concurrent mapped outages are excluded from individual attribution. Failed balance or insufficient controls produce unavailable results.</p>'+table(reasons)+'</section>'
    body+='<section><h2>Interpretation</h2><p>NOS lists expected constraint sets. It does not prove invocation or that a set determined the limit. Standing equation mappings are reconstructed retrospectively, so this report cannot establish live feature availability. O5 outcome-weighted features remain disabled until fold-local encodings and dependence/rank-stability gates pass.</p></section>'
    out=root/'report/nos_outage_impact_analysis.html';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(render_page('VNI NOS impact analysis',body),encoding='utf-8')
    (out.parent/'nos_impact_build.json').write_text(json.dumps(clean({'status_sha256':digest(folder/'status.json'),'rankings_sha256':digest(folder/'rankings.json'),'report_sha256':digest(out),'generator_sha256':digest(__file__)}),indent=2)+'\n')
    print(out)


if __name__=='__main__':build()
