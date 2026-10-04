"""Revision-aware conversion of verified half-hour target snapshots."""
from __future__ import annotations

import pandas as pd

from .contracts import TARGETS, connector


def normalize_targets(frame, *, received, revision_id, availability_evidence="measured_receipt"):
    received = pd.Timestamp(received)
    if received.tzinfo is None:
        raise ValueError("Outcome receipt must be timezone aware")
    required = {"time", "ic", *TARGETS}
    if required - set(frame):
        raise ValueError(f"Missing target fields: {sorted(required - set(frame))}")
    if "n5" in frame and frame.n5.ne(6).any():
        raise ValueError("Incomplete half-hour outcomes must not be scored")
    wide = frame[["time", "ic", *TARGETS]].copy()
    delivery = pd.to_datetime(wide.pop("time"))
    if delivery.dt.tz is None:
        delivery = delivery.dt.tz_localize("Australia/Brisbane")
    else:
        delivery = delivery.dt.tz_convert("Australia/Brisbane")
    wide["delivery"] = delivery
    wide["connector"] = wide.pop("ic").map(connector)
    result = wide.melt(id_vars=["connector", "delivery"], value_vars=list(TARGETS),
                       var_name="target", value_name="actual")
    if result.actual.isna().any() or result.duplicated(["connector", "target", "delivery"]).any():
        raise ValueError("Target snapshot contains missing or duplicate outcomes")
    result["received"] = received.tz_convert("UTC")
    result["revision_id"] = str(revision_id)
    result["availability_evidence"] = availability_evidence
    return result
