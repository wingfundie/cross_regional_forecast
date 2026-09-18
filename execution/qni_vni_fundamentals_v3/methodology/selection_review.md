# Feature reduction methodology review

Written before selector implementation, 2026-09-17.

## Alternatives

1. Correlation-group screening removes algebraic/near duplicates cheaply but can remove a useful interaction parent; use deterministic representative selection with hierarchy restoration.
2. Standardized elastic net handles collinearity and offers sparse screening; coefficients are predictive, scaling-dependent and unstable between correlated substitutes. Restore parents and compare group stability.
3. Shallow-tree grouped permutation captures nonlinear usefulness. Individual permutation can underrate correlated variables; jointly permute feature blocks and interaction parents. Use chronological blocks, not independently shuffled future-origin rows, for selection uncertainty.
4. Sequential elimination compares progressively smaller ranked group sets on the same inner validation periods. It costs more than filtering; pilot runtime sets the search budget. There is no arbitrary final count cap.

Scikit-learn's correlated-feature example demonstrates why a strong predictive model can show weak individual permutation importance: https://scikit-learn.org/stable/auto_examples/inspection/plot_permutation_importance_multicollinear.html . Nested chronological selection and preprocessing protect the outer comparison from selecting on evaluation outcomes. See docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md sections 9 and 14 for the existing local evidence and literature review.

## Frozen initial procedure

Fit quality filters and fills in each inner training split, keep explicit missing-quality fields, cluster abs Spearman >0.98 among main effects, and preserve a full network-only control. Rank groups using the three candidate approaches. Assess nested group fractions 0.25/0.5/0.75/1 with ridge correction as the inexpensive common probe. Rank group counts, not arbitrary unstructured products. Choose the smallest set whose MAE is within one standard error of the best, using paired seven-day validation-block losses. Then freeze schema before full ridge/LightGBM tuning. Report any selector not executed.

The outer training fold may refit the chosen screening procedure; it may not consult outer evaluation labels. Calibrators and alert thresholds have separate later windows. Keep parent closure even when that increases the selected count. Main effects and interactions compete through explicit ablation, not only a feature-importance ranking.

## Required result fields

Method, connector, target, lead band, fold, training rows/origins, original/filtered/retained feature counts, exclusions/reasons, parent map, inner losses, standard error, fit seconds and selection frequency. Reduction-versus-MAE and stability charts are generated only from measured results. If historical source overlap is insufficient, publish unavailable status, not a synthetic model score.
