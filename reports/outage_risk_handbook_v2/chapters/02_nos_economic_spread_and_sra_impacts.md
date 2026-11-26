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

{{exhibit:b2}}

Three commercial insights jump directly off the matched SRA leaderboard:

1. **Multi-week transmission outages can systematically bleed SRA holders by half a million to $1.6 million per day:** Consider `N-MNYS_5_WG_CLOSE` (Marulan to Yass 330 kV Line 5 outage with Wagga bus closed), one of the largest sustained outage families in the two-year sample (9,345 matched half-hours across 91 treated days and 15 episodes, logging 3,593 binding intervals at a $257/MWh median marginal value). On VNI forward, `N-MNYS_5_WG_CLOSE` reduced median directional capacity by 45 MW while reducing matched daily VNI forward SRA payouts by -$572.6k/day (95% block CI strictly negative: -$1,256k to -$127k/day). Similarly, `V-MLSY_NOEMTT_R` on Heywood forward (4,730 matched half-hours across 42 days) cut Heywood forward capacity by -131 MW and eroded VIC to SA SRA payouts by -$1,624.8k/day (95% block CI strictly negative: -$4,593k to -$112k/day). On QNI reverse, `Q-BRTX1` (238 matched half-hours) slashed QNI southward capacity by -291 MW and cut QLD to NSW SRA payouts by -$858.1k/day (95% block CI strictly negative).
2. **Cross-border spillover outages rival local border outages in dollar impact:** Notice how southern New South Wales 220 kV and 330 kV outage families (`N-BABU`, `N-JNWG_RADIAL`, `N-LTWG_RADIAL`) appear at the very top of the Heywood and Murraylink economic tables. Because the Buronga-Balranald-Darlington Point-Wagga spine forms the northern arc of the southern NEM loop, taking a line out in south-western New South Wales reshapes loop flows into Victoria and South Australia, producing a statistically decisive +$720.5k/day SRA increase on Heywood forward during `N-BABU` (2,915 matched half-hours across 34 days) and a -$2,440.0k/day drop during `N-LTWG_RADIAL` on Murraylink forward.
3. **Directional polarity flips across opposite borders:** The Kerang-Wemen-Red Cliffs 220 kV family (`V-KG_WE_RC`) illustrates why desks must price directional portfolios jointly. During `V-KG_WE_RC`, VNI forward spreads contracted by -$278.9/MWh (-$965.4k/day SRA impact), while VNI reverse spreads widened symmetrically by +$270.8/MWh, delivering a statistically significant +$428.3k/day gain on VNI reverse.

### 2.2 Why capacity drops do not map monotonically to spreads

Plotting every outage family's matched megawatt capacity effect against its matched regional price-spread change confirms that physical limit contraction is a necessary diagnostic rather than a sufficient pricing proxy.

{{exhibit:b3}}

The scatter divides into four operational quadrants:

- **Lower-left quadrant (negative MW, negative spread delta):** Outages that restrict transfer during shoulder-season periods when the sending region was already surplus or that clamp flow before regional scarcity develops, such as `V-MLSY_NOEMTT_R` (-131 MW, -$112.5/MWh) and `Q-BRTX1` (-291 MW, -$44.1/MWh).
- **Upper-left quadrant (negative MW, positive spread delta):** Classic scarcity bottlenecks where cutting transfer capacity directly isolates a high-cost importing region, such as `N-JNWG_RADIAL` on Murraylink forward (-107 MW, +$690.9/MWh).
- **Upper-right quadrant (positive MW, positive spread delta):** Outages on neighbouring corridors or opposite directions that relieve a local parallel loop while simultaneously trapping regional generation elsewhere, lifting both nominal headroom and border spreads (for example, `N-DTSS_11` on QNI reverse at +58 MW and +$84.7/MWh across 3,669 matched half-hours).
- **Near-zero MW band with wide vertical dispersion:** Outages whose average capacity shift over 24 hours is modest (-20 to +20 MW), yet whose binding shadow prices spike sharply during narrow evening-peak windows, generating large dollar swings without showing up in raw median-MW league tables.

> [!WARNING] Interpreting Wide Block-Bootstrap Confidence Intervals on Skewed Spikes
> Wholesale electricity prices in the NEM are heavily right-skewed up to the Market Price Cap. An outage family spanning 9 to 15 treated days where one single evening hit $15,000/MWh can display a very large point-average SRA gain (+$9.7m/day for `N-JNWG_RADIAL` on Murraylink) whose seven-day block-bootstrap 95% CI still crosses zero (-$283k to +$11.3m/day). Desks should therefore always check the `sra_ci_excl_zero` flag and sample days alongside the point estimate rather than extrapolating single-episode price-cap coincidences as repeatable carry.

The searchable directory below enables risk analysts and traders to filter all 260 highest-impact matched NOS outage family-directions by interconnector and sort interactively by daily SRA impact, regional spread shift, megawatt capacity drop, or binding marginal value.

{{interactive:nosEconDirectory}}

### 2.3 Worked SRA P&L anatomy: comparing Marulan Line 5 against Moorabool-Sydenham

To see how physical flow clamping translates directly into daily trading P&L, consider a portfolio holding a 25% share of quarterly VIC to NSW Settlement Residue Auction units during a planned 14-day outage on Marulan to Yass 330 kV Line 5 (`N-MNYS_5_WG_CLOSE`), and contrast it with a 25% share of VIC to SA units during a 14-day Moorabool to Sydenham outage (`V-MLSY_NOEMTT_R`).

Under normal intact spring conditions, VNI forward transfer clears near 750 MW during daytime ramps and 900 MW overnight, collecting positive settlement residue whenever NSW prices clear above Victoria. Once `N-MNYS_5_WG_CLOSE` is invoked, transient stability and thermal constraints on the remaining Snowy to Sydney 330 kV paths (`N::N_MNYS_2` and `V^^N_MNYS_1`, documented in Flagship Edition A) tighten across 9,345 matched half-hours, cutting median forward capacity by 45 MW and collapsing net daily border residue by -$572.6k/day across the pooled VNI forward bucket. For a 25% SRA holder, a two-week execution window represents roughly -$2.0 million in lost or negative settlement carry relative to matched non-outage days, even though a naive headline glance at the -45 MW median capacity reduction might suggest only a minor nuisance. The reason the dollar impact is large relative to the median MW shift is timing: the 3,593 binding intervals inside `N-MNYS_5_WG_CLOSE` carry a $257/MWh median shadow price and concentrate precisely in the high-spread hours when NSW imports are needed most, while counter-price loop flows during midday solar peaks erode the rest of the day's accrual.

On VIC to SA during `V-MLSY_NOEMTT_R`, the volume-starvation effect is even sharper. Removing a primary 500 kV feeder west of Melbourne cuts Heywood forward capacity by -131 MW across 4,730 matched half-hours (42 treated days), compressing both transfer volume and with-price spread capture for a combined -$1,624.8k/day pooled reduction (95% block CI strictly negative: -$4,593k to -$112k/day). A desk holding 25% of VIC to SA SRA units across a two-week execution window faces an expected -$5.7 million draw relative to matched controls. Critically, the exact opposite occurs during `N-BABU` (Balranald to Buronga 220 kV outage in south-western New South Wales): instead of starving Heywood flow, cutting the northern 220 kV bypass routes additional transfer pressure across the Victoria to South Australia cut-plane while widening the SA minus VIC spread by +$45.8/MWh, adding +$720.5k/day (95% block CI strictly positive) to the pooled VIC to SA SRA bucket.

These worked comparisons establish a practical trading principle: desks cannot map outage risk using a single scalar "MW lost" column. Every forward booking must be tagged with its economic polarity (SRA-expanding bottleneck, volume-starving flow clamp, or counter-price loop-flow trap) before sizing quarterly SRA bids or regional cap swaps.

Evaluating single outage families in isolation still leaves out one of the most dangerous operational realities on the transmission grid: what happens when two planned or forced outages occur at the exact same time? Chapter 3 measures that N-1-1 compounding risk directly.
