"""Verify EnergyConnect report hashes, links and offline browser layouts."""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown

from . import report as generator
from .report import file_digest


class ReportLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors = set()
        self.duplicate_anchors = set()
        self.links = []
        self.resources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if anchor := attrs.get("id"):
            if anchor in self.anchors:
                self.duplicate_anchors.add(anchor)
            self.anchors.add(anchor)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        if tag in {"iframe", "img", "script", "source"} and attrs.get("src"):
            self.resources.append(attrs["src"])
        if tag == "link" and attrs.get("rel") in {"stylesheet", "icon"}:
            self.resources.append(attrs["href"])


def check_links(path: Path, source: str, embedded: bool) -> int:
    parser = ReportLinks()
    parser.feed(source)
    if parser.duplicate_anchors:
        raise ValueError(f"Duplicate report anchors {sorted(parser.duplicate_anchors)}")
    if embedded and any(not resource.startswith("data:") for resource in parser.resources):
        raise ValueError("HTML report rendering requires an external resource.")
    for url in parser.links + parser.resources:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            continue
        if parts.path and not (path.parent / unquote(parts.path)).is_file():
            raise ValueError(f"Broken report link {url}")
        if not parts.path and parts.fragment and unquote(parts.fragment) not in parser.anchors:
            raise ValueError(f"Broken report anchor {url}")
    return len(parser.links)


def validate(output_dir: Path, data_dir: Path) -> dict:
    manifest = json.loads((output_dir / "report_manifest.json").read_text(encoding="utf-8"))
    checks = manifest["artifacts"]
    for name, digest in checks.items():
        if file_digest(output_dir / name) != digest:
            raise ValueError(f"Report artifact hash differs for {name}")
    if file_digest(data_dir / "half_hour.parquet") != manifest["half_hour_sha256"]:
        raise ValueError("Half-hour evidence differs from the report input hash.")
    forecast_inputs = manifest.get("local_forecast_inputs", {})
    for name, digest in forecast_inputs.items():
        if file_digest(data_dir / name) != digest:
            raise ValueError(f"Forecast row evidence hash differs for {name}.")
    if file_digest(Path(generator.__file__)) != manifest["generator_sha256"]:
        raise ValueError("The report generator differs from the build manifest.")
    theme = Path(generator.__file__).resolve().parents[3] / "scripts" / "report_theme"
    for name, digest in manifest["theme"].items():
        if file_digest(theme / name) != digest:
            raise ValueError(f"The report theme hash differs for {name}.")
    report = output_dir / "index.html"
    md = output_dir / "report.md"
    return {
        "verified_hashes": len(checks) + len(manifest["theme"]) + len(forecast_inputs) + 2,
        "html_links": check_links(report, report.read_text(encoding="utf-8"), embedded=True),
        "markdown_links": check_links(md, markdown.markdown(md.read_text(encoding="utf-8")), embedded=False),
    }


def browser_check(output_dir: Path, executable: str | None) -> dict:
    from playwright.sync_api import sync_playwright

    report = output_dir / "index.html"
    qa = output_dir / "qa"
    qa.mkdir(exist_ok=True)
    views = {}
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, executable_path=executable)
        for label, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
            context = browser.new_context(viewport={"width": width, "height": height}, offline=True, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(15_000)
            errors, external = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: external.append(request.url) if request.url.startswith(("http:", "https:")) else None)
            page.goto(report.resolve().as_uri(), wait_until="load")
            page.wait_for_function("Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)")
            images = page.locator("figure img").count()
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            if overflow or errors or external or not images:
                raise ValueError(f"Report browser check failed at {label} width with overflow={overflow}, errors={errors}, "
                                 f"requests={external} and images={images}.")
            page.screenshot(path=qa / f"report_{label}.png")
            page.locator("figure").first.screenshot(path=qa / f"report_{label}_chart.png")
            page.locator("nav a[href='#forecast']").click()
            if not page.url.endswith("#forecast"):
                raise ValueError(f"Forecast anchor did not activate at {label} width.")
            forecast_tables = page.locator("#forecast .table-wrap")
            dense = forecast_tables.filter(has=page.get_by_role("columnheader", name="Matched rows", exact=True))
            (dense.first if dense.count() else forecast_tables.first).screenshot(path=qa / f"report_{label}_table.png")
            page.locator("#evidence").evaluate("element => element.scrollIntoView({block:'start',behavior:'instant'})")
            page.screenshot(path=qa / f"report_{label}_methods.png")
            with page.expect_download() as download:
                page.locator("figure a[download]").first.click()
            if file_digest(Path(download.value.path())) != file_digest(output_dir / "downloads" / "half_hour_limits.csv"):
                raise ValueError(f"Browser downloaded the wrong half-hour data at {label} width.")
            views[label] = {"width": width, "height": height, "images": images, "external_requests": external,
                            "page_errors": errors, "document_overflow": overflow, "half_hour_download_verified": True}
            context.close()
        version = browser.version
        browser.close()
    screenshots = {path.name: file_digest(path) for path in sorted(qa.glob("report_*.png"))}
    return {"browser": version, "views": views, "offline": True, "screenshots": screenshots}


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--data-dir", type=Path, default=Path("data/pec_limits_v1"))
    cli.add_argument("--out", type=Path, default=Path("local_exports/pec_limits_v1"))
    cli.add_argument("--browser", action="store_true", help="Check offline layouts and downloads with Playwright.")
    cli.add_argument("--executable", help="Path to an existing Chromium executable.")
    args = cli.parse_args()
    result = validate(args.out, args.data_dir)
    if args.browser:
        result.update(browser_check(args.out, args.executable))
    result["report_sha256"] = file_digest(args.out / "index.html")
    print(json.dumps(result, indent=2))
    qa = args.out / "qa"
    qa.mkdir(exist_ok=True)
    (qa / "report_checks.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
