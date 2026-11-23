"""Chronological comparisons with explicit support/falsification gates."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd

from .core import REGIONS, STUDIES, IC_REGIONS, grid, interval_mask, json_write, load, save

PRICE_OUTCOMES = ["price_change", "spike300", "spike1000", "negative", "negative100", "tail99", "tail01"]


def bins(values, eligible):
    x = np.asarray(values,dtype=float)
    ref=x[eligible & np.isfinite(x)]
    if not len(ref):return np.full(len(x),-1,dtype="int8")
    q=np.quantile(ref,[.2,.8])
    return np.where(np.isfinite(x),np.searchsorted(q,x),-1).astype("int8")


def match_pairs(c, frame, source, windows, asset, period, relaxed=False, excluded=None, vre=False):
    """Vectorised deterministic same-minute controls; never match on outcomes/dispatch mediators."""
    times=pd.DatetimeIndex(frame.time);n=len(times)
    all_events=windows
    treated=interval_mask(times,all_events)
    split=times < pd.Timestamp(c["selection_end"])
    eligible=np.asarray(split if period=="selection" else ~split)
    ti=np.flatnonzero(treated & eligible)
    if not len(ti):return pd.DataFrame(columns=["treated","control","event_id","rung"])
    labels=np.full(n,"",dtype=object)
    for r in all_events.itertuples():
        labels[interval_mask(times,pd.DataFrame([{"start":r.start,"end":r.end}]))]=r.event_id
    weekend=(times.dayofweek>=5); seasons=frame.season.to_numpy()
    train=np.asarray(split)
    columns=["demand","temperature"]+(["wind_available","solar_available"] if vre else [])
    driver_bins=[bins(frame[col],train) for col in columns]
    if source is not frame:
        driver_bins += [bins(source[col],train) for col in columns]
    signatures=[];counts=[]
    h=hashlib.sha256(asset.encode()).digest()
    for f in ([frame] if source is frame else [frame,source]):
        remove=f.REGIONID.iat[0]==source.REGIONID.iat[0]
        for col,start in [("co_sig1",0),("co_sig2",8)]:
            s=f[col].to_numpy().copy()
            own_mask = treated if excluded is None else excluded
            if remove:s[own_mask] ^= np.uint64(int.from_bytes(h[start:start+8],"little"))
            signatures.append(s)
        ct=f.outage_count.to_numpy().copy()
        if remove:ct[own_mask]-=1
        counts.append(ct)
    excluded=np.zeros(n,bool) if excluded is None else excluded
    valid=~treated & eligible & ~excluded
    # Primary price analysis omits intervention or overridden/suspended price intervals.
    for f in ([frame] if source is frame else [frame,source]):
        bad=f.physical_intervention.fillna(1).ne(0).to_numpy()
        for col in ["apc_binding","voll_override","manual_override","MARKETSUSPENDEDFLAG"]:
            if col in f:bad |= f[col].fillna(True).astype(bool).to_numpy()
        valid &= ~bad
        ti=ti[~bad[ti]]
    controls=np.full((len(ti),c["max_controls"]),-1,dtype=np.int32)
    filled=np.zeros(len(ti),dtype=np.int8)
    # Prefer the nearest earlier day, then nearest later day. No outcome-dependent ordering.
    for d in range(1,c["match_days"]+1):
        for delta in [-d*288,d*288]:
            ci=ti+delta;inside=(ci>=0)&(ci<n);safe=ci.clip(0,n-1)
            ok=inside & valid[safe] & (filled<c["max_controls"]) & (weekend[ti]==weekend[safe]) & (seasons[ti]==seasons[safe])
            for b in driver_bins:ok &= (b[ti]>=0)&(b[ti]==b[safe])
            if relaxed:
                for count in counts:ok &= count[ti]==count[safe]
            else:
                for s in signatures:ok &= s[ti]==s[safe]
            idx=np.flatnonzero(ok)
            controls[idx,filled[idx]]=ci[idx];filled[idx]+=1
    rr,cc=np.nonzero(controls>=0)
    return pd.DataFrame({"treated":ti[rr],"control":controls[rr,cc],"event_id":labels[ti[rr]],"rung":"count" if relaxed else "exact"})


def effect(frame,pairs,outcome,c):
    if pairs.empty:return {"effect":np.nan,"ci_lo":np.nan,"ci_hi":np.nan,"p":np.nan,"matched":0,"episodes":0},pd.DataFrame()
    y=frame[outcome].to_numpy(dtype=float)
    p=pairs.assign(t=y[pairs.treated],v=y[pairs.control]).dropna(subset=["t","v"])
    if p.empty:return {"effect":np.nan,"ci_lo":np.nan,"ci_hi":np.nan,"p":np.nan,"matched":0,"episodes":0},pd.DataFrame()
    units=p.groupby(["event_id","treated"]).agg(t=("t","first"),v=("v","mean")).reset_index()
    units["difference"]=units.t-units.v
    episodes=units.groupby("event_id").difference.mean()
    mean=float(episodes.mean())
    if len(episodes)>=2:
        rng=np.random.default_rng(c["seed"])
        b=episodes.to_numpy()[rng.integers(0,len(episodes),size=(c["bootstrap_replicates"],len(episodes)))].mean(axis=1)
        lo,hi=np.quantile(b,[.025,.975]);pvalue=min(1.,2*min((np.count_nonzero(b<=0)+1)/(len(b)+1),(np.count_nonzero(b>=0)+1)/(len(b)+1)))
    else:lo=hi=pvalue=np.nan
    return {"effect":mean,"ci_lo":float(lo),"ci_hi":float(hi),"p":float(pvalue),"matched":len(units),"episodes":len(episodes),
            "treated_mean":float(units.t.mean()),"control_mean":float(units.v.mean())},units


def bh_adjust(pvalues):
    p=np.asarray(pvalues,dtype=float);out=np.full(len(p),np.nan);good=np.flatnonzero(np.isfinite(p))
    if not len(good):return out
    order=good[np.argsort(p[good])];q=p[order]*len(order)/np.arange(1,len(order)+1)
    out[order]=np.minimum.accumulate(q[::-1])[::-1].clip(0,1)
    return out


def balance(frame,pairs,selection_end):
    if pairs.empty:return np.nan
    s=[]
    for name in ["demand","temperature"]:
        x=frame[name].to_numpy(dtype=float)
        matched=pairs.assign(t=x[pairs.treated],v=x[pairs.control]).groupby("treated").agg(t=("t","first"),v=("v","mean"))
        sd=np.nanstd(frame.loc[frame.time.lt(pd.Timestamp(selection_end)),name])
        s.append(abs(matched.t.mean()-matched.v.mean())/sd if sd>0 else 0.)
    return max(s)


def compare(c):
    cohort=load(c,"cohort");events=load(c,"events")
    panels={region:load(c,"panel_"+region) for region in REGIONS}
    price_rows,network_rows,diagnostics=[],[],[]
    pair_dir=c["_data"]/"pairs";pair_dir.mkdir(exist_ok=True)
    ic_panels={ic:load(c,"ic_"+ic).set_index("time").reindex(grid(c)).reset_index() for ic in STUDIES}
    for ic,f in ic_panels.items():
        left,right=IC_REGIONS[ic]
        f["price_spread"]=panels[right].RRP.to_numpy()-panels[left].RRP.to_numpy()
    for number,r in enumerate(cohort.itertuples(),1):
        print(f"compare {number}/{len(cohort)} {r.asset}",flush=True)
        checkpoint=c["_data"]/"compare_checkpoints"/f"{number:02d}.json"
        if checkpoint.exists():
            saved=json.loads(checkpoint.read_text())
            if saved.get("fingerprint")==c.get("_stage_fingerprint") and saved.get("asset")==r.asset:
                price_rows.extend(saved["price_rows"]);network_rows.extend(saved["network_rows"]);diagnostics.extend(saved["diagnostics"])
                continue
        initial=(len(price_rows),len(network_rows),len(diagnostics))
        windows=events[events.asset.eq(r.asset)]
        source=panels[r.region]
        actual_mask=interval_mask(source.time,windows)
        for region,frame in panels.items():
            for period in ["selection","confirmation"]:
                eligible=frame.time.lt(pd.Timestamp(c["selection_end"])) if period=="selection" else frame.time.ge(pd.Timestamp(c["selection_end"]))
                treated=int((actual_mask&eligible.to_numpy()).sum())
                pairs=match_pairs(c,frame,source,windows,r.asset,period)
                relaxed=match_pairs(c,frame,source,windows,r.asset,period,relaxed=True)
                vre_pairs=match_pairs(c,frame,source,windows,r.asset,period,vre=True)
                match_rate=pairs.treated.nunique()/treated if treated else 0.
                smd=balance(frame,pairs,c["selection_end"])
                if source is not frame:smd=max(smd,balance(source,pairs,c["selection_end"])) if np.isfinite(smd) else np.nan
                pairs.to_parquet(pair_dir/f"{number:02d}_{region}_{period}.parquet",index=False)
                # Shifted-date placebo retains exclusion of the actual treatment windows.
                placebo=[]
                for shift in [-7,7]:
                    w=windows.copy();w["start"]+=pd.Timedelta(days=shift);w["end"]+=pd.Timedelta(days=shift)
                    pp=match_pairs(c,frame,source,w,r.asset,period,excluded=actual_mask)
                    placebo.append(effect(frame,pp,"price_change",c)[0])
                placebo_ok=all(np.isfinite(p["ci_lo"]) and p["ci_lo"]<=0<=p["ci_hi"] for p in placebo)
                # Pretrend: six hours before each event, excluding actual outage intervals.
                pre=windows.copy();pre["end"]=pre.start;pre["start"]-=pd.Timedelta(hours=6)
                pre_pairs=match_pairs(c,frame,source,pre,r.asset,period,excluded=actual_mask)
                pret=effect(frame,pre_pairs,"price_change",c)[0]
                pre_ok=np.isfinite(pret["ci_lo"]) and pret["ci_lo"]<=0<=pret["ci_hi"]
                for outcome in PRICE_OUTCOMES:
                    out,units=effect(frame,pairs,outcome,c);sens,_=effect(frame,relaxed,outcome,c)
                    vre_sens,_=effect(frame,vre_pairs,outcome,c)
                    support=(out["episodes"]>=c["minimum_episodes"] and out["matched"]/12>=c["minimum_treated_hours"] and
                             match_rate>=c["minimum_match_rate"] and np.isfinite(smd) and smd<=c["maximum_smd"])
                    ep=units.groupby("event_id").difference.mean() if len(units) else pd.Series(dtype=float)
                    loo=[float(ep.drop(i).mean()) for i in ep.index] if len(ep)>1 else []
                    stable=bool(loo and all(np.sign(v)==np.sign(out["effect"]) for v in loo))
                    sensitivity_ok=np.isfinite(sens["effect"]) and (np.sign(sens["effect"])==np.sign(out["effect"]) or abs(out["effect"])<1e-9)
                    vre_ok=np.isfinite(vre_sens["effect"]) and (np.sign(vre_sens["effect"])==np.sign(out["effect"]) or abs(out["effect"])<1e-9)
                    # Significant causal headlines are not produced; this gate permits controlled-estimate display only.
                    gate=support and placebo_ok and pre_ok and stable and sensitivity_ok and vre_ok
                    price_rows.append({"asset":r.asset,"region":region,"period":period,"outcome":outcome,**out,
                        "treated_intervals":treated,"match_rate":match_rate,"max_smd":smd,"support":support,
                        "placebo_pass":placebo_ok,"pretrend_pass":pre_ok,"leave_one_out_stable":stable,
                        "sensitivity_sign_agreement":bool(sensitivity_ok),"display_estimate":bool(gate),
                        "vre_sign_agreement":bool(vre_ok),"vre_sensitivity_effect":vre_sens["effect"],"vre_match_rate":vre_pairs.treated.nunique()/treated if treated else 0.,
                        "relaxed_effect":sens["effect"],"relaxed_match_rate":relaxed.treated.nunique()/treated if treated else 0.,
                        "multi_equipment_events":int(windows.multi_equipment.sum()),
                        "evidence_label":"controlled retrospective estimate" if gate else "withheld; descriptive evidence only"})
                diagnostics.append({"asset":r.asset,"region":region,"period":period,"placebo_minus7":placebo[0]["effect"],
                        "placebo_plus7":placebo[1]["effect"],"pretrend":pret["effect"],"match_rate":match_rate,"max_smd":smd})
                if region==r.region:
                    for ic,f in ic_panels.items():
                        for outcome in ["flow","forward_capacity","reverse_capacity","forward_headroom","reverse_headroom","price_spread"]:
                            out,_=effect(f,pairs,outcome,c)
                            network_rows.append({"asset":r.asset,"ic":ic,"period":period,"outcome":outcome,**out,
                               "match_rate":match_rate,"evidence_label":"source-region matched association; remote conditions not fully controlled"})
        def safe_records(rows):
            return json.loads(pd.DataFrame(rows).to_json(orient="records"))
        json_write(checkpoint,{"fingerprint":c.get("_stage_fingerprint"),"asset":r.asset,
            "price_rows":safe_records(price_rows[initial[0]:]),"network_rows":safe_records(network_rows[initial[1]:]),
            "diagnostics":safe_records(diagnostics[initial[2]:])})
    result=pd.DataFrame(price_rows)
    result["q_value"]=np.nan
    for period in ["selection","confirmation"]:
        mask=result.period.eq(period)&result.outcome.eq("price_change")
        result.loc[mask,"q_value"]=bh_adjust(result.loc[mask,"p"])
    # A confirmed statement must satisfy both phases, adjusted p, and same-sign effects.
    key=["asset","region","outcome"]
    train=result[result.period.eq("selection")].set_index(key)
    result["confirmed"]=False
    for i,row in result[result.period.eq("confirmation") & result.outcome.eq("price_change")].iterrows():
        prev=train.loc[(row.asset,row.region,row.outcome)]
        result.loc[i,"confirmed"]=bool(row.display_estimate and prev.display_estimate and row.q_value<=.05 and prev.q_value<=.05 and
                                           np.sign(row.effect)==np.sign(prev.effect))
    save(c,"price_effects",result);save(c,"network_effects",pd.DataFrame(network_rows));save(c,"falsification",pd.DataFrame(diagnostics))
    return {"price_tests":len(result),"displayable":int(result.display_estimate.sum()),"confirmed_movement_tests":int(result.confirmed.sum()),
            "network_associations":len(network_rows)}
