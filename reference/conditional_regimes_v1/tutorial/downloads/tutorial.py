"""An end-to-end conditional-limit example using the installed package only.

python tutorial.py --bundle regime_bundle --output my_outputs [--models]
No downloads, retraining, production routes or schedules are triggered.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import pandas as pd
from nemic_regimes import load_bundle


REGION_PAIRS = {
    "QNI": ("NSW1", "QLD1"), "Directlink": ("NSW1", "QLD1"),
    "VNI": ("VIC1", "NSW1"), "Heywood": ("VIC1", "SA1"),
    "Murraylink": ("VIC1", "SA1"), "Basslink": ("TAS1", "VIC1"),
}


def interval_keys(delivery):
    """Use a timezone-aware interval END, converted to fixed NEM time."""
    t = pd.Timestamp(delivery)
    if t.tzinfo is None:
        raise ValueError("Supply a timezone-aware interval ending timestamp")
    t = t.tz_convert("Australia/Brisbane")
    if t.minute not in (0, 30) or t.second or t.microsecond or t.nanosecond:
        raise ValueError("Delivery must end exactly on a half-hour boundary")
    return {"quarter": t.quarter, "half_hour": t.hour * 2 + t.minute // 30}


def directional_conditions(connector, direction, regional):
    """Map the SAME physical regional assumptions into either direction."""
    if direction not in ("forward", "reverse"):
        raise ValueError("direction must be forward or reverse")
    source, sink = REGION_PAIRS[connector]
    if direction == "reverse":
        source, sink = sink, source
    return {f"{side}_{field}": value
            for side, region in (("source", source), ("sink", sink))
            for field, value in regional.get(region, {}).items()}


def brief(result):
    keys = ("direction", "target", "method", "status", "p10_mw", "p50_mw", "p90_mw",
            "tight_p10_mw", "exact_days", "analogue_days", "outage_episodes", "relaxed_conditions")
    return {key: result.get(key) for key in keys}


def run(bundle_path, output, include_models=False):
    bundle = load_bundle(bundle_path)  # Hash verification is enabled by default.
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # This date supplies calendar keys only. These are general scenario queries,
    # not a claim that the final bundle was available on 15 January 2026.
    interval = interval_keys("2026-01-15T18:30:00+10:00")
    regional = {"NSW1": {"temperature": {"min": 25}},
                "QLD1": {"residual": {"min": 5000}}}
    queries, directional, comparisons = [], [], []
    for direction in ("forward", "reverse"):
        query = {"connector": "QNI", "direction": direction, **interval,
                 "era": "current", "target": "average", "method": "table",
                 "mode": "scenario", "scenario_name": "warm_nsw_high_qld_residual",
                 **directional_conditions("QNI", direction, regional)}
        queries.append(query)
        baseline = bundle.select({k: v for k, v in query.items()
                                  if not k.startswith(("source_", "sink_"))})
        selected = bundle.select(query)
        tight = bundle.select({**query, "target": "tight"})
        analogue = bundle.select({**query, "method": "analogue"})
        directional.append(brief(selected))
        for label, result in (("quarter_reference", baseline), ("conditional_table", selected),
                              ("tight_target", tight), ("weighted_analogue", analogue)):
            comparisons.append({"case": label, **brief(result)})
        bundle.export(selected, output / f"{direction}_interval_evidence.json")
        bundle.export(bundle.profile(1, {k: v for k, v in query.items()
                                        if k not in {"quarter", "half_hour"}}),
                      output / f"{direction}_profile.csv")
    # A list returns a list; a DataFrame returns a DataFrame.
    batch_inputs = pd.DataFrame(queries).astype(object)
    batch_inputs = batch_inputs.where(batch_inputs.notna(), None)
    batch = bundle.select(batch_inputs)
    assert len(batch) == 2
    assert all(batch.p50_mw.notna()), "The demonstration has lost its historical support"
    bundle.export(batch, output / "both_directions.csv")
    bundle.export(comparisons, output / "method_comparison.csv")
    bundle.export(bundle.select([{**q, "quarter": quarter} for quarter in range(1, 5)
                                for q in queries]), output / "four_quarter_intervals.json")
    # Each interval can have different assumptions. Keep separate input records.
    varying = [{**queries[0], "half_hour": 36, "source_temperature": {"min": 24}},
               {**queries[0], "half_hour": 37, "source_temperature": {"min": 25}}]
    bundle.export(bundle.select(pd.DataFrame(varying)), output / "varying_conditions.csv")
    if include_models:
        for method in ("additive", "boosting"):
            result = bundle.select({**queries[0], "source_temperature": 28, "sink_residual": 5500,
                                    "scenario_name": "point_assumptions_for_model", "method": method,
                                    "allow_extrapolation": True})
            comparisons.append({"case": "explicit_model", **brief(result)})
        bundle.export(comparisons, output / "method_comparison.csv")
    (output / "one_interval_conditions.json").write_text(json.dumps(queries[0], indent=2), encoding="utf-8")
    forward, reverse = directional
    illustrative_bounds = {"lower_signed_flow_mw": -reverse["p50_mw"],
                           "upper_signed_flow_mw": forward["p50_mw"],
                           "interpretation": "Independent directional medians; not a jointly secure or calibrated flow interval"}
    summary = {"bundle_id": bundle.metadata["bundle_id"], "training_cutoff": bundle.metadata["training_cutoff"],
               "regional_assumptions": regional, "queries": queries, "directional_results": directional,
               "illustrative_p50_bounds": illustrative_bounds,
               "models_requested": include_models, "files": sorted(p.name for p in output.iterdir() if p.is_file())}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"bundle_id": summary["bundle_id"], "directional_results": directional,
                      "output": str(output)}, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("my_outputs"))
    parser.add_argument("--models", action="store_true", help="Also exercise the optional fitted challengers")
    args = parser.parse_args()
    run(args.bundle, args.output, args.models)
