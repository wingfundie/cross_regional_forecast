"""Training-only, signed generator-sensitivity representations.

This module has no data-loading side effects.  The caller supplies the exact
equation/version universe and its training-period exposure weights.  Versions
outside that universe are ignored, which keeps fold fitting chronological.

The canonical coefficient is ``sensitivity = -FACTOR / ic_factor``.  A missing
coefficient for a DUID in a *verified* equation version is a structural zero.
A version whose coefficient record is unavailable is kept distinguishable and
never transformed to zero pressure.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.cluster import KMeans
from sklearn.decomposition import TruncatedSVD


REQUIRED_COLUMNS = (
    "version_key", "GENCONID", "DUID", "FACTOR", "ic_factor", "sensitivity",
)
VALID_DIRECTIONS = {"upper", "lower"}


def _exposure_series(
    exposure_weights: Mapping[str, float] | pd.Series | pd.DataFrame,
) -> pd.Series:
    """Return a deterministic, validated training-version exposure series."""
    if isinstance(exposure_weights, pd.DataFrame):
        required = {"version_key", "exposure_weight"}
        missing = required.difference(exposure_weights.columns)
        if missing:
            raise ValueError(f"Exposure frame missing columns: {sorted(missing)}")
        if exposure_weights["version_key"].duplicated().any():
            raise ValueError("Exposure weights contain duplicate version_key rows")
        values = pd.Series(
            exposure_weights["exposure_weight"].to_numpy(),
            index=exposure_weights["version_key"].to_numpy(),
        )
    elif isinstance(exposure_weights, pd.Series):
        if exposure_weights.index.has_duplicates:
            raise ValueError("Exposure weights contain duplicate version keys")
        values = exposure_weights.copy()
    else:
        values = pd.Series(dict(exposure_weights), dtype="float64")
    if values.empty:
        raise ValueError("At least one training version exposure is required")
    if values.index.isna().any():
        raise ValueError("Exposure version keys cannot be missing")
    string_index = values.index.map(str)
    if string_index.duplicated().any():
        raise ValueError("Exposure version keys collide after string conversion")
    numeric = pd.to_numeric(values, errors="coerce").astype("float64")
    numeric.index = string_index
    if not np.isfinite(numeric.to_numpy()).all() or (numeric < 0).any():
        raise ValueError("Exposure weights must be finite and non-negative")
    return numeric.sort_index()


def _slug(value: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "feature"
    return token


def _unique_tokens(labels: Sequence[str]) -> tuple[str, ...]:
    tokens: list[str] = []
    used: set[str] = set()
    for label in labels:
        base = _slug(label)
        token = base
        if token in used:
            digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:8]
            token = f"{base}_{digest}"
        while token in used:
            token += "_x"
        used.add(token)
        tokens.append(token)
    return tuple(tokens)


@dataclass(frozen=True)
class SensitivityMatrix:
    """Sparse equation/version-by-DUID sensitivity matrix and coverage state."""

    version_keys: tuple[str, ...]
    duids: tuple[str, ...]
    values: sparse.csr_matrix
    recorded: sparse.csr_matrix
    exposure_weights: np.ndarray
    available_versions: np.ndarray
    ic_factors: np.ndarray
    genconids: tuple[str | None, ...]
    audit: dict[str, object]

    def __post_init__(self) -> None:
        shape = (len(self.version_keys), len(self.duids))
        if self.values.shape != shape or self.recorded.shape != shape:
            raise ValueError("Sensitivity matrices do not match labels")
        if len(self.exposure_weights) != shape[0]:
            raise ValueError("Exposure weights do not match version labels")
        if len(self.available_versions) != shape[0] or len(self.ic_factors) != shape[0]:
            raise ValueError("Version metadata does not match version labels")

    @property
    def directions(self) -> np.ndarray:
        """Return ``upper``, ``lower`` or ``unavailable`` per version."""
        return np.where(
            ~self.available_versions,
            "unavailable",
            np.where(self.ic_factors > 0, "upper", "lower"),
        )

    @property
    def version_index(self) -> dict[str, int]:
        return {value: i for i, value in enumerate(self.version_keys)}

    @property
    def duid_index(self) -> dict[str, int]:
        return {value: i for i, value in enumerate(self.duids)}

    def weighted_generator_vectors(self) -> sparse.csr_matrix:
        """DUID-by-version vectors weighted by training equation exposure."""
        eligible = self.available_versions & (self.exposure_weights > 0)
        if not eligible.any():
            raise ValueError("No available equation version has positive exposure")
        weights = self.exposure_weights[eligible].astype("float64")
        weights = weights / weights.sum()
        weighted = self.values[eligible].multiply(np.sqrt(weights)[:, None])
        return weighted.T.tocsr()

    def metadata_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "version_key": self.version_keys,
            "GENCONID": self.genconids,
            "exposure_weight": self.exposure_weights,
            "available": self.available_versions,
            "ic_factor": self.ic_factors,
            "direction": self.directions,
        })


def build_sensitivity_matrix(
    training_rows: pd.DataFrame,
    exposure_weights: Mapping[str, float] | pd.Series | pd.DataFrame,
    *,
    verified_versions: Iterable[str] | None = None,
    weak_ic_factor: float = 1e-8,
    max_abs_sensitivity: float = 100.0,
    consistency_rtol: float = 1e-7,
    consistency_atol: float = 1e-10,
) -> SensitivityMatrix:
    """Build a sparse signed matrix from an authoritative training universe.

    ``exposure_weights`` defines the only equation versions eligible for this
    fit.  If ``verified_versions`` is supplied, a version is available only if
    it is both on that list and has one consistent, finite, non-weak IC factor
    in ``training_rows``.  Rows with a missing DUID may be used as version
    metadata markers; they are not coefficient records.
    """
    missing = set(REQUIRED_COLUMNS).difference(training_rows.columns)
    if missing:
        raise ValueError(f"Sensitivity rows missing columns: {sorted(missing)}")
    if not np.isfinite(weak_ic_factor) or weak_ic_factor <= 0:
        raise ValueError("weak_ic_factor must be finite and positive")
    if not np.isfinite(max_abs_sensitivity) or max_abs_sensitivity <= 0:
        raise ValueError("max_abs_sensitivity must be finite and positive")

    exposures = _exposure_series(exposure_weights)
    versions = tuple(exposures.index.tolist())
    version_set = set(versions)
    requested = None if verified_versions is None else {str(v) for v in verified_versions}

    frame = training_rows.loc[:, REQUIRED_COLUMNS].copy()
    raw_version = frame["version_key"]
    frame["_version"] = raw_version.where(raw_version.notna(), "").map(str)
    in_scope = frame["_version"].isin(version_set)
    rows_outside = int((~in_scope).sum())
    frame = frame.loc[in_scope].copy()
    for column in ("FACTOR", "ic_factor", "sensitivity"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    raw_duid = frame["DUID"]
    frame["_duid"] = raw_duid.where(raw_duid.notna(), "").map(str).str.strip()
    coefficient_row = frame["_duid"].ne("")

    finite_ic = np.isfinite(frame["ic_factor"])
    strong_ic = finite_ic & frame["ic_factor"].abs().ge(weak_ic_factor)
    metadata = frame.loc[strong_ic, ["_version", "GENCONID", "ic_factor"]].copy()

    conflicting_factor_versions: set[str] = set()
    conflicting_gencon_versions: set[str] = set()
    version_factor: dict[str, float] = {}
    version_gencon: dict[str, str | None] = {}
    for version, group in metadata.groupby("_version", sort=True):
        factors = group["ic_factor"].dropna().to_numpy(dtype="float64")
        reference = float(factors[0])
        if not np.allclose(factors, reference, rtol=consistency_rtol, atol=consistency_atol):
            conflicting_factor_versions.add(version)
            continue
        gencons = sorted({str(x) for x in group["GENCONID"].dropna() if str(x)})
        if len(gencons) > 1:
            conflicting_gencon_versions.add(version)
            continue
        version_factor[version] = reference
        version_gencon[version] = gencons[0] if gencons else None

    available_set = set(version_factor)
    if requested is not None:
        available_set &= requested
    available_set -= conflicting_factor_versions | conflicting_gencon_versions

    finite_factor = np.isfinite(frame["FACTOR"])
    finite_sensitivity = np.isfinite(frame["sensitivity"])
    expected = -frame["FACTOR"] / frame["ic_factor"]
    consistent = np.isclose(
        frame["sensitivity"], expected,
        rtol=consistency_rtol, atol=consistency_atol, equal_nan=False,
    )
    extreme = finite_sensitivity & frame["sensitivity"].abs().gt(max_abs_sensitivity)
    coefficient_quality = strong_ic & finite_factor & finite_sensitivity & consistent & ~extreme
    # If a published coefficient row for an otherwise verified version is
    # corrupt, the equation record is incomplete.  Excluding just that DUID
    # would incorrectly turn a bad record into a structural zero.
    bad_record_versions = set(frame.loc[
        coefficient_row & frame["_version"].isin(available_set) & ~coefficient_quality,
        "_version",
    ])
    available_set -= bad_record_versions
    version_available = frame["_version"].isin(available_set)
    valid = coefficient_row & version_available & coefficient_quality

    valid_rows = frame.loc[valid, [
        "_version", "_duid", "FACTOR", "ic_factor", "sensitivity",
    ]].copy()
    duplicate_mask = valid_rows.duplicated(keep="first")
    exact_duplicates = int(duplicate_mask.sum())
    valid_rows = valid_rows.loc[~duplicate_mask]
    # Recompute from the canonical equation terms after validating the supplied
    # sensitivity.  This preserves sign while avoiding accumulated rounding.
    valid_rows["_canonical"] = -valid_rows["FACTOR"] / valid_rows["ic_factor"]
    grouped = (valid_rows.groupby(["_version", "_duid"], sort=True, as_index=False)
               .agg(sensitivity=("_canonical", "sum"), source_rows=("_canonical", "size")))
    aggregate_extreme = grouped["sensitivity"].abs().gt(max_abs_sensitivity)
    aggregate_extreme_pairs = int(aggregate_extreme.sum())
    aggregate_bad_versions = set(grouped.loc[aggregate_extreme, "_version"])
    available_set -= aggregate_bad_versions
    grouped = grouped.loc[grouped["_version"].isin(available_set)].copy()
    valid_rows = valid_rows.loc[valid_rows["_version"].isin(available_set)].copy()

    duids = tuple(sorted(grouped["_duid"].unique().tolist()))
    version_index = {value: i for i, value in enumerate(versions)}
    duid_index = {value: i for i, value in enumerate(duids)}
    row_indices = grouped["_version"].map(version_index).to_numpy(dtype="int64")
    column_indices = grouped["_duid"].map(duid_index).to_numpy(dtype="int64")
    shape = (len(versions), len(duids))
    values = sparse.csr_matrix(
        (grouped["sensitivity"].to_numpy(dtype="float64"), (row_indices, column_indices)),
        shape=shape,
    )
    recorded = sparse.csr_matrix(
        (np.ones(len(grouped), dtype="int8"), (row_indices, column_indices)),
        shape=shape,
    )
    available = np.array([version in available_set for version in versions], dtype=bool)
    ic_factors = np.array([version_factor.get(version, np.nan) for version in versions])
    genconids = tuple(version_gencon.get(version) for version in versions)
    absent_verified = int(available.sum() * len(duids) - recorded[available].nnz)

    coefficient_count = int(coefficient_row.sum())
    rejected = coefficient_row & ~valid
    audit: dict[str, object] = {
        "input_rows": int(len(training_rows)),
        "training_scope_rows": int(len(frame)),
        "rows_outside_training_versions": rows_outside,
        "metadata_only_rows": int((~coefficient_row).sum()),
        "coefficient_rows": coefficient_count,
        "accepted_source_rows": int(len(valid_rows)),
        "accepted_version_duid_pairs": int(len(grouped)),
        "rejected_coefficient_rows": int(rejected.sum()),
        "rejected_nonfinite_factor": int((coefficient_row & ~finite_factor).sum()),
        "rejected_nonfinite_ic_factor": int((coefficient_row & ~finite_ic).sum()),
        "rejected_weak_ic_factor": int((coefficient_row & finite_ic & ~strong_ic).sum()),
        "rejected_nonfinite_sensitivity": int((coefficient_row & ~finite_sensitivity).sum()),
        "rejected_sensitivity_mismatch": int((
            coefficient_row & finite_factor & strong_ic & finite_sensitivity & ~consistent
        ).sum()),
        "rejected_extreme_sensitivity": int((coefficient_row & extreme).sum()),
        "rejected_unverified_version_rows": int((coefficient_row & ~version_available).sum()),
        "exact_duplicate_rows_removed": exact_duplicates,
        "aggregate_extreme_pairs_removed": aggregate_extreme_pairs,
        "training_version_count": len(versions),
        "verified_version_count": int(available.sum()),
        "unavailable_version_count": int((~available).sum()),
        "conflicting_ic_factor_versions": sorted(conflicting_factor_versions),
        "conflicting_genconid_versions": sorted(conflicting_gencon_versions),
        "versions_with_rejected_coefficient_records": sorted(bad_record_versions),
        "versions_with_aggregate_extreme_sensitivity": sorted(aggregate_bad_versions),
        "absent_verified_coefficient_cells": absent_verified,
        "duid_count": len(duids),
        "weak_ic_factor_threshold": float(weak_ic_factor),
        "max_abs_sensitivity": float(max_abs_sensitivity),
    }
    return SensitivityMatrix(
        version_keys=versions,
        duids=duids,
        values=values,
        recorded=recorded,
        exposure_weights=exposures.to_numpy(dtype="float64"),
        available_versions=available,
        ic_factors=ic_factors,
        genconids=genconids,
        audit=audit,
    )


@dataclass
class GeneratorRepresentation:
    """A frozen manual, K-means, or signed-SVD generator representation."""

    name: str
    kind: str
    sensitivity: SensitivityMatrix
    feature_labels: tuple[str, ...]
    feature_tokens: tuple[str, ...]
    unit_group: np.ndarray | None = None
    components: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"manual", "kmeans", "svd"}:
            raise ValueError(f"Unknown representation kind: {self.kind}")
        if len(self.feature_labels) != len(self.feature_tokens):
            raise ValueError("Feature labels and tokens differ in length")
        if self.kind == "svd":
            if self.components is None:
                raise ValueError("SVD representation requires components")
            if self.components.shape != (len(self.feature_labels), len(self.sensitivity.duids)):
                raise ValueError("SVD component shape does not match matrix")
        else:
            if self.unit_group is None or len(self.unit_group) != len(self.sensitivity.duids):
                raise ValueError("Grouped representation requires one group per DUID")

    @property
    def feature_columns(self) -> tuple[str, ...]:
        columns: list[str] = []
        for token in self.feature_tokens:
            for direction in ("upper", "lower"):
                columns.extend([
                    f"{self.name}__{token}__{direction}_tightening",
                    f"{self.name}__{token}__{direction}_relief",
                ])
        return tuple(columns)

    def assignments(self) -> pd.DataFrame:
        """Return discrete assignments, or signed loadings for SVD."""
        if self.kind != "svd":
            labels = [self.feature_labels[int(value)] for value in self.unit_group]
            tokens = [self.feature_tokens[int(value)] for value in self.unit_group]
            return pd.DataFrame({"DUID": self.sensitivity.duids, "label": labels, "token": tokens})
        rows: list[dict[str, object]] = []
        assert self.components is not None
        for feature, token, loadings in zip(self.feature_labels, self.feature_tokens, self.components):
            for duid, loading in zip(self.sensitivity.duids, loadings):
                rows.append({"DUID": duid, "label": feature, "token": token,
                             "loading": float(loading)})
        return pd.DataFrame(rows)

    def _base_output(self, observation_ids: Sequence[object]) -> pd.DataFrame:
        result = pd.DataFrame(index=pd.Index(observation_ids, name="observation_id"))
        for column in self.feature_columns:
            result[column] = np.nan
        return result

    @staticmethod
    def _direction_values(direction: str, impact: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if direction == "upper":
            return np.maximum(-impact, 0.0), np.maximum(impact, 0.0)
        return np.maximum(impact, 0.0), np.maximum(-impact, 0.0)

    def _write_features(
        self,
        result: pd.DataFrame,
        observation: object,
        direction: str,
        signed_impact: np.ndarray,
    ) -> None:
        tightening, relief = self._direction_values(direction, signed_impact)
        for i, token in enumerate(self.feature_tokens):
            # Known observations use zero in the inactive direction so the
            # resulting wide feature schema is model-ready.
            for side in ("upper", "lower"):
                result.at[observation, f"{self.name}__{token}__{side}_tightening"] = 0.0
                result.at[observation, f"{self.name}__{token}__{side}_relief"] = 0.0
            result.at[observation, f"{self.name}__{token}__{direction}_tightening"] = float(tightening[i])
            result.at[observation, f"{self.name}__{token}__{direction}_relief"] = float(relief[i])

    def _status(
        self,
        rows: pd.DataFrame,
        *,
        observation_col: str,
        version_col: str,
        duid_col: str,
        value_col: str,
        direction_col: str | None,
    ) -> tuple[pd.DataFrame, list[dict[str, object]]]:
        required = {observation_col, version_col, duid_col, value_col}
        if direction_col is not None:
            required.add(direction_col)
        missing = required.difference(rows.columns)
        if missing:
            raise ValueError(f"Transform rows missing columns: {sorted(missing)}")
        if rows.empty:
            empty = self._base_output([])
            return empty, []

        frame = rows.loc[:, list(required)].copy()
        if frame[observation_col].isna().any():
            raise ValueError("Observation identifiers cannot be missing")
        frame[version_col] = frame[version_col].where(frame[version_col].notna(), "").map(str)
        frame[duid_col] = frame[duid_col].where(frame[duid_col].notna(), "").map(str)
        frame[value_col] = pd.to_numeric(frame[value_col], errors="coerce")
        observations = list(pd.unique(frame[observation_col]))
        result = self._base_output(observations)
        version_index = self.sensitivity.version_index
        duid_index = self.sensitivity.duid_index
        statuses: list[dict[str, object]] = []

        for observation, group in frame.groupby(observation_col, sort=False, dropna=False):
            versions = sorted(set(group[version_col]))
            if len(versions) != 1:
                raise ValueError(f"Observation {observation!r} contains multiple version keys")
            version = versions[0]
            vi = version_index.get(version)
            version_known = vi is not None
            version_available = bool(version_known and self.sensitivity.available_versions[vi])
            trained_direction = self.sensitivity.directions[vi] if version_known else "unavailable"

            if direction_col is None:
                direction = str(trained_direction)
                direction_valid = direction in VALID_DIRECTIONS
                direction_mismatch = False
            else:
                directions = sorted(set(group[direction_col].dropna().map(lambda x: str(x).lower())))
                if len(directions) != 1:
                    raise ValueError(f"Observation {observation!r} needs exactly one direction")
                direction = directions[0]
                if direction not in VALID_DIRECTIONS:
                    raise ValueError(f"Invalid direction {direction!r} for observation {observation!r}")
                direction_valid = True
                direction_mismatch = bool(version_available and direction != trained_direction)

            finite = np.isfinite(group[value_col].to_numpy(dtype="float64"))
            known_duid = group[duid_col].isin(duid_index)
            nonzero = group[value_col].fillna(0).abs().gt(0)
            unknown_count = int((~known_duid).sum())
            unknown_nonzero = int((~known_duid & nonzero).sum())
            missing_values = int((~pd.Series(finite, index=group.index)).sum())
            finite_abs = group.loc[finite, value_col].abs()
            total_abs = float(finite_abs.sum())
            known_abs = float(group.loc[finite & known_duid.to_numpy(), value_col].abs().sum())
            if total_abs > 0:
                movement_coverage = known_abs / total_abs
            else:
                movement_coverage = float(known_duid.mean()) if len(group) else 0.0

            required_indices: np.ndarray
            observed_known = set(group.loc[known_duid & pd.Series(finite, index=group.index), duid_col])
            if version_available:
                if self.kind == "svd":
                    assert self.components is not None
                    coefficients = np.asarray(self.sensitivity.values.getrow(vi).toarray()).ravel()
                    scores = coefficients @ self.components.T
                    reconstructed = scores @ self.components
                    required_indices = np.flatnonzero(np.abs(reconstructed) > 1e-12)
                else:
                    coefficients = np.asarray(self.sensitivity.values.getrow(vi).toarray()).ravel()
                    required_indices = np.flatnonzero(np.abs(coefficients) > 0)
            else:
                required_indices = np.array([], dtype="int64")
            required_duids = {self.sensitivity.duids[i] for i in required_indices}
            missing_required = len(required_duids.difference(observed_known))
            required_coverage = (
                (len(required_duids) - missing_required) / len(required_duids)
                if required_duids else (1.0 if version_available else 0.0)
            )
            supported = bool(
                version_available and direction_valid and not direction_mismatch
                and unknown_nonzero == 0 and missing_values == 0 and missing_required == 0
            )
            recorded_count = 0
            implicit_zero_count = 0
            if version_available:
                present_indices = [duid_index[x] for x in group.loc[known_duid, duid_col]]
                if present_indices:
                    marks = np.asarray(
                        self.sensitivity.recorded.getrow(vi)[:, present_indices].toarray()
                    ).ravel().astype(bool)
                    recorded_count = int(marks.sum())
                    implicit_zero_count = int((~marks).sum())
            statuses.append({
                "observation_id": observation,
                "version_key": version or None,
                "direction": direction if direction_valid else None,
                "version_known": version_known,
                "version_available": version_available,
                "unknown_version": not version_known,
                "direction_mismatch": direction_mismatch,
                "unknown_duid": unknown_count > 0,
                "unknown_duid_count": unknown_count,
                "unknown_nonzero_movement_count": unknown_nonzero,
                "missing_value_count": missing_values,
                "required_duid_count": len(required_duids),
                "missing_required_duid_count": missing_required,
                "required_duid_coverage_fraction": float(required_coverage),
                "movement_coverage_fraction": float(movement_coverage),
                "recorded_coefficient_count": recorded_count,
                "implicit_zero_count": implicit_zero_count,
                "pressure_supported": supported,
            })
        return result, statuses

    def transform_movements(
        self,
        movements: pd.DataFrame,
        *,
        observation_col: str = "observation_id",
        version_col: str = "version_key",
        duid_col: str = "DUID",
        movement_col: str = "delta_mw",
        direction_col: str | None = "direction",
        allow_partial: bool = False,
    ) -> pd.DataFrame:
        """Transform caller-computed movements into signed pressure features.

        This method does not derive movement from dispatch or availability.  The
        caller must provide an origin-available movement/scenario column.  By
        default any unsupported observation retains NaN pressure values so a
        downstream pooled fallback can be used.  ``allow_partial=True`` is an
        explicit diagnostic mode and leaves coverage flags in the output.
        """
        result, statuses = self._status(
            movements,
            observation_col=observation_col,
            version_col=version_col,
            duid_col=duid_col,
            value_col=movement_col,
            direction_col=direction_col,
        )
        if not statuses:
            return result.reset_index()
        frame = movements.copy()
        frame[movement_col] = pd.to_numeric(frame[movement_col], errors="coerce")
        vi_lookup = self.sensitivity.version_index
        ui_lookup = self.sensitivity.duid_index
        status_lookup = {row["observation_id"]: row for row in statuses}

        for observation, group in frame.groupby(observation_col, sort=False, dropna=False):
            status = status_lookup[observation]
            if not status["version_available"]:
                continue
            if not status["pressure_supported"] and not allow_partial:
                continue
            vi = vi_lookup[str(status["version_key"])]
            delta = np.zeros(len(self.sensitivity.duids), dtype="float64")
            valid = np.isfinite(group[movement_col]) & group[duid_col].map(str).isin(ui_lookup)
            for duid, value in group.loc[valid].groupby(duid_col, sort=False)[movement_col].sum().items():
                delta[ui_lookup[str(duid)]] = float(value)
            coefficients = np.asarray(self.sensitivity.values.getrow(vi).toarray()).ravel()
            if self.kind == "svd":
                assert self.components is not None
                equation_scores = coefficients @ self.components.T
                movement_scores = self.components @ delta
                impact = equation_scores * movement_scores
            else:
                unit_impact = coefficients * delta
                assert self.unit_group is not None
                impact = np.bincount(
                    self.unit_group, weights=unit_impact, minlength=len(self.feature_labels),
                ).astype("float64")
            self._write_features(result, observation, str(status["direction"]), impact)
        status_frame = pd.DataFrame(statuses).set_index("observation_id")
        return result.join(status_frame).reset_index()

    def aggregate_signed_pressure(
        self,
        pressure_rows: pd.DataFrame,
        *,
        observation_col: str = "observation_id",
        version_col: str = "version_key",
        duid_col: str = "DUID",
        pressure_col: str = "tightening_mw",
        direction_col: str = "direction",
        allow_partial: bool = False,
    ) -> pd.DataFrame:
        """Aggregate precomputed signed pressure without recomputing dispatch.

        ``pressure_col`` must use the project convention: positive values are
        tightening and negative values are relief for the supplied direction.
        Grouped representations retain exact per-unit positive/negative sums.
        SVD features are deterministic signed latent projections and therefore
        are not additive physical MW totals.
        """
        result, statuses = self._status(
            pressure_rows,
            observation_col=observation_col,
            version_col=version_col,
            duid_col=duid_col,
            value_col=pressure_col,
            direction_col=direction_col,
        )
        if not statuses:
            return result.reset_index()
        frame = pressure_rows.copy()
        frame[pressure_col] = pd.to_numeric(frame[pressure_col], errors="coerce")
        ui_lookup = self.sensitivity.duid_index
        status_lookup = {row["observation_id"]: row for row in statuses}
        for observation, group in frame.groupby(observation_col, sort=False, dropna=False):
            status = status_lookup[observation]
            if not status["version_available"]:
                continue
            if not status["pressure_supported"] and not allow_partial:
                continue
            pressure = np.zeros(len(self.sensitivity.duids), dtype="float64")
            valid = np.isfinite(group[pressure_col]) & group[duid_col].map(str).isin(ui_lookup)
            for duid, value in group.loc[valid].groupby(duid_col, sort=False)[pressure_col].sum().items():
                pressure[ui_lookup[str(duid)]] = float(value)
            if self.kind == "svd":
                assert self.components is not None
                signed = self.components @ pressure
                # The input is already direction-oriented tightening pressure.
                tightening = np.maximum(signed, 0.0)
                relief = np.maximum(-signed, 0.0)
            else:
                assert self.unit_group is not None
                tightening = np.bincount(
                    self.unit_group, weights=np.maximum(pressure, 0.0),
                    minlength=len(self.feature_labels),
                ).astype("float64")
                relief = np.bincount(
                    self.unit_group, weights=np.maximum(-pressure, 0.0),
                    minlength=len(self.feature_labels),
                ).astype("float64")
            direction = str(status["direction"])
            for i, token in enumerate(self.feature_tokens):
                for side in ("upper", "lower"):
                    result.at[observation, f"{self.name}__{token}__{side}_tightening"] = 0.0
                    result.at[observation, f"{self.name}__{token}__{side}_relief"] = 0.0
                result.at[observation, f"{self.name}__{token}__{direction}_tightening"] = float(tightening[i])
                result.at[observation, f"{self.name}__{token}__{direction}_relief"] = float(relief[i])
        status_frame = pd.DataFrame(statuses).set_index("observation_id")
        return result.join(status_frame).reset_index()


@dataclass(frozen=True)
class RepresentationSuite:
    models: dict[str, GeneratorRepresentation]
    skipped: dict[str, str]


def _canonical_cluster_groups(labels: np.ndarray, duids: Sequence[str]) -> np.ndarray:
    members: list[tuple[tuple[str, ...], int]] = []
    for label in sorted(set(labels.tolist())):
        group = tuple(sorted(duid for duid, value in zip(duids, labels) if value == label))
        members.append((group, int(label)))
    members.sort(key=lambda item: item[0])
    remap = {old: new for new, (_, old) in enumerate(members)}
    return np.array([remap[int(value)] for value in labels], dtype="int64")


def fit_generator_representations(
    sensitivity: SensitivityMatrix,
    *,
    manual_groups: Mapping[str, str] | None = None,
    manual_other_label: str = "other",
    cluster_sizes: Sequence[int] = (4, 8),
    svd_components: Sequence[int] = (4, 8),
    random_state: int = 741,
) -> RepresentationSuite:
    """Fit deterministic manual, K-means and signed-SVD comparators."""
    if not sensitivity.duids:
        raise ValueError("No accepted DUID sensitivities are available")
    vectors = sensitivity.weighted_generator_vectors()
    models: dict[str, GeneratorRepresentation] = {}
    skipped: dict[str, str] = {}

    if manual_groups is not None:
        labels = tuple(str(manual_groups.get(duid, manual_other_label)) for duid in sensitivity.duids)
        unique = tuple(sorted(set(labels)))
        lookup = {value: i for i, value in enumerate(unique)}
        assignment = np.array([lookup[value] for value in labels], dtype="int64")
        models["manual"] = GeneratorRepresentation(
            name="manual", kind="manual", sensitivity=sensitivity,
            feature_labels=unique, feature_tokens=_unique_tokens(unique), unit_group=assignment,
        )

    for raw_k in cluster_sizes:
        k = int(raw_k)
        name = f"kmeans_k{k}"
        if k < 1 or k > len(sensitivity.duids):
            skipped[name] = f"requires 1 <= k <= {len(sensitivity.duids)}"
            continue
        estimator = KMeans(
            n_clusters=k, random_state=random_state, n_init=20,
            algorithm="lloyd", max_iter=500,
        )
        labels = estimator.fit_predict(vectors)
        assignment = _canonical_cluster_groups(labels, sensitivity.duids)
        actual = len(set(assignment.tolist()))
        if actual != k:
            skipped[name] = f"only {actual} distinct clusters were identified"
            continue
        feature_labels = tuple(f"cluster_{i:02d}" for i in range(k))
        models[name] = GeneratorRepresentation(
            name=name, kind="kmeans", sensitivity=sensitivity,
            feature_labels=feature_labels, feature_tokens=feature_labels,
            unit_group=assignment,
        )

    max_rank = min(vectors.shape)
    for raw_n in svd_components:
        n = int(raw_n)
        name = f"svd_n{n}"
        if n < 1 or n > max_rank:
            skipped[name] = f"requires 1 <= components <= {max_rank}"
            continue
        estimator = TruncatedSVD(n_components=n, n_iter=10, random_state=random_state)
        estimator.fit(vectors.T)
        components = estimator.components_.astype("float64", copy=True)
        # Resolve SVD sign indeterminacy: the largest absolute DUID loading is
        # always positive.  Component contributions remain algebraically equal.
        for i in range(len(components)):
            pivot = int(np.argmax(np.abs(components[i])))
            if components[i, pivot] < 0:
                components[i] *= -1.0
        feature_labels = tuple(f"component_{i:02d}" for i in range(n))
        models[name] = GeneratorRepresentation(
            name=name, kind="svd", sensitivity=sensitivity,
            feature_labels=feature_labels, feature_tokens=feature_labels,
            components=components,
        )
    return RepresentationSuite(models=models, skipped=skipped)
