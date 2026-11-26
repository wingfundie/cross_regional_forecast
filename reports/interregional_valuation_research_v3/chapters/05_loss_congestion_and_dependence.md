## 5 Loss-driven versus congestion-driven spreads and flow–spread dependence

Separating ordinary transmission losses from binding network congestion, and measuring how interconnector transfer behaves as regional price spreads widen, exposes two structural wedges that govern relative value between futures spreads and SRA units. The first wedge is physical and predictable: losses scale quadratically with flow and invert sign when exporting regions clear below zero. The second wedge is operational and asymmetric: flow and spread move together during ordinary hours but diverge sharply during destination scarcity on constrained links.

### 5.1 Separating transmission losses from binding congestion

In every five-minute interval where an interconnector clears strictly inside its export and import limits, AEMO's dispatch engine couples the importing region's price to the exporting region's price through the link's marginal loss factor $\lambda_t$. Defining the coupled reference price $P_t^{*} = \lambda_t P_{\text{from},t}$ splits the signed spread cleanly into a loss term $(P_t^{*} - P_{\text{from},t})$ and a congestion term $(P_{\text{to},t} - P_t^{*})$, each of which splits further at the $300/MWh strike into capped energy and scarcity (Chapter 1.3).

Across the nineteen complete quarters from October 2021 to June 2026, mainland interconnectors sat coupled at their marginal loss factor in half to nearly two-thirds of all five-minute intervals:

| Corridor (destination minus origin) | Mean loss part (AUD/MWh) | Mean congestion part (AUD/MWh) | Coupled intervals at loss factor | Largest quarterly loss share |
|---|---:|---:|---:|---:|
| NSW minus VIC | {{loss_nsw_vic}} | {{cong_nsw_vic}} | {{coupled_nsw_vic}}% | {{loss_share_max_nsw_vic}} |
| QLD minus NSW | {{loss_qld_nsw}} | {{cong_qld_nsw}} | {{coupled_qld_nsw}}% | {{loss_share_max_qld_nsw}} |
| SA minus VIC | {{loss_sa_vic}} | {{cong_sa_vic}} | {{coupled_sa_vic}}% | {{loss_share_max_sa_vic}} |

Although the average loss component appears modest relative to total congestion across multi-year horizons, it can dominate quiet quarters: losses accounted for up to {{loss_share_max_nsw_vic}} of the absolute spread components on New South Wales minus Victoria, {{loss_share_max_qld_nsw}} on Queensland minus New South Wales, and {{loss_share_max_sa_vic}} on South Australia minus Victoria. Basslink is reported in aggregate spread tables but excluded from loss-versus-congestion attribution because, operating as a market network service provider until July 2026, it cleared on its own commercial offers rather than sitting passively at its inter-regional marginal loss factor ({{coupled_vic_tas}}% coupled).

{{exhibit:n8}}

Because marginal loss factors are smooth, increasing functions of physical transfer (alongside regional demand terms specified in AEMO's annual loss-factor equations), the loss component is the most structurally forecastable element of an interregional spread. It scales directly with both transfer flow and the underlying wholesale price level.

{{exhibit:n9}}

> [!MECHANISM] Structural Wedge Between Futures and SRA Units on Losses
> A linear interregional futures spread receives 100% of the loss spread $P_{\text{from},t}(\lambda_t - 1)$ across every coupled interval. An SRA unit receives only the metered quadratic loss surplus $P_t L_t$. Because quadratic transmission losses $L = k F^2$ imply marginal losses $\lambda - 1 \approx 2 k F$ equal to twice average losses, an SRA captures only about half of the loss spread in coupled intervals while capturing the full congestion rent $F_t (P_{\text{to},t} - P_t^{*})$ whenever constraints bind. In quiet, heavily coupled quarters, futures spreads therefore earn a structural loss premium that SRA units do not replicate.

### 5.2 Negative-price regimes and loss-sign inversion

Daytime rooftop and utility-scale solar generation has made negative regional reference prices a permanent structural feature of the NEM. When an exporting region clears below zero while the importing region stays positive, regional spreads widen sharply inside the sub-$300 capped-energy bucket with zero $300 cap payout, and marginal transmission losses invert sign.

| Corridor | Origin below $0 share | Mean spread when origin below $0 | Mean loss term when origin below $0 | Mean loss term when origin non-negative | Share of forward SRA residue earned while origin below $0 |
|---|---:|---:|---:|---:|---:|
| NSW minus VIC | {{neg_share_nsw_vic}} | {{neg_spread_nsw_vic}}/MWh | {{neg_loss_nsw_vic}}/MWh | {{pos_loss_nsw_vic}}/MWh | {{neg_res_share_nsw_vic}} |
| QLD minus NSW | {{neg_share_qld_nsw}} | {{neg_spread_qld_nsw}}/MWh | {{neg_loss_qld_nsw}}/MWh | {{pos_loss_qld_nsw}}/MWh | {{neg_res_share_qld_nsw}} |
| SA minus VIC | {{neg_share_sa_vic}} | {{neg_spread_sa_vic}}/MWh | {{neg_loss_sa_vic}}/MWh | {{pos_loss_sa_vic}}/MWh | {{neg_res_share_sa_vic}} |

Victoria cleared below $0/MWh in {{neg_share_nsw_vic}} of all five-minute intervals across the nineteen-quarter window. During those negative Victorian intervals, the New South Wales minus Victoria spread averaged {{neg_spread_nsw_vic}}/MWh, generating {{neg_res_share_nsw_vic}} of all settled northward VNI residue across the entire five-year sample. Simultaneously, the marginal loss term $P_{\text{from},t}(\lambda_t - 1)$ inverted from an average of {{pos_loss_nsw_vic}}/MWh when Victoria was non-negative to {{neg_loss_nsw_vic}}/MWh when Victoria was negative. Physically, pushing power across a lossy line out of a negatively priced region consumes excess zero- or negative-cost generation in line losses, reducing the price gap required to couple the two nodes rather than widening it. Valuation models that treat the loss spread as a fixed positive markup misprice daytime solar-export quarters systematically.

### 5.3 Why expected flow and expected spread cannot be multiplied mechanically

For a directional transfer $F^{+} = \max(F, 0)$ and positive price spread $S^{+} = \max(S, 0)$, the gross lossless revenue expectation decomposes as:

$$
\mathbb{E}[F^{+} S^{+}] = \mathbb{E}[F^{+}] \, \mathbb{E}[S^{+}] + \operatorname{Cov}(F^{+}, S^{+}).
$$

Conditioning on direction, loss treatment, and allocation gates introduces further state dependence, while quarterly net average flows frequently conceal large bidirectional diurnal swings. Three distinct physical regimes illustrate why average flow and average spread cannot be multiplied to estimate SRA value:

1. **Unconstrained arbitrage:** With spare transfer headroom, increased flow displaces dearer generation in the importing region and compresses price separation toward the marginal loss band.
2. **High-flow binding congestion:** When an import limit binds at high physical throughput while destination demand is tight, elevated flows and wide price spreads coexist, generating peak SRA unit payouts.
3. **Outage or stability contraction:** When a transmission outage, voltage constraint, or transient-stability equation cuts transfer capability sharply during destination scarcity, regional price spreads can surge to the market price cap while transferable megawatts collapse. This third state pays a linear futures spread in full while starving a flow-linked SRA unit of volume.

A subtle statistical pitfall must be avoided when measuring this covariance. Version 1 computed its independence benchmark using a flow variable already gated by the positive-spread indicator $\mathbf{1}\{S > 0\}$. Sharing that indicator between flow and spread injects a mechanical positive bias even if flow and spread were statistically independent:

$$
\operatorname{Cov}\left(F \mathbf{1}\{S > 0\}, \, S^{+}\right) = \operatorname{Cov}(F^{+}, S^{+}) + \mathbb{E}[F^{+}] \, \mathbb{E}[S^{+}] \frac{1 - \Pr(S > 0)}{\Pr(S > 0)}.
$$

Correcting that benchmark to ungated positive flow on the original two-year window lowers northward VNI's apparent covariance from ${{v1_cov_vninorth}}/hour to ${{v1_ungated_vninorth}}/hour, and conditional on a positive spread the covariance turns sharply negative at ${{v1_condcov_vninorth}}/hour. Across the full nineteen-quarter window, northward VNI displays a positive conditional Spearman rank correlation of {{full_condsp_vninorth}} alongside a deeply negative conditional linear covariance of ${{full_condcov_vninorth}}/hour. Ordinary intervals exhibit positive co-movement as rising New South Wales demand draws Victorian exports, whereas extreme New South Wales scarcity intervals experience flow contraction that drives linear covariance negative. On northward QNI, by contrast, the conditional Spearman correlation reaches {{full_condsp_qninorth}} and flow expands under New South Wales scarcity.

{{interactive:flowBridge}}

### 5.4 Non-monotone capacity responses and dispatch limits

Even in a simplified two-region network, expanding interconnector transfer capability does not raise SRA residue monotonically. Additional transfer megawatts let lower-cost generation displace peak local offers, shrinking the price spread and lowering scarcity arrival probabilities; the volume gain can be more than offset by spread compression. Prospective valuation sensitivities must therefore evaluate full capacity-response curves rather than assuming that a 10% limit increase raises SRA value by 10%.

Equally important, AEMO's reported dispatch import and export limits are endogenous outputs of solved dispatch equations in which other generators and parallel interconnectors appear on the left-hand side [S12, L02]. Treating each reported directional limit as an independent physical pipe capacity can construct physically impossible multi-region states. Meaningful valuation sensitivities specify a concrete physical perturbation, such as a 100 MW shift in an identified constraint right-hand side, one additional day of a named transmission outage, a battery endurance reduction, or a wind-output shock, and state explicitly whether dispatch was re-optimised, offers held fixed, topology modified, or only a conditional statistical distribution perturbed.
