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
