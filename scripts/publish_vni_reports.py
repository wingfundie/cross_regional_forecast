"""Copy the validated VNI report suite into the Git-tracked reports area."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
def report_files(slug: str):
    return (
    "index.html",
    f"{slug}_research_paper.html",
    "pages/01_model_performance.html",
    "pages/02_model_explorer.html",
    "pages/03_feature_fundamentals.html",
    "pages/04_nos_outages.html",
    "pages/05_risk_and_refinements.html",
    "pages/06_model_handoff.html",
    f"full_run/{slug}_diurnal_nos_model_report.html",
    "full_run/nos_outage_impact_analysis.html",
    "downloads/model_results.csv",
    "downloads/artifact_catalog.csv",
    "downloads/source_build.json",
    "downloads/nos_impact_build.json",
    "downloads/research_performance.csv",
    "downloads/research_feature_importance.csv",
    "downloads/research_shap_importance.csv",
    "downloads/research_paper_build.json",
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def publish(name='VNI', campaign='vni_diurnal_nos_v2', build_script='build_vni_report_suite.py', publish_script='publish_vni_reports.py') -> Path:
    slug=name.lower();source_root=ROOT/'data/forecast_experiments'/campaign/'report';destination_root=ROOT/'reports'/campaign
    files=report_files(slug)
    missing = [relative for relative in files if not (source_root / relative).exists()]
    if missing:
        raise FileNotFoundError(f"Build the local report suite first; missing: {missing}")
    for relative in files:
        source = source_root / relative
        destination = destination_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if destination.suffix == ".html":
            rendered = destination.read_text(encoding="utf-8")
            destination.write_text("\n".join(line.rstrip() for line in rendered.splitlines()) + "\n", encoding="utf-8")

    # The local report centre links to ignored model binaries.  The published
    # version links to the tracked saved-model guide instead.
    index = destination_root / "index.html"
    text = index.read_text(encoding="utf-8")
    text = text.replace('../final/catalogue.json', f'../../docs/{name}_SAVED_MODEL_GUIDE.md')
    text = text.replace(f'../../../../docs/{name}_SAVED_MODEL_GUIDE.md', f'../../docs/{name}_SAVED_MODEL_GUIDE.md')
    text = text.replace('report_suite_manifest.json', 'published_manifest.json')
    index.write_text(text, encoding="utf-8")
    (destination_root / "report_suite_manifest.json").unlink(missing_ok=True)

    published = [destination_root / relative for relative in files]
    for path in published:
        if path.stat().st_size >= 95 * 1024 * 1024:
            raise ValueError(f"Published report exceeds the 95 MiB repository limit: {path}")
        if path.suffix == ".html" and "C:\\Users\\" in path.read_text(encoding="utf-8"):
            raise ValueError(f"Published report contains an absolute Windows user path: {path}")

    manifest = {
        "study": campaign,
        "source": "validated cached run reports",
        "rebuild": f"python scripts/{build_script}",
        "publish": f"python scripts/{publish_script}",
        "files": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in published
        ],
    }
    (destination_root / "published_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (destination_root / "README.md").write_text(
        f"# Published {name} diurnal and NOS reports\n\n"
        f"Open [`{slug}_research_paper.html`]({slug}_research_paper.html) for the full research paper or "
        "[`index.html`](index.html) for the report centre. The focused pages split model performance, "
        "the model explorer, feature fundamentals, NOS outages, risk/refinements and the trained-model handoff. "
        "`full_run/` contains the complete report and matched NOS impact report.\n\n"
        "These files are rendered from the completed cached run. Rebuild locally with "
        f"`python scripts/{build_script}`, then refresh this tracked copy with "
        f"`python scripts/{publish_script}`.\n",
        encoding="utf-8",
    )
    return index


if __name__ == "__main__":
    print(publish())
