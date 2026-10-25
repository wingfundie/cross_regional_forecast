"""Render the tutorial from executed package examples; never fits research models."""
from __future__ import annotations
import argparse
import base64
from datetime import datetime, timezone
import hashlib
from html import escape
import json
from pathlib import Path
import re
import shutil
import sys
import zipfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import markdown
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/report_theme"))
from report_theme import hero, metric, render_page, matplotlib_style


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(results, output):
    results, output = Path(results), Path(output)
    downloads, figures = output / "downloads", output / "figures"
    downloads.mkdir(parents=True, exist_ok=True)
    figures.mkdir(exist_ok=True)
    summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["directional_results"]) == 2
    frame = pd.DataFrame(summary["directional_results"])
    assert frame.p50_mw.notna().all() and (frame.analogue_days > 0).all()
    for p in results.iterdir():
        if p.is_file():
            shutil.copy2(p, downloads / p.name)
    sources = [ROOT / "docs/CONDITIONAL_REGIMES_PYTHON_TUTORIAL.md",
               ROOT / "packages/nemic-regimes/examples/tutorial.py",
               ROOT / "packages/nemic-regimes/dist/nemic_regimes-0.1.0-py3-none-any.whl",
               ROOT / "packages/nemic-regimes/requirements-bundle-v1.txt",
               ROOT / "data/forecast_experiments/conditional_regimes_v1/nemic_regimes_bundle_v1.zip",
               ROOT / "execution/conditional_regimes_v1/RUNBOOK_PYTHON.md"]
    for p in sources[1:]:
        shutil.copy2(p, downloads / p.name)
    plt.rcParams.update(matplotlib_style())
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), sharex=True)
    support_rows = []
    for direction, title, color, ax in zip(("forward", "reverse"), ("NSW → QLD", "QLD → NSW"),
                                          ("#5696b9", "#8370b4"), axes):
        profile = pd.read_csv(results / f"{direction}_profile.csv")
        assert len(profile) == 48 and profile.half_hour.tolist() == list(range(48))
        counts = profile.status.value_counts()
        support_rows.append({"Direction": title, "Supported periods": int(counts.get("supported_table", 0)),
                             "Indicative periods": int(counts.get("indicative_table", 0)), "Unavailable periods": int(counts.get("unavailable", 0))})
        x = profile.half_hour.to_numpy() / 2
        ax.fill_between(x, profile.p10_mw.to_numpy(), profile.p90_mw.to_numpy(), color=color, alpha=.2, label="P10–P90")
        ax.plot(x, profile.p50_mw.to_numpy(), color=color, label="P50")
        indicative = profile.status.ne("supported_table")
        if indicative.any():
            ax.scatter(x[indicative], profile.loc[indicative, "p50_mw"], color="#ce9a48", s=20, zorder=4, label="Indicative support")
        ax.axhline(0, color="#66717e", lw=.8)
        ax.set(title=title, xlabel="Interval-ending hour · NEM UTC+10", ylabel="Reported directional limit MW", xticks=[0, 6, 12, 18, 23])
        ax.legend(loc="best")
    fig.suptitle("QNI · Q1 · fixed warm-NSW / high-QLD-residual assumptions", y=1.02, fontsize=13)
    fig.tight_layout()
    figure_path = figures / "directional_profiles.png"
    fig.savefig(figure_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    displayed = frame[["direction", "p10_mw", "p50_mw", "p90_mw", "analogue_days", "status"]].copy()
    displayed["direction"] = ["NSW → QLD", "QLD → NSW"]
    displayed.columns = ["Direction", "P10 MW", "P50 MW", "P90 MW", "Independent days", "Status"]
    for c in ("P10 MW", "P50 MW", "P90 MW"):
        displayed[c] = displayed[c].map(lambda v: f"{v:,.1f}")
    result_table = displayed.to_markdown(index=False)
    worked = ("### Actual output from the worked example\n\n"
              "These values were produced by the downloadable script, rather than typed as illustrative estimates. "
              "Both directions use the same 69 qualifying days for the same physical conditions at 18:30 in Q1. "
              "The source/sink field names differ because the direction changes.\n\n" + result_table + "\n\n"
              "The negative forward P10 is preserved. It records a restrictive/forced-flow side of this conditional distribution, "
              f"not {abs(float(frame.p10_mw.iat[0])):,.1f} MW of positive export capability.\n\n"
              "![Two directional profiles](figures/directional_profiles.png)\n\n"
              "Each profile holds the supplied regional assumptions fixed across the day. Gold markers identify indicative cells, and gaps mean unavailable, not zero. The two plots have independent vertical scales. "
              "Source: the identified saved bundle; strict conditional tables, quarter 1.\n\n"
              "Support changes with the ending period. The warm-NSW condition is uncommon overnight, so the supported 18:30 result does not imply a supported full-day curve.\n\n" + pd.DataFrame(support_rows).to_markdown(index=False) + "\n\n")
    source = sources[0].read_text(encoding="utf-8")
    # Derive counts in the prose as well as the result table.
    if frame.analogue_days.nunique() == 1:
        worked = worked.replace("69 qualifying days", f"{int(frame.analogue_days.iat[0])} qualifying days")
    else:
        worked = worked.replace("Both directions use the same 69 qualifying days", "The table reports each direction's qualifying days")
    companion = source.replace("<!-- WORKED_RESULTS -->", worked)
    (output / "tutorial.md").write_text(companion, encoding="utf-8")
    body = markdown.markdown(companion, extensions=["tables", "fenced_code", "toc"], output_format="html")
    body = re.sub(r"<h1\b[^>]*>.*?</h1>", "", body, count=1, flags=re.S)
    body = body.replace("<table>", '<div class="table-wrap" tabindex="0"><table>').replace("</table>", "</table></div>")
    encoded = base64.b64encode(figure_path.read_bytes()).decode()
    body = body.replace('src="figures/directional_profiles.png"', f'src="data:image/png;base64,{encoded}"')
    body = re.sub(r"<p>(<img[^>]+>)</p>", r'<figure><figcaption>Two directions · the same physical assumptions</figcaption><div class="chart-scroll tutorial-chart">\1</div></figure>', body)
    navigation = '<nav class="section-nav"><a href="#1-install-and-find-the-bundle">Install</a><a href="#5-add-the-conditions-you-mean">One interval</a><a href="#6-ask-for-the-reverse-limit-for-the-same-grid-state">Both directions</a><a href="#11-full-input-reference">Input reference</a><a href="tutorial.md">Markdown copy</a><a href="downloads/tutorial.py" download>Runnable example</a></nav>'
    heading = hero("INTERFLOW · Python tutorial", "Specify the conditions.", "Read the directional limits.",
                   "A runnable guide to loading the bundle, mapping inputs, selecting an interval and inspecting its evidence.",
                   ["nemic-regimes 0.1.0", "Q1–Q4 · six links", "Snapshot " + summary["training_cutoff"] + " NEM"])
    cards = '<div class="metrics">' + ''.join(metric(*x) for x in [
        ("Start here", "1 interval", "An explicit quarter and ending half-hour"),
        ("Two directions", "Same grid", "Source/sink assumptions remapped"),
        ("Returned range", "P10 / P50 / P90", "Signed reported limits, in MW"),
        ("Whole profile", "48 periods", "Or varying inputs in a batch")]) + '</div>'
    styles = '<style>pre{padding:20px;background:#ececf3;border:1px solid #dfe3eb;border-radius:8px;white-space:pre;overflow:auto;max-width:100%;line-height:1.6}pre code{background:transparent;padding:0;font-size:13px;overflow-wrap:normal}h2{margin-top:52px}h3{margin-top:30px}img{max-width:100%;height:auto}.tutorial-chart{overflow:auto}.tutorial-chart img{min-width:900px;max-width:none;width:100%;display:block}.metric strong{font-size:27px}p code,li code{word-break:break-word}</style>'
    (output / "index.html").write_text(render_page("Python package tutorial · conditional directional limits", styles + heading + navigation + cards + body, plotly=False), encoding="utf-8")
    manifest = {"schema": 1, "built": datetime.now(timezone.utc).isoformat(), "bundle_id": summary["bundle_id"],
                "snapshot_cutoff": summary["training_cutoff"], "inputs": {str(p.relative_to(ROOT)): digest(p) for p in
                    sources + [Path(__file__), ROOT / "scripts/report_theme/report_theme.py", ROOT / "scripts/report_theme/report.css"] + list(results.glob("*")) if p.is_file()},
                "files": {str(p.relative_to(output)).replace("\\", "/"): digest(p) for p in output.rglob("*")
                          if p.is_file() and p.name not in {"build_manifest.json", "tutorial.zip", "verification.json"} and "qa" not in p.relative_to(output).parts},
                "rebuild": "python scripts/build_conditional_regimes_tutorial.py",
                "examples": "python tutorial.py --bundle regime_bundle --output my_outputs --models"}
    (output / "build_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"html": str(output / "index.html"), "markdown": str(output / "tutorial.md"), "bundle_id": summary["bundle_id"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "data/forecast_experiments/conditional_regimes_tutorial/example_outputs")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/conditional_regimes_tutorial")
    args = parser.parse_args()
    build(args.results, args.output)
