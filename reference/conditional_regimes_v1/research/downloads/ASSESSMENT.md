# Cached assessment contract

This is the assessment of saved chronological predictions, separate from fitting and hyperparameter selection. It adds no model features and does not retrain. The original evaluation score tables are retained; the reports use the `assessed_*` tables.

Each row's actual pre-evaluation alert threshold is applied when aggregating across folds. Taking a median threshold across several fold policies would give a different alert decision and is not used in the final reports. Missing proportional restriction references are excluded from restriction scoring, rather than treated as non-events. Point and quantile scores retain all matched valid target rows.

Comparisons use the intersection of available rows across the seven methods. The availability table also reports all requested rows. Slices include connector/direction, quarter, delivery period, era, outage state, support and restrictive/forced outcomes.

The final historical guardrails preserve the predeclared point, quantile-loss, calibration and overstatement gates. They additionally display restriction and forced-flow precision and reject deterioration greater than two percentage points. False alerts cannot exceed the greater of one per exposure day or control plus 0.1. Extreme support must include ten distinct restricted days and ten distinct forced-flow days; five-minute/half-hour interval counts are not independent incident counts. These are conservative study conventions and not operational reliability guarantees.

These additional conservative diagnostics were specified during implementation after preliminary point results were visible. They are labelled development assessment, cannot support a pristine untouched-test claim, and cannot promote a model. All candidate predictions and negative outcomes remain in the evidence. The separate as-of track remains unavailable where historical measured receipt cannot be established.
