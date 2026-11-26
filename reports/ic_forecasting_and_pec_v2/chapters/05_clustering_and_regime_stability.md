## Chapter 5 · Leakage-Controlled Regime Clustering and Stability Audit

Unsupervised clustering is a recurring proposal in electricity market modelling: partition historical market intervals into discrete operating regimes (such as "high-solar midday congestion," "evening peak scarcity," or "mild overnight slack") using K-means or Gaussian Mixture Models (GMM), and then train either cluster-interaction features or separate local expert regressors inside each cluster. The intuition is appealing, because Flagship Edition A proved that interconnector limits jump across qualitatively different physical constraint regimes.

Yet clustering in time-series forecasting is notoriously vulnerable to two subtle statistical illusions: in-sample look-ahead leakage (fitting cluster centroids across the entire dataset before evaluating out-of-sample folds) and multiple-testing cherry-picking (reporting a few favourable fold-horizon wins while ignoring dozens of neutral or negative folds). The repository's leakage-controlled clustering campaign (`qni_vni_clustering_v1`) eliminated both illusions by fitting all cluster partitions strictly inside pre-origin training windows across 10 chronological folds, measuring chronological stability via Adjusted Rand Index (ARI), and benchmarking every cluster model against matched control models (`boost_fundamentals`, `boost_network`, `ridge_fundamentals`, `ridge_network`, `persistence`, and seasonal baselines) with seven-day block-bootstrap p-values and Holm-Bonferroni family-wise error correction.

### 5.1 Structural state stability: only coarse two-state partitions persist chronologically

Before a cluster label can help a live forecasting pipeline, the discovered regimes must actually recur consistently across consecutive chronological folds rather than mutating randomly each month. Measuring both random-seed stability (`seed_ari`) and out-of-sample chronological block stability (`block_ari`) across $k \in \{1, 2, 3, 4, 6, 8\}$ exposes a clear structural boundary.

| Connector | Method | k = 2 block ARI (seed ARI) | k = 3 block ARI (seed ARI) | k = 4 block ARI (seed ARI) | k = 6 block ARI (seed ARI) | k = 8 block ARI (seed ARI) | Stability verdict |
|---|---|---:|---:|---:|---:|---:|---|
| VNI | K-means | **0.94** (1.00) | 0.88 (1.00) | 0.71 (0.92) | 0.87 (0.99) | 0.66 (0.96) | Coarse k=2-3 stable; decays at k>=4 |
| VNI | GMM | **0.89** (1.00) | 0.71 (0.79) | 0.61 (0.85) | 0.45 (0.67) | 0.47 (0.51) | Unstable beyond k=2 |
| QNI | K-means | **0.89** (1.00) | **0.94** (1.00) | 0.91 (1.00) | 0.87 (0.97) | 0.78 (0.92) | K-means stable to k=4 |
| QNI | GMM | 0.37 (1.00) | 0.89 (1.00) | 0.77 (0.86) | 0.71 (0.79) | 0.71 (0.77) | Erratic at k=2 and k>=6 |

{{exhibit:c9}}

Look at the telling divergence between `seed_ari` and `block_ari` on VNI: K-means achieves near-perfect seed reproducibility (0.96 to 1.00 across $k=2$ to $k=8$) when refit on the same window, yet its chronological block stability falls from 0.94 at $k=2$ down to 0.71 at $k=4$ and 0.66 at $k=8$. Gaussian Mixture Models decay even faster on VNI, dropping from 0.89 at $k=2$ to 0.45 at $k=6$ and 0.47 at $k=8$. What the algorithm cleanly recovers across time is the dominant binary day/night or solar/non-solar split ($k=2$ to $k=3$), which is already captured deterministically by simple clock-hour and solar-irradiance features. Attempting to slice the NEM into six or eight unsupervised sub-regimes mostly chases transient seasonal weather clusters that do not recur reliably in the next chronological block.

### 5.2 Forecasting accuracy versus matched controls: 0 of 241 survive Holm correction

Across all 241 seven-day block-bootstrap evaluations comparing cluster-based models (`cluster_local_experts` and `cluster_interactions`) against matched controls across VNI and QNI folds, horizon bands, and targets, the verdict is clear: 155 of 241 raw evaluations showed negative point MAE deltas (apparent gains), yet exactly 0 of 241 survived Holm-Bonferroni multiple-testing correction at the 5% significance level.

| Connector | Matched control model | Target | 7-day evaluations | Mean MAE delta (MW) | Mean MAE delta (%) | Raw point wins | Unadjusted p < 0.05 wins | Holm-Bonferroni sig. wins |
|---|---|---|---:|---:|---:|---:|---:|---:|
| VNI | `boost_fundamentals` | `flow` | 29 | -44.7 | -16.2% | 27 | 17 | **0** |
| VNI | `boost_fundamentals` | `import_tight` | 19 | -28.3 | -13.8% | 18 | 13 | **0** |
| VNI | `boost_fundamentals` | `export_tight` | 18 | -27.9 | -12.7% | 14 | 7 | **0** |
| VNI | `boost_network` | `export_tight` | 6 | +34.0 | +10.4% | 1 | 1 | **0** |
| VNI | `ridge_fundamentals` | `export_tight` | 11 | -3.9 | -2.5% | 6 | 6 | **0** |
| VNI | `ridge_fundamentals` | `import_tight` | 13 | +1.1 | +0.4% | 5 | 1 | **0** |
| QNI | `boost_fundamentals` | `import_tight` | 15 | -136.3 | -98.1% | 12 | 10 | **0** |
| QNI | `boost_fundamentals` | `export_tight` | 18 | -57.9 | -42.8% | 14 | 11 | **0** |
| QNI | `boost_fundamentals` | `flow` | 22 | -19.4 | -9.4% | 14 | 10 | **0** |
| QNI | `ridge_fundamentals` | `export_tight` | 8 | -2.1 | -0.9% | 6 | 5 | **0** |
| QNI | `ridge_fundamentals` | `flow` | 13 | +6.4 | +1.1% | 4 | 2 | **0** |

{{exhibit:c10}}

Why do cluster models appear to beat `boost_fundamentals` by 13% to 43% in raw unadjusted tables, yet shrink to roughly zero (-2.5% to +1.1%) against `ridge_fundamentals` and lose by +10.4% against `boost_network` on VNI export-tight?

The diagnostic explanation is straightforward and instructive for every quantitative team:
1. **Unconstrained gradient boosting on fundamentals alone overfits across regimes:** When a global tree model is given raw regional demand and renewable fundamentals without network-state features (`boost_fundamentals`), partitioning the data into coarse clusters acts merely as a crude regulariser.
2. **Once proper regularisation (`ridge_fundamentals`) or explicit network-state features (`boost_network`) are included in the control model, the clustering advantage evaporates:** Against `ridge_fundamentals`, mean cluster MAE changes collapse to -2.5% to +1.1% across both VNI and QNI. Against `boost_network` on VNI, clustering actively degrades accuracy by +1.4% on flow, +1.9% on import-tight, and +10.4% on export-tight because hard cluster boundaries fragment already scarce outage-regime training samples across separate local trees.

### 5.3 Why explicit physical state features outperform unsupervised clusters

The contrast between `+10.4%` MAE degradation under `cluster_local_experts` versus `boost_network` on VNI export-tight highlights an elementary bias-variance trade-off that applies across every power-system forecasting task.

Consider a two-year training window containing roughly 730 calendar days, of which only 45 to 80 days exhibit an active Southern NSW 330 kV outage regime (such as a Line 6 or Line 8 work window mapped in Flagship Edition B). If a global network-state model receives continuous, physically grounded regime descriptors directly as input features (specifically the leading active constraint family, the `setter_matched` audit flag from Flagship Edition A, signed directional headroom, and the chronologically calibrated NOS binding probability $p_{\text{cal}}$ from Flagship Edition B), every decision tree retains access to all 730 training days while splitting sharply on the exact physical outage flag whenever it turns active.

By contrast, fitting an unsupervised K-means or GMM partition on regional demand, wind, and solar splits those 730 days across $k=6$ or $k=8$ weather-driven centroids that are largely orthogonal to transmission maintenance schedules. Each local expert regressor now sees only 6 to 12 outage days inside its assigned cluster, causing severe small-sample variance and brittle boundary jumps whenever an afternoon cloud front pushes an hour across a Voronoi boundary from Cluster 3 into Cluster 5. Moreover, because cluster labels are estimated from continuous weather variables, any shift in seasonal solar output or new battery capacity shifts cluster geometry between chronological folds (driving VNI GMM `block_ari` down to 0.45 at $k=6$), whereas physical transmission constraint equations and NOS corridor tags remain anchored to the actual high-voltage topology.

> [!WARNING] Engineering Verdict on Regime Clustering
> Do not add unsupervised K-means or GMM cluster-splitting layers into operational interconnector forecasting pipelines. Explicit physical network-state features (leading constraint family, `setter_matched` flag, signed directional headroom, and calibrated NOS outage occupancy from Flagships A and B) outperform black-box unsupervised clusters without fragmenting training sample sizes or failing multiple-testing gates.

Chapter 6 now consolidates all ten registered workstreams across the entire repository into a clear three-stack governance map and defines the exact prospective receipt-time confirmation gates required before promoting any live interconnector forecast model.
