"""Engineering, artifact, source and identical-row evaluation verification."""
from __future__ import annotations
import json
from pathlib import Path
from urllib.parse import unquote,urlparse
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup
from nemic_regimes import load_bundle
from .common import DATA,REPORT,ROOT,config,digest,now,stage,write_json
from .research import research_signature,usable_panel,folds


def report_checks():
    errors=[]
    manifest=json.loads((REPORT/"build_manifest.json").read_text())
    for relative,expected in manifest["inputs"].items():
        p=ROOT/relative
        if not p.exists() or digest(p)!=expected:errors.append("Report input hash mismatch: "+relative)
    for relative,expected in manifest["files"].items():
        p=REPORT/relative
        if not p.exists() or digest(p)!=expected:errors.append("Report file hash mismatch: "+relative)
    for p in REPORT.glob("*.html"):
        soup=BeautifulSoup(p.read_text(encoding="utf-8"),"html.parser")
        ids=[x["id"] for x in soup.select("[id]")]
        if len(ids)!=len(set(ids)):errors.append("Duplicate anchors in "+p.name)
        for tag,attribute in (("script","src"),("img","src"),("link","href")):
            for element in soup.find_all(tag):
                value=element.get(attribute,"")
                if value.startswith(("https://","http://","//")):errors.append("External rendering dependency: "+value)
        for a in soup.find_all("a",href=True):
            value=a["href"]
            if value.startswith(("https://","http://","mailto:")):continue
            parsed=urlparse(value);target=(p.parent/unquote(parsed.path)).resolve() if parsed.path else p
            if not target.exists():errors.append("Missing local link: "+value+" in "+p.name);continue
            if parsed.fragment and target.suffix==".html":
                dest=BeautifulSoup(target.read_text(encoding="utf-8"),"html.parser")
                if not dest.find(id=parsed.fragment):errors.append("Missing anchor: "+value)
    return errors


def workbook_checks(bundle=None):
    path=ROOT/"outputs/conditional_regimes_v1_20261025/conditional_limits.xlsx"
    errors=[]
    if not path.exists():return ["Workbook missing"]
    ns={"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        workbook=ET.fromstring(z.read("xl/workbook.xml"));sheets=workbook.findall("s:sheets/s:sheet",ns)
        if len(sheets)!=7:errors.append("Expected seven workbook sheets")
        sheet=ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        cells={c.attrib["r"]:c for c in sheet.findall("s:sheetData/s:row/s:c",ns)}
        selected=pd.read_csv(DATA/"example_profile.csv")
        for index,row in selected.iterrows():
            for letter,column in (("B","p10_mw"),("C","p50_mw"),("D","p90_mw")):
                address=f"{letter}{index+8}";value=cells[address].find("s:v",ns)
                if value is None or not np.isclose(float(value.text),float(row[column]),atol=1e-6):errors.append("Workbook/package value mismatch: "+address)
        formula=cells.get("J8")
        if formula is None or formula.find("s:f",ns) is None:errors.append("Band width formula missing")
        elif formula.find("s:v",ns) is not None:
            expected=float(selected.p90_mw.iat[0]-selected.p10_mw.iat[0])
            if not np.isclose(float(formula.find("s:v",ns).text),expected,atol=1e-5):errors.append("Band width cached result mismatch")
        if not any("/charts/chart" in n and n.endswith(".xml") for n in z.namelist()):errors.append("Profile chart missing from workbook")
        catalogue=pd.read_csv(DATA/"quarterly_catalogue.csv")
        reconciled=0
        for sheet_number,is_reference in ((2,True),(3,False)):
            exported=catalogue[catalogue.regime.eq("reference")==is_reference].reset_index(drop=True)
            keys=["connector","direction","era","quarter"]+([] if is_reference else ["regime"])
            sample=exported.groupby(keys,sort=False).head(1)
            if not is_reference:sample=sample.groupby(["connector","direction"],sort=False).head(4)
            wanted={int(i)+8:row for i,row in sample.iterrows()}
            found=set()
            with z.open(f"xl/worksheets/sheet{sheet_number}.xml") as stream:
                for _,element in ET.iterparse(stream,events=("end",)):
                    if element.tag!="{"+ns["s"]+"}row":continue
                    number=int(element.attrib["r"])
                    if number in wanted:
                        row=wanted[number];values={c.attrib["r"]:c.find("s:v",ns) for c in element.findall("s:c",ns)}
                        for letter,column in (("F","p10_mw"),("G","p50_mw"),("H","p90_mw")):
                            value=values.get(f"{letter}{number}")
                            if value is None or not np.isclose(float(value.text),row[column],atol=1e-6):errors.append(f"Catalogue/workbook mismatch sheet {sheet_number} row {number}")
                        if bundle is not None:
                            q={key:row[key] for key in ("connector","direction","era","quarter","half_hour")}
                            result=bundle.select({**q,**json.loads(row.conditions),"method":"table"},details=False)
                            for column in ("p10_mw","p50_mw","p90_mw"):
                                if result[column] is None or not np.isclose(result[column],row[column],atol=1e-6):errors.append(f"Catalogue/Python mismatch {q}")
                        found.add(number);reconciled+=1
                    element.clear()
            if found!=set(wanted):errors.append("Workbook catalogue sample rows missing")
        write_json(DATA/"interface_reconciliation.json",{"passed":not errors,"selected_quantile_cells":len(selected)*3,"catalogue_cases":reconciled,"errors":errors})
    return errors


def validate():
    with stage("validate",[REPORT/"build_manifest.json",DATA/"bundle/manifest.json"]) as artifacts:
        errors=[];bundle=load_bundle(DATA/"bundle");panel=bundle.panel
        if panel.duplicated(["connector","direction","time"]).any():errors.append("Duplicate directional target rows")
        if set(panel.connector)!=set(config()["connectors"]):errors.append("Connector coverage incomplete")
        if panel[["capacity","tight_capacity"]].isna().any().any():errors.append("Missing target in bundle")
        if not (panel.tight_capacity<=panel.capacity+1e-7).all():errors.append("Tight capacity exceeds average")
        for (name,direction,era),g in panel.groupby(["connector","direction","era"]):
            row=g.iloc[len(g)//2]
            r=bundle.select({"connector":name,"direction":direction,"era":era,"quarter":int(row.quarter),"half_hour":int(row.half_hour)})
            if r["p50_mw"] is None:errors.append("Reference query unexpectedly unavailable")
            elif not r["p10_mw"]<=r["p50_mw"]<=r["p90_mw"]:errors.append("Crossed quantiles")
        raw=pd.read_parquet(ROOT/"data/processed/ic_5min.parquet",columns=["time","INTERCONNECTORID","EXPORTLIMIT","IMPORTLIMIT"])
        raw["time30"]=raw.time.dt.ceil("30min")
        sample=panel[panel.time<pd.Timestamp("2026-09-01")].iloc[::max(1,len(panel)//40)]
        for row in sample.itertuples():
            native=raw[(raw.INTERCONNECTORID==row.ic)&(raw.time30==row.time)]
            values=pd.to_numeric(native.EXPORTLIMIT if row.direction=="forward" else -pd.to_numeric(native.IMPORTLIMIT),errors="coerce")
            if len(native)!=6 or not np.isclose(values.mean(),row.capacity,atol=1e-7) or not np.isclose(values.min(),row.tight_capacity,atol=1e-7):errors.append("Native target reconciliation failed")
        audit=json.loads((DATA/"fold_audit.json").read_text())
        expected=len(list(folds(usable_panel())))*12
        if len(audit)!=expected:errors.append(f"Fold completion mismatch {len(audit)} != {expected}")
        for row in audit:
            p=DATA/"evaluation"/f"{row['connector']}_{row['direction']}_{row['fold']}.parquet"
            tuning=DATA/"tuning"/f"{row['connector']}_{row['direction']}.json"
            if digest(p)!=row["sha256"]:errors.append("Fold prediction hash mismatch")
            if row["signature"]!=research_signature([DATA/"panel.parquet",tuning]):errors.append("Fitting dependency signature mismatch")
        canonical=json.loads((DATA/"canonical_partition_audit.json").read_text())
        if not canonical.get("passed"):errors.append("Canonical outage episode separation failed")
        if canonical.get("panel_sha256")!=digest(DATA/"panel.parquet") or canonical.get("manifest_sha256")!=digest(DATA/"bundle/manifest.json"):errors.append("Canonical episode audit is stale")
        source_records=[]
        for p in (DATA/"acquired").glob("*.json"):
            record=json.loads(p.read_text());raw_path=DATA/"raw"/unquote(record["url"].rsplit("/",1)[-1])
            if not raw_path.exists() or digest(raw_path)!=record["sha256"]:errors.append("Raw source hash mismatch: "+p.name)
            for relative,hash_ in record["outputs"].items():
                if digest(DATA/relative)!=hash_:errors.append("Parsed source hash mismatch: "+relative)
            source_records.append({"url":record["url"],"sha256":record["sha256"],"bytes":record["bytes"],"tables":record["tables"]})
        write_json(DATA/"source_integrity.json",{"verified":now(),"sources":source_records,"note":"Includes cached overlapping originals from the interrupted acquisition, all retained with hashes"})
        errors.extend(report_checks());errors.extend(workbook_checks(bundle))
        visual=DATA/"visual_qa.json"
        if not visual.exists():errors.append("Browser visual QA record missing")
        elif not json.loads(visual.read_text()).get("passed"):errors.append("Browser visual QA has unresolved failures")
        smoke=DATA/"package_smoke.json"
        if not smoke.exists() or not json.loads(smoke.read_text()).get("passed"):errors.append("Independent package installation check missing/failed")
        elif json.loads(smoke.read_text()).get("wheel_sha256")!=digest(ROOT/"packages/nemic-regimes/dist/nemic_regimes-0.1.0-py3-none-any.whl"):errors.append("Installed wheel verification is stale")
        tests=DATA/"test_results.json"
        if not tests.exists() or json.loads(tests.read_text()).get("exit_code")!=0:errors.append("Full repository test evidence missing/failed")
        result={"passed":not errors,"errors":errors,"verified":now(),"bundle_id":bundle.metadata["bundle_id"],
                "folds":len(audit),"source_archives":len(source_records),"asof_historical_rows":0,"production_promoted":False}
        write_json(REPORT/"verification.json",result);artifacts.append(REPORT/"verification.json")
        if errors:raise RuntimeError("Verification failed: "+"; ".join(errors[:15]))
        print(json.dumps(result,indent=2),flush=True)
