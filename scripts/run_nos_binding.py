"""Run NOS constraint mechanics stages (execution/nos_constraint_binding_v1/PLAN.md).

Wrap every invocation in scripts/nos_binding_log.py start/finish entries.

    python scripts/run_nos_binding.py --stage A1 [--ics T-V-MNSP1]   # pair replay
    python scripts/run_nos_binding.py --stage A2                     # setter tables (A2-A7)
    python scripts/run_nos_binding.py --stage B0                     # equation scope + standing tables
    python scripts/run_nos_binding.py --stage B1 [--months 2024-09]  # dispatch archives -> binding panel
    python scripts/run_nos_binding.py --stage B2                     # reconciliation gate
    python scripts/run_nos_binding.py --stage B0b                    # back-fill pre-window equation definitions
    python scripts/run_nos_binding.py --stage B3                     # binding / near / system tables, B4-B6, MV
    python scripts/run_nos_binding.py --stage B7                     # generator-only pressure
    python scripts/run_nos_binding.py --stage D2                     # outlook backtest (12 monthly origins)
    python scripts/run_nos_binding.py --stage D2c                    # embargo confirmation re-runs (two origins)
    python scripts/run_nos_binding.py --stage D3 [--snapshot PUBLIC_NETWORK_YYYYMMDD]   # live outlook (newest NOS file)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nemic.common import IC  # noqa: E402

STAGES = ["A1", "A2", "B0", "B1", "B2", "B0b", "B3", "B7", "D2", "D2c", "D3"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=STAGES)
    parser.add_argument("--ics", nargs="*", default=list(IC))
    parser.add_argument("--months", nargs="*", default=None)
    parser.add_argument("--snapshot", default=None)
    args = parser.parse_args(argv)
    if args.stage == "A1":
        from nemic.experiments.nos_regime.pairs import replay
        result = replay(args.ics)
    elif args.stage == "A2":
        from nemic.experiments.nos_regime.setters import build_setters
        result = build_setters(args.ics)
    elif args.stage == "B0":
        from nemic.experiments.nos_regime.binding import build_scope
        result = build_scope()
    elif args.stage == "B1":
        from nemic.experiments.nos_regime.binding import acquire
        result = acquire(args.months)
    elif args.stage == "B2":
        from nemic.experiments.nos_regime.binding import reconcile
        result = reconcile()
    elif args.stage == "B0b":
        from nemic.experiments.nos_regime.genonly import backfill
        result = backfill()
    elif args.stage == "B3":
        from nemic.experiments.nos_regime.binding_tables import build_binding_tables
        result = build_binding_tables(args.ics)
    elif args.stage == "B7":
        from nemic.experiments.nos_regime.genonly import pressure
        result = pressure()
    elif args.stage == "D2":
        from nemic.experiments.nos_regime.outlook import backtest
        result = backtest(only=[int(x) for x in args.months] if args.months else None)   # --months = origin indices for a worker
    elif args.stage == "D2c":
        from nemic.experiments.nos_regime.outlook import confirm_embargo
        result = confirm_embargo()
    elif args.stage == "D3":
        from nemic.experiments.nos_regime.outlook import live
        result = live(latest=args.snapshot is None, week=args.snapshot)
    else:
        raise SystemExit(f"stage {args.stage} not implemented yet")
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
