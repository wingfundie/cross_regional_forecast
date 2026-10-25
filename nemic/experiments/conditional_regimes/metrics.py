"""Identical-row conditional accuracy, risk metrics and paired block uncertainty."""
from __future__ import annotations
import numpy as np
import pandas as pd


def score(y, pred, threshold, probability=None, alert_threshold=.5):
    y, pred = np.asarray(y, float), np.asarray(pred, float)
    ok = np.isfinite(y) & np.isfinite(pred).all(axis=1)
    y, pred = y[ok], pred[ok]
    if np.isscalar(threshold):
        threshold = np.full(len(ok), threshold)
    threshold = np.asarray(threshold, float)[ok]
    if not len(y):
        return {"n": 0}
    err = pred[:,1]-y
    ae = abs(err)
    pinball = np.maximum((y[:,None]-pred)*np.array([.1,.5,.9]), (pred-y[:,None])*np.array([.9,.5,.1]))
    actual = y < threshold
    if probability is None:
        probability = (pred[:,0] < threshold).astype(float)
    else:
        probability = np.asarray(probability, float)[ok]
    predicted = probability >= alert_threshold
    tp = int(np.sum(actual & predicted)); fp = int(np.sum(~actual & predicted)); fn = int(np.sum(actual & ~predicted))
    forced = y < 0; forced_pred = pred[:,0] < 0
    ftp = np.sum(forced & forced_pred)
    width = pred[:,2]-pred[:,0]
    interval_score = width + 10*np.maximum(pred[:,0]-y,0) + 10*np.maximum(y-pred[:,2],0)
    wis = (.5*abs(y-pred[:,1]) + .1*interval_score) / 1.5
    return {"n": len(y), "mae": float(ae.mean()), "rmse": float(np.sqrt(np.square(err).mean())),
            "bias": float(err.mean()), "p95_absolute_error": float(np.quantile(ae,.95)),
            "overstatement_mean": float(np.maximum(err,0).mean()), "p95_overstatement": float(np.quantile(np.maximum(err,0),.95)),
            "pinball": float(pinball.mean()), "wis": float(wis.mean()),
            "coverage80": float(np.mean((y>=pred[:,0]) & (y<=pred[:,2]))), "width80": float(width.mean()),
            "restriction_events": int(actual.sum()), "restriction_recall": tp/(tp+fn) if tp+fn else None,
            "restriction_precision": tp/(tp+fp) if tp+fp else None, "false_alerts_per_day": fp/(len(y)/48),
            "forced_events": int(forced.sum()), "forced_recall": float(ftp/forced.sum()) if forced.any() else None,
            "forced_precision": float(ftp/forced_pred.sum()) if forced_pred.any() else None,
            "brier": float(np.mean((probability-actual)**2))}


def loss(y, pred):
    delta = np.asarray(y)[:,None]-np.asarray(pred)
    return float(np.maximum(delta*np.array([.1,.5,.9]), -delta*np.array([.9,.5,.1])).mean())


def block_improvement(frame, method, control="baseline", repeats=300, seed=741):
    a = frame[frame.method == method][["time","actual","p50"]]
    b = frame[frame.method == control][["time","p50"]]
    paired = a.merge(b,on="time",suffixes=("_candidate","_control"))
    paired["delta"] = abs(paired.p50_control-paired.actual)-abs(paired.p50_candidate-paired.actual)
    paired["block"] = (pd.to_datetime(paired.time)-pd.to_datetime(paired.time).min()).dt.days // 7
    blocks = paired.groupby("block").delta.agg(["sum","count"])
    if len(blocks) < 4:
        return {"improvement_mw": float(paired.delta.mean()) if len(paired) else None, "ci_lo": None, "ci_hi": None, "blocks": len(blocks)}
    rng = np.random.default_rng(seed)
    ix = rng.integers(0,len(blocks),size=(repeats,len(blocks)))
    estimates = blocks["sum"].to_numpy()[ix].sum(axis=1)/blocks["count"].to_numpy()[ix].sum(axis=1)
    return {"improvement_mw": float(paired.delta.mean()), "ci_lo": float(np.quantile(estimates,.025)),
            "ci_hi": float(np.quantile(estimates,.975)), "blocks": len(blocks)}
