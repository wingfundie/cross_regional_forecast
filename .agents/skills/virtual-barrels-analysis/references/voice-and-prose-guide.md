# Virtual Barrels Voice, Prose & Exhibit Guide

This reference defines the editorial craft behind the Virtual Barrels writing style: calm,
mechanistic, empirically grounded institutional analysis that respects an expert reader's time.

---

## 1. The Five Pillars of Virtual Barrels Prose

1. **Plumbing Before Prices:** Explain the physical network, storage geometry, contract term,
   regulatory rule, or balance-sheet constraint *before* citing the resulting price level or
   spread. Price is an output of physical and institutional mechanics, not an independent actor.
2. **Quantified Calm:** Replace adjectives with numbers. Instead of saying a spread "blew out
   violently," state that it widened from ¥2.10/kWh to ¥14.80/kWh between 16:30 and 18:00 JST
   once interconnector utilization reached 100%.
3. **Causal Precision Over Drama:** Trace the exact chain of events (e.g., coastal tank
   drawdown -> minimum-heel city-gas constraint -> rising shadow offer prices -> oil peaking
   dispatch). Never skip intermediate links with vague verbs like "drives," "fuels," or
   "sparks" when a concrete mechanism is known.
4. **Natural Exhibit Integration:** Place charts and tables right after the paragraph that
   introduces the mechanism they quantify. Never write robotic filler like "Figure 3 plots..."
   or "As Exhibit 7 confirms...". Readers can see that a chart plots numbers; prose should tell
   them *why the shape matters*.
5. **Earned Qualification & Exact Boundaries:** State what the data can and cannot prove.
   Separate metered actuals from scheduled plans, commissioned capacity from connection queues,
   and structural baselines from tail episodes.

---

## 2. Hard Punctuation & Typography Rules

| Element | Standard | Rationale |
| :--- | :--- | :--- |
| Exclamation marks (`!`) | **0** in all prose (outside callout tags like `[!MECHANISM]`) | Institutional research never shouts. |
| Em-dashes (`—`) | Target **0** (hard ceiling `<= 2` per 2,000 words) | Overuse creates breathless newsletter cadence; use commas, parentheses, colons, or a second sentence. |
| Inline bold (`**...**`) | Rare in running prose (`< 1.5%` of words) | Wall-to-wall bolding degrades readability; reserve bold for headings, table headers, callout titles, and list lead-ins. |
| Raw technical artifacts | **0** `.parquet`, `.csv`, `.xlsx`, `.json`, or backticked internal codes | Cite datasets cleanly in plain English (e.g., "OCCTO half-hourly interconnector telemetry"). |
| Seasonal & date labels | Plain English (`Winter`, `Spring`, `Summer`, `Autumn`; `April 2024–October 2026`) | Never use cryptic shorthands (`DJF`, `MAM`, `JJA`, `SON`, `Wi26`, `Sp26`, `Su26`, `Au25`). |
| Stacked bare figures | Never stack 3+ figures consecutively | Insert analytical prose between exhibits so every figure earns its space. |

---

## 3. Banned Vocabulary & Calm Replacements

Never use hyperbolic sell-side clichés, trading-desk bravado, or AI-writing filler:

- **Hyperbolic verbs & adjectives:** `relentless`, `brutal`, `violent`, `explosive`, `explodes`,
  `rockets`, `skyrockets`, `crushes`, `smashes`, `slams`, `vaults`, `astonishing`,
  `extraordinary`, `breathtaking`, `unmistakable`, `existential`, `catastrophic`, `notorious`,
  `razor-sharp`, `staggering`, `wild`, `savage`, `fierce`, `vicious`, `jaw-dropping`, `meteoric`.
- **Desk slang & hype nouns:** `blowout`, `powerhouse`, `titan`, `game-changer`, `epicenter`,
  `goldmine`, `monument`, `rookie`, `amateur`, `hunting ground`, `don't sleep`, `blow up`,
  `trading playbook`, `high-conviction`.
- **Generic AI clichés:** `delve`, `tapestry`, `testament to`, `in today's rapidly evolving`,
  `it is worth noting that`, `needless to say`, `paradigm shift`, `double-edged sword`,
  `at the end of the day`.

**Prefer calm, exact substitutes:**
- Instead of `skyrocketed` -> `rose sharply`, `climbed from X to Y`, `re-priced into the ¥40–50/kWh band`
- Instead of `crushed margins` -> `compressed clean dark spreads by $12/MWh`
- Instead of `game-changer` -> `structural shift`, `material capacity addition`
- Instead of `brutal bottleneck` -> `binding transmission constraint`, `persistent transfer ceiling`

---

## 4. Before & After Rewrite Examples

### Example A — Removing Hype and Adding Physical Mechanics

- **Before (Avoid):**
  > **Japan's LNG market is an existential powder keg!** When a brutal cold snap slams Tokyo,
  > gas tanks get crushed in weeks and JEPX prices violently skyrocket — a notorious blowout
  > that traps amateur traders! As Figure 4 confirms, Tokyo Bay has no pipeline backup.
- **After (Virtual Barrels Standard):**
  > To understand why Japanese electricity prices behave differently from European or North
  > American markets during prolonged winter cold snaps, it helps to begin with physical gas
  > plumbing. Across Japan's coastal receiving terminals, usable cryogenic storage equates to
  > roughly two to three weeks of peak winter burn, and no cross-regional high-pressure pipeline
  > connects Osaka Bay to Tokyo Bay. When multi-week heating demand draws Tokyo Bay inventories
  > faster than confirmed tanker arrivals, generators raise day-ahead shadow offer prices to
  > conserve remaining tank heel and protect urban city-gas networks.

### Example B — Removing Robotic Chart Narration

- **Before (Avoid):**
  > Exhibit 12 shows the monthly solar curtailment rate across regions and highlights that
  > Kyushu experienced the highest spring curtailment.
- **After (Virtual Barrels Standard):**
  > Midday solar curtailment concentrates in Kyushu and Shikoku during Spring, where mild
  > weekend demand collides with flat nuclear baseload and narrow export corridors across the
  > Kanmon Strait and Honshi Bridge.

---

## 5. Chart, Table & Layout Standards

When the analysis includes generated charts or PDF/HTML formatting:

1. **Pure White Canvas:** Set chart figure and axes backgrounds to `#ffffff` so exhibits blend
   seamlessly into the document page without tinted grey/lavender boxes.
2. **Clean 1-Line Subtitles:** Format exhibit subtitles as `<Units> · <Clean Date Range>`
   (e.g., `JPY/kWh · April 2024–October 2026`). Collapse any multi-month or multi-season
   series metadata into a clean start–end span; never dump enumerated month lists above charts.
3. **Zero Overlapping Text:** Add sufficient axis headroom for legends, keep tick labels crisp
   and uncrowded, and visually inspect rendered PNGs before finalizing.
4. **Full-Page & Paired Geometry:** Size multi-panel grids tall enough (`7.6–8.5 in` on A4) to
   use full-page vertical space cleanly, and calibrate companion chart pairs (`3.5–4.1 in` each)
   so two related exhibits share a page without leaving half-empty whitespace.
5. **Clean Section Transitions:** Start standalone chapters or major sections cleanly at the top
   of a fresh page in print/PDF deliverables rather than jamming headings onto the bottom third
   of a chart page.
