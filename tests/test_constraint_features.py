import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from nemic.constraint_features import bound_from_solution, canonical_bound, canonicalise_inequality, envelope
from nemic.constraint_ingest import load_config, validate_expanded_total
from nemic.vni_influence_study import _episode_onset


class ConstraintFeatureMath(unittest.TestCase):
    def test_positive_rescaling_preserves_bound(self):
        self.assertAlmostEqual(canonical_bound(900, 1, 300), canonical_bound(1800, 2, 600))

    def test_greater_than_conversion_preserves_feasible_set(self):
        kind, rhs, factors = canonicalise_inequality(">=", 100, {"flow": -2, "unit": 0.5})
        self.assertEqual(kind, "<=")
        self.assertEqual(rhs, -100)
        self.assertEqual(factors, {"flow": 2.0, "unit": -0.5})

    def test_zero_coefficient_has_no_direct_bound(self):
        self.assertTrue(np.isnan(canonical_bound(100, 0, 10)))

    def test_competing_constraint_switch(self):
        before = envelope([{"direction": "upper", "bound": 500},
                           {"direction": "upper", "bound": 530}])
        after = envelope([{"direction": "upper", "bound": 600},
                          {"direction": "upper", "bound": 520}])
        self.assertEqual(after["conditional_upper"] - before["conditional_upper"], 20)

    def test_signed_lower_and_ties(self):
        result = envelope([{"direction": "lower", "bound": -400},
                           {"direction": "lower", "bound": -400}])
        self.assertEqual(result["conditional_lower"], -400)
        self.assertEqual(result["lower_switch_gap"], 0)

    def test_published_lhs_isolates_current_conditional_bound(self):
        # LHS = 1*flow + other terms = 700. RHS 900 leaves 200 MW room.
        self.assertEqual(bound_from_solution(500, 900, 700, 1), 700)
        # A negative IC factor converts the same slack into a lower bound.
        self.assertEqual(bound_from_solution(-100, 900, 700, -2), -200)

    def test_contiguous_event_is_counted_once(self):
        mask = pd.Series([False, True, True, False, True, False])
        self.assertEqual(_episode_onset(mask).tolist(), [False, True, False, False, True, False])


class DownloadPolicy(unittest.TestCase):
    def test_rejects_non_nemweb_or_wrong_table_url(self):
        config = {
            "limits": {"pilot_compressed_bytes": 100},
            "files": [{"table": "DISPATCHLOAD", "phase": "interval", "expected_bytes": 10,
                       "url": "https://example.com/PUBLIC_ARCHIVE%23GENCONDATA%23FILE01%23202602010000.zip"}],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)

    def test_rejects_manifest_over_total_cap(self):
        config = {
            "limits": {"pilot_compressed_bytes": 5},
            "files": [{"table": "GENCONDATA", "phase": "static", "expected_bytes": 10,
                       "url": "https://nemweb.com.au/x/PUBLIC_ARCHIVE%23GENCONDATA%23FILE01%23202602010000.zip"}],
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cap"):
                load_config(path)

    def test_rejects_expanded_batch_over_cap(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "large.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("data.csv", b"x" * 1000)
            with self.assertRaisesRegex(ValueError, "decompressed"):
                validate_expanded_total([path], 999)


if __name__ == "__main__":
    unittest.main()
