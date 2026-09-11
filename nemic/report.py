"""Write the executed research report from computed results, never placeholders."""
import json,platform,importlib.metadata
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from .common import *
from .model import IDS,BANDS

def mdtable(columns,rows):
    return '\n'.join(['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |']+['| '+' | '.join(str(x) for x in row)+' |' for row in rows])

def run():
    s=pd.read_csv(RESULTS/'scores.csv');s=s[s['slice']=='all']
    audit=json.loads((RESULTS/'completion_audit.json').read_text())
    data=json.loads((RESULTS/'data_audit.json').read_text())
    aemo=json.loads((RESULTS/'aemo_audit.json').read_text())
    chosen=s[s.model=='selected']
    ref=s[s.model=='persistence'][['ic','target','band','mae']].rename(columns={'mae':'persistence_mae'})
    comparison=chosen.merge(ref,on=['ic','target','band'])
    wins=int((comparison.mae<comparison.persistence_mae).sum())
    rows=[]
    for k in IDS:
      for t in ['flow','export','import','export_tight','import_tight']:
        g=chosen[(chosen.ic==k)&(chosen.target==t)].sort_values('band')
        rows.append([IC[k]['name'],t]+[f'{v:.1f}' for v in g.mae])
    eventrows=[]
    for k in IDS:
      for t in ['export','import']:
        g=chosen[(chosen.ic==k)&(chosen.target==t)]
        tp,fp,fn=g[['tp','fp','fn']].sum()
        recall=tp/(tp+fn) if tp+fn else np.nan;precision=tp/(tp+fp) if tp+fp else np.nan
        eventrows.append([IC[k]['name'],t,f'{recall:.1%}',f'{precision:.1%}',f'{int(tp+fn):,}',f'{int(fp):,}'])
    source_records=[json.loads(p.read_text()) for p in (DATA/'manifest_records').glob('*.json')]
    dump(DATA/'manifest.json',source_records)
    versions={p:importlib.metadata.version(p) for p in ['pandas','numpy','pyarrow','lightgbm','scikit-learn','dash','plotly']}
    dump(RESULTS/'environment.json',dict(python=platform.python_version(),platform=platform.platform(),packages=versions))
    mean_coverage=float(np.average(chosen.coverage80,weights=chosen.n))
    text=f'''# INTERFLOW — NEM interconnector conditional backtest

Executed {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}. Local dashboard: http://127.0.0.1:8050

## What was completed

- September 2023 through August 2026: 36 complete months, all six historical NEM interconnectors.
- {data['half_hour_count']:,} connector/half-hour observations and {sum(v['five_min_rows'] for v in data['interconnectors'].values()):,} retained five-minute observations. No missing flow or limit targets.
- Five targets: signed dispatch flow, average export/import directional limits and tightest five-minute export/import limits within each half-hour.
- {audit['total_origin_lead_pairs']:,} test origin/lead pairs; {audit['target_forecasts']:,} target forecasts. Every available half-hour origin and all leads 30 minutes through seven days are covered. Origins near the dataset end have appropriately truncated horizons.
- P10/P50/P90, calibrated restriction probabilities, per-link/per-horizon model comparisons, seven-day block uncertainty estimates, original-vintage AEMO comparison, and a runnable seven-day scenario example.

## Results

The selected and calibrated forecasts beat persistence on MAE in **{wins} of {len(comparison)} connector/target/lead-band cells**. This count weights every cell equally; it is not a portfolio performance measure. Some cells can lose even though the underlying method was selected on validation. The detailed score table retains all losses.

The sample-weighted empirical coverage of the nominal 80% intervals is **{mean_coverage:.1%}**. Check individual target/horizon coverage in the dashboard: aggregate coverage can hide undercoverage. Uncertainty intervals are marginal; they do not guarantee simultaneous coverage across all 336 horizons or all connectors.

### Test MAE, MW

{mdtable(['Interconnector','Target',*BANDS],rows)}

### Restriction detection

A flag means the directional limit is below **50% of its training-only seasonal median of positive directional limits**. Forced-flow and zero outcomes remain in the target and can be flagged. Alert probability thresholds were tuned on February validation data to maximise F2, giving recall greater weight than precision. These are reported-limit restrictions, not classifications of line outages or maximum secure physical capability.

{mdtable(['Interconnector','Direction','Recall','Precision','Event pairs','False alerts'],eventrows)}

Counts are forecast-origin/lead pairs, not unique physical events. Repeated forecasts of the same restriction are intentionally retained in rolling-origin evaluation. Per-band metrics, stressed intervals, seasonal slices, Brier scores and five-minute observations are available in the dashboard and CSVs.

## AEMO benchmark

Matched **{aemo['matched_pairs']:,}** original AEMO predispatch origin/delivery pairs. Available matched leads span {aemo['min_lead_hours']:g}–{aemo['max_lead_hours']:g} hours. Original file creation times plus a one-minute ingestion buffer determine the first eligible half-hour origin; no forecast issued after that origin is used. Monthly predispatch snapshots were not treated as complete forecast-vintage archives.

This comparison is deliberately asymmetric: AEMO used forecast inputs, while our experiment is supplied with realised future demand, renewables and weather. It measures conditional explanatory skill, **not operational superiority over AEMO**. Standard predispatch does not provide a comparable seven-day series throughout this sample, and has no target equivalent to the tightest five-minute limit within a half-hour.

## Design and leakage controls

See the [improvement roadmap](docs/IMPROVEMENT_ROADMAP.md) for prioritised additional data and untested modelling proposals, with evaluation requirements.

For the full research rationale, model specifications and data definitions, see [Methods and research](docs/METHODS_AND_RESEARCH.md). For exact split boundaries, metrics, benchmark alignment and reproduction steps, see [Backtest protocol](docs/BACKTEST_PROTOCOL.md).

1. **Train:** September 2023–August 2025. Fit models, scales, categorical encodings and seasonal references exclusively here.
2. **Select:** September–November 2025. Choose a method separately for each connector, target and lead band on MAE.
3. **Calibrate:** December 2025–January 2026. Estimate the selected method's residual distribution; P10/P50/P90 are its empirical quantiles added to the base prediction.
4. **Alert tuning:** February 2026. Choose probability cutoffs using F2. A cell without validation events retains an explicitly labelled default cutoff.
5. **Test:** March–August 2026. Frozen models, references, calibration and thresholds. No training target crosses its boundary. Validation subperiods also exclude crossing origin/target windows.

The static boosted ablations use one observation per delivery state. The direct network model uses a reproducible random lead from each of four bands at every eligible training origin: roughly 832,000 pooled origin/lead examples per target. In contrast, the final test is exhaustive across all 336 half-hour leads. Boosting uses 180 trees, 23 leaves, absolute-error loss, regularisation and a fixed seed. Baselines include persistence and the same slot one week earlier; at the exact seven-day endpoint, the seasonal baseline uses an earlier observable week rather than the unavailable issue interval.

Future allowed inputs: regional demand, cleared semi-scheduled wind and solar, rooftop PV, and weather reanalysis. A separate availability ablation substitutes UIGF availability for cleared renewables. Origin features include lagged limits/flows, limit setters, local constraint/outage flags, generator availability and other connector flows. A 30-minute observation delay applies; late-published dispatch observations are additionally censored. The timestamp audit found and handled one late half-hour across six links in September 2024.

**Excluded future inputs:** prices, actual future interconnector flows, future realised constraint setters and future thermal availability. Prices are used only for descriptive regional spread analysis.

## Data and interpretation

- Market timestamps are fixed UTC+10 NEM time, without daylight saving. Half-hours are interval-ending; each target uses exactly six five-minute observations.
- Physical intervention runs are preferred when present. Price context uses the pricing run. Raw alternatives are retained in source archives.
- Import direction is minus AEMO's signed IMPORTLIMIT; negative directional values are preserved. Taking absolute values would misrepresent forced-flow states.
- TOTALDEMAND is already affected by behind-the-meter generation. Rooftop is not subtracted a second time. Semi-scheduled wind/solar are clearly distinguished from nonscheduled generation.
- Weather: hourly Open-Meteo ERA5 at 15 demand, corridor and renewable-area locations. Temperature, wind, cloud and humidity are interpolated to half-hours; hourly mean radiation is assigned to the two contained half-hours to preserve energy. This is a sparse regional proxy, not a full transmission line thermal model.
- {sum(int(round(v*52608)) for k,v in data['driver_missing_fraction'].items() if k.endswith('__rooftop'))} regional rooftop feature cells remain missing across the complete sample; the trees handle these as missing. Other model drivers are complete. No missing targets were filled synthetically.
- Archived actuals may contain retrospective revisions. Realised renewable dispatch is endogenous to congestion. These limitations prevent interpreting the experiment as a genuinely issue-time operational backtest.
- Future planned-outage schedules are not reconstructed. The network model uses delayed observed constraint regimes and generator availability. Unexpected topology changes can therefore cause large errors.
- EnergyConnect is not fabricated as a seventh three-year series. Existing-link changes are part of the recorded history; standalone new-link forecasts require a commissioning/scenario treatment and subsequent data.
- The final six-month test covers autumn/winter and an endpoint, not a complete seasonal year. Validation has additional seasons, but is not an independent full-year test. Seven-day block bootstrap intervals are approximate under overlapping forecasts and regime shifts.
- Regional price-spread charts establish associations, not the causal price effect of a changed transfer limit. No bidding strategy or trading P&L is claimed.

## Use the dashboard and scenario runner

Run `python app.py` in this folder, then open http://127.0.0.1:8050. Select a connector, historical origin, target and horizon. Forecast shows realised outcomes, P10/P50/P90, persistence, restriction probabilities and five-minute detail. Backtest provides baselines, coverage, recall/precision and matched AEMO results. Drivers isolates feature contributions; Price context shows historical spreads. Scenarios accepts 336 half-hour input rows and exports results for all connectors.

The supplied `results/scenario_template.csv` is a historical example, not a live weather forecast. Use `python -m nemic.scenario --origin "2026-08-24 00:00" --input your_inputs.csv --output scenario_results.csv` for a custom path. For an origin at the final observed timestamp, supply a complete future input path; the code does not invent missing network history for later issue dates.

Run `python run_pipeline.py` to execute the full pipeline. Downloads and fitted models are cached. Test prediction signatures check selected dependencies; they are not complete automatic cache invalidation. Follow the cache guidance in the backtest protocol when changing data, features or settings. Local data and model caches are excluded from Git by default. Package versions are recorded in `results/environment.json`.

## Evidence and files

- `data/manifest.json`: {len(source_records)} source archives, {sum(r['bytes'] for r in source_records)/1e9:.2f} GB compressed, with URLs and SHA-256 checksums.
- `data/weather_manifest.json`: coordinates, variables, native resolution, request parameters and checksums.
- `results/data_audit.json`, `split.json`, `training_proof.json`, `test_proof.json`, `completion_audit.json`: coverage, timing and completeness evidence.
- `results/scores.csv`, `validation_leaderboard.csv`, `skill_confidence.csv`, `aemo_scores.csv`: reusable score tables.
- `results/predictions/`: exhaustive per-origin predictions; `models/selection.json`: frozen selected methods, residual quantiles and alert cutoffs.
- `results/scenario_example.csv`: executed scenario forecasts for every connector and all 336 leads.

## Research and UI references

- [AEMO: reported interconnector limits, Appendix A](https://aemo.com.au/-/media/files/electricity/nem/market_notices_and_events/power_system_incident_reports/2024/final-report---loss-of-moorabool---sydenham-500-kv-lines-on-13-feb-2024.pdf): post-dispatch reported limits are not maximum secure capability.
- [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq): constraint equations and binding conditions.
- [Abdel-Khalek et al., capacity forecasting](https://d-nb.info/1204086990/34): public-data forecasting and the importance of persistence benchmarks; European results are not proof of NEM skill.
- [Congestion probability using boosted trees](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1351306/full): supports testing nonlinear congestion models; this project is not a reproduction of its physical optimisation model.
- [Forecasting: Principles and Practice, rolling origins](https://otexts.com/fpp3/tscv.html): chronological multi-step evaluation.
- [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api): reanalysis data and native temporal definitions.
- [TradingView layouts](https://www.tradingview.com/support/solutions/43000746975-tradingview-layouts-a-quick-guide/) and [Bloomberg Launchpad](https://professional.bloomberg.com/products/bloomberg-terminal/): chart-first layout and compact linked monitors, adapted to the local dark dashboard skill without copied branding.
'''
    (ROOT/'BACKTEST_REPORT.md').write_text(text,encoding='utf-8')
    dump(RESULTS/'summary.json',dict(wins_vs_persistence=wins,cells=len(comparison),weighted_coverage80=mean_coverage,matched_aemo_pairs=aemo['matched_pairs'],test_pairs=audit['total_origin_lead_pairs']))
    print('REPORT COMPLETE',wins,'/',len(comparison),'cells beat persistence; coverage',mean_coverage)

if __name__=='__main__':run()
