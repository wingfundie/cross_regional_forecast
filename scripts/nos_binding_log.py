"""Append-only execution log for the NOS constraint mechanics campaign (execution/nos_constraint_binding_v1).

Same commands as scripts/nos_regime_log.py (start / finish / decision / check / open), written to this campaign's folder.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nos_regime_log as log  # noqa: E402

log.FOLDER = log.ROOT / "execution" / "nos_constraint_binding_v1"
log.JSONL = log.FOLDER / "execution_log.jsonl"
log.MARKDOWN = log.FOLDER / "EXECUTION_LOG.md"

if __name__ == "__main__":
    if not log.MARKDOWN.exists():
        log.FOLDER.mkdir(parents=True, exist_ok=True)
        log.MARKDOWN.write_text("# Execution log — NOS constraint mechanics (v1)\n\nAppend-only; written by `scripts/nos_binding_log.py`. "
                                "The JSONL file is authoritative.\n\n| ID | Time | Kind | Stage | Status | Command | Artifacts | Note |\n"
                                "|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    raise SystemExit(log.main())
