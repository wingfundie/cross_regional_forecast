# Forward forecasting: evidence and verdict

Presentation: 5 October 2026. Results are frozen historical research; no new fit or live forecast is claimed.

## 01 · What can be used now

Use the calendar baseline and target persistence as transparent research references. The VNI diurnal policy is the strongest short-range candidate for prospective testing. No saved research model has established an operational forward-forecasting claim. The new long-range campaign promotes zero replacements, and its shadow route retains calendar in every cell. Both collection and shadow schedules were paused at the user’s request on 4 October 2026.



  
    

      Component | 
      Permitted use | 
      Condition / limitation | 
    

  
  
    

      Calendar + persistence | 
      Reference outlook / manual shadow | 
      Track both; calendar is the retained route, not proven best everywhere | 
    

    

      VNI diurnal/NOS v2 | 
      Priority short-range shadow candidate | 
      Verify live feature contract and recalibrate uncertainty | 
    

    

      QNI diurnal/NOS v2 | 
      Target-specific research only | 
      Mixed skill and inconclusive primary confidence bounds | 
    

    

      Long-range MT PASA v1 | 
      Sparse-horizon research outlook | 
      No challenger passes; not a full 4,320-step path | 
    

    

      Six-link original backtest | 
      Conditional scenarios | 
      Realised future fundamentals preclude a live accuracy claim | 
    

    

      NOS / outage scenarios | 
      Qualitative risk and scenario analysis | 
      Associations and scenario deltas are not calibrated event probabilities | 
    

    

      Fundamentals v3 / clustering | 
      Development evidence | 
      Revalidation and prospective confirmation remain outstanding | 
    

    

      Production scaffold | 
      Reusable engineering components | 
      Not an approved deployed service or model promotion | 
    

    

      Valuation v2 | 
      Historical settlement / hedge research | 
      Forward futures history and issue-time regimes still required | 
    

  



## 02 · What the new experiment actually covers

The prepared dataset contains 305 daily origins from 2 August 2025 to 2 June 2026 and 54,900 connector-target-lead rows. The held-out block contains 56 daily origins; each target has 1,008 evaluated rows. Only 18 half-hour-indexed leads are sampled. Each shadow output therefore has 90 rows per connector (18 leads × 5 targets), rather than 90 daily values or a complete half-hour curve. Delivery outcomes extend to day 90 after the last origin. Historical report-generation times are availability proxies, not measured receipts.


The first band includes 0.5 hours through 7 days. Only two sampled leads support each later band. Results cannot establish accuracy for every intervening half-hour, every delivery period, or all seasons.


  
    

      Lead index | 
      Hours ahead | 
      Days ahead | 
    

  
  
    

      1 | 
      0.50 | 
      0.02 | 
    

    

      3 | 
      1.50 | 
      0.06 | 
    

    

      6 | 
      3.00 | 
      0.12 | 
    

    

      12 | 
      6.00 | 
      0.25 | 
    

    

      24 | 
      12.00 | 
      0.50 | 
    

    

      48 | 
      24.00 | 
      1.00 | 
    

    

      96 | 
      48.00 | 
      2.00 | 
    

    

      144 | 
      72.00 | 
      3.00 | 
    

    

      240 | 
      120.00 | 
      5.00 | 
    

    

      336 | 
      168.00 | 
      7.00 | 
    

    

      480 | 
      240.00 | 
      10.00 | 
    

    

      672 | 
      336.00 | 
      14.00 | 
    

    

      960 | 
      480.00 | 
      20.00 | 
    

    

      1440 | 
      720.00 | 
      30.00 | 
    

    

      2160 | 
      1080.00 | 
      45.00 | 
    

    

      2880 | 
      1440.00 | 
      60.00 | 
    

    

      3600 | 
      1800.00 | 
      75.00 | 
    

    

      4320 | 
      2160.00 | 
      90.00 | 
    

  



## 03 · New results: comparison with both controls

“Selection winner” means the model chosen before evaluation; it does not mean a promoted model. VNI gains little against calendar even where it beats persistence. QNI export and flow gains against calendar disappear against persistence. QNI import is promising on average, but fails the dependence-aware confidence gates. A 75% / 25% weighting of the two primary bands cannot substitute for evidence in both bands.

Weighted primary skill by target[Data ↓](downloads/cell_results.csv)
[Chart: Weighted primary skill by target — see HTML edition]

Frozen selection winners; matched evaluation rows. Calendar winners have exactly zero skill against themselves.


  
    

      Connector | 
      Target | 
      Selection winner | 
      Skill vs calendar (%) | 
      Skill vs persistence (%) | 
      Decision | 
    

  
  
    

      VNI | 
      export_tight | 
      calendar | 
      0.00 | 
      25.66 | 
      retain_baseline | 
    

    

      VNI | 
      import_tight | 
      boosting | 
      -1.29 | 
      29.32 | 
      retain_baseline | 
    

    

      VNI | 
      export | 
      boosting | 
      -4.19 | 
      29.26 | 
      retain_baseline | 
    

    

      VNI | 
      import | 
      calendar | 
      0.00 | 
      22.88 | 
      retain_baseline | 
    

    

      VNI | 
      flow | 
      boosting | 
      3.01 | 
      22.32 | 
      retain_baseline | 
    

    

      QNI | 
      export_tight | 
      boosting | 
      17.85 | 
      -42.71 | 
      retain_baseline | 
    

    

      QNI | 
      import_tight | 
      ridge | 
      36.88 | 
      9.58 | 
      retain_baseline | 
    

    

      QNI | 
      export | 
      boosting | 
      7.69 | 
      -50.11 | 
      retain_baseline | 
    

    

      QNI | 
      import | 
      ridge | 
      39.25 | 
      12.19 | 
      retain_baseline | 
    

    

      QNI | 
      flow | 
      ridge | 
      6.47 | 
      -26.26 | 
      retain_baseline | 
    

  



## 04 · VNI: tight-limit performance by horizon

Tight limits are the minimum of the six five-minute observations in each complete half-hour. The retained sign convention matters: negative limits can represent forced flow. These are AEMO dispatch-solution limits, not maximum secure physical transfer capability. Lines connect sampled-band summaries and do not represent a continuous forecast path.

VNI tight-limit MAE[Data ↓](downloads/band_metrics.csv)
[Chart: VNI tight-limit MAE — see HTML edition]

Lower is better. Same held-out population within each cell; band populations differ.


## 04 · QNI: tight-limit performance by horizon

Tight limits are the minimum of the six five-minute observations in each complete half-hour. The retained sign convention matters: negative limits can represent forced flow. These are AEMO dispatch-solution limits, not maximum secure physical transfer capability. Lines connect sampled-band summaries and do not represent a continuous forecast path.

QNI tight-limit MAE[Data ↓](downloads/band_metrics.csv)
[Chart: QNI tight-limit MAE — see HTML edition]

Lower is better. Same held-out population within each cell; band populations differ.


## 05 · Uncertainty is still a separate gate

3 of 10 selected-model cells meet both empirical interval thresholds in both primary bands. These coverage checks do not establish prospective calibration, interval sharpness, or coverage of the retained calendar route where a challenger was evaluated. Interval widths, event precision/recall and false-alert durations are not present in this compact long-range evidence; they remain unverified, not zero. Wide intervals can achieve coverage without being useful.

Empirical interval coverage (%)[Data ↓](downloads/band_metrics.csv)
[Chart: Empirical interval coverage (%) — see HTML edition]

Coverage applies to the selection winner. Acceptance floors are 77% / 92% for nominal 80% / 95%.


## 06 · Why the headline gains do not pass

Promotion requires at least 2% weighted skill against both controls and a strictly positive lower confidence bound against both controls in each primary band. None passes all conditions. The seven-day moving-block bootstrap accounts for short-run dependence, but the evaluation contains only 56 issue days; long-lead overlap and a single seasonal evaluation window limit generalisation. The chart shows confidence interval ranges; dots indicate interval midpoints, not separately estimated effects.

Primary-band improvement confidence intervals[Data ↓](downloads/band_metrics.csv)
[Chart: Primary-band improvement confidence intervals — see HTML edition]

Crossing zero means an improvement is not established by this gate.


## 07 · How the earlier research changes the verdict

VNI diurnal v2 has the strongest retrospective evidence: tight-export skill versus persistence is 33.2%, 42.0%, 36.3% and 19.8% across its four bands through seven days; tight-import skill is 17.1%, 25.1%, 26.4% and 22.0%. Its primary moving-block tests exclude zero. QNI is mixed: the shortest-band export improves 4.6%, while import worsens 8.7%, and primary confidence intervals include zero. These studies have different samples, features and protocols from long-range v1; their percentages must not be ranked as a single leaderboard.


VNI nominal 80% / 95% intervals cover 74.14% / 90.53%; QNI covers 71.93% / 87.41%. Both under-cover. The diurnal “calendar policy” includes learned delivery-time specialisation and observed history; it is not the simple calendar-only long-range baseline. NOS point-model additions were not admitted to the VNI default. Fundamentals v3 retains a historical report but requires ledger revalidation. Clustering remains development evidence; no promotion record is established here.
Earlier diurnal models: interval undercoverage[Data ↓](downloads/earlier_coverage.csv)
[Chart: Earlier diurnal models: interval undercoverage — see HTML edition]

Twelve rolling monthly folds; delivery-period calibration; distinct from long-range v1.


## 08 · Data, method and implementation changes

Origins are fixed at 08:00 NEM time (UTC+10), equivalent to 06:00 Singapore. The experiment compares a seasonal calendar model, target-specific persistence at origin minus 30 minutes, ridge and fixed shallow boosting. Challengers add coherent source/sink MT PASA availability summaries and the observed target anchor. Selection and calibration each reserve 28 origins and evaluation reserves 56; delivery outcomes are purged at boundaries. This is a single chronological held-out experiment, not repeated walk-forward confirmation.


The new implementation preserves source/product/run identity, completed receipt time, age and hashes; records only lineage actually used; supports revision-aware outcomes, daily alert episodes and outage scenarios; and extends the scaffold’s horizon contract. These are engineering improvements, not measured forecasting skill. Prospective source selection requires receipt completed before issue and source age no greater than 42 hours. Realised future weather, demand, VRE, dispatch and constraint setters are excluded from this challenger.

The challenger adds an anchor as well as availability features relative to the calendar baseline. Consequently, this comparison does not isolate the incremental contribution of MT PASA; an anchor-only matched ablation is still needed. No matched AEMO forecast comparison is supplied in the new long-range scorecard.


## 09 · Practical route to usable forward forecasts

First establish a trusted prospective scorecard, then add complexity only when matched evidence supports it. Schedules remain paused; publishing this report does not resume collection or shadow execution.



- Freeze the evidence contract. Keep the new evaluation as development evidence. Specify point, risk and interval acceptance rules before the next unseen period.

- Complete delivery coverage. Generate and assess the requested 4,320 half-hour leads, with season and delivery-period breakdowns. Sparse lead tests are insufficient for a daily full-path product.

- Prove the feed. When collection is deliberately resumed, preserve completed receipts, coherent vintages, coverage, stale-source fallbacks and immutable issued forecasts.

- Test simple alternatives first. Run calendar, persistence and calendar-plus-anchor on identical rows. Add MT PASA alone next; use matched AEMO vintages where available.

- Prioritise VNI short-range. Reproduce its exact saved feature contract and collect prospective predictions. Treat QNI by direction and lead, with persistence retained as a serious competitor.

- Repair uncertainty and risk. Calibrate on eligible history and report coverage plus width, incident recall/precision, false episodes and duration. Test the agreed budget of at most three false episodes per connector per day.

- Promote only after confirmation. Require positive point-skill evidence against both controls, acceptable uncertainty and risk, provenance checks and an explicit promotion record. Use out-of-fold upstream forecasts in downstream valuation.


## 10 · Full long-range evidence

All 50 target-band records are provided below and as CSV. Missing metrics are not inferred. These compact tables allow independent comparison without publishing raw observations or fitted models.



  
    

      connector | 
      target | 
      winner | 
      band | 
      rows | 
      origins | 
      model_mae | 
      baseline_mae | 
      skill | 
      improvement_mw_ci95 | 
      persistence_mae | 
      skill_vs_persistence | 
      persistence_improvement_mw_ci95 | 
      coverage_80 | 
      coverage_95 | 
      calibrated | 
    

  
  
    

      VNI | 
      export_tight | 
      calendar | 
      days_1_7 | 
      560 | 
      56 | 
      304.60 | 
      304.60 | 
      0.00 | 
      [0.0, 0.0] | 
      416.71 | 
      0.27 | 
      [83.24478190451393, 150.3328768887248] | 
      0.91 | 
      0.99 | 
      True | 
    

    

      VNI | 
      export_tight | 
      calendar | 
      days_8_14 | 
      112 | 
      56 | 
      231.50 | 
      231.50 | 
      0.00 | 
      [0.0, 0.0] | 
      296.49 | 
      0.22 | 
      [24.400417309135538, 121.91644654952886] | 
      0.87 | 
      0.95 | 
      True | 
    

    

      VNI | 
      export_tight | 
      calendar | 
      days_15_30 | 
      112 | 
      56 | 
      265.74 | 
      265.74 | 
      0.00 | 
      [0.0, 0.0] | 
      357.66 | 
      0.26 | 
      [47.855361783752116, 152.00996496374592] | 
      0.89 | 
      0.96 | 
      True | 
    

    

      VNI | 
      export_tight | 
      calendar | 
      days_31_60 | 
      112 | 
      56 | 
      343.07 | 
      343.07 | 
      0.00 | 
      [0.0, 0.0] | 
      431.02 | 
      0.20 | 
      [7.994379858695908, 167.4749070727109] | 
      0.84 | 
      0.93 | 
      True | 
    

    

      VNI | 
      export_tight | 
      calendar | 
      days_61_90 | 
      112 | 
      56 | 
      396.24 | 
      396.24 | 
      0.00 | 
      [0.0, 0.0] | 
      538.53 | 
      0.26 | 
      [35.75143110703578, 202.67191003171314] | 
      0.78 | 
      0.92 | 
      False | 
    

    

      VNI | 
      import_tight | 
      boosting | 
      days_1_7 | 
      560 | 
      56 | 
      210.58 | 
      208.21 | 
      -0.01 | 
      [-9.59936278877806, 5.313931255640374] | 
      300.69 | 
      0.30 | 
      [52.28553824357325, 125.47318349157402] | 
      0.67 | 
      0.87 | 
      False | 
    

    

      VNI | 
      import_tight | 
      boosting | 
      days_8_14 | 
      112 | 
      56 | 
      228.82 | 
      224.92 | 
      -0.02 | 
      [-12.103615109569425, 2.4209798796782303] | 
      315.01 | 
      0.27 | 
      [32.42730455332619, 124.03928213327325] | 
      0.37 | 
      0.75 | 
      False | 
    

    

      VNI | 
      import_tight | 
      boosting | 
      days_15_30 | 
      112 | 
      56 | 
      271.49 | 
      269.74 | 
      -0.01 | 
      [-4.738243350552389, 0.3125465954024215] | 
      332.66 | 
      0.18 | 
      [3.7544157475604387, 108.53179448104122] | 
      0.59 | 
      0.82 | 
      False | 
    

    

      VNI | 
      import_tight | 
      boosting | 
      days_31_60 | 
      112 | 
      56 | 
      352.34 | 
      355.69 | 
      0.01 | 
      [-0.6452389492138106, 8.249626462570731] | 
      396.37 | 
      0.11 | 
      [3.101680857540155, 94.47219809183996] | 
      0.50 | 
      0.79 | 
      False | 
    

    

      VNI | 
      import_tight | 
      boosting | 
      days_61_90 | 
      112 | 
      56 | 
      291.40 | 
      290.08 | 
      -0.00 | 
      [-4.594329789415412, 4.629130029683938] | 
      367.36 | 
      0.21 | 
      [29.273440093294376, 113.1590700262548] | 
      0.60 | 
      0.84 | 
      False | 
    

    

      VNI | 
      export | 
      boosting | 
      days_1_7 | 
      560 | 
      56 | 
      276.28 | 
      260.44 | 
      -0.06 | 
      [-27.820570281915046, -3.9485583261769377] | 
      393.47 | 
      0.30 | 
      [86.58132487919981, 155.84090802700374] | 
      0.89 | 
      0.99 | 
      True | 
    

    

      VNI | 
      export | 
      boosting | 
      days_8_14 | 
      112 | 
      56 | 
      198.99 | 
      201.97 | 
      0.01 | 
      [-4.620943349707873, 10.421280956070795] | 
      275.23 | 
      0.28 | 
      [34.5277631355394, 121.77547608757759] | 
      0.83 | 
      0.91 | 
      False | 
    

    

      VNI | 
      export | 
      boosting | 
      days_15_30 | 
      112 | 
      56 | 
      243.68 | 
      251.77 | 
      0.03 | 
      [6.060377986155303, 15.194283957433623] | 
      345.45 | 
      0.29 | 
      [52.13277002151559, 155.88929488322233] | 
      0.91 | 
      0.96 | 
      True | 
    

    

      VNI | 
      export | 
      boosting | 
      days_31_60 | 
      112 | 
      56 | 
      330.17 | 
      339.57 | 
      0.03 | 
      [2.2125313563209197, 16.703736775353843] | 
      410.24 | 
      0.20 | 
      [12.751366027178491, 156.12010261187692] | 
      0.87 | 
      0.92 | 
      False | 
    

    

      VNI | 
      export | 
      boosting | 
      days_61_90 | 
      112 | 
      56 | 
      388.33 | 
      391.01 | 
      0.01 | 
      [-5.3385199818246525, 7.707428793767654] | 
      529.63 | 
      0.27 | 
      [52.18170310326238, 189.29374627199866] | 
      0.79 | 
      0.89 | 
      False | 
    

    

      VNI | 
      import | 
      calendar | 
      days_1_7 | 
      560 | 
      56 | 
      208.96 | 
      208.96 | 
      0.00 | 
      [0.0, 0.0] | 
      269.95 | 
      0.23 | 
      [24.48679188505332, 105.54978621044212] | 
      0.71 | 
      0.88 | 
      False | 
    

    

      VNI | 
      import | 
      calendar | 
      days_8_14 | 
      112 | 
      56 | 
      218.13 | 
      218.13 | 
      0.00 | 
      [0.0, 0.0] | 
      286.10 | 
      0.24 | 
      [9.717819642371127, 121.22840134682389] | 
      0.52 | 
      0.82 | 
      False | 
    

    

      VNI | 
      import | 
      calendar | 
      days_15_30 | 
      112 | 
      56 | 
      265.43 | 
      265.43 | 
      0.00 | 
      [0.0, 0.0] | 
      305.54 | 
      0.13 | 
      [-6.654847751953943, 88.25310277547266] | 
      0.63 | 
      0.80 | 
      False | 
    

    

      VNI | 
      import | 
      calendar | 
      days_31_60 | 
      112 | 
      56 | 
      345.07 | 
      345.07 | 
      0.00 | 
      [0.0, 0.0] | 
      379.61 | 
      0.09 | 
      [-1.8374655440736616, 72.5566967736922] | 
      0.52 | 
      0.73 | 
      False | 
    

    

      VNI | 
      import | 
      calendar | 
      days_61_90 | 
      112 | 
      56 | 
      279.80 | 
      279.80 | 
      0.00 | 
      [0.0, 0.0] | 
      323.11 | 
      0.13 | 
      [5.148070096101162, 79.35987917307035] | 
      0.66 | 
      0.82 | 
      False | 
    

    

      VNI | 
      flow | 
      boosting | 
      days_1_7 | 
      560 | 
      56 | 
      342.43 | 
      354.00 | 
      0.03 | 
      [2.522473666113373, 18.2584798903382] | 
      473.44 | 
      0.28 | 
      [86.32601629693828, 206.8694832851274] | 
      0.71 | 
      0.94 | 
      False | 
    

    

      VNI | 
      flow | 
      boosting | 
      days_8_14 | 
      112 | 
      56 | 
      441.29 | 
      451.37 | 
      0.02 | 
      [-0.6849970927601502, 20.192459736130644] | 
      470.89 | 
      0.06 | 
      [-127.67570046876743, 228.02251165798117] | 
      0.84 | 
      0.98 | 
      True | 
    

    

      VNI | 
      flow | 
      boosting | 
      days_15_30 | 
      112 | 
      56 | 
      420.52 | 
      439.12 | 
      0.04 | 
      [13.539572181664516, 29.53331960386128] | 
      547.48 | 
      0.23 | 
      [16.160395266323036, 181.5879210808661] | 
      0.61 | 
      1.00 | 
      False | 
    

    

      VNI | 
      flow | 
      boosting | 
      days_31_60 | 
      112 | 
      56 | 
      419.47 | 
      452.81 | 
      0.07 | 
      [15.077101475503442, 48.00193770458647] | 
      524.69 | 
      0.20 | 
      [17.846908286091235, 157.55750114403156] | 
      0.63 | 
      1.00 | 
      False | 
    

    

      VNI | 
      flow | 
      boosting | 
      days_61_90 | 
      112 | 
      56 | 
      366.59 | 
      387.70 | 
      0.05 | 
      [14.20248673407057, 37.935012732333924] | 
      559.38 | 
      0.34 | 
      [59.39831727054715, 252.61750594403887] | 
      0.74 | 
      1.00 | 
      False | 
    

    

      QNI | 
      export_tight | 
      boosting | 
      days_1_7 | 
      560 | 
      56 | 
      294.97 | 
      367.01 | 
      0.20 | 
      [48.40593759109056, 99.56475935667115] | 
      187.40 | 
      -0.57 | 
      [-198.15763418186992, -44.424047538482384] | 
      0.93 | 
      0.98 | 
      True | 
    

    

      QNI | 
      export_tight | 
      boosting | 
      days_8_14 | 
      112 | 
      56 | 
      323.33 | 
      369.49 | 
      0.12 | 
      [15.029568409334065, 73.14850858669811] | 
      327.77 | 
      0.01 | 
      [-78.88189726113067, 104.94714879762358] | 
      0.85 | 
      0.96 | 
      True | 
    

    

      QNI | 
      export_tight | 
      boosting | 
      days_15_30 | 
      112 | 
      56 | 
      356.30 | 
      415.26 | 
      0.14 | 
      [38.784419560885986, 78.60256747559347] | 
      282.00 | 
      -0.26 | 
      [-165.8604445253199, 1.4164887667560841] | 
      0.93 | 
      1.00 | 
      True | 
    

    

      QNI | 
      export_tight | 
      boosting | 
      days_31_60 | 
      112 | 
      56 | 
      324.85 | 
      389.09 | 
      0.17 | 
      [50.1582614408674, 85.81959545112014] | 
      374.01 | 
      0.13 | 
      [-70.4568239776239, 132.52163443497622] | 
      0.86 | 
      0.99 | 
      True | 
    

    

      QNI | 
      export_tight | 
      boosting | 
      days_61_90 | 
      112 | 
      56 | 
      196.00 | 
      196.77 | 
      0.00 | 
      [-25.257920186973255, 25.782719494457886] | 
      410.48 | 
      0.52 | 
      [136.2836280666288, 294.64958224548747] | 
      0.76 | 
      0.94 | 
      False | 
    

    

      QNI | 
      import_tight | 
      ridge | 
      days_1_7 | 
      560 | 
      56 | 
      272.69 | 
      440.37 | 
      0.38 | 
      [86.20747606070904, 308.6922352219349] | 
      274.74 | 
      0.01 | 
      [-39.29681956948652, 47.29338251898452] | 
      0.57 | 
      0.74 | 
      False | 
    

    

      QNI | 
      import_tight | 
      ridge | 
      days_8_14 | 
      112 | 
      56 | 
      301.61 | 
      452.25 | 
      0.33 | 
      [-52.096541180975656, 315.9502902310517] | 
      471.93 | 
      0.36 | 
      [47.03437881551488, 281.17538246535184] | 
      0.51 | 
      0.56 | 
      False | 
    

    

      QNI | 
      import_tight | 
      ridge | 
      days_15_30 | 
      112 | 
      56 | 
      313.30 | 
      498.14 | 
      0.37 | 
      [87.25030619298174, 313.58624042329376] | 
      419.25 | 
      0.25 | 
      [80.4462412607686, 136.21075916417703] | 
      0.46 | 
      0.62 | 
      False | 
    

    

      QNI | 
      import_tight | 
      ridge | 
      days_31_60 | 
      112 | 
      56 | 
      411.66 | 
      371.36 | 
      -0.11 | 
      [-231.2817300998525, 145.35075126763758] | 
      511.22 | 
      0.19 | 
      [60.749763462583815, 168.81481372587592] | 
      0.36 | 
      0.44 | 
      False | 
    

    

      QNI | 
      import_tight | 
      ridge | 
      days_61_90 | 
      112 | 
      56 | 
      498.83 | 
      174.67 | 
      -1.86 | 
      [-440.0503013979428, -256.8078648215029] | 
      501.42 | 
      0.01 | 
      [-60.00400289106169, 72.4491914513526] | 
      0.09 | 
      0.15 | 
      False | 
    

    

      QNI | 
      export | 
      boosting | 
      days_1_7 | 
      560 | 
      56 | 
      302.88 | 
      330.91 | 
      0.08 | 
      [3.814013271208191, 51.810435850368826] | 
      181.45 | 
      -0.67 | 
      [-226.20160877485196, -42.96163865025414] | 
      0.89 | 
      0.98 | 
      True | 
    

    

      QNI | 
      export | 
      boosting | 
      days_8_14 | 
      112 | 
      56 | 
      327.55 | 
      346.03 | 
      0.05 | 
      [-8.562979296554388, 53.13493417645921] | 
      328.67 | 
      0.00 | 
      [-93.6852168236119, 112.36180050997413] | 
      0.83 | 
      0.97 | 
      True | 
    

    

      QNI | 
      export | 
      boosting | 
      days_15_30 | 
      112 | 
      56 | 
      373.71 | 
      411.95 | 
      0.09 | 
      [21.091514932280674, 53.00972526491151] | 
      275.62 | 
      -0.36 | 
      [-196.52482119927467, -10.741829711173052] | 
      0.82 | 
      0.99 | 
      True | 
    

    

      QNI | 
      export | 
      boosting | 
      days_31_60 | 
      112 | 
      56 | 
      352.24 | 
      388.65 | 
      0.09 | 
      [23.845641429297643, 56.1871895614332] | 
      363.10 | 
      0.03 | 
      [-117.08901178455265, 101.61723418064774] | 
      0.80 | 
      1.00 | 
      True | 
    

    

      QNI | 
      export | 
      boosting | 
      days_61_90 | 
      112 | 
      56 | 
      200.79 | 
      201.20 | 
      0.00 | 
      [-11.914906624559684, 18.095077787003845] | 
      408.13 | 
      0.51 | 
      [125.2888499810732, 300.66803010172674] | 
      0.83 | 
      0.96 | 
      True | 
    

    

      QNI | 
      import | 
      ridge | 
      days_1_7 | 
      560 | 
      56 | 
      249.34 | 
      418.08 | 
      0.40 | 
      [88.01760946379319, 302.43733893965975] | 
      257.89 | 
      0.03 | 
      [-32.22388351724149, 45.363538484075995] | 
      0.60 | 
      0.76 | 
      False | 
    

    

      QNI | 
      import | 
      ridge | 
      days_8_14 | 
      112 | 
      56 | 
      271.27 | 
      423.21 | 
      0.36 | 
      [-35.16944090859148, 305.6804658615181] | 
      443.34 | 
      0.39 | 
      [52.720750902092924, 272.5544261080749] | 
      0.54 | 
      0.62 | 
      False | 
    

    

      QNI | 
      import | 
      ridge | 
      days_15_30 | 
      112 | 
      56 | 
      276.14 | 
      468.36 | 
      0.41 | 
      [99.28744787928929, 312.12871226695165] | 
      387.50 | 
      0.29 | 
      [85.76052846611294, 137.4900794272686] | 
      0.57 | 
      0.66 | 
      False | 
    

    

      QNI | 
      import | 
      ridge | 
      days_31_60 | 
      112 | 
      56 | 
      374.13 | 
      343.68 | 
      -0.09 | 
      [-214.57172479435224, 147.58035525346767] | 
      487.51 | 
      0.23 | 
      [72.16334265872447, 180.77543289760828] | 
      0.41 | 
      0.47 | 
      False | 
    

    

      QNI | 
      import | 
      ridge | 
      days_61_90 | 
      112 | 
      56 | 
      482.40 | 
      155.28 | 
      -2.11 | 
      [-439.95689320900897, -262.65892981697664] | 
      486.22 | 
      0.01 | 
      [-54.542947280148624, 71.88848513553553] | 
      0.12 | 
      0.15 | 
      False | 
    

    

      QNI | 
      flow | 
      ridge | 
      days_1_7 | 
      560 | 
      56 | 
      345.58 | 
      383.50 | 
      0.10 | 
      [-5.099602920352007, 65.27917651306753] | 
      268.18 | 
      -0.29 | 
      [-140.9801048450857, -37.7059827275092] | 
      0.48 | 
      0.80 | 
      False | 
    

    

      QNI | 
      flow | 
      ridge | 
      days_8_14 | 
      112 | 
      56 | 
      404.06 | 
      389.35 | 
      -0.04 | 
      [-28.74487797371395, 0.5690108608306157] | 
      341.12 | 
      -0.18 | 
      [-193.97951256244474, 25.318211311874965] | 
      0.12 | 
      0.26 | 
      False | 
    

    

      QNI | 
      flow | 
      ridge | 
      days_15_30 | 
      112 | 
      56 | 
      428.53 | 
      417.30 | 
      -0.03 | 
      [-39.83705748948624, 19.93251759592059] | 
      342.76 | 
      -0.25 | 
      [-188.199852634119, -49.321168746570386] | 
      0.28 | 
      0.71 | 
      False | 
    

    

      QNI | 
      flow | 
      ridge | 
      days_31_60 | 
      112 | 
      56 | 
      392.72 | 
      377.58 | 
      -0.04 | 
      [-54.383119948602555, 18.14754632786401] | 
      442.88 | 
      0.11 | 
      [-88.19546871972254, 170.84390699920792] | 
      0.36 | 
      0.71 | 
      False | 
    

    

      QNI | 
      flow | 
      ridge | 
      days_61_90 | 
      112 | 
      56 | 
      285.44 | 
      258.43 | 
      -0.10 | 
      [-74.99479979161875, 15.724067090323109] | 
      533.04 | 
      0.46 | 
      [141.63067118371566, 310.419954519741] | 
      0.68 | 
      0.89 | 
      False | 
    

  



## 11 · Sources, provenance and rebuilding

This report synthesises the repository’s frozen research evidence; no external market data was refreshed and no model was retrained. The manifest hashes the inputs, generator, local theme and delivered outputs. The HTML embeds its figures and CSS and works offline; keep the downloads folder alongside it for CSV access.



- [reports\qni_vni_longrange_v1\downloads\cell_results.csv](../../reports/qni_vni_longrange_v1/downloads/cell_results.csv)

- [reports\qni_vni_longrange_v1\downloads\band_metrics.csv](../../reports/qni_vni_longrange_v1/downloads/band_metrics.csv)

- [configs\experiments\qni_vni_longrange_v1.json](../../configs/experiments/qni_vni_longrange_v1.json)

- [docs\RESEARCH_REGISTER.json](../../docs/RESEARCH_REGISTER.json)

- [docs\VNI_DIURNAL_NOS_RESULTS.md](../../docs/VNI_DIURNAL_NOS_RESULTS.md)

- [docs\QNI_DIURNAL_NOS_RESULTS.md](../../docs/QNI_DIURNAL_NOS_RESULTS.md)

- [reports\qni_vni_longrange_v1\manifest.json](../../reports/qni_vni_longrange_v1/manifest.json)

- [execution\qni_vni_longrange_v1\METHODOLOGY.md](../../execution/qni_vni_longrange_v1/METHODOLOGY.md)

[Cell results CSV](downloads/cell_results.csv) · [Band metrics CSV](downloads/band_metrics.csv) · [Markdown edition](report.md) · [Build manifest](manifest.json)

python scripts/build_forward_forecasting_verdict.py


## New cell results

| Connector   | Target       | Selection winner   |   Skill vs calendar (%) |   Skill vs persistence (%) | Decision        |
|:------------|:-------------|:-------------------|------------------------:|---------------------------:|:----------------|
| VNI         | export_tight | calendar           |                 0       |                   25.6585  | retain_baseline |
| VNI         | import_tight | boosting           |                -1.28717 |                   29.3166  | retain_baseline |
| VNI         | export       | boosting           |                -4.19206 |                   29.2637  | retain_baseline |
| VNI         | import       | calendar           |                 0       |                   22.8842  | retain_baseline |
| VNI         | flow         | boosting           |                 3.00924 |                   22.3247  | retain_baseline |
| QNI         | export_tight | boosting           |                17.8455  |                  -42.7127  | retain_baseline |
| QNI         | import_tight | ridge              |                36.885   |                    9.58128 | retain_baseline |
| QNI         | export       | boosting           |                 7.68777 |                  -50.1053  | retain_baseline |
| QNI         | import       | ridge              |                39.2471  |                   12.1909  | retain_baseline |
| QNI         | flow         | ridge              |                 6.47263 |                  -26.2595  | retain_baseline |

## Full band results

| connector   | target       | winner   | band       |   rows |   origins |   model_mae |   baseline_mae |       skill | improvement_mw_ci95                        |   persistence_mae |   skill_vs_persistence | persistence_improvement_mw_ci95            |   coverage_80 |   coverage_95 | calibrated   |
|:------------|:-------------|:---------|:-----------|-------:|----------:|------------:|---------------:|------------:|:-------------------------------------------|------------------:|-----------------------:|:-------------------------------------------|--------------:|--------------:|:-------------|
| VNI         | export_tight | calendar | days_1_7   |    560 |        56 |     304.597 |        304.597 |  0          | [0.0, 0.0]                                 |           416.71  |             0.269044   | [83.24478190451393, 150.3328768887248]     |     0.907143  |      0.994643 | True         |
| VNI         | export_tight | calendar | days_8_14  |    112 |        56 |     231.496 |        231.496 |  0          | [0.0, 0.0]                                 |           296.489 |             0.219207   | [24.400417309135538, 121.91644654952886]   |     0.866071  |      0.946429 | True         |
| VNI         | export_tight | calendar | days_15_30 |    112 |        56 |     265.736 |        265.736 |  0          | [0.0, 0.0]                                 |           357.658 |             0.257009   | [47.855361783752116, 152.00996496374592]   |     0.892857  |      0.964286 | True         |
| VNI         | export_tight | calendar | days_31_60 |    112 |        56 |     343.075 |        343.075 |  0          | [0.0, 0.0]                                 |           431.024 |             0.204048   | [7.994379858695908, 167.4749070727109]     |     0.839286  |      0.928571 | True         |
| VNI         | export_tight | calendar | days_61_90 |    112 |        56 |     396.243 |        396.243 |  0          | [0.0, 0.0]                                 |           538.529 |             0.264213   | [35.75143110703578, 202.67191003171314]    |     0.776786  |      0.919643 | False        |
| VNI         | import_tight | boosting | days_1_7   |    560 |        56 |     210.581 |        208.209 | -0.0113932  | [-9.59936278877806, 5.313931255640374]     |           300.695 |             0.299684   | [52.28553824357325, 125.47318349157402]    |     0.671429  |      0.871429 | False        |
| VNI         | import_tight | boosting | days_8_14  |    112 |        56 |     228.817 |        224.924 | -0.0173072  | [-12.103615109569425, 2.4209798796782303]  |           315.007 |             0.273613   | [32.42730455332619, 124.03928213327325]    |     0.366071  |      0.75     | False        |
| VNI         | import_tight | boosting | days_15_30 |    112 |        56 |     271.49  |        269.737 | -0.00649764 | [-4.738243350552389, 0.3125465954024215]   |           332.664 |             0.183893   | [3.7544157475604387, 108.53179448104122]   |     0.589286  |      0.821429 | False        |
| VNI         | import_tight | boosting | days_31_60 |    112 |        56 |     352.341 |        355.691 |  0.0094183  | [-0.6452389492138106, 8.249626462570731]   |           396.366 |             0.111072   | [3.101680857540155, 94.47219809183996]     |     0.5       |      0.794643 | False        |
| VNI         | import_tight | boosting | days_61_90 |    112 |        56 |     291.401 |        290.079 | -0.00455779 | [-4.594329789415412, 4.629130029683938]    |           367.359 |             0.206768   | [29.273440093294376, 113.1590700262548]    |     0.598214  |      0.839286 | False        |
| VNI         | export       | boosting | days_1_7   |    560 |        56 |     276.276 |        260.44  | -0.0608065  | [-27.820570281915046, -3.9485583261769377] |           393.471 |             0.297849   | [86.58132487919981, 155.84090802700374]    |     0.889286  |      0.9875   | True         |
| VNI         | export       | boosting | days_8_14  |    112 |        56 |     198.991 |        201.967 |  0.014737   | [-4.620943349707873, 10.421280956070795]   |           275.229 |             0.277001   | [34.5277631355394, 121.77547608757759]     |     0.830357  |      0.910714 | False        |
| VNI         | export       | boosting | days_15_30 |    112 |        56 |     243.678 |        251.771 |  0.0321442  | [6.060377986155303, 15.194283957433623]    |           345.455 |             0.294616   | [52.13277002151559, 155.88929488322233]    |     0.910714  |      0.964286 | True         |
| VNI         | export       | boosting | days_31_60 |    112 |        56 |     330.167 |        339.567 |  0.0276804  | [2.2125313563209197, 16.703736775353843]   |           410.236 |             0.195178   | [12.751366027178491, 156.12010261187692]   |     0.866071  |      0.919643 | False        |
| VNI         | export       | boosting | days_61_90 |    112 |        56 |     388.33  |        391.011 |  0.00685783 | [-5.3385199818246525, 7.707428793767654]   |           529.628 |             0.266788   | [52.18170310326238, 189.29374627199866]    |     0.794643  |      0.892857 | False        |
| VNI         | import       | calendar | days_1_7   |    560 |        56 |     208.959 |        208.959 |  0          | [0.0, 0.0]                                 |           269.946 |             0.225926   | [24.48679188505332, 105.54978621044212]    |     0.710714  |      0.883929 | False        |
| VNI         | import       | calendar | days_8_14  |    112 |        56 |     218.126 |        218.126 |  0          | [0.0, 0.0]                                 |           286.102 |             0.237592   | [9.717819642371127, 121.22840134682389]    |     0.517857  |      0.821429 | False        |
| VNI         | import       | calendar | days_15_30 |    112 |        56 |     265.432 |        265.432 |  0          | [0.0, 0.0]                                 |           305.541 |             0.131273   | [-6.654847751953943, 88.25310277547266]    |     0.633929  |      0.803571 | False        |
| VNI         | import       | calendar | days_31_60 |    112 |        56 |     345.072 |        345.072 |  0          | [0.0, 0.0]                                 |           379.614 |             0.0909907  | [-1.8374655440736616, 72.5566967736922]    |     0.517857  |      0.732143 | False        |
| VNI         | import       | calendar | days_61_90 |    112 |        56 |     279.802 |        279.802 |  0          | [0.0, 0.0]                                 |           323.115 |             0.134047   | [5.148070096101162, 79.35987917307035]     |     0.660714  |      0.821429 | False        |
| VNI         | flow         | boosting | days_1_7   |    560 |        56 |     342.43  |        353.998 |  0.0326781  | [2.522473666113373, 18.2584798903382]      |           473.435 |             0.276712   | [86.32601629693828, 206.8694832851274]     |     0.710714  |      0.944643 | False        |
| VNI         | flow         | boosting | days_8_14  |    112 |        56 |     441.289 |        451.371 |  0.0223355  | [-0.6849970927601502, 20.192459736130644]  |           470.886 |             0.0628528  | [-127.67570046876743, 228.02251165798117]  |     0.839286  |      0.982143 | True         |
| VNI         | flow         | boosting | days_15_30 |    112 |        56 |     420.516 |        439.123 |  0.0423739  | [13.539572181664516, 29.53331960386128]    |           547.479 |             0.231905   | [16.160395266323036, 181.5879210808661]    |     0.607143  |      1        | False        |
| VNI         | flow         | boosting | days_31_60 |    112 |        56 |     419.471 |        452.809 |  0.0736251  | [15.077101475503442, 48.00193770458647]    |           524.694 |             0.200541   | [17.846908286091235, 157.55750114403156]   |     0.633929  |      1        | False        |
| VNI         | flow         | boosting | days_61_90 |    112 |        56 |     366.592 |        387.7   |  0.054444   | [14.20248673407057, 37.935012732333924]    |           559.381 |             0.344647   | [59.39831727054715, 252.61750594403887]    |     0.741071  |      1        | False        |
| QNI         | export_tight | boosting | days_1_7   |    560 |        56 |     294.973 |        367.014 |  0.196291   | [48.40593759109056, 99.56475935667115]     |           187.401 |            -0.574017   | [-198.15763418186992, -44.424047538482384] |     0.933929  |      0.978571 | True         |
| QNI         | export_tight | boosting | days_8_14  |    112 |        56 |     323.327 |        369.495 |  0.124947   | [15.029568409334065, 73.14850858669811]    |           327.766 |             0.0135428  | [-78.88189726113067, 104.94714879762358]   |     0.848214  |      0.955357 | True         |
| QNI         | export_tight | boosting | days_15_30 |    112 |        56 |     356.304 |        415.257 |  0.141967   | [38.784419560885986, 78.60256747559347]    |           282     |            -0.263492   | [-165.8604445253199, 1.4164887667560841]   |     0.928571  |      1        | True         |
| QNI         | export_tight | boosting | days_31_60 |    112 |        56 |     324.847 |        389.087 |  0.165106   | [50.1582614408674, 85.81959545112014]      |           374.012 |             0.131455   | [-70.4568239776239, 132.52163443497622]    |     0.857143  |      0.991071 | True         |
| QNI         | export_tight | boosting | days_61_90 |    112 |        56 |     196.001 |        196.772 |  0.00391951 | [-25.257920186973255, 25.782719494457886]  |           410.484 |             0.522512   | [136.2836280666288, 294.64958224548747]    |     0.758929  |      0.9375   | False        |
| QNI         | import_tight | ridge    | days_1_7   |    560 |        56 |     272.689 |        440.371 |  0.380773   | [86.20747606070904, 308.6922352219349]     |           274.737 |             0.00745316 | [-39.29681956948652, 47.29338251898452]    |     0.573214  |      0.735714 | False        |
| QNI         | import_tight | ridge    | days_8_14  |    112 |        56 |     301.612 |        452.245 |  0.333078   | [-52.096541180975656, 315.9502902310517]   |           471.927 |             0.360892   | [47.03437881551488, 281.17538246535184]    |     0.508929  |      0.5625   | False        |
| QNI         | import_tight | ridge    | days_15_30 |    112 |        56 |     313.299 |        498.137 |  0.371058   | [87.25030619298174, 313.58624042329376]    |           419.247 |             0.252709   | [80.4462412607686, 136.21075916417703]     |     0.455357  |      0.616071 | False        |
| QNI         | import_tight | ridge    | days_31_60 |    112 |        56 |     411.66  |        371.357 | -0.108528   | [-231.2817300998525, 145.35075126763758]   |           511.217 |             0.194746   | [60.749763462583815, 168.81481372587592]   |     0.357143  |      0.4375   | False        |
| QNI         | import_tight | ridge    | days_61_90 |    112 |        56 |     498.834 |        174.669 | -1.85587    | [-440.0503013979428, -256.8078648215029]   |           501.415 |             0.00514798 | [-60.00400289106169, 72.4491914513526]     |     0.0892857 |      0.151786 | False        |
| QNI         | export       | boosting | days_1_7   |    560 |        56 |     302.876 |        330.907 |  0.0847084  | [3.814013271208191, 51.810435850368826]    |           181.449 |            -0.669208   | [-226.20160877485196, -42.96163865025414]  |     0.885714  |      0.982143 | True         |
| QNI         | export       | boosting | days_8_14  |    112 |        56 |     327.553 |        346.026 |  0.0533856  | [-8.562979296554388, 53.13493417645921]    |           328.675 |             0.00341215 | [-93.6852168236119, 112.36180050997413]    |     0.830357  |      0.973214 | True         |
| QNI         | export       | boosting | days_15_30 |    112 |        56 |     373.708 |        411.954 |  0.0928394  | [21.091514932280674, 53.00972526491151]    |           275.617 |            -0.355896   | [-196.52482119927467, -10.741829711173052] |     0.821429  |      0.991071 | True         |
| QNI         | export       | boosting | days_31_60 |    112 |        56 |     352.243 |        388.647 |  0.0936689  | [23.845641429297643, 56.1871895614332]     |           363.105 |             0.0299147  | [-117.08901178455265, 101.61723418064774]  |     0.803571  |      1        | True         |
| QNI         | export       | boosting | days_61_90 |    112 |        56 |     200.789 |        201.2   |  0.00204207 | [-11.914906624559684, 18.095077787003845]  |           408.128 |             0.508025   | [125.2888499810732, 300.66803010172674]    |     0.830357  |      0.964286 | True         |
| QNI         | import       | ridge    | days_1_7   |    560 |        56 |     249.335 |        418.081 |  0.40362    | [88.01760946379319, 302.43733893965975]    |           257.89  |             0.0331712  | [-32.22388351724149, 45.363538484075995]   |     0.601786  |      0.7625   | False        |
| QNI         | import       | ridge    | days_8_14  |    112 |        56 |     271.269 |        423.212 |  0.359025   | [-35.16944090859148, 305.6804658615181]    |           443.337 |             0.388121   | [52.720750902092924, 272.5544261080749]    |     0.544643  |      0.616071 | False        |
| QNI         | import       | ridge    | days_15_30 |    112 |        56 |     276.143 |        468.359 |  0.410403   | [99.28744787928929, 312.12871226695165]    |           387.503 |             0.287378   | [85.76052846611294, 137.4900794272686]     |     0.571429  |      0.660714 | False        |
| QNI         | import       | ridge    | days_31_60 |    112 |        56 |     374.13  |        343.677 | -0.0886079  | [-214.57172479435224, 147.58035525346767]  |           487.513 |             0.232575   | [72.16334265872447, 180.77543289760828]    |     0.410714  |      0.473214 | False        |
| QNI         | import       | ridge    | days_61_90 |    112 |        56 |     482.399 |        155.278 | -2.10668    | [-439.95689320900897, -262.65892981697664] |           486.222 |             0.00786228 | [-54.542947280148624, 71.88848513553553]   |     0.116071  |      0.151786 | False        |
| QNI         | flow         | ridge    | days_1_7   |    560 |        56 |     345.579 |        383.504 |  0.0988923  | [-5.099602920352007, 65.27917651306753]    |           268.177 |            -0.288623   | [-140.9801048450857, -37.7059827275092]    |     0.476786  |      0.801786 | False        |
| QNI         | flow         | ridge    | days_8_14  |    112 |        56 |     404.056 |        389.35  | -0.0377716  | [-28.74487797371395, 0.5690108608306157]   |           341.117 |            -0.184509   | [-193.97951256244474, 25.318211311874965]  |     0.125     |      0.258929 | False        |
| QNI         | flow         | ridge    | days_15_30 |    112 |        56 |     428.531 |        417.303 | -0.0269065  | [-39.83705748948624, 19.93251759592059]    |           342.764 |            -0.25022    | [-188.199852634119, -49.321168746570386]   |     0.276786  |      0.714286 | False        |
| QNI         | flow         | ridge    | days_31_60 |    112 |        56 |     392.719 |        377.577 | -0.0401017  | [-54.383119948602555, 18.14754632786401]   |           442.88  |             0.113263   | [-88.19546871972254, 170.84390699920792]   |     0.357143  |      0.714286 | False        |
| QNI         | flow         | ridge    | days_61_90 |    112 |        56 |     285.44  |        258.431 | -0.104511   | [-74.99479979161875, 15.724067090323109]   |           533.041 |             0.464506   | [141.63067118371566, 310.419954519741]     |     0.678571  |      0.892857 | False        |
