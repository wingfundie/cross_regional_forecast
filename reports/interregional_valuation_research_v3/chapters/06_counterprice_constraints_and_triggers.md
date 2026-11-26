## 6 Counter-price flows, binding constraints, outage plans, and physical triggers

Regional price spreads and SRA payouts do not emerge from abstract stochastic noise; they arise from identifiable combinations of network security constraints, thermal plant outages, renewable output ramps, battery energy depletion, and dispatch rules governing negative settlement residues. Tracing how those physical triggers propagate through dispatch clearing into contract cashflows is essential both for evaluating the November 2026 loop regime and for designing the Stage 2 and Stage 3 valuation models of Part IV.

{{diagram:mechanismChain}}

### 6.1 Counter-price flows and forced negative residue

Pre-loop, a negative inter-regional residue arises whenever power flows from a higher-priced region toward a lower-priced region. Across all six mainland directional interconnectors over nineteen complete quarters, settled negative residue totalled {{all_neg}}. Crucially, {{all_forced_share}} of that counter-price total occurred while the interconnector was physically forced by a binding security equation: a negative export limit pushing flow in reverse or a positive import limit forcing forward transfer toward the cheaper node.

New South Wales to Victoria alone generated {{nswvic_neg}} of settled negative residue, overwhelmingly driven by emergency and security constraints during New South Wales scarcity events:

- {{nswvic_forced_share}} of New South Wales to Victoria negative residue occurred under forced southward flow (a negative northward export ceiling on VNI);
- {{nswvic_exp300_share}} occurred while New South Wales prices exceeded $300/MWh;
- automated negative-residue management (NRM) was active across {{nswvic_nrm_intervals}} five-minute intervals in the post-August 2024 period for which public activation flags exist.

{{exhibit:n17}}

Under pre-loop rules, negative residues never reduce SRA unit payouts directly because they are recovered weekly from the importing region's transmission network service provider (NER 3.6.5(a)(4)) [R1]. Under AEMO's pre-loop NRM automation, clamping triggers on an individual link once accumulated negative residue reaches -$100,000 [R5, S14]. From November 2026 onward, however, whole-loop settlement nets negative arm allocations directly against positive loop arms before unit distribution, and automated loop NRM clamps only when the net loop residue itself turns negative [S09, R5]. Forced southward flows during New South Wales spikes therefore shift from a transmission-network cost recovery item into a direct payout drag on Victoria-connected SRA holders. Historical individual-link clamping patterns documented in practitioner analyses [S14] cannot be extrapolated mechanically into the post-EnergyConnect loop regime.

### 6.2 Which constraints drive regional price separation

Attributing the congestion component of each five-minute spread ($P_{\text{to},t} - \lambda_t P_{\text{from},t}$) to the binding constraint equation reported as setting the interconnector limit reveals which physical limits actually generate interregional value. Using AEMO's standard constraint-naming convention (thermal, voltage stability, transient stability, and system-normal versus outage equations; exact identifier rules in Appendix B), congestion on New South Wales minus Victoria averages:

- **Transient stability equations:** ${{vni_cong_transient}}/MWh;
- **Thermal equations:** ${{vni_cong_thermal}}/MWh;
- **Voltage stability equations:** ${{vni_cong_voltage}}/MWh;
- **Network state split:** ${{vni_cong_system_normal}}/MWh from system-normal equations versus ${{vni_cong_outage}}/MWh from outage and abnormal-network equations.

{{exhibit:n18}}

Beneath the family aggregates, a compact set of recurring named equations accounts for a disproportionate share of multi-year congestion value across each mainland corridor:

| Corridor | Leading recurring limit-setting equations (19-quarter mean contribution) | Dominant family and state |
|---|---|---|
| NSW minus VIC | Top voltage-stability normal equations (`V^^N_NIL_1` at ${{top_set_vni_val}}/MWh across {{top_set_vni_int}} intervals; `N^^N_NIL_3` at $3.82/MWh) alongside transient outage equations (`N::N_CTYS_2` at $2.77/MWh) and thermal normal equations (`N>>NIL_970_051` at $2.15/MWh) | Mixed system-normal voltage/thermal plus high-impact transient outage sets |
| QLD minus NSW | Voltage outage equation (`N^^Q_LS_VC_B1` at ${{top_set_qld_val}}/MWh across {{top_set_qld_int}} intervals) offset by southward thermal normal limits (`N>>NIL_964_84_S` at -$2.80/MWh) and northward thermal limits (`N>>NIL_33_34` at $2.27/MWh) | Bidirectional thermal normal plus Queensland voltage outage constraints |
| SA minus VIC | Transient outage equation (`V::S_SETB_TBSE_2` at ${{top_set_sa_val}}/MWh across {{top_set_sa_int}} intervals) alongside Heywood dynamic transfer limits (`VS_600_TEST` at $2.65/MWh, `VS_050_DYN` at $2.09/MWh) | Outage-driven transient stability and Heywood dynamic operational limits |

*(Note: exact constraint identifiers in the summary table above are retained as proper AEMO equation names to support direct cross-reference against the repository's network-outage constraint studies; full naming-heuristic definitions sit in Appendix B.)* Because naming conventions are a heuristic classification rather than a full left-hand-side coefficient decomposition, equation-level sensitivity modelling should reference the repository's dedicated constraint-coefficient studies alongside this attribution.

### 6.3 Pre-auction outage plans as an information signal

Because SRA tranches are auctioned prior to delivery while transmission network service providers submit planned outage schedules months in advance, planned outage hours known before the auction constitute a testable ex-ante information signal. Counting only outage-to-constraint-set hours timestamped strictly prior to each delivery quarter's Tranche 12 notification date (from 2023 Q1 onward, spanning {{outage_quarters}} quarters where outage-to-set mappings exist) yields positive rank correlations with the realised share of separated intervals across all three mainland corridors:

| Corridor | Spearman correlation (pre-auction set hours vs. realised separation share) | Quarters observed |
|---|---:|---:|
| NSW minus VIC | {{outage_rho_nsw_vic}} | {{outage_quarters}} |
| QLD minus NSW | {{outage_rho_qld_nsw}} | {{outage_quarters}} |
| SA minus VIC | {{outage_rho_sa_vic}} | {{outage_quarters}} |
| VIC minus TAS | {{outage_rho_vic_tas}} | {{outage_quarters}} |

Positive mainland correlations (reaching {{outage_rho_sa_vic}} on South Australia minus Victoria, where planned Heywood outage sets tighten transfer directly) indicate that pre-auction network outage plans carry genuine forward information. With only {{outage_quarters}} quarterly observations, however, this relationship is suggestive rather than definitive; as Chapter 9 confirms, translating raw outage hours into a linear dollar adjustment without controlling for weather and scarcity regime noise still underperforms clearing prices out of sample.

{{exhibit:n19}}

### 6.4 Exploratory offer-curve steepness diagnostic (scoped four-day pilot)

Economic theory predicts that binding import constraints can alter local generator offer behaviour by isolating importing-region residual demand from external competition [R16]. To test whether public offer stacks exhibit steeper local supply curves when imports bind, an exploratory pilot examined energy offer bands across the highest-separation days per importing region, measuring the price rise required to dispatch an additional 200 MW above the cleared regional stack.

> [!RISK] Strict Scope Boundary on the Exploratory Offer-Curve Pilot
> Four of the six targeted archive months lacked public bid-per-offer files during automated extraction (leaving zero Queensland coverage and only {{strategic_days_total}} calendar days in total: two days in New South Wales in November 2024 and two days in South Australia in January 2026, totalling {{strategic_intervals}} five-minute intervals). Results are therefore reported strictly as a narrow diagnostic rather than a generalisable empirical finding.

Across those four calendar days, median offer-stack steepness pointed in opposite directions across the two observed regions ({{strategic_by_region}}). Measuring local offer slope alone does not identify strategic intent, and a full market-power study would require multi-year offer coverage, rebid timing forensics, and portfolio contract positions.

{{exhibit:n27}}

### 6.5 Compound physical triggers, accessible supply margin, and dual attribution ledgers

Individual grid stresses rarely produce extreme spreads in isolation. A coal unit trip during mild Spring demand with strong wind behaves entirely differently from the identical outage during a hot evening with low wind, a binding import constraint, and depleted battery storage. Prospective valuation must model triggers as compound states, separating the arrival probability of a trigger combination from the conditional severity of price separation given that trigger.

| Physical trigger mechanism | Ex-ante observable information | Transmission pathway into spread and SRA value |
|---|---|---|
| High residual demand | Joint weather, demand, rooftop solar, and VRE scenarios | Moves regional clearing onto steep thermal and gas-peaker offer bands and lifts import demand |
| Thermal outages or derating | Issue-dated availability submissions, outage notices, ambient heat | Shrinks local accessible supply; price impact depends on replacement plant and import headroom |
| Transmission outage or security constraint | Published outage plans, generic constraint sets, credible contingencies | Caps imports, triggers separation beyond losses, or alters loop net-trade allocation |
| Multi-region wind drought | Spatial weather ensembles and low-wind duration | Erodes geographic diversity across mainland regions and elevates simultaneous scarcity risk |
| Evening solar ramp | Sunset timing, temperature persistence, thermal ramp limits | Creates sharp short-duration flexibility premiums during 16:00–21:00 intervals |
| Battery and hydro depletion | Sequential state-of-charge tracking, MWh capacity, efficiency | Suppresses early peak hours but allows sustained high prices once storage energy exhausts |
| Midday renewable surplus | High available solar/wind, low operational demand, minimum synchronous load | Drives negative regional prices, export congestion, and loss-sign inversion inside capped energy |
| Offer and rebid shifts | Historical offer bands, fuel costs, water/gas opportunity costs | Steepens effective supply curves even when physical megawatt availability is unchanged |
| FCAS and system security | Co-optimised energy-FCAS availability and local inertia rules | Constrains generator energy headroom and alters interconnector limits |
| Statutory interventions and price caps | Effective market price cap, rolling 7-day CPT, administered caps | Truncates multi-day extreme tails and governs suspension pricing |

Direct forensic evidence from the AER's Q2 2026 significant-price reports confirms how South Australian scarcity episodes combined cold-driven demand, multi-hour wind lulls, cascading battery state-of-charge depletion, network limits, and rebidding [S13]. Such regulator incident reports are invaluable for building falsifiable mechanism hypotheses, though they remain selected extreme case studies rather than unbiased frequency samples.

To operationalise compound triggers in Stage 2 and Stage 3 models, construct an explicit **accessible supply margin** per region combining locally deliverable thermal generation, available renewable output (distinct from curtailed dispatch), feasible battery discharge bounded by remaining megawatt-hour endurance, demand response, and jointly feasible imports, minus operational demand (avoiding double-counting rooftop solar already netted out of operational demand). Tracking both megawatt headroom and megawatt-hour endurance prevents treating a 500 MW battery with 20 minutes of charge remaining as sustained multi-hour cover.

Finally, maintain strict discipline between predictive screening and causal attribution by keeping two separate ledgers:

- **Event ledger (predictive):** Records overlapping physical conditions (such as low wind plus coal outage plus binding VNI transient constraint) alongside sample counts, confidence intervals, lead times, and strict verification that every predictor was knowable at issue time.
- **Value ledger (causal):** Assigns dollar contributions via declared dispatch counterfactuals (rerunning clearing with one physical mechanism altered, or using Shapley allocations across paired scenarios with an explicit residual) so identical spread dollars are never triple-counted across correlated causes. Unresolved episodes should be stored openly rather than forced into ad-hoc explanations.
