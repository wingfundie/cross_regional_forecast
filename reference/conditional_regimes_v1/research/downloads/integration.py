"""Run from any project after installing the wheel; no repository imports."""
import argparse
from pathlib import Path
import pandas as pd
from nemic_regimes import load_bundle

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("bundle", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
bundle = load_bundle(args.bundle)
scenario = {"connector": "VNI", "direction": "forward", "era": "pre_pec_market",
            "sink_residual": {"min": 7000}, "scenario_name": "high_nsw_residual"}
result = bundle.profile(1, scenario)
bundle.export(result, args.output / "quarter_one_profile.csv")
bundle.export(result, args.output / "quarter_one_evidence.json")
batch = pd.DataFrame([{**scenario, "quarter": q, "half_hour": 24} for q in range(1, 5)])
bundle.export(bundle.select(batch), args.output / "four_quarter_noon.csv")
print("Exported the 48-interval profile, evidence and four-quarter comparison.")
