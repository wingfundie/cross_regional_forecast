## Chapter 5 · Contraction Anatomy: Equation Switches, LHS Ramps, and RHS Shifts

When an interconnector's export or import limit drops sharply over a 30-minute window, trading desks and automated models face a fundamental attribution problem. Three physically distinct mechanisms can produce the exact same headline megawatt drop on a dispatch screen, yet each mechanism has completely different predictability and persistence:

1. **Path A (Active-leader equation switch):** A different constraint equation takes over as the tightest directional bound between $t - 30\text{ min}$ and $t$. Common triggers include a planned or unplanned transmission outage invoking an outage constraint set, AEMO invoking a soft-ramping constraint (`#R`) or Negative Residue Management clamp, or a rapid regional load shift crossing from a thermal boundary onto a lower transient-stability or voltage-stability boundary.
2. **Path B (Same-equation LHS generator ramp):** The exact same constraint equation leads at both $t - 30\text{ min}$ and $t$, and the drop is explained mechanically by scheduled and semi-scheduled generating units ramping along that equation's fixed left-hand-side coefficients: $\Delta \text{LHS}_{\text{gen}} = \sum_i s_{c,i} (P_{i,t} - P_{i,t-6})$.
3. **Path C (Same-equation RHS and Z-term shift):** The exact same constraint equation leads at both endpoints, but the drop comes from a reduction in the equation's right-hand side $\text{RHS}_{c,t}$ (dynamic line rating reductions from rising ambient temperature or falling wind speed, loss of synchronous inertia units, or dynamic stability curve shifts) or non-generator left-hand-side terms $Z_{c,t}$ (such as parallel interconnector flows or FCAS enablement).

{{diagram:contractionSplit}}

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

{{exhibit:a6}}

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
