# Switch position, outage schedules and dispatch state

- The evaluation covered 641 binary signals at twelve delivery times on 19, 20 and 22 February 2026.
- Short-lead state persistence was 95.7% accurate overall and 63.7% accurate on the 59 signals that varied.
- The issued outage schedule recovered 97.8% of linked-set activations at both leads.

An outage schedule can identify the sets expected to apply while leaving individual switches and timers unresolved. At the previous-afternoon horizon the schedule identified 182 active set-intervals, produced 18 false positives and missed four. Carrying the prior case produced 72 false positives and missed 22. The comparison covers the sets linked to the available outage information at origin.

Among signals that varied, previous-afternoon persistence accuracy fell to 51.7%. At George Town, the previous-afternoon published limit selected 594 MW throughout the sample while dispatch used 350 MW. The full discrepancy came from the branch choice.

For Basslink, zero preceding transfer occurred alongside full directional offers in seven training observations. An idle link therefore gives insufficient information about its availability. Carry separate offer and direction scenarios. For voltage and reactive load, benchmark each measurement against its own clock profile and prior public reading before introducing regional demand.

### What to inject

| Input and estimator | About 59 min | Previous afternoon | Recommendation |
|---|---:|---:|---|
| Tasmania BU_SH1_LINE_220KV, prior case / clock / nearest demand (kV) | 0.64 / 0.85 / 0.90 | 0.71 / 0.85 / 0.96 | Carry the same bus's latest available same-clock value. Test tap settings, reactive resources and local topology if issued. |
| Victoria APDLOAD_MVAR, prior case / clock / nearest demand (MVAr) | 3.33 / 2.67 / 2.47 | 4.93 / 2.67 / 2.93 | Start with clock and preserve sign. Regional demand helped the short lead by 0.20 MVAr and lost 0.26 at the long lead. Test local MW and power factor by operating mode if available. |
| BL_PREVDI_TARGET, latest dispatch target / issued flow / clock (MW) | 34.58 / 35.89 / 122.74 | 46.07 / 58.45 / 122.74 | Anchor to the freshest published target. Propagate each simulated dispatch target into the next five-minute step. |
| Basslink TAS1 offer M, prior case / clock (MW) | 119.5 / 119.5 | 239.0 / 119.5 | Use entitled directional offers if available and bracket the missing offer with full, derated and zero cases. |
| Basslink VIC1 offer N, prior case / clock (MW) | 148.5 / 148.5 | 297.0 / 148.5 | Keep an independent directional offer. A dispatch limit or forecast flow can differ from the offer. |
| Basslink winning switch status, prior case / clock / issued-flow class (errors out of 12) | 3 / 3 / 2 | 6 / 3 / 3 | Evaluate both switch runs and use a range where they disagree materially. |
| Mortlake inertia, prior case / clock / plant-output proxy (source units) | 0 / 0 / 0 | 0 / 0 / 0 | Supply individual future synchronous states and compatible inertia coefficients. Held-out labels were all zero. |
| T^V_NIL_9, last dispatch RHS / issued equation RHS (MW) | 0 / 0 | 0 / 244 | Verify the timer branch and process-specific equation before injecting an inferred state. |

### Predicting activation from the issued outage schedule

| Lead and method | Set-intervals | True / false positives | Missed activations | Precision / recall |
|---|---:|---:|---:|---:|
| About 59 minutes, NOS | 2,476 | 182 / 6 | 4 | 96.8% / 97.8% |
| About 59 minutes, prior case | 2,476 | 168 / 62 | 18 | 73.0% / 90.3% |
| Previous afternoon, NOS | 2,472 | 182 / 18 | 4 | 91.0% / 97.8% |
| Previous afternoon, prior case | 2,472 | 164 / 72 | 22 | 69.5% / 88.2% |

## Sources and evidence

- [February 2026 research record, method and supporting tables](../../local_exports/rhs_approximation_study/states/report.md)
- [AEMO NEMDE Queue Users' Guide, p. 20](https://www.aemo.com.au/-/media/files/electricity/nem/it-systems-and-change/nemde-queue/nemde_queue_users_guide.pdf?la=en)
- [AEMO MNSP bid data](https://visualisations.aemo.com.au/aemo/nemweb/mmsdatamodelreport/electricity/mms%20data%20model%20report_files/MMS_24.htm)
- [AEMO Network Outage Schedule](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/network-outage-schedule)
