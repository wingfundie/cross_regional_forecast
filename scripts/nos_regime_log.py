"""Append-only execution log for the NOS outage regime research (execution/nos_outage_regime_v1).

Usage:
    python scripts/nos_regime_log.py start --stage S-1 --command "python scripts/run_nos_regime.py --stage S-1" --note "pilot VNI+Heywood"
    python scripts/nos_regime_log.py finish E004 --status completed --artifacts data/nos_regime_v1/pilot --note "gate met"
    python scripts/nos_regime_log.py decision --stage G9 --note "switch matching to either-year"
    python scripts/nos_regime_log.py check --stage S5 --command "..." --note "one-off analysis result"
    python scripts/nos_regime_log.py open     # list started entries without a finish
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "execution" / "nos_outage_regime_v1"
JSONL = FOLDER / "execution_log.jsonl"
MARKDOWN = FOLDER / "EXECUTION_LOG.md"
STATUSES = ("completed", "failed", "partial")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).astimezone().isoformat(timespec="seconds")


def load() -> list[dict]:
    if not JSONL.exists():
        return []
    return [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]


def next_id(events: list[dict]) -> str:
    numbers = [int(e["id"][1:]) for e in events if e.get("id", "").startswith("E")]
    return f"E{max(numbers, default=0) + 1:03d}"


def append(event: dict) -> None:
    with JSONL.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    cells = [event["id"], event["time"], event["kind"], event.get("stage", ""), event.get("status", ""),
             f"`{event['command']}`" if event.get("command") else "",
             "<br>".join(event.get("artifacts", [])), event.get("note", "")]
    row = "| " + " | ".join(str(c).replace("|", "\\|").replace("\n", " ") for c in cells) + " |\n"
    with MARKDOWN.open("a", encoding="utf-8") as handle:
        handle.write(row)


def open_entries(events: list[dict]) -> list[dict]:
    finished = {e["ref"] for e in events if e["kind"] == "finish"}
    return [e for e in events if e["kind"] == "start" and e["id"] not in finished]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("start")
    start.add_argument("--stage", required=True)
    start.add_argument("--command", required=True)
    start.add_argument("--note", default="")
    finish = sub.add_parser("finish")
    finish.add_argument("ref")
    finish.add_argument("--status", choices=STATUSES, required=True)
    finish.add_argument("--artifacts", nargs="*", default=[])
    finish.add_argument("--note", default="")
    decision = sub.add_parser("decision")
    decision.add_argument("--stage", required=True)
    decision.add_argument("--note", required=True)
    check = sub.add_parser("check")
    check.add_argument("--stage", required=True)
    check.add_argument("--command", default="")
    check.add_argument("--note", required=True)
    sub.add_parser("open")
    args = parser.parse_args(argv)

    events = load()
    if args.action == "open":
        for e in open_entries(events):
            print(e["id"], e["stage"], e["time"], e["command"])
        return 0
    event = {"id": next_id(events), "time": now(), "kind": args.action}
    if args.action == "start":
        clash = [e for e in open_entries(events) if e["stage"] == args.stage]
        if clash:
            print(f"Stage {args.stage} already has open entry {clash[0]['id']}; check its process first.", file=sys.stderr)
            return 2
        event.update(stage=args.stage, status="started", command=args.command, note=args.note)
    elif args.action == "finish":
        ref = next((e for e in events if e["id"] == args.ref and e["kind"] == "start"), None)
        if ref is None or args.ref not in {e["id"] for e in open_entries(events)}:
            print(f"No open start entry {args.ref}", file=sys.stderr)
            return 2
        event.update(ref=args.ref, stage=ref["stage"], status=args.status, artifacts=args.artifacts,
                     note=f"closes {args.ref}. {args.note}".strip())
    elif args.action == "check":
        event.update(stage=args.stage, status="completed", command=args.command, note=args.note)
    else:
        event.update(stage=args.stage, status="recorded", note=args.note)
    append(event)
    print(event["id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
