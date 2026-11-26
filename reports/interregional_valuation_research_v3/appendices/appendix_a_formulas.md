## Appendix A Mathematical and formula reference

This reference consolidates every accounting identity, settlement equation, statistical estimator, and optimisation formulation used across Chapters 1 through 12, paired with the implementing module inside the repository valuation package.

| Quantity | Formula | Implementing module / stage |
|---|---|---|
| Quarterly arithmetic mean | $\bar X = \frac{1}{H}\sum_{t \in Q}\Delta t \, X_t$, with $\Delta t = \frac{1}{12}\text{ h}$, $H = \sum_{t \in Q}\Delta t$ | `nemic/valuation/baseline.py` |
| Capped energy and scarcity excess | $E_{r,t} = \min(P_{r,t}, K)$, $C_{r,t} = \max(P_{r,t} - K, 0)$, $K = 300$ | `nemic/valuation/baseline.py` |
| Market energy / scarcity split | $F_B - F_A = [(F_B - G_B) - (F_A - G_A)] + (G_B - G_A)$ | `nemic/valuation/market.py` |
| Frequency times severity | $\bar C_r = p_r \, m_r$, where $p_r = \Pr(P_r > K)$ and $m_r = \mathbb{E}[P_r - K \mid P_r > K]$ | `nemic/valuation/baseline.py` |
| Joint four-state contribution | $\bar S = \sum_z \frac{1}{H}\sum_{t \in Q}\Delta t \, S_t \mathbf{1}\{z_t = z\}$ | `nemic/valuation/baseline.py` |
| Loss and congestion split | $P_{\text{to},t} - P_{\text{from},t} = (P_t^{*} - P_{\text{from},t}) + (P_{\text{to},t} - P_t^{*})$, $P_t^{*} = \lambda_t P_{\text{from},t}$ | `nemic/valuation/evidence.py` |
| Single-asset five-minute residue | $r_{a,t} = \frac{\Delta t}{1\text{ h}}\left[P_{\text{to},t}(F_{a,t} - (1 - s_a)L_{a,t}) - P_{\text{from},t}(F_{a,t} + s_a L_{a,t})\right]$ | `nemic/valuation/settlement.py` |
| Pre-loop directional unit payoff | $\Pi_Q^{\text{unit}} = \theta_Q \sum_{t \in Q}\max\left(\sum_a r_{a,t}\mathbf{1}\{\sum_a F_{a,t} > 0\}, 0\right)$ | `nemic/valuation/settlement.py` |
| AEMC net-trade loop allocation | $a_k = q_k(P_{\text{imp}(k)} - P_{\text{exp}(k)})$, $\tilde a_k = R^{\text{loop}} \frac{a_k}{\sum_j a_j}$, $\text{payout}_k = R^{\text{loop}} \frac{\max(\tilde a_k, 0)}{\sum_j \max(\tilde a_j, 0)}$ | `nemic/valuation/loop.py` |
| Mechanical unit-count dilution | $\Delta \text{per unit} = \theta_{\text{new}} / \theta_{\text{old}} - 1 = U_{\text{old}} / U_{\text{new}} - 1$ | `nemic/valuation/v3_analytics.py` |
| Rolling 7-day CPT truncation | $P_{r,t}^{\text{CPT}} = \min(P_{r,t}^{\text{MPC}}, P_{\text{APC}})$ if $\sum_{u=t-2015}^{t-1} P_{r,u}^{\text{CPT}} + P_{r,t}^{\text{MPC}} > \text{CPT}$ | `nemic/valuation/v3_analytics.py` |
| Value-weighted auction ratio | $\rho(\mathcal{T}) = \frac{\sum_{i \in \mathcal{T}} n_i \, \text{payoff}_i}{\sum_{i \in \mathcal{T}} n_i \, \text{price}_i}$ | `nemic/valuation/market.py` |
| Credit-support carry drag | $\text{net HPR} = (\rho - 1) - r_{\text{carry}} \cdot \frac{\text{days}_{\text{auction}\to\text{cash}}}{365}$ | `nemic/valuation/v3_analytics.py` |
| Minimum-variance hedge ratio | $n^{*} = \frac{\operatorname{Cov}(S_w, U_w)}{\operatorname{Var}(U_w)}$, variance removed $= \operatorname{Corr}(S_w, U_w)^2$ | `nemic/valuation/market.py` |
| Conditional value at risk (CVaR) | $\operatorname{CVaR}_{\alpha}(\ell) = \min_c \left\{ c + \frac{1}{1-\alpha}\mathbb{E}[(\ell - c)^{+}] \right\}$ | `nemic/valuation/v3_analytics.py` |
| Ungated flow–spread covariance | $\mathbb{E}[F^{+} S^{+}] = \mathbb{E}[F^{+}]\mathbb{E}[S^{+}] + \operatorname{Cov}(F^{+}, S^{+})$ | `nemic/valuation/baseline.py` |
| Cross-regional extremogram | $\hat{\pi}_{ij}(h) = \widehat{\Pr}(P_{j,t+h} > K \mid P_{i,t} > K)$ | `nemic/valuation/evidence.py` |
| Moving day-block bootstrap | $\bar S^{(b)} = \frac{1}{D}\sum_{d \in \mathcal{B}^{(b)}} \bar S_d$, contiguous 7-day blocks | `nemic/valuation/evidence.py` |
| Ex-ante Bachelier regime call | $\mathbb{E}[S^{+}] = \sigma \varphi(\mu / \sigma) + \mu \Phi(\mu / \sigma)$ weighted by training calendar weights $w_{\text{train}}$ | `nemic/valuation/v3_analytics.py` |
| Ensemble CRPS | $\text{CRPS}(F, y) = \frac{1}{M}\sum_i \lvert x_i - y \rvert - \frac{1}{2M^2}\sum_{i,j} \lvert x_i - x_j \rvert$ | `nemic/valuation/valuation_tests.py` |
| In-quarter remaining implied average | $\bar P^{\text{remaining}} = \frac{F - w \bar P^{\text{elapsed}}}{1 - w}$ | Interactive Workbench |
| Destination cap-implied hours | $h = \frac{H \, G}{(1 + \rho_{\text{risk}}) \, m}$ | Interactive Workbench |
| Dual entropy-pooling objective | $\mathcal{L}(\lambda) = \log \sum_s p_s \exp(-\lambda^{\top} X_s) + \lambda^{\top} \bar{q} + \sum_k \lvert \lambda_k \rvert \delta_k$, $N_{\text{eff}} = 1 / \sum_s q_s^2$ | Stage 4b specification (Ch. 11) |
