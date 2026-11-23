# EnergyConnect directional-limit results

This study covers NSW1-SA1 from 1 October through 22 November 2026 in fixed NEM time (UTC+10). All 15,264 five-minute observations formed 2,544 complete interval-ending half-hours. The two directional minima occurred at different five-minute timestamps in 1,550 half-hours. Limits describe AEMO's observed dispatch solutions under the recorded commissioning and network conditions.

Matching the reported setter to its exact equation version and interconnector factor reproduced the published limit within 1 MW in 12,664 NSW-to-SA intervals (83.0%) and 14,673 SA-to-NSW intervals (96.1%). Choosing the tightest equation independently produced much larger errors. The remaining rows retain their reported setter and dispatch version key in the local evidence.

The issue-time replay scheduled 48,336 origin and delivery pairs. Published PredispatchIS and ST PASA vintages support separate comparisons. Verified ST PASA delivery leads reached 164 hours. Older predispatch archives support a separately labelled timing proxy.

On 3,728 common day 4 to 7 pairs, adding forecast constraint inputs reduced NSW-to-SA tight-limit MAE from 215.24 to 205.45 MW. The corresponding SA-to-NSW MAE fell from 218.00 to 209.10 MW, and issued ST PASA scored 148.10 MW. The constraint challenger missed 1,264 NSW-to-SA restrictions and 1,186 SA-to-NSW restrictions. SA-to-NSW forecast intervals covered 48.6% of the 1,152 calibrated pairs. These scores cover one commissioning period.

The scenario tool compares observed configurations and delivery periods using regional MW assumptions, a CSV path or a historical day. Of 271 configuration and period cohorts, 61 have observations on more than one day. The remaining 210 are labelled single-day examples.

- [Dispatch coverage](evidence/coverage.csv)
- [Constraint reconstruction](evidence/reconstruction_summary.csv)
- [Overall forecast scores](evidence/forecast_scores_overall.csv)
- [Frozen restriction thresholds](evidence/restriction_thresholds.csv)
- [Aggregate evidence hashes](evidence/manifest.json)

Run the [execution guide](README.md) to rebuild the offline report, scenario tool and interval evidence from retained or newly collected sources.
