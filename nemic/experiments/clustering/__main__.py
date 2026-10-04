"""Command-line entry point for the clustering research campaign."""
from __future__ import annotations

import argparse
import json
import os

from nemic.experiments.core import clean
from .config import DEFAULT_CONFIG, load_config


def main() -> None:
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")
    parser = argparse.ArgumentParser(description="QNI/VNI clustering research campaign")
    parser.add_argument("command", choices=["inventory", "pilot", "run", "report", "validate", "status"])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--connector", choices=["VNI", "QNI"])
    parser.add_argument("--max-origins", type=int)
    parser.add_argument("--stage", choices=["state", "generator", "forecast", "risk", "all"], default="all")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "inventory":
        from .data import inventory
        result = inventory(config)
    elif args.command == "status":
        from .campaign import status
        result = status(config)
    elif args.command == "pilot":
        from .campaign import pilot
        result = pilot(config, connector=args.connector or "VNI", max_origins=args.max_origins)
    elif args.command == "run":
        if not args.connector:
            parser.error("run requires --connector; execute VNI before QNI")
        from .campaign import run
        result = run(config, connector=args.connector, stage=args.stage)
    elif args.command == "report":
        from .report import build_report
        result = build_report(config)
    else:
        from .report import validate_report
        result = validate_report(config)
    print(json.dumps(clean(result), indent=2))


if __name__ == "__main__":
    main()
