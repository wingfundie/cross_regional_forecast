### Digital state, equipment outages and special electrical inputs

Carrying the previous day's binary state forward was correct on 95.7% of all point-intervals at the short lead. For the 59 points that actually varied across the three target mornings, accuracy fell to 63.7%. A good aggregate score can conceal material operating-state errors. An explicit pair of state scenarios makes their effect on the equation visible.

The test uses dispatch intervals ending 10:30, 11:00, 11:30 and 12:00 fixed NEM time on 19, 20 and 22 February 2026. Each label is one five-minute interval. Training uses the same four clock times on 9–15 February. Each target has a P5MIN vintage 58.2–59.3 minutes before delivery and a previous-afternoon PREDISPATCHIS vintage 18.46–19.96 hours before delivery. The long-lead predictions for each date use one fixed vintage. There are 12 short-lead origins and three long-lead origins. Results describe three correlated mornings.

Case SCADA labels require Can_Use_Value=True. The 4 February S-type inventory supplies 641 points with usable 0/1 observations. The short-lead prior-case baseline uses yesterday's morning. At the previous-afternoon cutoff that morning's case awaited the end of its trading day, so the long-lead baseline uses two mornings before delivery. Clock references use seven earlier observations per clock time. Case eligibility follows AEMO's documented 04:00 publication cycle. The forecast-product cutoff is the later of source creation and archive member modification. Both timestamps on the latest dispatch and SCADA reports used precede the cutoff. For NOS the last report generated at least two minutes earlier is eligible. Historical recipient timestamps are unavailable. [AEMO NEMDE Queue Users' Guide, p. 20](https://www.aemo.com.au/-/media/files/electricity/nem/it-systems-and-change/nemde-queue/nemde_queue_users_guide.pdf?la=en)

### What to inject

Entries are MAE against 12 dispatch case values per lead, except the switch row which counts classification errors. The demand estimator averages the target point over the three training observations closest to the issued regional MW forecast.

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

The case's previous Basslink target agreed with the preceding public DISPATCHINTERCONNECTORRES.MWFLOW within 0.000004 MW on 12/12 examples. The P5 comparison uses the issued flow for the preceding five-minute interval. The predispatch comparator supplies a coarser half-hour flow ending at the delivery time. All previous-target labels in this test were between −239.17 and 0 MW.

Basslink's TAS1/VIC1 offer maxima were 478/594 MW in all 28 training observations. They both fell to zero at the three 11:00–12:00 snapshots on 20 February and returned to 478/594 on 22 February. Training min/max covered 9/12 held-out offer values in each direction. Seven training snapshots showed zero preceding dispatch target alongside full offers. For the winning switch, the issued-flow proxy takes the training mode for the zero or nonzero preceding transfer class, with a 0.1 MW zero tolerance. Its label is PeriodSolution.SwitchRunBestStatus. Applying W also requires the switched point's value under the selected branch. AEMO publishes the 5-minute MNSP bid data for other participants next day. [AEMO MNSP bid data](https://visualisations.aemo.com.au/aemo/nemweb/mmsdatamodelreport/electricity/mms%20data%20model%20report_files/MMS_24.htm)

Mortlake's two DUIDs MORTLK11 and MORTLK12 were classified separately using 5 MW. Both were off in 24 training cases with zero inertia. In four training cases unit 11 exceeded 100 MW and case inertia was 21.079 source units. The origin-state proxy takes the training median for the same pair of plant states. Future plant starts, shutdowns and synchronous-condenser operation need separate validation. The 28-point training envelope covered all 12 voltage and reactive-load observations with widths of 6.30 kV and 35.20 MVAr. These descriptive ranges have no calibrated probability.

### Status changes and timer branches

Prior-case persistence missed 330/7,692 binary point-intervals at the short lead and 442/7,692 at the long lead. Clock mode missed 411 at either lead. Among the 59 points varying in the held-out mornings, persistence missed 257/708 and 342/708. Clock mode missed 252/708 at both leads. Of 330 short-lead point-intervals where the flag differed from the prior case, clock mode recovered 179. It recovered 208 of 442 at long lead. The other 582 points were constant across these delivery snapshots. Validate each material flag under actual changes before assigning it a probability.

Across all 52 sampled cases the T^V_NIL_9 dispatch RHS equalled 594 − 244 × GTOWN_FL_TIMER. The two branches differ by 244 MW. Previous-afternoon published RHS was 594 in all 12 held-out intervals while dispatch and P5 were 350 in every one. Use the latest dispatch RHS to infer a timer only under a verified version-specific mapping. The predispatch RHS difference alone cannot identify its physical timer state.

### Predicting activation from the issued outage schedule

At each cutoff we score every set linked to any outage in that NOS snapshot. The predictor intersects the equipment and set windows, omits closed and superseded bookings and uses actual start/end times only when already reached and recorded. The target is a set tracked on an invoked equation in the non-intervention dispatch case. A set can be invoked for several reasons. The results measure set-level activation within the origin's linked universe. They do not measure causal outage attribution or unlinked set coverage. [AEMO Network Outage Schedule](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/network-outage-schedule)

| Lead and method | Set-intervals | True / false positives | Missed activations | Precision / recall |
|---|---:|---:|---:|---:|
| About 59 minutes, NOS | 2,476 | 182 / 6 | 4 | 96.8% / 97.8% |
| About 59 minutes, prior case | 2,476 | 168 / 62 | 18 | 73.0% / 90.3% |
| Previous afternoon, NOS | 2,472 | 182 / 18 | 4 | 91.0% / 97.8% |
| Previous afternoon, prior case | 2,472 | 164 / 72 | 22 | 69.5% / 88.2% |

Use NOS for scheduled activation and carry delayed/cancelled alternatives where a set materially changes headroom. All four misses at each lead were T-SHWI. Short-lead false positives included Q-GBMU_835_836, S-RBMWP4 and T-FARC1. Activation identifies equations to evaluate. Binding additionally requires their signed LHS and the relevant solution's marginal values.
