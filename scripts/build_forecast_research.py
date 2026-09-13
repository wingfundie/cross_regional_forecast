"""Render the cited forecasting research from Markdown; no data acquisition."""
from pathlib import Path
import hashlib
import json
import re
import sys
from html import escape
from urllib.parse import urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/report_theme'))
from report_theme import render_page

SOURCE = ROOT / 'docs/QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md'
OUTPUT = ROOT / 'docs/html/qni_vni_forecast_model_improvement.html'
MANIFEST = ROOT / 'docs/data/qni_vni_forecast_research_build.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    source = SOURCE.read_text(encoding='utf-8')
    renderer = markdown.Markdown(extensions=['tables', 'fenced_code', 'footnotes', 'toc'],
                                 extension_configs={'toc': {'toc_depth': '2-2'}})
    body = renderer.convert(source)

    def rewrite(match):
        href = match.group(1)
        if href.startswith('#') or urlsplit(href).scheme:
            return match.group(0)
        # Both Markdown and HTML source links resolve to the same repository file.
        return f'href="../{href}"'

    body = re.sub(r'href="([^"]+)"', rewrite, body)
    body = body.replace('<table>', '<div class="table-scroll" tabindex="0"><table>').replace('</table>', '</table></div>')
    title_end = body.index('</h1>') + len('</h1>')
    nav = ('<nav aria-label="Report contents"><details open><summary>Contents</summary>'
           + renderer.toc + '</details></nav>')
    downloads = ('<p class="downloads"><a href="../QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md">Markdown edition</a>'
                 ' · <a href="../data/qni_vni_simple_model_research.json">Full numerical evidence and input log</a></p>')
    body = body[:title_end] + downloads + nav + body[title_end:]
    page = render_page('QNI and VNI flow forecasting improvement methodology', body, plotly=False, accent='blue')
    # The deep-research document style takes priority over the theme's optional cards/pills.
    css = '''
body{background:#fff;color:#202327}main{max-width:1120px;padding:40px 32px 80px}
h1{font-size:clamp(32px,4vw,52px);line-height:1.12;max-width:1000px;letter-spacing:-.035em}
h2{font-size:27px;margin-top:52px;padding-top:12px;border-top:1px solid #ddd;scroll-margin-top:16px}
h3{font-size:20px;margin-top:28px}p,li{line-height:1.7}p{max-width:1000px}
a{color:#285f8e;overflow-wrap:anywhere}nav{margin:28px 0;background:#f7f7f7;padding:16px 20px}
nav ul{columns:2;column-gap:32px;padding-left:20px}nav li{break-inside:avoid;margin:4px 0;font-size:14px}
summary{cursor:pointer;font-weight:650}.downloads{font-size:14px;color:#666}
.table-scroll{overflow-x:auto;width:100%;margin:22px 0;border:1px solid #ddd}
table{width:100%;border-collapse:collapse;margin:0;font-size:13px;line-height:1.5}
th,td{padding:11px 12px;vertical-align:top;border-bottom:1px solid #e5e5e5;text-align:left}
th{background:#f0f1f3;font-weight:650}tbody tr:nth-child(even){background:#fafafa}
pre{white-space:pre;overflow-x:auto;background:#f5f5f5;border:1px solid #ddd;padding:16px;font-size:13px}
code{overflow-wrap:anywhere}pre code{overflow-wrap:normal}.footnote{font-size:13px}.footnote li{margin:14px 0}
@media(max-width:650px){main{padding:24px 16px 50px}nav ul{columns:1}h2{font-size:23px}table{min-width:640px}}
@media print{main{max-width:none;padding:0}nav,.downloads{display:none}h1{font-size:30px}
h2{break-after:avoid}table{font-size:9px;min-width:0}.table-scroll{overflow:visible}a{color:#222}}
'''
    page = page.replace('</style>', css + '</style>', 1)
    OUTPUT.write_text(page, encoding='utf-8')
    inputs = [SOURCE, ROOT / 'docs/data/qni_vni_simple_model_research.json',
              ROOT / 'scripts/report_theme/report_theme.py', ROOT / 'scripts/report_theme/report.css',
              Path(__file__)]
    manifest = {'report': OUTPUT.relative_to(ROOT).as_posix(), 'markdown': SOURCE.relative_to(ROOT).as_posix(),
                'research_access_date': '2026-09-13', 'study_cutoff': '2026-08-31 23:55 fixed UTC+10',
                'status': 'research methodology plus exploratory simple-model probe',
                'rebuild_command': 'python scripts/build_forecast_research.py',
                'probe_command': 'python scripts/research_simple_models.py',
                'render_downloads': [], 'markdown_package_version': markdown.__version__,
                'inputs': [{'path': p.relative_to(ROOT).as_posix(), 'sha256': digest(p), 'bytes': p.stat().st_size} for p in inputs],
                'output_sha256': digest(OUTPUT)}
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(OUTPUT)
    print('words:', len(source.split()), 'bytes:', OUTPUT.stat().st_size)


if __name__ == '__main__':
    build()
