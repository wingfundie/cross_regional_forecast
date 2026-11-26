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

{{diagram:constraintPipeline}}

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
