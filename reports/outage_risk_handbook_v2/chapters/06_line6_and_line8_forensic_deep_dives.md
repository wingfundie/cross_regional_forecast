## Chapter 6 · Forensic Deep Dives: Capital-Canberra Line 6 and Dapto-Marulan Line 8

Two specific 330 kV transmission lines in southern New South Wales have drawn sustained operational scrutiny from NEM trading desks: Capital Wind Farm to Canberra Line 6 (`CANBERRA/LINE/6`) and Dapto to Marulan Line 8 (`DAPTO/LINE/8`). Both lines sit directly on the main 330 kV cut-plane connecting Snowy Hydro, the Canberra-Yass-Marulan renewable cluster, and the Sydney-Wollongong load centre. Yet in the legacy single-line study, ultra-strict exact-matching gates withheld quantitative estimates for both assets, leaving desks with descriptive narratives rather than calibrated risk numbers.

Placing Line 6 and Line 8 inside the hierarchical Southern NSW & Snowy 330/500 kV corridor alongside their immediate physical neighbours (`MARULAN/LINE/5`, `CANBERRA/LINE/07`, and `STOCKDIL/LINE/3C`) resolves both the small-sample problem on Line 6 and the sharp VNI flow-reversal mechanics on Line 8.

### 6.1 Side-by-side Southern NSW 330 kV corridor benchmark

| Transmission line | Events (withdrawn) | Outage hours | Raw Cap delta (MW) | EB Cap delta (MW, weight) | Raw Price delta ($/MWh) | EB Price delta ($/MWh) | EB Spread delta ($/MWh) | Binding intervals | Max clean \|MV\| ($/MWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `CANBERRA/LINE/6` (Capital-Canberra 6) | 2 (5) | 390.4 | -129 | -121 (61%) | -$74.24 | -$72.24 | -$12.15 | 1,185 | $263 |
| `DAPTO/LINE/8` (Dapto-Marulan 8) | 8 (4) | 232.1 | -49 | -57 (87%) | -$30.46 | -$31.66 | -$35.36 | 267 | $1,383 |
| `MARULAN/LINE/5` (Yass-Marulan 5) | 11 (5) | 1,480.8 | -225 | -219 (95%) | +$31.35 | -$3.82 | +$18.58 | 5,941 | $1,280 |
| `CANBERRA/LINE/07` (Lwr Tumut-Canberra 07) | 7 (8) | 567.8 | -167 | -163 (93%) | -$13.49 | -$17.93 | -$2.26 | 2,136 | $1,095 |
| `STOCKDIL/LINE/3C` (Stockdill-Canberra 3C) | 4 (2) | 29.1 | -488 | -236 (33%) | +$120.01 | -$38.97 | +$4.28 | 156 | $1,101 |

{{exhibit:b10}}

### 6.2 Capital-Canberra Line 6: why two shoulder-season events require corridor pooling

Capital Wind Farm to Canberra Line 6 illustrates the exact danger of drawing strong commercial conclusions from an $n = 2$ event sample. Across the two-year study window, seven NOS outage bookings were submitted for Line 6, of which five (71%) were withdrawn and only two actually executed, totalling 390.4 outage hours (roughly 16.3 calendar days combined).

Inspecting the realised five-minute telemetry and matched controls during those two executed windows yields four precise findings:

1. **Modest physical VNI limit compression during observed outages:** During Line 6's two executed windows, VNI mean forward limit dipped gently from 860 MW before to 823 MW during (recovering to 803 MW after), while VNI reverse capacity contracted more noticeably from 422 MW before to 312 MW during (-110 MW shift, rebounding to 581 MW after). Mean VNI flow eased from +214 MW northward before the outage to +156 MW during.
2. **Continuous matched and EB-pooled capacity delta (-121 MW):** Against same-season, same-time-of-day non-outage half-hours (781 matched half-hours), Line 6 recorded a raw VNI forward capacity delta of -129 MW (day-clustered SE 51.4 MW). Because $n = 2$ triggers the finite-sample degrees-of-freedom penalty inside the Southern NSW corridor, Empirical-Bayes pooling assigns a 61.0% weight to Line 6's own capacity delta and 39.0% weight to the Southern NSW corridor prior (-125 MW), producing a stabilised estimate of -121 MW.
3. **Benign shoulder-season price realisation (-$72.24/MWh EB, max price $311.91/MWh):** Neither of Line 6's two executed outages coincided with an extreme New South Wales scarcity event (maximum realised NSW price across all 390.4 hours was just $311.91/MWh, averaging $97.99/MWh). Three associated constraint equations bound across 1,185 intervals with a moderate maximum clean median shadow price of $262.86/MWh.
4. **Operational verdict for Line 6:** Line 6 is not a benign zero-risk wire, nor is it a proven standalone price-spike trigger. With 71% historical withdrawal and only two mild-season executions on record, desks should price a future Line 6 booking near the Southern NSW 330 kV corridor prior (-120 to -125 MW VNI capacity risk) while monitoring whether the booking overlaps with Marulan Line 5 (`MARULAN/LINE/5`) or Lower Tumut-Canberra Line 07 (`CANBERRA/LINE/07`), where N-1-1 southern-corridor compounding (Chapter 3) immediately amplifies exposure.

### 6.3 Dapto-Marulan Line 8: severe VNI forward-limit collapse and 571 MW flow reversal

Dapto to Marulan Line 8 presents a sharper and far better-observed physical signature. Over the two-year study window, 12 bookings were submitted, of which 4 were withdrawn (33%) and 8 distinct events executed across 232.1 outage hours (464 matched half-hours).

The most distinctive empirical signature of Line 8 appears directly in the event-aligned VNI telemetry (`before` versus `during` versus `after` across all 8 executed outages):

- **VNI forward export limit collapsed by 440 MW during execution:** Mean VNI forward export limit fell from 600.2 MW before the outage down to 160.2 MW during Line 8 execution, before snapping straight back to 636.9 MW after restoration.
- **VNI physical flow reversed by 571 MW across the border:** Mean VNI dispatch flow flipped from +214.9 MW northward (VIC to NSW) before the outage to -356.3 MW southward (NSW to VIC) during Line 8 execution, recovering to +108.2 MW northward after restoration. Meanwhile, VNI reverse capacity expanded from 434.0 MW before to 657.6 MW during.
- **Elevated binding shadow prices during tight windows ($1,382.59/MWh median |MV|):** Although Line 8's 8 outages were scheduled largely during moderate daytime demand periods (keeping average event NSW price at $45.42/MWh, max $317.33/MWh, EB price delta -$31.66/MWh at 93% weight, and EB spread delta -$35.36/MWh), whenever its three active constraint equations bound (267 binding intervals), their clean median marginal value reached $1,382.59/MWh, the highest binding shadow-price intensity of any line in the entire Southern NSW 330 kV corridor.

### 6.4 Physical grid geometry explaining why Line 8 flips VNI flow while Line 6 softens it

Why do two 330 kV lines sitting less than 120 kilometres apart inside the exact same Southern NSW transmission backbone produce such distinct VNI signatures? Tracing the physical topology from Snowy Hydro to Sydney provides the exact engineering explanation.

Capital Wind Farm to Canberra Line 6 sits on the inland western leg feeding the Canberra sub-ring alongside Lower Tumut-Canberra Line 07 and Stockdill-Canberra 3C. When Line 6 opens under intact neighbouring lines, power generated in the Snowy Mountains and Victoria can still bypass Canberra along the primary eastern 330 kV trunk via Yass and Marulan toward Sydney, as well as parallel feeds into Canberra itself. Consequently, VNI northward transfer eases moderately (-121 MW EB) without forcing wholesale reversal across the Victoria to New South Wales border.

Dapto to Marulan Line 8, by contrast, sits directly on the coastal southern gateway carrying power from the Marulan 330 kV switching hub into the Illawarra-Dapto-Sydney South metropolitan ring. Removing Line 8 throttles the main southern thermal outlet out of Marulan toward Sydney. Because Snowy Hydro generation and southern NSW renewables inject immediately upstream of Marulan, throttling the Marulan-to-Dapto exit immediately backs power up into the Snowy-Yass-Wagga cut-plane. To avoid overloading remaining Marulan-Bannaby-Sydney circuits under an N-1 contingency, NEMDE clamps VNI northward export ceilings down from 600 MW to 160 MW and pushes surplus southern NSW energy southward back into Victoria (-356 MW mean VNI flow during execution). For a VIC to NSW SRA holder, that 571 MW flow reversal is an acute directional hazard: whenever NSW clears even modestly above Victoria during a Line 8 window, southward loop flow converts positive settlement carry into negative residue.

> [!TAKEAWAY] Commercial Distinction Between Line 6, Line 8, and Marulan Line 5
> Within the Southern NSW 330 kV triangle, Marulan Line 5 (`MARULAN/LINE/5`, 11 events, 1,481 hours, -219 MW EB cap drop, +$18.58/MWh EB spread widening, 5,941 binding intervals) is the primary sustained VNI spread-widening and SRA-eroding bottleneck (`N-MNYS_5_WG_CLOSE` cost -$573k/day in Chapter 2). Dapto-Marulan Line 8 (`DAPTO/LINE/8`, 8 events) triggers an immediate 440 MW VNI forward limit collapse and a 571 MW southward flow reversal with $1,383/MWh binding shadow prices whenever active, making it a sharp directional flow-reversal and negative-residue hazard for long VIC-to-NSW SRA positions even when headline NSW spot prices stay moderate. Capital-Canberra Line 6 (`CANBERRA/LINE/6`, 2 events) remains data-scarce and must be evaluated via Southern NSW corridor pooling (-121 MW EB) plus concurrent N-1-1 overlap screening.

Chapter 7 translates all four analytical pillars of Flagship Edition B into a single operational forward-outage screening workflow and exposes the calibrated live forward watchlist.
