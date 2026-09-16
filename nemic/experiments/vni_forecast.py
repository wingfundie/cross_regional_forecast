"""Load and apply the frozen VNI research bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .diurnal import periods
from .diurnal_export import predict_bundle


DEFAULT_FINAL_DIR = Path("data/forecast_experiments/vni_diurnal_nos_v2/final")
TARGETS = ("export_tight", "import_tight", "export", "import")
BANDS = ((1, 12), (13, 48), (49, 144), (145, 336))


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _band_for_lead(lead: float) -> int:
    if not np.isfinite(lead) or lead != int(lead):
        raise ValueError(f"Lead must be a finite integer half-hour count; received {lead!r}")
    for band, (lower, upper) in enumerate(BANDS):
        if lower <= int(lead) <= upper:
            return band
    raise ValueError(f"Lead {int(lead)} is outside the supported 1–336 half-hour range")


class VniBundleRepository:
    """Catalogue-backed access to the frozen VNI bundle set."""

    def __init__(self, final_dir: str | Path = DEFAULT_FINAL_DIR, *, verify_hashes: bool = True):
        self.final_dir = Path(final_dir)
        catalogue_path = self.final_dir / "catalogue.json"
        if not catalogue_path.exists():
            raise FileNotFoundError(f"Saved-model catalogue not found: {catalogue_path}")
        rows = json.loads(catalogue_path.read_text(encoding="utf-8"))
        self.catalogue = {(row["target"], int(row["band"])): row for row in rows}
        expected = {(target, band) for target in TARGETS for band in range(len(BANDS))}
        missing = expected - set(self.catalogue)
        if missing:
            raise ValueError(f"Saved-model catalogue is incomplete: {sorted(missing)}")
        self.verify_hashes = verify_hashes
        self._cache: dict[tuple[str, int], dict] = {}

    def _path(self, row: dict) -> Path:
        # Catalogue paths are relative to the run root and may use Windows separators.
        relative = Path(str(row["path"]).replace("\\", "/"))
        run_root = self.final_dir.parent
        return run_root / relative

    def load(self, target: str, band: int) -> dict:
        if target not in TARGETS:
            raise ValueError(f"Unknown target {target!r}; choose one of {TARGETS}")
        key = (target, int(band))
        if key in self._cache:
            return self._cache[key]
        row = self.catalogue[key]
        path = self._path(row)
        if not path.exists():
            raise FileNotFoundError(f"Saved model not found: {path}")
        if self.verify_hashes:
            actual = _digest(path)
            if actual != row["sha256"]:
                raise ValueError(f"Saved-model hash mismatch for {path}: {actual} != {row['sha256']}")
        bundle = joblib.load(path)
        if bundle.get("target") != target or int(bundle.get("band", -1)) != int(band):
            raise ValueError(f"Bundle identity mismatch in {path}")
        self._cache[key] = bundle
        return bundle

    def forecast(self, features: pd.DataFrame, target: str, *, allow_research: bool = False) -> pd.DataFrame:
        """Route feature rows by lead and return point and calibrated interval forecasts."""
        features = features.reset_index(drop=True)
        if target not in TARGETS:
            raise ValueError(f"Unknown target {target!r}; choose one of {TARGETS}")
        if "lead" not in features:
            raise ValueError("Input must contain lead in half-hour intervals")
        if features.empty:
            raise ValueError("Input feature table is empty")

        routed = features.copy()
        routed["band"] = [_band_for_lead(value) for value in pd.to_numeric(routed["lead"], errors="coerce")]
        output = pd.DataFrame(index=features.index)
        for name in ("origin", "delivery", "lead"):
            if name in features:
                output[name] = features[name]
        output["target"] = target
        output["band"] = routed["band"]
        output["model"] = ""
        output["forecast_mw"] = np.nan
        for column in ("p02_5_mw", "p10_mw", "p50_mw", "p90_mw", "p97_5_mw"):
            output[column] = np.nan
        output["interval_basis"] = ""

        for band, positions in routed.groupby("band").groups.items():
            bundle = self.load(target, int(band))
            if not bundle.get("operationally_eligible", False) and not allow_research:
                raise ValueError(
                    "This saved bundle is marked operationally_eligible=false. "
                    "Pass allow_research=True (or --allow-research) for research/development forecasting."
                )
            missing = [column for column in bundle["input_columns"] if column not in features]
            if missing:
                raise ValueError(f"Input is missing {len(missing)} required feature columns: {missing}")
            local = features.loc[positions, bundle["input_columns"]].astype("float64")
            point = predict_bundle(bundle, local)
            quantiles = np.asarray(bundle["quantiles"], dtype=float)
            pooled = np.asarray(bundle["pooled_adjustments"], dtype=float)
            if "delivery" in features:
                delivery = pd.DatetimeIndex(pd.to_datetime(features.loc[positions, "delivery"], errors="raise"))
                group = periods(delivery)
                adjustments = np.stack([np.asarray(bundle["period_adjustments"][int(value)]) for value in group])
                basis = "delivery_period"
            else:
                adjustments = np.tile(pooled, (len(local), 1))
                basis = "pooled"
            calibrated = point[:, None] + adjustments
            expected_quantiles = np.array([.025, .1, .5, .9, .975])
            if not np.allclose(quantiles, expected_quantiles):
                raise ValueError(f"Unsupported bundle quantiles: {quantiles.tolist()}")
            output.loc[positions, "model"] = bundle["winner"]
            output.loc[positions, "forecast_mw"] = point
            output.loc[positions, ["p02_5_mw", "p10_mw", "p50_mw", "p90_mw", "p97_5_mw"]] = calibrated
            output.loc[positions, "interval_basis"] = basis
        return output.reset_index(drop=True)


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".parquet", ".pq"):
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    raise ValueError("Feature input must be .parquet, .pq or .csv")


def _write_table(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix in (".parquet", ".pq"):
        frame.to_parquet(path, index=False)
    elif suffix == ".csv":
        frame.to_csv(path, index=False)
    else:
        raise ValueError("Forecast output must be .parquet, .pq or .csv")


def forecast_file(
    features_path: str | Path,
    target: str,
    output_path: str | Path,
    *,
    final_dir: str | Path = DEFAULT_FINAL_DIR,
    allow_research: bool = False,
) -> dict:
    features_path, output_path = Path(features_path), Path(output_path)
    features = _read_table(features_path)
    repository = VniBundleRepository(final_dir)
    forecast = repository.forecast(features, target, allow_research=allow_research)
    _write_table(forecast, output_path)
    return {
        "features": str(features_path),
        "output": str(output_path),
        "target": target,
        "rows": len(forecast),
        "bands": sorted(int(value) for value in forecast.band.unique()),
        "models": sorted(str(value) for value in forecast.model.unique()),
        "operationally_eligible": False,
    }
