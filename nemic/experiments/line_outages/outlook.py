"""Frozen current booking outlook and publication-time historical replay audit."""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urljoin

import numpy as np
import pandas as pd

from nemic.common import session
from nemic.experiments.nos import parse_snapshot
from nemic.experiments.nos_regime import outlook as legacy

from .core import OLD, ROOT, REGIONS, json_write, load, save, sha


def latest_snapshot(c):
    directory="https://www.nemweb.com.au/Reports/CURRENT/Network/"
    received=pd.Timestamp.now(tz="UTC")
    try:
        response=session().get(directory,timeout=(20,90));response.raise_for_status()
        names=sorted(set(re.findall(r"PUBLIC_NETWORK_\d{14}_[^\"<>\s/]+\.zip",response.text,re.I)))
        if not names:raise ValueError("No current NOS snapshot links")
        name=names[-1];url=urljoin(directory,name)
        response=session().get(url,timeout=(20,120));response.raise_for_status()
        received=pd.Timestamp.now(tz="UTC")
        if len(response.content)>100_000_000:raise ValueError("Oversized NOS snapshot")
        generated,records=parse_snapshot(response.content,name)
        raw=c["_data"]/"raw"/name;raw.parent.mkdir(exist_ok=True);raw.write_bytes(response.content)
        df=pd.DataFrame([dict(v["fields"],_table=v["table"]) for v in records.values()])
        detail=df[df._table.eq("OUTAGEDETAIL")].drop(columns="_table")
        sets=df[df._table.eq("OUTAGECONSTRAINTSET")].drop(columns="_table")
        return generated,detail,sets,{"source":"current","snapshot_id":name,"url":url,"sha256":sha(raw),
          "generated_nem":str(generated),"received_utc":received.isoformat(),"age_hours":float((received.tz_convert("Etc/GMT-10").tz_localize(None)-generated).total_seconds()/3600)}
    except Exception as exc:
        weeks=legacy.week_dirs()
        if weeks.empty:raise RuntimeError("No current or archived verifiable NOS snapshot") from exc
        generated,name,detail,sets,meta=legacy.snapshot(weeks.iloc[-1].path)
        return generated,detail,sets,{**meta,"source":"archived_fallback","current_fetch_error":repr(exc),"snapshot_id":name,
                    "received_utc":None,"age_hours":float((received.tz_convert("Etc/GMT-10").tz_localize(None)-generated).total_seconds()/3600)}


def booking_rows(c,detail,sets,as_of):
    register=load(c,"cohort");aliases=json.loads((c["_data"]/"aliases.json").read_text())
    d=detail.copy()
    for col in ["STARTTIME","ENDTIME","SUBMITTEDDATE"]:d[col]=pd.to_datetime(d[col],errors="coerce")
    d["status"]=d.OUTAGESTATUSCODE.str.upper().str.strip()
    known=set(d.OUTAGEID.astype(str));d=d[~d.RESUBMITOUTAGEID.fillna("").astype(str).isin(known)]
    d=d[~d.status.isin(["WDRAWN","WD REQ","CANCELLED","CANCEL","COMPLETE","INFO","INFORMATION"])]
    d=d[d.ENDTIME.gt(as_of)&d.STARTTIME.le(as_of+pd.Timedelta(days=c["outlook_horizon_days"]))&d.ENDTIME.gt(d.STARTTIME)]
    d=d[d.ISSECONDARY.eq("0")]
    raw=d.SUBSTATIONID.fillna("")+"/"+d.EQUIPMENTTYPE.fillna("")+"/"+d.EQUIPMENTID.fillna("")
    by_element=register.set_index("element_id").asset.to_dict()
    d["asset"]=raw.map(aliases).fillna(d.ELEMENTID.astype(str).map(by_element))
    d=d[d.asset.isin(register.asset)].drop_duplicates(["OUTAGEID","asset"])
    linked=sets.groupby("OUTAGEID").GENCONSETID.agg(lambda x:"|".join(sorted(set(x.dropna())))) if len(sets) else pd.Series(dtype=str)
    out=[]
    for r in d.itertuples():
        a=register[register.asset.eq(r.asset)].iloc[0];lead=(r.STARTTIME-as_of).total_seconds()/86400
        families=linked.get(r.OUTAGEID,"")
        out.append({"asset":r.asset,"description":a.description,"region":a.region,"OUTAGEID":r.OUTAGEID,
          "start":r.STARTTIME,"end":r.ENDTIME,"status":r.status,"submitted":r.SUBMITTEDDATE,"lead_days":lead,
          "lead_band":"0–7" if lead<=7 else "8–30" if lead<=30 else "31–90" if lead<=90 else "91–365",
          "linked_sets":families,"mapping_status":"direct" if families else "unresolved; no family proxy used",
          "historical_events":int(a.events),"probability":np.nan,
          "assessment":"Conditional network-risk scenario; numerical price-risk estimate withheld pending receipt-provenance and calibration gates"})
    frame=pd.DataFrame(out,columns=["asset","description","region","OUTAGEID","start","end","status","submitted","lead_days","lead_band","linked_sets","mapping_status","historical_events","probability","assessment"])
    frame["overlap_ids"]=""
    for i,r in frame.iterrows():
        others=frame[(frame.region.eq(r.region))&frame.start.lt(r.end)&frame.end.gt(r.start)&frame.OUTAGEID.ne(r.OUTAGEID)]
        frame.loc[i,"overlap_ids"]="|".join(sorted(set(others.OUTAGEID)))
    return frame


def run(c):
    generated,detail,sets,meta=latest_snapshot(c)
    bookings=booking_rows(c,detail,sets,generated)
    meta["assessment_as_of_nem"]=str(generated)
    meta["numerical_price_probability_gate"]="withheld: historical receipt and independent price-risk calibration not verified"
    meta["historical_receipt_provenance"]="unavailable; replay is publication-time research only"
    save(c,"outlook_bookings",bookings)
    # Replay real archived snapshots; score availability/occurrence, never pretend their later retrieval was historical receipt.
    weeks=legacy.week_dirs();weeks=weeks[(weeks.date>=pd.Timestamp("2025-09-01"))&(weeks.date<pd.Timestamp("2026-09-01"))]
    first=weeks.assign(month=weeks.date.dt.to_period("M")).drop_duplicates("month")
    eps=pd.read_parquet(OLD/"episodes.parquet").set_index("OUTAGEID")
    successor=legacy.successor_map();replay=[];price_tests=[]
    panels={r:load(c,"panel_"+r) for r in REGIONS}
    events=load(c,"events")
    for w in first.itertuples():
        as_of,name,d,s,m=legacy.snapshot(w.path)
        rows=booking_rows(c,d,s,as_of)
        for r in rows.itertuples():
            final=legacy.final_id(str(r.OUTAGEID),successor)
            if final not in eps.index:truth="unresolved"
            else:
                e=eps.loc[final]
                truth="withdrawn" if e.withdrawn else "actual_complete" if e.window_source=="actual" and e.status=="COMPLETE" else "scheduled_only"
                if e.end>pd.Timestamp(c["window_end"]):truth="not_yet_scorable"
            replay.append({"as_of":as_of,"snapshot_id":name,"asset":r.asset,"OUTAGEID":r.OUTAGEID,"final_id":final,
                           "lead_band":r.lead_band,"booking_start":r.start,"booking_end":r.end,"truth":truth,
                           "historical_receipt_verified":False,"numerical_price_prediction":np.nan})
            if truth!="actual_complete" or final not in eps.index:continue
            actual=eps.loc[final]
            if actual.start<as_of:continue
            frame=panels[r.region]
            historical=frame[frame.time.lt(as_of)&frame.time.ge(as_of-pd.Timedelta(days=365))]
            delivered=frame[frame.time.gt(actual.start)&frame.time.le(actual.end)]
            if delivered.empty or historical.empty:continue
            # No future fundamentals: only pre-origin outcome history. Final-state asset history is a conditional research proxy.
            past_events=events[events.asset.eq(r.asset)&events.end.lt(as_of-pd.Timedelta(days=21))]
            episode_rates=[]
            for pe in past_events.itertuples():
                g=historical[historical.time.gt(pe.start)&historical.time.le(pe.end)]
                if len(g):episode_rates.append(float(g.spike1000.mean()))
            baseline=float(historical.spike1000.mean())
            if episode_rates:
                raw=float(np.mean(episode_rates));weight=len(episode_rates)/(len(episode_rates)+5)
                candidate=weight*raw+(1-weight)*baseline
            else:candidate=baseline
            observed=float(delivered.spike1000.mean())
            price_tests.append({"as_of":as_of,"asset":r.asset,"region":r.region,"OUTAGEID":r.OUTAGEID,
                "lead_band":r.lead_band,"past_episodes":len(episode_rates),"intervals":len(delivered),
                "baseline_probability":baseline,"candidate_probability":candidate,"observed_share":observed,
                "brier_baseline":baseline**2-2*baseline*observed+observed,
                "brier_candidate":candidate**2-2*candidate*observed+observed,
                "event":observed>=.05,"mode":"conditional final-state-history probe; receipt unverified"})
    save(c,"outlook_replay",pd.DataFrame(replay,columns=["as_of","snapshot_id","asset","OUTAGEID","final_id","lead_band","booking_start","booking_end","truth","historical_receipt_verified","numerical_price_prediction"]))
    tests=pd.DataFrame(price_tests,columns=["as_of","asset","region","OUTAGEID","lead_band","past_episodes","intervals","baseline_probability","candidate_probability","observed_share","brier_baseline","brier_candidate","event","mode"])
    scores=[]
    if len(tests):
        origins=sorted(tests.as_of.unique());fit_origins=origins[:6]
        fit=tests[tests.as_of.isin(fit_origins)]
        thresholds=np.unique(np.r_[0.,fit.candidate_probability.to_numpy(),1.])
        def f1(threshold):
            alert=fit.candidate_probability.ge(threshold);truth=fit.event
            tp=int((alert&truth).sum());fp=int((alert&~truth).sum());fn=int((~alert&truth).sum())
            return 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.
        threshold=max(thresholds,key=lambda t:(f1(t),t))
        tests["partition"]=np.where(tests.as_of.isin(fit_origins),"alert_tuning","evaluation")
        tests["alert"]=tests.candidate_probability.ge(threshold)
        for (region,band),g in tests[tests.partition.eq("evaluation")].groupby(["region","lead_band"]):
            weights=g.intervals
            bc=float(np.average(g.brier_candidate,weights=weights));bb=float(np.average(g.brier_baseline,weights=weights))
            tp=int((g.alert&g.event).sum());fp=int((g.alert&~g.event).sum());fn=int((~g.alert&g.event).sum())
            scores.append({"region":region,"lead_band":band,"bookings":len(g),"intervals":int(weights.sum()),
                          "brier_candidate":bc,"brier_baseline":bb,"skill":1-bc/bb if bb else np.nan,
                          "alert_threshold":float(threshold),"precision":tp/(tp+fp) if tp+fp else np.nan,
                          "recall":tp/(tp+fn) if tp+fn else np.nan,"false_alerts":fp,
                          "minimum_sample_pass":len(g)>=30,"receipt_gate":False,"publish_probability":False})
        meta["price_probe_alert_threshold"]=float(threshold)
    save(c,"outlook_price_backtest",tests)
    save(c,"outlook_backtest_scores",pd.DataFrame(scores,columns=["region","lead_band","bookings","intervals","brier_candidate","brier_baseline","skill","alert_threshold","precision","recall","false_alerts","minimum_sample_pass","receipt_gate","publish_probability"]))
    json_write(c["_data"]/"outlook_provenance.json",meta)
    return {"current_bookings":len(bookings),"historical_booking_replays":len(replay),"conditional_price_probe_rows":len(tests),"snapshot":meta["snapshot_id"],
            "probabilities_published":0,"outlook_mode":"conditional mechanism assessment"}
