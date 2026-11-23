"""Event-scoped public offer revisions; preserve native identities and rebid reasons."""
from __future__ import annotations

import csv
import io
import json
import shutil
import zipfile
from pathlib import Path
from urllib.parse import unquote

import numpy as np
import pandas as pd
import polars as pl
import hashlib
import requests

from nemic import ingest
from nemic.common import links
from nemic.constraint_ingest import download_entry

from .core import BIND, ROOT, json_write, load, save, sha

PARSER_CONTRACT = "native-sample-v2"


def verified_prior_offers(c):
    """Reuse complete parsed outputs only after verifying their recorded hashes."""
    manifest=c["_execution"]/"manifests/offers.json"
    metadata=c["_data"]/"offer_sources.json";rows=c["_data"]/"offer_revisions.parquet"
    if not all(p.is_file() for p in [manifest,metadata,rows]):return {},pd.DataFrame()
    recorded=json.loads(manifest.read_text(encoding="utf-8")).get("outputs",{})
    if any(recorded.get(str(p))!=sha(p) for p in [metadata,rows]):return {},pd.DataFrame()
    previous=json.loads(metadata.read_text(encoding="utf-8"))
    if previous.get("parser_contract","native-sample-v2")!=PARSER_CONTRACT:return {},pd.DataFrame()
    sources={(s["month"],s["table"]):s for s in previous["sources"] if s["status"]=="parsed"}
    return sources,pd.read_parquet(rows)


def prior_offer_part(sources,rows,month,table,job):
    source=sources.get((month,table))
    if source is None or source["days"]!=sorted(job["days"]) or source["duids"]!=sorted(job["duids"]):return None
    frame=(rows.iloc[:0].copy() if source["selected_rows"]==0 else
           rows[rows.source_month.eq(month)&rows.source_table.eq(table)&rows.source_sha256.eq(source["sha256"])].copy())
    if len(frame)!=source["selected_rows"]:return None
    record=dict(source,verified_output_cache=True,cache_read_utc=pd.Timestamp.now(tz="UTC").isoformat())
    return record,frame


def csv_streams(archive):
    for member in archive.infolist():
        if member.filename.lower().endswith(".zip"):
            with archive.open(member) as f:
                with zipfile.ZipFile(io.BytesIO(f.read())) as inner:yield from csv_streams(inner)
        elif member.filename.lower().endswith(".csv"):
            yield archive.open(member)


def period_selected(path,duids,days):
    """Stream native period rows with quote-aware CSV filtering before materialising."""
    parts=[];scratch=Path(path).with_suffix(".selected-scan.csv")
    with zipfile.ZipFile(path) as archive:
        for file in csv_streams(archive):
            schema=None;skip=0
            with file:
                # Period files have one native schema per CSV, without multiline fields.
                for line in file:
                    skip+=1;row=next(csv.reader([line.decode("utf-8-sig")]))
                    if row and row[0]=="I":schema=row[4:];break
                if not schema or not {"DUID","BIDTYPE"}.issubset(schema):continue
                with scratch.open("wb") as target:shutil.copyfileobj(file,target,16<<20)
            try:
                names=["_type","_report","_table","_version"]+schema
                frame=pl.scan_csv(scratch,has_header=False,new_columns=names,infer_schema=False,
                                  truncate_ragged_lines=True,missing_utf8_is_empty_string=True)
                date="INTERVAL_DATETIME" if "INTERVAL_DATETIME" in schema else "SETTLEMENTDATE"
                frame=frame.filter((pl.col("_type")=="D")&pl.col("DUID").is_in(sorted(duids))&
                                   (pl.col("BIDTYPE")=="ENERGY")&pl.col(date).str.slice(0,10).str.replace_all("/","-").is_in(sorted(days)))
                selected=frame.select(schema).collect(engine="streaming").to_pandas()
                selected["source_table"]="BIDPEROFFER_D";parts.append(selected)
            finally:scratch.unlink(missing_ok=True)
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()


def stream_selected(path,duids,days,table):
    if table=="BIDPEROFFER_D":return period_selected(path,duids,days)
    rows=[]
    with zipfile.ZipFile(path) as archive:
        for file in csv_streams(archive):
            schemas={}
            with io.TextIOWrapper(file,encoding="utf-8-sig",errors="replace",newline="") as text:
                for row in csv.reader(text):
                    if len(row)<4:continue
                    key=tuple(row[1:4])
                    if row[0]=="I":schemas[key]=row[4:];continue
                    if row[0]!="D" or key not in schemas:continue
                    header=schemas[key]
                    if "DUID" not in header or "BIDTYPE" not in header:continue
                    vals=row[4:];di=header.index("DUID");bi=header.index("BIDTYPE")
                    if len(vals)!=len(header) or vals[di] not in duids or vals[bi]!="ENERGY":continue
                    fields=dict(zip(header,vals))
                    valid=fields.get("INTERVAL_DATETIME") or fields.get("SETTLEMENTDATE") or ""
                    if valid[:10].replace("/","-") in days:
                        fields["source_table"]=table;rows.append(fields)
    return pd.DataFrame(rows)


def sample_days(event):
    return {(event.start.normalize()+pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in [-7,-1,0,1,7]}|{(event.end.normalize()+pd.Timedelta(days=k)).strftime("%Y-%m-%d") for k in [-1,0,1]}


def case_offer_rows(offers,units,event):
    f=offers[offers.DUID.isin(units)].copy()
    valid=f.get("INTERVAL_DATETIME",pd.Series("",index=f.index)).fillna("").replace("",np.nan)
    valid=valid.fillna(f.get("SETTLEMENTDATE",pd.Series("",index=f.index)))
    return f[valid.str[:10].str.replace("/","-",regex=False).isin(sample_days(event))]


def run(c):
    cases=load(c,"case_selection");crosswalk=load(c,"asset_constraint_crosswalk");cp=load(c,"equation_cp_terms")
    duid=pd.read_parquet(BIND/"standing/DUDETAILSUMMARY.parquet")
    duid["START_DATE"]=pd.to_datetime(duid.START_DATE,errors="coerce")
    duid["END_DATE"]=pd.to_datetime(duid.END_DATE.astype(str).str.replace(r"^9999.*","2262-04-01",regex=True),errors="coerce")
    jobs={};case_duids={};unit_sources={}
    for e in cases.itertuples():
        equations=set(crosswalk.loc[crosswalk.asset.eq(e.asset),"constraint"])
        terms=cp[cp.GENCONID.isin(equations)&cp.EFFECTIVEDATE.le(e.start)].copy()
        if len(terms):
            # One complete native factor version per equation at event start, retaining all its terms.
            version=terms[["GENCONID","EFFECTIVEDATE","VERSIONNO"]].drop_duplicates().sort_values(["EFFECTIVEDATE","VERSIONNO"]).drop_duplicates("GENCONID",keep="last")
            terms=terms.merge(version,on=["GENCONID","EFFECTIVEDATE","VERSIONNO"],how="inner")
        points=set(terms.CONNECTIONPOINTID)
        active=duid[duid.START_DATE.le(e.end)&(duid.END_DATE.isna()|duid.END_DATE.ge(e.start))]
        units=set(active.loc[active.CONNECTIONPOINTID.isin(points),"DUID"])
        unit_sources[e.event_id]="exact-version energy equation factors"
        if e.asset=="CANBERRA/LINE/6":
            units |= set(active.loc[active.DUID.str.contains("CAPTL|WOODL",case=False,regex=True,na=False),"DUID"])
            unit_sources[e.event_id]="exact-version energy equation factors plus documented Capital/Woodlawn candidates; top-20 cap applies"
        # Include at most the 20 largest equation-factor units, deterministic, documented event sample.
        factor=terms.groupby("CONNECTIONPOINTID").FACTOR.apply(lambda x:x.abs().max()).sort_values(ascending=False)
        ranked=active[active.DUID.isin(units)].assign(weight=lambda x:x.CONNECTIONPOINTID.map(factor)).sort_values(["weight","DUID"],ascending=[False,True]).drop_duplicates("DUID")
        units=set(ranked.DUID.head(20));case_duids[e.event_id]=sorted(units)
        # Daily energy prices apply from 04:00 NEM time: include preceding trading day.
        for date in sample_days(e):
            day=pd.Timestamp(date);month=str(day.to_period("M"));job=jobs.setdefault(month,{"days":set(),"duids":set()})
            job["days"].add(date);job["duids"] |= units
    previous_sources,previous_rows=verified_prior_offers(c)
    revisions=[];sources=[]
    raw=c["_data"]/"raw/offers";raw.mkdir(parents=True,exist_ok=True)
    for month,job in sorted(jobs.items()):
        if not job["duids"]:continue
        print(f"offers {month}: {len(job['duids'])} units, {len(job['days'])} dates",flush=True)
        folder=ingest.archive_dir(pd.Timestamp(month+"-01"))
        urls=None
        for table in ["BIDDAYOFFER_D","BIDPEROFFER_D"]:
            reused=prior_offer_part(previous_sources,previous_rows,month,table,job)
            if reused is not None:
                source,frame=reused;sources.append(source)
                if len(frame):revisions.append(frame)
                continue
            candidates=list((ROOT/"data/raw").glob(f"*{table}*{month.replace('-','')}010000.zip"))
            path=candidates[0] if candidates else None
            source={"month":month,"table":table,"days":sorted(job["days"]),"duids":sorted(job["duids"])}
            try:
                if path is None:
                    if shutil.disk_usage(raw).free<c["limits"]["minimum_free_bytes"]:raise RuntimeError("Insufficient free disk space")
                    if urls is None:urls=links(folder)
                    url=next(u for u in urls if ingest.is_table(u,table))
                    path=download_entry({"url":url},{"file_compressed_bytes":c["limits"]["download_file_bytes"],"batch_decompressed_bytes":10_000_000_000},raw)
                    source["url"]=url
                else:
                    source["url"]=folder+path.name.replace("#","%23")
                source.update(sha256=sha(path),bytes=path.stat().st_size,received_utc=pd.Timestamp.now(tz="UTC").isoformat(),historical_receipt_verified=False)
                cache=c["_data"]/"offer_samples";cache.mkdir(exist_ok=True)
                signature=hashlib.sha256(json.dumps([source["sha256"],sorted(job["duids"]),sorted(job["days"]),PARSER_CONTRACT]).encode()).hexdigest()
                saved=cache/(signature+".parquet")
                frame=pd.read_parquet(saved) if saved.exists() else stream_selected(path,job["duids"],job["days"],table)
                if not saved.exists():frame.to_parquet(saved,index=False)
                source["selected_rows"]=len(frame);source["status"]="parsed"
                if len(frame):
                    frame["source_sha256"]=source["sha256"];frame["source_month"]=month
                    revisions.append(frame)
                # Source hash + coverage retained before deleting campaign-owned temporary monthly archive.
                sources.append(source);json_write(c["_data"]/"offer_sources.json",{"sources":sources,"case_duids":case_duids})
                if path.parent.resolve()==raw.resolve():path.unlink()
            except (StopIteration, requests.RequestException) as exc:
                source.update(status="unavailable",error=repr(exc));sources.append(source)
                json_write(c["_data"]/"offer_sources.json",{"sources":sources,"case_duids":case_duids})
    offers=pd.concat(revisions,ignore_index=True,sort=False) if revisions else pd.DataFrame(columns=["DUID","source_table","source_month"])
    save(c,"offer_revisions",offers)
    rows=[]
    for e in cases.itertuples():
        units=case_duids[e.event_id];g=case_offer_rows(offers,units,e)
        for unit,part in g.groupby("DUID"):
            day=part[part.source_table.eq("BIDDAYOFFER_D")].copy()
            if len(day):
                day["offer_time"]=pd.to_datetime(day.get("OFFERDATE"),errors="coerce")
                day=day[day.offer_time.ge(e.start-pd.Timedelta(hours=48))&day.offer_time.le(e.end+pd.Timedelta(hours=48))]
            reasons=day.get("REBIDEXPLANATION",pd.Series(dtype=str)).dropna().astype(str)
            prices=[p for p in day if p.startswith("PRICEBAND")]
            changed=[]
            for col in prices:
                v=pd.to_numeric(day.sort_values("offer_time")[col],errors="coerce")
                if v.nunique()>1:changed.append(col)
            rows.append({"asset":e.asset,"event_id":e.event_id,"DUID":unit,"daily_revisions":len(day),
                         "period_records":int(part.source_table.eq("BIDPEROFFER_D").sum()),
                         "changed_price_bands":"|".join(changed),"rebid_reasons":" | ".join(reasons.unique()[:8]),
                         "stack_counterfactual":"withheld: no verified historical receipt/offer pairing gate",
                         "unit_selection_source":unit_sources[e.event_id],"interpretation":"records on declared case sample dates only; observed revisions, no strategic-intent attribution"})
    summary=pd.DataFrame(rows,columns=["asset","event_id","DUID","daily_revisions","period_records","changed_price_bands","rebid_reasons","stack_counterfactual","unit_selection_source","interpretation"])
    save(c,"offer_summary",summary)
    json_write(c["_data"]/"offer_sources.json",{"sources":sources,"case_duids":case_duids,"unit_selection_sources":unit_sources,"parser_contract":PARSER_CONTRACT,
          "method":"top 20 energy-equation-sensitive DUIDs per case; start/restoration with preceding and following trading-day dates, and ±7-day comparison dates; all selected revisions retained",
          "dispatch_stack_gate":"withheld until native offer identities and receipt/effective timing pass validation"})
    return {"archives_parsed":sum(s["status"]=="parsed" for s in sources),"archives_unavailable":sum(s["status"]=="unavailable" for s in sources),"offer_rows":len(offers),"unit_case_summaries":len(summary)}
