"""Frozen chronological protocol and scoring helpers for clustering research.

The helpers in this module are deliberately free of filesystem and model-fitting
side effects.  All timestamps use the caller's fixed-NEM-time representation and
all partitions are half-open.  A row is eligible only when its delivery outcome
has matured before the end of its partition.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score


DEFAULT_SEED = 741
PARTITIONS = ("train", "select", "calibrate", "alert", "evaluate")
CONFIGURED_LEADS = (1, 2, 4, 8, 12, 24, 48, 72, 96, 144, 192, 240, 288, 336)
CHECKPOINT_LEADS = {24: 48, 48: 96, 168: 336}


@dataclass(frozen=True)
class ProtocolConfig:
    """Durations for one expanding chronological evaluation protocol."""

    minimum_train_days: int = 60
    select_days: int = 14
    calibrate_days: int = 14
    alert_days: int = 14
    evaluate_days: int = 28
    advance_days: int = 28
    maturity_delay_minutes: int = 30
    seed: int = DEFAULT_SEED

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "ProtocolConfig":
        """Build from the campaign JSON's frozen fold field names."""

        fields = {
            "minimum_train_days": value.get("minimum_train_days", 60),
            "select_days": value.get("select_days", 14),
            "calibrate_days": value.get("calibrate_days", 14),
            "alert_days": value.get("alert_days", 14),
            "evaluate_days": value.get("evaluate_days", 28),
            "advance_days": value.get("advance_days", value.get("step_days", 28)),
            "maturity_delay_minutes": value.get(
                "maturity_delay_minutes", value.get("maturity_minutes", 30)
            ),
            "seed": value.get("seed", DEFAULT_SEED),
        }
        return cls(**fields)

    def __post_init__(self) -> None:
        values = asdict(self)
        for name, value in values.items():
            if name == "seed":
                continue
            if not isinstance(value, (int, np.integer)) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class ProtocolFold:
    """One expanding fold with disjoint selection and evaluation stages."""

    name: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    select_end: pd.Timestamp
    calibrate_end: pd.Timestamp
    alert_end: pd.Timestamp
    evaluate_end: pd.Timestamp

    def windows(self) -> tuple[tuple[pd.Timestamp, pd.Timestamp], ...]:
        boundaries = (
            self.train_start,
            self.train_end,
            self.select_end,
            self.calibrate_end,
            self.alert_end,
            self.evaluate_end,
        )
        return tuple(zip(boundaries[:-1], boundaries[1:]))

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, **{
            key: value.isoformat() for key, value in asdict(self).items() if key != "name"
        }}


@dataclass(frozen=True)
class LeadBand:
    name: str
    first_half_hour: int
    last_half_hour: int

    @property
    def first_hours(self) -> float:
        return self.first_half_hour / 2

    @property
    def last_hours(self) -> float:
        return self.last_half_hour / 2

    def contains(self, lead_half_hours: int) -> bool:
        return self.first_half_hour <= lead_half_hours <= self.last_half_hour


LEAD_BANDS = (
    LeadBand("0.5-6h", 1, 12),
    LeadBand("6.5-24h", 13, 48),
    LeadBand("24.5-72h", 49, 144),
    LeadBand("72.5-168h", 145, 336),
)


def expanding_folds(
    history_start: object,
    history_end: object,
    config: ProtocolConfig = ProtocolConfig(),
) -> tuple[ProtocolFold, ...]:
    """Return full expanding folds inside ``[history_start, history_end)``.

    The training start stays fixed while its end advances by 28 days by
    default.  Partial evaluation windows are never emitted.
    """

    start, end = pd.Timestamp(history_start), pd.Timestamp(history_end)
    if pd.isna(start) or pd.isna(end) or start >= end:
        raise ValueError("history_start must precede history_end")
    if (start.tz is None) != (end.tz is None):
        raise ValueError("history bounds must have matching timezone awareness")

    day = pd.Timedelta(days=1)
    train_end = start + config.minimum_train_days * day
    result: list[ProtocolFold] = []
    while True:
        select_end = train_end + config.select_days * day
        calibrate_end = select_end + config.calibrate_days * day
        alert_end = calibrate_end + config.alert_days * day
        evaluate_end = alert_end + config.evaluate_days * day
        if evaluate_end > end:
            break
        result.append(ProtocolFold(
            name=f"fold_{len(result):02d}_{alert_end.strftime('%Y%m%d')}",
            train_start=start,
            train_end=train_end,
            select_end=select_end,
            calibrate_end=calibrate_end,
            alert_end=alert_end,
            evaluate_end=evaluate_end,
        ))
        train_end += config.advance_days * day
    return tuple(result)


def partition_masks(
    origin: Sequence[object],
    delivery: Sequence[object],
    fold: ProtocolFold,
    maturity_delay_minutes: int = 30,
) -> dict[str, np.ndarray]:
    """Build disjoint masks, purging deliveries that mature at/after an end.

    ``delivery + maturity_delay`` must be strictly earlier than the partition
    end.  This makes a delivery exactly 30 minutes before a boundary ineligible.
    """

    if maturity_delay_minutes < 0:
        raise ValueError("maturity_delay_minutes cannot be negative")
    origins, deliveries = pd.DatetimeIndex(origin), pd.DatetimeIndex(delivery)
    if len(origins) != len(deliveries):
        raise ValueError("origin and delivery must have equal length")
    if origins.hasnans or deliveries.hasnans:
        raise ValueError("origin and delivery timestamps cannot be missing")
    if origins.tz != deliveries.tz or origins.tz != fold.train_start.tz:
        raise ValueError("row and fold timestamps must use the same timezone")
    if np.any(deliveries < origins):
        raise ValueError("delivery cannot precede origin")

    matured = deliveries + pd.Timedelta(minutes=maturity_delay_minutes)
    masks = {
        name: np.asarray((origins >= lower) & (matured < upper), dtype=bool)
        for name, (lower, upper) in zip(PARTITIONS, fold.windows())
    }
    membership = np.sum(np.vstack(tuple(masks.values())), axis=0)
    if np.any(membership > 1):
        raise AssertionError("chronological partition masks overlap")
    return masks


def one_row_per_origin(
    frame: pd.DataFrame,
    origin_column: str = "origin",
    constant_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """Return the first stable row per origin for origin-state clustering.

    Callers can nominate origin-state columns that must be identical across
    repeated lead rows.  Delivery-specific columns should not be nominated.
    """

    if origin_column not in frame:
        raise KeyError(origin_column)
    missing = set(constant_columns) - set(frame.columns)
    if missing:
        raise KeyError(f"missing constant columns: {sorted(missing)}")
    if frame[origin_column].isna().any():
        raise ValueError("origin cannot be missing")
    if constant_columns:
        variation = frame.groupby(origin_column, sort=False, dropna=False)[list(constant_columns)].nunique(dropna=False)
        bad = variation.gt(1).any(axis=1)
        if bad.any():
            raise ValueError(f"origin-state values vary within {int(bad.sum())} origins")
    return frame.drop_duplicates(origin_column, keep="first").copy()


def origin_balanced_weights(origins: Sequence[object]) -> np.ndarray:
    """Give every origin total weight one, irrespective of repeated leads."""

    values = np.asarray(origins)
    if values.ndim != 1:
        raise ValueError("origins must be one-dimensional")
    if len(values) == 0:
        return np.array([], dtype=float)
    if pd.isna(values).any():
        raise ValueError("origins cannot be missing")
    _, inverse, counts = np.unique(values, return_inverse=True, return_counts=True)
    return 1.0 / counts[inverse]


def lead_band(lead_half_hours: int) -> LeadBand:
    """Return the frozen band for a positive half-hour lead through 168h."""

    if not isinstance(lead_half_hours, (int, np.integer)):
        raise TypeError("lead_half_hours must be an integer")
    for band in LEAD_BANDS:
        if band.contains(int(lead_half_hours)):
            return band
    raise ValueError("lead must be between 1 and 336 half-hours (0.5 to 168h)")


def _matched_arrays(*values: Sequence[float]) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(value, dtype=float) for value in values)
    if not arrays or any(array.ndim != 1 for array in arrays):
        raise ValueError("metric inputs must be one-dimensional")
    if len({len(array) for array in arrays}) != 1:
        raise ValueError("metric inputs must have equal length")
    if any(not np.isfinite(array).all() for array in arrays):
        raise ValueError("metrics require explicit matched finite rows")
    return arrays


def _weights(weights: Sequence[float] | None, length: int) -> np.ndarray:
    value = np.ones(length, dtype=float) if weights is None else np.asarray(weights, dtype=float)
    if value.ndim != 1 or len(value) != length:
        raise ValueError("weights must be one-dimensional and match the rows")
    if not np.isfinite(value).all() or np.any(value < 0) or value.sum() <= 0:
        raise ValueError("weights must be finite, non-negative and have positive mass")
    return value


def _weighted_quantile(values: np.ndarray, quantile: float, weights: np.ndarray | None) -> float:
    if weights is None:
        return float(np.quantile(values, quantile))
    order = np.argsort(values, kind="mergesort")
    value, weight = values[order], weights[order]
    positions = (np.cumsum(weight) - 0.5 * weight) / weight.sum()
    return float(np.interp(quantile, positions, value, left=value[0], right=value[-1]))


def regression_metrics(
    actual: Sequence[float],
    prediction: Sequence[float],
    weights: Sequence[float] | None = None,
) -> dict[str, float | int]:
    """Matched point metrics; absolute-error tails are P90/P95/P99."""

    actual_array, prediction_array = _matched_arrays(actual, prediction)
    if len(actual_array) == 0:
        return {"n": 0}
    weight = _weights(weights, len(actual_array))
    error = prediction_array - actual_array
    absolute = np.abs(error)
    quantile_weight = None if weights is None else weight
    return {
        "n": len(actual_array),
        "mae": float(np.average(absolute, weights=weight)),
        "rmse": float(np.sqrt(np.average(error ** 2, weights=weight))),
        "bias": float(np.average(error, weights=weight)),
        "positive_overstatement": float(np.average(np.maximum(error, 0), weights=weight)),
        "overstatement_100_rate": float(np.average(error > 100, weights=weight)),
        "overstatement_200_rate": float(np.average(error > 200, weights=weight)),
        "p90_absolute_error": _weighted_quantile(absolute, 0.90, quantile_weight),
        "p95_absolute_error": _weighted_quantile(absolute, 0.95, quantile_weight),
        "p99_absolute_error": _weighted_quantile(absolute, 0.99, quantile_weight),
    }


def interval_metrics(
    actual: Sequence[float],
    median: Sequence[float],
    lower80: Sequence[float],
    upper80: Sequence[float],
    lower95: Sequence[float],
    upper95: Sequence[float],
    weights: Sequence[float] | None = None,
) -> dict[str, float | int]:
    """Coverage, width, interval scores and WIS for 80%/95% intervals."""

    y, centre, lo80, hi80, lo95, hi95 = _matched_arrays(
        actual, median, lower80, upper80, lower95, upper95
    )
    if len(y) == 0:
        return {"n": 0}
    if np.any(lo80 > hi80) or np.any(lo95 > hi95):
        raise ValueError("lower interval endpoints cannot exceed upper endpoints")
    weight = _weights(weights, len(y))

    components: list[np.ndarray] = []
    result: dict[str, float | int] = {"n": len(y)}
    for nominal, alpha, lower, upper in (
        (80, 0.20, lo80, hi80),
        (95, 0.05, lo95, hi95),
    ):
        width = upper - lower
        score = width + (2 / alpha) * np.maximum(lower - y, 0) + (2 / alpha) * np.maximum(y - upper, 0)
        result[f"coverage_{nominal}"] = float(np.average((y >= lower) & (y <= upper), weights=weight))
        result[f"width_{nominal}"] = float(np.average(width, weights=weight))
        result[f"interval_score_{nominal}"] = float(np.average(score, weights=weight))
        components.append((alpha / 2) * score)

    crossing = (lo95 > lo80) | (lo80 > centre) | (centre > hi80) | (hi80 > hi95)
    result["crossing_rate"] = float(np.average(crossing, weights=weight))
    wis = (0.5 * np.abs(y - centre) + np.sum(components, axis=0)) / 2.5
    result["wis"] = float(np.average(wis, weights=weight))
    return result


def moving_block_indices(
    calendar_days: int,
    block_days: int,
    replicates: int = 2_000,
    seed: int = DEFAULT_SEED,
) -> np.ndarray:
    """Sample non-wrapping contiguous calendar-day blocks deterministically."""

    if block_days <= 0 or calendar_days < block_days:
        raise ValueError("calendar_days must be at least one positive block")
    if replicates <= 0:
        raise ValueError("replicates must be positive")
    rng = np.random.default_rng(seed)
    blocks_per_draw = int(np.ceil(calendar_days / block_days))
    starts = rng.integers(0, calendar_days - block_days + 1, size=(replicates, blocks_per_draw))
    indices = starts[:, :, None] + np.arange(block_days)
    return indices.reshape(replicates, -1)[:, :calendar_days]


def paired_block_bootstrap(
    actual: Sequence[float],
    challenger: Sequence[float],
    control: Sequence[float],
    origins: Sequence[object],
    block_days: int,
    replicates: int = 2_000,
    seed: int = DEFAULT_SEED,
) -> dict[str, object]:
    """Paired MAE effect interval, first balancing repeated leads by origin.

    Positive effects favour the challenger: ``control MAE - challenger MAE``.
    Missing calendar dates are retained with zero observations so bootstrap
    blocks never splice non-adjacent observed days together.
    """

    y, candidate, baseline = _matched_arrays(actual, challenger, control)
    origin_index = pd.DatetimeIndex(origins)
    if len(origin_index) != len(y) or origin_index.hasnans:
        raise ValueError("origins must be complete and match metric rows")
    if len(y) == 0:
        return {"status": "insufficient_support", "rows": 0, "origins": 0, "calendar_days": 0}

    rows = pd.DataFrame({
        "origin": origin_index,
        "challenger_loss": np.abs(y - candidate),
        "control_loss": np.abs(y - baseline),
    })
    per_origin = rows.groupby("origin", sort=True)[["challenger_loss", "control_loss"]].mean()
    per_origin["day"] = per_origin.index.normalize()
    daily = per_origin.groupby("day")[["challenger_loss", "control_loss"]].agg(["sum", "count"])
    daily.columns = ["challenger_sum", "challenger_count", "control_sum", "control_count"]
    calendar = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(calendar, fill_value=0)
    calendar_days = len(daily)
    minimum_days = 2 * block_days
    if calendar_days < minimum_days:
        return {
            "status": "insufficient_support",
            "rows": len(y),
            "origins": len(per_origin),
            "calendar_days": calendar_days,
            "block_days": block_days,
            "minimum_calendar_days": minimum_days,
        }

    indices = moving_block_indices(calendar_days, block_days, replicates, seed)
    challenger_sum = daily["challenger_sum"].to_numpy()
    control_sum = daily["control_sum"].to_numpy()
    counts = daily["challenger_count"].to_numpy()
    sampled_count = counts[indices].sum(axis=1)
    valid = sampled_count > 0
    challenger_draw = challenger_sum[indices].sum(axis=1)[valid] / sampled_count[valid]
    control_draw = control_sum[indices].sum(axis=1)[valid] / sampled_count[valid]
    effect_draw = control_draw - challenger_draw
    percent_draw = np.divide(
        100 * effect_draw,
        control_draw,
        out=np.full_like(effect_draw, np.nan),
        where=control_draw > 0,
    )
    total_count = counts.sum()
    challenger_mae = challenger_sum.sum() / total_count
    control_mae = control_sum.sum() / total_count
    effect = control_mae - challenger_mae
    percent = 100 * effect / control_mae if control_mae > 0 else np.nan
    finite_percent = percent_draw[np.isfinite(percent_draw)]
    # The sign-based two-sided bootstrap probability is descriptive evidence;
    # family-wise adjustment is applied when cells are assembled in the report.
    lower_tail = (1 + np.sum(effect_draw <= 0)) / (len(effect_draw) + 1)
    upper_tail = (1 + np.sum(effect_draw >= 0)) / (len(effect_draw) + 1)
    return {
        "status": "measured",
        "rows": len(y),
        "origins": len(per_origin),
        "calendar_days": calendar_days,
        "block_days": block_days,
        "replicates": replicates,
        "challenger_mae": float(challenger_mae),
        "control_mae": float(control_mae),
        "effect_mae": float(effect),
        "effect_percent": float(percent),
        "p_value_two_sided": float(min(1.0, 2 * min(lower_tail, upper_tail))),
        "effect_mae_ci95": np.quantile(effect_draw, [0.025, 0.975]).tolist(),
        "effect_percent_ci95": (
            np.quantile(finite_percent, [0.025, 0.975]).tolist() if len(finite_percent) else [np.nan, np.nan]
        ),
    }


def paired_effect_intervals(
    actual: Sequence[float],
    challenger: Sequence[float],
    control: Sequence[float],
    origins: Sequence[object],
    block_days: Iterable[int] = (7, 14),
    replicates: int = 2_000,
    seed: int = DEFAULT_SEED,
) -> dict[str, dict[str, object]]:
    """Return the predeclared 7- and 14-day paired sensitivity results."""

    return {
        str(days): paired_block_bootstrap(
            actual, challenger, control, origins, days, replicates=replicates, seed=seed
        )
        for days in block_days
    }


def holm_adjust(pvalues: Sequence[float]) -> np.ndarray:
    """Holm family-wise p-value adjustment, preserving missing entries."""

    values = np.asarray(pvalues, dtype=float)
    if values.ndim != 1:
        raise ValueError("pvalues must be one-dimensional")
    finite = np.isfinite(values)
    if np.any((values[finite] < 0) | (values[finite] > 1)):
        raise ValueError("finite p-values must lie between zero and one")
    result = np.full(len(values), np.nan)
    if not finite.any():
        return result
    positions = np.flatnonzero(finite)
    subset = values[finite]
    order = np.argsort(subset, kind="mergesort")
    adjusted = np.maximum.accumulate((len(subset) - np.arange(len(subset))) * subset[order])
    restored = np.empty(len(subset), dtype=float)
    restored[order] = np.minimum(adjusted, 1.0)
    result[positions] = restored
    return result


def regime_stability(labelings: Sequence[Sequence[object]]) -> dict[str, object]:
    """Pairwise adjusted Rand stability across seeds or day-block fits."""

    arrays = [np.asarray(labels) for labels in labelings]
    if len(arrays) < 2:
        return {"status": "insufficient_fits", "comparisons": 0, "median_ari": np.nan, "ari": []}
    lengths = {len(labels) for labels in arrays}
    if len(lengths) != 1 or not lengths.pop():
        raise ValueError("all labelings must cover the same non-empty observations")
    scores = [float(adjusted_rand_score(left, right)) for left, right in combinations(arrays, 2)]
    return {
        "status": "measured",
        "comparisons": len(scores),
        "median_ari": float(np.median(scores)),
        "ari": scores,
    }


def recurring_regime_screen(
    stability_ari: float | Sequence[float],
    training_days: int,
    evaluation_days: int,
    minimum_ari: float = 0.70,
    minimum_training_days: int = 30,
    minimum_evaluation_days: int = 14,
) -> dict[str, object]:
    """Apply the predeclared recurring-regime stability/support convention."""

    scores = np.atleast_1d(np.asarray(stability_ari, dtype=float))
    finite = scores[np.isfinite(scores)]
    median_ari = float(np.median(finite)) if len(finite) else np.nan
    checks = {
        "stable": bool(np.isfinite(median_ari) and median_ari >= minimum_ari),
        "training_support": bool(training_days >= minimum_training_days),
        "evaluation_support": bool(evaluation_days >= minimum_evaluation_days),
    }
    return {
        "recurring": all(checks.values()),
        "median_ari": median_ari,
        "training_days": int(training_days),
        "evaluation_days": int(evaluation_days),
        "thresholds": {
            "minimum_ari": minimum_ari,
            "minimum_training_days": minimum_training_days,
            "minimum_evaluation_days": minimum_evaluation_days,
        },
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
    }


def limited_support_flags(
    evaluation_days: int | Sequence[object],
    incidents: int,
    minimum_evaluation_weeks: int = 8,
    minimum_incidents: int = 30,
) -> dict[str, object]:
    """Flag results with fewer than 8 evaluation weeks or 30 incidents."""

    if isinstance(evaluation_days, (int, np.integer)):
        days = int(evaluation_days)
    else:
        index = pd.DatetimeIndex(evaluation_days)
        if index.hasnans:
            raise ValueError("evaluation dates cannot be missing")
        days = int(index.normalize().nunique())
    if days < 0 or incidents < 0:
        raise ValueError("support counts cannot be negative")
    minimum_days = minimum_evaluation_weeks * 7
    flags = {
        "evaluation_history": days < minimum_days,
        "incidents": incidents < minimum_incidents,
    }
    return {
        "limited_support": any(flags.values()),
        "evaluation_days": days,
        "evaluation_weeks": days / 7,
        "incidents": int(incidents),
        "thresholds": {
            "minimum_evaluation_weeks": minimum_evaluation_weeks,
            "minimum_incidents": minimum_incidents,
        },
        "flags": flags,
    }
