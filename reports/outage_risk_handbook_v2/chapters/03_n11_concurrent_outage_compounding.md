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

{{exhibit:b4}}

Four physical N-1-1 archetypes emerge clearly from the 109 compounding pairs:

1. **Southern NSW dual-corridor bottleneck (`N-BABU` + `N-X_03+4_WG_CLOSE` on VNI forward):** Taken separately, `N-BABU` (Balranald-Buronga 220 kV) averaged +190 MW above baseline on VNI forward (reflecting mild weather timing) and `N-X_03+4_WG_CLOSE` averaged -91 MW, giving an additive expectation of +99 MW. During the 75 half-hours when both families overlapped simultaneously, however, VNI forward capacity collapsed to **-677 MW below baseline** (an extra super-additive collapse of **-776 MW**), forcing heavy reverse flow while super-additively widening the Victoria to New South Wales spread by **+$69.4/MWh**. The physical mechanism is textbook N-1-1: cutting the western 220 kV parallel path (`N-BABU`) at the exact same moment as Lower Tumut-Yass/Collector-Marulan 330 kV lines (`03+4`) removes both east and west escape routes around Snowy, forcing NEMDE to clamp VNI northward transfer deeply negative.
2. **Northern NSW QNI spine stacking (`N-DMSR_8J` or `N-ARDM_8C` + `N-ARKS_965` on QNI forward):** Removing a 330 kV QNI feeder (`8C` Armidale-Dumaresq or `8J` Dumaresq-Bulli Creek) already cuts QNI forward capacity by -376 to -385 MW standalone. Stacking an overlapping northern NSW 132 kV Armidale-Koolkhan (`N-ARKS_965`) outage on top of it drives the observed joint drop down to **-439 to -456 MW** across 204 overlapping half-hours (-185 to -194 MW worse than the linear sum). On QNI reverse, stacking Braemar transformer (`Q-BRTX1`, -175 MW standalone) with Blackwall-Belmont (`Q-BKBM`, -234 MW standalone) produces a **-626 MW** joint ceiling collapse (-217 MW worse than additive).
3. **South Australian Tailem Bend 275 kV bus and line stacking on Heywood:** Because Tailem Bend is the primary South Australian landing point for Heywood, overlapping a South East to Tailem Bend (`S-TBSE`, -140 MW) or Tailem Bend to Tungkillo (`S-TBTU`, -108 MW) line outage with a Tailem Bend 275 kV West Bus outage (`S-TB275_W_BUS_BC-2CP`) slashes Heywood reverse capacity by **-256 to -257 MW** (-330 to -361 MW super-additive relative to the +74 to +104 MW linear sum). In the forward direction, stacking `S-TBSE` (-168 MW) with the `S-X_BGBW+BGDV+BGTX` outage family (-95 MW) slashes Heywood forward capacity by **-418 MW** (-155 MW beyond linear addition).
4. **Cross-corridor FCAS and frequency-protection stacking on Basslink:** On Basslink reverse, overlapping Tasmanian/global fast-frequency-response constraints (`F-I_FFR_GLOBAL` or `F-T-GO_CB_A752`) with mainland southern-ring radial outages (`N-JNWG_RADIAL`, `N-LDTW_84`, `V-MLSY_NOEMTT_R`) triggers large negative super-additivity (-147 to -393 MW across 415 to 2,346 overlapping half-hours) as combined system-inertia and continental balancing limits tighten simultaneously.

### 3.3 Distribution of compounding severity across the six interconnectors

{{exhibit:b5}}

Comparing compounding pair counts and worst-decile (P10) super-additive losses across all six links confirms that N-1-1 risk is concentrated where meshed AC paths converge on narrow regional choke points: VNI, QNI, Heywood, and Basslink exhibit P10 super-additive losses of -150 to -350 MW, whereas Directlink and Murraylink show smaller absolute megawatt residuals proportional to their 180 to 220 MW cable ratings.

> [!TAKEAWAY] Operational Rule for Forward Outage Calendars
> Any forward NOS screening tool that scores booked outages one line at a time misses one-third of real network risk. Whenever a forward calendar week shows two or more bookings overlapping inside the same regional choke point (Southern NSW 330/220 kV around Wagga-Yass-Buronga; Northern NSW 330/132 kV around Armidale-Dumaresq; or South Australia's Tailem Bend 275 kV hub), desks must apply an explicit N-1-1 compounding multiplier rather than summing standalone single-family MW impacts.

### 3.4 Worked physical example: why parallel-path removal breaks linear additivity

Why does overlapping `N-BABU` (Balranald to Buronga 220 kV) with `N-X_03+4_WG_CLOSE` (Lower Tumut to Yass Line 03 plus Collector to Marulan Line 4) cut VNI forward capacity by -677 MW when the standalone effects sum linearly to +99 MW? The answer lies in basic Kirchhoff impedance redistribution across parallel corridors.

In an intact N-0 network, power flowing northward from Victoria into New South Wales divides naturally across two parallel north-south pathways: the main 330 kV Snowy-Murray-Wagga-Yass-Marulan eastern spine and the western 220 kV Murray-Kerang-Red Cliffs-Buronga-Balranald-Darlington Point arc. When only one corridor loses a circuit (an N-1 state), the intact parallel corridor absorbs redistributed power flow without immediately violating thermal or transient-stability limits, and transmission operators frequently schedule single-circuit work during mild spring or autumn weekends when baseline transfer capacity sits high.

When both corridors suffer simultaneous outages (an N-1-1 state), the redistribution safety valve vanishes. Any contingent trip of a remaining 330 kV spine circuit (such as Line 5 or Line 051) now dumps the entire interregional transfer onto a single weakened path with no western 220 kV relief route, pushing voltage angles beyond the transient-stability boundary. NEMDE responds by invoking a dedicated dual-outage stability or thermal constraint equation whose right-hand side is dramatically lower than either standalone N-1 equation, clamping VNI forward limits deeply negative (forcing southward flow) and widening the Victoria to New South Wales spread by an extra +$69.4/MWh beyond standalone expectations.

A parallel N-1-1 geometry governs South Australia's Tailem Bend 275 kV hub. Removing one South East to Tailem Bend 275 kV feeder (`S-TBSE`) still leaves the second parallel circuit and intact Tailem Bend bus tie-breakers to absorb Heywood transfer. Removing a Tailem Bend West Bus section (`S-TB275_W_BUS_BC-2CP`) at the exact same moment strips away bus redundancy so a single fault isolates both lines or trips the remaining path, causing observed Heywood reverse capacity to drop -256 MW against a +74 MW linear sum (-330 MW super-additive collapse). Quantitative forecasting models that encode NOS outages strictly as independent additive binary dummy variables ($x_A + x_B$) structurally cannot represent these N-1-1 cliffs unless they include explicit regional overlap counts and pairwise corridor interaction terms.

Having quantified what outages cost in dollars (Chapter 2) and how overlapping outages compound non-linearly (Chapter 3), we now turn to the core forecasting challenge of the NOS regime: repairing the legacy forward binding outlook so its probabilities can be trusted across 0 to 365 day horizons.
