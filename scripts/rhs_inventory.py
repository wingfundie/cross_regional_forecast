"""Inventory the active DS formulations in one public February 2026 NEMDE case.

From the repository root: python scripts/rhs_inventory.py. The case reader
fetches only the first compressed ZIP member and checks its CRC and size.
All snapshot conclusions refer to the case identified in sources.json.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nemic.common import session
from scripts.rhs_cases import region_demand, rhs_terms

RAW = ROOT / "data/rhs_replay/inventory"
OUT = ROOT / "reports/rhs_replay/inventory"
LIMIT = 450_000_000
CASE_URL = ("https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/2026/"
            "NEMDE_2026_02/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_20260204_loaded.zip")
EMS_URL = ("https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/"
           "MMSDM_2026_02/MMSDM_Historical_Data_SQLLoader/DATA/"
           "PUBLIC_ARCHIVE%23EMSMASTER%23FILE01%23202602010000.zip")
DISPATCH_URL = "https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/PUBLIC_DISPATCHIS_20260204.zip"
GUIDE = ("https://aemo.com.au/-/media/files/stakeholder_consultation/consultations/"
         "nem-consultations/2023/constraints-implementation-guidelines/final-constraint-implementation-guidelines-v3.pdf")
RATING = "https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/transmission-equipment-ratings"
TRIGGERS = "https://tech-specs.docs.public.aemo.com.au/Content/TSP_TechnicalSpecificationPortal/EMMSDMTableTriggers.htm"
EXTERNAL = set("ASRITEMNW")
INTERNAL = set("CGBU")
LABEL = {"A": "SCADA analog", "S": "SCADA equipment status", "I": "Interconnector metered flow",
         "T": "Trader initial MW", "E": "Operator-entered value or forecast", "R": "Regional demand",
         "M": "MNSP offered availability at from-region", "N": "MNSP offered availability at to-region",
         "W": "Switch-run status"}
SCHEMA = {"A": "Case.ConstraintScadaData[A].ScadaValues.Value", "S": "Case.ConstraintScadaData[S].ScadaValues.Value",
          "I": "Case.ConstraintScadaData[I].ScadaValues.Value", "R": "Case.ConstraintScadaData[R].ScadaValues.Value",
          "W": "Case.ConstraintScadaData[W].ScadaValues.Value and selected switch run",
          "T": "Case.Trader.TraderInitialCondition[InitialMW].Value", "E": "Case.Period.EnteredValuePeriod.Value",
          "M": "Case.Period.InterconnectorPeriod.MNSPOffer[FromRegion].MaxAvail",
          "N": "Case.Period.InterconnectorPeriod.MNSPOffer[ToRegion].MaxAvail"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    used = sum(f.stat().st_size for folder in (RAW, OUT) for f in folder.rglob("*") if f.is_file())
    if used + len(data) > LIMIT:
        raise ValueError("Inventory sub-budget exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def fetch(url, maximum, headers=None):
    with session().get(url, headers=headers or {}, stream=True, timeout=(15, 80)) as res:
        res.raise_for_status()
        if headers and res.status_code != 206:
            raise ValueError("Archive server did not honour byte range")
        buf = io.BytesIO()
        for chunk in res.iter_content(131072):
            if buf.tell() + len(chunk) > maximum:
                raise ValueError("Source exceeds declared download bound")
            buf.write(chunk)
        return buf.getvalue()


def cached(name, url, maximum):
    path = RAW / name
    if not path.exists():
        write(path, fetch(url, maximum))
    if path.stat().st_size > maximum:
        raise ValueError("Unexpected archive size")
    return path.read_bytes()


def load_case():
    path = RAW / "snapshot.loaded.zip.slice"
    payload = path.read_bytes() if path.exists() else fetch(CASE_URL, 1_048_576, {"Range": "bytes=0-1048575"})
    sig, version, flags, method, tm, day, crc, compressed, size, namesize, extrasize = struct.unpack_from("<4s5H3I2H", payload)
    start = 30 + namesize + extrasize
    name = payload[30:30+namesize].decode()
    if sig != b"PK\x03\x04" or method != 8 or flags or size > 20_000_000 or name != "NEMSPDOutputs_2026020400100.loaded":
        raise ValueError("Unexpected ZIP member")
    payload = payload[:start+compressed]
    xml = zlib.decompress(payload[start:], -15)
    if len(xml) != size or zlib.crc32(xml) != crc:
        raise ValueError("Case integrity check failed")
    if not path.exists():
        write(path, payload)
    return ET.fromstring(xml), dict(url=CASE_URL, member=name, member_sha256=digest(xml),
            bytes=len(payload), slice_sha256=digest(payload), member_bytes=len(xml))


def load_ems():
    data = cached("ems.zip", EMS_URL, 1_000_000)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        name, = z.namelist()
        rows = csv.reader(io.TextIOWrapper(z.open(name), encoding="cp1252"))
        next(rows)
        columns = next(rows)[4:]
        values = [dict(zip(columns, row[4:])) for row in rows if row[0] == "D"]
    points = {(r["SPD_TYPE"], r["SPD_ID"]):r for r in values}
    assert len(points) == len(values)
    return points, dict(url=EMS_URL, member=name, rows=len(values), bytes=len(data), sha256=digest(data))


def load_dispatch():
    data = cached("dispatchis.zip", DISPATCH_URL, 12_000_000)
    with zipfile.ZipFile(io.BytesIO(data)) as outer:
        name, = [n for n in outer.namelist() if "_202602040405_" in n]
        inner = zipfile.ZipFile(io.BytesIO(outer.read(name)))
        member, = inner.namelist()
        csv_data = inner.read(member)
    rows = csv.reader(io.StringIO(csv_data.decode("cp1252")))
    header = next(rows)
    timestamp = datetime.strptime(" ".join(header[5:7]), "%Y/%m/%d %H:%M:%S")
    result = {}
    for row in rows:
        if row[1:3] != ["DISPATCH", "CONSTRAINT"]:
            continue
        if row[0] == "I":
            cols = row[4:]
        if row[0] == "D":
            r = dict(zip(cols, row[4:]))
            if r["RUNNO"] == "1" and r["INTERVENTION"] == "0" and r["SETTLEMENTDATE"] == "2026/02/04 04:05:00":
                result[r["CONSTRAINTID"]] = r
    return result, dict(url=DISPATCH_URL, sha256=digest(data), bytes=len(data), member=name, inner_member=member,
                        member_sha256=digest(csv_data), header_generated_nem=timestamp.isoformat()+"+10:00")


def write_csv(name, rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(dict.fromkeys(k for row in rows for k in row)), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    write(OUT / name, buf.getvalue().encode())


def point_values(inputs, full_case, dispatch):
    scada = defaultdict(list)
    for category in inputs.iter("ConstraintScadaData"):
        for collection in category:
            for x in collection:
                scada[category.get("SpdType"), x.get("SpdID")].append((collection.tag, x.attrib))
    trader = {}
    for x in inputs.iter("Trader"):
        t = x.find(".//TraderInitialCondition[@InitialConditionID='InitialMW']")
        if t is not None:
            trader[x.get("TraderID")] = t.get("Value")
    entered = {x.get("SpdID"):x.get("Value") for x in inputs.iter("EnteredValuePeriod")}
    avail = {}
    for x in inputs.iter("InterconnectorPeriod"):
        for t in x.iter("MNSPOffer"):
            for k, side in (("M", "FromRegion"), ("N", "ToRegion")):
                if t.get("RegionID") == x.get(side):
                    avail[k, x.get("InterconnectorID")] = t.get("MaxAvail")
    calculated_terms = {}
    details, validation = [], []
    for region in ("NSW1","QLD1","SA1"):
        components = []
        calculated, rhs_component = region_demand(inputs, region, components)
        solution = full_case.find(f'.//RegionSolution[@RegionID="{region}"][@Intervention="0"]')
        reference = float(solution.attrib["FixedDemand"])
        delta = abs(reference-calculated)
        verified = delta <= 0.005
        validation.append(dict(region=region,calculated_fixed_demand=calculated,reference_fixed_demand=reference,
                               fixed_demand_absolute_difference=delta,components=len(components),within_0_005_mw=verified,
                               calculated_rhs_term=rhs_component, rhs_check_equation="",calculated_rhs="",reference_rhs="",
                               absolute_rhs_difference="",rhs_term_validation="untested"))
        calculated_terms[region] = rhs_component
        details.extend(components)
    entity = inputs.find('.//GenericConstraint[@ConstraintID="N::Q_NIL_KC"]')
    result = dispatch[entity.get("ConstraintID")]
    assert result["GENCONID_VERSIONNO"]==entity.get("VersionNo")
    assert result["GENCONID_EFFECTIVEDATE"]==entity.get("EffectiveDate")[:19].replace("T"," ").replace("-","/")
    reported_rhs = float(result["RHS"])
    trace = []
    derived_rhs = rhs_terms(inputs, entity, calculated_terms, trace)
    difference = abs(derived_rhs-reported_rhs)
    used_regions = {t["spd_id"] for t in trace if t["spd_type"]=="R"}
    assert used_regions=={"NSW1","QLD1"}
    regional = {}
    for row in validation:
        region = row["region"]
        if region in used_regions:
            row.update(rhs_check_equation=entity.get("ConstraintID"),calculated_rhs=derived_rhs,reference_rhs=reported_rhs,
                       absolute_rhs_difference=difference,rhs_term_validation="joint equation replay")
            if difference<=0.000005:
                regional[region] = str(calculated_terms[region])
    write_csv("region_components.csv",details)
    write_csv("region_validation.csv",validation)
    return scada, trader, entered, avail, regional


def describe(key, metadata, observations):
    kind, point = key
    scada, trader, entered, avail, regional = observations
    rows = scada[key]
    usable = [x for group, x in rows if group=="ScadaValuesCollection" and x.get("Can_Use_Value")=="True"]
    record = {}
    value, status = "", "unresolved"
    if kind in "ASIW":
        if len(usable)==1:
            record = usable[0]
            value, status = record["Value"], "observed"
        elif rows:
            status = "selection_or_quality_unresolved"
        if kind=="W" and value:
            status = "switch_run_selection_required"
    if kind=="R" and rows:
        status = "regional_components_require_selection"
    if kind=="R" and point in regional:
        value,status = regional[point],"derived_inputs_joint_rhs_check"
    if kind=="T":
        duid, _, cp = point.partition(".")
        # A dotted identifier needs corroboration for its connection point.
        if duid in trader and (not cp or rows):
            value, status = trader[duid], "case_initial_mw"
        elif rows:
            status = "selection_or_quality_unresolved"
    if kind=="E" and point in entered:
        value, status = entered[point], "case_entered_value"
    if key in avail:
        value, status = avail[key], "case_offer_value"
    meta = metadata.get(key, {})
    description = meta.get("DESCRIPTION", "") or LABEL.get(kind,kind)
    unit = {"S":"binary", "T":"MW", "I":"MW", "R":"MW", "W":"binary", "M":"MW", "N":"MW"}.get(kind, "")
    if not unit and record.get("EMS_ID") in {"MW","MVA","MVAR","KV","HZ","AMP","MWER"}:
        unit = record["EMS_ID"] if record["EMS_ID"]!="MWER" else "unverified"
    rating = kind=="E" and any(x.get("EMS_ID") in {"NORM","EMER","LDSH"} for _,x in rows)
    if rating:
        unit = "MVA (verify equipment rating)"
    alternate = {"T":"DISPATCH_UNIT_SCADA.SCADAVALUE; matched DUID, interval and quality required",
                 "I":"DISPATCHINTERCONNECTORRES.METEREDMWFLOW; match direction and vintage",
                 "R":"DISPATCHREGIONSUM.INITIALSUPPLY or TOTALDEMAND are candidates only; definitions differ",
                 "M":"MNSP energy offer vintage and direction", "N":"MNSP energy offer vintage and direction",
                 }.get(kind, "")
    if rating:
        alternate = "NETWORK_REALTIMERATING.RATINGVALUE by SPD_ID and SETTLEMENTDATE; PUBLIC_TER_DAILY alternate rating definitions"
    return dict(spd_type=kind, spd_id=point, meaning=description, region_group=meta.get("GROUPING_ID",""),
                unit=unit or "unverified", sign="as reported; apply signed term coefficient",
                source_field=("Case initial demand, demand change, ADE and allocated initial interconnector losses; see region_components.csv"
                              if status=="derived_inputs_joint_rhs_check" else SCHEMA.get(kind,"unresolved")),
                match_key="case/period plus typed SPD ID"+(" and TraderID; confirm connection point" if kind=="T" else ""),
                snapshot_value=value, historical_status=status, dispatch_time_status="exact current value unverified",
                availability="Anonymous NEMDE file published after this run; five-minute input snapshot",
                alternate_public_source=alternate, scada_records=len(rows), usable_records=len(usable),
                ems_keys="|".join(sorted({x.get("EMS_Key","") for _,x in rows})),
                ems_ids="|".join(sorted({x.get("EMS_ID","") for _,x in rows})),
                sensor_time=record.get("EMS_TimeStamp",""), ems_good=record.get("EMS_Good",""),
                ems_replaced=record.get("EMS_Replaced",""), selected_sensor_usable=record.get("Can_Use_Value",""))


def affine(eq, shared, stack=()):
    """Recognise unbranched sums only. Reject all stack and grouped programs."""
    offset = Decimal(0)
    coeffs = Counter()
    for t in eq.findall("RHSTermCollection/RHSTerm"):
        kind, point = t.get("SpdType"), t.get("SpdID")
        scale = Decimal(t.get("Multiplier"))
        if t.get("Operation") or t.get("GroupTerm"):
            return None
        if kind=="C":
            offset += scale
        elif kind=="X" and point in shared and point not in stack:
            sub = affine(shared[point], shared, stack+(point,))
            if sub is None:
                return None
            osub, csub = sub
            offset += osub*scale
            for k,v in csub.items():
                coeffs[k] += scale*v
        elif kind in EXTERNAL:
            coeffs[kind,point] += scale
        else:
            return None
    return offset, {k:v for k,v in coeffs.items() if v}


def datasnap(equations, shared, points, dispatch, generated):
    rows = []
    for eid,e in equations.items():
        if not eid.startswith("DATASNAP"):
            continue
        rec = dispatch.get(eid, {})
        expected = e.get("EffectiveDate","")[:19].replace("T"," ").replace("-","/")
        verified = rec.get("GENCONID_EFFECTIVEDATE")==expected and rec.get("GENCONID_VERSIONNO")==e.get("VersionNo")
        f = affine(e, shared)
        row = dict(monitor=eid, effective_date=e.get("EffectiveDate"), version=e.get("VersionNo"),
                   spd_type="", spd_id="", scale="", offset="", published_rhs=rec.get("RHS",""),
                   implied_input="", case_input="", absolute_difference="", validation="complex_program",
                   dispatchis_generated_nem=generated, interval_end_nem="2026-02-04T04:05:00+10:00")
        if f:
            offset, coef = f
            row["validation"] = "multiple_or_no_leaves"
            if len(coef)==1:
                key, scale = next(iter(coef.items()))
                value = points[key]["snapshot_value"]
                row.update(spd_type=key[0], spd_id=key[1], scale=str(scale), offset=str(offset), case_input=value,
                           validation="missing_matching_result_or_independent_input")
                if rec and verified and value!="":
                    inferred = (Decimal(rec["RHS"])-offset)/scale
                    error = abs(inferred-Decimal(value))
                    # Public RHS is quoted to 5 decimals. Check in original RHS units.
                    rhs_error = error*abs(scale)
                    status = "disagreement"
                    if rhs_error <= Decimal("0.000005"):
                        status = "verified_after_run"
                    elif rhs_error <= Decimal("0.00001"):
                        status = "within_one_published_increment"
                    row.update(implied_input=str(inferred), absolute_difference=str(error), validation=status)
                    if status in {"verified_after_run", "within_one_published_increment"}:
                        points[key]["alternate_public_source"] += (" | " if points[key]["alternate_public_source"] else "")+f"DISPATCHIS.CONSTRAINT[{eid}].RHS inverse, scale {scale}, offset {offset}"
                        points[key]["dispatch_time_status"] = "matched DATASNAP generated after cutoff; lagged proxy only with receipt"
        rows.append(row)
    return rows


def lookup(points, dependencies):
    users = defaultdict(list)
    for r in dependencies:
        users[r["spd_type"],r["spd_id"]].append(r["equation"])
    records = [[p["spd_type"],p["spd_id"],p["meaning"],p["historical_status"],p["snapshot_value"],
                p["unit"],p["source_field"],p["alternate_public_source"],p["dispatch_time_status"],
                users[k]] for k,p in sorted(points.items())]
    html = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Dispatch RHS input lookup</title><style>*{box-sizing:border-box}body{font:16px/1.5 system-ui;color:#182a35;background:#f8fafb;max-width:80rem;margin:auto;padding:clamp(1rem,4vw,3rem)}h1{font-size:clamp(1.7rem,4vw,3rem);line-height:1.1}a{color:#07576a}input{width:100%;max-width:48rem;font:inherit;padding:.7rem;border:1px solid #647986;border-radius:4px}article{border-top:1px solid #bccad0;padding:1rem 0;overflow-wrap:anywhere}h2{font:600 1.2rem/1.4 ui-monospace,monospace;margin:.2rem 0}p{margin:.4rem 0}label{display:block;font-weight:600;margin:1.4rem 0 .25rem}details{margin-top:.4rem}button{font:inherit;padding:.5rem 1rem;border:1px solid #506772;background:white}#count{color:#415965}dt{font-weight:600}dd{margin:0 0 .5rem}</style></head>
<body><main><h1>Dispatch RHS input lookup</h1><p>All external inputs referenced in the NEM-wide dispatch case ending 4 February 2026 at 04:05 NEM time. Each result lists the equations that use it.</p>
<p><a href="inputs.csv" download>Input register</a> · <a href="dependencies.csv" download>Equation dependencies</a> · <a href="terms.csv" download>Versioned terms</a> · <a href="datasnap.csv" download>DATASNAP inversions</a></p>
<label for="q">Search by input, equation ID or description</label><input id="q" type="search" placeholder="e.g. N_SYDNEY_LOAD"><p id="count" role="status"></p><div id="list"></div><button id="more" type="button">Show more</button></main>
<script type="application/json" id="data">RECORDS</script><script>
const rows=JSON.parse(document.getElementById('data').textContent);
const search=document.querySelector('#q'),list=document.querySelector('#list'),more=document.querySelector('#more');
let limit=20;
function add(p,t,msg){const e=document.createElement(t);e.textContent=msg;p.append(e);return e}
function render(){
  const q=search.value.trim().toLowerCase();
  const found=rows.filter(r=>[r[0]+':'+r[1],r[2],...r[9]].join(' ').toLowerCase().includes(q));
  list.replaceChildren();document.querySelector('#count').textContent=found.length+' matching inputs · showing '+Math.min(limit,found.length);
  for(const r of found.slice(0,limit)){
    const a=add(list,'article','');add(a,'h2',r[0]+' · '+r[1]);add(a,'p',r[2]);const dl=add(a,'dl','');
    for(const [k,v] of [['Case value',r[4]===''?'Unresolved':r[4]+' ('+r[5]+')'],['Historical evidence',r[3].replaceAll('_',' ')+' — '+r[6]],['At the interval start',r[8]],['Other public source',r[7]]]){
      if(v){add(dl,'dt',k);add(dl,'dd',v)}
    }
    const d=add(a,'details','');add(d,'summary',r[9].length+' equation(s)');add(d,'p',r[9].join(', '));
  }
  more.hidden=found.length<=limit;
}
search.addEventListener('input',()=>{limit=20;render()});more.addEventListener('click',()=>{limit+=20;render()});render();
</script></body></html>"""
    encoded = json.dumps(records,ensure_ascii=True,separators=(",",":")).replace("<","\\u003c")
    write(OUT/"lookup.html", html.replace("RECORDS", encoded).encode())


def build():
    full_case, case_source = load_case()
    inputs = full_case.find("NemSpdInputs")
    metadata, ems_source = load_ems()
    dispatch, dispatch_source = load_dispatch()
    period = inputs.find(".//Period")
    assert period.get("PeriodID") == "2026-02-04T04:05:00+10:00"
    obs = point_values(inputs, full_case, dispatch)
    loaded = {e.get("ConstraintID"):e for e in inputs.iter("GenericConstraint")}
    active = {e.get("ConstraintID"):e for e in inputs.iter("GenericConstraintPeriod")}
    equations = {eid:loaded[eid] for eid in active}
    assert all(e.get("Version")==active[k].get("Version") for k,e in equations.items())
    shared = {e.get("EquationID"):e for e in inputs.iter("GenericEquation")}
    terms, deps, coverage, points = [], [], [], {}
    visiting, finished = set(), set()

    def collect(e, owner, name):
        """Store each versioned program once. Recursion only follows type X."""
        token = owner, name
        if token in finished:
            return
        visiting.add(token)
        for j,t in enumerate(e.findall("RHSTermCollection/RHSTerm"),1):
            k, p = t.get("SpdType"),t.get("SpdID")
            terms.append(dict(owner_type=owner, owner_id=name, effective_date=e.get("EffectiveDate"), version=e.get("VersionNo"),
                         ordinal=j, term_id=t.get("TermID"), group_term=t.get("GroupTerm",""), spd_type=k, spd_id=p,
                         multiplier=t.get("Multiplier"), operation=t.get("Operation",""), default_value=t.get("Default",""),
                         parameters=json.dumps({key:v for key,v in t.attrib.items() if key not in
                               {"TermID","GroupTerm","SpdType","SpdID","Multiplier","Operation","Default"}},sort_keys=True)))
            if k=="X" and p in shared and ("shared",p) not in visiting:
                collect(shared[p],"shared",p)
            if k in EXTERNAL and (k,p) not in points:
                points[k,p] = describe((k,p),metadata,obs)
        visiting.remove(token)
        finished.add(token)

    def leaves(e, path=()):
        for t in e.findall("RHSTermCollection/RHSTerm"):
            k,p = t.get("SpdType"), t.get("SpdID")
            if k=="X" and p in shared and p not in path:
                yield from leaves(shared[p],path+(p,))
            elif k not in INTERNAL:
                yield k,p,path

    for name,e in equations.items():
        collect(e,"constraint",name)
        unique = defaultdict(set)
        for k,p,path in leaves(e):
            unique[k,p].add(" > ".join(path) or "(direct)")
        problems = []
        for (k,p),paths in sorted(unique.items()):
            status = points.get((k,p),{}).get("historical_status","unresolved_reference")
            if status not in {"observed","case_initial_mw","case_offer_value","case_entered_value","derived_inputs_joint_rhs_check"}:
                problems.append(f"{k}:{p} ({status})")
            deps.append(dict(equation=name, effective_date=e.get("EffectiveDate"), version=e.get("VersionNo"),
                        spd_type=k,spd_id=p,via_shared_equations=" | ".join(sorted(paths)),historical_status=status))
        dynamic = e.find("RHSTermCollection") is not None
        track = list(e.iter("ConstraintTrkItem"))
        coverage.append(dict(equation=name,effective_date=e.get("EffectiveDate"), version=e.get("VersionNo"),
                        relation=e.get("Type"), formulation="dynamic" if dynamic else "static", static_value="" if dynamic else e.get("RHS"),
                        force_scada=e.get("Force_SCADA"),case_period_category=active[name].get("Category"),
                        sets="|".join(sorted({x.get("GenConSetID","") for x in track})),
                        external_inputs=len(unique), unresolved_inputs=len(problems),first_gap=next(iter(problems),""),
                        historical_status=("some_inputs_unresolved" if problems else "case_inputs_located" if dynamic else "case_static_constant"),
                        dispatch_time_status="unverified at interval start"))
    monitors = datasnap(equations,shared,points,dispatch,dispatch_source["header_generated_nem"])
    write_csv("inputs.csv", [points[x] for x in sorted(points)])
    write_csv("equations.csv",coverage)
    write_csv("terms.csv",terms)
    write_csv("dependencies.csv",deps)
    write_csv("datasnap.csv",monitors)
    write_csv("nsw_demand_points.csv", [dict(spd_type=k,spd_id=p,description=r["DESCRIPTION"],group=r["GROUPING_ID"],
              referenced_in_snapshot=(k,p) in points) for (k,p),r in sorted(metadata.items())
              if r["GROUPING_ID"]=="NSW1" and re.search(r"load|demand",p+" "+r["DESCRIPTION"],re.I)])
    refs = dict(case=case_source,ems=ems_source,dispatchis=dispatch_source,implementation=GUIDE,
                public_ratings=RATING,table_publication=TRIGGERS)
    write(OUT/"sources.json",json.dumps(refs,indent=2).encode())
    summary = dict(interval=period.get("PeriodID"), cutoff="2026-02-04T04:00:00+10:00",loaded_formulations=len(loaded),
                   active_in_period=len(active),excluded_loaded=sorted(set(loaded)-set(active)),shared_loaded=len(shared),
                   shared_used=sum(k=="shared" for k,p in finished),formulations=Counter(r["formulation"] for r in coverage),
                   external_input_count=len(points), by_spd_type=Counter(k for k,p in points), program_terms=len(terms),
                   historical_input_status=Counter(r["historical_status"] for r in points.values()),
                   historical_equation_status=Counter(r["historical_status"] for r in coverage),
                   datasnap=Counter(r["validation"] for r in monitors), generated_nem=dispatch_source["header_generated_nem"],
                   missing_references=[r for r in deps if r["historical_status"]=="unresolved_reference"],
                   external_input_equation_pairs=len(deps))
    write(OUT/"summary.json",json.dumps(summary,indent=2).encode())
    lookup(points,deps)
    resolved = summary["historical_equation_status"]["case_inputs_located"]
    qualified = summary["historical_equation_status"]["some_inputs_unresolved"]
    readme = f"""# How to use the input inventory

The snapshot is the NEM-wide dispatch case ending **4 February 2026, 04:05 NEM time**. It covers all 1,125 equation versions listed for that period. The XML carried 1,126 formulations in memory. `S_WDR_NO_SCADA` had no matching period row and was excluded. Other outages, seasons and predispatch can invoke different formulas. Monthly MMSDM change files alone omit older versions still in force.

Open [the offline lookup](lookup.html) to search either a point or an equation. To recreate a program, select its row in [equations](equations.csv), follow its terms in [versioned programs](terms.csv) in ordinal order, and resolve every type X reference to the shared program with that ID in this case. The same [external dependencies](dependencies.csv) can recur through multiple paths. The [point register](inputs.csv) retains source keys, quality flags, units where verified, the historical lookup result and an interval-start verdict. The [NSW demand index](nsw_demand_points.csv) includes regional candidates even if this case did not reference them.

## What coverage measures

The case includes 117 static and 1,008 dynamic equations. Across 170 shared programs it references 2,206 unique external type/ID pairs. For {resolved} dynamic equations the audit located a candidate case value for every external input. Another {qualified} contain at least one unresolved input or choice of component or switch run. Presence is a necessary condition. Replicating a calculation may also require the operator, data quality fallback, intervention branch, overriding value or run-specific state. The three detailed replays test arithmetic separately.

Nine input IDs remain qualified. Six traders have no matched initial MW, two regional terms lack an equation-level check, and the Basslink switch-run state requires run selection. For NSW and Queensland the sum of initial demand, forecast change and ADE less the allocated initial-flow losses reproduces the joint R contribution in N::Q_NIL_KC within the published rounding interval. This validates the combination of the two regional terms in that equation. A separate regional FixedDemand check includes scheduled-load and WDR adjustments. South Australian FixedDemand reconciles, while the independent R test covers NSW and Queensland. Victoria also requires a Basslink adjustment. All sampled WDR initial values are zero. [Regional input components](region_components.csv) · [Regional validation](region_validation.csv). Their equation counts overlap. A missing trader can trigger an equation-specific default. This inventory preserves each default in the term program and leaves its actual use open. The switch-run winner depends on the dispatch solution. Constants, groups and stack labels are instructions inside the versioned formulation, so the distinct-input count excludes them. [AEMO implementation guidelines, version 3 of 20 April 2023](https://aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2023/constraints-implementation-guidelines/final-constraint-implementation-guidelines-v3.pdf)

## Recovering a point after dispatch

The [DATASNAP audit](datasnap.csv) records every loaded monitor. Among 54, 43 had a single nonzero external coefficient in an unbranched affine formula. Each had a matching public result, equation version and separately observed case value. Forty-one inversions agreed within half the last published RHS decimal and the other two within one last-place increment. Three formulas depend on more than one input. Eight contain additional stack operations. The single-point inversion is `(published_rhs - offset) / scale`. Compare against separate XML sensor data when verifying the monitor's own RHS.

For `DATASNAP_DFS_NSYD`, the public RHS was 13,705.96655, the offset was 10,000 and the coefficient was one. The implied 3,705.96655 MW matches the XML analog to 0.000003 MW. EMSMASTER describes it as Sydney, Wollongong and Newcastle load. The analog was stamped 03:59:55, accepted for use and marked EMS-replaced. The saved DispatchIS header was generated at **04:00:11**, eleven seconds after interval start. Header generation is an earliest-possible availability bound. Independent publication or receipt evidence is required before using a previous report at the next cutoff. [February EMSMASTER](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/MMSDM_2026_02/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23EMSMASTER%23FILE01%23202602010000.zip) · [DispatchIS day archive](https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/PUBLIC_DISPATCHIS_20260204.zip)

## Public source alternatives

For a typed trader input, check the DUID and connection point against case initial MW and compare the matching public DISPATCH_UNIT_SCADA record. For interconnector flow, check sign and initial metered flow in DISPATCHINTERCONNECTORRES. For eligible entered equipment ratings, use the SPD ID and interval in NETWORK_REALTIMERATING and check alternate rating definitions in PUBLIC_TER_DAILY. AEMO describes the ratings file as updated on change. Units, equipment end, contingency level and data vintage matter. These are source leads unless the point register records a measured cross-check. Free-registration services, participant systems and commercial data have no role in the measured coverage. [AEMO equipment ratings](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/transmission-equipment-ratings) · [AEMO publication triggers](https://tech-specs.docs.public.aemo.com.au/Content/TSP_TechnicalSpecificationPortal/EMMSDMTableTriggers.htm)

The [source manifest](sources.json) gives anonymous retrieval URLs, exact archive members and SHA-256 hashes. The case extraction stores only the first compressed member; its archive slice and expanded XML have separate hashes. Rebuild from the repository root with `python scripts/rhs_inventory.py`.
"""
    write(OUT/"README.md",readme.encode())
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    build()
