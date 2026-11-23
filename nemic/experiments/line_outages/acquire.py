"""Supplement the old interconnector-scoped archive with required line-specific equations."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import pandas as pd
import polars as pl
from requests import HTTPError

from nemic.constraint_ingest import _table_rows, download_entry
from nemic.experiments.nos_regime.binding import archive_url, physical

from .core import BIND, OLD, ROOT, STUDIES, json_write, load, save, sha


def existing(table):
    paths=[BIND/"standing"/(table+".parquet")]+[ROOT/f"data/constraint_{s}_2y/standing/{table}.parquet" for s in STUDIES.values()]
    parts=[pd.read_parquet(p) for p in paths if p.exists()]
    return pd.concat(parts,ignore_index=True).drop_duplicates() if parts else pd.DataFrame()


def fetch(c,table,month,predicate,records):
    month=pd.Period(month,freq="M");raw=c["_data"]/"raw/supplements";raw.mkdir(parents=True,exist_ok=True)
    target=c["_data"]/"supplements"/f"{table}_{month}.parquet";target.parent.mkdir(exist_ok=True)
    signature=target.with_suffix(".json")
    wanted=[sorted(v.cell_contents) for v in (predicate.__closure__ or ()) if isinstance(v.cell_contents,set)]
    request=hashlib.sha256(json.dumps(wanted,sort_keys=True).encode()).hexdigest()
    if target.exists() and signature.exists():
        meta=json.loads(signature.read_text())
        valid_cache=meta["sha256"]==sha(target)
        if valid_cache and meta.get("request_signature")==request:
            records.append(meta);return pd.read_parquet(target)
        old_values=meta.get("requested_values",[])
        if valid_cache and len(wanted)==len(old_values)==1 and set(wanted[0]).issubset(old_values[0]):
            key="GENCONSETID" if table.startswith("GENCONSET") else "CONSTRAINTID" if table=="DISPATCHCONSTRAINT" else "GENCONID"
            frame=pd.read_parquet(target,filters=[(key,"in",wanted[0])] if meta.get("selected_rows",0)>0 else None)
            records.append({**meta,"cache_reuse":"verified superset; filtered to required values",
                            "analysis_requested_values":wanted,"analysis_selected_rows":len(frame)})
            return frame
    url=archive_url(month,table,"dvd" if month<pd.Period("2024-08") else "archive")
    print(f"supplement {table} {month}",flush=True)
    # Reuse original source archives when present; only campaign-owned scratch is deleted.
    name=url.rsplit("/",1)[-1].replace("%23","#")
    paths=[ROOT/"data/raw"/name]+[ROOT/f"data/constraint_{s}_2y/raw"/name for s in STUDIES.values()]
    path=next((p for p in paths if p.exists()),None)
    if path is None:
        if shutil.disk_usage(raw).free<c["limits"]["minimum_free_bytes"]:raise RuntimeError("Insufficient free disk space")
        path=download_entry({"url":url},{"file_compressed_bytes":c["limits"]["download_file_bytes"],"batch_decompressed_bytes":10_000_000_000},raw)
    raw_hash=sha(path)
    if table=="DISPATCHCONSTRAINT":
        # Native streaming filtering avoids Python dictionaries for millions of unrelated equations.
        parts=[];ids=sorted(set(value for group in wanted for value in group))
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                if not member.filename.lower().endswith(".csv"):continue
                with archive.open(member) as file:
                    schema=None;skip=0
                    for line in file:
                        skip+=1;row=next(csv.reader([line.decode("utf-8-sig")]))
                        if row and row[0]=="I":schema=row[4:];break
                    if not schema or "CONSTRAINTID" not in schema:continue
                scratch=raw/(path.stem+".csv")
                try:
                    with archive.open(member) as source,scratch.open("wb") as output:shutil.copyfileobj(source,output,16<<20)
                    names=["_record_type","_report","_table","_schema_version"]+schema
                    scanned=pl.scan_csv(scratch,has_header=False,skip_rows=skip,new_columns=names,infer_schema=False,
                        ignore_errors=False,truncate_ragged_lines=True,missing_utf8_is_empty_string=True)
                    selected=scanned.filter((pl.col("_record_type")=="D")&pl.col("CONSTRAINTID").is_in(ids)).select(schema).collect(engine="streaming")
                    parts.append(selected.to_pandas())
                finally:
                    if scratch.exists() and scratch.parent.resolve()==raw.resolve():scratch.unlink()
        frame=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
    else:frame=_table_rows(path,table,value_filter=predicate)
    frame.to_parquet(target,index=False)
    meta={"table":table,"month":str(month),"url":url,"raw_sha256":raw_hash,"sha256":sha(target),
          "selected_rows":len(frame),"request_signature":request,"requested_values":wanted,
          "received_utc":pd.Timestamp.now(tz="UTC").isoformat(),"selection":"required selected-line families/equations only"}
    json_write(signature,meta);records.append(meta)
    json_write(c["_data"]/"supplement_sources.json",{"records":records})
    # Retain local source cache for exact scoped replays; cleanup can use the recorded hash and coverage.
    return frame


def optional_fetch(c,table,month,predicate,records):
    """An unavailable historical table is a provenance gap, never a zero observation."""
    try:
        return fetch(c,table,month,predicate,records)
    except HTTPError as exc:
        if exc.response is None or exc.response.status_code!=404:raise
        records.append({"table":table,"month":str(month),"url":exc.response.url,
                        "status":"unavailable", "http_status":404,
                        "checked_utc":pd.Timestamp.now(tz="UTC").isoformat()})
        return pd.DataFrame()


def supplement(c):
    cohort=load(c,"cohort");linked=load(c,"asset_sets");ledger=load(c,"outage_ledger")
    linked=linked[linked.verified&linked.asset.isin(cohort.asset)]
    families=set(linked.GENCONSETID)
    members=existing("GENCONSET")
    records=[]
    # Acquire complete membership for the selected families; old caches were filtered by interconnector dependencies.
    # Monthly standing archives contain changes. Read every study month, including changes
    # outside the equipment window; then seek a pre-window version in a bounded lookback.
    for month in pd.period_range(pd.Timestamp(c["window_start"]).to_period("M"),pd.Timestamp(c["window_end"]).to_period("M")-1,freq="M"):
        additional=fetch(c,"GENCONSET",month,lambda r:r.get("GENCONSETID") in families,records)
        members=pd.concat([members,additional],ignore_index=True).drop_duplicates()
    members=members[members.GENCONSETID.isin(families)]
    first_use=linked.merge(ledger[["OUTAGEID","asset","start"]],on=["OUTAGEID","asset"]).groupby("GENCONSETID").start.min()
    for month in pd.period_range(pd.Timestamp(c["window_start"]).to_period("M")-24,pd.Timestamp(c["window_start"]).to_period("M")-1,freq="M")[::-1]:
        earliest=pd.to_datetime(members.EFFECTIVEDATE).groupby(members.GENCONSETID).min()
        fs={f for f in families if f not in earliest or earliest[f]>first_use[f]}
        if not fs:break
        extra=optional_fetch(c,"GENCONSET",month,lambda r:r.get("GENCONSETID") in fs,records)
        if len(extra):
            members=pd.concat([members,extra],ignore_index=True).drop_duplicates()
    ids=set(members.GENCONID)
    save(c,"complete_set_members",members)
    inv_parts=[]
    for month in pd.period_range(pd.Timestamp(c["window_start"]).to_period("M"),pd.Timestamp(c["window_end"]).to_period("M")-1,freq="M"):
        part=fetch(c,"GENCONSETINVOKE",month,lambda r:r.get("GENCONSETID") in families,records)
        if len(part):inv_parts.append(part)
    inv=pd.concat(inv_parts,ignore_index=True).drop_duplicates()
    inv=inv.sort_values("LASTCHANGED").drop_duplicates("INVOCATION_ID",keep="last")
    inv=inv[~inv.INTERVENTION.eq("Y")]
    save(c,"supplement_invocations",inv)
    tables={}
    for table in ["GENCONDATA","SPDINTERCONNECTORCONSTRAINT","SPDCONNECTIONPOINTCONSTRAINT"]:
        tables[table]=fetch(c,table,"2026-08",lambda r:r.get("GENCONID") in ids,records)
        save(c,"supplement_"+table,tables[table])
    # Scope previously absent from binding archive. Acquire only months with verified selected-line events.
    scope=pd.read_parquet(BIND/"equation_scope.parquet")
    column="CONSTRAINTID" if "CONSTRAINTID" in scope else "GENCONID"
    missing=ids-set(scope[column])
    extracted=[]
    if missing:
        events=load(c,"events");event_ids={}
        for e in events[events.asset.isin(cohort.asset)].itertuples():
            fs=set(linked.loc[linked.OUTAGEID.isin(e.outage_ids.split("|")),"GENCONSETID"])
            eq=set(members.loc[members.GENCONSETID.isin(fs),"GENCONID"])&missing
            if not eq:continue
            for month in pd.period_range(e.start.to_period("M"),e.end.to_period("M"),freq="M"):
                event_ids.setdefault(str(month),set()).update(eq)
        for month,eq in sorted(event_ids.items()):
            frame=fetch(c,"DISPATCHCONSTRAINT",month,lambda r:r.get("CONSTRAINTID") in eq,records)
            if len(frame):
                frame=physical(frame,"CONSTRAINTID")
                frame=frame.rename(columns={"GENCONID_EFFECTIVEDATE":"EFFECTIVEDATE","GENCONID_VERSIONNO":"VERSIONNO"})
                for col in ["RHS","LHS","MARGINALVALUE","VIOLATIONDEGREE","VERSIONNO"]:frame[col]=pd.to_numeric(frame[col],errors="coerce")
                frame["binding"]=frame.MARGINALVALUE.abs().gt(1e-9)
                frame["EFFECTIVEDATE"]=pd.to_datetime(frame.EFFECTIVEDATE)
                extracted.append(frame)
        # Backfill exact observed versions missing from current definition snapshot.
        defs=pd.concat([existing("GENCONDATA"),tables["GENCONDATA"]],ignore_index=True).drop_duplicates()
        defs["EFFECTIVEDATE"]=pd.to_datetime(defs.EFFECTIVEDATE);defs["VERSIONNO"]=pd.to_numeric(defs.VERSIONNO)
        known=set(zip(defs.GENCONID,defs.EFFECTIVEDATE,defs.VERSIONNO))
        observed=pd.concat(extracted,ignore_index=True) if extracted else pd.DataFrame()
        backfill={}
        if len(observed):
            for r in observed[["CONSTRAINTID","EFFECTIVEDATE","VERSIONNO"]].drop_duplicates().itertuples(index=False):
                if (r.CONSTRAINTID,r.EFFECTIVEDATE,r.VERSIONNO) not in known:
                    backfill.setdefault(str(r.EFFECTIVEDATE.to_period("M")),set()).add(r.CONSTRAINTID)
        for month,eq in sorted(backfill.items()):
            for table in ["GENCONDATA","SPDINTERCONNECTORCONSTRAINT","SPDCONNECTIONPOINTCONSTRAINT"]:
                f=optional_fetch(c,table,month,lambda r:r.get("GENCONID") in eq,records)
                if len(f):tables[table]=pd.concat([tables[table],f],ignore_index=True).drop_duplicates()
        for table,f in tables.items():save(c,"supplement_"+table,f)
    obs=pd.concat(extracted,ignore_index=True) if extracted else pd.DataFrame(columns=["time","CONSTRAINTID","EFFECTIVEDATE","VERSIONNO","RHS","LHS","MARGINALVALUE","binding"])
    save(c,"supplement_constraint_observations",obs)
    json_write(c["_data"]/"supplement_sources.json",{"records":records,"equations_outside_old_scope":len(missing),
        "families_without_membership":sorted(families-set(members.GENCONSETID)),
        "membership_lookback_start":"2022-09", "membership_limit":"Change archives plus retained history; absence is unresolved, not an empty set."})
    return {"families":len(families),"member_equations":len(ids),"previously_unscoped_equations":len(missing),"supplement_dispatch_rows":len(obs)}
