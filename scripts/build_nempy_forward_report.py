"""Rebuild the NEMPy design report from cached evidence; no market acquisition."""
from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from bs4 import BeautifulSoup
from nempy import markets

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'report_theme'))
from report_theme import hero, metric, finding, figure_html, render_page, matplotlib_style

OUT = ROOT / 'reports' / 'nempy_forward_forecast_design_20261004'
REPORT = OUT / 'Forward_Forecast_with_NEMPy.md'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def num(value):
    return float(value.replace('%', '').replace(',', '').strip())


def evidence():
    rows = []
    for connector in ['VNI', 'QNI']:
        source = ROOT / 'docs' / f'{connector}_DIURNAL_NOS_RESULTS.md'
        for line in source.read_text(encoding='utf-8').splitlines():
            cells = [s.strip() for s in line.strip().strip('|').split('|')]
            if line.startswith('|') and len(cells) == 8 and cells[0].lower() in (
                'export tight', 'import tight', 'export minimum', 'import minimum'
            ):
                rows.append(dict(connector=connector, metric='skill_vs_persistence_pct',
                                 target=cells[0].split()[0].lower()+'_tight', band=cells[1],
                                 nominal='', value=num(cells[6]),
                                 source=source.relative_to(ROOT).as_posix()))
            if line.startswith('|') and len(cells) == 6 and cells[0] == 'Delivery period':
                rows.append(dict(connector=connector, metric='interval_coverage_pct',
                                 target='pooled_four_targets', band='all',
                                 nominal=num(cells[1]), value=num(cells[2]),
                                 source=source.relative_to(ROOT).as_posix()))
    assert len(rows) == 20, f'Unexpected evidence schema/count: {len(rows)}'
    with (OUT / 'evidence.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    return rows


def toy_solve(name, cap, include_equation):
    market = markets.SpotMarket(market_regions=['SOUTH', 'NORTH'], unit_info=pd.DataFrame({
        'unit': ['S', 'N'], 'region': ['SOUTH', 'NORTH']}))
    market.set_unit_volume_bids(pd.DataFrame({'unit': ['S', 'N'], '1': [2000.0, 2000.0]}))
    market.set_unit_price_bids(pd.DataFrame({'unit': ['S', 'N'], '1': [20.0, 100.0]}))
    market.set_demand_constraints(pd.DataFrame({'region': ['SOUTH', 'NORTH'], 'demand': [0.0, 1000.0]}))
    market.set_interconnectors(pd.DataFrame({'interconnector': ['S-N'], 'from_region': ['SOUTH'],
                                            'to_region': ['NORTH'], 'min': [-2000.0], 'max': [float(cap)]}))
    if include_equation:
        market.set_generic_constraints(pd.DataFrame({'set': ['synthetic_network'], 'type': ['<='], 'rhs': [700.0]}))
        market.link_units_to_generic_constraints(pd.DataFrame({'set': ['synthetic_network'],
            'unit': ['S'], 'service': ['energy'], 'coefficient': [0.5]}))
        market.link_interconnectors_to_generic_constraints(pd.DataFrame({'set': ['synthetic_network'],
            'interconnector': ['S-N'], 'coefficient': [1.0]}))
    market.dispatch()
    flow = float(market.get_interconnector_flows()['flow'].iloc[0])
    dispatch = market.get_unit_dispatch().set_index('unit')['dispatch']
    south, north = float(dispatch['S']), float(dispatch['N'])
    assert abs(south-flow) < 1e-6 and abs(north+flow-1000) < 1e-6
    if include_equation:
        assert flow + 0.5*south <= 700 + 1e-6
    return dict(case=name, flow_mw=flow, southern_generation_mw=south,
                northern_generation_mw=north, offer_cost_per_hour=20*south+100*north,
                synthetic=True, nempy_version=importlib.metadata.version('nempy'))


def make_charts(rows, toy):
    figs = OUT / 'figures'; figs.mkdir(exist_ok=True)
    plt.rcParams.update(matplotlib_style())
    data = pd.DataFrame(rows)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    colors = {'VNI export': '#5696b9', 'VNI import': '#268a87', 'QNI export': '#8370b4', 'QNI import': '#ce9a48'}
    for (ic, target), g in data[data.metric == 'skill_vs_persistence_pct'].groupby(['connector', 'target'], sort=False):
        label = ic+' '+target.removesuffix('_tight')
        ax.plot(range(4), g.value, marker='o', linewidth=2, label=label, color=colors[label])
    ax.axhline(0, color='#66717e', lw=1)
    ax.set_xticks(range(4), ['0.5–6 h', '6.5–24 h', '24.5–72 h', '72.5–168 h'])
    ax.set_ylabel('Tight-limit MAE skill versus persistence (%)')
    ax.set_xlabel('Forecast lead band')
    ax.legend(ncol=4, loc='upper center', bbox_to_anchor=(.5, 1.16))
    fig.tight_layout(); fig.savefig(figs / 'limit_skill.png'); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    g = data[data.metric == 'interval_coverage_pct'].sort_values(['nominal', 'connector'])
    labels = [f'{r.connector}\nNominal {r.nominal:g}%' for r in g.itertuples()]
    bars = ax.bar(labels, g.value, color=['#8370b4', '#5696b9']*2, width=.6)
    ax.scatter(range(4), g.nominal, color='#282b30', marker='_', s=900, label='Nominal target', zorder=3)
    ax.bar_label(bars, labels=[f'{x:.2f}%' for x in g.value], padding=4)
    ax.set_ylim(0, 106); ax.set_ylabel('Empirical coverage (%)')
    ax.legend(loc='upper left'); fig.tight_layout()
    fig.savefig(figs / 'interval_coverage.png'); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.2))
    bars = ax.barh(['Fixed reference cap', 'Explicit equation', 'Equation + same cap'],
                  [r['flow_mw'] for r in toy], color=['#8370b4', '#268a87', '#ce9a48'], height=.55)
    ax.invert_yaxis(); ax.set_xlim(0, 550)
    ax.bar_label(bars, labels=[f"{r['flow_mw']:.2f} MW" for r in toy], padding=6)
    ax.set_xlabel('Solved northbound flow (MW) · synthetic two-region example')
    fig.tight_layout(); fig.savefig(figs / 'toy_comparison.png'); plt.close(fig)


def audit_sources():
    sources = ['README.md', 'BACKTEST_REPORT.md', 'nemic/prepare.py', 'nemic/common.py',
        'docs/RESULTS_DATA_AND_FEATURES.md', 'docs/VNI_DIURNAL_NOS_RESULTS.md',
        'docs/QNI_DIURNAL_NOS_RESULTS.md', 'docs/VNI_SAVED_MODEL_GUIDE.md',
        'docs/QNI_SAVED_MODEL_GUIDE.md', 'docs/PRODUCTION_PIPELINE_GUIDE.md',
        'docs/VNI_TWO_YEAR_CONSTRAINT_STUDY.md', 'docs/QNI_TWO_YEAR_CONSTRAINT_STUDY.md',
        'execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md',
        'reports/nos_outage_regime_research_20260924/build_manifest.json',
        'reports/nos_outage_regime_research_20260924/sources/constraint_mechanics/RESULTS_SUMMARY.md',
        'reports/qni_vni_clustering_v1/Clustering_Research.md',
        'reports/qni_vni_clustering_v1/manifest.json',
        'data/forecast_experiments/qni_vni_clustering_v1/continuation_status.json',
        'data/forecast_experiments/qni_vni_clustering_v1/run/VNI/summary.json',
        'data/forecast_experiments/qni_vni_clustering_v1/run/QNI/summary.json',
        'execution/qni_vni_fundamentals_v3/README.md',
        'data/forecast_experiments/qni_vni_fundamentals_v3/assessment/results.json']
    records = [dict(path=s, sha256=digest(ROOT/s), bytes=(ROOT/s).stat().st_size) for s in sources]
    published = []
    for ic in ['vni', 'qni']:
        manifest_path = ROOT / f'reports/{ic}_diurnal_nos_v2/published_manifest.json'
        records.append(dict(path=manifest_path.relative_to(ROOT).as_posix(), sha256=digest(manifest_path)))
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for item in manifest['files']:
            if item['path'].endswith('/index.html') or 'research_interval_coverage.csv' in item['path']:
                p = ROOT / item['path']
                actual = digest(p) if p.is_file() else None
                published.append(dict(path=item['path'], expected_sha256=item['sha256'],
                                      actual_sha256=actual, matches=actual == item['sha256']))
    assessments = json.loads((ROOT / sources[-1]).read_text(encoding='utf-8'))
    report = dict(scope='Hashes of inspected evidence; selected published outputs checked, not full raw-data revalidation.',
                  sources=records, selected_published_checks=published,
                  fundamentals_v3=dict(rows=len(assessments), promotion_true=sum(bool(x.get('promotion')) for x in assessments)),
                  source_cutoff='Primarily August 2026; NOS outlook uses the archived snapshot stated in its source.',
                  external_checked_date='2026-10-04')
    write_json(OUT / 'source_audit.json', report)
    return report


def render(rows):
    doc = markdown.Markdown(extensions=['tables', 'fenced_code', 'toc'], extension_configs={'toc': {'toc_depth': '2'}})
    html = doc.convert(REPORT.read_text(encoding='utf-8'))
    soup = BeautifulSoup(html, 'html.parser')
    title_id = soup.h1.get('id')
    soup.h1.decompose()
    for table in soup.find_all('table'):
        wrap = soup.new_tag('div', attrs={'class': 'table-wrap', 'tabindex': '0'})
        table.wrap(wrap)
    for img in soup.find_all('img'):
        p = OUT / img['src']
        img['src'] = 'data:image/png;base64,' + base64.b64encode(p.read_bytes()).decode('ascii')
        img['loading'] = 'lazy'
        chart = str(img)
        fragment = BeautifulSoup(figure_html(chart, img.get('alt', ''), 'Source and interpretation are stated immediately below.'), 'html.parser')
        img.replace_with(fragment)
    body = hero('INTERFLOW / RESEARCH DESIGN', 'Forecast the network.', 'Then solve the market.',
                'An end-to-end design for next-seven-day and month-ahead interconnector, flow and spread forecasts with NEMPy.',
                ['4 October 2026', 'QNI + VNI first', 'Five-region market', 'Research proposal'])
    body = body.replace('<header>', f'<header id="{title_id}">', 1)
    body += '<nav class="contents"><h2>In this report</h2>'+doc.toc+'</nav>'
    body += '<div class="metrics">'+metric('Near-term horizon', '7 days', 'Existing bundles stop at 336 half-hours')
    body += metric('Extended horizon', '30 days', 'A distinct ensemble and validation contract')
    body += metric('Network branches', '3', 'Envelope, equations and hybrid')
    body += metric('Core principle', 'Solve binding', 'Forecast scenarios and let dispatch select the active constraints')+'</div>'
    body += '<div class="findings">'+finding(1, 'Begin with forecast limits', 'Test the value of the existing VNI-led research on common-row downstream flow and spread forecasts.')
    body += finding(2, 'Use NOS to forecast configurations', 'Booking, invocation, limit-setting and economic binding are different events.')
    body += finding(3, 'Preserve redispatch', 'Complete equations let generator response change transfer headroom; duplicate restrictions can prevent that response.')+'</div>'
    body += '<article class="report-content">'+str(soup)+'</article>'
    page = render_page('Forward forecasts with NEMPy — seven days and month ahead', body, plotly=False)
    extra = '''.report-content{max-width:1120px;margin:auto}.report-content h2{margin-top:54px;scroll-margin-top:20px}
    .report-content h3{margin-top:30px}.table-wrap{overflow-x:auto;max-width:100%;margin:20px 0}
    table{min-width:660px;width:100%;border-collapse:collapse;white-space:normal}th,td{vertical-align:top;text-align:left}
    th:first-child,td:first-child{min-width:150px}.chart-scroll img{min-width:660px;border-top:2px solid #4c94df}
    pre{overflow-x:auto;background:#ececf3;padding:18px;border-radius:8px;font-size:13px;line-height:1.6}
    code{overflow-wrap:anywhere}pre code{overflow-wrap:normal}.report-content img{max-width:100%;height:auto;display:block}
    .report-content a{overflow-wrap:anywhere}.contents{margin:26px 0;padding:20px;border:1px solid #dfe3eb;border-radius:10px}
    .contents .toc>ul>li>a{display:none}.contents .toc ul{list-style:none;margin:0;padding:0}
    .contents .toc>ul>li>ul{columns:2;column-gap:32px}.contents li{break-inside:avoid;padding:3px 0}
    blockquote{border-left:4px solid #268a87;background:#e9f4f2;margin:22px 0;padding:12px 20px}
    .metrics .metric strong{font-size:28px}.report-content figure{margin:28px 0}
    @media(max-width:650px){.contents .toc>ul>li>ul{columns:1}.report-content h2{font-size:25px}}
    @media print{pre{white-space:pre-wrap}table{min-width:0}.table-wrap{overflow:visible}}
    '''
    page = page.replace('</head>', '<style>'+extra+'</style></head>')
    (OUT / 'index.html').write_text(page, encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    rows = evidence()
    toy = [toy_solve('fixed_reference_cap', 400, False),
           toy_solve('explicit_equation', 2000, True),
           toy_solve('equation_plus_duplicate_cap', 400, True)]
    assert abs(toy[1]['flow_mw'] - 700/1.5) < 1e-6
    assert all(abs(toy[i]['flow_mw']-400) < 1e-6 for i in [0, 2])
    pd.DataFrame(toy).to_csv(OUT / 'toy_results.csv', index=False)
    make_charts(rows, toy)
    audit = audit_sources()
    render(rows)
    paths = [REPORT, OUT/'index.html', OUT/'evidence.csv', OUT/'toy_results.csv', OUT/'source_audit.json',
             *sorted((OUT/'figures').glob('*.png'))]
    inputs = [Path(__file__), ROOT/'scripts/verify_nempy_forward_report.py',
              ROOT/'scripts/report_theme/report_theme.py', ROOT/'scripts/report_theme/report.css']
    manifest = dict(report='nempy_forward_forecast_design_20261004',
        built_at=datetime.now(timezone.utc).isoformat(), report_date='2026-10-04',
        horizon='30 minutes through 7 days, separate days 8–30 scenarios',
        rebuild='python scripts/build_nempy_forward_report.py',
        status='research design, not a forecast service',
        dependencies={k: importlib.metadata.version(k) for k in ['nempy','mip','pandas','Markdown','matplotlib','beautifulsoup4']},
        inputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)) for p in inputs],
        outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p),bytes=p.stat().st_size) for p in paths])
    write_json(OUT/'manifest.json', manifest)
    print(json.dumps({'report':str(REPORT), 'words':len(REPORT.read_text(encoding='utf-8').split()),
                      'evidence_rows':len(rows), 'toy_flows':[r['flow_mw'] for r in toy],
                      'source_mismatches':[r['path'] for r in audit['selected_published_checks'] if not r['matches']]}))


if __name__ == '__main__':
    main()
