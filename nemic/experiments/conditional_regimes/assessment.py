"""Cached assessment with per-fold alert policies and independent-day risk support."""
from __future__ import annotations
import numpy as np
import pandas as pd
from .common import DATA,stage,config
from .metrics import score,block_improvement


def assessed_score(f):
    metric=score(f.actual,f[["p10","p50","p90"]],f.threshold,f.probability)
    if not len(f):return metric
    valid=f.threshold.notna() & f.probability.notna()
    s=f[valid]
    actual=s.actual.to_numpy()<s.threshold.to_numpy()
    alert=s.probability.to_numpy()>=s.alert_threshold.to_numpy()
    tp=np.sum(actual&alert);fp=np.sum(~actual&alert);fn=np.sum(actual&~alert)
    metric.update(restriction_events=int(actual.sum()),restriction_recall=float(tp/(tp+fn)) if tp+fn else None,
                  restriction_precision=float(tp/(tp+fp)) if tp+fp else None,
                  false_alerts_per_day=float(fp/(len(s)/48)) if len(s) else None,
                  restriction_scored_rows=len(s),
                  restricted_days=int(s.loc[actual,"time"].dt.normalize().nunique()),
                  forced_days=int(f.loc[f.actual<0,"time"].dt.normalize().nunique()),
                  independent_days=int(f.time.dt.normalize().nunique()),
                  brier=float(np.mean((s.probability.to_numpy()-actual)**2)) if len(s) else None)
    return metric


def assess():
    with stage("assess",[DATA/"predictions.parquet"]) as artifacts:
        predictions=pd.read_parquet(DATA/"predictions.parquet")
        scores=[];paired=[];gates=[]
        for (name,direction),g in predictions.groupby(["connector","direction"]):
            available=g.assign(valid=np.isfinite(g[["p10","p50","p90"]]).all(axis=1)).pivot_table(index="time",columns="method",values="valid",aggfunc="min")
            common=available.index[available.fillna(False).all(axis=1)]
            matched=g[g.time.isin(common)].copy()
            matched["delivery_period"]=np.select([matched.half_hour<12,matched.half_hour<18,matched.half_hour<32,matched.half_hour<42],["overnight","morning","solar","evening"],default="overnight")
            summaries={}
            for method,f in matched.groupby("method"):
                summaries[method]=assessed_score(f)
                scores.append({"connector":name,"direction":direction,"method":method,"slice":"overall",**summaries[method]})
                for field in ("quarter","outage_state","delivery_period","support","era"):
                    for value,s in f.groupby(field):scores.append({"connector":name,"direction":direction,"method":method,"slice":f"{field}:{value}",**assessed_score(s)})
                for label,mask in (("restricted",f.actual<f.threshold),("forced",f.actual<0)):
                    scores.append({"connector":name,"direction":direction,"method":method,"slice":label,**assessed_score(f[mask])})
                if method=="baseline":continue
                controls=["baseline","analogue"] if method in {"additive","boosting"} else ["baseline"]
                for control in controls:
                    paired.append({"connector":name,"direction":direction,"method":method,"control":control,
                                   **block_improvement(matched,method,control=control,repeats=config()["bootstrap_repeats"])})
            for method,a in summaries.items():
                if method=="baseline":continue
                control="analogue" if method in {"additive","boosting"} else "baseline"
                b=summaries[control]
                ci=next(x for x in paired if x["connector"]==name and x["direction"]==direction and x["method"]==method and x["control"]==control)
                reasons=[]
                if ci["ci_lo"] is None or ci["ci_lo"]<=0:reasons.append("paired point improvement not established")
                if a["pinball"]>=b["pinball"]:reasons.append("distributional loss not improved")
                if abs(a["coverage80"]-.8)>.05:reasons.append("80% interval coverage outside 75–85% convention")
                if a["p95_overstatement"]>b["p95_overstatement"]*1.05+1:reasons.append("overstatement tail worsened")
                for metric in ("restriction_recall","restriction_precision","forced_recall","forced_precision"):
                    if a[metric] is not None and b[metric] is not None and a[metric]<b[metric]-.02:reasons.append(metric+" worsened")
                if a["false_alerts_per_day"] is not None and b["false_alerts_per_day"] is not None and a["false_alerts_per_day"]>max(1.,b["false_alerts_per_day"]+.1):reasons.append("false alert rate worsened")
                if a["forced_days"]<10 or a["restricted_days"]<10:reasons.append("fewer than 10 independent extreme days")
                gates.append({"connector":name,"direction":direction,"method":method,"control":control,
                              "historical_gate_pass":not reasons,"reasons":"; ".join(reasons),"production_promotion":False})
        pd.DataFrame(scores).to_csv(DATA/"assessed_scores.csv",index=False)
        pd.DataFrame(paired).to_csv(DATA/"assessed_paired_comparisons.csv",index=False)
        pd.DataFrame(gates).to_csv(DATA/"assessed_method_gates.csv",index=False)
        artifacts.extend([DATA/x for x in ("assessed_scores.csv","assessed_paired_comparisons.csv","assessed_method_gates.csv")])
        print("Assessed all methods with per-row alert thresholds and independent-day support",flush=True)
