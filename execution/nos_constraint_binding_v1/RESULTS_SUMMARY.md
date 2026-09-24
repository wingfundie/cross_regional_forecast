# Results summary — NOS constraint mechanics and outlook (v1)

**Status:** complete (2026-09-24). All stages of [`PLAN.md`](PLAN.md) have run; the execution log is authoritative. Report: `reports/nos_outage_regime_research_20260924/index.html` (chapters `#constraints` and `#outlook`), with a summary in `reports/all_interconnector_regime_research_20260921/index.html#outages`. Rebuild commands are at the end.

All historical results are retrospective and conditional on realised invocations. The outlook is a research outlook, not an operational forecast. AEMO limits are dispatch outputs, not physical capability.

## Gates

| Gate | Result |
|---|---|
| Matched-pair replay equals v1 (A1) | Identical on all six links: 405,120 outage half-hours, 0 unit or key-effect mismatches |
| Limit-setter counts equal v1 leading intervals (A2) | 2,159 family-connector checks, 0 mismatches |
| Dispatch archives hash-checked (B1) | 48 of 48 DISPATCHCONSTRAINT and DISPATCHLOAD archives match the constraint-study ledger (6.96 GB streamed, all deleted) |
| Binding reconciles with the regime report (B2) | Exact: 144 connector-months, 1,284,417 binding equation-intervals, 0 per-constraint mismatches |
| Placebo (±7 days) | Own-set difference clean for 97% of 750 family-directions (setter and binding) |
| Backtest leakage (Q28) | Embargoed and cut-data re-run estimates agree for 98.8% of 334 supported family-directions at two origins |

## What sets the limit and what binds during outages

Supported family-directions (median shares of five-minute intervals while the outage family is invoked; matched normal is about 0% throughout):

| Link | Supported | Own set sets the limit | Own set dominant (≥ 50%) | Own set binds | Largest own-set binding share | Any-binding change |
|---|---|---|---|---|---|---|
| QNI | 37 | 2.9% | 5% | 1.3% | 82% | +4.1 pp |
| Directlink | 27 | 0.4% | 0% | 1.1% | 30% | +1.4 pp |
| VNI | 41 | 20.2% | 15% | 4.1% | 46% | +0.2 pp |
| Heywood | 50 | 3.8% | 18% | 0.8% | 49% | 0.0 pp |
| Murraylink | 67 | 4.0% | 10% | 2.2% | 42% | −1.9 pp |
| Basslink | 18 | 5.8% | 11% | 0.0% | 8% | +0.1 pp |

- **Most outages tighten rather than replace.** In most supported family-directions the outage's own equations rarely set the limit or bind. The system-normal equation stays in charge and is tightened.
- **A minority take over.** QNI forward during the Armidale–Dumaresq (N-ARDM_8C, 82% binding, 95% CI 77–86%), Armidale–Sapphire (N-ARSR_8E, 81%) and Dumaresq–Sapphire (N-DMSR_8J, 61%) outages. Also VNI forward during N-DTKV_18_WG_CLOSE (46%), Heywood during V-CRML (43–45%) and Murraylink forward during N-BABU (42%).
- **The two layers mostly disagree.** Averaged over supported families while invoked, the own set both binds and sets the limit 5% of the time, sets the limit without binding 10%, binds without setting it 1%, and does neither 84%.
- **Displacement.** During the take-over families the usual system-normal leaders lose share. Example: `N>>NIL_33_34` falls from 44% to 16% of QNI forward intervals during N-ARSR_8E.
- **Timing.** Own-set shares switch on within the first half-hour of invocation and off within an hour of its end (event study, clean spells).
- **Known in advance vs late.** Year 2 only. Outages already in the NOS snapshot a week before bind their own set in 12.1% of intervals, against 4.7% for outages booked later.
- **Marginal values.** Median |MV| of own-set binding is $35.7/MWh while invoked against $17.8/MWh in matched periods. 5.1% of binding intervals exceed the equation's outage-free P90, against 3.8%. Descriptive only.
- **Footprint.** On other links (spillover), the median change in any-binding share is about 0 pp.
- **Generator-only equations.** None. After back-filling pre-window definitions, every resolvable member equation of a relevant outage set contains a term for one of the six links, so generator pressure is already covered by the connector-leader pressure (`nos_duid_pressure.csv`).
- **Correction.** The v1 "leader changed" share was misaligned. Aligned per run, the limit-setter changes at invocation start in 33% of runs on average across families.

## Outlook and backtest

- **Backtest scale.** 12 monthly year-2 origins; 30,838 prediction rows; 126,582 scored rows.
- **Skill.** The outlook beats the equation's normal season × half-hour rate on Brier score in 23 of 96 layer × lead-band × link-direction cells:
  - QNI reverse binding at 8–365 days (skill +25% to +45%)
  - parts of Directlink reverse binding
  - Basslink limit-setting

  Elsewhere it over-predicts. In the highest well-populated binding bin, predicted shares averaging 36% were followed by 15% realised. The binding outlook beats last year's family rate in most lead bands.
- **Limit change.** MAE 119–140 MW, against 125–152 MW for a no-change forecast.
- **Family inference.** For bookings without a linked set, the first-ranked family was later linked for 8% of 2,781 bookings, mostly because such bookings rarely invoke any set. Among the 1,175 bookings that did, it was right 19% of the time (top three 22%).
- **Live outlook.** Built from NOS snapshot `PUBLIC_NETWORK_20260911000007` (generated 2026-09-11 00:00:07; newest archived weekly file `PUBLIC_NETWORK_20260904`):
  - 2,855 bookings within 12 months and 3,712 booking × family × link-direction rows
  - 1,642 of those rows fall in skilful cells; the rest show the matched normal rate
  - change flags: 527 name a new equation and 54 an equation re-versioned in the last 30 days
  - 1,337 overlapping rows carry a joint historical estimate

## Limitations

- **Records and matching:** year-1 outage records are final-state only, and weather and VRE bins use full-history percentiles.
- **Outlook:** it assumes past behaviour carries forward and relies on asset history for unlinked bookings.
- **Unresolved definitions:** four set equations versioned in 2013 remain undefined.
- **Near-binding:** back-filled equations have near-binding rows only where they also bound.

## Rebuild

```
python scripts/run_nos_binding.py --stage A1|A2|B0|B1|B2|B0b|B3|B7
python scripts/run_nos_binding.py --stage D2 --months 0 4 8   # one backtest worker (four in parallel), then combine
python -c "from nemic.experiments.nos_regime.outlook import combine_backtest; combine_backtest()"
python scripts/run_nos_binding.py --stage D2c                 # embargo confirmation
python scripts/run_nos_binding.py --stage D3                  # live outlook from the newest weekly NOS file
python scripts/build_nos_regime_section.py && python scripts/build_nos_outage_report.py   # reports, cached tables only
```
