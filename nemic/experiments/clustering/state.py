"""Train-only clustering of observable interconnector state.

The objects in this module deliberately separate ``fit`` from ``transform``.
Callers are responsible for passing only an eligible training partition to
``fit``; selection, calibration and evaluation frames should only ever be
passed to ``transform`` or ``augment``.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import ceil
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import RobustScaler


@dataclass(frozen=True)
class StateAssignments:
    """Cluster assignments aligned to the input frame's index."""

    labels: pd.Series
    probabilities: pd.DataFrame
    distance: pd.Series
    out_of_distribution: pd.Series

    def frame(self, prefix: str = "state_cluster") -> pd.DataFrame:
        """Return assignments as a single, consistently named frame."""

        result = pd.DataFrame(index=self.labels.index)
        result[f"{prefix}__label"] = self.labels.astype("int32")
        for position, column in enumerate(self.probabilities.columns):
            result[f"{prefix}__probability_{position}"] = self.probabilities[column]
        result[f"{prefix}__distance"] = self.distance.astype("float64")
        result[f"{prefix}__ood"] = self.out_of_distribution.astype(bool)
        return result


@dataclass(frozen=True)
class StabilityReport:
    """Pairwise adjusted-Rand stability on a training population."""

    seed_scores: pd.DataFrame
    block_scores: pd.DataFrame
    seed_mean_ari: float
    block_mean_ari: float
    seeds: tuple[int, ...]
    block_days: int


class StateClusterer:
    """Fit deterministic hard or soft clusters to training-only state data.

    Each declared feature group receives equal aggregate Euclidean weight:
    after median imputation and robust scaling, columns in a group are
    multiplied by ``1 / sqrt(number of retained columns in the group)``.
    Constant and near-duplicate columns are detected on the training frame and
    remain excluded for all later transforms.

    ``n_clusters=1`` is a genuine no-segmentation control. It does not invoke a
    clustering algorithm, but still supplies distances and a train-fitted OOD
    threshold so it has the same downstream interface as other candidates.
    """

    METHODS = frozenset({"kmeans", "gmm"})

    def __init__(
        self,
        *,
        n_clusters: int,
        method: str = "kmeans",
        feature_groups: Mapping[str, Sequence[str]] | None = None,
        random_state: int = 741,
        maximum_missing_fraction: float = 0.8,
        near_duplicate_threshold: float = 0.9995,
        constant_tolerance: float = 1e-12,
        ood_quantile: float = 0.99,
        clip_value: float | None = 10.0,
        kmeans_n_init: int = 20,
        gmm_n_init: int = 5,
        gmm_reg_covar: float = 1e-6,
    ) -> None:
        method = str(method).lower()
        if method not in self.METHODS:
            raise ValueError(f"method must be one of {sorted(self.METHODS)}")
        if int(n_clusters) != n_clusters or n_clusters < 1:
            raise ValueError("n_clusters must be a positive integer")
        if not 0.0 <= maximum_missing_fraction < 1.0:
            raise ValueError("maximum_missing_fraction must be in [0, 1)")
        if not 0.0 < near_duplicate_threshold <= 1.0:
            raise ValueError("near_duplicate_threshold must be in (0, 1]")
        if not 0.0 < ood_quantile < 1.0:
            raise ValueError("ood_quantile must be strictly between 0 and 1")
        if clip_value is not None and clip_value <= 0:
            raise ValueError("clip_value must be positive or None")

        self.n_clusters = int(n_clusters)
        self.method = method
        self.feature_groups = feature_groups
        self.random_state = int(random_state)
        self.maximum_missing_fraction = float(maximum_missing_fraction)
        self.near_duplicate_threshold = float(near_duplicate_threshold)
        self.constant_tolerance = float(constant_tolerance)
        self.ood_quantile = float(ood_quantile)
        self.clip_value = None if clip_value is None else float(clip_value)
        self.kmeans_n_init = int(kmeans_n_init)
        self.gmm_n_init = int(gmm_n_init)
        self.gmm_reg_covar = float(gmm_reg_covar)
        self._fitted = False

    def fit(self, x: pd.DataFrame) -> "StateClusterer":
        """Fit preprocessing, clusters and the OOD threshold on ``x`` only."""

        x = _as_frame(x)
        if len(x) < self.n_clusters:
            raise ValueError(
                f"training frame has {len(x)} rows, fewer than n_clusters={self.n_clusters}"
            )

        groups = _normalise_groups(self.feature_groups, x.columns)
        declared = [column for columns in groups.values() for column in columns]
        missing = [column for column in declared if column not in x.columns]
        if missing:
            raise ValueError(f"training frame is missing declared features: {missing}")
        numeric = _numeric_frame(x, declared)

        retained, dropped = self._screen_features(numeric)
        if not retained:
            raise ValueError("no usable clustering features remain after screening")

        self.feature_groups_ = {name: tuple(columns) for name, columns in groups.items()}
        self.feature_names_in_ = tuple(declared)
        self.retained_features_ = tuple(retained)
        self.dropped_features_ = dropped
        self.empty_groups_ = tuple(
            name for name, columns in groups.items() if not any(c in retained for c in columns)
        )
        self.feature_to_group_ = {
            column: name
            for name, columns in groups.items()
            for column in columns
            if column in retained
        }
        counts = {
            name: sum(column in retained for column in columns)
            for name, columns in groups.items()
        }
        self.group_weights_ = {
            name: 1.0 / np.sqrt(count)
            for name, count in counts.items()
            if count
        }
        self.feature_weights_ = np.asarray(
            [self.group_weights_[self.feature_to_group_[column]] for column in retained],
            dtype="float64",
        )

        selected = numeric.loc[:, retained]
        self.imputer_ = SimpleImputer(strategy="median", keep_empty_features=True)
        imputed = self.imputer_.fit_transform(selected)
        self.scaler_ = RobustScaler(quantile_range=(25.0, 75.0))
        self.scaler_.fit(imputed)
        z = self._finish_preprocessing(self.scaler_.transform(imputed))

        self.model_ = None
        if self.n_clusters == 1:
            raw_centres = np.mean(z, axis=0, keepdims=True)
        elif self.method == "kmeans":
            self.model_ = KMeans(
                n_clusters=self.n_clusters,
                n_init=self.kmeans_n_init,
                random_state=self.random_state,
                algorithm="lloyd",
            ).fit(z)
            raw_centres = self.model_.cluster_centers_
        else:
            self.model_ = GaussianMixture(
                n_components=self.n_clusters,
                covariance_type="diag",
                n_init=self.gmm_n_init,
                reg_covar=self.gmm_reg_covar,
                random_state=self.random_state,
            ).fit(z)
            raw_centres = self.model_.means_

        # Canonical labels make artifacts deterministic and human-comparable;
        # ARI itself remains label permutation invariant.
        self.canonical_order_ = np.asarray(
            sorted(range(self.n_clusters), key=lambda i: tuple(raw_centres[i].tolist())),
            dtype="int64",
        )
        self.raw_to_canonical_ = np.empty(self.n_clusters, dtype="int64")
        self.raw_to_canonical_[self.canonical_order_] = np.arange(self.n_clusters)
        self.cluster_centers_ = np.asarray(raw_centres[self.canonical_order_], dtype="float64")

        labels, probabilities, distances = self._assign_prepared(z)
        self.ood_threshold_ = float(
            np.quantile(distances, self.ood_quantile, method="higher")
        )
        self.training_rows_ = int(len(x))
        self.active_clusters_ = tuple(int(v) for v in np.unique(labels))
        self.n_features_in_ = len(declared)
        self.n_features_retained_ = len(retained)
        self._fitted = True
        return self

    def transform(self, x: pd.DataFrame) -> StateAssignments:
        """Assign rows without changing any fitted preprocessing or threshold."""

        self._check_fitted()
        x = _as_frame(x)
        missing = [column for column in self.retained_features_ if column not in x.columns]
        if missing:
            raise ValueError(f"frame is missing fitted clustering features: {missing}")
        selected = _numeric_frame(x, self.retained_features_)
        imputed = self.imputer_.transform(selected)
        z = self._finish_preprocessing(self.scaler_.transform(imputed))
        labels, probabilities, distances = self._assign_prepared(z)
        columns = [f"cluster_{i}" for i in range(self.n_clusters)]
        index = x.index.copy()
        return StateAssignments(
            labels=pd.Series(labels, index=index, name="cluster", dtype="int32"),
            probabilities=pd.DataFrame(probabilities, index=index, columns=columns),
            distance=pd.Series(distances, index=index, name="cluster_distance"),
            out_of_distribution=pd.Series(
                distances > self.ood_threshold_, index=index, name="cluster_ood", dtype=bool
            ),
        )

    def augment(
        self,
        x: pd.DataFrame,
        *,
        prefix: str = "state_cluster",
        include_label: bool = False,
        include_distance: bool = True,
        include_ood: bool = True,
    ) -> pd.DataFrame:
        """Return ``x`` with cluster probabilities and optional diagnostics."""

        x = _as_frame(x)
        assignment = self.transform(x)
        values = assignment.frame(prefix)
        keep = [column for column in values if "__probability_" in column]
        if include_label:
            keep.insert(0, f"{prefix}__label")
        if include_distance:
            keep.append(f"{prefix}__distance")
        if include_ood:
            keep.append(f"{prefix}__ood")
        collisions = [column for column in keep if column in x.columns]
        if collisions:
            raise ValueError(f"cluster feature names collide with input columns: {collisions}")
        return pd.concat([x.copy(), values.loc[:, keep]], axis=1)

    def support_summary(self, x: pd.DataFrame) -> pd.DataFrame:
        """Summarise cluster row/day support for a transformed population."""

        return support_summary(self.transform(x), n_clusters=self.n_clusters)

    def _screen_features(self, x: pd.DataFrame) -> tuple[list[str], dict[str, dict[str, str]]]:
        retained: list[str] = []
        dropped: dict[str, dict[str, str]] = {}
        for column in x.columns:
            values = x[column].to_numpy(dtype="float64")
            finite = values[np.isfinite(values)]
            missing_fraction = 1.0 - finite.size / len(values)
            if missing_fraction > self.maximum_missing_fraction:
                dropped[column] = {"reason": "too_missing", "representative": ""}
                continue
            if finite.size == 0:
                dropped[column] = {"reason": "all_missing", "representative": ""}
                continue
            span = float(np.max(finite) - np.min(finite))
            scale = max(1.0, float(np.max(np.abs(finite))))
            if span <= self.constant_tolerance * scale:
                dropped[column] = {"reason": "constant", "representative": ""}
                continue
            retained.append(column)

        if len(retained) < 2 or len(x) < 2:
            return retained, dropped

        provisional = SimpleImputer(strategy="median", keep_empty_features=True).fit_transform(
            x.loc[:, retained]
        )
        correlation = np.corrcoef(provisional, rowvar=False)
        keep_positions: list[int] = []
        for position, column in enumerate(retained):
            representative = next(
                (
                    retained[kept]
                    for kept in keep_positions
                    if np.isfinite(correlation[kept, position])
                    and abs(correlation[kept, position]) >= self.near_duplicate_threshold
                ),
                None,
            )
            if representative is None:
                keep_positions.append(position)
            else:
                dropped[column] = {
                    "reason": "near_duplicate",
                    "representative": representative,
                }
        return [retained[position] for position in keep_positions], dropped

    def _finish_preprocessing(self, values: np.ndarray) -> np.ndarray:
        z = np.asarray(values, dtype="float64")
        if self.clip_value is not None:
            z = np.clip(z, -self.clip_value, self.clip_value)
        return z * self.feature_weights_

    def _assign_prepared(self, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        if self.n_clusters == 1:
            probabilities = np.ones((len(z), 1), dtype="float64")
            labels = np.zeros(len(z), dtype="int32")
            distances = np.linalg.norm(z - self.cluster_centers_[0], axis=1)
            return labels, probabilities, distances

        if self.method == "kmeans":
            raw_distances = self.model_.transform(z)
            all_distances = raw_distances[:, self.canonical_order_]
            labels = np.argmin(all_distances, axis=1).astype("int32")
            probabilities = np.eye(self.n_clusters, dtype="float64")[labels]
            distances = all_distances[np.arange(len(z)), labels]
            return labels, probabilities, distances

        probabilities = self.model_.predict_proba(z)[:, self.canonical_order_]
        labels = np.argmax(probabilities, axis=1).astype("int32")
        covariance = self.model_.covariances_[self.canonical_order_]
        residual = z - self.cluster_centers_[labels]
        distances = np.sqrt(
            np.sum((residual * residual) / covariance[labels], axis=1)
        )
        return labels, probabilities, distances

    def _check_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("StateClusterer must be fitted on training data first")


def assess_stability(
    x: pd.DataFrame,
    *,
    n_clusters: int,
    method: str,
    feature_groups: Mapping[str, Sequence[str]] | None = None,
    seeds: Sequence[int] = (741, 742, 743),
    block_days: int = 1,
    block_sample_fraction: float = 1.0,
    **clusterer_options: object,
) -> StabilityReport:
    """Assess seed and day-block-resample stability on training data only.

    Every fitted candidate assigns the same original training population before
    pairwise ARI is calculated. The resampling leg requires a sorted
    ``DatetimeIndex`` and samples contiguous, non-overlapping day blocks with
    replacement.
    """

    x = _as_frame(x)
    seeds = tuple(int(seed) for seed in seeds)
    if len(set(seeds)) != len(seeds) or not seeds:
        raise ValueError("seeds must be a non-empty sequence of unique integers")
    if int(block_days) != block_days or block_days < 1:
        raise ValueError("block_days must be a positive integer")
    if not 0.0 < block_sample_fraction <= 1.0:
        raise ValueError("block_sample_fraction must be in (0, 1]")
    if not isinstance(x.index, pd.DatetimeIndex):
        raise ValueError("day-block stability requires a DatetimeIndex")
    if not x.index.is_monotonic_increasing:
        raise ValueError("day-block stability requires a sorted DatetimeIndex")

    common = dict(
        n_clusters=n_clusters,
        method=method,
        feature_groups=feature_groups,
        **clusterer_options,
    )
    seed_labels: dict[int, np.ndarray] = {}
    block_labels: dict[int, np.ndarray] = {}
    for seed in seeds:
        seed_model = StateClusterer(random_state=seed, **common).fit(x)
        seed_labels[seed] = seed_model.transform(x).labels.to_numpy()

        sampled = _day_block_resample(
            x,
            random_state=seed,
            block_days=int(block_days),
            sample_fraction=block_sample_fraction,
        )
        block_model = StateClusterer(random_state=seed, **common).fit(sampled)
        block_labels[seed] = block_model.transform(x).labels.to_numpy()

    seed_scores = _pairwise_ari(seed_labels)
    block_scores = _pairwise_ari(block_labels)
    return StabilityReport(
        seed_scores=seed_scores,
        block_scores=block_scores,
        seed_mean_ari=_mean_score(seed_scores),
        block_mean_ari=_mean_score(block_scores),
        seeds=seeds,
        block_days=int(block_days),
    )


def support_summary(
    assignments: StateAssignments,
    *,
    n_clusters: int | None = None,
) -> pd.DataFrame:
    """Return support, time coverage, distance and OOD rates by cluster."""

    labels = assignments.labels
    if n_clusters is None:
        n_clusters = assignments.probabilities.shape[1]
    if len(labels) != len(assignments.distance) or len(labels) != len(assignments.out_of_distribution):
        raise ValueError("assignment components must have the same length")
    if not labels.index.equals(assignments.distance.index) or not labels.index.equals(
        assignments.out_of_distribution.index
    ):
        raise ValueError("assignment components must have aligned indices")

    datetimes = labels.index if isinstance(labels.index, pd.DatetimeIndex) else None
    rows: list[dict[str, object]] = []
    for cluster in range(int(n_clusters)):
        mask = labels.to_numpy() == cluster
        count = int(mask.sum())
        distances = assignments.distance.to_numpy(dtype="float64")[mask]
        ood = assignments.out_of_distribution.to_numpy(dtype=bool)[mask]
        if datetimes is not None and count:
            selected_times = datetimes[mask]
            days = int(pd.DatetimeIndex(selected_times).normalize().nunique())
            first_seen: object = selected_times.min()
            last_seen: object = selected_times.max()
        else:
            days = 0
            first_seen = pd.NaT
            last_seen = pd.NaT
        rows.append(
            {
                "cluster": cluster,
                "rows": count,
                "row_fraction": count / len(labels) if len(labels) else np.nan,
                "unique_days": days,
                "first_seen": first_seen,
                "last_seen": last_seen,
                "ood_rows": int(ood.sum()),
                "ood_fraction": float(ood.mean()) if count else np.nan,
                "median_distance": float(np.median(distances)) if count else np.nan,
                "p95_distance": (
                    float(np.quantile(distances, 0.95, method="higher"))
                    if count
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows).set_index("cluster")


def _normalise_groups(
    feature_groups: Mapping[str, Sequence[str]] | None,
    available_columns: pd.Index,
) -> dict[str, tuple[str, ...]]:
    if feature_groups is None:
        if not len(available_columns):
            raise ValueError("clustering frame has no columns")
        return {"all": tuple(str(column) for column in available_columns)}
    if not feature_groups:
        raise ValueError("feature_groups must not be empty")
    groups: dict[str, tuple[str, ...]] = {}
    seen: set[str] = set()
    for raw_name, raw_columns in feature_groups.items():
        name = str(raw_name)
        if not name:
            raise ValueError("feature group names must be non-empty")
        if isinstance(raw_columns, (str, bytes)):
            raise TypeError(f"feature group {name!r} must contain a sequence of column names")
        columns = tuple(str(column) for column in raw_columns)
        if not columns:
            raise ValueError(f"feature group {name!r} is empty")
        if len(set(columns)) != len(columns):
            raise ValueError(f"feature group {name!r} contains duplicate features")
        duplicates = [column for column in columns if column in seen]
        if duplicates:
            raise ValueError(f"features occur in more than one group: {duplicates}")
        seen.update(columns)
        groups[name] = columns
    return groups


def _as_frame(x: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(x, pd.DataFrame):
        raise TypeError("clustering input must be a pandas DataFrame")
    if x.columns.has_duplicates:
        raise ValueError("clustering input has duplicate column names")
    return x


def _numeric_frame(x: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    selected = x.loc[:, list(columns)]
    try:
        numeric = selected.apply(pd.to_numeric, errors="raise").astype("float64")
        return numeric.replace([np.inf, -np.inf], np.nan)
    except (TypeError, ValueError) as exc:
        raise ValueError("all clustering features must be numeric") from exc


def _day_block_resample(
    x: pd.DataFrame,
    *,
    random_state: int,
    block_days: int,
    sample_fraction: float,
) -> pd.DataFrame:
    dates = x.index.normalize()
    unique_days = pd.DatetimeIndex(dates.unique())
    blocks = [
        unique_days[start : start + block_days]
        for start in range(0, len(unique_days), block_days)
    ]
    if not blocks:
        raise ValueError("cannot day-block resample an empty frame")
    draws = max(1, ceil(len(blocks) * sample_fraction))
    rng = np.random.default_rng(random_state)
    sampled: list[pd.DataFrame] = []
    for block_position in rng.integers(0, len(blocks), size=draws):
        block = blocks[int(block_position)]
        sampled.append(x.loc[dates.isin(block)])
    return pd.concat(sampled, ignore_index=True)


def _pairwise_ari(labels: Mapping[int, np.ndarray]) -> pd.DataFrame:
    rows = [
        {
            "seed_a": seed_a,
            "seed_b": seed_b,
            "adjusted_rand_index": float(adjusted_rand_score(labels[seed_a], labels[seed_b])),
        }
        for seed_a, seed_b in combinations(labels, 2)
    ]
    return pd.DataFrame(rows, columns=["seed_a", "seed_b", "adjusted_rand_index"])


def _mean_score(scores: pd.DataFrame) -> float:
    if scores.empty:
        return float("nan")
    return float(scores["adjusted_rand_index"].mean())
