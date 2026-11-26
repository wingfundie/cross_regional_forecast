## 8 Hedging futures spreads with SRA units: firmness, loop impact, and cap combinations

A core commercial question for any NEM trading or retail portfolio desk is whether directional SRA units can substitute for interregional ASX futures spreads, how many units replicate one megawatt of flat spread exposure, and what happens to that hedge during extreme price separation and under the November 2026 loop rules. This chapter evaluates hedge performance across both weekly and quarterly settlement horizons, separates sub-$300 capped-energy replication from $300 scarcity-tail replication, tests post-loop hedge firmness, and introduces a two-instrument SRA-plus-cap frontier.

### 8.1 Converting unit prices into spread equivalents

An SRA clearing price in dollars per unit cannot be compared directly with a futures spread in dollars per megawatt-hour without translating contractual pool share into effective megawatt transfer. With dated unit proportion $\theta_Q$, quarterly delivery hours $H$, and an assumed effective positive-spread transfer $\bar F$, the breakeven flow-weighted spread implied by a unit clearing price is:

$$
\text{required flow-weighted spread} = \frac{\text{clearing price}}{\theta_Q \, H \, \bar F}.
$$

For illustration, with $\theta_Q = 1/1{,}500$, $H = 2{,}160$ hours, and $\bar F = 500$ MW, a $15,000 unit price requires a flow-weighted positive spread of $20.83/MWh. Because physical transfer $\bar F$ varies systematically with the price spread, empirical hedging replaces assumed megawatts with the measured minimum-variance hedge ratio $n^{*}$ against a 1 MW flat spread. Comparing unit payoff $U_w$ against the 1 MW flat spread P&L $S_w = \sum_{t \in w} \Delta t (P_{B,t} - P_{A,t})$ across all {{hedge_weeks}} complete weeks gives:

$$
n^{*} = \frac{\operatorname{Cov}(S_w, U_w)}{\operatorname{Var}(U_w)}, \qquad
R^2 = 1 - \frac{\operatorname{Var}(S_w - n^{*} U_w)}{\operatorname{Var}(S_w)} = \operatorname{Corr}(S_w, U_w)^2.
$$

The implied empirical relative-value parity between SRA units and futures spreads is therefore:

$$
\text{SRA cost per MW-equivalent} = n^{*} \times \text{clearing price} \quad \text{versus} \quad H \times (\text{futures spread}),
$$

evaluated jointly with the stress MW-equivalent ratio $\sum_{w \in \text{top } 10} U_w / \sum_{w \in \text{top } 10} S_w$ across the ten highest-spread weeks to verify how much replication survives during market stress.

### 8.2 Weekly versus quarterly effectiveness and energy-versus-cap replication

Hedge performance differs sharply across interconnectors and across underlying price components. Measuring both weekly and quarterly settlement horizons eliminates the concern that weekly variance reduction might merely penalise intra-quarter timing mismatch.

| Direction | Min-variance units per MW ($n^{*}$) | Weekly $R^2$ (total spread) | Quarterly $R^2$ (total spread) | Weekly $R^2$ (capped energy) | Weekly $R^2$ ($300 cap tail) | Stress MW-equiv. (top 10 weeks) |
|---|---:|---:|---:|---:|---:|---:|
| VICNSW | {{hedge_mv_VICNSW}} | {{hedge_vr_VICNSW}} | {{hc_qr2_tot_VICNSW}} | {{hc_wr2_eng_VICNSW}} | {{hc_wr2_cap_VICNSW}} | {{hedge_ratio_top_VICNSW}} |
| QLDNSW | {{hedge_mv_QLDNSW}} | {{hedge_vr_QLDNSW}} | {{hc_qr2_tot_QLDNSW}} | {{hc_wr2_eng_QLDNSW}} | {{hc_wr2_cap_QLDNSW}} | {{hedge_ratio_top_QLDNSW}} |
| VICSA | {{hedge_mv_VICSA}} | {{hedge_vr_VICSA}} | {{hc_qr2_tot_VICSA}} | {{hc_wr2_eng_VICSA}} | {{hc_wr2_cap_VICSA}} | {{hedge_ratio_top_VICSA}} |
| NSWQLD | {{hedge_mv_NSWQLD}} | {{hedge_vr_NSWQLD}} | {{hc_qr2_tot_NSWQLD}} | {{hc_wr2_eng_NSWQLD}} | {{hc_wr2_cap_NSWQLD}} | {{hedge_ratio_top_NSWQLD}} |
| NSWVIC | {{hedge_mv_NSWVIC}} | {{hedge_vr_NSWVIC}} | {{hc_qr2_tot_NSWVIC}} | {{hc_wr2_eng_NSWVIC}} | {{hc_wr2_cap_NSWVIC}} | {{hedge_ratio_top_NSWVIC}} |
| SAVIC | {{hedge_mv_SAVIC}} | {{hedge_vr_SAVIC}} | {{hc_qr2_tot_SAVIC}} | {{hc_wr2_eng_SAVIC}} | {{hc_wr2_cap_SAVIC}} | {{hedge_ratio_top_SAVIC}} |

Separating capped-energy exposure from $300 cap exposure uncovers the precise physical mechanism behind VNI's low headline hedge score. On VICNSW, weekly $R^2$ against the total spread is {{hedge_vr_VICNSW}} (rising only modestly to {{hc_qr2_tot_VICNSW}} on quarterly settlement), while weekly $R^2$ against the sub-$300 capped-energy spread doubles to {{hc_wr2_eng_VICNSW}} and collapses to {{hc_wr2_cap_VICNSW}} against the $300 scarcity cap spread ({{hc_qr2_cap_VICNSW}} quarterly). When New South Wales clears above $300/MWh, mean northward VNI flow drops from {{vni_flow_normal}} MW to {{vni_flow_stress}} MW as thermal, voltage, and transient-stability limits bind, cutting one unit's effective transfer from {{hedge_mwpu_VICNSW}} MW on average down to {{hedge_ratio_top_VICNSW}} MW in the ten worst weeks.

{{exhibit:n10}}

By contrast, QLDNSW and VICSA function as credible scarcity-tail hedges. When New South Wales clears above $300/MWh, northward QNI transfer expands from {{qni_flow_normal}} MW to {{qni_flow_stress}} MW, lifting QLDNSW weekly $R^2$ to {{hedge_vr_QLDNSW}} ({{hc_qr2_tot_QLDNSW}} quarterly), preserving {{hc_wr2_cap_QLDNSW}} weekly $R^2$ on the $300 cap spread ({{hc_qr2_cap_QLDNSW}} quarterly), and holding stress-week equivalence at {{hedge_ratio_top_QLDNSW}} MW per unit. Similarly, VICSA reaches {{hedge_vr_VICSA}} weekly $R^2$ ({{hc_qr2_tot_VICSA}} quarterly) and {{hc_wr2_cap_VICSA}} weekly cap-spread $R^2$ ({{hc_qr2_cap_VICSA}} quarterly), though its stress-week equivalence still softens to {{hedge_ratio_top_VICSA}} MW as Heywood transfer constraints tighten during South Australian peaks.

### 8.3 Post-loop hedge firmness across the NSW–Victoria–South Australia triangle

Evaluating the identical 256-week and 19-quarter hedge regressions against five-minute payouts generated under the AEMC net-trade loop rule (holding physical dispatch fixed) demonstrates that loop settlement further weakens standalone VIC-side hedging:

| Loop direction | Pre-loop weekly $R^2$ | Post-loop weekly $R^2$ | Post-loop quarterly $R^2$ | Post-loop $n^{*}$ (units/MW) | Post-loop stress MW-equiv. |
|---|---:|---:|---:|---:|---:|
| VICNSW | {{hedge_vr_VICNSW}} | {{loop_hr2_VICNSW}} | {{loop_hqr2_VICNSW}} | {{loop_hnmv_VICNSW}} | {{loop_hstress_VICNSW}} |
| VICSA | {{hedge_vr_VICSA}} | {{loop_hr2_VICSA}} | {{loop_hqr2_VICSA}} | {{loop_hnmv_VICSA}} | {{loop_hstress_VICSA}} |
| NSWSA (indicative 800 units) | Not applicable | {{loop_hr2_NSWSA}} | {{loop_hqr2_NSWSA}} | {{loop_hnmv_NSWSA}} | {{loop_hstress_NSWSA}} |
| SANSW (indicative 800 units) | Not applicable | {{loop_hr2_SANSW}} | {{loop_hqr2_SANSW}} | {{loop_hnmv_SANSW}} | {{loop_hstress_SANSW}} |

Under the loop rule, VICNSW weekly variance reduction falls from {{hedge_vr_VICNSW}} to {{loop_hr2_VICNSW}} and stress-week MW-equivalence drops from {{hedge_ratio_top_VICNSW}} to {{loop_hstress_VICNSW}} MW, because forced southward NSW-to-VIC counter-price residues now net directly against the shared loop pool during New South Wales scarcity events. Meanwhile, the new NSWSA and SANSW categories exhibit low standalone variance reduction ({{loop_hr2_NSWSA}} and {{loop_hr2_SANSW}} weekly) prior to physical EnergyConnect operation, because they receive payouts only during the {{loop_pass_through}} of intervals when Victoria acts as a pass-through region.

{{exhibit:n11}}

### 8.4 Repairing tail firmness: the two-instrument SRA plus $300 cap frontier

Because an SRA unit's payout is right-skewed and its firmness failure on VNI occurs specifically during destination prices above $300/MWh, evaluating tail risk requires Conditional Value at Risk (CVaR) rather than variance alone. For a desk short 1 MW of flat regional spread hedged with $n$ SRA units bought at quarterly clearing prices plus $m_{\text{cap}}$ MW of a destination $300 cap future, the 95% CVaR of weekly loss $\ell$ is minimised via the Rockafellar-Uryasev formulation [R18]:

$$
\operatorname{CVaR}_{0.95}(\ell) = \min_{c} \left\{ c + \frac{1}{0.05} \mathbb{E}\left[(\ell - c)^{+}\right] \right\}.
$$

To illustrate two-instrument replication before licensed ASX cap quotes are ingested, the destination $300 cap is priced at an illustrative 1.15 times its historical realised mean payout (explicitly a parametric loading assumption, not observed market pricing).

| Short 1 MW spread | Unhedged CVaR95 weekly loss | Best SRA-only CVaR95 (units) | Best SRA + 1 MW dest. cap CVaR95 (SRA units) | Total CVaR95 reduction (mix) |
|---|---:|---:|---:|---:|
| NSW minus VIC (via VICNSW) | {{cvar_unhedged_VICNSW}} | {{cvar_sra_only_VICNSW}} ({{cvar_sra_units_VICNSW}}) | {{cvar_sra_cap_VICNSW}} ({{cvar_sra_cap_units_VICNSW}}) | {{cvar_reduction_mix_VICNSW}} |
| NSW minus QLD (via QLDNSW) | {{cvar_unhedged_QLDNSW}} | {{cvar_sra_only_QLDNSW}} ({{cvar_sra_units_QLDNSW}}) | {{cvar_sra_cap_QLDNSW}} ({{cvar_sra_cap_units_QLDNSW}}) | {{cvar_reduction_mix_QLDNSW}} |
| SA minus VIC (via VICSA) | {{cvar_unhedged_VICSA}} | {{cvar_sra_only_VICSA}} ({{cvar_sra_units_VICSA}}) | {{cvar_sra_cap_VICSA}} ({{cvar_sra_cap_units_VICSA}}) | {{cvar_reduction_mix_VICSA}} |

{{exhibit:n12}}

Pairing VICNSW units with a destination New South Wales $300 cap fundamentally transforms the risk profile: unhedged 95% weekly tail loss of {{cvar_unhedged_VICNSW}} falls modestly to {{cvar_sra_only_VICNSW}} with SRA units alone, but drops sharply to {{cvar_sra_cap_VICNSW}} (a {{cvar_reduction_mix_VICNSW}} reduction) once 1 MW of New South Wales $300 cap absorbs the scarcity tail while fewer SRA units ({{cvar_sra_cap_units_VICNSW}} units) hedge the remaining sub-$300 energy divergence. That composite structure directly matches the physical mechanics of VNI.

### 8.5 Missing market leg: AER and ASX futures premia

> [!CONTEXT] Unobserved Futures and $300 Cap Quotes (Conditional Module Ready)
> Public Australian Energy Regulator (AER) base-futures chart series are currently {{futures_observed}} in this build because the AER web server blocks automated retrieval. Once the manual AER exports listed in the repository external-data guide are placed locally, the build pipeline automatically computes ex-post regional and spread premia $\pi_{r,Q}^{\text{fut}} = F_{r,Q}(\tau) - \bar P_{r,Q}$ (using the final pre-delivery quote), activates the futures-scaled walk-forward benchmark, and renders the futures-path and premium exhibits. Because AER exports exclude $300 cap quotes, empirical decomposition of observed market prices into capped energy versus scarcity still requires licensed ASX historical settlement data [S31].

Published empirical research finds positive, seasonal, cross-correlated risk premia in Australian base futures [R7] and significant area-price risk premia in Nordic locational spread contracts [R9, R10]. Before treating the SRA auction discount of Chapter 7 as pure relative-value cheapness against futures, a desk must compare the SRA discount per MW-equivalent directly against the matched futures spread premium, four-leg bid-ask execution costs, and daily ASX variation-margin funding risk.
