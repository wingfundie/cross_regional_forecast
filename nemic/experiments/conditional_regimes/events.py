"""Reproducible month-spanning event search and evidence/access register."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from urllib.parse import urlencode

import pandas as pd
from bs4 import BeautifulSoup
from nemic.common import session
from .common import DATA, EXECUTION, digest, now, stage, write_json


def review():
    with stage("events", [EXECUTION / "event_catalogue.json"]) as artifacts:
        events = json.loads((EXECUTION / "event_catalogue.json").read_text(encoding="utf-8"))
        urls = {e["url"] for e in events} | {e["primary"] for e in events if e.get("primary")}
        web_registry={}
        for p in DATA.glob("web_evidence_*.json"):
            evidence=json.loads(p.read_text(encoding="utf-8"))
            candidates=evidence.get("urls",[])
            if not candidates:
                import re
                candidates=re.findall(r"https://wattclarity\.com\.au/articles/[^\s)\"]+",str(evidence.get("result","")))
            for url in candidates:
                web_registry[url]={"evidence_file":p.name,"evidence_sha256":digest(p)}
        previous=DATA/"event_review.json"
        prior={r["url"]:r for r in json.loads(previous.read_text(encoding="utf-8")).get("access",[])} if previous.exists() else {}
        search = []
        for month in pd.period_range("2025-10", "2026-10", freq="M"):
            url = "https://wattclarity.com.au/?" + urlencode({"s": "interconnector", "year": month.year, "monthnum": month.month})
            search.append({"month": str(month), "query": "interconnector", "url": url})
            urls.add(url)
        def fetch(url):
            if url in web_registry:
                return {"url":url,"status":"reviewed_via_web_research","source_page_hash":None,
                        "retrieved":now(),"evidence_kind":"Research tool response; hash is not the original page hash",**web_registry[url]}
            if url in prior:
                return prior[url]
            p = DATA / "event_sources" / (hashlib.sha256(url.encode()).hexdigest() + ".html")
            try:
                if not p.exists():
                    r = session().get(url, timeout=(10, 25))
                    r.raise_for_status()
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(r.text, encoding="utf-8")
                soup = BeautifulSoup(p.read_text(encoding="utf-8"), "html.parser")
                links = [{"title": a.get_text(" ", strip=True), "url": a.get("href")} for a in soup.select("h2 a, h3 a") if "/articles/" in str(a.get("href"))]
                return {"url": url, "status": "retrieved", "sha256": digest(p), "retrieved": now(),
                        "title": soup.title.get_text(" ", strip=True) if soup.title else "", "discovered_articles": links[:100]}
            except Exception as exc:
                return {"url": url, "status": "access_gap", "reason": str(exc)}
        with ThreadPoolExecutor(max_workers=2) as pool:
            access = list(pool.map(fetch, sorted(urls)))
        access_map = {a["url"]: a for a in access}
        for e in events:
            e["access"] = access_map[e["url"]]["status"]
            e["primary_status"] = access_map.get(e.get("primary"), {}).get("status", "notice_citation_requires_original_reconciliation")
            e["numerical_limit_claim"] = "No numerical adjustment inferred from article alone"
        for s in search:
            s.update(access_map[s["url"]])
        write_json(DATA / "event_review.json", {"window": ["2025-10-25", "2026-10-25"], "events": events,
                   "access": access, "monthly_search": search,
                   "inclusion": "Mechanism-bearing transfer events, structural changes, stress backgrounds, negative controls and data anomalies",
                   "exclusion": "Out-of-window cases, price-only narratives without a transfer hypothesis, duplicate followups and commercial-only content",
                   "completeness": "Bounded twelve-month public search, not a census of all grid incidents; no search hit does not imply no event"})
        artifacts.append(DATA / "event_review.json")
        print("Event review", len(events), "cases;", len(search), "calendar-month searches;", sum(a["status"] == "access_gap" for a in access), "direct access gaps", flush=True)
