"""Shared institutional Virtual Barrels HTML/KaTeX/Plotly/Manifest build kit.

Reuses the proven Valuation v3 visual standard (#244e78 navy hero, pure #ffffff canvas,
non-wrapping tables, Virtual Barrels callouts, inline Plotly exhibits, server-side KaTeX,
paginated searchable directory tables, and offline Playwright QA) across all three flagship
v2 research reports and the compressed Event Atlases.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import subprocess
from html import escape
from pathlib import Path
from typing import Any

import plotly
from bs4 import BeautifulSoup, NavigableString

ROOT = Path(__file__).resolve().parents[2]
V3_REF = ROOT / "reports/interregional_valuation_research_v3"
V2_REF = ROOT / "reports/interregional_valuation_research_v2"

PALETTE = {
    "navy": "#244e78",
    "deep": "#073c64",
    "blue": "#4c94df",
    "sky": "#83b6d9",
    "pale": "#d9e7f1",
    "gold": "#b08b42",
    "sand": "#dcc28f",
    "teal": "#268a87",
    "mint": "#8fcbc9",
    "purple": "#7658c9",
    "lavender": "#b9a9e6",
    "red": "#b44d5e",
    "rose": "#e0a3ad",
    "slate": "#66717e",
    "green": "#3f7d3a",
}

LINK_COLORS = {
    "VNI": "#4c94df",
    "QNI": "#b08b42",
    "Heywood": "#7658c9",
    "Directlink": "#dcc28f",
    "Murraylink": "#268a87",
    "Basslink": "#b44d5e",
}

TECH_COLORS = {
    "BESS": "#7658c9",
    "Hydro": "#073c64",
    "Solar": "#b08b42",
    "Wind": "#268a87",
    "Coal": "#66717e",
    "Gas": "#b44d5e",
    "Other": "#9aa6b2",
}


def sha256_file(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix.lower() in {".py", ".md", ".json", ".csv", ".js", ".mjs", ".cjs", ".css", ".txt", ".html"}:
        b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest()


def style_plotly_white(fig, ytitle: str = "", height: int = 390, xtitle: str = "", margin_t: int = 56, legend_y: float = 1.15):
    """Apply pure #ffffff Virtual Barrels institutional Plotly styling."""
    fig.update_layout(
        height=height,
        margin=dict(l=72, r=24, t=margin_t, b=56),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font=dict(family="Segoe UI, Arial, sans-serif", size=12, color="#30343a"),
        legend=dict(orientation="h", x=0, y=legend_y, font=dict(size=11)),
        hovermode="closest",
    )
    fig.update_xaxes(gridcolor="#edf0f2", automargin=True, title_text=xtitle, title_font_size=12)
    fig.update_yaxes(gridcolor="#e8edf1", zerolinecolor="#97a8b6", automargin=True, title_text=ytitle, title_font_size=12)
    return fig


def chart_spec(cid: str, title: str, subtitle: str, note: str, fig, csv_name: str) -> dict[str, Any]:
    return {
        "id": cid,
        "title": title,
        "subtitle": subtitle,
        "note": note,
        "fig": json.loads(fig.to_json()),
        "csv": csv_name,
    }


def _clean_json(o: Any) -> Any:
    if isinstance(o, float) and o != o:
        return None
    if isinstance(o, dict):
        return {k: _clean_json(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean_json(v) for v in o]
    return o


def dump_js(obj: Any) -> str:
    return json.dumps(_clean_json(obj), ensure_ascii=False, allow_nan=False, default=lambda _: None).replace("</", "<\\/")


def inline_katex_css(mod_root: Path) -> str:
    kcss = (mod_root / "katex/dist/katex.min.css").read_text(encoding="utf-8")

    def inline_font(m: re.Match) -> str:
        rel = m.group(1)
        fp = mod_root / "katex/dist" / rel
        if not fp.exists() or fp.suffix != ".woff2":
            return ""
        return f"url(data:font/woff2;base64,{base64.b64encode(fp.read_bytes()).decode()}) format(\"woff2\")"

    kcss = re.sub(r'url\((fonts/[^)]+\.woff2)\)\s*format\("woff2"\)', inline_font, kcss)
    kcss = re.sub(r',?\s*url\(fonts/[^)]+\.(?:woff|ttf)\)\s*format\("[^"]+"\)', "", kcss)
    return kcss


def convert_markdown_katex(md_text: str, work_dir: Path, node_exe: str | None = None) -> tuple[str, int, Path]:
    node = node_exe or shutil.which("node") or r"C:\Program Files\nodejs\node.EXE"
    tmp = work_dir / ".assembled_build.md"
    tmp.write_text(md_text, encoding="utf-8", newline="\n")
    try:
        proc = subprocess.run(
            [node, str(V3_REF / "convert_markdown.mjs"), str(tmp)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        tmp.unlink(missing_ok=True)
    if proc.returncode:
        raise RuntimeError(f"convert_markdown.mjs failed:\n{proc.stderr}")
    meta = json.loads(proc.stderr.strip().splitlines()[-1])
    return proc.stdout, int(meta["math"]), Path(meta["modRoot"])


def embedded_download_link(ev_dir: Path, filename: str) -> str:
    p = ev_dir / filename
    mime = "text/csv" if filename.endswith(".csv") else "application/json"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f'<a id="dl-{escape(filename.replace(".", "-"))}" href="data:{mime};base64,{b64}" download="{escape(filename)}">{escape(filename)} ↓</a>'


EXTRA_WIDGET_CSS = """
.dir-widget{margin:22px 0 26px;padding:16px 18px;background:#fafcfe;border:1px solid #cfd9e2;border-top:2px solid var(--navy)}
.dir-widget h4{font-family:'Arial Narrow','Segoe UI',sans-serif;font-size:20px;color:var(--deep);margin:0 0 6px;font-weight:650}
.dir-widget .dir-controls{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:10px 0 12px}
.dir-widget .dir-controls input{max-width:300px;min-height:34px;font-size:13px}
.dir-widget .dir-controls select{min-height:34px;font-size:13px}
.dir-widget .dir-meta{margin-left:auto;font-size:12px;color:#5a6976}
.dir-widget .dir-pager{display:flex;gap:8px;align-items:center;margin-top:10px;font-size:12px;color:#5a6976}
.dir-widget .dir-pager button{padding:4px 10px;font-size:12px}
.dir-widget table th{cursor:pointer;user-select:none}
.dir-widget table th:hover{background:#e1ebf3}
"""

COMMON_INTERACTIONS_JS = r"""
'use strict';
const $ = id => document.getElementById(id);
const PLOT_CFG = {responsive: true, displaylogo: false, modeBarButtonsToRemove: ['select2d', 'lasso2d', 'autoScale2d'], toImageButtonOptions: {format: 'png', scale: 2}};

function jump(id) {
  const el = $(id);
  if (!el) return;
  const d = el.closest('details');
  if (d) d.open = true;
  location.hash = id;
  el.scrollIntoView({behavior: 'smooth', block: 'start'});
}

function initNavigation() {
  const chapters = [...document.querySelectorAll('details.chapter')];
  if ($('expandChapters')) $('expandChapters').onclick = () => { chapters.forEach(d => d.open = true); window.dispatchEvent(new Event('resize')); };
  if ($('collapseChapters')) $('collapseChapters').onclick = () => chapters.forEach(d => d.open = false);
  if ($('printReport')) $('printReport').onclick = () => { chapters.forEach(d => d.open = true); window.print(); };
  chapters.forEach(d => d.addEventListener('toggle', () => { if (d.open) setTimeout(() => window.dispatchEvent(new Event('resize')), 60); }));
  document.querySelectorAll('a[href^="#"]').forEach(a => a.addEventListener('click', e => {
    const id = decodeURIComponent(a.hash.slice(1));
    if ($(id)) { e.preventDefault(); jump(id); }
  }));
  const index = chapters.map(d => ({id: d.querySelector('h2').id, title: d.querySelector('h2').textContent, text: d.textContent.toLowerCase()}));
  if ($('reportSearch')) {
    $('reportSearch').addEventListener('input', () => {
      const q = $('reportSearch').value.toLowerCase().trim();
      const found = q.length < 2 ? [] : index.filter(x => x.text.includes(q));
      const out = $('searchResults');
      out.replaceChildren();
      if (q.length >= 2) {
        const p = document.createElement('p');
        p.textContent = found.length + ' matching chapters';
        out.append(p);
        found.forEach(x => { const b = document.createElement('button'); b.textContent = x.title; b.onclick = () => jump(x.id); out.append(b); });
      }
    });
  }
  const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
      if (e.isIntersecting) document.querySelectorAll('.toc a').forEach(a => a.classList.toggle('active', a.hash === '#' + e.target.id));
    });
  }, {rootMargin: '-8% 0px -72% 0px'});
  document.querySelectorAll('h2[id]').forEach(h => observer.observe(h));
  if (location.hash) requestAnimationFrame(() => jump(decodeURIComponent(location.hash.slice(1))));
  window.addEventListener('beforeprint', () => chapters.forEach(d => d.open = true));
}

function initInlineCharts() {
  (typeof INLINE_CHARTS === 'undefined' ? [] : INLINE_CHARTS).forEach(c => {
    const el = $(c.id);
    if (el) Plotly.react(el, c.fig.data, {...c.fig.layout, autosize: true}, PLOT_CFG);
  });
}

function initDirectoryWidgets() {
  (typeof DIR_WIDGETS === 'undefined' ? [] : DIR_WIDGETS).forEach(w => {
    const root = $(w.id);
    if (!root) return;
    const searchEl = root.querySelector('.dir-search');
    const filterEl = root.querySelector('.dir-filter');
    const tbody = root.querySelector('tbody');
    const metaEl = root.querySelector('.dir-meta');
    const pageEl = root.querySelector('.dir-page-label');
    const prevBtn = root.querySelector('.dir-prev');
    const nextBtn = root.querySelector('.dir-next');
    const ths = [...root.querySelectorAll('thead th')];
    let sortCol = w.defaultSort || 0, sortAsc = Boolean(w.defaultAsc), page = 0;
    const pageSize = w.pageSize || 15;

    const esc = s => String(s == null ? '' : s).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    const fmtCell = (val, col) => {
      if (val === null || val === undefined || val === '') return '—';
      if (typeof val === 'number' && Number.isFinite(val)) {
        if (col.fmt === 'int') return Math.round(val).toLocaleString('en-AU');
        if (col.fmt === 'pct1') return (val * 100).toFixed(1) + '%';
        if (col.fmt === 'pct0') return Math.round(val * 100) + '%';
        if (col.fmt === 'aud0') return (val < 0 ? '−$' : '$') + Math.round(Math.abs(val)).toLocaleString('en-AU');
        if (col.fmt === 'aud2') return (val < 0 ? '−$' : '$') + Math.abs(val).toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2});
        if (col.fmt === 'f1') return val.toLocaleString('en-AU', {minimumFractionDigits: 1, maximumFractionDigits: 1});
        if (col.fmt === 'f2') return val.toLocaleString('en-AU', {minimumFractionDigits: 2, maximumFractionDigits: 2});
      }
      return esc(val);
    };

    function render() {
      const q = searchEl ? searchEl.value.trim().toLowerCase() : '';
      const fv = filterEl ? filterEl.value : 'ALL';
      let rows = w.rows.filter(r => {
        if (fv !== 'ALL' && w.filterKey && String(r[w.filterKey]) !== fv) return false;
        if (q && !w.cols.some(c => String(r[c.key] ?? '').toLowerCase().includes(q))) return false;
        return true;
      });
      const ck = w.cols[sortCol].key;
      rows.sort((a, b) => {
        const av = a[ck], bv = b[ck];
        if (typeof av === 'number' && typeof bv === 'number') return sortAsc ? av - bv : bv - av;
        return sortAsc ? String(av ?? '').localeCompare(String(bv ?? '')) : String(bv ?? '').localeCompare(String(av ?? ''));
      });
      const maxPage = Math.max(0, Math.ceil(rows.length / pageSize) - 1);
      if (page > maxPage) page = maxPage;
      const slice = rows.slice(page * pageSize, (page + 1) * pageSize);
      tbody.innerHTML = slice.map(r => '<tr>' + w.cols.map(c => '<td' + (c.num ? ' style="text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap"' : '') + '>' + fmtCell(r[c.key], c) + '</td>').join('') + '</tr>').join('');
      if (metaEl) metaEl.textContent = rows.length.toLocaleString('en-AU') + ' matching rows';
      if (pageEl) pageEl.textContent = 'Page ' + (page + 1) + ' of ' + (maxPage + 1);
      if (prevBtn) prevBtn.disabled = page <= 0;
      if (nextBtn) nextBtn.disabled = page >= maxPage;
    }

    ths.forEach((th, idx) => th.addEventListener('click', () => {
      if (sortCol === idx) sortAsc = !sortAsc; else { sortCol = idx; sortAsc = false; }
      render();
    }));
    if (searchEl) searchEl.addEventListener('input', () => { page = 0; render(); });
    if (filterEl) filterEl.addEventListener('change', () => { page = 0; render(); });
    if (prevBtn) prevBtn.addEventListener('click', () => { if (page > 0) { page--; render(); } });
    if (nextBtn) nextBtn.addEventListener('click', () => { page++; render(); });
    render();
  });
}

window.addEventListener('load', () => {
  initInlineCharts();
  initDirectoryWidgets();
  if (typeof window.initCustomLabs === 'function') window.initCustomLabs();
  initNavigation();
  document.documentElement.classList.add('ready');
});
"""


def build_directory_widget_html(widget_id: str, kicker: str, title: str, dek: str, cols: list[dict], filter_label: str = "", filter_options: list[str] | None = None, csv_name: str = "") -> str:
    flt = ""
    if filter_options:
        opts = '<option value="ALL">All (' + escape(filter_label or "group") + ")</option>" + "".join(
            f'<option value="{escape(o)}">{escape(o)}</option>' for o in filter_options
        )
        flt = f'<select class="dir-filter" aria-label="Filter table">{opts}</select>'
    dl = f' · <a href="#dl-{escape(csv_name.replace(".", "-"))}">Download full CSV ↓</a>' if csv_name else ""
    r_style = ' style="text-align:right"'
    headers = "".join(f'<th{r_style if c.get("num") else ""}>{escape(c["label"])} ↕</th>' for c in cols)
    return (
        f'<div id="{escape(widget_id)}" class="dir-widget">'
        f'<div class="section-kicker">{escape(kicker)}</div>'
        f"<h4>{escape(title)}</h4>"
        f'<p class="small-note" style="margin:0 0 8px">{escape(dek)}{dl}</p>'
        f'<div class="dir-controls"><input class="dir-search" type="search" placeholder="Search unit, constraint, corridor..." autocomplete="off">{flt}<span class="dir-meta"></span></div>'
        f'<div class="table-wrap" style="margin:8px 0"><table><thead><tr>{headers}</tr></thead><tbody></tbody></table></div>'
        f'<div class="dir-pager"><button type="button" class="dir-prev">← Previous</button><button type="button" class="dir-next">Next →</button><span class="dir-page-label"></span></div>'
        f"</div>"
    )


def assemble_flagship_html(
    *,
    report_dir: Path,
    output_html_name: str,
    page_title: str,
    brand_sub: str,
    dateline_top: str,
    dateline_bottom: str,
    hero_kicker: str,
    hero_title: str,
    hero_accent: str,
    nav_links: list[tuple[str, str]],
    summary_bullets_html: list[str],
    brief_items: list[tuple[str, str]],
    dual_paths: tuple[tuple[str, str], tuple[str, str]],
    chapter_order: list[str],
    part_map: dict[str, tuple[str, str, str]],
    headline_numbers: dict[str, Any],
    charts_map: dict[str, dict],
    diagrams_map: dict[str, str],
    widgets_html_map: dict[str, str],
    directory_widgets_data: list[dict],
    download_files: list[str],
    footer_left: str,
    footer_right: str,
    extra_js: str = "",
    code_files_for_manifest: list[Path] | None = None,
) -> dict[str, Any]:
    """Assemble modular Virtual Barrels chapters into unified Markdown + self-contained offline HTML + manifest."""
    ev_dir = report_dir / "evidence"
    raw_parts = []
    for rel in chapter_order:
        p = report_dir / rel
        text = p.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        if rel in part_map:
            kicker, title, dek = part_map[rel]
            raw_parts.append(f"{{{{part:{kicker}||{title}||{dek}}}}}\n\n" + text)
        else:
            raw_parts.append(text)
    front_md = (report_dir / "chapters/00_front.md").read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    full_tpl = front_md + "\n\n" + "\n\n".join(raw_parts) + "\n"

    tokens = set(re.findall(r"\{\{([a-zA-Z0-9_]+)\}\}", full_tpl))
    missing = sorted(tokens - set(headline_numbers))
    if missing:
        raise SystemExit(f"Unfilled numeric placeholders in {report_dir.name}: {missing}")
    assembled = re.sub(r"\{\{([a-zA-Z0-9_]+)\}\}", lambda m: str(headline_numbers[m.group(1)]), full_tpl)

    clean_md = re.sub(r"^\{\{(?:exhibit|diagram|interactive|part):[^}]+\}\}\n*", "", assembled, flags=re.M)
    clean_md = re.sub(r"\n{3,}", "\n\n", clean_md)
    (report_dir / "research_report.md").write_text(clean_md, encoding="utf-8", newline="\n")

    html_frag, math_count, mod_root = convert_markdown_katex(assembled, report_dir)
    soup = BeautifulSoup(html_frag, "html.parser")
    if soup.h1:
        soup.h1.decompose()

    used_charts = []

    def chart_html(cid: str) -> str:
        c = charts_map[cid]
        used_charts.append(c)
        link = f'<span class="figure-links"><a href="#dl-{escape(c["csv"].replace(".", "-"))}">Data ↓</a></span>'
        return (
            f'<figure id="fig-{c["id"]}" class="inline-exhibit">'
            f'<figcaption><span>{escape(c["title"])}</span>{link}</figcaption>'
            f'<p class="exhibit-sub">{escape(c["subtitle"])}</p>'
            f'<div class="chart-scroll"><div id="{c["id"]}" class="plot" role="img" aria-label="{escape(c["title"])}"></div></div>'
            f'<p class="figure-note">{escape(c["note"])}</p></figure>'
        )

    for slot in list(soup.find_all("div", class_="embed-slot")):
        kind = slot["data-kind"]
        arg = slot["data-arg"]
        if kind == "exhibit":
            frag = BeautifulSoup(chart_html(arg), "html.parser")
        elif kind == "diagram":
            frag = BeautifulSoup(diagrams_map[arg], "html.parser")
        elif kind == "interactive":
            frag = BeautifulSoup(widgets_html_map[arg], "html.parser")
        elif kind == "part":
            kicker, title, dek = arg.split("||", 2)
            part_html = (
                f'<div class="part-banner" data-part-kicker="{escape(kicker)}">'
                f'<div class="part-kicker">{escape(kicker)}</div>'
                f"<h2>{escape(title)}</h2><p>{escape(dek)}</p></div>"
            )
            frag = BeautifulSoup(part_html, "html.parser")
        else:
            raise SystemExit(f"Unknown embed directive: {kind}:{arg}")
        slot.replace_with(frag)

    toc = []
    chap_idx = 0
    for h in soup.find_all("h2"):
        if h.find_parent(class_="part-banner"):
            kicker = h.find_parent(class_="part-banner").get("data-part-kicker", "")
            toc.append(("__part__", kicker))
            continue
        h["id"] = f"chapter-{chap_idx}"
        toc.append((h["id"], h.get_text()))
        chap_idx += 1
    for i, h in enumerate(soup.find_all("h3")):
        h["id"] = f"subsection-{i}"

    # Citation anchor linking ([S01], [R1], [L01])
    for p in soup.find_all("p"):
        m = re.match(r"^\[([SLR]\d{1,2})\]", p.get_text())
        if m:
            p["id"] = "source-" + m.group(1)
            p["class"] = "source-entry"
    for node in list(soup.find_all(string=True)):
        if node.parent.name in ("a", "code", "pre", "script", "style", "annotation") or node.find_parent(class_="katex"):
            continue
        if node.parent.get("class") == ["source-entry"]:
            continue
        ms = list(re.finditer(r"\[([SLR]\d{1,2})((?:(?:[–-]|, )[SLR]?\d{1,2})*)\]", str(node)))
        if not ms:
            continue
        start = 0
        for m in ms:
            node.insert_before(NavigableString(str(node)[start : m.start()]))
            a = soup.new_tag("a", href="#source-" + m.group(1))
            a["class"] = "citation"
            a.string = m.group(0)
            node.insert_before(a)
            start = m.end()
        node.insert_before(NavigableString(str(node)[start:]))
        node.extract()

    # Wrap tables in .table-wrap
    for t in soup.find_all("table"):
        if t.find_parent(class_="table-wrap") or t.find_parent(class_="dir-widget"):
            continue
        w = soup.new_tag("div", **{"class": "table-wrap", "tabindex": "0"})
        t.wrap(w)

    # Group each h2 chapter into collapsible <details class="chapter" open>
    top_nodes = list(soup.children)
    grouped = BeautifulSoup("", "html.parser")
    cur_details = None
    cur_content = None
    for el in top_nodes:
        if getattr(el, "name", None) == "div" and "part-banner" in (el.get("class") or []):
            cur_details = None
            cur_content = None
            grouped.append(el)
        elif getattr(el, "name", None) == "h2" and el.get("id", "").startswith("chapter-"):
            det = grouped.new_tag("details", **{"class": "chapter", "open": ""})
            summ = grouped.new_tag("summary")
            summ.append(el)
            det.append(summ)
            body_div = grouped.new_tag("div", **{"class": "chapter-content"})
            det.append(body_div)
            grouped.append(det)
            cur_details = det
            cur_content = body_div
        else:
            if cur_content is not None:
                cur_content.append(el)
            else:
                grouped.append(el)

    research_html = str(grouped)
    toc_html = "".join(
        f'<a class="toc-part" tabindex="-1">{escape(t)}</a>' if i == "__part__" else f'<a href="#{i}">{escape(t)}</a>'
        for i, t in toc
    )
    nav_html = "".join(f'<a href="{escape(href)}">{escape(label)}</a>' for href, label in nav_links)
    bullets_html = "".join(f"<li>{b}</li>" for b in summary_bullets_html)
    brief_html = "".join(f"<p><strong>{escape(k)}</strong><br>{v}</p>" for k, v in brief_items)
    dl_html = "".join(embedded_download_link(ev_dir, f) for f in download_files if (ev_dir / f).exists())

    body = f"""
<div id="top" class="masthead"><div class="brand"><strong>IC Flow<br>Forecasting</strong><span>{brand_sub}</span></div><div class="dateline">{escape(dateline_top)}<br>{escape(dateline_bottom)}</div></div>
<div class="hero-band"><header><div class="eyebrow">{escape(hero_kicker)}</div><h1>{escape(hero_title)}<br><span>{escape(hero_accent)}</span></h1></header></div>
<nav class="topnav" aria-label="Report navigation">
  {nav_html}
  <button id="printReport" type="button">Print / save PDF</button>
</nav>
<div class="front">
  <div><ul class="summary-points">{bullets_html}</ul></div>
  <aside class="research-note"><h3>Research brief</h3>{brief_html}</aside>
</div>
<div class="dual-paths">
  <div><strong>{escape(dual_paths[0][0])}</strong><p>{dual_paths[0][1]}</p></div>
  <div><strong>{escape(dual_paths[1][0])}</strong><p>{dual_paths[1][1]}</p></div>
</div>
<div class="reading-intro" id="fullResearch">
  <div><div class="section-kicker">Complete mechanics-first analysis</div><h2>Structured research chapters and technical appendices</h2></div>
  <div class="reading-actions"><button id="expandChapters" type="button">Expand all</button><button id="collapseChapters" type="button">Collapse all</button></div>
</div>
<p class="small-note">{chap_idx} chapters and appendices · {len(used_charts)} inline Plotly exhibits · {len(diagrams_map)} structural diagrams · {len(directory_widgets_data)} interactive lookup tables · {math_count} KaTeX formulas · every statistic bound to audited CSVs.</p>
<div class="reading-layout">
  <article class="research-body">{research_html}</article>
  <aside class="research-rail" aria-label="Research navigation">
    <div class="rail-label">Reading guide</div>
    <label class="sr-only" for="reportSearch">Search the report</label>
    <input id="reportSearch" type="search" placeholder="Search topic, link, or constraint" autocomplete="off">
    <div id="searchResults" aria-live="polite"></div>
    <nav class="toc">{toc_html}</nav>
  </aside>
</div>
<section class="downloads" id="downloads">
  <h2>Research data and reproducibility</h2>
  <p class="small-note">Every exhibit and directory dataset is embedded offline below for direct inspection and audit.</p>
  <div class="download-grid">{dl_html}</div>
</section>
<footer class="footer">
  <span>{footer_left}</span>
  <span>{footer_right}</span>
</footer>
<a class="back-top" href="#top" aria-label="Back to top">↑ Top</a>
"""

    base_css = (V3_REF / "report.css").read_text(encoding="utf-8") + "\n:root{--accent:#4c94df}"
    inst_css = (V3_REF / "institutional.css").read_text(encoding="utf-8") + "\n" + EXTRA_WIDGET_CSS
    kcss = inline_katex_css(mod_root)
    from plotly.offline import get_plotlyjs

    runtime = (
        f'<script>const INLINE_CHARTS={dump_js([{"id": c["id"], "fig": c["fig"]} for c in used_charts])};'
        f"const DIR_WIDGETS={dump_js(directory_widgets_data)};</script>"
        f"<script>{COMMON_INTERACTIONS_JS}\n{extra_js}</script>"
    )
    full_html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="icon" href="data:,">'
        f"<title>{escape(page_title)}</title>"
        f"<style>{base_css}</style><style>{kcss}</style><style>{inst_css}</style>"
        f"<script>{get_plotlyjs()}</script></head>"
        f"<body><main>{body}</main>{runtime}</body></html>"
    )
    out_path = report_dir / output_html_name
    out_path.write_text(full_html, encoding="utf-8", newline="\n")

    words_md = len(re.findall(r"\b\w+\b", clean_md))
    manifest = {
        "editorial_standard": "virtual-barrels-analysis",
        "output": output_html_name,
        "output_sha256": sha256_file(out_path),
        "bytes": out_path.stat().st_size,
        "chapters_and_appendices": chap_idx,
        "katex_formulas": math_count,
        "inline_plotly_exhibits": len(used_charts),
        "diagrams": len(diagrams_map),
        "directory_widgets": len(directory_widgets_data),
        "words_md": words_md,
        "hash_convention": "SHA-256 of file bytes with CRLF normalised to LF for text files",
        "evidence_sha256": {p.name: sha256_file(p) for p in sorted(ev_dir.glob("*")) if p.is_file()},
        "code_sha256": {
            p.relative_to(ROOT).as_posix(): sha256_file(p)
            for p in (code_files_for_manifest or [])
            if p.exists()
        },
        "dependencies": {"plotly": plotly.__version__, "katex": "0.16.22", "marked": "15.0.12"},
    }
    (report_dir / "report_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    return manifest
