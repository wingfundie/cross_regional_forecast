### Issued regional demand and offered capacity

The public MT PASA regional availability product supplies regional planning demand and offered scheduled generation capacity for target delivery days. Its DEMAND50 field describes a most probable peak as-generated demand excluding non-scheduled generation and scheduled load. Its weekly ENERGYREQDEMAND50 describes operational as-generated consumption excluding scheduled load in GWh. Both have different temporal and physical definitions from a five-minute equation-specific regional demand input. [AEMO MT PASA process, Appendix F](https://wa.aemo.com.au/-/media/files/electricity/nem/planning_and_forecasting/pasa/mt-pasa-process-description-v62.pdf?la=en) · [AEMO report timing and public visibility](https://markets-portal-help.docs.public.aemo.com.au/Content/MTPASA/MTPASAreports.htm)

The pilot selected one coherent original report for NSW, Queensland and Victoria at midnight on the delivery date minus 10, 21 or 42 days, in fixed NEM time. The report creation and original ZIP member modification had to precede that origin by more than 24 hours, allowing for the next-day public release. Publication is inferred from the documented release and preserved source times. Client receipt is unavailable. The retained extracts identify the member, checksum, generation, source fields, offer date and delivery day. [Vintage extracts](pasa_issued.csv) · [Original MT PASA archives](https://www.nemweb.com.au/Reports/ARCHIVE/MTPASA_RegionAvailability/)

The clock benchmark averages observed regional demand at each delivery time on five matching weekdays one year earlier (364 days earlier plus or minus zero, seven and fourteen days). For the daily-peak method, the recorded fraction of each training day's maximum scales the issued daily peak. For the weekly-energy method, the clock profile is divided by the corresponding average hourly MW over five matched historical weeks and multiplied by the issued GWh converted to weekly mean MW. Each historical week and its profile come from before origin. The conversion respects the 04:00 NEM trading-day boundary. Both are research approximations to public dispatch TOTALDEMAND. An updated regional forecast from a user must still be matched to the equation's load definition.

MAE in MW on 192 complete half-hours per region at each lead, covering 4, 11, 18 and 25 February 2026. The three horizons gave the same demand values for all 576 region/half-hour combinations. Equal scores therefore reflect unchanged planning assumptions on these test dates.

| region   |   Historical clock |   Issued peak × shape |   Weekly GWh × shape |
|:---------|-------------------:|----------------------:|---------------------:|
| NSW1     |              925.6 |                2276.2 |                923.9 |
| QLD1     |              477.6 |                1430.9 |                521.5 |
| VIC1     |              698.0 |                2093.5 |                709.6 |

The weekly-energy route was close to the simple historical shape. Scaling to the MT PASA peak substantially overstated intraday demand. Use the weekly conversion and clock as joint baselines when only public data are available, and keep peak-based output for a planning sensitivity. The public regional offered capacity changed by as much as 1129 MW between the 42- and 10-day vintages. It constrains a regional supply scenario; an individual unit's on/off state or MW requires further evidence. [Regional half-hour predictions](regional_forecasts.csv) · [Separate November calibration and February stress results](regional_scores.csv)

### Scheduled outage sets at long leads

The original public network schedule specifies planned outage and linked set windows. A standing set is counted once per half-hour if any of the six native five-minute intervals is active. The direct test uses the delivery window in the schedule issued before origin. The matched baseline carries the set schedule at the same time of day on the origin date. Labels come from the archived nonintervention invocation register, including start and end interval timestamps. A supplementary previous-weekday comparator uses retrospectively reconstructed labels and is listed separately in the evidence. [AEMO network outage schedule](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/network-outage-schedule)

The common universe was frozen on 15 December 2025, before the earliest February forecast. It uses outage-linked sets seen in four earlier monthly NOS snapshots and standing equations with a nonzero QNI or VNI interconnector term. It contains 40 QNI sets and 33 VNI sets. An alternative, origin-listed universe is included in the evidence to identify coverage changes. Neither denominator covers outages with no observed set mapping. Standing membership uses effective/revision times as public-availability proxies, and different valid versions inside the forecast horizon can change actual scope. Each eligible NOS report was generated at least 30 minutes before origin. The absence of original workstation receipt times limits historical verification.

| Link   |   Lead (days) | Source                |   Hits |   False alerts |   Misses | Precision   | Recall   |
|:-------|--------------:|:----------------------|-------:|---------------:|---------:|:------------|:---------|
| QNI    |            10 | Delivery schedule     |     17 |              0 |       56 | 100.0%      | 23.3%    |
| QNI    |            10 | Carry origin schedule |      0 |              0 |       73 | n/a         | 0.0%     |
| QNI    |            21 | Delivery schedule     |     17 |              0 |       56 | 100.0%      | 23.3%    |
| QNI    |            21 | Carry origin schedule |      0 |            112 |       73 | 0.0%        | 0.0%     |
| QNI    |            42 | Delivery schedule     |      0 |              0 |       73 | n/a         | 0.0%     |
| QNI    |            42 | Carry origin schedule |      0 |              0 |       73 | n/a         | 0.0%     |
| VNI    |            10 | Delivery schedule     |      0 |              0 |        0 | n/a         | n/a      |
| VNI    |            10 | Carry origin schedule |      0 |              0 |        0 | n/a         | n/a      |
| VNI    |            21 | Delivery schedule     |      0 |              0 |        0 | n/a         | n/a      |
| VNI    |            21 | Carry origin schedule |      0 |              0 |        0 | n/a         | n/a      |
| VNI    |            42 | Delivery schedule     |      0 |              0 |        0 | n/a         | n/a      |
| VNI    |            42 | Carry origin schedule |      0 |              0 |        0 | n/a         | n/a      |

The fixed VNI cohort had zero active positives in the routine sample, so its recall is unmeasurable. Updating the universe to the sets actually listed in each origin's vintage changes coverage. Among those origin-listed sets, the 10-day QNI schedule returned 80 hits, two false alerts and 135 misses. The 10-day VNI schedule returned 120 hits, 36 false alerts and 58 misses. Longer-horizon origin-listed scores have different denominators. These results favour explicit scenarios for both missing links and changes to known work.

Hits, false alerts and misses count set/half-hour combinations. Repeated half-hours within a single outage are correlated. The four routine Wednesdays and two selected stress dates provide a check of the issued schedule, not a season-wide estimate of accuracy. The target is invocation, which can differ from physical breaker state or the onset of an economic bind. Use the scheduled configuration alongside delayed or cancelled-work cases. [Outage scorecard](outage_scores.csv) · [Forecasts, target labels and original member IDs](outage_rows.csv) · [Set universes](set_universes.csv) · [Source hashes](source_hashes.json)
