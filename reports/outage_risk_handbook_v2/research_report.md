# Outage Risk and NOS Regime Handbook (v2)

## Executive Overview and Reader Guide

Transmission outages account for more than two-fifths of all sharp 30-minute interconnector limit contractions across the Australian National Electricity Market. Yet market participants attempting to price planned outages from the Australian Energy Market Operator's Network Outage Scheduler (NOS) confront four persistent analytical failures: nearly one-third of booked outages are withdrawn or drift in timing before execution; legacy studies measure outage severity in megawatts without translating limit drops into regional price spreads or daily Settlement Residue Auction (SRA) dollars; overlapping maintenance windows compound non-linearly beyond the sum of individual outage effects; and single-line historical studies of low-event transmission lines suffer severe small-sample noise.

This second-edition flagship handbook consolidates two full years of matched NOS outage attribution (1 September 2024 to 31 August 2026, fixed NEM time UTC+10), 126,582 walk-forward outage-outlook forecasts across 12 chronological monthly origins, and all 50 monitored transmission lines (631 verified outage events) into a single institutional reference. Every raw megawatt shift is paired with matched-control regional spread and daily SRA dollar attribution; the legacy binding and setter outlooks are repaired using strictly chronological Empirical-Bayes shrinkage and isotonic probability calibration; 338 concurrent N-1-1 outage pairs are audited for super-additive compounding; and all 50 transmission lines are stabilised via hierarchical Empirical-Bayes pooling across eight electrical corridors, anchored by forensic deep dives on Capital-Canberra Line 6 and Dapto-Marulan Line 8.

## Chapter 1 · Network Outage Scheduler Reliability and Matched-Pair Control Design

Evaluating the commercial impact of a planned transmission outage requires overcoming two distinct statistical traps before a single dollar is calculated. First, an outage appearing on the forward Network Outage Scheduler (NOS) calendar is a contingent operational plan rather than a binding physical commitment: transmission network service providers routinely cancel, postpone, or finish maintenance hours earlier than booked. Second, transmission maintenance is not scheduled randomly across the year. Network operators deliberately cluster line outages into mild shoulder seasons (spring and autumn) and daytime working hours when regional demand is moderate and security risk is lower. Simply comparing average interconnector limits or regional prices during outage hours against the rest of the year therefore confounds the physical effect of removing a transmission line with the seasonal calendar of when maintenance is allowed to proceed.

> [!TAKEAWAY] Core Methodological Discipline
> Credible outage risk pricing requires separating two distinct probabilities: the scheduling probability that a booked outage executes during its stated window, and the conditional physical and economic impact given that its constraint set is actually invoked, measured strictly against same-season, same-time-of-day, non-outage control intervals.

### 1.1 Anatomy of NOS schedule drift across six interconnectors

Auditing all 3,165 booked NOS transmission-outage episodes linked to interconnector constraint sets over the two-year study window (September 2024 to August 2026) exposes why naive calendar-based trading rules systematically over-hedge distant outage dates.

| Interconnector | Study Year 1 episodes | Study Year 2 episodes | Mean withdrawn / cancelled (%) | Invoked given non-withdrawn (%) | Median start shift (hours) | Median end shift (hours) | Early return share (%) | Overrun share (%) | Median booking lead (days) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| VNI | 385 | 295 | 35.0% | 99.8% | +0.13 | -0.76 | 43.5% | 5.4% | 16.4 |
| QNI | 201 | 201 | 23.9% | 99.0% | +0.09 | -0.68 | 43.3% | 6.0% | 14.0 |
| Heywood | 456 | 345 | 33.7% | 99.8% | +0.08 | -0.46 | 37.7% | 4.4% | 14.4 |
| Directlink | 127 | 128 | 23.9% | 99.5% | +0.13 | -0.83 | 47.0% | 6.2% | 16.3 |
| Murraylink | 419 | 365 | 34.0% | 99.8% | +0.13 | -0.69 | 42.6% | 4.3% | 14.5 |
| Basslink | 136 | 107 | 35.4% | 100.0% | +0.08 | -0.49 | 37.9% | 4.7% | 14.9 |

Three empirical regularities govern NOS execution across all six links:

1. **Nearly one-third of all bookings never execute (31.0% mean withdrawal rate):** Across the twelve corridor-years, withdrawal rates range from 18.1% (Directlink Year 1) up to 45.6% (Basslink Year 1), averaging 35.0% on VNI, 33.7% on Heywood, 34.0% on Murraylink, and 23.9% on QNI and Directlink. Any forward pricing model that treats a booking 30 to 90 days ahead as a 100% certain capacity drop immediately introduces a 24% to 35% upward bias before a single constraint equation is evaluated.
2. **Once an outage proceeds, constraint-set invocation is virtually deterministic (99.7%):** Conditional on a booking not being withdrawn, AEMO invokes the associated constraint set in 99.0% to 100.0% of episodes across every interconnector. Operational uncertainty therefore concentrates heavily in whether the transmission operator cancels or reschedules the booking, rather than whether AEMO enforces the security equations once switching begins.
3. **Asymmetric execution duration favours early return over overrun by roughly eight to one:** Executed outages start slightly late (median start shift +0.08 to +0.15 hours) and finish materially early (median end shift -0.38 to -0.95 hours). Between 34.7% and 48.4% of non-withdrawn outages return early, whereas only 3.2% to 8.7% overrun their booked end time. That early-return asymmetry matters directly for evening-peak risk: maintenance booked from 07:00 to 17:00 frequently restores lines by 16:00, just ahead of the highest-priced evening demand ramp.

### 1.2 From raw bookings to matched-pair economic attribution

To eliminate seasonal and diurnal selection bias when valuing outage families, the attribution pipeline constructs exact matched treated-versus-control half-hour pairs across every interconnector and direction. Each treated half-hour in which a specific constraint-set family (such as `N-MNYS_5_WG_CLOSE` or `V-MLSY_NOEMTT_R`) is actually invoked is paired with a strictly non-outage control half-hour matched on calendar proximity, time of day, and ambient system conditions.

Once exact treated-control pairs $(t_m, c_m)$ are assembled for each family-direction across all six interconnectors, every economic outcome is evaluated strictly as the paired difference:

$$\Delta Y_m = Y(t_m) - Y(c_m)$$

where $Y$ is either the directional regional dispatch price spread ($\pi_{\text{recv}} - \pi_{\text{send}}$ in $/MWh) or the settled directional SRA residue scaled to a 48-half-hour daily rate ($/day). Because transmission outages persist across multi-hour and multi-day blocks, standard independent-interval standard errors severely understate uncertainty. Every confidence interval reported in this handbook is therefore computed via a seven-day contiguous calendar-block bootstrap, ensuring that week-long maintenance episodes are resampled as intact blocks.

### 1.3 Why megawatt limit drops and dollar impacts decouple

Before inspecting the family-level economic ledger in Chapter 2, desks should internalise a fundamental physical asymmetry: a 200 MW reduction in an interconnector's export limit does not automatically raise the directional price spread or increase SRA payouts. Three distinct commercial regimes occur under transmission outages:

- **With-price tightening (SRA-expanding):** When an outage caps transfer in the dominant economic direction while flow remains positive and regional price separation widens faster than volume shrinks, directional congestion rent ($F \times \Delta\pi$) rises and SRA holders earn higher daily payouts.
- **Volume-starvation clamping (SRA-destroying):** When an outage slashes directional transfer capacity nearly to zero (or below zero into forced reverse flow), the flow factor $F$ collapses even if the regional price spread widens. Because SRA payouts equal flow multiplied by spread, clamping a corridor down to 0 MW destroys daily SRA revenue completely.
- **Counter-price loop-flow forcing (negative-residue trap):** When an outage forces physical power to flow from a high-price region into a low-price region to protect a parallel line, directional settlement residues turn sharply negative, imposing direct dollar losses on the pooled border SRA bucket.

Chapter 2 quantifies all three regimes across 697 supported outage family-directions spanning all six NEM interconnectors.

## Chapter 2 · Economic Spread and SRA Dollar Attribution by NOS Outage Family

Legacy NOS outage studies documented how many megawatts each constraint-set family removed from an interconnector's export or import ceiling, leaving trading desks to guess what a 120 MW reduction on Heywood or a 45 MW reduction on VNI was actually worth in regional spreads and Settlement Residue Auction payouts. Joining every exact matched treated-control half-hour pair across all six interconnectors directly to realised 30-minute regional price spreads and settled directional SRA residues closes that gap completely.

Across the two-year panel, 697 outage family-directions (representing 201 distinct constraint-set families across VNI, QNI, Heywood, Directlink, Murraylink, and Basslink) meet the minimum 24 matched half-hour threshold, and 312 meet a stricter well-supported commercial screen (at least five treated days, at least 96 matched half-hours, and supported or indicative tier status). Across all 697 family-directions, 384 register statistically non-zero directional price-spread effects (seven-day block-bootstrap 95% confidence interval excluding zero) and 367 register statistically non-zero daily SRA residue shifts.

### 2.1 The highest-impact SRA-widening and SRA-destroying outage families

Ranking well-supported outage families by their matched daily SRA residue shift ($/day, evaluated on the pooled border settlement bucket) separates genuinely lucrative with-price congestion events from destructive flow-clamping and counter-price traps.

| Link & direction | Outage family | Matched half-hours | Matched Cap delta (MW) | Matched Spread delta ($/MWh) | Matched SRA delta ($k/day) | 95% Block CI excludes zero (SRA) | Economic regime |
|---|---|---:|---:|---:|---:|---|---|
| Murraylink forward | `N-JNWG_RADIAL` | 500 | -107 | +$690.9 | +$9,664.1k | No (wide skew) | Extreme SA scarcity coincidence |
| Heywood forward | `N-JNWG_RADIAL` | 1,369 | +38 | +$245.3 | +$3,372.5k | No (spread CI > 0) | Southern NSW radial outage spillover |
| QNI reverse | `N-DTSS_11` | 3,669 | +58 | +$84.7 | +$1,430.6k | No (spread CI > 0) | NSW north-south spread widening |
| Heywood forward | `N-BABU` | 2,915 | +17 | +$45.8 | +$720.5k | Yes | Balranald-Buronga 220 kV spillover |
| VNI reverse | `V-KG_WE_RC` | 508 | -2 | +$270.8 | +$428.3k | Yes | Kerang-Wemen-Red Cliffs 220 kV |
| VNI forward | `N-MNYS_5_WG_CLOSE` | 9,345 | -45 | -$72.1 | -$572.6k | Yes | Marulan-Yass Line 5 (91 days) |
| QNI reverse | `Q-BRTX1` | 238 | -291 | -$44.1 | -$858.1k | Yes | Braemar transformer outage |
| VNI forward | `V-KG_WE_RC` | 488 | +134 | -$278.9 | -$965.4k | No (spread CI < 0) | Reverse polarity on VNI forward |
| Heywood forward | `V-MLSY_NOEMTT_R` | 4,730 | -131 | -$112.5 | -$1,624.8k | Yes | Moorabool-Sydenham (42 days) |
| Murraylink forward | `N-LTWG_RADIAL` | 306 | -74 | -$186.5 | -$2,440.0k | Yes | Lower Tumut-Wagga radial clamp |
| Murraylink forward | `I-VSML_132` | 182 | +83 | -$214.6 | -$2,744.1k | No (spread CI < 0) | Riverland 132 kV Murraylink clamp |

Three commercial insights jump directly off the matched SRA leaderboard:

1. **Multi-week transmission outages can systematically bleed SRA holders by half a million to $1.6 million per day:** Consider `N-MNYS_5_WG_CLOSE` (Marulan to Yass 330 kV Line 5 outage with Wagga bus closed), one of the largest sustained outage families in the two-year sample (9,345 matched half-hours across 91 treated days and 15 episodes, logging 3,593 binding intervals at a $257/MWh median marginal value). On VNI forward, `N-MNYS_5_WG_CLOSE` reduced median directional capacity by 45 MW while reducing matched daily VNI forward SRA payouts by -$572.6k/day (95% block CI strictly negative: -$1,256k to -$127k/day). Similarly, `V-MLSY_NOEMTT_R` on Heywood forward (4,730 matched half-hours across 42 days) cut Heywood forward capacity by -131 MW and eroded VIC to SA SRA payouts by -$1,624.8k/day (95% block CI strictly negative: -$4,593k to -$112k/day). On QNI reverse, `Q-BRTX1` (238 matched half-hours) slashed QNI southward capacity by -291 MW and cut QLD to NSW SRA payouts by -$858.1k/day (95% block CI strictly negative).
2. **Cross-border spillover outages rival local border outages in dollar impact:** Notice how southern New South Wales 220 kV and 330 kV outage families (`N-BABU`, `N-JNWG_RADIAL`, `N-LTWG_RADIAL`) appear at the very top of the Heywood and Murraylink economic tables. Because the Buronga-Balranald-Darlington Point-Wagga spine forms the northern arc of the southern NEM loop, taking a line out in south-western New South Wales reshapes loop flows into Victoria and South Australia, producing a statistically decisive +$720.5k/day SRA increase on Heywood forward during `N-BABU` (2,915 matched half-hours across 34 days) and a -$2,440.0k/day drop during `N-LTWG_RADIAL` on Murraylink forward.
3. **Directional polarity flips across opposite borders:** The Kerang-Wemen-Red Cliffs 220 kV family (`V-KG_WE_RC`) illustrates why desks must price directional portfolios jointly. During `V-KG_WE_RC`, VNI forward spreads contracted by -$278.9/MWh (-$965.4k/day SRA impact), while VNI reverse spreads widened symmetrically by +$270.8/MWh, delivering a statistically significant +$428.3k/day gain on VNI reverse.

### 2.2 Why capacity drops do not map monotonically to spreads

Plotting every outage family's matched megawatt capacity effect against its matched regional price-spread change confirms that physical limit contraction is a necessary diagnostic rather than a sufficient pricing proxy.

The scatter divides into four operational quadrants:

- **Lower-left quadrant (negative MW, negative spread delta):** Outages that restrict transfer during shoulder-season periods when the sending region was already surplus or that clamp flow before regional scarcity develops, such as `V-MLSY_NOEMTT_R` (-131 MW, -$112.5/MWh) and `Q-BRTX1` (-291 MW, -$44.1/MWh).
- **Upper-left quadrant (negative MW, positive spread delta):** Classic scarcity bottlenecks where cutting transfer capacity directly isolates a high-cost importing region, such as `N-JNWG_RADIAL` on Murraylink forward (-107 MW, +$690.9/MWh).
- **Upper-right quadrant (positive MW, positive spread delta):** Outages on neighbouring corridors or opposite directions that relieve a local parallel loop while simultaneously trapping regional generation elsewhere, lifting both nominal headroom and border spreads (for example, `N-DTSS_11` on QNI reverse at +58 MW and +$84.7/MWh across 3,669 matched half-hours).
- **Near-zero MW band with wide vertical dispersion:** Outages whose average capacity shift over 24 hours is modest (-20 to +20 MW), yet whose binding shadow prices spike sharply during narrow evening-peak windows, generating large dollar swings without showing up in raw median-MW league tables.

> [!WARNING] Interpreting Wide Block-Bootstrap Confidence Intervals on Skewed Spikes
> Wholesale electricity prices in the NEM are heavily right-skewed up to the Market Price Cap. An outage family spanning 9 to 15 treated days where one single evening hit $15,000/MWh can display a very large point-average SRA gain (+$9.7m/day for `N-JNWG_RADIAL` on Murraylink) whose seven-day block-bootstrap 95% CI still crosses zero (-$283k to +$11.3m/day). Desks should therefore always check the `sra_ci_excl_zero` flag and sample days alongside the point estimate rather than extrapolating single-episode price-cap coincidences as repeatable carry.

The searchable directory below enables risk analysts and traders to filter all 260 highest-impact matched NOS outage family-directions by interconnector and sort interactively by daily SRA impact, regional spread shift, megawatt capacity drop, or binding marginal value.

### 2.3 Worked SRA P&L anatomy: comparing Marulan Line 5 against Moorabool-Sydenham

To see how physical flow clamping translates directly into daily trading P&L, consider a portfolio holding a 25% share of quarterly VIC to NSW Settlement Residue Auction units during a planned 14-day outage on Marulan to Yass 330 kV Line 5 (`N-MNYS_5_WG_CLOSE`), and contrast it with a 25% share of VIC to SA units during a 14-day Moorabool to Sydenham outage (`V-MLSY_NOEMTT_R`).

Under normal intact spring conditions, VNI forward transfer clears near 750 MW during daytime ramps and 900 MW overnight, collecting positive settlement residue whenever NSW prices clear above Victoria. Once `N-MNYS_5_WG_CLOSE` is invoked, transient stability and thermal constraints on the remaining Snowy to Sydney 330 kV paths (`N::N_MNYS_2` and `V^^N_MNYS_1`, documented in Flagship Edition A) tighten across 9,345 matched half-hours, cutting median forward capacity by 45 MW and collapsing net daily border residue by -$572.6k/day across the pooled VNI forward bucket. For a 25% SRA holder, a two-week execution window represents roughly -$2.0 million in lost or negative settlement carry relative to matched non-outage days, even though a naive headline glance at the -45 MW median capacity reduction might suggest only a minor nuisance. The reason the dollar impact is large relative to the median MW shift is timing: the 3,593 binding intervals inside `N-MNYS_5_WG_CLOSE` carry a $257/MWh median shadow price and concentrate precisely in the high-spread hours when NSW imports are needed most, while counter-price loop flows during midday solar peaks erode the rest of the day's accrual.

On VIC to SA during `V-MLSY_NOEMTT_R`, the volume-starvation effect is even sharper. Removing a primary 500 kV feeder west of Melbourne cuts Heywood forward capacity by -131 MW across 4,730 matched half-hours (42 treated days), compressing both transfer volume and with-price spread capture for a combined -$1,624.8k/day pooled reduction (95% block CI strictly negative: -$4,593k to -$112k/day). A desk holding 25% of VIC to SA SRA units across a two-week execution window faces an expected -$5.7 million draw relative to matched controls. Critically, the exact opposite occurs during `N-BABU` (Balranald to Buronga 220 kV outage in south-western New South Wales): instead of starving Heywood flow, cutting the northern 220 kV bypass routes additional transfer pressure across the Victoria to South Australia cut-plane while widening the SA minus VIC spread by +$45.8/MWh, adding +$720.5k/day (95% block CI strictly positive) to the pooled VIC to SA SRA bucket.

These worked comparisons establish a practical trading principle: desks cannot map outage risk using a single scalar "MW lost" column. Every forward booking must be tagged with its economic polarity (SRA-expanding bottleneck, volume-starving flow clamp, or counter-price loop-flow trap) before sizing quarterly SRA bids or regional cap swaps.

Evaluating single outage families in isolation still leaves out one of the most dangerous operational realities on the transmission grid: what happens when two planned or forced outages occur at the exact same time? Chapter 3 measures that N-1-1 compounding risk directly.

## Chapter 3 · N-1-1 Concurrent-Outage Super-Additivity

Standard outage risk screening treats the forward NOS calendar additively: if Outage Family A typically cuts an interconnector's limit by 100 MW and Outage Family B cuts it by 80 MW, a naive linear spreadsheet projects a combined 180 MW drop when their maintenance windows overlap. Power-system physics does not obey linear superposition. Removing a single transmission line moves the grid from an N-0 intact state to an N-1 state while leaving parallel redundancy intact. Removing a second electrically coupled line simultaneously pushes the corridor into an N-1-1 contingency regime where remaining thermal paths, voltage-support margins, and transient stability angles collapse non-linearly, often triggering dedicated dual-outage (`N-X_*`) constraint equations with severely depressed transfer ceilings.

To test whether concurrent outages compound beyond linear sums across the NEM, we audited the complete 35,040-half-hour family occupancy matrix across all six interconnectors. For every link, we identified every pair of relevant outage families $(A, B)$ that overlapped concurrently for at least 24 half-hours (12 hours) while also occurring standalone (A without B, and B without A) for at least 24 half-hours each over the two-year study window. Across all six interconnectors, exactly 338 concurrent family pairs satisfied these strict empirical support rules.

### 3.1 Formal super-additivity accounting

Let $\bar{C}_0$ denote the baseline average half-hour tight directional capacity during intervals when neither family A nor family B is active. Denote the standalone effects by $\Delta C_A = \bar{C}_{A \setminus B} - \bar{C}_0$ and $\Delta C_B = \bar{C}_{B \setminus A} - \bar{C}_0$, and the observed concurrent joint effect by $\Delta C_{A \cap B} = \bar{C}_{A \cap B} - \bar{C}_0$. The exact super-additivity residual is:

$$S_{A,B} = \Delta C_{A \cap B} - (\Delta C_A + \Delta C_B)$$

Whenever $S_{A,B} < 0$, the simultaneous overlap cuts transfer capacity deeper than the linear sum of the two standalone outages. A pair is flagged as a statistically compounding N-1-1 hazard if $S_{A,B} < -20\text{ MW}$ and its seven-day block-bootstrap 95% upper confidence bound lies strictly below zero.

### 3.2 Nearly one-third of overlapping outage pairs compound non-linearly

Across the 338 tested pairs, 109 pairs (32.2%) exhibit statistically significant super-additive capacity collapses. The worst compounding pairs cut hundreds of megawatts deeper than standalone linear expectations, and frequently flip regional spreads from benign to stressed.

| Link & direction | Overlapping outage pair (Family A + Family B) | Overlap (hh) | Standalone A (MW) | Standalone B (MW) | Linear sum (MW) | Observed joint (MW) | Extra N-1-1 loss (MW) | Extra spread shift ($/MWh) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| VNI forward | `N-BABU` + `N-X_03+4_WG_CLOSE` | 75 | +190 | -91 | +99 | -677 | -776 | +$69.4 |
| Basslink reverse | `N-LTWG_RADIAL` + `N-TWUL_85` | 32 | +144 | +47 | +191 | -242 | -433 | -$83.8 |
| VNI forward | `N-DPWG_63_X5` + `N-JNWG_RADIAL` | 495 | +119 | +415 | +534 | +113 | -420 | -$17.3 |
| Heywood reverse | `S-TBTU` + `S-TB275_W_BUS_BC-2CP` | 114 | -108 | +212 | +104 | -257 | -361 | -$32.8 |
| VNI forward | `N-DPWG_63_X5` + `N-WAGGA_330_BUSB` | 429 | +116 | +341 | +458 | +117 | -341 | -$13.2 |
| Heywood reverse | `S-TBSE` + `S-TB275_W_BUS_BC-2CP` | 114 | -140 | +213 | +74 | -256 | -330 | +$29.5 |
| QNI forward | `N-X_LPSS_MPWW` + `Q-X_HACL_HATR` | 206 | +133 | +133 | +266 | +9 | -257 | -$4.3 |
| QNI forward | `N-DTSS_11` + `N-AVMA_17` | 168 | +90 | +173 | +264 | +18 | -246 | -$359.5 |
| QNI reverse | `Q-BRTX1` + `Q-BKBM` | 28 | -175 | -234 | -410 | -626 | -217 | +$2.6 |
| QNI forward | `N-DMSR_8J` + `N-ARKS_965` | 204 | -376 | +132 | -245 | -439 | -194 | -$29.8 |
| QNI forward | `N-ARDM_8C` + `N-ARKS_965` | 204 | -385 | +114 | -271 | -456 | -185 | -$16.0 |
| Heywood forward | `S-TBSE` + `S-X_BGBW+BGDV+BGTX` | 36 | -168 | -95 | -263 | -418 | -155 | -$98.0 |

Four physical N-1-1 archetypes emerge clearly from the 109 compounding pairs:

1. **Southern NSW dual-corridor bottleneck (`N-BABU` + `N-X_03+4_WG_CLOSE` on VNI forward):** Taken separately, `N-BABU` (Balranald-Buronga 220 kV) averaged +190 MW above baseline on VNI forward (reflecting mild weather timing) and `N-X_03+4_WG_CLOSE` averaged -91 MW, giving an additive expectation of +99 MW. During the 75 half-hours when both families overlapped simultaneously, however, VNI forward capacity collapsed to **-677 MW below baseline** (an extra super-additive collapse of **-776 MW**), forcing heavy reverse flow while super-additively widening the Victoria to New South Wales spread by **+$69.4/MWh**. The physical mechanism is textbook N-1-1: cutting the western 220 kV parallel path (`N-BABU`) at the exact same moment as Lower Tumut-Yass/Collector-Marulan 330 kV lines (`03+4`) removes both east and west escape routes around Snowy, forcing NEMDE to clamp VNI northward transfer deeply negative.
2. **Northern NSW QNI spine stacking (`N-DMSR_8J` or `N-ARDM_8C` + `N-ARKS_965` on QNI forward):** Removing a 330 kV QNI feeder (`8C` Armidale-Dumaresq or `8J` Dumaresq-Bulli Creek) already cuts QNI forward capacity by -376 to -385 MW standalone. Stacking an overlapping northern NSW 132 kV Armidale-Koolkhan (`N-ARKS_965`) outage on top of it drives the observed joint drop down to **-439 to -456 MW** across 204 overlapping half-hours (-185 to -194 MW worse than the linear sum). On QNI reverse, stacking Braemar transformer (`Q-BRTX1`, -175 MW standalone) with Blackwall-Belmont (`Q-BKBM`, -234 MW standalone) produces a **-626 MW** joint ceiling collapse (-217 MW worse than additive).
3. **South Australian Tailem Bend 275 kV bus and line stacking on Heywood:** Because Tailem Bend is the primary South Australian landing point for Heywood, overlapping a South East to Tailem Bend (`S-TBSE`, -140 MW) or Tailem Bend to Tungkillo (`S-TBTU`, -108 MW) line outage with a Tailem Bend 275 kV West Bus outage (`S-TB275_W_BUS_BC-2CP`) slashes Heywood reverse capacity by **-256 to -257 MW** (-330 to -361 MW super-additive relative to the +74 to +104 MW linear sum). In the forward direction, stacking `S-TBSE` (-168 MW) with the `S-X_BGBW+BGDV+BGTX` outage family (-95 MW) slashes Heywood forward capacity by **-418 MW** (-155 MW beyond linear addition).
4. **Cross-corridor FCAS and frequency-protection stacking on Basslink:** On Basslink reverse, overlapping Tasmanian/global fast-frequency-response constraints (`F-I_FFR_GLOBAL` or `F-T-GO_CB_A752`) with mainland southern-ring radial outages (`N-JNWG_RADIAL`, `N-LDTW_84`, `V-MLSY_NOEMTT_R`) triggers large negative super-additivity (-147 to -393 MW across 415 to 2,346 overlapping half-hours) as combined system-inertia and continental balancing limits tighten simultaneously.

### 3.3 Distribution of compounding severity across the six interconnectors

Comparing compounding pair counts and worst-decile (P10) super-additive losses across all six links confirms that N-1-1 risk is concentrated where meshed AC paths converge on narrow regional choke points: VNI, QNI, Heywood, and Basslink exhibit P10 super-additive losses of -150 to -350 MW, whereas Directlink and Murraylink show smaller absolute megawatt residuals proportional to their 180 to 220 MW cable ratings.

> [!TAKEAWAY] Operational Rule for Forward Outage Calendars
> Any forward NOS screening tool that scores booked outages one line at a time misses one-third of real network risk. Whenever a forward calendar week shows two or more bookings overlapping inside the same regional choke point (Southern NSW 330/220 kV around Wagga-Yass-Buronga; Northern NSW 330/132 kV around Armidale-Dumaresq; or South Australia's Tailem Bend 275 kV hub), desks must apply an explicit N-1-1 compounding multiplier rather than summing standalone single-family MW impacts.

### 3.4 Worked physical example: why parallel-path removal breaks linear additivity

Why does overlapping `N-BABU` (Balranald to Buronga 220 kV) with `N-X_03+4_WG_CLOSE` (Lower Tumut to Yass Line 03 plus Collector to Marulan Line 4) cut VNI forward capacity by -677 MW when the standalone effects sum linearly to +99 MW? The answer lies in basic Kirchhoff impedance redistribution across parallel corridors.

In an intact N-0 network, power flowing northward from Victoria into New South Wales divides naturally across two parallel north-south pathways: the main 330 kV Snowy-Murray-Wagga-Yass-Marulan eastern spine and the western 220 kV Murray-Kerang-Red Cliffs-Buronga-Balranald-Darlington Point arc. When only one corridor loses a circuit (an N-1 state), the intact parallel corridor absorbs redistributed power flow without immediately violating thermal or transient-stability limits, and transmission operators frequently schedule single-circuit work during mild spring or autumn weekends when baseline transfer capacity sits high.

When both corridors suffer simultaneous outages (an N-1-1 state), the redistribution safety valve vanishes. Any contingent trip of a remaining 330 kV spine circuit (such as Line 5 or Line 051) now dumps the entire interregional transfer onto a single weakened path with no western 220 kV relief route, pushing voltage angles beyond the transient-stability boundary. NEMDE responds by invoking a dedicated dual-outage stability or thermal constraint equation whose right-hand side is dramatically lower than either standalone N-1 equation, clamping VNI forward limits deeply negative (forcing southward flow) and widening the Victoria to New South Wales spread by an extra +$69.4/MWh beyond standalone expectations.

A parallel N-1-1 geometry governs South Australia's Tailem Bend 275 kV hub. Removing one South East to Tailem Bend 275 kV feeder (`S-TBSE`) still leaves the second parallel circuit and intact Tailem Bend bus tie-breakers to absorb Heywood transfer. Removing a Tailem Bend West Bus section (`S-TB275_W_BUS_BC-2CP`) at the exact same moment strips away bus redundancy so a single fault isolates both lines or trips the remaining path, causing observed Heywood reverse capacity to drop -256 MW against a +74 MW linear sum (-330 MW super-additive collapse). Quantitative forecasting models that encode NOS outages strictly as independent additive binary dummy variables ($x_A + x_B$) structurally cannot represent these N-1-1 cliffs unless they include explicit regional overlap counts and pairwise corridor interaction terms.

Having quantified what outages cost in dollars (Chapter 2) and how overlapping outages compound non-linearly (Chapter 3), we now turn to the core forecasting challenge of the NOS regime: repairing the legacy forward binding outlook so its probabilities can be trusted across 0 to 365 day horizons.

## Chapter 4 · Chronological Empirical-Bayes and Isotonic Calibration of the NOS Binding Outlook

One of the sharpest self-diagnoses in the prior NOS constraint-binding study was that its forward 12-month outage outlook failed basic probabilistic calibration and skill gates. Across the 96 evaluation cells (2 layers: binding and setter; 4 lead bands: 0-7, 8-30, 31-90, and 91-365 days; 6 interconnectors x 2 directions), the legacy outlook achieved positive Brier skill over both system-normal and last-year baselines on only a small minority of cells (23/96 across the full legacy panel, and just 14/96 on strictly expanding out-of-sample origins 2 through 12). Worse, its reliability curve was severely biased upward: whenever the legacy binding model emitted a 30% to 50% binding probability (bin mean 34.7% to 36.2%), the equation actually bound only 12.8% to 15.0% of the time, and when the setter model predicted 70% to 100% (bin mean 89.1%), the equation set the limit only 46.2% of the time.

Rather than merely documenting that failure as a caveat, this second-edition handbook diagnoses its three exact statistical root causes and implements a strictly chronological, zero-leakage calibration upgrade evaluated on identical out-of-sample rows across all 96 cells.

### 4.1 Why the legacy NOS outlook over-predicted by two to three times

Inspecting the 126,582 walk-forward rows across the 12 monthly issue origins (12 September 2025 through 14 August 2026) exposes three compounding biases baked into the legacy raw score (`p_outlook`):

1. **Unadjusted booking withdrawal and rescheduling hazard:** As Chapter 1 established, 31.0% of NOS bookings are withdrawn outright and up to 48% return early. Because the legacy outlook multiplied historical conditional binding frequencies without discounting for lead-band cancellation and window-drift decay, a booking 60 or 180 days ahead carried nearly the same raw binding probability as a confirmed outage starting tomorrow morning.
2. **Unshrunk small-sample family noise:** Rare outage families that bound heavily during one brief past episode received high raw conditional probabilities (`q`), even when the family had only 10 to 20 historical bookings and high variance across seasons.
3. **Uncertain family inference on forward bookings:** Many distant NOS bookings do not yet carry an explicit AEMO constraint-set ID at issue time and rely on inferred family matching (`family_probability < 1.0`). When family inference misses (`family_realised = False`), the predicted family equation almost never binds, pulling realised frequency sharply below raw conditional probability.

### 4.2 Strictly chronological expanding-origin calibration architecture

To eliminate every trace of future look-ahead bias, calibration is fitted inside a strict expanding chronological loop across the 12 monthly issue origins $t_1, t_2, \dots, t_{12}$. For every test origin $t_k$ ($k \in \{2, \dots, 12\}$), all parameters are estimated exclusively from strictly earlier origins $\{t_1, \dots, t_{k-1}\}$:

The three-stage calibration pipeline transforms each booking's raw outlook score $p_{\text{raw}}$ as follows:

1. **Lead-band occurrence-hazard scaling:** From prior origins only, compute the empirical ratio of realised binding frequency to raw predicted probability within each `(layer, lead_band)` bucket, clipped safely to $[0.15, 1.20]$, and form the hazard-adjusted score $p_{\text{adj}} = \text{clip}(p_{\text{raw}} \cdot h_{\text{layer,lead}}, 0, 1)$.
2. **Hierarchical Empirical-Bayes shrinkage:** Shrink each outage family's prior empirical binding rate $\bar{y}_f$ toward its `(layer, link, direction, lead_band)` cell prior $\mu_{\text{cell}}$ with pseudo-count $m_0 = 25$ bookings: $\hat{y}^{\text{EB}}_f = (n_f \bar{y}_f + m_0 \mu_{\text{cell}}) / (n_f + m_0)$. Blend $p_{\text{adj}}$ with $\hat{y}^{\text{EB}}_f$ weighted by `family_probability` (trusting the family-specific hazard score more when family identification is certain and shrinking harder toward the cell prior when family inference is uncertain), anchored lightly to system-normal probability $p_{\text{normal}}$.
3. **Monotonic isotonic regression:** Fit a non-decreasing isotonic regression curve $\hat{p}_{\text{cal}} = g_{\text{iso}}(s)$ per `(layer, lead_band)` strictly on past origins $\{t_1, \dots, t_{k-1}\}$, then evaluate $\hat{p}_{\text{cal}}$ out-of-sample on origin $t_k$.

### 4.3 Out-of-sample verification across all 96 cells and reliability curves

Evaluating the legacy raw outlook (`p_outlook`) and the chronological EB + Isotonic calibrated outlook (`p_cal`) on the exact same out-of-sample rows (origins 2 through 12, 114,618 scored rows) delivers a decisive improvement across every single evaluation metric.

| Layer & lead band | Legacy raw skilful cells (out of 12) | Calibrated skilful cells (out of 12) | Calibrated beats raw Brier (out of 12) | Mean Brier raw | Mean Brier calibrated | Relative Brier reduction |
|---|---:|---:|---:|---:|---:|---:|
| Binding · 0-7 days | 2 | **8** | 11 | 0.0158 | 0.0115 | -26.9% |
| Binding · 8-30 days | 2 | **7** | 12 | 0.0165 | 0.0134 | -18.6% |
| Binding · 31-90 days | 2 | **10** | 12 | 0.0135 | 0.0097 | -28.4% |
| Binding · 91-365 days | 3 | **10** | 12 | 0.0102 | 0.0058 | -43.3% |
| **Binding Subtotal (48 cells)** | **9** | **35** | **47 / 48** | **0.0158** | **0.0113** | **-28.4%** |
| Setter · 0-7 days | 2 | **6** | 10 | 0.0884 | 0.0660 | -25.3% |
| Setter · 8-30 days | 0 | **4** | 11 | 0.0878 | 0.0591 | -32.7% |
| Setter · 31-90 days | 1 | **4** | 12 | 0.0832 | 0.0563 | -32.3% |
| Setter · 91-365 days | 2 | **6** | 12 | 0.0791 | 0.0478 | -39.5% |
| **Setter Subtotal (48 cells)** | **5** | **20** | **45 / 48** | **0.0781** | **0.0517** | **-33.9%** |
| **All 96 Cells Combined** | **14 / 96** | **55 / 96** | **92 / 96** | n/a | n/a | n/a |

The reliability curves confirm that systematic over-prediction has been virtually eliminated across both layers:

- **Binding layer Expected Calibration Error (ECE) drops seven-fold, from 3.05 percentage points to 0.43 percentage points.** In the 5% to 10% bin, raw predictions averaged 7.2% against 2.7% realised, whereas calibrated predictions average **6.5% against 6.9% realised**. In the 30% to 50% bin, raw predictions averaged 34.7% against 12.8% realised, whereas calibrated predictions average **37.8% against 39.9% realised**. In the top 70% to 100% bin, raw predictions averaged 78.0% against a severe 4.1% realised (unshrunk rare-family blowups), whereas calibrated predictions average **78.5% against 69.5% realised**.
- **Setter layer ECE drops nearly eight-fold, from 9.00 percentage points to 1.14 percentage points.** Across the key 20% to 30% bin, calibrated predictions track **25.6% against 22.9% realised** (versus 24.4% against 12.2% raw), in the 50% to 70% bin **56.1% against 58.8% realised** (versus 60.0% against 31.2% raw), and in the 70% to 100% bin **95.3% against 95.0% realised** (versus 89.1% against 46.2% raw).

### 4.4 Remaining honest boundaries: why 41 of 96 cells still fail the dual baseline gate

Intellectual honesty requires explaining why 55/96 skilful cells (including 35/48 binding cells and 92/96 raw-Brier wins) is a genuine step forward rather than a claim of solved long-range outage forecasting. Most of the 41 cells that still do not clear both system-normal and last-year baselines sit inside the setter layer (28 of 48 setter cells) and on HVDC links (Directlink and Basslink), where non-generic cable ratings and bidding determine the reported setter equation regardless of AC outage bookings (confirming the Chapter 3 audit of Flagship Edition A). On the binding layer across AC interconnectors, however, chronological EB + isotonic calibration turns a biased raw screening table into a well-calibrated, Brier-skilful risk signal across 35 of 48 cells.

### 4.5 Worked calibration audit: how a single 60-day booking transforms across stages

To trace the exact numerical mechanics of the calibration pipeline, follow a typical QNI reverse booking submitted 60 days ahead (inside the 31-to-90-day lead band) whose inferred outage family carries a raw historical conditional binding probability of $p_{\text{raw}} = 0.40$ and a family-inference confidence of $p_{\text{fam}} = 0.65$, while the system-normal baseline binding probability on the same equation is $p_{\text{norm}} = 0.02$.

1. **Stage 1 (Lead-band occurrence-hazard scaling):** Across strictly prior origins, bookings in the 31-to-90-day binding bucket experience roughly one-third withdrawal plus substantial rescheduling drift, yielding an empirical hazard scale near $h \approx 0.42$. Multiplying $p_{\text{raw}}$ by $h$ immediately discounts the raw 40% claim down to $p_{\text{adj}} = 0.168$.
2. **Stage 2 (Empirical-Bayes family shrinkage):** Suppose the inferred family appeared in $n_f = 15$ prior bookings with an empirical binding rate of $\bar{y}_f = 0.20$, while the broader QNI reverse 31-to-90-day cell prior sits at $\mu_{\text{cell}} = 0.04$. With pseudo-count $m_0 = 25$, the shrunk Empirical-Bayes family rate is $(15 \times 0.20 + 25 \times 0.04) / (15 + 25) = 0.100$. Blending $p_{\text{adj}}$ and $\hat{y}^{\text{EB}}_f$ weighted by $0.45 \times p_{\text{fam}} = 0.2925$ yields $0.2925(0.168) + 0.7075(0.100) = 0.120$, and anchoring lightly to $p_{\text{norm}}$ yields a composite pre-isotonic score $s = 0.82(0.120) + 0.18(0.020) = 0.102$.
3. **Stage 3 (Monotonic isotonic projection):** Passing $s = 0.102$ through the monotonic isotonic curve fitted strictly on prior origins maps the booking to a final out-of-sample calibrated binding probability near $\hat{p}_{\text{cal}} \approx 0.11$, closely matching realised 31-to-90-day binding frequency rather than the legacy 40% false alarm.

Because every parameter ($h$, $\mu_{\text{cell}}$, $\bar{y}_f$, and the isotonic step function) is re-estimated strictly from past issue origins $t_1, \dots, t_{k-1}$ before predicting origin $t_k$, the resulting 28.4% binding Brier reduction, 33.9% setter Brier reduction, and seven-fold drop in binding ECE are completely free of hindsight leakage and represent genuinely achievable walk-forward performance.

Part III now zooms from system-wide NOS outage families down to the asset level: all 50 individual transmission lines, hierarchical corridor pooling, and dedicated forensic deep dives on Capital-Canberra Line 6 and Dapto-Marulan Line 8.

## Chapter 5 · Hierarchical Corridor Pooling Across Fifty Transmission Lines

Asset-specific outage research faces an unavoidable statistical dilemma: the transmission lines that matter most to regional security and market risk rarely fail or go on outage dozens of times per year. Across the 50-line transmission cohort audited in the prior line-outage campaign (631 verified outage events spanning NSW, VIC, QLD, SA, and TAS), individual lines range from 35 to 69 events (such as Alcoa Portland-Heywood 500 kV Line 2 and Mt Beauty-West Kiewa 220 kV) down to just 2 to 5 events (such as Capital-Canberra Line 6 with 2 events, Stockdill-Canberra 3C with 4 events, and Cowra-Forbes 998 with 5 events).

In the legacy line-outage study, enforcing ultra-strict exact-matching gates on binary extreme-price indicators (`spike300`, `tail99`) left almost every mainland line with withheld estimates (`match_rate = 0.0`, `effect = NaN`), reducing the deliverable to descriptive tables without quantitative cross-line ranking. Conversely, relying on unshrunk raw averages for low-event lines invites severe small-sample noise: if one of a line's four outages happened to coincide with a $17,500/MWh evening scarcity spike, its raw average price effect jumps to +$398/MWh even if the line itself barely moved interconnector headroom.

### 5.1 Electrically coherent regional corridors and Empirical-Bayes partial pooling

To achieve complete 50-line analytical coverage while respecting finite-sample uncertainty, we replace binary withheld screens with continuous same-season, same-time-of-day matched outcomes across all 50 lines (regional price delta in $/MWh, primary interconnector worst directional capacity delta in MW, primary border spread delta in $/MWh, and clean binding marginal value severity excluding synthetic linear-programme penalty rows above $30,000/MWh), and then apply hierarchical Empirical-Bayes (James-Stein) partial pooling inside eight electrically coherent regional corridors.

Within each corridor $c$, every line $i$ with raw continuous estimate $\hat{\theta}_i$ and day-clustered standard error $s_i$ (scaled by finite-sample degrees-of-freedom factor $\sqrt{\max(1, 6/n_i)}$ for low-event lines) is shrunk toward the inverse-variance-weighted corridor mean $\mu_c$:

$$\hat{\theta}^{\text{EB}}_i = w_i \hat{\theta}_i + (1 - w_i) \mu_c, \qquad w_i = \frac{\tau_c^2}{\tau_c^2 + s_{i,\text{adj}}^2}$$

where $\tau_c^2$ is the empirical between-line variance within corridor $c$. Lines with high event counts and tight standard errors receive weights $w_i$ of 0.85 to 0.99 and retain their individual physical signature; noisy low-event lines receive smaller weights and borrow statistical strength cleanly from their immediate electrical neighbours on the same regional backbone.

### 5.2 Eight-corridor risk hierarchy across the NEM

Aggregating the 50 monitored transmission lines into eight regional corridors reveals a sharp physical separation between corridors that slash interconnector capacity deepest and corridors that separate regional prices widest.

| Regional transmission corridor | Lines | Total events | Outage hours | Mean EB Cap delta (MW) | Mean EB Spread delta ($/MWh) | Mean EB Regional price delta ($/MWh) | Total binding intervals | Max clean median \|MV\| ($/MWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SA Heywood & Mid-North 275 kV | 6 | 94 | 2,992 | **-179** | **+$17.4** | -$4.1 | 18,564 | $1,218 |
| VIC Metro & Latrobe 500 kV | 5 | 114 | 420 | -174 | -$17.5 | -$30.8 | 0 | n/a |
| NSW Central & Sydney Ring | 4 | 45 | 4,006 | -157 | **+$16.4** | **+$29.2** | 2,293 | $1,084 |
| NSW Northern & QNI 330 kV | 5 | 58 | 1,939 | -156 | +$3.9 | -$12.4 | 7,577 | $1,222 |
| NSW Southern & Snowy 330/500 kV | 11 | 67 | 4,855 | -125 | -$15.5 | -$33.8 | 10,971 | $1,383 |
| TAS North-South 220 kV | 8 | 82 | 2,194 | -104 | -$28.2 | -$2.1 | 78 | $155 |
| VIC Western & Border 220/500 kV | 2 | 43 | 499 | -81 | -$14.9 | -$14.9 | 2,635 | $1,084 |
| QLD Central & Southern 275 kV | 9 | 128 | 5,756 | -70 | +$0.1 | -$6.5 | 20,986 | $1,178 |

Three structural takeaways stand out from the eight-corridor synthesis:

1. **SA Heywood & Mid-North 275 kV is the single sharpest physical and spread-widening corridor (-179 MW, +$17.4/MWh spread):** Anchored by Tailem Bend-South East 275 kV Lines 1 and 2 (`S_EAST/LINE/TABSES_1` with 24 events and -263 MW EB cap drop / +$63.9/MWh EB spread widening; `S_EAST/LINE/TABSES_2` with 18 events and -279 MW EB cap drop), this six-line South Australian spine logged 18,564 binding constraint intervals with clean median shadow prices up to $1,218/MWh.
2. **NSW Central & Sydney Ring and NSW Northern & QNI 330 kV drive positive regional price risk:** Across NSW Central & Sydney Ring (4 lines, 4,006 outage hours), Empirical-Bayes pooled regional prices average **+$29.2/MWh** and border spreads **+$16.4/MWh**, while NSW Northern & QNI 330 kV (led by `ARMIDALE/LINE/86` at -184 MW EB cap drop / +$19.1/MWh spread and `ARMIDALE/LINE/87` at -187 MW EB cap drop) averages -156 MW capacity contraction across 7,577 binding intervals.
3. **NSW Southern & Snowy 330/500 kV carries the highest binding marginal value ($1,383/MWh) alongside mild-season scheduling bias:** Across 11 Southern NSW lines (4,855 outage hours and 10,971 binding intervals), average EB capacity drops reach **-125 MW**, led by `MARULAN/LINE/5` (-219 MW EB cap drop, +$18.6/MWh EB spread widening, 5,941 binding intervals) and `CANBERRA/LINE/07` (-163 MW EB cap drop, 2,136 binding intervals). Notice that the corridor mean regional price delta is negative (-$33.8/MWh), reflecting the strong shoulder-season and daytime maintenance scheduling effect discussed in Chapter 1, even while individual binding constraints carry $1,000 to $1,383/MWh shadow prices when evening load or wind swings collide with the outage.

### 5.3 How Empirical-Bayes shrinkage rescues noisy outliers

Comparing raw single-line estimates against Empirical-Bayes corridor-pooled estimates across all 50 transmission lines demonstrates exactly why hierarchical shrinkage outperforms both unshrunk point estimates and wholesale data withholding.

Two concrete examples from the 50-line register prove the point:
- **`COWRA/LINE/998` (5 events, 46.3 outage hours):** Because one single 46-hour window coincided with a $17,500/MWh NSW price spike, its raw regional price effect surged to **+$397.6/MWh** (with a large day-clustered standard error of $474.1/MWh) and its raw VNI capacity delta hit -482 MW. Empirical-Bayes pooling automatically assigns a low 2.7% weight to the noisy price spike, shrinking it to a realistic **+$19.7/MWh**, while keeping a 63.3% weight on the much tighter capacity drop (**-355 MW**).
- **`STOCKDIL/LINE/3C` (4 events, 29.1 outage hours):** One $17,500/MWh spike inflated its raw NSW price effect to **+$120.0/MWh** (SE $116.0/MWh) and raw capacity drop to -488 MW (SE 127.9 MW). Corridor pooling assigns just 5.4% price weight and 33.5% capacity weight, pulling the estimate cleanly back to **-$39.0/MWh** and **-236 MW**.
- By contrast, high-precision, multi-event backbone lines such as `S_EAST/LINE/TABSES_1` (24 events, 91.0% capacity weight, -263 MW EB vs -269 MW raw) and `MARULAN/LINE/5` (11 events, 94.8% capacity weight, -219 MW EB vs -225 MW raw) barely move at all, preserving their exact asset-specific physical signatures.

Use the searchable 50-line directory below to inspect every line's region, corridor, event count, raw versus Empirical-Bayes pooled capacity drop, spread delta, and maximum clean binding marginal value.

Chapter 6 now zooms directly into the two mandatory focus assets inside the Southern NSW 330 kV corridor: Capital-Canberra Line 6 and Dapto-Marulan Line 8.

## Chapter 6 · Forensic Deep Dives: Capital-Canberra Line 6 and Dapto-Marulan Line 8

Two specific 330 kV transmission lines in southern New South Wales have drawn sustained operational scrutiny from NEM trading desks: Capital Wind Farm to Canberra Line 6 (`CANBERRA/LINE/6`) and Dapto to Marulan Line 8 (`DAPTO/LINE/8`). Both lines sit directly on the main 330 kV cut-plane connecting Snowy Hydro, the Canberra-Yass-Marulan renewable cluster, and the Sydney-Wollongong load centre. Yet in the legacy single-line study, ultra-strict exact-matching gates withheld quantitative estimates for both assets, leaving desks with descriptive narratives rather than calibrated risk numbers.

Placing Line 6 and Line 8 inside the hierarchical Southern NSW & Snowy 330/500 kV corridor alongside their immediate physical neighbours (`MARULAN/LINE/5`, `CANBERRA/LINE/07`, and `STOCKDIL/LINE/3C`) resolves both the small-sample problem on Line 6 and the sharp VNI flow-reversal mechanics on Line 8.

### 6.1 Side-by-side Southern NSW 330 kV corridor benchmark

| Transmission line | Events (withdrawn) | Outage hours | Raw Cap delta (MW) | EB Cap delta (MW, weight) | Raw Price delta ($/MWh) | EB Price delta ($/MWh) | EB Spread delta ($/MWh) | Binding intervals | Max clean \|MV\| ($/MWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CANBERRA/LINE/6` (Capital-Canberra 6) | 2 (5) | 390.4 | -129 | -121 (61%) | -$74.24 | -$72.24 | -$12.15 | 1,185 | $263 |
| `DAPTO/LINE/8` (Dapto-Marulan 8) | 8 (4) | 232.1 | -49 | -57 (87%) | -$30.46 | -$31.66 | -$35.36 | 267 | $1,383 |
| `MARULAN/LINE/5` (Yass-Marulan 5) | 11 (5) | 1,480.8 | -225 | -219 (95%) | +$31.35 | -$3.82 | +$18.58 | 5,941 | $1,280 |
| `CANBERRA/LINE/07` (Lwr Tumut-Canberra 07) | 7 (8) | 567.8 | -167 | -163 (93%) | -$13.49 | -$17.93 | -$2.26 | 2,136 | $1,095 |
| `STOCKDIL/LINE/3C` (Stockdill-Canberra 3C) | 4 (2) | 29.1 | -488 | -236 (33%) | +$120.01 | -$38.97 | +$4.28 | 156 | $1,101 |

### 6.2 Capital-Canberra Line 6: why two shoulder-season events require corridor pooling

Capital Wind Farm to Canberra Line 6 illustrates the exact danger of drawing strong commercial conclusions from an $n = 2$ event sample. Across the two-year study window, seven NOS outage bookings were submitted for Line 6, of which five (71%) were withdrawn and only two actually executed, totalling 390.4 outage hours (roughly 16.3 calendar days combined).

Inspecting the realised five-minute telemetry and matched controls during those two executed windows yields four precise findings:

1. **Modest physical VNI limit compression during observed outages:** During Line 6's two executed windows, VNI mean forward limit dipped gently from 860 MW before to 823 MW during (recovering to 803 MW after), while VNI reverse capacity contracted more noticeably from 422 MW before to 312 MW during (-110 MW shift, rebounding to 581 MW after). Mean VNI flow eased from +214 MW northward before the outage to +156 MW during.
2. **Continuous matched and EB-pooled capacity delta (-121 MW):** Against same-season, same-time-of-day non-outage half-hours (781 matched half-hours), Line 6 recorded a raw VNI forward capacity delta of -129 MW (day-clustered SE 51.4 MW). Because $n = 2$ triggers the finite-sample degrees-of-freedom penalty inside the Southern NSW corridor, Empirical-Bayes pooling assigns a 61.0% weight to Line 6's own capacity delta and 39.0% weight to the Southern NSW corridor prior (-125 MW), producing a stabilised estimate of -121 MW.
3. **Benign shoulder-season price realisation (-$72.24/MWh EB, max price $311.91/MWh):** Neither of Line 6's two executed outages coincided with an extreme New South Wales scarcity event (maximum realised NSW price across all 390.4 hours was just $311.91/MWh, averaging $97.99/MWh). Three associated constraint equations bound across 1,185 intervals with a moderate maximum clean median shadow price of $262.86/MWh.
4. **Operational verdict for Line 6:** Line 6 is not a benign zero-risk wire, nor is it a proven standalone price-spike trigger. With 71% historical withdrawal and only two mild-season executions on record, desks should price a future Line 6 booking near the Southern NSW 330 kV corridor prior (-120 to -125 MW VNI capacity risk) while monitoring whether the booking overlaps with Marulan Line 5 (`MARULAN/LINE/5`) or Lower Tumut-Canberra Line 07 (`CANBERRA/LINE/07`), where N-1-1 southern-corridor compounding (Chapter 3) immediately amplifies exposure.

### 6.3 Dapto-Marulan Line 8: severe VNI forward-limit collapse and 571 MW flow reversal

Dapto to Marulan Line 8 presents a sharper and far better-observed physical signature. Over the two-year study window, 12 bookings were submitted, of which 4 were withdrawn (33%) and 8 distinct events executed across 232.1 outage hours (464 matched half-hours).

The most distinctive empirical signature of Line 8 appears directly in the event-aligned VNI telemetry (`before` versus `during` versus `after` across all 8 executed outages):

- **VNI forward export limit collapsed by 440 MW during execution:** Mean VNI forward export limit fell from 600.2 MW before the outage down to 160.2 MW during Line 8 execution, before snapping straight back to 636.9 MW after restoration.
- **VNI physical flow reversed by 571 MW across the border:** Mean VNI dispatch flow flipped from +214.9 MW northward (VIC to NSW) before the outage to -356.3 MW southward (NSW to VIC) during Line 8 execution, recovering to +108.2 MW northward after restoration. Meanwhile, VNI reverse capacity expanded from 434.0 MW before to 657.6 MW during.
- **Elevated binding shadow prices during tight windows ($1,382.59/MWh median |MV|):** Although Line 8's 8 outages were scheduled largely during moderate daytime demand periods (keeping average event NSW price at $45.42/MWh, max $317.33/MWh, EB price delta -$31.66/MWh at 93% weight, and EB spread delta -$35.36/MWh), whenever its three active constraint equations bound (267 binding intervals), their clean median marginal value reached $1,382.59/MWh, the highest binding shadow-price intensity of any line in the entire Southern NSW 330 kV corridor.

### 6.4 Physical grid geometry explaining why Line 8 flips VNI flow while Line 6 softens it

Why do two 330 kV lines sitting less than 120 kilometres apart inside the exact same Southern NSW transmission backbone produce such distinct VNI signatures? Tracing the physical topology from Snowy Hydro to Sydney provides the exact engineering explanation.

Capital Wind Farm to Canberra Line 6 sits on the inland western leg feeding the Canberra sub-ring alongside Lower Tumut-Canberra Line 07 and Stockdill-Canberra 3C. When Line 6 opens under intact neighbouring lines, power generated in the Snowy Mountains and Victoria can still bypass Canberra along the primary eastern 330 kV trunk via Yass and Marulan toward Sydney, as well as parallel feeds into Canberra itself. Consequently, VNI northward transfer eases moderately (-121 MW EB) without forcing wholesale reversal across the Victoria to New South Wales border.

Dapto to Marulan Line 8, by contrast, sits directly on the coastal southern gateway carrying power from the Marulan 330 kV switching hub into the Illawarra-Dapto-Sydney South metropolitan ring. Removing Line 8 throttles the main southern thermal outlet out of Marulan toward Sydney. Because Snowy Hydro generation and southern NSW renewables inject immediately upstream of Marulan, throttling the Marulan-to-Dapto exit immediately backs power up into the Snowy-Yass-Wagga cut-plane. To avoid overloading remaining Marulan-Bannaby-Sydney circuits under an N-1 contingency, NEMDE clamps VNI northward export ceilings down from 600 MW to 160 MW and pushes surplus southern NSW energy southward back into Victoria (-356 MW mean VNI flow during execution). For a VIC to NSW SRA holder, that 571 MW flow reversal is an acute directional hazard: whenever NSW clears even modestly above Victoria during a Line 8 window, southward loop flow converts positive settlement carry into negative residue.

> [!TAKEAWAY] Commercial Distinction Between Line 6, Line 8, and Marulan Line 5
> Within the Southern NSW 330 kV triangle, Marulan Line 5 (`MARULAN/LINE/5`, 11 events, 1,481 hours, -219 MW EB cap drop, +$18.58/MWh EB spread widening, 5,941 binding intervals) is the primary sustained VNI spread-widening and SRA-eroding bottleneck (`N-MNYS_5_WG_CLOSE` cost -$573k/day in Chapter 2). Dapto-Marulan Line 8 (`DAPTO/LINE/8`, 8 events) triggers an immediate 440 MW VNI forward limit collapse and a 571 MW southward flow reversal with $1,383/MWh binding shadow prices whenever active, making it a sharp directional flow-reversal and negative-residue hazard for long VIC-to-NSW SRA positions even when headline NSW spot prices stay moderate. Capital-Canberra Line 6 (`CANBERRA/LINE/6`, 2 events) remains data-scarce and must be evaluated via Southern NSW corridor pooling (-121 MW EB) plus concurrent N-1-1 overlap screening.

Chapter 7 translates all four analytical pillars of Flagship Edition B into a single operational forward-outage screening workflow and exposes the calibrated live forward watchlist.

## Chapter 7 · Operational Outage-Risk Screening Playbook and Calibrated Watchlist

Converting retrospective NOS attribution and 50-line corridor pooling into day-to-day trading-desk and portfolio-risk discipline requires replacing ad-hoc outage spreadsheets with a structured four-step screening protocol. Every step below maps directly to the verified local evidence tables committed alongside this handbook.

### 7.1 Applying the calibrated isotonic map to the live forward NOS book

To demonstrate how chronological probability calibration changes real forward risk decisions, the full-history isotonic calibration map trained across all 12 monthly walk-forward origins (September 2025 to August 2026) was applied directly to the latest retained forward NOS weekly schedule (spanning September 2026 through August 2027, detailed in Appendix B).

The contrast between raw legacy binding probabilities and calibrated binding probabilities is immediate and commercially decisive:

- **QNI reverse (`N>>NIL_964_84_S`, up to -656 MW reduction in late September 2026 and March 2027):** The raw legacy score emits an elevated 83.7% to 84.2% binding probability across 19 to 30 concurrent outages. After discounting for booking withdrawal, early return, and empirical binding frequency, the isotonic calibrated probability drops cleanly to 34.8% to 35.0%, still the highest genuine binding risk on the entire forward board, but priced at a realistic 1-in-3 hazard rather than near-certainty.
- **QNI forward (`N>>NIL_33_34`, up to -570 MW reduction in September to November 2026 and March 2027):** Raw legacy scores of 78.8% calibrate down to 13.5%, alerting the desk to monitor the bookings closely as the 0-to-7-day execution window approaches without prematurely paying up for expensive interstate caps 60 days out.
- **VNI reverse (`N^^V_DTSS_1`, -914 MW max reduction in late September 2026):** Raw legacy score of 61.4% calibrates to 11.9%, reflecting the reality that most distant southern NSW outage bookings either shift out of the peak window or clear without invoking the voltage-stability boundary.

Use the interactive calibrated forward watchlist below to filter upcoming high-risk outage weeks by interconnector and compare raw versus calibrated binding probabilities alongside concurrent outage overlap counts and maximum megawatt reductions.

### 7.2 Four-step desk screening protocol for forward NOS releases

Whenever AEMO publishes a fresh Network Outage Scheduler update, interregional trading and risk desks should evaluate the forward calendar through four sequential gates:

1. **Gate 1 · Lead-horizon withdrawal filter (Chapter 1 and Chapter 4):** Treat bookings beyond 30 days strictly through their calibrated binding probabilities (`p_cal`) rather than raw historical family frequencies. Remember that 31.0% of all NOS bookings are withdrawn before execution and 35% to 48% return early. Escalate hedge adjustments only as bookings survive inside the 0-to-7-day confirmation window where calibrated binding skill reaches 8 of 12 corridor-directions and withdrawal risk collapses.
2. **Gate 2 · Economic SRA direction screen (Chapter 2):** Look up every confirmed constraint-set family in the Supported Outage Family Economic Directory (Chapter 2). Separate SRA-destroying flow clamps (such as `V-MLSY_NOEMTT_R` at -$1.62m/day on Heywood forward, `N-MNYS_5_WG_CLOSE` at -$573k/day on VNI forward, `Q-BRTX1` at -$858k/day on QNI reverse, and `N-LTWG_RADIAL` at -$2.44m/day on Murraylink forward) from SRA-widening bottlenecks (`N-BABU` at +$720k/day on Heywood forward, `V-KG_WE_RC` at +$428k/day on VNI reverse). Never hedge a flow-clamping outage by buying additional SRA units in the clamped direction.
3. **Gate 3 · N-1-1 concurrent overlap alarm (Chapter 3):** Scan each forward calendar week for overlapping bookings within the same electrical choke point (Southern NSW Wagga-Yass-Buronga-Marulan; Northern NSW Armidale-Dumaresq-Koolkhan; South Australia Tailem Bend 275 kV). Whenever two or more relevant families overlap, override linear MW sums with the N-1-1 super-additivity register (Chapter 3), noting that 109 of 338 tested pairs compound by -20 to -776 MW beyond additive expectations.
4. **Gate 4 · Asset-level corridor prior for rare transmission lines (Chapter 5 and Chapter 6):** When a forward NOS release lists a specific high-voltage line with fewer than five historical events (such as Capital-Canberra Line 6 with $n = 2$), never rely on its noisy raw historical average or dismiss it because strict exact-match tables withheld a number. Read its Empirical-Bayes corridor-pooled risk from the 50-line register (Chapter 5), check its binding marginal-value history (for instance, Dapto-Marulan Line 8's $1,383/MWh median `|MV|` and 571 MW VNI flow reversal), and cross-check whether neighbouring lines in the same corridor are booked concurrently.

### 7.3 Integrating outage risk into quarterly SRA bidding and forecasting pipelines

For quarterly Settlement Residue Auction desks preparing bids across Q1 through Q4 tranches, the calibrated outage ledger converts qualitative transmission-maintenance commentary into three quantitative bid adjustments. First, discount expected quarterly transfer volume strictly by the product of calibrated booking binding probability (`p_cal`) and matched daily SRA impact summed across booked calendar weeks, rather than multiplying uncalibrated raw probabilities that overstate expected outage losses by two to three times. Second, apply an explicit tail-risk reserve whenever a forward quarter contains multi-week Southern NSW, Northern NSW, or Tailem Bend N-1-1 overlaps, because 109 concurrent pairs across the NEM exhibit super-additive drops of -150 to -776 MW. Third, for quantitative forecasting teams operating inside the repository's `nemic.experiments` stack, inject NOS features strictly under measured issue-time vintage replay (retaining booking status, lead days, calibrated binding probability, and regional overlap count as-of the forecast origin) so out-of-sample backtests never peek at post-issue booking withdrawals or early returns.

### 7.4 Bridge to Flagship Editions A and C

Flagship Edition A (*Constraint Pressure Atlas v2*) established that 43.5% of all sharp 30-minute contraction megawatts come from active-leader equation switches, while Flagship Edition B has now quantified the economic cost, N-1-1 compounding, and calibrated forward probability of the transmission outages that trigger those switches. Yet one structural change is actively redrawing the entire southern NEM transmission topology and challenging both historical constraint equations and interconnector forecasting models: Project EnergyConnect (`NSW1-SA1`) and the broader limits of long-range interconnector forecasting. Flagship Edition C (*Interconnector Forecasting Verdict, Clustering & Project EnergyConnect v2*) bridges observed EnergyConnect commissioning telemetry directly into the AEMC loop-settlement framework and audits every forecasting model stack across the repository.

## Appendix A · Mathematical Identities and Calibration Formulas

All outage timestamps, control matches, and market panels are aligned to fixed NEM market time (UTC+10, interval-ending) on the half-hourly settlement grid ($T = 35,040$ half-hours covering 1 September 2024 to 31 August 2026).

### A.1 Matched-pair economic attribution and seven-day block bootstrap

For each interconnector $k$, direction $d \in \{\text{forward}, \text{reverse}\}$, and constraint-set family $f$, let $\mathcal{M}_{k,d,f} = \{(t_m, c_m)\}_{m=1}^{M}$ denote the exact set of deduplicated matched treated-control half-hour pairs. The paired directional spread difference and daily-scaled SRA residue difference are:

$$\Delta \pi_m = \pi^{\text{dir}}_{k,d}(t_m) - \pi^{\text{dir}}_{k,d}(c_m), \qquad \Delta R^{\text{day}}_m = 48 \cdot \Big(R^{\text{net}}_{k,d}(t_m) - R^{\text{net}}_{k,d}(c_m)\Big)$$

where $R^{\text{net}}_{k,d}(h) = \sum_{s \in h} \big(R^{+}_{k,d,s} + R^{-}_{k,d,s}\big)$ sums settled five-minute positive and negative directional SRA residues across the six five-minute dispatch intervals inside half-hour $h$. Point estimates equal sample means over $\mathcal{M}_{k,d,f}$. To preserve multi-day outage autocorrelation, treated dates are partitioned into seven-day contiguous calendar blocks $\{B_1, \dots, B_G\}$ and resampled with replacement ($B = 150$, seed 42) via exact cluster-sum weighting:

$$\bar{\Delta}^{(b)} = \frac{\sum_{g=1}^{G} S_{u^{(b)}_g}}{\sum_{g=1}^{G} n_{u^{(b)}_g}}$$

yielding the 2.5th and 97.5th percentile 95% block-bootstrap confidence intervals.

### A.2 Strictly chronological Empirical-Bayes + hazard + isotonic calibration

Let $t_1 < t_2 < \dots < t_{12}$ be the twelve monthly NOS outlook issue origins. For each out-of-sample test origin $t_k$ ($k \ge 2$), let $\mathcal{D}_{<k}$ denote strictly prior origins $\{t_1, \dots, t_{k-1}\}$. Within $\mathcal{D}_{<k}$:

1. Lead-band occurrence hazard scaling factor per `(layer, lead_band)`:
   $$h_{\ell, b} = \text{clip}\!\left(\frac{\bar{y}_{\ell,b} + 0.01}{\bar{p}_{\text{raw},\ell,b} + 0.01},\; 0.15,\; 1.20\right)$$
2. Empirical-Bayes family binding rate shrunk toward `(layer, link, direction, lead_band)` prior $\mu_{\text{cell}}$ ($m_0 = 25$):
   $$\hat{y}^{\text{EB}}_{f} = \frac{n_f \bar{y}_f + m_0 \mu_{\text{cell}}}{n_f + m_0}$$
3. Pre-isotonic composite score incorporating family inference certainty $p_{\text{fam}}$ and system-normal anchor $p_{\text{norm}}$:
   $$s_i = \text{clip}\!\left(0.82 \cdot \big[0.45 p_{\text{fam},i} \cdot \text{clip}(p_{\text{raw},i} h_{\ell,b}, 0, 1) + (1 - 0.45 p_{\text{fam},i})\hat{y}^{\text{EB}}_{f}\big] + 0.18 p_{\text{norm},i},\; 0,\; 1\right)$$
4. Monotonic isotonic map $\hat{g}_{\ell,b} = \arg\min_{g \text{ non-decreasing}} \sum_{j \in \mathcal{D}_{<k, \ell, b}} (y_j - g(s_j))^2$, applied strictly out-of-sample on origin $t_k$ as $\hat{p}_{\text{cal},i} = \hat{g}_{\ell,b}(s_i)$.

Cell-level Brier score and Expected Calibration Error (ECE) over bins $B_1, \dots, B_K$ are:

$$\text{Brier} = \frac{1}{N}\sum_{i=1}^{N} (\hat{p}_i - y_i)^2, \qquad \text{ECE} = \sum_{r=1}^{K} \frac{|B_r|}{N} \left|\bar{p}_{B_r} - \bar{y}_{B_r}\right|$$

### A.3 N-1-1 concurrent super-additivity

For any two families $(A, B)$ with non-empty disjoint and overlapping sets ($|A \cap B| \ge 24$, $|A \setminus B| \ge 24$, $|B \setminus A| \ge 24$ half-hours) on link $k$ and direction $d$, let $C_{k,d}(h)$ be the half-hour tight directional capacity (minimum across the six five-minute intervals):

$$\Delta C_A = \bar{C}_{A \setminus B} - \bar{C}_{\overline{A \cup B}}, \qquad \Delta C_B = \bar{C}_{B \setminus A} - \bar{C}_{\overline{A \cup B}}, \qquad \Delta C_{A \cap B} = \bar{C}_{A \cap B} - \bar{C}_{\overline{A \cup B}}$$

$$S_{A,B} = \Delta C_{A \cap B} - (\Delta C_A + \Delta C_B)$$

### A.4 Hierarchical Empirical-Bayes corridor partial pooling

Within each of the eight regional transmission corridors $c$, let $\hat{\theta}_i$ be line $i$'s continuous matched outcome (season x half-hour-of-day baseline subtracted) with day-clustered standard error $s_i$ and verified event count $n_i$. Define the finite-sample adjusted variance $v_i = s_i^2 \cdot \max(1, 6 / n_i)$, precision-weighted corridor prior $\mu_c$, and empirical between-line variance $\tau_c^2$:

$$\mu_c = \frac{\sum_{i \in c} \hat{\theta}_i / v_i}{\sum_{i \in c} 1 / v_i}, \qquad \tau_c^2 = \max\!\left(\text{Var}_{i \in c}(\hat{\theta}_i) - \frac{1}{|c|}\sum_{i \in c} v_i,\; 0.30\,\text{Var}_{i \in c}(\hat{\theta}_i),\; 4.0\right)$$

$$w_i = \frac{\tau_c^2}{\tau_c^2 + v_i}, \qquad \hat{\theta}^{\text{EB}}_i = w_i \hat{\theta}_i + (1 - w_i)\mu_c$$

## Appendix B · Data Schema, NOS Lineage, and Reproducible Build Commands

All raw AEMO Network Outage Scheduler (NOS) files, local parquet caches, and repository module filenames are consolidated in this technical appendix while preserving clean institutional prose in Chapters 1 through 7.

### B.1 Local archive inputs (zero new NEMWEB downloads)

| Analytical module | Local repository path | Upstream source & coverage |
|---|---|---|
| C7a matched pairs (6 links) | `data/nos_binding_v1/pairs__{VIC1-NSW1,NSW1-QLD1,V-SA,N-Q-MNSP1,V-S-MNSP1,T-V-MNSP1}.parquet` | Exact `kind == 'actual'`, `level == 'K2'` treated-control half-hour matches (`2024-09` to `2026-08`) |
| C7a baseline MW & MV tables | `reports/nos_outage_regime_research_20260924/downloads/{nos_family_effects,nos_binding_marginal_value,nos_booking_reliability}.csv` | Compact audited outputs from `scripts/run_nos_regime.py` and `scripts/run_nos_binding.py` |
| C7b walk-forward outlook panel | `data/nos_binding_v1/outlook/backtest_scored.parquet` | 126,582 scored rows across 12 chronological monthly origins (`2025-09-12` to `2026-08-14`), 2 layers, 4 lead bands, 6 links x 2 directions |
| C7b live forward snapshot | `reports/nos_outage_regime_research_20260924/downloads/{nos_outlook_outages.csv.gz,nos_outlook_weekly.csv}` | Latest forward NOS booking snapshot (`PUBLIC_NETWORK_20260911000007`) |
| C8 family occupancy matrix | `data/nos_regime_v1/family_coverage_30min.parquet` | 35,040 half-hours x 237 constraint-set families across the 24-month panel |
| C9 50-line cohort & events | `reports/line_outage_risk_v1/downloads/{cohort,events,event_summary,mechanism_summary,falsification,interconnector_event_response}.csv` | 50 monitored transmission lines (631 verified outage events) across NSW1, VIC1, QLD1, SA1, TAS1 |
| Regional prices, IC limits & SRA residues | `data/valuation_v2/panel/{prices,interconnectors}.parquet`, `data/valuation_v2/settlement/directional_5min.parquet` | Native five-minute `DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES`, and settled directional SRA residue ledger |

### B.2 Generated compact evidence files (`reports/outage_risk_handbook_v2/evidence/`)

1. `nos_economic_effects.csv` (697 rows): matched `$/MWh` spread, `$/day` SRA residue, 7-day block-bootstrap 95% CIs, MW capacity effects, binding `|MV|`, and `well_supported` flag.
2. `nos_outlook_calibration.csv` (96 rows): per-cell (`layer x lead_band x link x direction`) OOS Brier scores, Brier skill vs normal/last-year, and raw vs calibrated skilful indicators.
3. `nos_reliability_curves.csv` (32 rows): raw vs calibrated reliability curves across 8 probability bins for both binding and setter layers.
4. `nos_live_outlook_calibrated.csv` (150 rows): top forward outage weeks ranked by full-history isotonic-calibrated binding probability.
5. `nos_n11_superadditivity.csv` (338 rows): tested concurrent family pairs across all 6 links with standalone, additive, observed joint, and super-additive MW & spread deltas + 95% CIs.
6. `line_corridor_pooled_risk.csv` (8 rows): hierarchical corridor-level Empirical-Bayes capacity, price, spread, and binding `|MV|` summaries.
7. `line_50_directory.csv` (50 rows): complete 50-line directory comparing raw vs Empirical-Bayes corridor-pooled risk and shrinkage weights.
8. `line_deep_dives_6_8.csv` (5 rows): Southern NSW 330 kV peer benchmark for `CANBERRA/LINE/6` and `DAPTO/LINE/8` including event-aligned VNI flow and limit shifts.
9. `nos_booking_reliability_summary.csv` (12 rows): withdrawal, invocation, start/end drift, early-return, and overrun rates across 6 links x 2 study years.
10. `headline_numbers.json`: 53 single-source-of-truth macro numbers checked by unit tests.

### B.3 Deterministic rebuild and verification commands

```powershell
# 1. Recompute all C7-C9 compact CSVs and headline numbers
python -m nemic.experiments.outage_risk_v2

# 2. Assemble Flagship Edition B self-contained HTML + SHA-256 build manifest
python reports/outage_risk_handbook_v2/build_html.py

# 3. Run Wave 2 unit and accounting-invariant tests
python -m pytest -q tests/test_outage_risk_v2.py

# 4. Run headless Playwright desktop/mobile QA
node reports/outage_risk_handbook_v2/qa_report.cjs
```

## Appendix C · Sources, Methodology Notes, and Scope Qualifications

### C.1 Institutional and repository references

1. **Australian Energy Market Operator (AEMO).** *Network Outage Scheduler (NOS) Operating Procedures and Market Management System Data Model* (booking submission, revision, withdrawal, actual switching timestamps, and constraint-set linkage).
2. **Australian Energy Market Operator (AEMO).** *Settlement Residue Auction (SRA) Rules* (directional pooling of interconnector settlement residues across border pairs and treatment of negative settlement residues).
3. **Efron, B., & Morris, C. (1975).** *Data analysis using Stein's estimator and its generalizations.* Journal of the American Statistical Association, 70(350), 311-319 (foundation for Empirical-Bayes partial pooling across regional transmission corridors).
4. **Zadrozny, B., & Elkan, C. (2002).** *Transforming classifier scores into accurate multiclass probability estimates.* KDD 2002 (monotonic isotonic regression calibration for probabilistic event forecasting).
5. **IC Flow Forecasting Research Programme.** Baseline archived studies preserved untouched on disk: `reports/nos_outage_regime_research_20260924/` and `reports/line_outage_risk_v1/`.
6. **IC Flow Forecasting Research Programme.** Companion Flagship Edition A: *Six-Link Constraint Pressure, Generator Influence, and Contraction Atlas v2* (`reports/constraint_pressure_atlas_v2/Constraint_Pressure_Atlas_v2.html`).

### C.2 Scope qualifications and permitted claims

- **Observational matching versus randomised causation:** Although every NOS family economic estimate pairs treated half-hours strictly against matched non-outage control half-hours and applies seven-day block-bootstrap confidence intervals, transmission maintenance scheduling remains an operational decision conditioned on weather and system security. Estimates represent matched observational attribution rather than randomised causal experiments.
- **Research-only calibrated outlook:** The chronological Empirical-Bayes and isotonic calibration in Chapter 4 demonstrates verified out-of-sample improvement across 11 monthly test origins (`55/96` skilful cells, `92/96` Brier reductions over legacy raw scores). It remains a retrospective research workflow inside `nemic.experiments`, not a deployed or scheduled live outage-alert service.
- **Dispatch-solution limits:** Consistent with all repository standards, AEMO reported interconnector limits are dispatch-solution outputs conditional on simultaneous system dispatch and must not be conflated with static maximum physical transfer ratings.
- **Model-stack isolation:** Flagship Edition B belongs strictly to the `nemic.experiments` outage-research stack and does not modify the original six-interconnector conditional backtest (`run_pipeline.py`), the saved QNI/VNI research bundles, or `nemic.production`.
