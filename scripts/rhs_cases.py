"""Bounded, interval-member replay of three historical NEMDE equations."""
from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nemic.common import session

RAW = ROOT / "data/rhs_replay/cases"
OUT = ROOT / "reports/rhs_replay/cases"
BASE = "https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/2026/NEMDE_2026_02/NEMDE_Market_Data/NEMDE_Files/"
BUDGET = 1_300_000_000
NET = session()


def save(path, data):
    usage = sum(p.stat().st_size for root in [RAW, OUT] for p in root.rglob("*") if p.is_file())
    if usage + len(data) + 1_000_000 > BUDGET:
        raise ValueError("Replay sub-budget exceeded")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def byte_range(url, spec):
    for attempt in range(3):
        try:
            with NET.get(url, headers={"Range": f"bytes={spec}"}, timeout=(20, 90), stream=True) as response:
                response.raise_for_status()
                if response.status_code != 206:
                    raise ValueError(f"Range unsupported: {response.status_code}")
                bounds, total = response.headers["Content-Range"].split("/")
                start, end = map(int, bounds.split()[-1].split("-"))
                if (end - start + 1 > 50_000_000 or (not spec.startswith("-") and bounds != f"bytes {spec}")):
                    raise ValueError(f"Unexpected HTTP range {bounds}")
                body = response.content
                assert len(body) == end - start + 1
                return start, int(total), body
        except Exception:
            if attempt == 2:
                raise


def selected_files(day, numbers):
    """Use the ZIP central directory and one contiguous HTTP range per run of needed members."""
    url = BASE + f"NemSpdOutputs_{day}_loaded.zip"
    dirname = RAW / day
    tail = dirname / "zip_tail.bin"
    if not tail.exists():
        start, total, data = byte_range(url, "-131072")
        save(dirname / "offset.txt", str(start).encode())
        save(tail, data)
    buffer = io.BytesIO()
    buffer.seek(int((dirname / "offset.txt").read_text()))
    buffer.write(tail.read_bytes())
    with ZipFile(buffer) as archive:
        all_info = sorted(archive.infolist(), key=lambda x: x.header_offset)
        info = [i for i in all_info if any(re.search(f"{day}{n:03d}0[0-9]*\\.loaded", i.filename, re.I) for n in numbers)]
        if not info:
            print([i.filename for i in all_info[:4]])
            raise ValueError("No matching files")
        first, last = info[0], info[-1]
        low = first.header_offset
        high = last.header_offset + len(last.filename.encode()) + len(last.extra) + 100 + last.compress_size
        next_index = all_info.index(last) + 1
        if next_index < len(all_info):
            high = all_info[next_index].header_offset - 1
        chunkfile = dirname / f"range_{low}_{high}.bin"
        if not chunkfile.exists():
            _, _, block = byte_range(url, f"{low}-{high}")
            save(chunkfile, block)
        buffer.seek(low)
        buffer.write(chunkfile.read_bytes())
        for item in info:
            content = archive.read(item)
            if content.startswith(b"PK"):
                with ZipFile(io.BytesIO(content)) as nested:
                    content = nested.read(nested.namelist()[0])
            yield item.filename, content



EQUATIONS = ["DATASNAP_DFS_NSYD", "N::Q_NIL_KC", "T^V_NIL_9"]
WINDOWS = [
    ("W1", "20260201", 1, "First complete NEMDE market-day two-hour block in February, before first N::Q_NIL_KC economic bind."),
    ("W2", "20260215", 97, "Largest binding count in a mixed two-hour block before the final event day; excludes the 24/24 binding block."),
    ("W3", "20260219", 73, "Final February date with a N::Q_NIL_KC economic bind. Select the two-hour block containing the event."),
]
TZ = timezone(timedelta(hours=10))
MMS = "https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/MMSDM_2026_02/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23DISPATCHCONSTRAINT%23FILE01%23202602010000.zip"


def mms_solutions():
    path = next((ROOT / "data/constraint_pilot/raw").glob("*DISPATCHCONSTRAINT*202602*"))
    cache = RAW / "validation.parquet"
    columns = ["SETTLEMENTDATE", "RUNNO", "INTERVENTION", "CONSTRAINTID", "RHS", "LHS",
               "MARGINALVALUE", "VIOLATIONDEGREE", "GENCONID_EFFECTIVEDATE", "GENCONID_VERSIONNO"]
    if not cache.exists():
        groups = []
        with ZipFile(path) as archive, archive.open(archive.namelist()[0]) as stream:
            stream.readline()
            header = stream.readline().decode().strip().split(",")
            header[:4] = ["row_type", "package", "table", "schema"]
            for chunk in pd.read_csv(stream, names=header, usecols=columns, chunksize=300000):
                match = chunk.CONSTRAINTID.isin(EQUATIONS) & chunk.INTERVENTION.eq(0) & chunk.RUNNO.eq(1)
                groups.append(chunk.loc[match])
        save(cache, pd.concat(groups).to_parquet(index=False))
    data = pd.read_parquet(cache)
    data["time"] = pd.to_datetime(data.SETTLEMENTDATE).dt.tz_localize(TZ)
    return data.set_index(["time", "CONSTRAINTID"], verify_integrity=True), path


def csv_output(name, records):
    save(OUT / name, pd.DataFrame(records).to_csv(index=False, lineterminator="\n").encode())


def value_of(parent, tag, name):
    child = parent.find(f'.//{tag}[@InitialConditionID="{name}"]')
    if child is None:
        raise KeyError((tag, name))
    return float(child.attrib["Value"])


def region_demand(inputs, region, details):
    """Return the regional fixed demand diagnostic and the sampled constraint R term."""
    region_input = inputs.find(f'.//Region[@RegionID="{region}"]')
    region_period = inputs.find(f'.//RegionPeriod[@RegionID="{region}"]')
    amounts = []
    rhs_components = []
    def component(group, key, amount, **extra):
        rhs_amount = 0.0 if group in ('LOAD', 'NORMALLY_ON_LOAD', 'WDR') else amount
        rhs_components.append(rhs_amount)
        details.append(dict(region=region, component=group, input=key, value=amount, rhs_component=rhs_amount, **extra))
        amounts.append(amount)

    component("InitialDemand", region, value_of(region_input, "RegionInitialCondition", "InitialDemand"))
    component("DemandChange", region, float(region_period.attrib["DF"]))
    component("ADE", region, value_of(region_input, "RegionInitialCondition", "ADE"))
    traders = {t.get("TraderID"): t for t in inputs.findall(".//Trader")}
    for period in inputs.findall(f'.//TraderPeriod[@RegionID="{region}"]'):
        uid = period.get("TraderID")
        trader = traders[uid]
        typ = trader.get("TraderType")
        if typ in ("LOAD", "NORMALLY_ON_LOAD", "WDR"):
            initial = value_of(trader, "TraderInitialCondition", "InitialMW")
            if typ == 'WDR' and initial != 0:
                raise ValueError('Nonzero WDR adjustment unverified for constraint R')
            component(typ, uid, initial if typ == "WDR" else -initial, initial_mw=initial)
    for period in inputs.findall(".//InterconnectorPeriod"):
        if region not in (period.get("FromRegion"), period.get("ToRegion")):
            continue
        assert period.get("MNSP") == "0", "MNSP-specific regional deductions require separate evaluation"
        id_ = period.get("InterconnectorID")
        connector = inputs.find(f'.//Interconnector[@InterconnectorID="{id_}"]')
        model = connector.find('.//LossModel[@LossModelID="' + period.attrib["LossModelID"] + '"]')
        flow = value_of(connector, "InterconnectorInitialCondition", "InitialMW")
        left = -float(model.attrib["LossLowerLimit"])
        share = float(model.attrib["LossShare"])
        if region == period.get("ToRegion"):
            share = 1.0 - share
        for seg in model.findall(".//Segment"):
            right, factor = float(seg.attrib["Limit"]), float(seg.attrib["Factor"])
            span = min(max(flow, left), right) - min(max(0, left), right)
            if span:
                component("allocated_initial_loss_segment", id_, -share * factor * span,
                          initial_mw=flow, left=left, right=right, segment_factor=factor,
                          regional_loss_share=share, used_width=span, loss_model_id=model.attrib["LossModelID"])
            left = right
        if not -float(model.attrib["LossLowerLimit"]) <= flow <= left:
            raise ValueError("Initial flow outside loss model support")
    return sum(amounts), sum(rhs_components)


def scada_value(inputs, id_, typ):
    rows = inputs.findall(f'.//ConstraintScadaData[@SpdType="{typ}"]/ScadaValuesCollection/ScadaValues[@SpdID="{id_}"]')
    if len(rows) != 1 or rows[0].get("Can_Use_Value") != "True":
        raise ValueError(f"Missing or ambiguous measured input {typ}/{id_}")
    return rows[0].attrib


def rhs_terms(inputs, entity, rhs_regions, trace, path=""):
    """Evaluate only operators actually used by these frozen versions. Fail on any extension."""
    x = 0.0
    for term in entity.findall("./RHSTermCollection/RHSTerm"):
        id_, typ = term.attrib["SpdID"], term.attrib["SpdType"]
        factor = float(term.attrib["Multiplier"])
        operation = term.get("Operation", "ADD")
        term_path = f"{path}/{term.attrib['TermID']}"
        metadata = {}
        if typ == "C":
            value = 1.0
        elif typ in ("A", "S", "I"):
            attrs = scada_value(inputs, id_, typ)
            value = float(attrs["Value"])
            metadata = {key: attrs.get(key) for key in
                        ["EMS_Key", "EMS_ID", "EMS_TimeStamp", "EMS_Good", "EMS_Replaced",
                         "Can_Use_Value", "Site_ID", "Grouping_ID", "Data_Flags", "IsReferenced"]}
        elif typ == "R":
            value = rhs_regions[id_]
        elif typ == "X":
            shared = inputs.find(f'.//GenericEquation[@EquationID="{id_}"]')
            if shared is None:
                raise ValueError(f"unresolved shared expression {id_}")
            value = rhs_terms(inputs, shared, rhs_regions, trace, term_path)
        elif typ == "U" and operation == "POW2":
            value = x
        else:
            raise ValueError(f"unsupported {typ}/{id_}")
        if operation == "ADD":
            x += factor * value
        elif operation == "POW2" and typ == "U":
            x = factor * value ** 2
        else:
            raise ValueError(operation)
        trace.append(dict(path=term_path, expression=entity.get("ConstraintID") or entity.attrib["EquationID"],
                          effective_date=entity.attrib["EffectiveDate"], version=entity.attrib["VersionNo"],
                          term_id=term.attrib["TermID"], spd_type=typ, spd_id=id_, operator=operation,
                          multiplier=factor, default=term.get("Default"), value=value, accumulator=x, **metadata))
    return x


def digest(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def verify_regional_publication(replays):
    source = next((ROOT / "data/tables/DISPATCHREGIONSUM").glob("*202602*"))
    data = pd.read_parquet(source, columns=["SETTLEMENTDATE", "REGIONID", "INTERVENTION", "TOTALDEMAND"])
    data = data.loc[data.INTERVENTION.astype(str).eq("0") & data.REGIONID.isin(["NSW1", "QLD1"])].copy()
    data["interval_end"] = pd.to_datetime(data.SETTLEMENTDATE).dt.tz_localize(TZ)
    published = data.set_index(["interval_end", "REGIONID"], verify_integrity=True).TOTALDEMAND
    diagnostics = []
    for row in replays:
        if row["equation"] != "N::Q_NIL_KC":
            continue
        for region, suffix in [("NSW1", "nsw"), ("QLD1", "qld")]:
            total = float(published.loc[(pd.Timestamp(row["interval_end"]), region)])
            fixed = row["fixed_" + suffix]
            rhs_region = row["rhs_region_" + suffix]
            if abs(total - fixed) > 0.0051:
                raise ValueError("Public total demand mismatch")
            diagnostics.append(dict(interval_end=row["interval_end"], window=row["window"], region=region,
                public_totaldemand=total, rebuilt_fixed_demand=fixed, rebuilt_rhs_region=rhs_region,
                public_total_minus_rhs_region=total - rhs_region))
    csv_output("regional_validation.csv", diagnostics)
    return source


def run():
    selection = [dict(window=w, first=(datetime.strptime(day, "%Y%m%d").replace(tzinfo=TZ)
                                  + timedelta(hours=4, minutes=n*5)).isoformat(),
                      intervals=24, reason=reason) for w, day, n, reason in WINDOWS]
    save(OUT / "selection.json", json.dumps(dict(equations=EQUATIONS, windows=selection,
         screening="Historical marginal values for run 1 intervention 0 only; two-hour blocks aligned to even NEM clock hours. This event-enriched sample cannot estimate event prevalence."), indent=2).encode())
    mms, mms_path = mms_solutions()
    results, terms, parts, members = [], [], [], []
    for window, day, first, _ in WINDOWS:
        for name, body in selected_files(day, range(first, first + 24)):
            tree = ET.fromstring(body)
            inputs = tree.find("NemSpdInputs")
            assert inputs.find("Case").attrib["Intervention"] == "False"
            outputs = tree.find("NemSpdOutputs")
            dt = pd.Timestamp(inputs.find(".//Period").attrib["PeriodID"])
            base = dict(interval_end=dt.isoformat(), window=window)
            members.append(dict(**base, url=BASE + f"NemSpdOutputs_{day}_loaded.zip", member=name,
                                bytes=len(body), sha256=hashlib.sha256(body).hexdigest()))
            region_parts = []
            demands = {key: region_demand(inputs, key, region_parts) for key in ["NSW1", "QLD1"]}
            fixed = {k: pair[0] for k, pair in demands.items()}
            rhs_regions = {k: pair[1] for k, pair in demands.items()}
            parts.extend(dict(**base, **part) for part in region_parts)
            for region, computed in fixed.items():
                reported = float(outputs.find(f'.//RegionSolution[@RegionID="{region}"][@Intervention="0"]').get("FixedDemand"))
                if abs(reported - computed) > 0.0051:
                    raise ValueError(f"Regional fixed demand discrepancy {dt} {region} {computed} {reported}")
            for eq in EQUATIONS:
                meta = dict(**base, equation=eq)
                entity = inputs.find(f'.//GenericConstraint[@ConstraintID="{eq}"]')
                period = inputs.find(f'.//GenericConstraintPeriod[@ConstraintID="{eq}"][@Intervention="0"]')
                blocked = inputs.find(f'.//BlockedGenericConstraint[@ConstraintID="{eq}"]') is not None
                assert period is not None and not blocked
                audit = []
                rhs = rhs_terms(inputs, entity, rhs_regions, audit)
                terms.extend(dict(**meta, **v) for v in audit)
                demand_id = {"DATASNAP_DFS_NSYD": "N_SYDNEY_LOAD", "N::Q_NIL_KC": "TERRANORA_LOAD"}.get(eq)
                d = float(scada_value(inputs, demand_id, "A")["Value"]) if demand_id else None
                c = b = a = None
                if eq == "DATASNAP_DFS_NSYD":
                    a,b,c = 10000.,1.,0.
                elif eq == "N::Q_NIL_KC":
                    i = float(scada_value(inputs, "N-Q-MNSP1", "I")["Value"])
                    a = 1383 - .0239 * rhs_regions["NSW1"] + .0524 * rhs_regions["QLD1"] - .001 * i**2
                    b,c = -.6394 - .002*i, -.001
                if d is not None:
                    assert abs((a+b*d+c*d*d) - rhs) < 1e-8
                solution = outputs.find(f'.//ConstraintSolution[@ConstraintID="{eq}"][@Intervention="0"]')
                solved = mms.loc[(dt, eq)]
                assert (solution is not None and entity.attrib["Version"] == solution.attrib["Version"] == period.attrib["Version"]
                        and int(entity.attrib["VersionNo"]) == solved.GENCONID_VERSIONNO
                        and pd.Timestamp(entity.attrib["EffectiveDate"]).tz_localize(None) == pd.Timestamp(solved.GENCONID_EFFECTIVEDATE))
                assert abs(float(solution.attrib["RHS"])-solved.RHS)<0.000006
                if abs(rhs-float(solution.attrib["RHS"])) > 1e-6:
                    raise ValueError(f"Unreconciled independent replay {eq} {dt} {rhs} {solution.attrib}")
                tracks = entity.findall(".//ConstraintTrkItem")
                results.append(dict(**meta, relation=entity.attrib["Type"], version=entity.attrib["Version"],
                     set_ids="|".join(sorted({t.attrib["GenConSetID"] for t in tracks})),
                     invocation_ids="|".join(sorted({t.attrib["Invocation_ID"] for t in tracks})),
                     invoked=bool(tracks), blocked=blocked, runno=1, intervention=0, rhs_replay=rhs,
                     rhs_reference=solved.RHS, rhs_case=float(solution.attrib["RHS"]), lhs=solved.LHS,
                     marginal_value=solved.MARGINALVALUE, violation=solved.VIOLATIONDEGREE, error=rhs-solved.RHS,
                     demand_spd=demand_id, demand_mw=d, proxy_constant=a, proxy_linear=b, proxy_quadratic=c,
                     rhs_region_nsw=rhs_regions["NSW1"], rhs_region_qld=rhs_regions["QLD1"],
                     fixed_nsw=fixed["NSW1"], fixed_qld=fixed["QLD1"]))
    if len(results)!=216 or len(members)!=72 or len({row['interval_end'] for row in members})!=72:
        raise ValueError("Interval coverage mismatch")
    csv_output("terms.csv",terms)
    csv_output("regional_demand_components.csv",parts)
    csv_output("case_members.csv",members)
    csv_output("replay.csv",results)
    region_source = verify_regional_publication(results)
    df=pd.DataFrame(results)
    summary = df.groupby("equation").agg(rows=("error","size"),max_error=("error",lambda s:s.abs().max()),
                 mae=("error",lambda s:s.abs().mean()), economic_bind=("marginal_value",lambda s:s.ne(0).sum()))
    csv_output("summary.csv",summary.reset_index().to_dict("records"))
    sources = [dict(source=mms_path.name, sha256=digest(mms_path), bytes=mms_path.stat().st_size, url=MMS,
                    scope="existing complete monthly ZIP; read only")]
    sources.append(dict(source=region_source.name, sha256=digest(region_source), bytes=region_source.stat().st_size,
                        url=MMS.replace("DISPATCHCONSTRAINT", "DISPATCHREGIONSUM"), scope="existing parsed parquet; validation rows only"))
    for path in sorted(RAW.glob("*/*.bin")):
        sources.append(dict(source=str(path.relative_to(RAW)), sha256=digest(path), bytes=path.stat().st_size,
                       url=BASE+f"NemSpdOutputs_{path.parent.name}_loaded.zip", scope="source byte range"))
    csv_output("source_hashes.csv",sources)
    print(summary)


if __name__ == "__main__":
    run()
