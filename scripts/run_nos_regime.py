"""Run NOS outage regime stages (execution/nos_outage_regime_v1/PLAN.md §5).

Every invocation should be wrapped by scripts/nos_regime_log.py start/finish entries.

    python scripts/run_nos_regime.py --stage acquire
    python scripts/run_nos_regime.py --stage episodes
    python scripts/run_nos_regime.py --stage state
    python scripts/run_nos_regime.py --stage keys
    python scripts/run_nos_regime.py --stage compare --ics VIC1-NSW1 V-SA --tag pilot
    python scripts/run_nos_regime.py --stage compare --tag full
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nemic.common import IC  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True, choices=["acquire", "episodes", "state", "keys", "compare"])
    parser.add_argument("--ics", nargs="*", default=list(IC))
    parser.add_argument("--tag", default="full")
    args = parser.parse_args(argv)
    if args.stage == "acquire":
        from nemic.experiments.nos_regime.acquire import acquire_mmsdm
        result = acquire_mmsdm()
    elif args.stage == "episodes":
        from nemic.experiments.nos_regime.episodes import build_episodes
        result = build_episodes()
    elif args.stage == "state":
        from nemic.experiments.nos_regime.state import build_state
        result = build_state()
    elif args.stage == "keys":
        from nemic.experiments.nos_regime.keys import build_keys
        result = build_keys()
    else:
        from nemic.experiments.nos_regime.compare import build_compare
        result = build_compare(args.ics, args.tag)
    print(json.dumps(result, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
