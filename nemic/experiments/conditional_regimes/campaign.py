"""Resumable explicit stages; rendering never fits models."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from .common import DATA, ROOT, verified_stage

STAGES = ["inventory", "acquire", "events", "prepare", "pilot", "evaluate", "assess", "bundle", "report", "validate"]


def run(name):
    if name in {"inventory", "acquire"}:
        from . import sources
        return getattr(sources, name)()
    if name == "events":
        from .events import review
        return review()
    if name == "prepare":
        from .data import prepare
        return prepare()
    if name == "bundle":
        from .packaging import build_bundle
        return build_bundle()
    if name == "assess":
        from .assessment import assess
        return assess()
    if name in {"pilot", "evaluate"}:
        from . import research
        return getattr(research, name)()
    if name == "report":
        from .reports import build
        return build()
    if name == "validate":
        from .verify import validate
        return validate()
    raise ValueError(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES + ["all", "status"], default="status")
    parser.add_argument("--resume", action="store_true", help="Skip hash-valid completed stages")
    args = parser.parse_args()
    if args.stage == "status":
        p = DATA / "ledger.json"
        print(p.read_text() if p.exists() else "Campaign has not started")
        return
    for name in STAGES if args.stage == "all" else [args.stage]:
        if args.resume and verified_stage(name):
            print("Verified cached stage", name, flush=True)
            continue
        run(name)


if __name__ == "__main__":
    main()
