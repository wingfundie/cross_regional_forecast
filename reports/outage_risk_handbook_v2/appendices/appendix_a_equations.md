## Appendix A · Mathematical Identities and Calibration Formulas

All outage timestamps, control matches, and market panels are aligned to fixed NEM market time (UTC+10, interval-ending) on the half-hourly settlement grid ($T = 35,040$ half-hours covering 1 September 2024 to 31 August 2026).

### A.1 Matched-pair economic attribution and seven-day block bootstrap

For each interconnector $k$, direction $d \in \{\text{forward}, \text{reverse}\}$, and constraint-set family $f$, let $\mathcal{M}_{k,d,f} = \{(t_m, c_m)\}_{m=1}^{M}$ denote the exact set of deduplicated matched treated-control half-hour pairs. The paired directional spread difference and daily-scaled SRA residue difference are:

$$\Delta \pi_m = \pi^{\text{dir}}_{k,d}(t_m) - \pi^{\text{dir}}_{k,d}(c_m), \qquad \Delta R^{\text{day}}_m = 48 \cdot \Big(R^{\text{net}}_{k,d}(t_m) - R^{\text{net}}_{k,d}(c_m)\Big)$$

where $R^{\text{net}}_{k,d}(h) = \sum_{s \in h} \big(R^{+}_{k,d,s} + R^{-}_{k,d,s}\big)$ sums settled five-minute positive and negative directional SRA residues across the six five-minute dispatch intervals inside half-hour $h$. Point estimates equal sample means over $\mathcal{M}_{k,d,f}$. To preserve multi-day outage autocorrelation, treated dates are partitioned into seven-day contiguous calendar blocks $\{B_1, \dots, B_G\}$ and resampled with replacement ($B = 150$, seed 42) via exact cluster-sum weighting:

$$\bar{\Delta}^{(b)} = \frac{\sum_{g=1}^{G} S_{u^{(b)}_g}}{\sum_{g=1}^{G} n_{u^{(b)}_g}}$$

yielding the 2.5th and 97.5th percentile 95% block-bootstrap confidence intervals.

### A.2 Strictly chronological Empirical-Bayes + hazard + isotonic calibration

Let $t_1 < t_2 < \dots < t_{12}$ be the twelve monthly NOS outlook issue origins. For each out-of-sample test origin $t_k$ ($k \ge 2$), let $\mathcal{D}_{<k}$ denote strictly prior origins $\{t_1, \dots, t_{k-1}\}$. Within $\mathcal{D}_{<k}$:

1. Lead-band occurrence hazard scaling factor per `(layer, lead_band)`:
   $$h_{\ell, b} = \text{clip}\!\left(\frac{\bar{y}_{\ell,b} + 0.01}{\bar{p}_{\text{raw},\ell,b} + 0.01},\; 0.15,\; 1.20\right)$$
2. Empirical-Bayes family binding rate shrunk toward `(layer, link, direction, lead_band)` prior $\mu_{\text{cell}}$ ($m_0 = 25$):
   $$\hat{y}^{\text{EB}}_{f} = \frac{n_f \bar{y}_f + m_0 \mu_{\text{cell}}}{n_f + m_0}$$
3. Pre-isotonic composite score incorporating family inference certainty $p_{\text{fam}}$ and system-normal anchor $p_{\text{norm}}$:
   $$s_i = \text{clip}\!\left(0.82 \cdot \big[0.45 p_{\text{fam},i} \cdot \text{clip}(p_{\text{raw},i} h_{\ell,b}, 0, 1) + (1 - 0.45 p_{\text{fam},i})\hat{y}^{\text{EB}}_{f}\big] + 0.18 p_{\text{norm},i},\; 0,\; 1\right)$$
4. Monotonic isotonic map $\hat{g}_{\ell,b} = \arg\min_{g \text{ non-decreasing}} \sum_{j \in \mathcal{D}_{<k, \ell, b}} (y_j - g(s_j))^2$, applied strictly out-of-sample on origin $t_k$ as $\hat{p}_{\text{cal},i} = \hat{g}_{\ell,b}(s_i)$.

Cell-level Brier score and Expected Calibration Error (ECE) over bins $B_1, \dots, B_K$ are:

$$\text{Brier} = \frac{1}{N}\sum_{i=1}^{N} (\hat{p}_i - y_i)^2, \qquad \text{ECE} = \sum_{r=1}^{K} \frac{|B_r|}{N} \left|\bar{p}_{B_r} - \bar{y}_{B_r}\right|$$

### A.3 N-1-1 concurrent super-additivity

For any two families $(A, B)$ with non-empty disjoint and overlapping sets ($|A \cap B| \ge 24$, $|A \setminus B| \ge 24$, $|B \setminus A| \ge 24$ half-hours) on link $k$ and direction $d$, let $C_{k,d}(h)$ be the half-hour tight directional capacity (minimum across the six five-minute intervals):

$$\Delta C_A = \bar{C}_{A \setminus B} - \bar{C}_{\overline{A \cup B}}, \qquad \Delta C_B = \bar{C}_{B \setminus A} - \bar{C}_{\overline{A \cup B}}, \qquad \Delta C_{A \cap B} = \bar{C}_{A \cap B} - \bar{C}_{\overline{A \cup B}}$$

$$S_{A,B} = \Delta C_{A \cap B} - (\Delta C_A + \Delta C_B)$$

### A.4 Hierarchical Empirical-Bayes corridor partial pooling

Within each of the eight regional transmission corridors $c$, let $\hat{\theta}_i$ be line $i$'s continuous matched outcome (season x half-hour-of-day baseline subtracted) with day-clustered standard error $s_i$ and verified event count $n_i$. Define the finite-sample adjusted variance $v_i = s_i^2 \cdot \max(1, 6 / n_i)$, precision-weighted corridor prior $\mu_c$, and empirical between-line variance $\tau_c^2$:

$$\mu_c = \frac{\sum_{i \in c} \hat{\theta}_i / v_i}{\sum_{i \in c} 1 / v_i}, \qquad \tau_c^2 = \max\!\left(\text{Var}_{i \in c}(\hat{\theta}_i) - \frac{1}{|c|}\sum_{i \in c} v_i,\; 0.30\,\text{Var}_{i \in c}(\hat{\theta}_i),\; 4.0\right)$$

$$w_i = \frac{\tau_c^2}{\tau_c^2 + v_i}, \qquad \hat{\theta}^{\text{EB}}_i = w_i \hat{\theta}_i + (1 - w_i)\mu_c$$
