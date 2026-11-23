"""Render the offline atlas and save reproducible desktop/mobile verification evidence.

Screenshots must still be inspected; --record-inspection records that completed human/agent
review against the current HTML hash and does not replace rendering or structural checks.
"""
from __future__ import annotations

import argparse
import json
import sys
import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nemic.experiments.line_outages.core import config, json_write, sha


def main():
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument("--record-inspection",action="store_true")
    options=args.parse_args();c=config();html=c["_report"]/"index.html";record=c["_execution"]/"report_qa.json"
    if options.record_inspection:
        qa=json.loads(record.read_text())
        if not qa.get("passed") or qa["html_sha256"]!=sha(html):raise RuntimeError("No passing render for the current report")
        qa["visual_inspection"]=True;json_write(record,qa);print("Desktop/mobile screenshots inspected and recorded");return
    from playwright.sync_api import sync_playwright
    directory=c["_report"]/"qa";directory.mkdir(exist_ok=True)
    results=[];errors=[];screenshots=[]
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(headless=True)
        browser_version=browser.version
        for label,width,height in [("desktop",1440,1000),("mobile",390,844)]:
            context=browser.new_context(viewport={"width":width,"height":height},offline=True)
            page=context.new_page();page.on("pageerror",lambda exc:errors.append(str(exc)))
            page.goto(html.as_uri(),wait_until="load",timeout=60000)
            page.wait_for_function("[...document.querySelectorAll('.plotly-graph-div')].every(e=>e._fullLayout)",timeout=60000)
            overflow=page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")
            plots=page.locator(".plotly-graph-div").count()
            for name,selector in [("hero","header"),("chart","figure"),("evidence","#findings figure:nth-of-type(2)"),("matching","#findings figure:nth-of-type(3)"),("subplot","#deep-dives figure"),("route","#line-CANBERRA-LINE-6 figure"),("line6","#line-CANBERRA-LINE-6"),("methods","#methods")]:
                item=page.locator(selector).first;item.scroll_into_view_if_needed()
                if name=="hero":page.evaluate("window.scrollTo(0,0)")
                else:item.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
                path=directory/f"{label}_{name}.png"
                if name in ["chart","evidence","matching","subplot","route"]:item.screenshot(path=str(path))
                else:page.screenshot(path=str(path))
                screenshots.append(path)
            search=page.locator("#line-search");search.fill("CANBERRA/LINE/6")
            visible=page.locator(".line-profile:visible").count()
            search.fill("")
            page.locator("#line-CANBERRA-LINE-6 details").first.evaluate("e=>e.open=true")
            page.locator("#line-CANBERRA-LINE-6 details").first.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
            path=directory/f"{label}_dense_table.png";page.screenshot(path=str(path));screenshots.append(path)
            if label=="mobile":
                for name,selector in [("chart","figure .chart-scroll"),("subplot","#deep-dives figure .chart-scroll"),("route","#line-CANBERRA-LINE-6 figure .chart-scroll"),("dense_table","#line-CANBERRA-LINE-6 details .table-scroll")]:
                    item=page.locator(selector).first
                    item.evaluate("e=>{e.scrollTo({left:e.scrollWidth-e.clientWidth,behavior:'instant'});e.scrollIntoView({block:'start',behavior:'instant'});}")
                    path=directory/f"mobile_{name}_right.png";page.screenshot(path=str(path));screenshots.append(path)
            results.append({"viewport":label,"width":width,"height":height,"document_overflow":overflow,
                            "rendered_charts":plots,"search_one_line":visible==1})
            context.close()
        browser.close()
    passed=not errors and all(not r["document_overflow"] and r["rendered_charts"]>=10 and r["search_one_line"] for r in results)
    json_write(record,{"passed":passed,"html_sha256":sha(html),"offline":True,"viewports":results,
                       "browser_errors":errors,"screenshots":{str(p.relative_to(ROOT)):sha(p) for p in screenshots},"visual_inspection":False,
                       "browser_version":browser_version,"script_sha256":sha(Path(__file__)),"rendered_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()})
    print(json.dumps({"passed":passed,"viewports":results,"browser_errors":errors,"screenshots":len(screenshots)}))
    if not passed:raise RuntimeError("Browser verification failed")


if __name__=="__main__":main()
