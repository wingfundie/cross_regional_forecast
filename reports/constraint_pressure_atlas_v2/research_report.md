# Six-Link Constraint Pressure, Generator Influence, and Contraction Atlas (v2)

## Executive Overview and Reader Guide

This flagship edition consolidates two full years of native five-minute constraint-equation telemetry across all six interconnectors of the Australian National Electricity Market (1 September 2024 to 31 August 2026, fixed NEM time UTC+10) into a single mechanical and economic reference. It brings Directlink, Murraylink, and Basslink to full analytical parity with VNI, QNI, and Heywood; closes the megawatts-without-dollars disconnect through tight-headroom congestion-rent weighting and shadow-rent constraint valuation; audits the root causes of envelope reconstruction error; decomposes all 44,185 sharp 30-minute contractions into equation switches, left-hand-side generator ramps, and right-hand-side shifts; isolates five-minute utility battery impulses; and maps the complete six-by-six cross-link cascade matrix alongside negative-residue clamping attribution.

Readers should treat every reported interconnector export and import limit as an endogenous dispatch-solution output rather than maximum secure physical transfer capability, and interpret fixed-equation generator sensitivities as mechanical linear-programme decompositions rather than independent causal treatment effects. Three companion standalone Event Atlases v2 covering VNI, QNI, and Heywood retain full five-minute forensic case windows at 67% to 72% smaller file size.

## Chapter 1 · Constraint Envelope Mechanics and Accounting

Interconnector transfer limits in the Australian National Electricity Market are frequently misread by market participants as fixed wire ratings stamped on transmission towers. In practice, every five-minute export and import limit published by the Australian Energy Market Operator is an endogenous output of the central dispatch linear programme. That distinction is not merely academic. When a directional limit on the Victoria to New South Wales interconnector drops by 350 MW within half an hour, or when Heywood shifts from a 400 MW transfer ceiling to a forced reverse flow requirement, the physical conductors between substations have rarely changed state. What has changed is either the balance of competing generator injections inside a shared linear inequality, the right-hand-side boundary condition reflecting ambient temperatures and inertia, or the identity of the binding constraint equation itself.

> [!TAKEAWAY] Core Operational Principle
> Reported interconnector limits are dispatch-solution outputs conditional on the simultaneous state of every generator, load, and contingency equation in the NEM dispatch engine. They do not represent maximum secure physical transfer capability, and treating them as static corridor capacities obscures the specific units and network conditions that actually move regional price spreads.

### 1.1 The solved linear inequality and conditional transfer bounds

In each five-minute dispatch interval $t$, the NEM dispatch engine (NEMDE) enforces a catalogue of generic constraint equations governing thermal ratings, transient stability, voltage stability, oscillatory damping, rate of change of frequency, and system-strength margins. Any generic constraint $c$ that includes an interconnector flow term $F_t$ can be written in canonical less-than-or-equal-to form:

$$a_{c,t} F_t + \sum_{i \in \mathcal{G}_c} b_{c,i,t} P_{i,t} + Z_{c,t} \le \text{RHS}_{c,t}$$

Here $a_{c,t}$ is the interconnector left-hand-side coefficient, $P_{i,t}$ is the dispatched output of scheduled or semi-scheduled generating unit $i$ (with negative values for charging bidirectional batteries or pumping hydro), $b_{c,i,t}$ is that unit's left-hand-side participation factor, and $Z_{c,t}$ aggregates all non-generator terms on the left-hand side, including other interconnectors, frequency control ancillary service enablement, and regional demand components. The right-hand side $\text{RHS}_{c,t}$ is evaluated dynamically from SCADA telemetry, line ratings, synchronous unit counts, and stability nomograms before the linear programme solves.

The sign of $a_{c,t}$ dictates which directional boundary equation $c$ constrains. Under AEMO's sign convention, each interconnector has a nominal positive forward direction (Victoria to New South Wales on VNI, New South Wales to Queensland on QNI and Directlink, Victoria to South Australia on Heywood and Murraylink, and Tasmania to Victoria on Basslink). When $a_{c,t} > 0$, increasing forward flow pushes the left-hand side closer to $\text{RHS}_{c,t}$, so the equation sets an upper (forward) transfer bound. When $a_{c,t} < 0$, increasing reverse flow (making $F_t$ more negative) pushes the left-hand side toward $\text{RHS}_{c,t}$, so the equation sets a lower (reverse) transfer bound.

Rearranging the inequality around the solved flow $F_t$ yields the exact conditional transfer bound implied by equation $c$ at interval $t$:

$$F^{\text{bound}}_{c,t} = F_t + \frac{\text{RHS}_{c,t} - \text{LHS}_{c,t}}{a_{c,t}}$$

When equation $c$ is binding at the dispatch solution, $\text{RHS}_{c,t} - \text{LHS}_{c,t} = 0$ and the conditional bound collapses identically to the solved flow $F_t$. When equation $c$ is non-binding, the slack term $(\text{RHS}_{c,t} - \text{LHS}_{c,t}) / a_{c,t}$ measures how many additional megawatts of interconnector transfer could clear in that direction before equation $c$ would bind, holding every other unit's output and the right-hand side constant. Taking the tightest conditional upper bound across all active equations with $a_{c,t} > 0$ defines the reconstructed forward envelope $U_t$; taking the tightest conditional lower bound across all active equations with $a_{c,t} < 0$ (expressed as positive reverse transfer capacity, matching AEMO's negated import limit convention) defines the reconstructed reverse envelope $L_t$.

### 1.2 Directional sign conventions and negative transfer limits

Directional capacities in the NEM are asymmetric and signed, and careless preprocessing frequently corrupts empirical work. AEMO publishes an export limit (bounding positive forward flow $F_t \le U_t$) and an import limit (bounding negative reverse flow $F_t \ge I_t$). To place both directions on a comparable positive-capacity scale while preserving exact physical meaning, reverse directional capacity is defined throughout this study as $L_t = -I_t$, so that a positive value of $L_t$ indicates available megawatts of transfer from the nominal receiving region back to the nominal sending region.

Crucially, neither $U_t$ nor $L_t$ is clamped at zero. A negative value of $U_t$ means the forward export limit itself is negative, which forces the interconnector to flow in the reverse direction ($F_t \le U_t < 0$) simply to keep a thermal or stability equation feasible. Symmetrically, a negative value of $L_t$ (meaning a positive import limit $I_t > 0$) forces forward flow ($F_t \ge I_t > 0$). Clamping signed limits at zero would erase forced-flow regimes, misstate directional headroom, and hide the exact intervals in which negative settlement residues accumulate.

Directional headroom is therefore defined without truncation as $H^{\text{upper}}_t = U_t - F_t$ in the forward direction and $H^{\text{lower}}_t = L_t + F_t = F_t - I_t$ in the reverse direction. Throughout this report, an interval is classified as having tight headroom whenever directional headroom is at or below 50 MW ($H_t \le 50\text{ MW}$). That 50 MW threshold captures both strictly binding intervals ($H_t = 0$) and near-binding intervals where a modest generator ramp or contingency re-rating can push the interconnector into immediate price separation.

### 1.3 Worked physical example: why local generation shrinks interconnector limits

To make the algebra concrete, consider the leading thermal equation on VNI in the reverse direction during the 24-month study window, `N>>NIL_060_051`, which protects the Jindera to Wodonga 330 kV line against overload following a contingent trip of the Wagga to Lower Tumut 330 kV line. Suppose at interval $t$ the equation carries an interconnector coefficient of $a = -1.0$ (so reverse flow from New South Wales into Victoria increases the left-hand side) and a Snowy hydro unit enters with a left-hand-side coefficient of $b_i = +0.55$, meaning each megawatt of generation pushes 0.55 MW of parallel loop flow across the same monitored 330 kV boundary.

Differentiating the conditional bound with respect to unit $i$'s output while holding the equation fixed yields the unit's exact mechanical sensitivity:

$$s_{c,i,t} = -\frac{b_{c,i,t}}{a_{c,t}}$$

In this example, for reverse transfer capacity $L_t = -F^{\text{lower}}_t$, the sensitivity of reverse capacity to unit $i$ is $-b_i / |a| = -0.55$. If the unit ramps up by $\Delta P_i = +200\text{ MW}$ over 30 minutes to serve evening demand, the mechanical pressure term $s_i \Delta P_i$ reduces available reverse interconnector capacity by $110\text{ MW}$, even though no transmission line tripped and ambient thermal ratings did not budge. Because a single generator's ramp competes directly with interconnector transfer for the same finite thermal margin on the 330 kV cut-plane, an observer monitoring only the headline interconnector limit sees a sudden 110 MW contraction unless the underlying linear-programme coefficients are unpacked.

The reverse is equally true when a generator sits on the receiving side of the monitored cut-plane and enters with an opposite-signed coefficient. In that geometry, ramping the unit up provides counter-flow relief that expands the interconnector limit, whereas ramping the unit down (for instance, a sudden cloud transient dropping a solar farm by 150 MW, or a battery switching from discharging to charging) abruptly strips away relief and contracts the limit.

### 1.4 From mechanical megawatts to economic congestion rent

Previous internal constraint studies ranked generators and equations almost exclusively by unweighted mechanical movement: summing $|s_{c,i,t} \Delta P_{i,t}|$ across all 210,240 five-minute intervals in two years, or counting how often an equation held the tightest conditional bound. That mechanical accounting answers an engineering question (which units move the constraint boundary most often?) but leaves the commercial desk question unanswered: which units and equations actually create regional price separation and transfer settlement residue?

A solar farm that moves a thermal boundary by 120 MW at 11:30 on a mild spring morning when interconnector headroom is 250 MW and the regional price spread is $1.50/MWh generates zero congestion rent and zero trading P&L impact. By contrast, a Snowy hydro unit or grid-scale battery that shifts a binding boundary by 80 MW during an evening ramp when headroom is below 50 MW and the Victoria to New South Wales price spread sits at $280/MWh directly reshapes interregional settlement residues and regional clearing prices.

To close that disconnect, this second-edition atlas pairs every mechanical metric with an explicit economic counterpart computed over the exact same 24-month panel (1 September 2024 to 31 August 2026, in fixed NEM time UTC+10):

1. **Tight-headroom and scarcity-weighted unit pressure:** For each unit $i$ active inside a leading equation on link $k$, five-minute and 30-minute mechanical moves are weighted by the concurrent positive directional regional price spread $\Delta \pi^{+}_{k,t}$ strictly during tight-headroom intervals ($H_{k,t} \le 50\text{ MW}$), converted to five-minute dollar-flow equivalents via $|\Delta \text{bound}_{i,t}| \times \Delta \pi^{+}_{k,t} / 12$.
2. **Shadow-rent constraint valuation:** Rather than counting non-binding leader intervals, each constraint equation is valued by its cumulative 24-month binding shadow rent, defined as the sum of $|\text{MV}_{c,t}| / 12$ across intervals in which the equation actually binds in the dispatch solution (excluding synthetic zero-flow linear-programme penalty constraints whose marginal values exceed the $30,000/MWh penalty band).
3. **Five-minute impulse tracking alongside 30-minute ramps:** Because utility batteries frequently execute full charge-to-discharge reversals within a single five-minute dispatch interval, five-minute step impulses are extracted alongside rolling 30-minute net moves so short-horizon volatility is no longer averaged away.

The chapters that follow apply this unified mechanical and economic framework across all six NEM interconnectors without exception, beginning with the full 24-month six-link parity baseline.

## Chapter 2 · Full Six-Link Parity and Parallel Co-Binding

Prior constraint-pressure reporting concentrated almost exclusively on the three primary alternating-current interconnectors (VNI, QNI, and Heywood), relegating Directlink, Murraylink, and Basslink to secondary notes despite two full years of native five-minute attribution archives sitting on disk. Treating those three HVDC links as an afterthought creates a blind spot for both settlement-residue desks and grid modellers. Under the NEM settlement rules, Directlink flows and residues are pooled directly into the Queensland to New South Wales Settlement Residue Auction (SRA) buckets alongside QNI, while Murraylink flows and residues are pooled directly into the Victoria to South Australia SRA buckets alongside Heywood. Basslink, while outside the SRA scheme, governs the entire hydroelectric exchange between Tasmania and mainland Victoria and experiences the highest forced-limit frequency in the market.

Across the full 24-month study window from 1 September 2024 to 31 August 2026 (210,240 five-minute intervals per link, or 1,261,440 link-intervals in total), the six-link system logged 44,185 sharp 30-minute directional contraction episodes, 1,284,417 binding constraint equation-intervals, and 446 unique participating generating units. Placing all six interconnectors side by side exposes sharp structural differences between meshed AC corridors and regulated or market-network HVDC links.

### 2.1 Structural comparison across all twelve directional corridors

| Link | Direction | Median cap (MW) | P05 cap (MW) | Tight headroom (%) | Forced limit (%) | Contractions (24m) | Median drop (MW) | Mean spread when tight ($/MWh) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| VNI | VIC to NSW | 755 | -272 | 42.5% | 12.8% | 4,029 | 350 | $87.04 |
| VNI | NSW to VIC | 450 | -10 | 17.6% | 5.3% | 3,455 | 317 | -$33.34 |
| QNI | NSW to QLD | 557 | -46 | 11.8% | 7.9% | 3,122 | 168 | $49.64 |
| QNI | QLD to NSW | 957 | 153 | 29.9% | 1.0% | 4,300 | 173 | $65.06 |
| Heywood | VIC to SA | 401 | -119 | 31.7% | 9.6% | 3,859 | 236 | $73.04 |
| Heywood | SA to VIC | 350 | -217 | 23.3% | 14.6% | 3,867 | 258 | $20.85 |
| Directlink | NSW to QLD | 47 | -59 | 42.9% | 21.2% | 4,395 | 59 | $1.82 |
| Directlink | QLD to NSW | 81 | -61 | 32.3% | 11.0% | 4,354 | 62 | $52.48 |
| Murraylink | VIC to SA | 107 | -131 | 61.8% | 17.9% | 3,740 | 90 | $31.25 |
| Murraylink | SA to VIC | 9 | -168 | 51.2% | 40.9% | 3,365 | 98 | -$14.66 |
| Basslink | TAS to VIC | -17 | -258 | 27.0% | 50.1% | 2,625 | 185 | -$19.80 |
| Basslink | VIC to TAS | 183 | -227 | 48.1% | 22.7% | 3,074 | 175 | $35.63 |

The six-link comparison immediately overturns the informal assumption that small HVDC links are lightly loaded backup pathways. On a frequency-of-tightness basis, Murraylink is the most persistently constrained interconnector in the entire NEM: forward Victoria to South Australia headroom sits at or below 50 MW in 61.8% of all five-minute intervals, and reverse South Australia to Victoria headroom sits at or below 50 MW in 51.2% of intervals, with a median reverse transfer ceiling of just 9 MW and forced forward-flow requirements in 40.9% of all intervals. Directlink displays a similar pattern along the northern border, clearing at tight headroom in 42.9% of forward (NSW to QLD) intervals and 32.3% of reverse (QLD to NSW) intervals, while posting more monthly P90 contraction episodes (4,395 forward and 4,354 reverse) than any other link in the market.

On the large AC corridors, economic tightness concentrates along the dominant north-to-south and west-to-east scarcity axes. VNI forward transfer from Victoria into New South Wales operates at tight headroom in 42.5% of intervals, and during those tight intervals the Victoria to New South Wales price spread averages $87.04/MWh (compared with $34.02/MWh unconditionally). QNI reverse transfer from Queensland into New South Wales operates at tight headroom in 29.9% of intervals with an average tight-interval spread of $65.06/MWh, while Heywood forward transfer from Victoria into South Australia clears tight in 31.7% of intervals at an average spread of $73.04/MWh.

Basslink occupies a category of its own. Because Basslink operates as a long-distance subsea HVDC cable subject to frequency-control system protection scheme (FCSPS) constraints, thermal cable de-ratings, and Tasmania-side dynamic stability bounds, its median forward (Tasmania to Victoria) upper limit over the two-year window was actually -17 MW, meaning reverse import flow into Tasmania was forced in 50.1% of all five-minute intervals during the 2024 to 2026 hydroelectric storage management cycle. Reverse Victoria to Tasmania transfer operated within 50 MW of its limit in 48.1% of intervals at a mean tight spread of $35.63/MWh (Tasmania above Victoria).

### 2.2 Negative tight-headroom spreads: diagnosing counter-price flow regimes

A notable feature of the table above is that three directional corridors display negative average price spreads during tight-headroom intervals: VNI reverse (NSW to VIC, -$33.34/MWh), Murraylink reverse (SA to VIC, -$14.66/MWh), and Basslink forward (TAS to VIC, -$19.80/MWh). Those negative figures are not data anomalies; they are the signature of forced counter-price binding.

On VNI reverse, for instance, a tight lower headroom ($H^{\text{lower}}_t \le 50\text{ MW}$) frequently arises not because New South Wales is exporting cheap surplus power into an expensive Victoria, but because the reverse limit has been clamped down to a small positive or negative number while Victoria is already exporting heavily into a higher-priced New South Wales, or because loop flows from Snowy and southern New South Wales solar farms push flow southward against a positive NSW minus VIC spread. Whenever the directional price spread has the opposite sign to physical flow, tight headroom marks a negative-residue trap rather than a positive-residue rent opportunity. Chapter 6 quantifies the exact dollar toll of these counter-price regimes.

### 2.3 Parallel HVDC co-binding and SRA bucket dilution

For traders and risk analysts evaluating Settlement Residue Auction units, the primary commercial reason to integrate Directlink and Murraylink into the constraint atlas is parallel co-binding. Under the NEM settlement formula, a buyer of QLD to NSW SRA units receives a pro-rata share of the combined settlement residue generated across both QNI and Directlink, while a buyer of VIC to SA or SA to VIC SRA units receives a pro-rata share of combined residue across Heywood and Murraylink. If the parallel HVDC link retained ample spare headroom whenever the main AC link constrained, price separation could be partially relieved by rerouting flow across the DC link. The empirical evidence shows the exact opposite.

| Pooled corridor pair | Direction | Main link tight (%) | Parallel HVDC tight (%) | Both tight simultaneously (%) | P(HVDC tight given Main tight) | P(Main tight given HVDC tight) |
|---|---|---:|---:|---:|---:|---:|
| QNI + Directlink (QLD-NSW) | Forward (NSW to QLD) | 11.8% | 42.9% | 11.3% | 95.4% | 26.3% |
| QNI + Directlink (QLD-NSW) | Reverse (QLD to NSW) | 29.9% | 32.3% | 21.0% | 70.3% | 64.9% |
| Heywood + Murraylink (VIC-SA) | Forward (VIC to SA) | 31.7% | 61.8% | 27.4% | 86.5% | 44.4% |
| Heywood + Murraylink (VIC-SA) | Reverse (SA to VIC) | 23.3% | 51.2% | 20.3% | 87.2% | 39.6% |

Whenever QNI operates at tight headroom in the forward NSW to QLD direction, Directlink is simultaneously tight 95.4% of the time (11.3% of all intervals overlap out of 11.8% total QNI forward tightness). In the economically dominant QLD to NSW southward direction, Directlink is simultaneously tight in 70.3% of tight QNI intervals. Along the southern border, whenever Heywood hits tight headroom, Murraylink is simultaneously tight 86.5% of the time in the VIC to SA direction and 87.2% of the time in the SA to VIC direction.

The asymmetry in the two conditional probabilities explains the physical hierarchy of each border. Because the parallel HVDC links have much smaller nominal capacities (180 MW on Directlink, 220 MW on Murraylink) and sit embedded inside constrained regional sub-networks (northern New South Wales 132 kV lines around Lismore and Mullumbimby for Directlink; the Riverland 132 kV and North West Victoria 220 kV corridor around Red Cliffs, Monash, and Buronga for Murraylink), they hit local thermal or voltage limits frequently even when the main AC spine still has room to move. Thus $P(\text{Main tight} \mid \text{HVDC tight})$ is moderate (26.3% on Directlink forward and 39.6% to 44.4% on Murraylink). Once regional price separation becomes large enough to drive the main AC corridor into tight headroom, however, economic dispatch almost always saturates the parallel HVDC link first, leaving effectively zero unpriced parallel relief.

> [!WARNING] Implication for Pooled SRA Valuation
> Modelling QNI or Heywood limits in isolation overstates diversification across parallel links. In 70% to 95% of main-corridor binding intervals, the paired HVDC link is already saturated or forced-clamped. Moreover, during periods when Murraylink or Directlink is forced to flow counter-price by local 132 kV or 220 kV voltage constraints while the main AC corridor flows with the price spread, the negative residue accrued on the HVDC leg directly dilutes the pooled SRA payout for the entire border.

This structural co-binding finding sets up the next analytical question: how accurately can an external analyst reconstruct each link's published limit envelope from standing generic constraint equations, and why did earlier studies observe seemingly puzzling reconstruction errors on QNI and Heywood? Chapter 3 audits that exact discrepancy.

## Chapter 3 · Root-Cause Audit of Envelope Reconstruction Error

Before using constraint-equation sensitivities to attribute generator pressure or engineer forecasting features, a quantitative team must know when the reconstructed linear-programme envelope matches AEMO's published interconnector limits and when it diverges. Early multi-link diagnostics revealed an unsettling disparity: across the two-year sample, VNI forward limit reconstruction achieved a mean absolute error (MAE) of just 6.8 MW (with a median error effectively indistinguishable from floating-point zero at $2.3 \times 10^{-13}\text{ MW}$), yet QNI forward limits exhibited a reconstruction MAE of 409.8 MW, QNI reverse showed 248.4 MW, and Heywood showed 126.8 MW forward and 129.3 MW reverse. On the HVDC links, the gap grew wider still, reaching 8,737.7 MW on Directlink forward and 3,515.0 MW on Basslink forward.

Without a formal root-cause audit, a desk analyst might reasonably worry that the reconstruction pipeline contains a sign error, a broken unit factor, or corrupted SCADA inputs on QNI and Heywood. A systematic interval-by-interval audit across all 1,261,440 link-intervals resolves the mystery completely and produces a clean, actionable reliability rule for downstream modelling.

### 3.1 The decisive binary split: matched versus unmatched setter equations

In every five-minute dispatch interval, AEMO reports not only the numerical export and import limit but also the identity of the specific constraint equation that set each directional bound (the reported setter equation). Auditing reconstruction error conditional on whether that exact reported setter equation is present and matched in the reconstructed standing-equation candidate set reveals a striking binary result:

- **When the reported setter equation matches the reconstructed candidate set (`setter_matched = True`):** Reconstruction error collapses to numerical machine precision across *every single interconnector and every constraint family*. On VNI, matched thermal, voltage stability, transient stability, and ramp equations all record MAE below **0.00002 MW**. On QNI, matched thermal equations (36,213 forward intervals and 49,258 reverse intervals) record MAE of **0.000006 MW** and **0.000004 MW** respectively. Even on Heywood, Murraylink, Directlink, and Basslink, matched intervals show MAE under **0.0013 MW**.
- **When the reported setter equation is absent from the reconstructed candidate set (`setter_matched = False`):** **100%** of the material reconstruction MAE on VNI, QNI, Heywood, Directlink, Murraylink, and Basslink arises exclusively inside unmatched intervals.

There is no algebraic bug in the linear-programme factor reconstruction. Rather, the MAE disparity across links reflects exact structural differences in how often AEMO sets each corridor's published bound using equations outside the standard single-interconnector energy-equation formulation.

### 3.2 Decomposing MAE across all six interconnectors by setter family

| Link & direction | Setter match rate (%) | Total MAE (MW) | Median error (MW) | Leading unmatched setter family | Family interval share (%) | Family conditional MAE (MW) | Family MAE contribution (MW) |
|---|---:|---:|---:|---|---:|---:|---:|
| VNI forward | 94.8% | 6.8 | 0.0 | Voltage Stability | 0.7% | 399.0 | 2.7 |
| VNI reverse | 95.2% | 22.6 | 0.0 | NRM / Discretionary | 2.7% | 808.1 | 22.2 |
| QNI forward | 21.7% | 409.8 | 284.1 | Transient Stability | 48.1% | 365.1 | 175.5 |
| QNI reverse | 33.2% | 248.4 | 96.7 | ROCOF / UFLS / FCAS | 19.7% | 726.0 | 143.2 |
| Heywood forward | 71.5% | 126.8 | 0.0 | ROCOF / UFLS / FCAS | 6.5% | 922.6 | 60.2 |
| Heywood reverse | 75.4% | 129.3 | 0.0 | ROCOF / UFLS / FCAS | 7.5% | 1,044.2 | 78.1 |
| Directlink forward | 0.9% | 8,737.7 | 10,228.1 | Other (MNSP / cable) | 51.8% | 9,044.3 | 4,689.3 |
| Directlink reverse | 12.0% | 279.5 | 204.8 | Other (MNSP / cable) | 80.3% | 306.8 | 246.3 |
| Murraylink forward | 28.2% | 72.1 | 66.6 | Other (MNSP / local) | 43.9% | 121.1 | 53.2 |
| Murraylink reverse | 30.3% | 94.8 | 71.7 | Other (MNSP / local) | 63.8% | 146.8 | 93.6 |
| Basslink forward | 0.0% | 3,515.0 | 831.9 | Other (MNSP / cable) | 60.0% | 5,271.8 | 3,165.4 |
| Basslink reverse | 0.7% | 3,439.7 | 1,023.8 | Other (MNSP / cable) | 52.0% | 5,275.0 | 2,740.9 |

Examining each corridor's unmatched residuals reveals four distinct operational mechanisms that explain the entire error profile:

#### 3.2.1 VNI: high structural fidelity (95% matched), isolated NRM and stability misses
VNI achieves exact setter matching in 94.8% of forward intervals and 95.2% of reverse intervals. On VNI forward, the tiny 6.8 MW aggregate MAE splits almost entirely between 0.7% unmatched voltage-stability intervals (contributing 2.7 MW), 3.1% unmatched transient-stability intervals (2.6 MW), and 0.7% unmatched thermal intervals (1.2 MW). On VNI reverse, 98% of the 22.6 MW MAE comes from a single narrow bucket: 5,738 unmatched NRM and system-normal discretionary intervals (2.7% of the sample, averaging 808.1 MW residual error when AEMO invokes dynamic negative-residue clamping whose live right-hand side is overridden inside the dispatch engine outside standard standing energy factors). Excluding those 2.7% discretionary overrides, VNI's constraint envelope is reconstructed to near-exact precision across the two-year horizon.

#### 3.2.2 QNI: coupled FCAS/ROCOF equations and dynamic stability overrides
Why does QNI's exact setter match rate fall to 21.7% forward and 33.2% reverse? Three specific equation families account for over 94% of QNI's reconstruction error:

1. **Unmatched Transient Stability equations on QNI forward (48.1% of intervals, 175.5 MW MAE contribution):** Nearly half of all five-minute intervals on QNI forward are governed by Queensland-NSW transient stability formulations (including dynamic headroom and parallel-flow equations) whose effective interconnector factor or multi-interconnector coupling is not captured by a single-link energy equation without co-solving Directlink and Queensland inertia states.
2. **Unmatched ROCOF, UFLS, and FCAS co-optimisation equations (19.7% of QNI reverse intervals contributing 143.2 MW MAE; 10.0% of QNI forward intervals contributing 114.9 MW MAE):** Joint energy-and-FCAS constraints include both interconnector flow $F_t$ and regional Raise/Lower FCAS enablement terms inside the same inequality (for example, protecting Queensland against credible islanding events by capping transfer as a function of available fast-raise FCAS). Because the energy-only reconstruction treats FCAS terms as part of a residual $Z$-term rather than co-optimising the FCAS simplex, the implied energy-only conditional bound diverges systematically by 726 MW to 1,154 MW whenever a coupled FCAS equation sets the published QNI limit.
3. **Unmatched Voltage Stability equations (38.8% of QNI reverse intervals contributing 78.1 MW MAE; 16.5% of QNI forward intervals contributing 94.3 MW MAE):** Many Queensland-NSW voltage stability equations depend on dynamic synchronous-condenser, reactive-power, or multi-bus voltage indices whose standing LHS records differ from the live dispatch version or couple QNI with Directlink.

Crucially, whenever QNI is bounded by standard Thermal equations (17.3% of forward intervals and 23.5% of reverse intervals), exact setter match is achieved over 96% of the time and reconstruction error drops to 0.000005 MW.

#### 3.2.3 Heywood: 71% to 75% exact match, with ROCOF and transient stability driving the residual
Heywood sits cleanly between VNI and QNI. Exact setter matching reaches 71.5% forward and 75.4% reverse, leaving a 0.0 MW median error in both directions. Over 70% of the 126.8 MW forward MAE and 129.3 MW reverse MAE stems from just two unmatched buckets: South Australian ROCOF / UFLS / FCAS islanding constraints (6.5% forward share contributing 60.2 MW MAE; 7.5% reverse share contributing 78.1 MW MAE) and Transient Stability formulations (14.1% forward share contributing 31.1 MW MAE; 12.1% reverse share contributing 15.7 MW MAE), including South East to Tailem Bend series-capacitor dynamic limits and synchronous-generator count rules in South Australia. When Heywood operates under matched thermal, voltage-stability, or standard discretionary bounds, reconstruction is exact to five decimal places.

#### 3.2.4 Directlink, Murraylink, and Basslink: why HVDC MAE rises sharply to 3,500 to 8,700 MW
The multi-thousand-megawatt MAE numbers on Directlink forward (8,737.7 MW) and Basslink (3,515.0 MW forward, 3,439.7 MW reverse) illustrate a vital modelling lesson rather than a pipeline defect. HVDC cables are not passive alternating-current impedance paths; their transfer limits are frequently governed by Market Network Service Provider (MNSP) energy bids, cable thermal ratings, inverter runback logic, or FCSPS protection rules rather than generic AC constraint equations. When no generic AC equation with an active interconnector coefficient restricts flow, the solver's default generic-equation envelope defaults to a large unconstrained ceiling (typically 10,000 MW or the sum of non-binding AC constraints), whereas AEMO's published export or import limit reflects the physical 180 MW Directlink or 478 to 594 MW Basslink cable cap. Subtracting a 10,000 MW unconstrained generic-equation ceiling from a 47 MW cable limit immediately creates an 8,700 MW residual.

Murraylink shows a hybrid profile (28.2% to 30.3% exact match, 72.1 to 94.8 MW MAE) because it operates as a regulated HVDC link whose local 132 kV and 220 kV thermal and voltage limits frequently appear as standard generic constraints alongside non-generic cable and runback caps.

### 3.3 Operational quarantine rule for forecasting and attribution

> [!TAKEAWAY] Practical Rule for Quant and Desk Workflows
> Never feed raw reconstructed envelope bounds blindly into a forecasting feature matrix or generator attribution ranking on QNI, Heywood, Directlink, or Basslink. Always propagate the binary `setter_matched` flag and setter-family label alongside every five-minute interval:
> 1. Tier 1 (Exact linear-programme attribution): Use exact generator sensitivities $s_{c,i,t} = -b_{c,i,t}/a_{c,t}$ strictly on intervals with `setter_matched = True` (95% of VNI, 72% to 75% of Heywood, 22% to 33% of QNI, and 28% to 30% of Murraylink).
> 2. Tier 2 (Published-limit regime modelling): On unmatched ROCOF/FCAS, dynamic stability, and HVDC cable intervals, model AEMO's published directional limit directly using system-state predictors (synchronous unit counts, inertia, FCAS enablement, cable availability, and NRM flags) rather than attempting single-link linear-programme reconstruction.

With the reliability boundary of every corridor cleanly mapped, Part II turns to the physical and seasonal dynamics of the published directional limits themselves: diurnal regimes with formal uncertainty bounds, full-population contraction decomposition, and cross-corridor contagion.

## Chapter 4 · Diurnal, Seasonal, and Weather Regimes

A two-year median interconnector limit hides more than it reveals. Because solar irradiance, rooftop PV net demand, ambient conductor temperatures, and interregional demand peaks follow tightly coupled diurnal and seasonal cycles, transfer capacity on the same corridor can swing by more than 700 MW between 13:00 and 19:00 on an ordinary weekday without a single transmission outage occurring. Earlier internal research reported unweighted diurnal averages without formal uncertainty intervals, leaving desks unable to tell whether a 120 MW seasonal shift represented a persistent structural regime or a handful of extreme multi-day outage weeks.

To separate structural diurnal physics from short-lived outage noise, every directional corridor across all six interconnectors was partitioned into sixteen season-by-diurnal cells (four southern-hemisphere seasons across four NEM-time blocks: Overnight 21:00 to 05:55, Morning Peak 06:00 to 08:55, Solar Midday 09:00 to 15:55, and Evening Ramp 16:00 to 20:55). Within each cell, 95% confidence intervals were estimated using a seven-day contiguous block bootstrap (200 resamples of weekly blocks), which preserves multi-day weather persistence, week-long transmission maintenance windows, and serial correlation in thermal limits.

### 4.1 The solar midday hollow and evening recovery across six links

Comparing forward directional capacity across the four diurnal blocks confirms that midday solar congestion is now the single strongest deterministic driver of mainland interconnector envelopes, though its polarity differs starkly across borders.

On VNI forward (VIC to NSW), solar midday depression is severe and statistically decisive. During Summer, median forward capacity falls from 896 MW overnight (95% block CI: 832 to 930 MW) to 273 MW in the Morning Peak (CI: 37 to 288 MW) and collapses to 0 MW during Solar Midday (CI: -72 to +78 MW), before rebounding to 690 MW in the Evening Ramp (CI: 669 to 823 MW). Because the confidence interval for Summer Solar Midday straddles zero, VNI forward transfer is routinely closed or forced southward during bright summer afternoons as utility-scale solar across north-western Victoria and south-western New South Wales saturates the 220 kV and 330 kV cut-planes between Murray, Jindera, Darlington Point, and Wagga. In Winter, when solar irradiance softens and ambient line ratings rise, VNI forward Solar Midday median capacity recovers to 589 MW (CI: 492 to 682 MW), and Winter Evening Ramp capacity reaches 992 MW (CI: 936 to 1,081 MW).

On VNI reverse (NSW to VIC), the diurnal profile inverts cleanly. During Summer, median reverse capacity climbs from 322 MW overnight (CI: 288 to 367 MW) to 740 MW during Solar Midday (CI: 698 to 792 MW), because southern New South Wales solar generation provides counter-flow relief or shifts the corridor southward precisely when Victoria's own rooftop solar suppresses Victorian net demand.

On Heywood forward (VIC to SA), the midday trough appears in every single season. Summer forward capacity drops from 530 MW overnight (CI: 499 to 593 MW) to 238 MW during Solar Midday (CI: 204 to 258 MW), recovering to 467 MW in the Evening Ramp. Winter shows an even tighter envelope across all hours, dropping to 176 MW at Solar Midday (CI: 124 to 216 MW) and 256 MW in the Evening Ramp (CI: 195 to 466 MW), reflecting winter southern-network outages and reduced synchronous-generation dispatch in South Australia during mild windy days.

QNI displays the opposite forward-versus-reverse solar signature because Queensland's immense utility and rooftop solar fleet sits on the northern side of the border. In the QNI forward (NSW to QLD) direction, Solar Midday actually exhibits the *highest* median capacity in Summer (762 MW, CI: 721 to 804 MW), Autumn (670 MW), and Winter (655 MW), because Queensland has little appetite to import at noon and southward loop-flow pressure relieves northward constraints; instead, QNI forward capacity drops sharply in the Evening Ramp (falling to 516 MW in Summer, 380 MW in Winter, and just 232 MW in Spring, CI: 151 to 308 MW) just as Queensland evening demand peaks. Conversely, in the QNI reverse (QLD to NSW) direction, Summer median capacity drops from 1,031 MW overnight to 708 MW during Solar Midday (CI: 654 to 733 MW), while Spring Solar Midday plunges to 487 MW (CI: 304 to 674 MW) under the combined weight of peak spring maintenance outages and midday solar injection.

### 4.2 Seasonal concentration of tight headroom

Capacity alone does not generate congestion rent; a low ceiling matters economically only when interregional dispatch actually presses against it. Mapping the percentage of five-minute intervals with tight forward headroom ($H^{\text{upper}}_t \le 50\text{ MW}$) across links and seasons reveals where physical transfer demand collides hardest with seasonal bounds.

Four operational hotspots stand out directly from the seasonal matrix:

1. **VNI forward in Summer and Spring midday:** Forward headroom sits at or below 50 MW in **64.4%** of Summer Solar Midday intervals (95% block CI: 58.9% to 72.0%) and **56.4%** of Spring Solar Midday intervals (CI: 47.8% to 65.1%). Even during Summer Evening Ramp, VNI forward remains tight in **48.3%** of intervals (CI: 42.2% to 54.9%), explaining why VNI forward generates the largest economic price spreads in the NEM.
2. **QNI reverse in Winter and Spring midday:** While QNI forward tight headroom stays low in Winter (2.3% to 5.0%), **QNI reverse (QLD to NSW)** surges to **65.7%** tight headroom during Winter Solar Midday (CI: 60.4% to 71.1%) and **55.0%** during Spring Morning Peak (CI: 48.1% to 64.3%). Queensland's surplus winter sunshine meets strong southern heating demand in New South Wales, pinning QNI southward against its thermal and voltage bounds all afternoon.
3. **Heywood forward in Winter across every time block:** Heywood forward tight headroom climbs above **40%** in Winter Overnight (42.0%), Morning Peak (42.3%), and Solar Midday (40.8%), while Heywood reverse (SA to VIC) spikes to **51.3%** in Summer Solar Midday (CI: 42.9% to 60.8%) and **45.3%** in Spring Solar Midday (CI: 40.2% to 49.7%) as South Australian rooftop and utility solar exports collide with Heywood southward limits.
4. **Murraylink and Directlink chronic tightness:** Murraylink forward remains above **55% to 70%** tight headroom across almost every season and block, confirming that the 220 MW DC link is structurally pinned whenever Victorian solar or wind pushes west toward South Australia. Directlink forward peaks at **59.5%** tight headroom in Summer Solar Midday (CI: 52.1% to 67.9%) and **57.6%** in Summer Morning Peak.

### 4.3 Block-bootstrap width as an operational regime-stability diagnostic

An overlooked benefit of the seven-day block bootstrap is that the *width* of the 95% confidence interval measures week-to-week regime instability. Compare two Spring blocks on QNI reverse: during Winter Overnight, QNI reverse median capacity is 1,085 MW with a razor-thin 95% block CI of just 39 MW (1,076 to 1,115 MW), indicating a highly stable system-normal thermal ceiling. During Spring Overnight, however, median capacity drops to 918 MW while the 95% block CI widens more than fourteen-fold to 563 MW (434 to 997 MW). That ballooning uncertainty width is the direct statistical footprint of transmission maintenance seasonality: in Spring, scheduled line outages periodically slash QNI's ceiling in half for multi-day blocks, creating a bimodal distribution that point-average climatology completely masks.

Similarly, on VNI forward Morning Peak in Summer, the 95% block CI spans 251 MW (37 to 288 MW) because warm-weather morning solar ramp-ups interact with ambient temperature deratings and southern New South Wales line outages. For forecasting models, wide block-bootstrap CIs signal exactly the season-block cells where static seasonal baselines fail and where explicit outage-set and weather features earn their keep.

> [!TAKEAWAY] Desk Interpretation of Diurnal and Seasonal Confidence Bounds
> Narrow block-bootstrap CIs (such as Winter Overnight on QNI or Summer Overnight on Heywood) indicate repeatable, weather-driven system-normal transfer envelopes suitable for baseline seasonal hedging. Wide CIs (such as Spring QNI, Winter Evening Heywood, and Summer Morning VNI) flag outage-dominated or bimodal regimes where directional capacity risk cannot be hedged with static seasonal profiles alone and requires explicit outage-calendar monitoring (developed in Flagship Edition B).

Knowing *when* transfer ceilings sit low still leaves the sharper operational question: when a limit suddenly drops by 200 to 600 MW within 30 minutes, what physically caused the drop? Chapter 5 resolves that question across all 44,185 sharp contractions.

## Chapter 5 · Contraction Anatomy: Equation Switches, LHS Ramps, and RHS Shifts

When an interconnector's export or import limit drops sharply over a 30-minute window, trading desks and automated models face a fundamental attribution problem. Three physically distinct mechanisms can produce the exact same headline megawatt drop on a dispatch screen, yet each mechanism has completely different predictability and persistence:

1. **Path A (Active-leader equation switch):** A different constraint equation takes over as the tightest directional bound between $t - 30\text{ min}$ and $t$. Common triggers include a planned or unplanned transmission outage invoking an outage constraint set, AEMO invoking a soft-ramping constraint (`#R`) or Negative Residue Management clamp, or a rapid regional load shift crossing from a thermal boundary onto a lower transient-stability or voltage-stability boundary.
2. **Path B (Same-equation LHS generator ramp):** The exact same constraint equation leads at both $t - 30\text{ min}$ and $t$, and the drop is explained mechanically by scheduled and semi-scheduled generating units ramping along that equation's fixed left-hand-side coefficients: $\Delta \text{LHS}_{\text{gen}} = \sum_i s_{c,i} (P_{i,t} - P_{i,t-6})$.
3. **Path C (Same-equation RHS and Z-term shift):** The exact same constraint equation leads at both endpoints, but the drop comes from a reduction in the equation's right-hand side $\text{RHS}_{c,t}$ (dynamic line rating reductions from rising ambient temperature or falling wind speed, loss of synchronous inertia units, or dynamic stability curve shifts) or non-generator left-hand-side terms $Z_{c,t}$ (such as parallel interconnector flows or FCAS enablement).

Previous internal studies decomposed LHS versus RHS versus equation switches only inside small hand-picked case studies of 70 to 90 events per link. That sample restriction left open whether generator ramps or exogenous equation switches dominate across the full population of market contractions. Here we execute the exact three-way decomposition across all 44,185 sharp contraction episodes recorded over 24 months across all six NEM interconnectors.

### 5.1 Full-population contraction detection and accounting identity

To ensure every season and every corridor is evaluated on an identical statistical footing, a sharp contraction onset is detected whenever a link's 30-minute directional capacity change $\Delta_{30} C_t = C_t - C_{t-6}$ falls below zero and equals or exceeds that link-direction's monthly 90th-percentile contraction threshold, with contiguous five-minute triggers grouped into a single onset episode (keeping the peak drop within each episode). For every episode $e$ with total contraction drop $D_e = -\Delta_{30} C_e > 0$:

- If the leading constraint equation ID at onset $t$ differs from the leading equation ID at $t - 30\text{ min}$, 100% of $D_e$ is attributed to Equation Switch (Path A).
- If the same constraint equation leads at both endpoints, the net fixed-equation generator tightening $G_e = \max\left(0, -\sum_i s_{c,i,t} \Delta_{30} P_{i,t}\right)$ is clipped to $[0, D_e]$ and attributed to Same-Equation LHS Generator Ramp (Path B), while the remaining $R_e = D_e - \min(G_e, D_e)$ is attributed to Same-Equation RHS / Z-Term Shift (Path C).

Because the three components sum identically to $D_e$ on every episode, cumulative megawatt shares across each link-direction are exact, auditable, and free of double-counting.

### 5.2 The six-link split: switches dominate megawatts, while LHS ramps concentrate on VNI and QNI

Aggregating across all 44,185 sharp contraction episodes and 9.04 million cumulative contraction megawatts across the six interconnectors delivers a clear headline verdict: equation switches account for 43.5% of all contraction megawatts (occurring in 35.5% of episodes, meaning switch episodes are systematically larger than fixed-equation episodes), same-equation RHS and Z-term shifts account for 32.3%, and same-equation LHS generator ramps account for 24.3%. Underneath that NEM-wide average, however, individual corridors diverge dramatically.

| Link & direction | Sharp episodes (24m) | Switch episodes (%) | Switch share of drop MW (%) | Same-eq LHS gen share (%) | Same-eq RHS / Z share (%) | Median switch drop (MW) | Median same-eq LHS (MW) | Median same-eq RHS (MW) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VNI forward | 4,029 | 46.7% | 49.7% | 37.3% | 13.0% | 384 | 260 | 50 |
| VNI reverse | 3,455 | 42.0% | 53.0% | 28.5% | 18.5% | 433 | 185 | 29 |
| QNI forward | 3,122 | 24.6% | 36.5% | 33.5% | 30.0% | 210 | 87 | 70 |
| QNI reverse | 4,300 | 27.8% | 31.2% | 25.3% | 43.5% | 182 | 11 | 124 |
| Heywood forward | 3,859 | 50.8% | 53.0% | 22.4% | 24.6% | 246 | 93 | 125 |
| Heywood reverse | 3,867 | 42.0% | 45.2% | 27.6% | 27.2% | 276 | 84 | 133 |
| Directlink forward | 4,395 | 2.5% | 2.5% | 4.3% | 93.3% | 63 | 0 | 57 |
| Directlink reverse | 4,354 | 30.8% | 32.7% | 13.3% | 54.1% | 67 | 0 | 49 |
| Murraylink forward | 3,740 | 52.6% | 54.9% | 12.5% | 32.6% | 95 | 0 | 73 |
| Murraylink reverse | 3,365 | 56.0% | 57.7% | 15.7% | 26.6% | 100 | 7 | 78 |
| Basslink forward | 2,625 | 26.0% | 28.7% | 1.5% | 69.8% | 192 | 0 | 176 |
| Basslink reverse | 3,074 | 27.0% | 28.3% | 6.0% | 65.7% | 185 | 0 | 160 |

Four structural regimes emerge cleanly from the six-link decomposition:

#### 5.2.1 VNI: the generator-ramp and equation-switch battleground
VNI is the corridor where scheduled and semi-scheduled generator ramps exert the largest direct leverage over fixed-equation limits. On VNI forward (VIC to NSW), same-equation LHS generator ramps account for 37.3% of all contraction megawatts, with a median same-equation LHS drop of 260 MW versus just 50 MW from RHS shifts (13.0% total share). The remaining 49.7% comes from active-leader equation switches (median drop 384 MW). On VNI reverse, equation switches account for 53.0% of contraction MW (median 433 MW), while LHS generator ramps explain 28.5% (median 185 MW) and RHS shifts just 18.5%. In physical terms, VNI's constraint envelope is relatively insensitive to gradual ambient RHS drift once a thermal or voltage equation is active; instead, VNI moves abruptly either because a major unit (such as Tumut 3, Upper Tumut, or a cluster of south-western NSW solar farms) ramps hard inside the active equation, or because an outage or stability boundary takes over completely.

#### 5.2.2 QNI: balanced three-way mechanics forward, RHS-dominated reverse
On QNI forward (NSW to QLD), all three paths contribute roughly one-third of total contraction megawatts: equation switches (36.5%), same-equation LHS generator ramps (33.5%), and same-equation RHS/Z-term shifts (30.0%). On QNI reverse (QLD to NSW), however, RHS and Z-term shifts take the lead at 43.5% (median same-equation RHS drop of 124 MW versus only 11 MW median LHS generator ramp), alongside 31.2% from equation switches and 25.3% from LHS ramps. That 43.5% RHS share directly mirrors the Chapter 3 audit: QNI southward transfer is heavily governed by dynamic thermal ratings, FCAS co-optimisation terms, and voltage/stability nomograms whose right-hand sides shift dynamically with Queensland load, inertia, and Directlink parallel flow even when no single generator ramps sharply.

#### 5.2.3 Heywood and Murraylink: high equation-switch churn across the southern ring
Along the Victoria to South Australia border, equation switching is the dominant contraction driver. Over half of all contraction megawatts on Heywood forward (53.0%), Murraylink forward (54.9%), and Murraylink reverse (57.7%) occur when a different constraint equation takes over within 30 minutes, alongside 45.2% on Heywood reverse. Heywood's remaining same-equation contractions split almost evenly between LHS generator ramps (22.4% forward, 27.6% reverse) and RHS/Z shifts (24.6% forward, 27.2% reverse), reflecting the twin pressures of rapid wind/battery ramping across western Victoria and South Australia plus discrete synchronous-unit and series-capacitor RHS steps.

#### 5.2.4 Directlink and Basslink: RHS, cable-rating, and bidding dominance
Directlink and Basslink confirm the HVDC physics diagnosed in Chapter 3. On Directlink forward, 93.3% of contraction megawatts sit in the same-equation RHS/Z bucket (with LHS generator ramps at just 4.3% and equation switches at 2.5%), because transfer changes are overwhelmingly driven by cable ambient ratings, MNSP offer changes, and local runback set-points rather than remote AC generator ramps. Basslink displays the same signature: 69.8% of forward contraction MW and 65.7% of reverse contraction MW occur via RHS/Z shifts (median 160 to 176 MW), with LHS generator ramps contributing only 1.5% forward and 6.0% reverse.

### 5.3 Why this split matters for forecasting architecture

> [!WARNING] Avoiding Feature Overfitting on Exogenous Switches
> A forecasting model trained to predict raw 30-minute limit drops using only generator output lags and solar/wind forecasts is structurally blind to 43.5% of all contraction megawatts (equation switches) and 32.3% of RHS/Z shifts. Worse, if the model is not conditioned on planned outage invocations and constraint-set states, tree-based learners will spuriously attribute large switch drops (such as a 433 MW VNI reverse switch) to whichever generator happened to move in the same five-minute interval.

The operational takeaway is direct: separate the prediction target by mechanism. On VNI and QNI forward, fixed-equation generator-ramp features (solar cloud ramps, Snowy hydro evening dispatches, and battery charge-discharge cycles) explain 29% to 37% of contraction megawatts and offer genuine short-horizon predictability when combined with predispatch generation trajectories. On Heywood, Murraylink, and VNI switch episodes, capturing the remaining 45% to 58% requires integrating the Network Outage Scheduler (NOS) and constraint-set calendars (Flagship Edition B) alongside cross-link contagion indicators. Chapter 6 maps exactly how those contractions propagate across borders.

## Chapter 6 · Cross-Link Contraction Cascades and NRM Clamping

Interconnectors in the NEM do not operate as six independent pipes. They form a long, weakly meshed north-to-south alternating-current spine from northern Queensland to South Australia, braced by parallel HVDC links and linked across Bass Strait to Tasmania. When a transmission outage invokes a constraint set in southern New South Wales or western Victoria, or when a synoptic weather front sweeps wind and solar output across state borders, limit contractions rarely stay confined to a single corridor. At the same time, when regional prices invert against physical loop flows, AEMO's automated Negative Residue Management (NRM) system and forced-flow constraints clamp transfer ceilings below zero, turning physical congestion into direct financial losses for settlement-residue holders.

This chapter maps the complete 6x6 cross-link contraction cascade matrix within a plus-or-minus 30-minute co-occurrence window and isolates the exact share of forced-negative limits and negative settlement residues attributable to counter-price flows and explicit NRM clamping.

### 6.1 The six-by-six contraction cascade matrix

To test whether sharp contractions cluster across borders above random chance, every five-minute interval $t$ on each link $A$ was marked as an active contraction onset window if link $A$ logged a sharp contraction in either direction within $[t - 30\text{ min}, t + 30\text{ min}]$. For each ordered pair $(A, B)$, we compute the conditional probability $P(B \text{ contracts within } \pm 30\text{ min} \mid A \text{ contracts})$ and divide it by link $B$'s unconditional 60-minute window occupancy baseline to obtain the cascade lift ratio. A lift ratio of $1.00\times$ indicates complete statistical independence; values meaningfully above $1.00\times$ quantify genuine multi-corridor contagion.

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

Two notable financial insights emerge immediately from this attribution:

#### 6.2.1 VNI's -$98.5 million negative-residue engine is loop-flow forcing, not just NRM
Between September 2024 and August 2026, negative settlement residues on the NSW to VIC directional settlement bucket totalled -$98.5 million, and -$97.4 million (98.9%) of that total accumulated strictly during the 26,949 intervals when VNI's forward export limit was forced negative ($U_t < 0$, forcing southward NSW to VIC flow). Fully 82.7% of all VNI forward forced-negative intervals occurred during counter-price flow (NSW priced higher than Victoria while VNI was physically forced to flow from NSW into Victoria). Yet only 0.5% of those intervals carried an explicit NRM or soft-ramp setter equation.

Why does VNI haemorrhage -$97.4 million in counter-price negative residues without an explicit NRM clamp setting the bound? Because the culprit is physical thermal and voltage loop-flow forcing in southern New South Wales and Snowy (such as thermal constraints on the Jindera-Wodonga and Lower Tumut-Wagga corridors, or Snowy-Murray voltage bounds). When northern and southern NSW thermal or stability equations require VNI to carry negative (southward) flow to prevent line overloads while New South Wales clears at a steep premium above Victoria, AEMO cannot invoke NRM to clamp flow back to zero without violating physical power-system security. Security constraints always override economic NRM clamping.

#### 6.2.2 Heywood's -$19.9 million negative-residue profile is heavily NRM-intervened
Contrast VNI with Heywood reverse (SA to VIC), where negative directional limits ($L_t < 0$) force eastward-to-westward VIC to SA flow. Over two years, Heywood reverse recorded 30,770 forced-negative intervals (14.6% of the entire sample), during which 41.3% were counter-price and 42.3% carried an explicit NRM or ramp setter equation. Those forced intervals accounted for -$18.8 million out of -$19.9 million (94.5%) of negative settlement residue on the VIC to SA settlement bucket. At the exact same time, parallel Murraylink reverse logged 86,013 forced-negative intervals (40.9%), capturing -$18.4 million of the same pooled VIC to SA negative-residue exposure.

On Basslink, by contrast, forced-negative forward limits occur in 50.1% of all intervals (105,402 intervals), yet only 5.8% are counter-price and negative residues are negligible (-$0.04m). That cleanly proves that Basslink's negative upper limit is predominantly a *with-price* hydroelectric import regime (Victoria exporting cheaper mainland power into Tasmania while cable rules or FCSPS hold the forward limit negative), rather than a counter-price congestion trap.

Part II has established when transfer envelopes contract, why they contract (switches versus LHS ramps versus RHS shifts), how contractions cascade across the 6x6 grid, and where forced-negative limits generate -$118 million in VNI and VIC-SA negative residues. Part III now drills down to the individual asset level: which specific generating units and constraint equations actually drive economic congestion rent, and how the surge of grid-scale batteries is altering five-minute network physics.

## Chapter 7 · Economic Versus Mechanical Generator and Constraint Influence

A persistent flaw in legacy constraint-pressure research is the megawatts-without-dollars disconnect. Ranking generators by summing every five-minute move $|s_{c,i,t} \Delta P_{i,t}|$ across two years treats a 100 MW cloud ripple on a midday solar farm during an unconstrained $2/MWh afternoon identically to a 100 MW evening ramp on a Snowy hydro turbine during a binding $450/MWh peak. Similarly, ranking constraint equations by how many intervals they sat as the tightest non-binding leader conflates harmless idle ceilings with the handful of thermal, voltage, and stability equations that carry hundreds or thousands of dollars per megawatt-hour in binding shadow prices.

Re-weighting the exact same two-year five-minute unit-pressure and constraint-population panels by tight-headroom congestion rent ($H_{k,t} \le 50\text{ MW}$ multiplied by positive directional regional price spread divided by 12) and cumulative binding shadow rent reshuffles the leaderboard on every single interconnector in the NEM.

### 7.1 How economic weighting reshuffles the generator leaderboard

Across all 446 active participating generating units, weighting mechanical constraint moves by concurrent tight-headroom congestion rent produces dramatic rank promotions for dispatchable hydro, gas peakers, utility batteries, and wind farms situated behind high-spread evening bottlenecks, while demoting slack-hour solar and baseload units whose mechanical movements occur mostly when regional prices are converged.

| Interconnector | #1 Mechanical unit (all MW-obs) | #1 Economic unit (rent-weighted) | Tech | Rent-weighted pressure ($m) | Rank shift (econ vs mech) | Tight-headroom share (%) | Evening Ramp share (%) |
|---|---|---|---|---:|---:|---:|---:|
| VNI | `MURRAY` (Hydro) | `TUMUT3` | Hydro | $103.7m | +2 (#3 to #1) | 45.9% | 63.0% |
| QNI | `NEWENSF2` (Solar) | `TUMUT3` | Hydro | $82.4m | +5 (#6 to #1) | 62.5% | 54.5% |
| Heywood | `KIAMSF1` (Solar) | `KESSB1` | BESS | $6.0m | +4 (#5 to #1) | 56.6% | 18.1% |
| Directlink | `METZSF1` (Solar) | `TUMUT3` | Hydro | $85.8m | +1 (#2 to #1) | 89.9% | 46.4% |
| Murraylink | `MURRAY` (Hydro) | `LIMOSF11` | Solar | $5.8m | +2 (#3 to #1) | 90.9% | 19.2% |
| Basslink | `MREHA3` (BESS) | `MREHA3` | BESS | $3.0m | +0 (#1 to #1) | 28.3% | 22.3% |

The structural reshuffling inside each of the three flagship AC corridors illustrates why trading desks cannot rely on unweighted mechanical counts:

#### 7.1.1 VNI: Tumut 3 and Upper Tumut overtake Murray, while gas peakers and NSW wind jump 25 to 64 ranks
On a pure mechanical basis, `MURRAY` (Snowy Hydro's Victorian-side power station) sits at #1 on VNI with 9.40 million cumulative MW-observations, ahead of `LIMOSF11` (#2) and `TUMUT3` (#3). Once weighted by tight-headroom congestion rent, `MURRAY` drops thirteen places to #14 ($9.76m), because only 18.6% of Murray's mechanical constraint movement occurs during tight-headroom intervals. By contrast, `TUMUT3` surges to #1 with $103.7m (nearly three times larger than #2 `UPPTUMUT` at $34.8m and #3 `LIMOSF11` at $29.4m), because 45.9% of Tumut 3's movement occurs under tight headroom and 63.0% concentrates inside the high-spread Evening Ramp (16:00 to 20:55).

Even sharper rank jumps appear among southern New South Wales wind farms, gas peakers, and grid-scale batteries that enter outage and evening-peak equations:
- `RYEPARK1` (wind) jumps +45 ranks from #52 mechanical to #7 economic ($13.8m), with 68.8% of its moves inside tight headroom and 41.4% in the Evening Ramp.
- `COLWF01` (wind) climbs +52 ranks (#67 to #15, $9.1m) and `BOCORWF1` climbs +64 ranks (#92 to #28, $5.5m).
- The Uranquinty gas peakers (`URANQ13`, `URANQ11`, `URANQ14`, `URANQ12`) jump +23 to +31 ranks into the top 30 economic drivers ($5.2m to $7.5m each), driven by 56% to 66% Evening Ramp concentration precisely when NSW minus VIC spreads spike.
- Meanwhile, Victorian-side wind farms that sit on slack equations suffer steep demotions: `MUWAWF1` falls -34 ranks (#8 to #42, $3.1m), `MOORAWF1` falls -25 ranks (#20 to #45, $2.8m), and `KIAMSF1` falls -22 ranks (#11 to #33, $4.9m).

#### 7.1.2 QNI and Directlink: NSW spine hydro and wind displace New England solar
On QNI, unweighted mechanical rankings placed the New England solar farms `NEWENSF2` (#1), `NEWENSF1` (#2), `SAPHWF1` (#3), and `METZSF1` (#5) at the top of the table. Economic weighting demotes `NEWENSF2` by -7 places to #8 ($7.9m), `NEWENSF1` by -8 places to #10 ($7.3m), `METZSF1` by -14 places to #19 ($5.7m), and `SAPHWF1` by -31 places to #34 ($3.5m), because only 18% to 25% of their solar midday oscillations coincide with tight QNI headroom.

In their place, `TUMUT3` rises +5 places to #1 on QNI ($82.4m) and `UPPTUMUT` rises +10 places to #2 ($22.3m), followed by NSW wind farms `RYEPARK1` (+27 ranks to #3, $14.9m) and `COLWF01` (+48 ranks to #4, $12.2m) and south-west NSW solar `DARLSF1` (+33 ranks to #5, $10.8m). The reason Snowy and southern NSW units dominate QNI economic rent is subtle and commercially decisive: when NSW evening scarcity binds both NSW borders simultaneously via system-wide NSW stability and voltage equations, Snowy hydro and southern NSW generation shifts directly govern the high-spread intervals on QNI and Directlink (`TUMUT3` is also #1 economic on Directlink at $85.8m, with 89.9% tight-headroom coincidence).

#### 7.1.3 Heywood, Murraylink, and Basslink: grid-scale batteries take the #1 spot
Along the southern and subsea borders, battery energy storage systems have already overtaken legacy solar and wind farms as the #1 economic constraint influencers. On Heywood (V-SA), `KESSB1` (Koorangie / Kerang-corridor BESS) jumps +4 places from #5 mechanical to #1 economic ($6.0m) ahead of `KIAMSF1` (#2, $4.7m), `WEMENSF1` (#3, $4.3m), `BANN1` (#4, $4.2m), and `MUWAWF1` (#5, $4.1m), while `VBB1` (Victorian Big Battery) leaps +16 places to #7 ($3.5m), `LIMBESS1` leaps +42 places to #13 ($2.7m), and South Australian `TB2B1` leaps +63 places to #18 ($2.0m). On Basslink, the Melbourne Renewable Energy Hub battery units `MREHA3` (#1, $3.0m), `VBB1` (#2, $1.4m), `MREHA1` (#3, $1.2m), and `MREHA2` (#5, $1.1m) occupy four of the top five economic slots ahead of `MURRAY` (#6, $0.85m). On Murraylink, south-western NSW solar (`LIMOSF11` #1 at $5.8m, `CUSF1` #2 at $5.5m) shares the top tier with `MURRAY` (#3, $5.0m) and Victorian batteries `KESSB1` (#4, +20 ranks, $4.6m) and `VBB1` (#6, +45 ranks, $3.9m).

### 7.2 The shadow-rent constraint register: separating real bottlenecks from paper leaders

Applying the same economic discipline to constraint equations (ranking by cumulative 24-month binding shadow rent, equal to binding intervals multiplied by mean absolute marginal value divided by 12, after removing synthetic zero-flow linear-programme penalty constraints) reveals an equally stark divergence from non-binding leader counts.

| Link | Top shadow-rent constraint ID | Direction | Category | Binding intervals | Leading intervals | Mean \|MV\| ($/MWh) | 24m shadow rent ($k/MW) | Physical bottleneck |
|---|---|---|---|---:|---:|---:|---:|---|
| Directlink | `N_X_MBTE_3A` | Reverse | Other / MNSP | 13,115 | 0 | $3,939.3 | $4,305k | Northern NSW Directlink transfer bound |
| Murraylink | `SVML_ROC_80` | Reverse | ROCOF / HVDC | 3,059 | 0 | $12,325.5 | $3,142k | SA-VIC Murraylink rate-of-change bound |
| Murraylink | `V^SML_BUDP_3` | Forward | Voltage Stab. | 4,688 | 8,152 | $2,261.8 | $884k | Buronga-Balranald/Darlington Pt 220 kV outage voltage collapse |
| QNI | `N^^Q_TW_330_BUS1_B1` | Reverse | Voltage Stab. | 810 | 0 | $7,307.6 | $493k | Tamworth 330 kV Bus 1 outage voltage limit |
| Murraylink | `S>NIL_MHNW1_MHNW2` | Reverse | Thermal | 42,794 | 0 | $132.6 | $473k | Monash to North West Bend 132 kV system-normal thermal |
| VNI | `N>>NIL_060_051` | Reverse | Thermal | 17,567 | 594 | $182.8 | $268k | Jindera-Wodonga (60) 330 kV for trip of Wagga-Lower Tumut (051) |
| Heywood | `V::S_SETB_TBSE_2` | Forward | Transient Stab. | 2,580 | 0 | $873.7 | $188k | South East-Tailem Bend 275 kV outage transient stability |
| Heywood | `VS_600_TEST` | Forward | Other / Test | 8,048 | 19,876 | $271.0 | $182k | Heywood 600 MW upgrade testing cap |
| VNI | `N>>BDBU_970_051` | Forward | Thermal | 4,865 | 5,266 | $381.3 | $155k | Bundey-Buronga (6F) outage; Burrinjuck-Yass (970) thermal |
| Basslink | `V_T_NIL_FCSPS` | Reverse | Other / FCSPS | 27,936 | 0 | $44.5 | $104k | Basslink VIC to TAS FCSPS load-enabled cap |
| QNI | `NRM_QLD1_NSW1` | Reverse | NRM | 752 | 7 | $1,542.1 | $97k | Negative Residue Management QLD to NSW clamp |
| QNI | `QN+RAISE_NIL` | Reverse | FCAS | 1,700 | 48,446 | $682.0 | $97k | QLD to NSW FCAS raise enablement for loss of 750 MW NSW unit |

Look closely at the contrast between the `Binding intervals` and `Leading intervals` columns in the table above. On QNI, `QN+RAISE_NIL` led the conditional envelope for 48,446 intervals, yet it actually bound in only 1,700 intervals, generating $96.6k/MW of shadow rent. Meanwhile, the Tamworth 330 kV Bus 1 voltage outage equation `N^^Q_TW_330_BUS1_B1` bound for only 810 intervals (less than 0.4% of the two-year sample), yet carried a mean marginal value of $7,307.6/MWh, generating $493.3k/MW of shadow rent, more than five times higher than the perennial leader `QN+RAISE_NIL`.

The exact same asymmetry governs VNI and Heywood:
- On VNI, system-normal `N>>NIL_060_051` (Jindera-Wodonga thermal) generated $267.6k/MW across 17,567 binding intervals, followed by the Bundey-Buronga 6F outage thermal equation `N>>BDBU_970_051` ($154.6k/MW, $381.3/MWh mean `|MV|`), the Lower Tumut-Yass (03) outage transient-stability equation `N::N_LTYS_2` ($69.2k/MW, $1,503.7/MWh mean `|MV|` in just 552 intervals), and system-normal Wagga-Lower Tumut voltage stability `N^^N_NIL_WGLT` ($32.7k/MW across 12,576 binding intervals).
- On Heywood, the EnergyConnect commissioning discretionary cap `I_6F_SN_150` (150 MW Bundey to Buronga 6F limit) led the reverse envelope for 73,858 intervals, yet bound for 3,442 intervals ($59.2k/MW), whereas the South East to Tailem Bend 275 kV outage transient-stability equation `V::S_SETB_TBSE_2` bound for 2,580 intervals at $873.7/MWh mean `|MV|` to generate $187.8k/MW, and the Heywood 600 MW test cap `VS_600_TEST` generated $181.7k/MW across 8,048 binding intervals.

> [!TAKEAWAY] Commercial Principle for Desk Monitoring
> Frequent non-binding leaders tell engineers which boundary sits closest to normal dispatch; cumulative shadow rent tells traders which equations pay or cost real money. Outage-specific voltage and transient stability equations (`N^^Q_TW_330_BUS1_B1`, `V^SML_BUDP_3`, `N>>BDBU_970_051`, `V::S_SETB_TBSE_2`, `N::N_LTYS_2`) routinely generate more shadow rent in 500 to 4,800 outage intervals than system-normal thermal leaders accumulate in 50,000 intervals.

One asset class in the economic leaderboard deserves its own dedicated forensic chapter because its rapid five-minute operational profile breaks the traditional 30-minute ramping assumptions baked into legacy NEM models: utility-scale Battery Energy Storage Systems (BESS). Chapter 8 isolates that exact fast-ramp signature.

## Chapter 8 · Utility BESS Fast-Ramp Signatures and Technology Profiles

Between 2024 and 2026, grid-scale Battery Energy Storage Systems transitioned from peripheral frequency-control assets into primary drivers of five-minute interconnector constraint physics across the NEM. Unlike coal boilers limited by multi-hour thermal ramp rates, or utility solar farms whose output follows a smooth diurnal arc punctuated by passing clouds, bidirectional batteries execute full-swing reversals from maximum charging to maximum discharging within a single five-minute dispatch interval. A 200 MW battery switching from -180 MW (charging during a negative-price solar dip) to +180 MW (discharging into a tight evening ramp or FCAS contingency) injects a 360 MW net change in five minutes, instantly shifting any thermal or voltage constraint equation in which it carries a material participation factor.

Earlier constraint studies grouped bidirectional units alongside generic "Other" or thermal classes and evaluated generator moves strictly over 30-minute rolling windows. Averaging a battery over 30 minutes hides its defining physical hazard: a battery that charges hard at 17:15, discharges hard at 17:20, and returns to neutral at 17:40 shows near-zero 30-minute net movement while having abruptly rattled a tight interconnector boundary across four consecutive dispatch intervals. By explicitly identifying all bidirectional storage units from standing dispatch registrations and computing five-minute step impulse distributions alongside 30-minute exposure and congestion-rent shares, we isolate the exact BESS footprint across all six corridors.

### 8.1 Technology-class five-minute impulse severity and evening-ramp concentration

Comparing the 95th-percentile five-minute step impulse (`|Δbound|` over a single five-minute interval) and Evening Ramp exposure concentration across all seven technology classes reveals how sharply utility batteries stand apart from thermal and variable renewable fleets.

| Link | Active BESS units | BESS share of all MW-obs (%) | BESS share of rent-weighted pressure (%) | BESS share of contraction-onset tightening (%) | BESS P95 5-min impulse (MW) | Solar P95 5-min impulse (MW) | BESS Evening Ramp share (%) | BESS Solar Midday share (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VNI | 38 | 9.9% | 7.1% | 8.4% | 24.7 | 27.6 | 30.1% | 44.3% |
| QNI | 34 | 6.8% | 5.2% | 7.6% | 18.2 | 16.2 | 32.8% | 46.6% |
| Heywood | 43 | 12.8% | **20.4%** | **15.1%** | 22.2 | 19.2 | 26.0% | 41.6% |
| Directlink | 27 | 3.0% | 5.2% | 4.0% | 17.4 | 26.9 | 29.9% | 58.8% |
| Murraylink | 41 | 10.2% | **15.9%** | 9.7% | 27.0 | 42.9 | 19.8% | 54.6% |
| Basslink | 26 | **56.4%** | **32.7%** | **55.1%** | **100.0** | 22.4 | 25.3% | 37.9% |

Three empirical findings define the operational role of BESS inside the NEM constraint stack:

#### 8.1.1 Economic punch far exceeds mechanical share on southern corridors
On Heywood (V-SA), 43 active BESS units account for 12.8% of raw mechanical MW-observations, yet generate 20.4% of all congestion-rent-weighted pressure ($22.0m) and 15.1% of all fixed-equation contraction-onset tightening. That 1.6x economic-to-mechanical multiplier reflects arbitrage timing: batteries do not drift randomly; their bidding engines actively seek out the exact tight-headroom price-separation intervals where regional spreads widen, meaning their megawatt swings disproportionately coincide with binding congestion.

The same economic amplification appears on Murraylink (41 active BESS units, 10.2% mechanical share rising to 15.9% rent-weighted share, $20.8m) and Directlink (27 BESS units, 3.0% mechanical share rising to 5.2% rent-weighted share, $22.2m). On Basslink, 26 Victorian BESS units (led by `MREHA3`, `VBB1`, `MREHA1`, `MREHA2`, and `HBESS1`) dominate the generic constraint equations outright, representing 56.4% of all mechanical MW-observations, 55.1% of contraction-onset tightening, and 32.7% of congestion-rent-weighted pressure, with a P95 five-minute impulse of 100.0 MW per step.

#### 8.1.2 Bimodal diurnal footprint: midday charging plus evening discharging
Every legacy technology in the NEM exhibits a unimodal diurnal profile: solar peaks overwhelmingly during Solar Midday (52% to 61% of its constraint pressure), gas peakers peak overwhelmingly in the Evening Ramp (52% to 60% on VNI, QNI, and Directlink), and hydro concentrates in the Evening Ramp (40% to 47% on VNI, QNI, Directlink, and Basslink). Grid-scale batteries are uniquely bimodal. Across VNI, QNI, Heywood, and Directlink, BESS units deliver 42% to 59% of their constraint pressure during Solar Midday (rapidly ramping into and out of negative-price charging as solar prices flip across $0/MWh) and a second large wave of 26% to 33% during the Evening Ramp (executing high-margin discharge ramps into regional scarcity).

Because battery charging carries a negative generation sign ($P_{i,t} < 0$), a battery entering a thermal equation on the congested exporting side actually *relieves* the interconnector limit while charging at noon, and then *double-tightens* the limit at 16:30 when it first stops charging (removing counter-flow relief) and immediately switches to discharging (adding forward loop flow). That sign reversal across zero explains why units like `KESSB1` on Heywood (P95 5-min impulse 22.2 MW, #1 economic rank), `VBB1` on Heywood and Murraylink, and `RIVNB2` / `RESS1` on VNI (#11 and #12 economic at $10.4m and $10.3m) sit at the very heart of intraday limit volatility.

### 8.2 Technology-class composition of congestion-rent pressure across all six links

Stepping back from batteries alone, comparing the full seven-technology breakdown of congestion-rent-weighted pressure across all six interconnectors exposes the distinct regional fuel mix driving economic congestion along each border.

| Link | Solar rent share (%) | Hydro rent share (%) | Wind rent share (%) | BESS rent share (%) | Coal rent share (%) | Gas rent share (%) | Total 24m rent weight ($m) |
|---|---:|---:|---:|---:|---:|---:|---:|
| VNI | **39.9%** | **26.7%** | 19.7% | 7.1% | 1.5% | 4.5% | $586.6m |
| QNI | **33.4%** | **24.2%** | 22.2% | 5.2% | 6.1% | 4.2% | $450.4m |
| Heywood | 30.5% | 2.4% | **44.6%** | **20.4%** | 0.7% | 1.0% | $107.8m |
| Directlink | **32.3%** | **26.3%** | 22.5% | 5.2% | 4.8% | 4.9% | $426.7m |
| Murraylink | **45.1%** | 6.4% | **29.3%** | **15.9%** | 0.9% | 2.2% | $130.9m |
| Basslink | 27.0% | 8.8% | 28.7% | **32.7%** | 2.0% | 0.1% | $27.7m |

Four regional economic signatures emerge cleanly from the six-link technology stack:

1. **VNI is a Solar + Hydro + Wind triad (86.3% combined):** Utility solar accounts for **39.9%** ($234.1m) of rent-weighted pressure (concentrated in the Riverina and south-western NSW solar belt: Limondale, Sunraysia, Darlington Point, Avonlie, Coleambally, Finley, Hillston), Snowy hydro contributes **26.7%** ($156.7m, led by Tumut 3 and Upper Tumut), and wind adds **19.7%** ($115.3m). Coal units account for just **1.5%** of VNI economic pressure, while gas peakers contribute **4.5%** ($26.5m, concentrated almost entirely during evening scarcity).
2. **QNI and Directlink mirror the NSW spine triad, with Queensland coal demoted economically:** On QNI, coal accounts for **20.0%** of raw mechanical MW-observations (driven by Stanwell, Gladstone, Callide, and Mount Piper ramping), yet drops to just **6.1%** ($27.4m) of congestion-rent-weighted pressure. Instead, Solar (**33.4%**, $150.5m), Hydro (**24.2%**, $109.1m), and Wind (**22.2%**, $99.9m) account for **79.8%** of QNI economic pressure, closely echoed on parallel Directlink (32.3% Solar, 26.3% Hydro, 22.5% Wind).
3. **Heywood and Murraylink are the Wind + Solar + BESS frontier (90% to 95% combined):** Along the Victoria to South Australia border, thermal coal and gas contribute less than **3.1%** of economic pressure combined. On **Heywood**, Wind (**44.6%**), Solar (**30.5%**), and BESS (**20.4%**) drive **95.5%** of all rent-weighted pressure. On **Murraylink**, Solar (**45.1%**), Wind (**29.3%**), and BESS (**15.9%**) drive **90.3%**. Any forecasting or valuation model for VIC to SA interconnector limits that treats thermal baseload as the dominant network driver is modelling the 2015 grid rather than the 2026 grid.
4. **Basslink's generic-equation pressure is split three ways across BESS (32.7%), Wind (28.7%), and Solar (27.0%):** Even though Tasmania is a hydro-dominated state, the Victorian-side AC constraint equations that intersect Basslink are overwhelmingly driven by Victorian grid-scale batteries (`MREHA3`, `VBB1`, `MREHA1`, `MREHA2`, `HBESS1`), western Victorian wind, and northern Victorian solar, with hydro contributing **8.8%** (carrying a very high 115.2 MW P95 five-minute step impulse when Tasmanian or Snowy hydro steps sharply).

### 8.3 Modelling rules for fast-ramping BESS inside limit forecasters

> [!WARNING] Why Standard 30-Minute Lag Features Miss Battery Volatility
> Incorporating BESS units into a 30-minute or half-hourly limit model via simple 30-minute rolling differences understates their risk by two mechanisms: first, intra-half-hour charge-to-discharge reversals cancel out in 30-minute averages even when they create severe five-minute price spikes; second, BESS output is state-of-charge (SOC) and price-threshold driven rather than weather driven.

Quantitative teams extending short-horizon limit forecasters on Heywood, Murraylink, VNI, and Basslink should therefore apply three targeted engineering rules:
- **Track aggregate corridor BESS net position and headroom-to-swing:** Sum active battery output $P^{\text{BESS}}_{c,t}$ inside each leading constraint equation separately from solar and wind, and track the distance to nameplate charge/discharge bounds so the model knows when local batteries have exhausted midday charging capacity and are poised to flip to discharge.
- **Monitor price-flip trigger proximity:** Because BESS units flip aggressively when regional dispatch prices cross from negative to positive (midday) or cross the $150 to $300/MWh evening-arbitrage threshold, interaction terms between battery sensitivity $\sum_{i \in \text{BESS}} |s_{c,i,t}|$ and predispatch price-ramp gradients capture onset risk far better than autoregressive output lags.
- **Retain five-minute peak-impulse metrics in tight-target evaluation:** Consistent with repository half-hour target semantics (where the tight half-hour limit is the *minimum* across all six five-minute intervals, never the mean), a single five-minute battery reversal that cuts a limit by 100 MW defines the entire half-hour tight target even if the remaining five intervals recover.

Part IV now brings together the standalone compressed Event Atlases v2 for VNI, QNI, and Heywood and specifies the exact operational feature-engineering contract bridging this constraint-pressure atlas to downstream forecasting and valuation models.

## Chapter 9 · Event Atlas Synthesis and Leak-Free Modelling Playbook

Statistical aggregates across 1.26 million five-minute link-intervals establish structural patterns, but trading desks and model builders also need to inspect real physical episodes minute by minute to verify how constraint switches, generator ramps, cloud transients, and price spikes unfold together. To preserve full five-minute forensic inspection without forcing analysts to download or render 25-megabyte legacy files, Wave 1 simultaneously rebuilt the three standalone interactive Event Atlases for VNI, QNI, and Heywood (V-SA) as compressed Version 2 deliverables (`reports/event_atlases_v2/`), accompanied by rewritten Virtual Barrels prose companions.

### 9.1 Standalone compressed Event Atlases v2: payload efficiency and headline forensic findings

Legacy Event Atlas HTML builds embedded raw uncompressed five-minute JSON arrays inline, inflating single-link files to 20 to 27 MB and degrading browser startup. Version 2 preserves 100% of the case windows, five-minute telemetry series, equation-factor reconstructions, coal-availability proxies, rooftop solar estimates, and hourly weather diagnostics while applying rounded columnar encoding, gzip compression, and native browser `DecompressionStream` unpacking at load time.

| Event Atlas v2 | Legacy HTML size | Version 2 HTML size | Size reduction | Detailed windows (contraction + price-only) | Total 24m detections (incidents) | Matched 1-hr peak price jump diff (95% block CI) | Exact-version 100% matched cases | Top case-level gross tightening unit |
|---|---:|---:|---:|---:|---:|---|---:|---|
| VNI (`vni_event_atlas_v2.html`) | 26.64 MB | **7.36 MB** | **-72.4%** | 103 (91 + 12) | 7,486 (5,379) | **+$94.97/MWh** ($58.27 to $136.83) | 87 / 91 (95.6%) | `TUMUT3` (35,038 MW gross) |
| QNI (`qni_event_atlas_v2.html`) | 25.04 MB | **7.04 MB** | **-71.9%** | 105 (92 + 13) | 7,430 (5,445) | **+$15.67/MWh** (-$26.73 to $53.33) | 31 / 92 (33.7%) | `TUMUT3` (12,234 MW gross) |
| Heywood (`vsa_event_atlas_v2.html`) | 20.09 MB | **6.70 MB** | **-66.7%** | 86 (77 + 9) | 7,731 (5,450) | **+$18.29/MWh** ($0.17 to $37.54) | 63 / 77 (81.8%) | `KESSB1` (5,741 MW gross) |

Synthesising the three standalone forensic atlases side by side confirms every major conclusion developed in Chapters 3, 5, 7, and 8:

1. **VNI contractions carry the clearest, statistically decisive price-spike signature:** Across 6,356 same-month, similar-condition matched pairs, a sharp VNI contraction is followed within the next hour by a peak receiving-region price jump that averages **+$94.97/MWh higher** than matched control windows (event-day block-bootstrap 95% CI: **+$58.27 to +$136.83/MWh**). Of the 26 exact Market Price Cap region-intervals logged on VNI's border over the two-year sample, 13 coincided with a sharp contraction detection within the preceding hour. Exact standing-equation version fidelity holds across **87 of 91** detailed VNI cases (95.6%), and deduplicated case-level attribution places `TUMUT3` (31,956 MW net tightening across 61 cases), `UPPTUMUT` (7,708 MW net across 61 cases), `LIMOSF11` (3,601 MW net across 85 cases), and `VBB1` (2,747 MW net across 11 high-impact cases) at the top.
2. **QNI contractions show modest average price jumps because unmatched stability/ROCOF regimes dilute the pool:** Across 5,810 matched QNI pairs, the next-hour peak price jump difference averages **+$15.67/MWh** with a 95% block-bootstrap CI straddling zero (-$26.73 to +$53.33/MWh). Only **31 of 92** detailed QNI cases (33.7%) achieve 100% exact equation-version matching, directly reflecting Chapter 3's finding that 67% to 78% of QNI intervals are governed by dynamic transient-stability, voltage, or coupled FCAS/ROCOF formulations. Yet inside the matched fixed-equation case segments, `TUMUT3` (9,547 MW net tightening across 14 spine-wide cases), Stanwell coal units `STAN-1` and `STAN-2` (2,840 MW and 2,433 MW net across 27 cases), and Queensland solar (`EMERASF1`, `CLARESF1`, `LILYSF1`) cleanly drive mechanical tightening, while `BBATTERY1` (-1,221 MW net) and `ALDGASF1` (-1,154 MW net) frequently supply counter-flow relief.
3. **Heywood contractions show a statistically positive price-jump premium led by grid-scale batteries:** Across 6,734 matched Heywood pairs, sharp contractions associate with a **+$18.29/MWh** next-hour peak price jump premium (95% CI: **+$0.17 to +$37.54/MWh**), with **63 of 77** detailed cases (81.8%) achieving 100% exact version matching. Deduplicated case-level attribution places **`KESSB1` at #1** (5,741 MW gross tightening, 2,102 MW net across 41 cases), with `BLYTHB1` (1,631 MW net in just 12 cases), `LIMBESS1`, and `HPR1` (Hornsdale Power Reserve) joining western Victorian wind and solar farms among the top twelve physical movers.

### 9.2 Translating constraint physics into leak-free forecasting and valuation features

Every insight in this atlas is strictly retrospective attribution unless it can be converted into a compact, leak-free feature contract usable at forecast issue time. In line with the repository's strict architectural boundary, the features specified below belong to a versioned challenger contract inside `nemic.experiments` and must never contaminate existing saved bundles or borrow realised future demand, generation, or weather inputs.

#### 9.2.1 Four-layer feature contract for short-horizon limit and SRA flow models

| Feature layer | Concrete issue-time variables | Physical problem solved | Applicable corridors | Strict leak-free discipline |
|---|---|---|---|---|
| **Layer 1 · Envelope & reliability state** | `own_anchor` at $t_0 - 30\text{m}$; `setter_matched` binary flag; leading setter family one-hot (Thermal / Voltage / Transient / ROCOF-FCAS / NRM / HVDC); signed directional headroom $H_{t_0}$; forced-negative indicator $I(C_{t_0} < 0)$ | Prevents models from applying single-link linear sensitivities during unmatched ROCOF/FCAS or HVDC cable regimes (Chapter 3) | All 6 links | Computed strictly from dispatch intervals published at or before issue time $t_0$ |
| **Layer 2 · Economic DUID sensitivity aggregates** | Equation-weighted net sensitivity by technology class ($\sum_{i \in \text{Solar}} s_{i,t_0}$, $\sum_{i \in \text{Hydro}} s_{i,t_0}$, $\sum_{i \in \text{BESS}} s_{i,t_0}$, $\sum_{i \in \text{Wind}} s_{i,t_0}$); top-10 economic-DUID 30-min ramp pressure; BESS 5-min peak impulse over past 30 min | Targets the 24% to 37% of contraction MW driven by fixed-equation LHS ramps (Chapter 5) while isolating fast BESS flips (Chapter 8) | VNI, QNI, Heywood, Murraylink | Uses only pre-issue standing factors and realised dispatch up to $t_0$; forward ramps only via timestamped predispatch vintages |
| **Layer 3 · Cross-corridor & parallel HVDC state** | Parallel HVDC tight-headroom flag (Directlink for QNI; Murraylink for Heywood); 6x6 neighbour contraction indicator over $[t_0 - 30\text{m}, t_0]$; counter-price flow flag $I(F_{t_0} \cdot \Delta \pi_{t_0} < 0)$ | Captures 70% to 95% parallel HVDC saturation (Chapter 2), 1.41x to 1.86x cross-link cascades, and NRM clamp risk (Chapter 6) | All 6 links (especially pooled SRA corridors) | Strict as-of publication alignment across all six links |
| **Layer 4 · Outage & constraint-set calendar** | Active NOS outage family occupancy; planned upcoming outage invocations within lead horizon; N-1-1 concurrent family overlap count | Captures the 43.5% of contraction MW driven by active-leader equation switches (Chapter 5) | All 6 links (developed in Flagship Edition B) | Strict NOS issue-vintage replay (no future revisions or cancelled bookings) |

#### 9.2.2 Practical operational checklist for trading desks and risk analysts

For commercial desks hedging interregional price spreads via Settlement Residue Auction units, regional swaps, or caps, the six-link evidence translates into five concrete operating screens:

1. **Monitor shadow-rent equations, not non-binding leaders:** Configure dispatch alert dashboards around the top shadow-rent equations in each corridor (`N>>NIL_060_051`, `N>>BDBU_970_051`, `N::N_LTYS_2` on VNI; `N^^Q_TW_330_BUS1_B1`, `QNI_SOUTH_590_DYN`, `NRM_QLD1_NSW1` on QNI; `V::S_SETB_TBSE_2`, `VS_600_TEST`, `V^^V_NIL_KGTS`, `I_6F_SN_150` on Heywood; `SVML_ROC_80`, `V^SML_BUDP_3`, `S>NIL_MHNW1_MHNW2` on Murraylink; `N_X_MBTE_3A` on Directlink; `V_T_NIL_FCSPS` on Basslink).
2. **Treat VNI and VIC-SA negative-residue exposure differently:** On VNI forward, -$97.4m of two-year negative residues occurred under forced thermal/voltage loop flow where AEMO cannot easily invoke NRM to stop the bleeding; hedging NSW to VIC SRA exposure requires explicitly pricing southern NSW loop-flow forcing rather than assuming NRM caps losses at -$100k per trading interval. On Heywood/Murraylink reverse, explicit NRM clamping intervened in 42.3% of forced intervals, making NRM trigger monitoring directly actionable.
3. **Price parallel HVDC co-binding into QNI and Heywood SRA bids:** Do not assume Directlink or Murraylink will absorb unpriced border flows when QNI or Heywood tightens. In 70% to 95% of tight AC intervals, the parallel DC link is already pinned or forced-clamped.
4. **Separate battery risk from solar risk in intraday books:** Track Victorian and South Australian grid-scale batteries (`KESSB1`, `VBB1`, `MREHA1-3`, `LIMBESS1`, `TB2B1`) on a five-minute cadence around morning and evening price-reversal windows. Their P95 five-minute step impulse (22 to 100 MW) hits half-hour tight limits faster than standard 30-minute weather forecasts anticipate.
5. **Pair this constraint-pressure atlas with Flagship Editions B and C:** Because 43.5% of all sharp contraction megawatts come from active-leader equation switches (overwhelmingly driven by planned and forced transmission outages), no constraint-pressure model is complete without formal outage-regime attribution and calibrated outage-outlook probabilities. Flagship Edition B (*Outage Risk & NOS Regime Handbook v2*) delivers that exact outage layer, while Flagship Edition C (*Interconnector Forecasting Verdict, Clustering & Project EnergyConnect v2*) bridges observed EnergyConnect commissioning physics into the AEMC loop-settlement framework and benchmarks every forecasting model stack.

## Appendix A · Mathematical Identities and Attribution Formulas

This appendix consolidates every formal mathematical identity used across Chapters 1 through 9. All timestamps are aligned to fixed NEM market time (UTC+10, interval-ending) on the native five-minute dispatch grid ($t \in \{1, \dots, 210,240\}$ covering 1 September 2024 00:05 to 31 August 2026 00:00).

### A.1 Directional capacity, headroom, and conditional constraint bounds

Let $F_{k,t}$ denote the solved five-minute dispatch flow on interconnector $k$ (positive in AEMO's nominal forward direction), $U^{\text{pub}}_{k,t}$ the published export limit, and $I^{\text{pub}}_{k,t}$ the published import limit. Reverse directional capacity is defined without clamping as:

$$L^{\text{pub}}_{k,t} = -I^{\text{pub}}_{k,t}$$

Signed directional headroom in each direction is:

$$H^{\text{upper}}_{k,t} = U^{\text{pub}}_{k,t} - F_{k,t}, \qquad H^{\text{lower}}_{k,t} = L^{\text{pub}}_{k,t} + F_{k,t} = F_{k,t} - I^{\text{pub}}_{k,t}$$

Tight headroom is defined by the indicator $\mathbb{I}(H_{k,t} \le 50\text{ MW})$, and forced-negative directional capacity by $\mathbb{I}(U^{\text{pub}}_{k,t} < 0)$ (forcing reverse flow $F_{k,t} < 0$) or $\mathbb{I}(L^{\text{pub}}_{k,t} < 0)$ (forcing forward flow $F_{k,t} > 0$).

For any active generic constraint equation $c$ with interconnector left-hand-side coefficient $a_{c,t} \ne 0$, solved left-hand side $\text{LHS}_{c,t}$, and dynamic right-hand side $\text{RHS}_{c,t}$, the conditional transfer bound is:

$$F^{\text{bound}}_{c,t} = F_{k,t} + \frac{\text{RHS}_{c,t} - \text{LHS}_{c,t}}{a_{c,t}}$$

The reconstructed forward and reverse envelopes across the active equation set $\mathcal{C}_{k,t}$ are:

$$U^{\text{recon}}_{k,t} = \min_{c \in \mathcal{C}_{k,t},\; a_{c,t} > 0} F^{\text{bound}}_{c,t}, \qquad L^{\text{recon}}_{k,t} = -\max_{c \in \mathcal{C}_{k,t},\; a_{c,t} < 0} F^{\text{bound}}_{c,t}$$

Envelope reconstruction mean absolute error (MAE) is audited by setter-match indicator $m_{k,t} = \mathbb{I}(c^{\text{leader}}_{k,t} = c^{\text{setter}}_{k,t})$ and AEMO setter family $g$:

$$\text{MAE}_{k} = \sum_{g, m} w_{k,g,m} \cdot \text{MAE}_{k,g,m}, \qquad w_{k,g,m} = \frac{N_{k,g,m}}{N_k}$$

where $w_{k,g,m} \cdot \text{MAE}_{k,g,m}$ is the exact additive MAE contribution (in MW) reported in Chapter 3 and Exhibit 3.1.

### A.2 Unit sensitivity, five-minute impulse, and economic rent weighting

Holding constraint equation $c$ fixed, the marginal sensitivity of directional transfer capacity to generating unit $i$ (carrying LHS factor $b_{c,i,t}$) is:

$$s_{c,i,t} = -\frac{b_{c,i,t}}{a_{c,t}} \quad (\text{upper}), \qquad s^{\text{rev}}_{c,i,t} = \frac{b_{c,i,t}}{a_{c,t}} = -\frac{b_{c,i,t}}{|a_{c,t}|} \quad (\text{lower})$$

Over a rolling 30-minute window (six five-minute intervals), mechanical unit pressure is $q^{(30)}_{i,t} = s_{c,i,t}(P_{i,t} - P_{i,t-6})$. The single-interval five-minute impulse capturing fast BESS reversals is approximated from consecutive unit-pressure observations as $q^{(5)}_{i,t} = |q^{(30)}_{i,t} - q^{(30)}_{i,t-1}|$ on active equation-intervals (yielding exact step impulses when consecutive 30-minute differences step cleanly).

Let $\Delta \pi^{\text{dir}}_{k,t} = \pi^{\text{recv}}_{k,t} - \pi^{\text{send}}_{k,t}$ be the directional regional dispatch price spread (receiving minus sending region in $/MWh). Congestion-rent-weighted unit pressure over the 24-month window is:

$$R_{k,i} = \sum_{t=1}^{T} \left|q^{(30)}_{k,i,t}\right| \cdot \mathbb{I}(H^{\text{dir}}_{k,t} \le 50) \cdot \frac{\max(\Delta \pi^{\text{dir}}_{k,t}, 0)}{12}$$

For each generic constraint equation $c$ on link $k$ (excluding synthetic LP zero-flow penalty constraints where `*_ZERO` or mean $|\text{MV}_{c,t}| > \$30,000/\text{MWh}$), cumulative 24-month binding shadow rent (in AUD per MW of right-hand-side relief) is:

$$S_{k,c} = \frac{1}{12} \sum_{t:\;\text{binding}(c,t)} |\text{MV}_{c,t}|$$

### A.3 Full-population three-way contraction decomposition

Let $\mathcal{E}_{k,d}$ be the set of distinct monthly-P90 sharp 30-minute contraction onset episodes on link $k$ and direction $d$, each with observed capacity drop $D_e = -\Delta_{30} C_e > 0$. For each episode $e$:

$$D^{\text{switch}}_e = D_e \cdot \mathbb{I}(c^{\text{leader}}_e \ne c^{\text{leader}}_{e-6})$$

$$D^{\text{LHS}}_e = \mathbb{I}(c^{\text{leader}}_e = c^{\text{leader}}_{e-6}) \cdot \min\left(D_e,\; \max\left(0,\; -\sum_{i} s_{c,i,e} \Delta_{30} P_{i,e}\right)\right)$$

$$D^{\text{RHS}}_e = D_e - D^{\text{switch}}_e - D^{\text{LHS}}_e$$

By construction, $D^{\text{switch}}_e + D^{\text{LHS}}_e + D^{\text{RHS}}_e \equiv D_e$ identically on every episode, and $D^{\text{switch}}_e, D^{\text{LHS}}_e, D^{\text{RHS}}_e \ge 0$.

### A.4 Seven-day block bootstrap and cross-link cascade lift

Within each link-direction-season-block cell, observations are grouped into contiguous seven-day NEM-time calendar blocks $\{B_1, \dots, B_M\}$. Across $B = 200$ resamples drawn with replacement from $\{B_1, \dots, B_M\}$ (fixed seed 42), the 2.5th and 97.5th percentiles of the resampled cell medians (and tight-headroom rates) form the reported 95% block-bootstrap confidence intervals.

For any ordered pair of links $(A, B)$, let $W_{k,t} \in \{0,1\}$ indicate whether link $k$ logged at least one sharp contraction onset in either direction within $[t - 6, t + 6]$ (plus or minus 30 minutes). Cascade conditional probability and lift ratio are:

$$P_{A \to B} = \frac{\sum_{t \in \mathcal{O}_A} W_{B,t}}{|\mathcal{O}_A|}, \qquad \text{Lift}_{A \to B} = \frac{P_{A \to B}}{\frac{1}{T}\sum_{t=1}^{T} W_{B,t}}$$

where $\mathcal{O}_A$ is the set of distinct onset timestamps on source link $A$.

## Appendix B · Data Schema, MMS Lineage, and Reproducible Build Commands

All raw AEMO Market Management System (MMS) table names, local archive directory structures, and repository module filenames are consolidated here to keep the analytical prose clean while preserving full engineering auditability.

### B.1 Local archive inputs and AEMO MMS lineage

No new NEMWEB downloads were required for Wave 1. Every table and exhibit in Flagship Edition A and Event Atlases v2 is computed deterministically from verified local archives already retained on disk:

| Analytical domain | Local repository path | Upstream AEMO MMS tables & coverage |
|---|---|---|
| Six-link five-minute constraint attribution | `data/constraint_{vni,qni,vsa,basslink,directlink,murraylink}_2y/months/YYYY-MM/` | Derived from `DISPATCHINTERCONNECTORRES`, `DISPATCHCONSTRAINT`, `DISPATCHLOAD`, `GENCONDATA`, `SPDINTERCONNECTORCONSTRAINT`, and `SPDCONNECTIONPOINTCONSTRAINT` (24 months: `2024-09` through `2026-08`; 7 parquet files per month per link) |
| Standing unit metadata & BESS flags | `data/constraint_vni_2y/standing/DUDETAILSUMMARY.parquet` | AEMO `DUDETAILSUMMARY` (`DISPATCHTYPE == 'BIDIRECTIONAL'` identifies grid-scale BESS; `FUEL_TYPE` / `STATIONNAME` maps hydro, solar, wind, coal, and gas) |
| Regional five-minute dispatch prices | `data/valuation_v2/panel/prices.parquet` | AEMO `DISPATCHPRICE` (2,592,000 region-intervals across `NSW1`, `QLD1`, `SA1`, `TAS1`, `VIC1`) |
| Settled directional SRA residues | `data/valuation_v2/settlement/directional_5min.parquet` | Five-minute interregional settlement residue panel aligned to AEMO SRA settlement buckets (negative residue attribution in Chapter 6) |
| Legacy Event Atlas payloads (read-only inputs) | `docs/html/{vni,qni,vsa}_event_atlas.html` and `reports/{vni,qni,vsa}_event_atlas_v1/` | Unmodified source case payloads compressed into `reports/event_atlases_v2/` |

### B.2 Generated compact evidence files (`reports/constraint_pressure_atlas_v2/evidence/`)

All ten compact CSV tables and the single-source-of-truth headline registry are committed cleanly to Git (raw parquet caches and fitted models remain local and Git-ignored):

1. `six_link_parity_summary.csv` — 12 rows (6 links x 2 directions): capacity quantiles, tight-headroom %, forced-limit %, contraction episodes, reconstruction MAE, mean tight spreads, and binding totals.
2. `parallel_link_cobinding.csv` — 4 rows: simultaneous tight-headroom co-binding for QNI+Directlink and Heywood+Murraylink in forward and reverse directions.
3. `reconstruction_mae_audit.csv` — 134 rows: full MAE decomposition by link, direction, setter family, and exact `setter_matched` status.
4. `diurnal_seasonal_ci_profiles.csv` — 192 rows: 6 links x 2 directions x 4 seasons x 4 diurnal blocks with 7-day block-bootstrap 95% confidence intervals.
5. `contraction_lhs_rhs_switch.csv` — 12 rows: full-population 3-way MW and episode decomposition across all 44,185 sharp contractions.
6. `cross_link_cascades.csv` — 36 rows: complete 6x6 ordered cascade conditional probabilities, baselines, and lift ratios (+/-30 min window).
7. `nrm_clamping_attribution.csv` — 12 rows: forced-negative interval counts, counter-price shares, explicit NRM/ramp setter shares, and settled negative SRA residues.
8. `duid_economic_influence.csv` — 270 rows (top 45 units per link): mechanical vs tight-headroom vs congestion-rent-weighted rankings, rank shifts, and diurnal shares.
9. `constraint_economic_influence.csv` — 240 rows (top 40 equations per link): binding intervals, leading intervals, mean `|MV|`, and cumulative 24-month shadow rent (LP `*_ZERO` penalty rows excluded).
10. `bess_ramp_signature.csv` — 42 rows (6 links x 7 technology classes): active DUID counts, mechanical/rent/onset shares, and P95 5-minute impulse MW.
11. `headline_numbers.json` — 270 verified macro strings rendered directly into the report summary and checked by unit tests.

### B.3 Deterministic rebuild and verification commands

Run from the repository root (`C:\Users\HomePC\Documents\ChatGPT\IC FLOW FORECASTING`):

```powershell
# 1. Recompute all C1-C6 compact CSVs and headline numbers from local 24-month archives
python -m nemic.experiments.constraint_pressure_v2

# 2. Build compressed standalone Event Atlases v2 + Virtual Barrels Markdown companions
python -m nemic.experiments.event_atlas_v2

# 3. Assemble Flagship Edition A self-contained HTML + SHA-256 build manifest
python reports/constraint_pressure_atlas_v2/build_html.py

# 4. Run unit & accounting-invariant tests
python -m pytest -q tests/test_constraint_pressure_v2.py

# 5. Run headless Playwright desktop/mobile QA (including Event Atlas gzip smoke checks)
node reports/constraint_pressure_atlas_v2/qa_report.cjs
```

## Appendix C · Sources, Methodology Notes, and Scope Qualifications

### C.1 Primary institutional and regulatory references

1. **Australian Energy Market Operator (AEMO).** *Constraint Formulation Guidelines* and *Constraint Implementation Guidelines* (NEM Dispatch Engine linear-programme structure, generic constraint naming conventions, feedback equations, and dynamic right-hand-side telemetry).
2. **Australian Energy Market Operator (AEMO).** *Negative Residue Management Procedures* (automatic interconnector clamping thresholds, counter-price accumulation triggers, and physical security override hierarchy).
3. **Australian Energy Market Operator (AEMO).** *Settlement Residue Auction (SRA) Rules and Procedures* (directional pooling of QNI with Directlink on the Queensland-New South Wales border, and Heywood with Murraylink on the Victoria-South Australia border).
4. **Australian Energy Market Commission (AEMC).** *National Electricity Rules (NER) Chapter 3* (central dispatch, regional reference pricing, interconnector settlement residues, and Market Network Service Provider dispatch offers).
5. **IC Flow Forecasting Research Programme.** *Interregional Valuation Research v3* (`reports/interregional_valuation_research_v3/NEM_Interconnector_Valuation_v3.html`), companion source for settled five-minute directional SRA residues and regional price panels.
6. **IC Flow Forecasting Research Programme.** *Standalone Event Atlases v2* (`reports/event_atlases_v2/{vni,qni,vsa}_event_atlas_v2.html` and `{VNI,QNI,VSA}_Event_Atlas_v2.md`), companion five-minute forensic case libraries covering 294 detailed windows across VNI, QNI, and Heywood.

### C.2 Methodological caveats and permitted claims

To uphold strict scientific and institutional discipline across the repository's three distinct model stacks, readers should keep four boundaries firmly in mind:

- **Dispatch-solution outputs versus physical capability:** Every interconnector export and import limit analysed in this atlas is an endogenous output of AEMO's five-minute dispatch solution. Limits reflect the joint state of generator offers, synchronous inertia, system-strength rules, dynamic line ratings, and discretionary clamps; they must never be interpreted as static maximum secure physical transfer capability.
- **Mechanical attribution versus independent causation:** Fixed-equation generator pressure ($-b_i / a \times \Delta P_i$) measures exact mechanical sensitivity along a solved linear inequality. Because generator dispatch, regional load, weather, and constraint invocations co-move within the same five-minute interval, generator rankings are mechanical and economic attributions rather than randomised causal treatment effects.
- **Model-stack separation:** This atlas belongs to the `nemic.experiments` network-state research stack. It does not alter, overwrite, or mix feature contracts with the original six-interconnector conditional backtest (`run_pipeline.py`) or the provider-neutral routing scaffold (`nemic.production`). Legacy baseline reports (`reports/all_interconnector_regime_research_20260921/` and `docs/html/*_event_atlas.html`) remain completely untouched on disk.
- **Backward-looking attribution versus live forecasting:** Although Chapter 9 defines a leak-free issue-time feature contract derived from these diagnostics, the metrics reported in Chapters 2 through 8 are retrospective attribution statistics over September 2024 to August 2026. Any predictive feature extracted from this atlas must pass strict chronological out-of-sample walk-forward evaluation against persistence and matched AEMO predispatch vintages before promotion.
