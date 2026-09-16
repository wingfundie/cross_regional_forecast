import hashlib
import json

import joblib
import numpy as np
import pandas as pd
import pytest

from nemic.experiments.vni_forecast import VniBundleRepository, _band_for_lead


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository(tmp_path):
    run = tmp_path / "run"
    final = run / "final"
    catalogue = []
    for band in range(4):
        for target in ("export_tight", "import_tight", "export", "import"):
            folder = final / f"band{band}" / target
            folder.mkdir(parents=True)
            path = folder / "model.joblib"
            bundle = {
                "winner": "persistence",
                "models": {},
                "input_columns": ["lead", "own_anchor"],
                "target": target,
                "band": band,
                "quantiles": [.025, .1, .5, .9, .975],
                "pooled_adjustments": np.array([-20, -10, 0, 10, 20]),
                "period_adjustments": {i: np.array([-i, -i / 2, 0, i / 2, i]) for i in range(5)},
                "operationally_eligible": False,
            }
            joblib.dump(bundle, path)
            catalogue.append({"target": target, "band": band, "path": str(path.relative_to(run)), "sha256": _digest(path)})
    (final / "catalogue.json").write_text(json.dumps(catalogue), encoding="utf-8")
    return VniBundleRepository(final)


def test_saved_bundle_forecast_routes_bands_and_intervals(tmp_path):
    repository = _repository(tmp_path)
    features = pd.DataFrame({"lead": [1, 24, 72, 336], "own_anchor": [100, 200, 300, 400]})
    result = repository.forecast(features, "export_tight", allow_research=True)
    assert result.band.tolist() == [0, 1, 2, 3]
    assert result.forecast_mw.tolist() == [100, 200, 300, 400]
    assert result.p10_mw.tolist() == [90, 190, 290, 390]
    assert result.interval_basis.eq("pooled").all()


def test_saved_bundle_requires_research_acknowledgement(tmp_path):
    repository = _repository(tmp_path)
    with pytest.raises(ValueError, match="operationally_eligible=false"):
        repository.forecast(pd.DataFrame({"lead": [1], "own_anchor": [100]}), "export")


@pytest.mark.parametrize("lead, band", [(1, 0), (12, 0), (13, 1), (48, 1), (49, 2), (144, 2), (145, 3), (336, 3)])
def test_band_boundaries(lead, band):
    assert _band_for_lead(lead) == band


@pytest.mark.parametrize("lead", [0, 337, 1.5, np.nan])
def test_invalid_lead_rejected(lead):
    with pytest.raises(ValueError):
        _band_for_lead(lead)
