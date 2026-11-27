---
name: virtual-barrels-analysis
description: >-
  Write rigorous, calm, mechanics-first institutional analysis pieces, research notes,
  primers, and deep dives using local data and online resources in the "Virtual Barrels"
  editorial style. Use this skill whenever the user asks to produce a fundamental analysis
  piece, market note, sector deep dive, or data-backed report combining datasets with web
  research in a restrained, authoritative, non-hyperbolic voice.
---

# Virtual Barrels Analysis Style & Research Workflow

Produce calm, authoritative, mechanics-first fundamental analysis that explains how physical,
institutional, and economic plumbing actually works before interpreting prices, margins, or
narratives. Prioritize empirical precision, clear causality, and verifiable sourcing from both
local datasets and online primary sources.

## When to Read Detailed References

- For full tone rules, punctuation hygiene, banned vocabulary, before/after rewrites, and chart
  standards, read [voice-and-prose-guide.md](./references/voice-and-prose-guide.md).
- For combining local datasets with web research, evidence hierarchy, and citation discipline,
  read [research-and-sourcing.md](./references/research-and-sourcing.md).

## End-to-End Workflow

### 1. Frame the Plumbing First (Outline Before Writing)

Before drafting prose, map the piece in first-principles order:

1. **Physical and institutional architecture:** What assets, rules, chokepoints, inventories,
   settlement cycles, or balance-sheet constraints govern the system?
2. **Baseline empirical structure:** What do the observed numbers show across time, geography,
   or operating regimes?
3. **Marginal mechanics and edge cases:** What happens when a constraint binds, an outage hits,
   an inventory drains, or a flow reverses?
4. **Forward catalysts and open uncertainties:** Separate confirmed capacity/rules on fixed
   timelines from proposals, applications, or forecasts.

Avoid opening with sensational hooks, rhetorical questions, or trading-desk slogans. Start with
a concrete structural observation grounded in physical or economic reality.

### 2. Synthesize Local Data and Online Resources

- **Local datasets first for empirical baselines:** Compute exact means, medians, tails (p05/p95),
  shares, and seasonal or regime splits directly from the data. Never eyeball or round away
  meaningful variation.
- **Online sources for context, rules, and latest developments:** Prefer primary sources
  (regulators, exchanges, ministries, customs agencies, grid/system operators, company filings,
  IEA/EIA/World Bank/IMF) over commentary. Cross-check secondary press numbers against primary
  disclosures whenever available.
- **Explicit scope discipline:** State exact sample windows, geographies, units, and bases
  (e.g., HHV vs. LHV, FOB vs. CIF, calendar vs. fiscal year) on first mention and keep them
  consistent across every table, chart, and paragraph.
- **Honest qualification:** Distinguish observed facts from estimates, applications from
  commissioned assets, and correlation from proven causation.

### 3. Draft in the Virtual Barrels Voice

Apply these non-negotiable editorial standards across all body prose:

- **Calm authority, zero hype:** Never use exclamation marks (`!`), sensational adjectives
  (`brutal`, `explosive`, `wild`, `staggering`, `game-changer`, `skyrockets`), desk slang
  (`trading playbook`, `high-conviction`, `hunting ground`), or generic AI filler (`delve`,
  `tapestry`, `paradigm shift`). Let the numbers carry the emphasis.
- **Clean sentence geometry:** Avoid em-dash clutter (`—`); prefer clean commas, parentheses,
  colons, or two crisp sentences (target `0` em-dashes; hard cap `<= 2` per 2,000 words).
- **Restrained typography:** Keep inline `**bold**` rare in narrative paragraphs; reserve bold
  for headings, table headers, callout titles, and short lead-in labels in structured lists.
- **Natural exhibit integration:** Never start sentences with robotic chart narration
  (`Figure 1 shows...`, `Exhibit 4 confirms...`). Explain the real-world mechanism in prose and
  let the adjacent exhibit or table substantiate it.
- **Zero code leakage in prose:** Never drop raw filenames (`prices.parquet`, `data.csv`),
  column names, or backticked internal codes into reader-facing analysis prose.
- **Plain-English chronology:** Write `Winter`, `Spring`, `Summer`, `Autumn` (in chronological
  order) and clear date ranges (`April 2024–October 2026`), never cryptic shorthands
  (`DJF`, `MAM`, `JJA`, `SON`, `Wi26`, `Sp26`).

### 4. Structure & Visuals Standard

- **Opening Takeaways:** Open long sections or standalone notes with 3–5 concise, quantified
  bullet takeaways stating the core mechanics and headline empirical numbers.
- **Narrative Flow:** Use tight 3–5 sentence paragraphs anchored by topic sentences that make a
  causal or structural claim, followed by exact numbers and institutional context.
- **Tables & Callouts:** Use compact Markdown tables for multi-region, multi-asset, or
  regime comparisons. Use restrained callouts (`> [!MECHANISM]`, `> [!CONTEXT]`,
  `> [!TAKEAWAY]`) sparingly to explain structural rules or subtle accounting traps.
- **Charts (when generating figures):** Render on a pure white `#ffffff` background matching
  the document canvas; use crisp 1-line subtitles (`Units · Clean Date Range`, never enumerated
  month/date dumps); verify zero overlapping labels or legends; avoid stacking 3+ bare figures
  without connective prose between them.
- **Source Register:** Cite every material fact, rule, and dataset inline (or via numbered
  references) and close with a compact Sources & Evidence section listing publisher, title,
  date, and URL or dataset provenance.

### 5. Lint and Verify Before Delivery

Run the bundled prose linter on every generated Markdown file or directory before returning the
piece to the user:

```bash
python .agents/skills/virtual-barrels-analysis/scripts/lint_virtual_barrels.py <path-to-markdown-or-dir>
```

Use `--strict-emdash` when you want zero em-dashes enforced strictly. Fix every reported error
and review any warnings until the linter exits with status `0` (`"status": "passed"`).
If figures were generated, inspect the rendered PNGs or PDF pages visually to confirm pure
white backgrounds, readable typography, and zero overlapping text.
