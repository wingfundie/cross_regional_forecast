"""Explicit operations; invoking help performs no downloads or training."""
import argparse
import json
from pathlib import Path
import pandas as pd

from .contracts import read_json, write_json
from .inputs import normalize, read_table, archive
from .registry import Registry


def main():
    parser = argparse.ArgumentParser(description="Portable interconnector forecast scaffold")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("demo", help="Offline synthetic end-to-end test")
    p.add_argument("--output", required=True)
    p = sub.add_parser("normalize")
    p.add_argument("--input", required=True); p.add_argument("--mapping", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("register")
    p.add_argument("--registry", required=True); p.add_argument("--package", required=True)
    p = sub.add_parser("list")
    p.add_argument("--registry", required=True)
    p = sub.add_parser("export")
    p.add_argument("--registry", required=True); p.add_argument("--model", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("activate-routes")
    p.add_argument("--registry", required=True); p.add_argument("--routes", required=True)
    p = sub.add_parser("features")
    p.add_argument("--input", required=True); p.add_argument("--requests", required=True)
    p.add_argument("--manifest", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("import-vni")
    p.add_argument("--registry", required=True); p.add_argument("--source", required=True); p.add_argument("--staging", required=True)
    p = sub.add_parser("train")
    p.add_argument("--input", required=True); p.add_argument("--manifest", required=True); p.add_argument("--output", required=True)
    p.add_argument("--budget-seconds", type=float, default=60); p.add_argument("--max-trials", type=int, default=24)
    p.add_argument("--objective", choices=["mae", "capacity_normalized_mae"], default="mae")
    p = sub.add_parser("report")
    p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("evaluate")
    p.add_argument("--input", required=True); p.add_argument("--actuals", required=True); p.add_argument("--output", required=True)
    for command in ("forecast", "preview"):
        p = sub.add_parser(command)
        p.add_argument("--registry", required=True); p.add_argument("--routes", required=True)
        p.add_argument("--input"); p.add_argument("--origin", required=True)
        p.add_argument("--connectors", nargs="+", required=True); p.add_argument("--targets", nargs="+", default=["export", "import", "export_tight", "import_tight"])
        p.add_argument("--days", type=int, default=1); p.add_argument("--mode", default="production", choices=["production", "research", "shadow"])
        p.add_argument("--scenario", default="baseline"); p.add_argument("--prepared"); p.add_argument("--history"); p.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "demo":
        from .demo import run
        print(run(args.output))
    elif args.command == "normalize":
        print(archive(normalize(read_table(args.input), read_json(args.mapping)), args.output))
    elif args.command == "register":
        print(Registry(args.registry).register(args.package))
    elif args.command == "list":
        print(json.dumps(Registry(args.registry).catalogue(), indent=2))
    elif args.command == "export":
        Registry(args.registry).export(args.model, args.output)
    elif args.command == "activate-routes":
        print(Registry(args.registry).activate(read_json(args.routes)))
    elif args.command == "features":
        from .features import training_table
        inputs = read_table(args.input)
        for col in ("issue", "received", "delivery"):
            inputs[col] = pd.to_datetime(inputs[col], utc=True)
        table = training_table(read_json(args.manifest), read_table(args.requests), inputs)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        table.to_parquet(args.output, index=False)
    elif args.command == "import-vni":
        from .adapters import import_legacy
        print(import_legacy(args.source, Registry(args.registry), args.staging))
    elif args.command == "train":
        from .training import train
        from .reports import training_report
        train(read_table(args.input), read_json(args.manifest), args.output, budget_seconds=args.budget_seconds, max_trials=args.max_trials, objective_metric=args.objective)
        print(training_report(args.output))
    elif args.command == "report":
        from .reports import report
        print(report(read_table(args.input), args.output))
    elif args.command == "evaluate":
        from .evaluation import attach_actuals, scorecard
        inputs, actuals = read_table(args.input), read_table(args.actuals)
        inputs["delivery"] = pd.to_datetime(inputs.delivery, utc=True)
        actuals["delivery"] = pd.to_datetime(actuals.delivery, utc=True)
        joined = attach_actuals(inputs, actuals)
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=False)
        joined.to_parquet(output / "scored_forecasts.parquet", index=False)
        scorecard(joined).to_csv(output / "metrics.csv", index=False)
        from .reports import report
        print(report(joined, output))
    else:
        from .pipeline import forecast, save_run
        inputs = read_table(args.input) if args.input else pd.DataFrame()
        for col in ("issue", "received", "delivery"):
            if col in inputs:
                inputs[col] = pd.to_datetime(inputs[col], utc=True)
        extras = {}
        for key in ("prepared", "history"):
            if getattr(args, key):
                table = read_table(getattr(args, key))
                for col in ("origin", "delivery", "received"):
                    if col in table:
                        table[col] = pd.to_datetime(table[col], utc=True)
                extras[key] = table
        result = forecast(Registry(args.registry), read_json(args.routes), inputs, origin=args.origin,
                          connectors=args.connectors, days=args.days, targets=args.targets, mode=args.mode,
                          scenario=args.scenario, preview=args.command == "preview", **extras)
        if args.command == "preview":
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            result.to_csv(args.output, index=False)
        else:
            from .contracts import digest
            provenance = {name: {"path": getattr(args, name), "sha256": digest(getattr(args, name))}
                          for name in ("input", "prepared", "history") if getattr(args, name)}
            save_run(result, args.output, {"sources": provenance, "policy": read_json(args.routes), "scenario": args.scenario})
        print(json.dumps(result.status.value_counts().to_dict()))


if __name__ == "__main__":
    main()
