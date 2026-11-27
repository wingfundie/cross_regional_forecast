"""Check evidence joins and offline views, and record hashes of the reviewed package."""
import hashlib
import importlib.metadata
import json
import os
import threading
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/rhs_replay"
RAW = ROOT / "data/rhs_replay"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_numbers():
    cases = pd.read_csv(OUT / "cases/replay.csv")
    group = ["equation", "interval_end"]
    assert len(cases) == 216 and not cases.duplicated(group).any()
    assert (cases.groupby(["equation","window"]).size() == 24).all()
    assert (cases.invoked & ~cases.blocked & cases.intervention.eq(0) & cases.runno.eq(1)).all()
    terms = pd.read_csv(OUT / "cases/terms.csv")
    final = terms[terms.expression == terms.equation].groupby(group).tail(1).set_index(group)
    original = cases.set_index(group).sort_index()
    np.testing.assert_allclose(final.accumulator.reindex(original.index), original.rhs_replay, rtol=0, atol=1e-8)
    assert np.isfinite(original[["rhs_reference","rhs_replay","rhs_case","lhs","marginal_value","violation"]]).all().all()
    direct = original.loc["DATASNAP_DFS_NSYD"]
    np.testing.assert_allclose(direct.rhs_replay, 10000 + direct.demand_mw, rtol=0, atol=1e-8)
    np.testing.assert_allclose(original.rhs_case, original.rhs_reference, rtol=0, atol=1e-5)
    np.testing.assert_allclose(original.rhs_replay, original.rhs_reference, rtol=0, atol=1e-5)
    data = pd.read_csv(OUT / "proxies/interval_results.csv")
    assert len(data) == 288 and not data.duplicated(group + ["method"]).any()
    for _, g in data.groupby(["equation","method"]):
        tune = g[g.window.eq("W2")]
        assert np.allclose(g.band_mw, tune.rhs_error.abs().max())
        assert (pd.to_datetime(g.producer_time) <= pd.to_datetime(g.cutoff)).all()
        assert (pd.to_datetime(g.source_interval_end) < pd.to_datetime(g.interval_end)).all()
    snapshot = json.loads((OUT / "inventory/summary.json").read_text())
    inv = pd.read_csv(OUT / "inventory/inputs.csv", keep_default_na=False)
    eqs = pd.read_csv(OUT / "inventory/equations.csv", keep_default_na=False)
    assert len(eqs) == snapshot["active_in_period"] and eqs.equation.is_unique
    assert len(inv) == snapshot["external_input_count"] and not inv.duplicated(["spd_type","spd_id"]).any()
    return dict(replay_rows=len(cases), proxy_rows=len(data), unique_points=len(inv),
                period_equations=len(eqs), max_replay_error_mw=float((original.rhs_replay-original.rhs_reference).abs().max()))


def verify_visuals():
    path = OUT / "index.html"
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    ids = [node["id"] for node in soup.select("[id]")]
    assert len(set(ids)) == len(ids)
    for a in soup.select("a[href]"):
        link = urlsplit(a["href"])
        if link.scheme:
            continue
        if link.path and link.path != "manifest.json":
            assert (OUT / unquote(link.path)).is_file(), link.path
        if not link.path and link.fragment:
            assert link.fragment in ids
    report = {}
    qa = RAW / "visual_checks"
    qa.mkdir(parents=True, exist_ok=True)
    browser_temp = RAW / "browser_temp"
    browser_temp.mkdir(exist_ok=True)
    os.environ.update(TEMP=str(browser_temp), TMP=str(browser_temp), TMPDIR=str(browser_temp))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for width, height in [(1366, 860), (390, 844)]:
            page = browser.new_page(viewport={"width":width,"height":height}, offline=True,
                                    reduced_motion="reduce")
            errors, remote = [], []
            page.on("pageerror",lambda e: errors.append(str(e)))
            page.on("request",lambda req: remote.append(req.url) if req.url.startswith(("http:","https:")) else None)
            page.goto(path.as_uri())
            page.locator("#lookup").fill("TERRANORA_LOAD")
            assert page.locator("#leaves").get_by_text("TERRANORA_LOAD",exact=True).is_visible()
            page.locator("#lookup").fill("N::Q_NIL_KC")
            assert page.locator("#leaves tr").count() > 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert page.locator("figure img").evaluate_all("ims=>ims.every(i=>i.complete && i.naturalWidth>0)")
            for label in ["header","#inventory","#binding","#binding figure","#method"]:
                loc = page.locator(label).first
                if label == "header":
                    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
                else:
                    loc.evaluate("el=>el.scrollIntoView({block:'start',behavior:'instant'})")
                page.screenshot(path=qa / f"{width}_{label.strip('#').replace(' ','_')}.png")
            assert not errors and not remote, (errors, remote)
            report[str(width)] = dict(page_errors=errors, remote_requests=remote,
                                      search_by_point_and_equation=True, horizontal_overflow=False)
            page.close()
        browser.close()
    return report


def main():
    peaks = []
    stop = threading.Event()
    def observe():
        while not stop.is_set():
            size = 0
            for root in [RAW, OUT]:
                for file in root.rglob("*"):
                    try:
                        if file.is_file():
                            size += file.stat().st_size
                    except FileNotFoundError:
                        pass
            peaks.append(size)
            stop.wait(0.25)
    monitor = threading.Thread(target=observe, daemon=True)
    monitor.start()
    verified = verify_numbers()
    verified["offline_browser"] = verify_visuals()
    stop.set()
    monitor.join()
    def record(path):
        return dict(file=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=digest(path))
    artifacts = [record(p) for p in sorted(OUT.rglob("*")) if p.is_file() and p != OUT / "manifest.json"]
    scripts = sorted((ROOT/"scripts").glob("rhs_*.py")) + [
        ROOT/"scripts/build_rhs_report.py", ROOT/"scripts/verify_rhs_study.py",
        ROOT/"scripts/report_theme/report_theme.py", ROOT/"scripts/report_theme/report.css"]
    raw_bytes = sum(p.stat().st_size for p in RAW.rglob("*") if p.is_file())
    written = sum(r["bytes"] for r in artifacts)
    manifest = dict(verified=verified, sources=["inventory/sources.json","cases/case_members.csv",
                    "cases/source_hashes.csv","proxies/regional_sources.json","sydney_sources.csv"],
                    artifacts=artifacts, generators=[record(p) for p in scripts],
                    versions={s:importlib.metadata.version(s) for s in ["pandas","numpy","matplotlib","markdown","playwright"]},
                    storage=dict(limit_bytes=5_000_000_000, local_cache_and_verification_bytes=raw_bytes,
                                 report_files_bytes_excluding_manifest=written,
                                 observed_high_water_bytes=max(raw_bytes+written, *peaks),
                                 accounting="Logical bytes in named data and report directories including test/QA scratch. Sampled high-water during verification; code and manifest separate. Earlier acquisition caches retained. Prior project data read in place. Daily public reports and expanded XML parsed in RAM."))
    assert raw_bytes + sum(r["bytes"] for r in artifacts) < 5_000_000_000
    (OUT/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    for row in artifacts:
        assert digest(ROOT / row["file"]) == row["sha256"]
    print(json.dumps(verified, indent=2))


if __name__ == "__main__":
    main()
