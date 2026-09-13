# QNI and VNI expanded research log

Research access: 13 September 2026. This log accompanies the [expanded report](QNI_VNI_EXPANDED_FORECAST_RESEARCH.md). The full source inventory is at the end of that report. This is an expanded integrative review, not a systematic census of every database or paper.

## Questions and method

The review asks how the retained constraint studies can improve operational flow, limit, contraction and direction forecasts; what compact features preserve mechanisms; which simple and boosted models merit testing; and what information, calibration and validation are necessary. Searches expanded from direct interconnector forecasting into congestion/active-set learning, generator movement, price extremes, weather ramps, low-dimensional flows, model comparisons and temporal evaluation. Reference and documentation links were followed where relevant. Queries returning largely irrelevant results were not counted as positive evidence.

The first edition's primary market definitions and core forecasting references were retained and supplemented with newly opened operator, academic and AEMO documents. Not every inherited source was independently reopened in this second pass. The expanded numerical experiment reused local data and trained the models recorded in its evidence file; the full original production backtest was not rerun.

## Search batches

### Batch 1

- interconnector flow forecasting Australia NEM QNI VNI statistical forecasting congestion machine learning
- cross border electricity flow forecasting econometric ARX gradient boosting interconnector
- transmission congestion forecasting active constraints classification optimal power flow machine learning
- electricity forecasting generalized additive quantile regression boosting benchmark linear

### Batch 2

- "interconnector" "forecasting" "regression" electricity
- "cross-border" "power flow" forecasting weather
- "congestion forecasting" "electricity" machine learning
- "NEM" "interconnector" "forecast" model AEMO

### Batch 3

- "forecasting" "interconnector flows" linear Statnett
- "Predicting cross-border power flow using weather data" Kledzik Haker
- "constraint" "forecasting" "Tumut" AEMO
- site.aemo.com.au "Predispatch" "Accuracy" "constraints"

### Batch 4

- "Forecasting the occurrence of extreme electricity prices" logistic authors
- "lightgbm" "forecast" "interconnector" Statnett
- "probabilistic" "congestion" "active set" optimal power flow Deka
- "forecasting" "ramp events" "wind" probabilistic review

### Batch 5

- "forecasting" "regime switching" "electricity" Weron Janczura
- "forecast combinations" "simple average" forecasting review Wang Hyndman
- "evaluating time series forecasting models" rolling origin Cerqueira Torgo Mozetic
- "machine learning" "congestion" "active constraints" Deka Misra

### Batch 6

- "Deka" "Misra" "active" "constraints" learning
- "Learning for DC-OPF" "active"
- "Janczura" "Weron" "regime" "2010"
- "Liu" "Bai" "Forecasting the occurrence of extreme electricity prices"

### Batch 7

- "Forecast combinations" Wang Hyndman Li Kang arxiv
- "Explainable Boosting Machine" Nori 2019 interpretML
- "Regularization and variable selection via the elastic net" Zou Hastie pdf
- "Multivariate adaptive regression splines" Friedman 1991

### Batch 8

- "AEMO" "seven day" "predispatch" "PD7DAY"
- "AEMO" "PREDISPATCH" "forecast errors" "constraint"
- "forecasting" "generator dispatch" "NEM" machine learning
- "SHAP" "causal" "feature relevance quantification"

### Batch 9

- site.aemo.com.au "131322" "0.15"
- site.aemo.com.au "PD7DAY" forecast
- "Forecasting the occurrence of extreme electricity prices" Liu Bai full text

## Screening and access decisions

| Material | Access / decision | Effect on conclusions |
|---|---|---|
| Statnett mFRR flow uncertainty account | Primary operator article read | Direct industry precedent; HVDC ATC not imported as NEM hard bounds |
| AEMO current formulation guideline and consultation | Primary final document and effective-date text read | December 2025 measurement/regime break included |
| AEMO version 19 predispatch procedure | Primary current procedure read | Supersedes a 2023 draft encountered during search |
| AEMO PD7DAY documentation and market notice | Primary indexed fields and notice text available; some direct pages returned retrieval errors | Longer-horizon opportunity retained; historical vintage coverage unproven |
| Liu et al. NEM logistic extreme-price paper | Primary accepted-manuscript abstract indexed; direct full-text retrieval failed | Supports candidate choice, not verified operational performance or availability |
| Gaillard et al. additive forecasting | Publisher abstract/introductory excerpts available; complete fetch unavailable | No detailed reproduction or universal ranking claim |
| KTH weather/cross-border thesis | Record encountered; bot challenge and PDF retrieval failure | Excluded from core performance evidence |
| Ng et al. and Deka/Misra OPF learning | Primary papers examined | Mechanistic regime rationale; synthetic optimisation not live forecasting |
| Schäfer et al. flow PCA | Primary paper examined | Descriptive compression hypothesis only |
| Gaugl et al. interconnector surrogate | Primary 2026 preprint examined | Planning/simulation evidence; not treated as operational forecast skill |
| Worsnop et al. wind ramp scenarios | Primary paper examined | Temporal dependence lesson, including mixed method results |
| Elastic net, EBM, forecast combinations | Author paper, official docs and review examined | Model portfolio broadened without assuming superiority |
| Temporal evaluation papers | Primary papers examined | Chronological replay and contamination controls |
| Janzing et al.; CQR | Primary proceedings/arXiv summaries read in this pass | Limited conceptual use; no local causal or coverage guarantee |
| AER/FTI/Modo and additional ramp/regime sources | Search candidates surfaced but not fully appraised | Not used as decisive evidence or padded into the core bibliography |
| Generic web mirrors and secondary abstracts | Discovery aids only where primary sources could be identified | Core technical claims use primary records |

## Empirical work and reproducibility

The expanded experiment produced 144 regression rows and 20 event rows from 100 hashed existing files. It also audited 48 monthly feature partitions and 183 selected event cases. No new MMSDM archive or weather dataset was acquired. The evidence file records configurations, library versions, runtime, limitations and input hashes. Regression bootstrap intervals are exploratory; event probabilities have no incident-level confidence interval in this run.

The first experiment's 90 simple-model score rows remain available separately. The feature blocks and validation dates differ between experiments, so they must not be concatenated as one controlled architecture trial. No retained source files were deleted merely to reduce the apparent data size.

## Open issues and boundaries

Unresolved: QNI reconstruction discrepancies, strict public availability of each unit/FCAS input, historical outage and individual weather forecast vintages, historical PD7DAY coverage, prospective incident-warning skill and causal dispatch replay. There is no unseen seven-day, eight-season operational validation in this research. The next implementation is specified in the report rather than claimed complete.

The HTML editions are built from Markdown without remote rendering dependencies. Static link, anchor and source checks are required. Browser visual preview was unavailable because the earlier local report URL was blocked by browser policy; no alternate serving or browser workaround is used.
