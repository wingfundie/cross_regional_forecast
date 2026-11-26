## Chapter 6 · Cross-Link Contraction Cascades and NRM Clamping

Interconnectors in the NEM do not operate as six independent pipes. They form a long, weakly meshed north-to-south alternating-current spine from northern Queensland to South Australia, braced by parallel HVDC links and linked across Bass Strait to Tasmania. When a transmission outage invokes a constraint set in southern New South Wales or western Victoria, or when a synoptic weather front sweeps wind and solar output across state borders, limit contractions rarely stay confined to a single corridor. At the same time, when regional prices invert against physical loop flows, AEMO's automated Negative Residue Management (NRM) system and forced-flow constraints clamp transfer ceilings below zero, turning physical congestion into direct financial losses for settlement-residue holders.

This chapter maps the complete 6x6 cross-link contraction cascade matrix within a plus-or-minus 30-minute co-occurrence window and isolates the exact share of forced-negative limits and negative settlement residues attributable to counter-price flows and explicit NRM clamping.

### 6.1 The six-by-six contraction cascade matrix

To test whether sharp contractions cluster across borders above random chance, every five-minute interval $t$ on each link $A$ was marked as an active contraction onset window if link $A$ logged a sharp contraction in either direction within $[t - 30\text{ min}, t + 30\text{ min}]$. For each ordered pair $(A, B)$, we compute the conditional probability $P(B \text{ contracts within } \pm 30\text{ min} \mid A \text{ contracts})$ and divide it by link $B$'s unconditional 60-minute window occupancy baseline to obtain the cascade lift ratio. A lift ratio of $1.00\times$ indicates complete statistical independence; values meaningfully above $1.00\times$ quantify genuine multi-corridor contagion.

{{exhibit:a7}}

| Triggering link | Co-contracting link | Conditional probability (%) | Baseline occupancy (%) | Cascade lift ratio | Primary physical coupling mechanism |
|---|---|---:|---:|---:|---|
| QNI | Directlink | 53.1% | 28.5% | **1.86x** | Shared QLD-NSW border equations, northern NSW thermal sets |
| Directlink | QNI | 53.7% | 28.9% | **1.86x** | Parallel MNSP saturation and shared border stability bounds |
| Heywood | Murraylink | 44.9% | 27.6% | **1.63x** | Shared VIC-SA cut-plane, western VIC 220 kV voltage sets |
| VNI | Heywood | 46.8% | 29.2% | **1.60x** | Southern-ring Snowy/western VIC solar & wind loop flows |
| Heywood | VNI | 46.2% | 29.0% | **1.59x** | Victorian export swing and shared 220/330 kV cut-planes |
| Murraylink | Heywood | 46.1% | 29.2% | **1.58x** | Riverland and North West VIC voltage/thermal co-binding |
| VNI | QNI | 44.8% | 28.9% | **1.55x** | NSW spine dispatch shifts (Snowy hydro, Sydney load swings) |
| VNI | Directlink | 41.9% | 28.5% | **1.47x** | NSW-wide constraint sets and Tumut/northern NSW overlap |
| VNI | Murraylink | 38.9% | 27.6% | **1.41x** | Shared south-west NSW solar (Limondale, Darlington Pt, Sunraysia) |
| Heywood | Basslink | 30.4% | 22.6% | **1.34x** | Victorian regional surplus/deficit rebalancing across Bass Strait |
| Basslink | Murraylink | 36.7% | 27.6% | **1.33x** | Victorian west-coast wind and statewide net-demand swings |
| QNI | Basslink | 25.6% | 22.6% | **1.13x** | Minimal direct electrical coupling (diurnal common factor only) |

Three operational tiers of cross-link contagion stand out cleanly:

1. **Parallel border twins (1.58x to 1.86x lift):** The tightest coupling in the NEM connects **QNI and Directlink** (**53.1%** conditional probability, **1.86x** lift) and **Heywood and Murraylink** (**44.9%** to **46.1%**, **1.58x to 1.63x** lift). More than half of all QNI sharp contractions coincide within half an hour with a sharp contraction on Directlink, confirming at the dynamic episode level what Chapter 2 established in static tight-headroom rates.
2. **The Victorian-NSW-SA southern triangle (1.41x to 1.60x lift):** Contractions on **VNI** spill forcefully into **Heywood** (**46.8%** probability, **1.60x** lift) and **Murraylink** (**38.9%**, **1.41x** lift), while Heywood contractions reflect back into VNI at **46.2%** (**1.59x** lift). The physical conduit is clear: the south-western New South Wales and north-western Victorian renewable energy zone (Limondale, Sunraysia, Darlington Point, Kiamal, and Wemen solar farms, plus Murra Warra wind and Kerang/Buronga 220 kV lines) sits directly on the shared equations that govern VNI, Heywood, and Murraylink simultaneously. When a major transmission line such as Bundey to Buronga (6F) or Wagga to Lower Tumut (051) trips or goes on outage, or when midday solar ramps across the Mallee and Riverina, all three corridors contract together.
3. **Spine-wide NSW coupling versus Bass Strait attenuation (1.13x to 1.55x lift):** VNI and QNI show strong spine-wide coupling (**44.8%** probability, **1.55x** lift) because Snowy hydro (Tumut 3 and Upper Tumut) and New South Wales thermal/renewable swings enter constraint equations on both NSW borders simultaneously. By contrast, coupling between geographically distant ends of the market (QNI to Basslink at **1.13x** lift, Directlink to Basslink at **1.10x** lift) decays nearly to the shared diurnal baseline, confirming that the lift metric is capturing genuine electrical topology rather than a mere time-of-day artefact.

> [!TAKEAWAY] Portfolio Risk Implication for Multi-Border SRA Books
> A trading desk holding long SRA portfolios across VNI, Heywood, and QNI does not hold three independent directional transfer options. Under southern-ring stress, VNI and Heywood contract within the same 30-minute window at 1.60x the baseline rate, and VNI and QNI co-contract at 1.55x. Stress-testing interregional hedge portfolios requires joint multi-link contraction scenarios rather than independent single-corridor shocks.

### 6.2 Forced-negative limits, counter-price flow, and NRM clamping attribution

When a directional capacity limit drops below zero ($U_t < 0$ or $L_t < 0$), the dispatch engine is no longer merely capping transfer; it is forcing flow in the opposite direction. In market commentary, forced-negative limits are routinely conflated with AEMO's automated Negative Residue Management (NRM) clamping. Auditing every forced-negative interval across all six interconnectors against concurrent counter-price flow status, explicit NRM/ramp setter equations, and settled five-minute negative SRA residues demonstrates that NRM clamping is only half of the story, and that the dominant mechanism differs radically between VNI and Heywood.

| Link & direction | Forced intervals (24m) | Forced share (%) | Counter-price share of forced (%) | Explicit NRM / ramp setter share of forced (%) | Total 24m neg. SRA residue ($m) | Neg. SRA residue during forced intervals ($m) |
|---|---:|---:|---:|---:|---:|---:|
| VNI forward (forces NSW to VIC) | 26,949 | 12.8% | **82.7%** | 0.5% | -$98.5m | **-$97.4m** |
| VNI reverse (forces VIC to NSW) | 11,205 | 5.3% | 27.9% | 12.3% | -$4.1m | -$3.5m |
| QNI forward (forces QLD to NSW) | 16,713 | 7.9% | 39.0% | 2.4% | -$5.6m | -$5.0m |
| QNI reverse (forces NSW to QLD) | 2,070 | 1.0% | 40.4% | 8.7% | -$1.1m | -$0.7m |
| Heywood forward (forces SA to VIC) | 20,155 | 9.6% | 35.9% | 20.9% | -$4.1m | -$3.1m |
| Heywood reverse (forces VIC to SA) | 30,770 | 14.6% | **41.3%** | **42.3%** | -$19.9m | **-$18.8m** |
| Directlink forward (forces QLD to NSW) | 44,634 | 21.2% | 33.3% | 1.1% | -$5.6m | -$3.8m |
| Directlink reverse (forces NSW to QLD) | 23,178 | 11.0% | 62.6% | 2.0% | -$1.1m | -$0.7m |
| Murraylink forward (forces SA to VIC) | 37,719 | 17.9% | 46.4% | 5.9% | -$4.1m | -$3.4m |
| Murraylink reverse (forces VIC to SA) | 86,013 | 40.9% | 34.6% | 3.1% | -$19.9m | -$18.4m |
| Basslink forward (forces VIC to TAS) | 105,402 | 50.1% | 5.8% | 0.0% | -$0.0m | -$0.0m |
| Basslink reverse (forces TAS to VIC) | 47,765 | 22.7% | 10.3% | 0.6% | -$0.9m | -$0.9m |

{{exhibit:a8}}

Two notable financial insights emerge immediately from this attribution:

#### 6.2.1 VNI's -$98.5 million negative-residue engine is loop-flow forcing, not just NRM
Between September 2024 and August 2026, negative settlement residues on the NSW to VIC directional settlement bucket totalled -$98.5 million, and -$97.4 million (98.9%) of that total accumulated strictly during the 26,949 intervals when VNI's forward export limit was forced negative ($U_t < 0$, forcing southward NSW to VIC flow). Fully 82.7% of all VNI forward forced-negative intervals occurred during counter-price flow (NSW priced higher than Victoria while VNI was physically forced to flow from NSW into Victoria). Yet only 0.5% of those intervals carried an explicit NRM or soft-ramp setter equation.

Why does VNI haemorrhage -$97.4 million in counter-price negative residues without an explicit NRM clamp setting the bound? Because the culprit is physical thermal and voltage loop-flow forcing in southern New South Wales and Snowy (such as thermal constraints on the Jindera-Wodonga and Lower Tumut-Wagga corridors, or Snowy-Murray voltage bounds). When northern and southern NSW thermal or stability equations require VNI to carry negative (southward) flow to prevent line overloads while New South Wales clears at a steep premium above Victoria, AEMO cannot invoke NRM to clamp flow back to zero without violating physical power-system security. Security constraints always override economic NRM clamping.

#### 6.2.2 Heywood's -$19.9 million negative-residue profile is heavily NRM-intervened
Contrast VNI with Heywood reverse (SA to VIC), where negative directional limits ($L_t < 0$) force eastward-to-westward VIC to SA flow. Over two years, Heywood reverse recorded 30,770 forced-negative intervals (14.6% of the entire sample), during which 41.3% were counter-price and 42.3% carried an explicit NRM or ramp setter equation. Those forced intervals accounted for -$18.8 million out of -$19.9 million (94.5%) of negative settlement residue on the VIC to SA settlement bucket. At the exact same time, parallel Murraylink reverse logged 86,013 forced-negative intervals (40.9%), capturing -$18.4 million of the same pooled VIC to SA negative-residue exposure.

On Basslink, by contrast, forced-negative forward limits occur in 50.1% of all intervals (105,402 intervals), yet only 5.8% are counter-price and negative residues are negligible (-$0.04m). That cleanly proves that Basslink's negative upper limit is predominantly a *with-price* hydroelectric import regime (Victoria exporting cheaper mainland power into Tasmania while cable rules or FCSPS hold the forward limit negative), rather than a counter-price congestion trap.

Part II has established when transfer envelopes contract, why they contract (switches versus LHS ramps versus RHS shifts), how contractions cascade across the 6x6 grid, and where forced-negative limits generate -$118 million in VNI and VIC-SA negative residues. Part III now drills down to the individual asset level: which specific generating units and constraint equations actually drive economic congestion rent, and how the surge of grid-scale batteries is altering five-minute network physics.
