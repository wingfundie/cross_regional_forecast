import json
import tempfile
import unittest
from pathlib import Path

from nemic.constraint_longitudinal import archive_url, load_study, months_between


class LongitudinalConstraintStudyTests(unittest.TestCase):
    def test_vni_configuration_is_exactly_two_years(self):
        config = load_study("configs/constraint_vni_2y.json")
        self.assertEqual(config["standing_start"], config["start"])
        self.assertEqual(len(months_between(config["start"], config["end"])), 24)
        self.assertEqual(months_between(config["start"], config["end"])[0].strftime("%Y-%m"), "2024-09")
        self.assertEqual(months_between(config["start"], config["end"])[-1].strftime("%Y-%m"), "2026-08")

    def test_qni_configuration_is_exactly_two_years_and_isolated(self):
        config = load_study("configs/constraint_qni_2y.json")
        self.assertEqual(config["interconnector"], "NSW1-QLD1")
        self.assertEqual(config["standing_start"], config["start"])
        self.assertEqual(len(months_between(config["start"], config["end"])), 24)
        self.assertEqual(config["output_dir"], "constraint_qni_2y")
        self.assertEqual(config["raw_cache_dir"], "constraint_qni_2y/raw")

    def test_broader_standing_acquisition_is_rejected(self):
        config = json.loads(Path("configs/constraint_vni_2y.json").read_text(encoding="utf-8"))
        config["standing_start"] = "2022-09-01 00:00:00"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "same two-year start"):
                load_study(path)

    def test_archive_url_requests_one_named_table_month(self):
        month = months_between("2024-09-01", "2024-09-30")[0]
        url = archive_url(month, "DISPATCHCONSTRAINT")
        self.assertIn("MMSDM_2024_09", url)
        self.assertIn("%23DISPATCHCONSTRAINT%23", url)
        self.assertNotIn("2022", url)


if __name__ == "__main__":
    unittest.main()
