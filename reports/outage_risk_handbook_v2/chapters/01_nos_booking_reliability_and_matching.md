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

{{exhibit:b1}}

Three empirical regularities govern NOS execution across all six links:

1. **Nearly one-third of all bookings never execute (31.0% mean withdrawal rate):** Across the twelve corridor-years, withdrawal rates range from 18.1% (Directlink Year 1) up to 45.6% (Basslink Year 1), averaging 35.0% on VNI, 33.7% on Heywood, 34.0% on Murraylink, and 23.9% on QNI and Directlink. Any forward pricing model that treats a booking 30 to 90 days ahead as a 100% certain capacity drop immediately introduces a 24% to 35% upward bias before a single constraint equation is evaluated.
2. **Once an outage proceeds, constraint-set invocation is virtually deterministic (99.7%):** Conditional on a booking not being withdrawn, AEMO invokes the associated constraint set in 99.0% to 100.0% of episodes across every interconnector. Operational uncertainty therefore concentrates heavily in whether the transmission operator cancels or reschedules the booking, rather than whether AEMO enforces the security equations once switching begins.
3. **Asymmetric execution duration favours early return over overrun by roughly eight to one:** Executed outages start slightly late (median start shift +0.08 to +0.15 hours) and finish materially early (median end shift -0.38 to -0.95 hours). Between 34.7% and 48.4% of non-withdrawn outages return early, whereas only 3.2% to 8.7% overrun their booked end time. That early-return asymmetry matters directly for evening-peak risk: maintenance booked from 07:00 to 17:00 frequently restores lines by 16:00, just ahead of the highest-priced evening demand ramp.

### 1.2 From raw bookings to matched-pair economic attribution

To eliminate seasonal and diurnal selection bias when valuing outage families, the attribution pipeline constructs exact matched treated-versus-control half-hour pairs across every interconnector and direction. Each treated half-hour in which a specific constraint-set family (such as `N-MNYS_5_WG_CLOSE` or `V-MLSY_NOEMTT_R`) is actually invoked is paired with a strictly non-outage control half-hour matched on calendar proximity, time of day, and ambient system conditions.

{{diagram:outagePipeline}}

Once exact treated-control pairs $(t_m, c_m)$ are assembled for each family-direction across all six interconnectors, every economic outcome is evaluated strictly as the paired difference:

$$\Delta Y_m = Y(t_m) - Y(c_m)$$

where $Y$ is either the directional regional dispatch price spread ($\pi_{\text{recv}} - \pi_{\text{send}}$ in $/MWh) or the settled directional SRA residue scaled to a 48-half-hour daily rate ($/day). Because transmission outages persist across multi-hour and multi-day blocks, standard independent-interval standard errors severely understate uncertainty. Every confidence interval reported in this handbook is therefore computed via a seven-day contiguous calendar-block bootstrap, ensuring that week-long maintenance episodes are resampled as intact blocks.

### 1.3 Why megawatt limit drops and dollar impacts decouple

Before inspecting the family-level economic ledger in Chapter 2, desks should internalise a fundamental physical asymmetry: a 200 MW reduction in an interconnector's export limit does not automatically raise the directional price spread or increase SRA payouts. Three distinct commercial regimes occur under transmission outages:

- **With-price tightening (SRA-expanding):** When an outage caps transfer in the dominant economic direction while flow remains positive and regional price separation widens faster than volume shrinks, directional congestion rent ($F \times \Delta\pi$) rises and SRA holders earn higher daily payouts.
- **Volume-starvation clamping (SRA-destroying):** When an outage slashes directional transfer capacity nearly to zero (or below zero into forced reverse flow), the flow factor $F$ collapses even if the regional price spread widens. Because SRA payouts equal flow multiplied by spread, clamping a corridor down to 0 MW destroys daily SRA revenue completely.
- **Counter-price loop-flow forcing (negative-residue trap):** When an outage forces physical power to flow from a high-price region into a low-price region to protect a parallel line, directional settlement residues turn sharply negative, imposing direct dollar losses on the pooled border SRA bucket.

Chapter 2 quantifies all three regimes across 697 supported outage family-directions spanning all six NEM interconnectors.
