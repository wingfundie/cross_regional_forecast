"""On-demand public snapshots with measured receipt. Never rewrites issued scenarios."""
from __future__ import annotations
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import ssl
from urllib.parse import urljoin
from urllib.request import urlopen, Request
import zipfile

import numpy as np
import pandas as pd
from .core import CONNECTORS, connector_name


def fetch(url, output):
    started = datetime.now(timezone.utc).isoformat()
    with urlopen(Request(url,headers={"User-Agent":"NEM-Conditional-Regimes/0.1 public research"}),context=ssl.create_default_context(),timeout=30) as r:
        blob = r.read(50_000_001)
    if len(blob)>50_000_000:raise ValueError("Public snapshot exceeds 50 MB bound")
    completed=datetime.now(timezone.utc).isoformat()
    hash_=hashlib.sha256(blob).hexdigest()
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/(hash_+".bin")).write_bytes(blob)
    return blob,{"url":url,"sha256":hash_,"retrieval_started":started,"received":completed,"receipt_completed":completed,
                 "availability_evidence":"measured_receipt"}


def latest_grid(connector="VNI",direction="forward",output="regime_inputs"):
    name=connector_name(connector)
    if direction not in {"forward","reverse"}:raise ValueError("Unknown direction")
    base="https://nemweb.com.au/Reports/Current/DispatchIS_Reports/"
    listing,_=fetch(base,output)
    links=[urljoin(base,x) for x in re.findall(r'HREF=["\']([^"\']+)',listing.decode(),re.I) if re.search(r"PUBLIC_DISPATCHIS_\d{12}.*\.zip$",x,re.I)]
    if not links:raise ValueError("No current dispatch snapshots")
    url=max(links,key=lambda x:re.search(r"DISPATCHIS_(\d{12})",x)[1])
    blob,record=fetch(url,output)
    tables={};schemas={}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.namelist():
            if not member.lower().endswith(".csv"):continue
            for row in csv.reader(io.StringIO(z.read(member).decode("utf-8-sig"))):
                if len(row)<4:continue
                key=(row[1],row[2],row[3])
                if row[0]=="I":schemas[key]=row[4:]
                elif row[0]=="D" and key in schemas and row[1]=="DISPATCH" and row[2]=="REGIONSUM":
                    tables.setdefault("regions",[]).append(dict(zip(schemas[key],row[4:])))
    frame=pd.DataFrame(tables.get("regions",[]))
    if frame.empty:raise ValueError("Regional dispatch table missing")
    for col in ("INTERVENTION","RUNNO"):frame[col]=pd.to_numeric(frame[col])
    frame=frame.sort_values(["SETTLEMENTDATE","REGIONID","INTERVENTION","RUNNO"]).drop_duplicates("REGIONID",keep="last").set_index("REGIONID")
    _,a,b=CONNECTORS[name]
    if direction=="reverse":a,b=b,a
    conditions={};inputs=[]
    issued=pd.to_datetime(re.search(r"DISPATCHIS_(\d{12})",url)[1],format="%Y%m%d%H%M").tz_localize("Australia/Brisbane").isoformat()
    for side,region in (("source",a),("sink",b)):
        row=frame.loc[region]
        wind=float(row["SS_WIND_CLEAREDMW"]);solar=float(row["SS_SOLAR_CLEAREDMW"]);demand=float(row["TOTALDEMAND"])
        for variable,value in ((side+"_vre",wind+solar),(side+"_demand",demand),(side+"_residual",demand-wind-solar),
                               (side+"_available_generation",float(row["AVAILABLEGENERATION"]))):
            conditions[variable]=value
            inputs.append({**record,"source":"AEMO","product":"DISPATCHIS","run_id":url.rsplit("/",1)[-1],"issue":issued,
                           "delivery":pd.Timestamp(row["SETTLEMENTDATE"]).tz_localize("Australia/Brisbane").isoformat(),
                           "variable":variable,"value":value,"region":region,"coherence_group":"AEMO:DISPATCHIS:regions","max_age_hours":1,
                           "information_class":"observed_grid","units":"MW"})
    result={"conditions":conditions,"inputs":inputs,"information_class":"observed_grid",
            "note":"Latest observed grid conditions. Applying these to another delivery time creates a scenario assumption, not an issued demand/VRE forecast.",
            "origin":datetime.now(timezone.utc).isoformat()}
    (Path(output)/"latest_grid.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result


def weather(connector="VNI",direction="forward",run=None,delivery=None,output="regime_inputs"):
    from urllib.parse import urlencode
    if run is None or delivery is None:raise ValueError("Weather collection requires explicit UTC model run and delivery")
    run=pd.Timestamp(run);delivery=pd.Timestamp(delivery)
    if run.tzinfo is None or delivery.tzinfo is None:raise ValueError("Weather run/delivery require timezones")
    if delivery.minute not in (0,30) or delivery.second:raise ValueError("Weather delivery must be a half-hour boundary")
    if delivery<run or delivery-run>pd.Timedelta(days=10):raise ValueError("Requested weather delivery must be within this collector's 10-day coverage")
    name=connector_name(connector);_,a,b=CONNECTORS[name]
    if direction=="reverse":a,b=b,a
    # Same three demand/corridor/renewable locations per region as the historical contract.
    sites={"NSW1":[(-33.87,151.21),(-30.51,151.67),(-32.25,148.60)],
           "QLD1":[(-27.47,153.03),(-27.88,151.27),(-23.38,150.51)],
           "VIC1":[(-37.81,144.96),(-38.13,141.63),(-36.71,142.20)],
           "SA1":[(-34.93,138.60),(-34.,139.08),(-33.20,138.61)],
           "TAS1":[(-42.88,147.33),(-41.10,146.83),(-40.68,144.75)]}
    locations=sites[a]+sites[b]
    lat=[x[0] for x in locations];lon=[x[1] for x in locations]
    params={"latitude":",".join(map(str,lat)),"longitude":",".join(map(str,lon)),"hourly":"temperature_2m,wind_speed_100m,shortwave_radiation,cloud_cover",
            "models":"ecmwf_ifs","run":run.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M"),"forecast_days":10,"timezone":"UTC","wind_speed_unit":"ms"}
    url="https://single-runs-api.open-meteo.com/v1/forecast?"+urlencode(params)
    blob,record=fetch(url,output);payload=json.loads(blob)
    if not isinstance(payload,list) or len(payload)!=6:raise ValueError("Incomplete coherent six-site weather run")
    selected=[]
    for item in payload:
        times=pd.to_datetime(item["hourly"]["time"],utc=True)
        expected={"temperature_2m":"°C","wind_speed_100m":"m/s","shortwave_radiation":"W/m²","cloud_cover":"%"}
        if any(item.get("hourly_units",{}).get(k)!=v for k,v in expected.items()):raise ValueError("Weather units differ from the condition contract")
        target=delivery.tz_convert("UTC")
        lo=np.flatnonzero(times==target.floor("h"));hi=np.flatnonzero(times==target.ceil("h"))
        if not len(lo) or not len(hi):raise ValueError("Requested delivery absent from this run")
        fraction=(target-target.floor("h")).total_seconds()/3600
        values={}
        for key,series in item["hourly"].items():
            if key=="time":continue
            a,b=series[int(lo[0])],series[int(hi[0])]
            if a is None or b is None:raise ValueError("Missing weather value in coherent run")
            # Match the historical contract: interpolate instantaneous fields; preserve radiation-hour energy.
            values[key]=float(b) if key=="shortwave_radiation" else float(a)*(1-fraction)+float(b)*fraction
        selected.append(values)
    conditions={"temperature_max":max(float(x["temperature_2m"]) for x in selected),
                "source_temperature":float(np.mean([x["temperature_2m"] for x in selected[:3]])),
                "sink_temperature":float(np.mean([x["temperature_2m"] for x in selected[3:]])),
                "corridor_wind_ms":float(np.mean([selected[i]["wind_speed_100m"] for i in (1,4)])),
                "corridor_radiation_wm2":float(np.mean([selected[i]["shortwave_radiation"] for i in (1,4)])),
                "corridor_cloud_pct":float(np.mean([selected[i]["cloud_cover"] for i in (1,4)]))}
    inputs=[{**record,"source":"Open-Meteo","product":"ECMWF_IFS_single_run","run_id":run.isoformat(),"issue":run.isoformat(),
             "delivery":delivery.isoformat(),"variable":key,"value":value,"coherence_group":"weather:region_pair","max_age_hours":48,
             "information_class":"issued_weather_forecast","region":a if key.startswith("source_") else b if key.startswith("sink_") else None,
             "regions":[a,b],"units":"C" if "temperature" in key else "m/s" if key=="corridor_wind_ms" else "W/m2" if key=="corridor_radiation_wm2" else "%"} for key,value in conditions.items()]
    return {"conditions":conditions,"inputs":inputs,"information_class":"issued_weather_forecast",
            "note":"One coherent six-site run using the historical feature contract. Issued model forecasts and realised reanalysis remain separate information classes."}
