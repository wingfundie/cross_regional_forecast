"""Matched pooled and cluster-aware forecast models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class TabularTransform:
    """Train-fitted numeric imputation and scaling with strict column order."""

    def __init__(self):
        self.columns: list[str] = []
        self.imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
        self.scaler = StandardScaler()

    def fit(self, frame: pd.DataFrame) -> "TabularTransform":
        self.columns = list(frame.columns)
        values = self.imputer.fit_transform(frame.astype(float))
        self.scaler.fit(values)
        return self

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        if list(frame.columns) != self.columns:
            raise ValueError("Model feature order changed")
        return self.scaler.transform(self.imputer.transform(frame.astype(float)))


@dataclass
class CorrectionModel:
    family: str
    settings: dict
    transform: TabularTransform
    estimator: object
    columns: list[str]

    def predict(self, frame: pd.DataFrame, anchor: Iterable[float]) -> np.ndarray:
        anchor = np.asarray(anchor, dtype=float)
        values = self.transform.transform(frame[self.columns])
        return anchor + np.asarray(self.estimator.predict(values), dtype=float)


def _fit_one(
    family: str,
    settings: dict,
    x: pd.DataFrame,
    residual: np.ndarray,
    *,
    seed: int,
) -> CorrectionModel:
    transform = TabularTransform().fit(x)
    z = transform.transform(x)
    if family == "ridge":
        estimator = Ridge(alpha=float(settings["alpha"]), random_state=seed)
    elif family == "boost":
        estimator = lgb.LGBMRegressor(
            objective="regression_l1",
            n_estimators=int(settings["trees"]),
            num_leaves=int(settings["leaves"]),
            learning_rate=0.04,
            min_child_samples=150,
            reg_lambda=10.0,
            n_jobs=2,
            verbosity=-1,
            random_state=seed,
            deterministic=True,
            force_col_wise=True,
        )
    else:
        raise ValueError(f"Unsupported model family: {family}")
    estimator.fit(z, residual)
    return CorrectionModel(family, dict(settings), transform, estimator, list(x.columns))


def select_correction_model(
    family: str,
    train_x: pd.DataFrame,
    train_y: np.ndarray,
    train_anchor: np.ndarray,
    select_x: pd.DataFrame,
    select_y: np.ndarray,
    select_anchor: np.ndarray,
    config: dict,
    *,
    seed: int,
) -> tuple[CorrectionModel, list[dict]]:
    """Select settings on the selection partition and return the refittable model."""
    if family == "ridge":
        candidates = [{"alpha": value} for value in config["models"]["ridge_alpha"]]
    elif family == "boost":
        candidates = [
            {"leaves": value, "trees": config["models"]["boost_trees"]}
            for value in config["models"]["boost_leaves"]
        ]
    else:
        raise ValueError(f"Unsupported model family: {family}")
    trials = []
    fitted = []
    residual = np.asarray(train_y) - np.asarray(train_anchor)
    for settings in candidates:
        model = _fit_one(family, settings, train_x, residual, seed=seed)
        prediction = model.predict(select_x, select_anchor)
        valid = np.isfinite(select_y) & np.isfinite(prediction)
        loss = float(np.abs(np.asarray(select_y)[valid] - prediction[valid]).mean()) if valid.any() else np.inf
        trials.append({"settings": settings, "selection_mae": loss})
        fitted.append(model)
    best = int(np.argmin([trial["selection_mae"] for trial in trials]))
    return fitted[best], trials


def append_cluster_probabilities(frame: pd.DataFrame, probabilities: np.ndarray) -> pd.DataFrame:
    values = frame.reset_index(drop=True).copy()
    probabilities = np.asarray(probabilities, dtype=float)
    if probabilities.ndim != 2 or len(probabilities) != len(values):
        raise ValueError("Cluster probabilities do not align with model rows")
    for index in range(probabilities.shape[1]):
        values[f"cluster_probability_{index}"] = probabilities[:, index]
    return values


def append_cluster_interactions(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
    interaction_columns: Iterable[str],
) -> pd.DataFrame:
    values = append_cluster_probabilities(frame, probabilities)
    source = frame.reset_index(drop=True)
    for column in interaction_columns:
        if column not in source:
            raise ValueError(f"Missing interaction parent: {column}")
        parent = pd.to_numeric(source[column], errors="coerce")
        for index in range(np.asarray(probabilities).shape[1]):
            values[f"cluster_{index}__x__{column}"] = parent * probabilities[:, index]
    return values


class LocalExpertModel:
    """Ridge experts with an explicit pooled fallback and shrinkage weight."""

    def __init__(self, alpha: float, shrinkage: float, minimum_rows: int = 200, seed: int = 741):
        self.alpha = float(alpha)
        self.shrinkage = float(shrinkage)
        self.minimum_rows = int(minimum_rows)
        self.seed = int(seed)
        self.pooled: CorrectionModel | None = None
        self.experts: dict[int, CorrectionModel] = {}

    def fit(
        self,
        frame: pd.DataFrame,
        actual: np.ndarray,
        anchor: np.ndarray,
        labels: np.ndarray,
    ) -> "LocalExpertModel":
        self.pooled = _fit_one("ridge", {"alpha": self.alpha}, frame, np.asarray(actual) - np.asarray(anchor), seed=self.seed)
        labels = np.asarray(labels, dtype=int)
        for label in np.unique(labels):
            mask = labels == label
            if mask.sum() < self.minimum_rows:
                continue
            self.experts[int(label)] = _fit_one(
                "ridge", {"alpha": self.alpha}, frame.loc[mask],
                np.asarray(actual)[mask] - np.asarray(anchor)[mask], seed=self.seed + int(label) + 1,
            )
        return self

    def predict(
        self,
        frame: pd.DataFrame,
        anchor: np.ndarray,
        labels: np.ndarray,
        ood: np.ndarray | None = None,
    ) -> np.ndarray:
        if self.pooled is None:
            raise ValueError("Local experts are not fitted")
        labels = np.asarray(labels, dtype=int)
        pooled = self.pooled.predict(frame, anchor)
        result = pooled.copy()
        fallback = np.zeros(len(frame), dtype=bool) if ood is None else np.asarray(ood, dtype=bool)
        for label, expert in self.experts.items():
            mask = (labels == label) & ~fallback
            if mask.any():
                local = expert.predict(frame.loc[mask], np.asarray(anchor)[mask])
                result[mask] = self.shrinkage * local + (1.0 - self.shrinkage) * pooled[mask]
        return result


@dataclass
class ResidualIntervals:
    levels: np.ndarray
    offsets: np.ndarray

    @classmethod
    def fit(cls, actual: np.ndarray, point: np.ndarray, levels: Iterable[float]) -> "ResidualIntervals":
        levels = np.asarray(list(levels), dtype=float)
        residual = np.asarray(actual, dtype=float) - np.asarray(point, dtype=float)
        residual = residual[np.isfinite(residual)]
        if not len(residual):
            raise ValueError("No finite calibration residuals")
        return cls(levels, np.quantile(residual, levels))

    def predict(self, point: np.ndarray) -> np.ndarray:
        return np.sort(np.asarray(point, dtype=float)[:, None] + self.offsets[None, :], axis=1)

