# QNI/VNI clustering experiment methodology

Version 1.0, frozen before implementation on 2026-09-22.

## Research questions

The campaign judges two questions separately:

1. Does clustering change held-out forecasts of signed flow, tight directional
   limits, calibrated intervals or two-hour contraction warnings relative to
   matched unclustered controls?
2. Does clustering expose reproducible, physically interpretable network
   regimes or generator-sensitivity groups?

Forecast results are effect estimates with uncertainty, not promotion
decisions. Stable explanatory structure can be useful without forecast uplift.

## Information tracks and claims

The primary input is the retained QNI/VNI `pasa_coal` feature generation from
the fundamentals-v3 campaign. Its provenance is
`retrospective_network_and_publication_proxy`: PASA generated times are
historical publication proxies rather than verified receipt times, coal
metadata include retrospective elements, and the 04:00 trading-day alignment
is a research assumption. The primary claim is therefore historical
development evidence, not live performance.

Origin-state clusters use only lagged network variables available at the
forecast origin. Forecast-condition clusters may add admissible delivery-time
PASA/coal features and are fitted separately by lead band. A realised-future
diagnostic, if executed, is isolated and labelled conditional research. Future
actual values and future realised cluster assignments never enter the primary
track.

All market calculations retain fixed NEM time (UTC+10), interval-ending
semantics, signed limits and target-specific origin-minus-30-minute anchors.
Reported limits remain dispatch-solution outputs, not maximum secure physical
transfer capability.

## Chronology

The retained forecast-feature overlap is about August 2025 through August
2026. Expanding folds require at least 60 days of training followed by disjoint
14-day selection, calibration and alert-tuning partitions and a 28-day
evaluation partition. Folds advance 28 days. A row belongs to a partition only
when delivery plus 30 minutes is inside that partition.

Every imputer, scaler, correlation filter, cluster solution, generator group,
SVD basis, model choice, interval adjustment and alert threshold is fitted on
its designated pre-evaluation history. Origin-state clustering fits one row per
origin. Forecast-condition clustering fits one deterministic, equally weighted
row per origin within each lead band and transforms all eligible rows.

## State clustering

Core candidates are the K=1 control, K-means and diagonal Gaussian mixtures at
K in {2, 3, 4, 6, 8}, using campaign seed 741 and two additional declared
seeds. Feature blocks are scaled separately and divided by the square root of
their retained dimension so large blocks do not dominate distance. Constants,
features with more than 80% missingness and near-duplicate correlations above
0.98 are filtered using training data only.

The sequence of forecast challengers is cluster probabilities appended to a
pooled model, regularised cluster interactions, then ridge local experts shrunk
toward the pooled model with weights in {0.25, 0.50, 0.75, 1.00}. A point beyond
the training 99th-percentile assignment distance uses the pooled fallback.

## Generator-sensitivity grouping

For each connector and fold, build a sparse equation-version by DUID matrix of
signed sensitivities (`-DUID factor / interconnector factor`, as retained in
the source sensitivity field) weighted by training invocation exposure.
Invalid or weak interconnector coefficients, non-finite values and extremes are
audited. An absent term in an otherwise verified equation is zero; an
unavailable equation is missing and never silently converted to zero.

Compare four declared interpretable groups, learned K-means groups at K=4 and
K=8, truncated SVD at 4 and 8 components, and the existing aggregate-pressure
control. At the forecast origin, DUID pressure is aggregated only from the last
complete historical half hour. Tightening and relief remain separate by
direction. Unknown units and equation versions emit explicit coverage flags.

## Models and evaluation

Matched controls are persistence, daily/weekly persistence, network-only ridge
and shallow LightGBM, and network-plus-fundamentals ridge and shallow LightGBM.
Candidates predict persistence residuals. Selection is separate by connector,
target and lead band. Intervals use later calibration rows. Contraction models
use a dedicated alert-tuning partition and the existing 30-to-120-minute event
window.

Report MAE, RMSE, bias, P90/P95/P99 absolute error, paired absolute and
percentage changes, interval coverage/width/WIS, capacity overstatement, event
recall/precision/Brier score and false alerts per exposure day. Use paired 7-
and 14-day block bootstrap intervals and Holm-adjusted primary comparisons.
Fewer than eight evaluation weeks or 30 incidents is limited support.

Explanatory regimes are called recurring only when median adjusted Rand index
is at least 0.70 and the regime appears on at least 30 training days and 14
evaluation days. Season, time-of-day and missingness controls must be shown.
These are study conventions, not universal academic thresholds. Descriptive
episodes are not causal evidence.

## Order, resources and completion

Run inventory and a bounded VNI pilot first, then VNI core evaluation, QNI
replication, robustness/conditional diagnostics and reporting. Protect the core
two tracks and QNI replication; optional density, transition and daily-shape
methods are recommendations only. Do not run connector model campaigns in
parallel. Within an active connector, use at most two workers and two numerical
threads per worker, combined RSS at most 8 GB, free disk at least 20 GB and a
48-hour modelling budget.

Runtime stages are content-addressed and resumable. Completion requires cached
predictions, compact evidence, manifests and hashes, focused tests, the full
test suite, Markdown plus self-contained offline HTML, link/hash validation and
representative desktop/mobile visual checks. A future unseen-data protocol is
part of the report; collecting future data, deployment, scheduling and Git
publication are outside this campaign.

