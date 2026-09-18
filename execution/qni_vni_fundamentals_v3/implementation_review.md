# Implementation review — not a completion certificate

The implemented continuation command runs historical acquisition, coal preparation,
daily weather acquisition, feature construction, chronological point-model fitting
and a conservative paired point audit. It does **not** yet execute every experiment
in the full research protocol. No new model is approved or activated.

## Implemented and exercised

- Dedicated SQLite execution ledger, ownership/heartbeats, checksums, method snapshots,
  dependency invalidation, daily API accounting and restartable source jobs.
- Original ST/PD PASA and near-horizon MT parsing; BOM-first coherent weather with
  ECMWF fallback and explicit exploratory/publication-assumption provenance.
- AEMO GENUNITS/DUALLOC fuel mapping and dated DUDETAIL/DUDETAILSUMMARY capacity
  records, scheduled-generator scope, retirement gaps and snapshot supersession.
- Regional/all-pair balance, demand, renewables, suppression, coal and weather
  features; same-vintage ramps and hierarchical power-system interactions.
- Three chronological feature screeners, network controls, ridge/LightGBM
  corrections, separate weather cohorts, residual intervals, seasonal references,
  immutable research packages and prediction contract checks.
- Paired calendar-block point audit and Holm correction; missing acceptance
  evidence cannot produce a promotion decision.
- Offline HTML evidence suite and 18-panel HTML presentation; absent empirical
  results are labelled absent. Desktop/narrow screenshots inspected.
- Real QNI feature smoke test and synthetic fit/package/reload test succeeded.

## Still required before the full plan is complete

1. Finish historical source backfill, validate interval coverage and acquire the
   matching weather cycles under the daily free API budget.
2. Run full QNI/VNI chronological selection and point experiments; none has yet
   established out-of-sample improvement on the acquired historical fundamentals.
3. Integrate the existing audited NOS exposure data and run the four-way factorial
   on identical eligible history. Feature hooks alone are not this experiment.
4. Run exhaustive 336-lead scoring (the fitting grid currently contains 14 leads).
5. Integrate and reassess the separate contraction classifier, probability
   calibration and joint-direction alert threshold; measure recall, incident
   count, uncertainty and power. Point overstatement is not a substitute.
6. Complete publication-delay and coal daily-boundary sensitivities, provider-policy
   overlap experiments, forecast-revision features and planned availability-state
   summaries. Current records do not prove historical receipt.
7. Export evaluated research winners and complete empirical report graphs, feature
   stability/selection review, interval diagnostics and final visual QA.

The ledger must keep these tasks open. A successful smoke test, rendered deck or
completed point fit must never be presented as an end-to-end model improvement.
