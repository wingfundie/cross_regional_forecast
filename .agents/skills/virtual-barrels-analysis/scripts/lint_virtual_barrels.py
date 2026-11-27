"""Standalone prose-quality linter enforcing the Virtual Barrels editorial standard.

Usage:
    python lint_virtual_barrels.py <file_or_dir> [<file_or_dir> ...] [--strict-emdash] [--json]

Checks:
  1. Zero exclamation marks in body prose (outside [!CALLOUT] tags & fenced code blocks)
  2. Zero banned hyperbolic, desk-slang, or generic AI-filler words/phrases
  3. Zero robotic sentence-leading figure/chart narrations ("Figure 1 shows...", "Exhibit 2 confirms...")
  4. Zero raw data filenames (.parquet, .csv, .xlsx, .json) or backticked internal codes in prose
  5. Em-dash restraint (<= 2 per 2,000 words by default; 0 with --strict-emdash)
  6. Restrained inline bold density in running prose (warning if > 1.5% bold spans per word)
  7. Zero cryptic seasonal shorthands (DJF, MAM, JJA, SON, Wi26, Sp26, Su26, Au25)
  8. Zero 3+ consecutive bare stacked figure/image embeds without connective prose
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BANNED_WORDS = re.compile(
    r"\b("
    r"relentless|relentlessly|brutal|brutally|violent|violently|explosive|explode[sd]?|exploding|"
    r"rocket(?:s|ed|ing)?|crush(?:es|ed|ing)?|smash(?:es|ed|ing)?|astonishing|extraordinary|breathtaking|"
    r"unmistakable|existential|catastrophic|notorious|razor-sharp|slam(?:s|med|ming)?|blowouts?|"
    r"skyrocket(?:s|ed|ing)?|vault(?:s|ed|ing)?|powerhouse|titan|game-changer|epicenter|goldmine|"
    r"wild|savage|fierce|vicious|staggering|monument|rookie|amateur|hunting ground|don't sleep|"
    r"blow up|trading playbook|high-conviction|jaw-dropping|meteoric|"
    r"delve[sd]?|delving|tapestry|paradigm shift|double-edged sword|needless to say|"
    r"at the end of the day|testament to"
    r")\b",
    re.I,
)

FIG_LEAD_RE = re.compile(
    r"(?:^|[.!?]\s+|\n)(?:As\s+)?(?:Figures?|Exhibits?|Charts?|Tables?)\s+\d+(?:[–\-]\d+| and \d+)?\s+"
    r"(?:shows?|plots?|tracks?|traces?|illustrates?|confirms?|highlights?|displays?|maps?|"
    r"contrasts?|quantifies?|summarizes?|decomposes?|documents?|reveals?|breaks?|compares?|"
    r"places?|reproduces?|provides?|demonstrates?|presents?)",
    re.M,
)

RAW_FILE_RE = re.compile(r"`[^`]*\.(?:parquet|csv|xlsx|tsv|json|db|sqlite)`")
SEASON_SHORTHAND_RE = re.compile(r"\b(?:DJF|MAM|JJA|SON|Wi\d{2}|Sp\d{2}|Su\d{2}|Au\d{2})\b")
CALLOUT_TAG_RE = re.compile(r"\[![A-Z0-9_-]+\]")
FENCED_CODE_RE = re.compile(r"```.*?```", re.S)
TRIPLE_FIG_RE = re.compile(
    r"(?:(?:\{\{figure:[^}]+\}\}|!\[[^\]]*\]\([^)]+\))\s*\n\s*){3,}"
)


def strip_non_prose(text: str) -> tuple[str, str]:
    """Return (body_without_code, running_prose_without_tables_headings_callouts)."""
    no_code = FENCED_CODE_RE.sub("", text)
    no_tbl = "\n".join(
        line
        for line in no_code.splitlines()
        if not line.strip().startswith("|")
        and not line.strip().startswith("{{figure:")
        and not re.match(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$", line)
    )
    prose_only = "\n".join(
        line
        for line in no_tbl.splitlines()
        if not line.strip().startswith("#")
        and not line.strip().startswith(">")
        and not re.match(r"^\s*(?:[-*]|\d+\.)\s+\*\*[^*]+\*\*[:\-]", line)
    )
    return no_code, prose_only


def lint_file(path: Path, strict_emdash: bool = False) -> dict:
    raw = path.read_text(encoding="utf-8")
    no_code, prose_only = strip_non_prose(raw)
    words = len(re.findall(r"\b\w+\b", prose_only))
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Exclamation marks outside [!CALLOUT] tags & markdown image syntax ![alt](src)
    clean_excl = CALLOUT_TAG_RE.sub("", no_code)
    clean_excl = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", clean_excl)
    excl = clean_excl.count("!")
    if excl:
        errors.append(f"{path.name}: {excl} exclamation mark(s) found")

    # 2. Banned hyperbolic / slang / AI-cliché terms
    hype = sorted({m.group(0).lower() for m in BANNED_WORDS.finditer(no_code)})
    if hype:
        errors.append(f"{path.name}: banned hyperbolic/filler terms: {', '.join(hype)}")

    # 3. Robotic sentence-leading figure narration
    fl = FIG_LEAD_RE.findall(no_code)
    if fl:
        sample = fl[0].strip().replace("\n", " ")[:65]
        errors.append(f"{path.name}: {len(fl)} robotic figure-leading narration(s): '{sample}'")

    # 4. Raw data filenames in prose
    rf = sorted(set(RAW_FILE_RE.findall(no_code)))
    if rf:
        errors.append(f"{path.name}: raw data filename(s) in prose: {', '.join(rf[:6])}")

    # 5. Em-dash restraint
    em = no_code.count("—")
    em_limit = 0 if strict_emdash else max(2, int((words / 2000) * 2) + 1)
    if em > em_limit:
        errors.append(f"{path.name}: {em} em-dash(es) (limit <= {em_limit})")
    elif em > 0 and not strict_emdash:
        warnings.append(f"{path.name}: {em} em-dash(es) present (prefer 0 when clean commas/parentheses work)")

    # 6. Inline bold density in running prose
    bolds = len(re.findall(r"\*\*[^*]+\*\*", prose_only))
    if words >= 150 and (bolds / words) > 0.015:
        warnings.append(
            f"{path.name}: high inline bold density in prose ({bolds} spans / {words} words = {bolds / words * 100:.1f}%)"
        )

    # 7. Cryptic seasonal shorthand codes
    sh = sorted(set(SEASON_SHORTHAND_RE.findall(no_code)))
    if sh:
        errors.append(f"{path.name}: cryptic seasonal shorthand(s): {', '.join(sh)}")

    # 8. 3+ consecutive bare stacked figures
    stacks = TRIPLE_FIG_RE.findall(no_code)
    if stacks:
        errors.append(f"{path.name}: {len(stacks)} block(s) of 3+ consecutive bare stacked figures")

    return {
        "file": str(path),
        "words": words,
        "emdash": em,
        "prose_bolds": bolds,
        "errors": errors,
        "warnings": warnings,
    }


def collect_markdown_files(targets: list[str]) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        p = Path(t)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*.md")))
        else:
            raise FileNotFoundError(f"Target not found: {t}")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint Markdown analysis files against the Virtual Barrels style.")
    parser.add_argument("targets", nargs="+", help="Markdown file(s) or directory(ies) to lint")
    parser.add_argument("--strict-emdash", action="store_true", help="Enforce zero em-dashes strictly")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON summary")
    args = parser.parse_args()

    files = collect_markdown_files(args.targets)
    if not files:
        print("No Markdown files found.", file=sys.stderr)
        sys.exit(1)

    results = [lint_file(f, strict_emdash=args.strict_emdash) for f in files]
    all_errors = [e for r in results for e in r["errors"]]
    all_warnings = [w for r in results for w in r["warnings"]]
    summary = {
        "status": "failed" if all_errors else "passed",
        "files_checked": len(results),
        "total_words": sum(r["words"] for r in results),
        "total_emdash": sum(r["emdash"] for r in results),
        "total_prose_bolds": sum(r["prose_bolds"] for r in results),
        "errors": all_errors,
        "warnings": all_warnings,
    }

    if args.as_json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(
            f"Virtual Barrels Lint: {summary['status'].upper()} | "
            f"{summary['files_checked']} file(s) | {summary['total_words']:,} words | "
            f"{summary['total_emdash']} em-dash(es) | {summary['total_prose_bolds']} prose bold(s)"
        )
        for err in all_errors:
            print(f"  [ERROR] {err}")
        for warn in all_warnings:
            print(f"  [WARN]  {warn}")

    sys.exit(1 if all_errors else 0)


if __name__ == "__main__":
    main()
