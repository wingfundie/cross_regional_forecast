import unittest

import numpy as np
import pandas as pd

from nemic.experiments.clustering.generator import (
    build_sensitivity_matrix,
    fit_generator_representations,
)


def _small_matrix():
    rows = pd.DataFrame([
        {"version_key": "v1", "GENCONID": "c1", "DUID": "A",
         "FACTOR": 2.0, "ic_factor": 1.0, "sensitivity": -2.0},
        {"version_key": "v1", "GENCONID": "c1", "DUID": "B",
         "FACTOR": -3.0, "ic_factor": 1.0, "sensitivity": 3.0},
        {"version_key": "v2", "GENCONID": "c2", "DUID": "A",
         "FACTOR": 1.0, "ic_factor": -2.0, "sensitivity": 0.5},
    ])
    return build_sensitivity_matrix(rows, {"v1": 10.0, "v2": 5.0, "v3": 2.0})


class SensitivityMatrixTests(unittest.TestCase):
    def test_signs_structural_zeros_and_unavailable_versions_are_distinct(self):
        matrix = _small_matrix()
        np.testing.assert_allclose(matrix.values.toarray(), [
            [-2.0, 3.0],
            [0.5, 0.0],
            [0.0, 0.0],
        ])
        np.testing.assert_array_equal(matrix.recorded.toarray(), [
            [1, 1],
            [1, 0],
            [0, 0],
        ])
        np.testing.assert_array_equal(matrix.available_versions, [True, True, False])
        np.testing.assert_array_equal(matrix.directions, ["upper", "lower", "unavailable"])
        self.assertEqual(matrix.audit["absent_verified_coefficient_cells"], 1)
        self.assertEqual(matrix.audit["unavailable_version_count"], 1)

    def test_invalid_coefficients_are_rejected_and_audited(self):
        valid = {"version_key": "v1", "GENCONID": "c1", "DUID": "A",
                 "FACTOR": 2.0, "ic_factor": 1.0, "sensitivity": -2.0}
        rows = pd.DataFrame([
            valid, valid,
            {"version_key": "vweak", "GENCONID": "cweak", "DUID": "B",
             "FACTOR": 1.0, "ic_factor": 0.0, "sensitivity": -1.0},
            {"version_key": "vextreme", "GENCONID": "cextreme", "DUID": "C",
             "FACTOR": -200.0, "ic_factor": 1.0, "sensitivity": 200.0},
            {"version_key": "vmismatch", "GENCONID": "cmismatch", "DUID": "D",
             "FACTOR": 1.0, "ic_factor": 1.0, "sensitivity": 1.0},
            {"version_key": "vfactor", "GENCONID": "cfactor", "DUID": "E",
             "FACTOR": np.nan, "ic_factor": 1.0, "sensitivity": 0.0},
            {"version_key": "vsensitivity", "GENCONID": "csensitivity", "DUID": "F",
             "FACTOR": 1.0, "ic_factor": 1.0, "sensitivity": np.inf},
            {"version_key": "future", "GENCONID": "cf", "DUID": "Z",
             "FACTOR": 1.0, "ic_factor": 1.0, "sensitivity": -1.0},
        ])
        exposures = {version: 1.0 for version in (
            "v1", "v2", "vweak", "vextreme", "vmismatch", "vfactor", "vsensitivity",
        )}
        matrix = build_sensitivity_matrix(rows, exposures)
        self.assertEqual(matrix.duids, ("A",))
        self.assertEqual(matrix.audit["exact_duplicate_rows_removed"], 1)
        self.assertEqual(matrix.audit["rejected_weak_ic_factor"], 1)
        self.assertEqual(matrix.audit["rejected_extreme_sensitivity"], 1)
        self.assertEqual(matrix.audit["rejected_sensitivity_mismatch"], 1)
        self.assertEqual(matrix.audit["rejected_nonfinite_factor"], 1)
        self.assertEqual(matrix.audit["rejected_nonfinite_sensitivity"], 1)
        self.assertEqual(matrix.audit["rows_outside_training_versions"], 1)
        self.assertEqual(matrix.audit["versions_with_rejected_coefficient_records"], [
            "vextreme", "vfactor", "vmismatch", "vsensitivity",
        ])
        self.assertFalse(matrix.available_versions[matrix.version_index["v2"]])
        self.assertTrue(matrix.available_versions[matrix.version_index["v1"]])

    def test_explicit_verification_cannot_rescue_missing_or_weak_metadata(self):
        rows = pd.DataFrame([
            {"version_key": "v1", "GENCONID": "c1", "DUID": "A",
             "FACTOR": 1.0, "ic_factor": 1.0, "sensitivity": -1.0},
            {"version_key": "v2", "GENCONID": "c2", "DUID": "A",
             "FACTOR": 1.0, "ic_factor": 0.0, "sensitivity": -1.0},
        ])
        matrix = build_sensitivity_matrix(
            rows, {"v1": 1.0, "v2": 1.0, "v3": 1.0},
            verified_versions=["v1", "v2", "v3"],
        )
        np.testing.assert_array_equal(matrix.available_versions, [True, False, False])


class RepresentationTests(unittest.TestCase):
    def test_manual_kmeans_and_svd_candidates_are_deterministic(self):
        rng = np.random.default_rng(17)
        rows = []
        duids = [f"D{i:02d}" for i in range(10)]
        versions = [f"v{i:02d}" for i in range(8)]
        coefficients = rng.normal(size=(len(versions), len(duids)))
        for i, version in enumerate(versions):
            ic_factor = 1.0 if i % 2 == 0 else -1.0
            for j, duid in enumerate(duids):
                sensitivity = float(coefficients[i, j])
                rows.append({
                    "version_key": version, "GENCONID": f"c{i:02d}", "DUID": duid,
                    "FACTOR": -sensitivity * ic_factor, "ic_factor": ic_factor,
                    "sensitivity": sensitivity,
                })
        matrix = build_sensitivity_matrix(
            pd.DataFrame(rows), {version: i + 1 for i, version in enumerate(versions)},
        )
        manual = {duid: "first" if i < 3 else "remaining" for i, duid in enumerate(duids)}
        one = fit_generator_representations(matrix, manual_groups=manual)
        two = fit_generator_representations(matrix, manual_groups=manual)
        self.assertEqual(
            set(one.models), {"manual", "kmeans_k4", "kmeans_k8", "svd_n4", "svd_n8"},
        )
        self.assertEqual(one.skipped, {})
        np.testing.assert_array_equal(
            one.models["kmeans_k8"].unit_group,
            two.models["kmeans_k8"].unit_group,
        )
        np.testing.assert_allclose(
            one.models["svd_n8"].components,
            two.models["svd_n8"].components,
        )

    def test_movements_emit_directional_pressure_and_conservative_fallback_flags(self):
        matrix = _small_matrix()
        model = fit_generator_representations(
            matrix, manual_groups={"A": "alpha", "B": "beta"},
            cluster_sizes=(), svd_components=(),
        ).models["manual"]
        movements = pd.DataFrame([
            {"observation_id": "complete_upper", "version_key": "v1", "direction": "upper",
             "DUID": "A", "delta_mw": 10.0},
            {"observation_id": "complete_upper", "version_key": "v1", "direction": "upper",
             "DUID": "B", "delta_mw": -2.0},
            {"observation_id": "structural_zero", "version_key": "v2", "direction": "lower",
             "DUID": "A", "delta_mw": 4.0},
            {"observation_id": "structural_zero", "version_key": "v2", "direction": "lower",
             "DUID": "B", "delta_mw": 5.0},
            {"observation_id": "unavailable", "version_key": "v3", "direction": "upper",
             "DUID": "A", "delta_mw": 1.0},
            {"observation_id": "unknown", "version_key": "new", "direction": "upper",
             "DUID": "A", "delta_mw": 1.0},
            {"observation_id": "partial", "version_key": "v1", "direction": "upper",
             "DUID": "A", "delta_mw": 1.0},
            {"observation_id": "partial", "version_key": "v1", "direction": "upper",
             "DUID": "NEW", "delta_mw": 1.0},
        ])
        transformed = model.transform_movements(movements).set_index("observation_id")
        self.assertEqual(transformed.at["complete_upper", "manual__alpha__upper_tightening"], 20.0)
        self.assertEqual(transformed.at["complete_upper", "manual__beta__upper_tightening"], 6.0)
        self.assertEqual(transformed.at["complete_upper", "manual__alpha__lower_tightening"], 0.0)
        self.assertEqual(transformed.at["structural_zero", "manual__alpha__lower_tightening"], 2.0)
        self.assertEqual(transformed.at["structural_zero", "manual__beta__lower_tightening"], 0.0)
        self.assertEqual(transformed.at["structural_zero", "implicit_zero_count"], 1)
        self.assertTrue(transformed.at["structural_zero", "pressure_supported"])
        self.assertTrue(np.isnan(transformed.at["unavailable", "manual__alpha__upper_tightening"]))
        self.assertFalse(transformed.at["unavailable", "version_available"])
        self.assertTrue(transformed.at["unknown", "unknown_version"])
        self.assertTrue(np.isnan(transformed.at["partial", "manual__alpha__upper_tightening"]))
        self.assertTrue(transformed.at["partial", "unknown_duid"])
        self.assertEqual(transformed.at["partial", "missing_required_duid_count"], 1)

    def test_existing_signed_pressure_keeps_tightening_and_relief_separate(self):
        matrix = _small_matrix()
        model = fit_generator_representations(
            matrix, manual_groups={"A": "alpha", "B": "beta"},
            cluster_sizes=(), svd_components=(),
        ).models["manual"]
        pressure = pd.DataFrame([
            {"observation_id": 1, "version_key": "v1", "direction": "upper",
             "DUID": "A", "tightening_mw": 5.0},
            {"observation_id": 1, "version_key": "v1", "direction": "upper",
             "DUID": "B", "tightening_mw": -2.0},
        ])
        result = model.aggregate_signed_pressure(pressure).iloc[0]
        self.assertEqual(result["manual__alpha__upper_tightening"], 5.0)
        self.assertEqual(result["manual__alpha__upper_relief"], 0.0)
        self.assertEqual(result["manual__beta__upper_tightening"], 0.0)
        self.assertEqual(result["manual__beta__upper_relief"], 2.0)
        self.assertEqual(result["manual__beta__lower_relief"], 0.0)


if __name__ == "__main__":
    unittest.main()
