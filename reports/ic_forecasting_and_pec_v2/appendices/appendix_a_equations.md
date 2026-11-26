## Appendix A · Mathematical Identities for EnergyConnect Loop Settlement and Forecast Evaluation

All five-minute and half-hourly market calculations are aligned to fixed NEM time (UTC+10, interval-ending). Tight directional half-hour limits equal the minimum across the six constituent five-minute dispatch intervals.

### A.1 AEMC ERC0386 net-trade loop settlement identities

Let the three southern-ring loop arms be $\text{VN} = (\text{VIC1} \to \text{NSW1})$, $\text{VS} = (\text{VIC1} \to \text{SA1}$, pooling Heywood and Murraylink), and $\text{NS} = (\text{NSW1} \to \text{SA1}$, Project EnergyConnect). In each five-minute interval $t$, let $F_{a,t}$ be the signed physical flow on arm $a \in \{\text{VN}, \text{VS}, \text{NS}\}$, and let $\pi_{r,t}$ be the regional reference price in $r \in \{\text{NSW1}, \text{VIC1}, \text{SA1}\}$.

1. **Signed arm IRSR allocation and net loop residue:**
   $$A_{a,t} = \frac{F_{a,t} \cdot (\pi_{\text{to}(a),t} - \pi_{\text{from}(a),t})}{12}, \qquad \text{NL}_t = A_{\text{VN},t} + A_{\text{VS},t} + A_{\text{NS},t}$$
   Whenever $\text{NL}_t \le 0$, zero payout is distributed to Settlement Residue Distribution (SRD) units in interval $t$ and the negative deficit is recovered through transmission network pricing.
2. **Net regional export positions:**
   $$E_{\text{NSW1},t} = F_{\text{NS},t} - F_{\text{VN},t}, \qquad E_{\text{VIC1},t} = F_{\text{VN},t} + F_{\text{VS},t}, \qquad E_{\text{SA1},t} = -F_{\text{VS},t} - F_{\text{NS},t}$$
   By conservation of flow across the lossless nodal triangle, $E_{\text{NSW1},t} + E_{\text{VIC1},t} + E_{\text{SA1},t} \equiv 0$.
3. **Net trade quantities and Step-1 amounts:** Let region $r$ be classified as net exporting if $E_{r,t} \ge 0$ and net importing if $E_{r,t} < 0$. Each arm $a$ linking an exporting region $e$ to an importing region $m$ carries net-trade quantity $q_{a,t}$ equal to $E_{e,t}$ when two regions export (one importer), or $-E_{m,t}$ when one region exports (two importers), with Step-1 amount:
   $$\text{Amt}_{a,t} = q_{a,t} \cdot (\pi_{m,t} - \pi_{e,t})$$
4. **Provisional allocation and secondary positive netting:**
   $$\text{Prov}_{a,t} = \text{NL}_t \cdot \frac{\text{Amt}_{a,t}}{\sum_{b} \text{Amt}_{b,t}}, \qquad \text{Final}_{a,t} = \mathbb{I}(\text{NL}_t > 0) \cdot \text{NL}_t \cdot \frac{\max(\text{Prov}_{a,t}, 0)}{\sum_{b} \max(\text{Prov}_{b,t}, 0)}$$
   satisfying exact payout conservation $\sum_{a} \text{Final}_{a,t} \equiv \max(\text{NL}_t, 0)$ whenever at least one arm has positive provisional allocation.

### A.2 Observed commissioning counterfactual flow response

For each commissioning regime $(C_{\text{fwd}}, C_{\text{rev}}, u)$ with empirical median utilisation ratio $u = \text{median}(|F_{\text{NS}}| / C^{\text{active}})$ measured over positive-limit half-hours ($C^{\text{active}} \ge 25\text{ MW}$), historical-price counterfactual PEC flow over the 24-month loop panel is:

$$F_{\text{NS},t} = \tanh\left(\frac{\pi_{\text{SA1},t} - \pi_{\text{NSW1},t}}{35}\right) \cdot u \cdot \Big(C_{\text{fwd}} \mathbb{I}(\pi_{\text{SA1},t} \ge \pi_{\text{NSW1},t}) + C_{\text{rev}} \mathbb{I}(\pi_{\text{SA1},t} < \pi_{\text{NSW1},t})\Big)$$

### A.3 Forecast MAE skill, interval coverage, and clustering ARI

For any forecast model $m$ and baseline $b$ evaluated on an identical set of as-of rows $\mathcal{I}$:

$$\text{MAE}_m = \frac{1}{|\mathcal{I}|}\sum_{i \in \mathcal{I}} |y_i - \hat{y}_{m,i}|, \qquad \text{Skill}_{m \text{ vs } b} = 1 - \frac{\text{MAE}_m}{\text{MAE}_b}$$

Empirical interval coverage for nominal prediction radius $r_{m,i}$ is $\text{Cov}_m = \frac{1}{|\mathcal{I}|}\sum_{i \in \mathcal{I}} \mathbb{I}(|y_i - \hat{y}_{m,i}| \le r_{m,i})$. Clustering partition agreement across random initialisations (`seed_ari`) and adjacent chronological folds (`block_ari`) is measured via the Hubert-Arabie Adjusted Rand Index ($\text{ARI} \in [-1, 1]$, where 1.0 denotes identical partitions and 0.0 denotes chance agreement), with forecast MAE differences tested via seven-day block bootstrap and Holm-Bonferroni step-down family-wise error control.
