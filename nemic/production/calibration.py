"""Separate held-out hourly residual calibration, never averaged bounds."""
import numpy as np
import pandas as pd

from .contracts import QUANTILES, QCOLS


def fit_hourly(frame, *, version, minimum_rows=30):
    """Caller supplies held-out hourly actual/forecast pairs, keyed by route version."""
    required = {"connector", "target", "actual", "forecast_mw", "delivery", "routing_version"}
    if required - set(frame):
        raise ValueError(f"Missing hourly calibration fields: {required - set(frame)}")
    result = {"version": version, "cells": []}
    for key, rows in frame.groupby(["connector", "target", "routing_version"]):
        residual = rows.actual.to_numpy() - rows.forecast_mw.to_numpy()
        residual = residual[np.isfinite(residual)]
        if len(residual) < minimum_rows:
            continue
        result["cells"].append(dict(connector=key[0], target=key[1], routing_version=key[2],
                                    calibration_end=pd.to_datetime(rows.delivery, utc=True).max().isoformat(),
                                    adjustments=np.quantile(residual, QUANTILES).tolist(), n=len(residual)))
    return result


def apply_hourly(frame, calibration, routing_version):
    out = frame.copy()
    for cell in calibration["cells"]:
        if cell["routing_version"] != routing_version:
            continue
        mask = ((out.connector == cell["connector"]) & (out.target == cell["target"]) & out.status.eq("complete")
                & (pd.to_datetime(out.origin, utc=True) > pd.Timestamp(cell["calibration_end"])))
        for col, adjustment in zip(QCOLS, cell["adjustments"]):
            out.loc[mask, col] = out.loc[mask, "forecast_mw"] + adjustment
        out.loc[mask, "interval_basis"] = "hourly calibration " + calibration["version"]
    return out
