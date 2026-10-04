# Review: Quarterly interregional valuation research (18 September 2026)

Reviewer: Claude (Opus 5.5), at the analyst's request. Review date: 25 September 2026.
Scope: everything in `reports/interregional_valuation_research_20260918/`, plus the project archives its code reads.
Audience: trading desk review of SRA versus futures-spread valuation.

This is a review, not an edit. No existing file was changed. Spot-check calculations ran on copies in a temporary scratch directory, reading the project's archived AEMO tables. Appendix A gives the method and results so they can be reproduced.

**How to read the evidence labels.** *Verified by rerun* means I recomputed the figure from the archived data. *Verified from source* means I read the primary document, or the AEMC's consultant report quoting it. *Inferred* means my judgement or knowledge that I did not check against a source during this review. Several AEMO PDFs returned HTTP 403 to automated access. Where that limited verification, I say so.

---

## 1. Executive summary

**Overall assessment.** The work is a careful, well-sourced research design built around a small descriptive analysis that reproduces exactly. The conceptual framing is largely correct and unusually well caveated:

- the additive energy/scarcity identity;
- the separation of a physical distribution from a pricing distribution;
- treating SRA value as the output of an effective-dated settlement function;
- warnings against causal readings of fixed-flow decompositions;
- awareness of the EnergyConnect loop and Basslink regime breaks.

I re-ran `analyse_history.py` against the archived inputs. All four CSVs and the audit JSON came out bit-identical. The committed build script also regenerates the HTML byte-for-byte. Every local number quoted in the report text matches the data.

However, the document is not yet a valuation, and it does not yet answer the desk's question. It never places a futures or cap price, an SRA clearing-price history or a realised SRA payout history next to each other. The market side consists of three auction clearing prices, quoted but never compared with anything. The workbench runs on hypothetical inputs. The only flow-based evidence is Exhibit 9 and §4's covariance diagnostic, and it rests on a proxy with four problems:

- it is lossless;
- it covers one physical link per region pair;
- it uses dispatch targets rather than metered energy;
- its "covariance" is partly produced by how it was constructed.

**Verdict.** In its current form the report is a sound research plan. It is not yet evidence a senior researcher would accept for a trading decision. The gap is closable quickly, because the repository already holds most of the data needed. `data/tables/` contains 36 months of `DISPATCHPRICE` for all five regions and `DISPATCHINTERCONNECTORRES` for all six interconnectors, including `MWLOSSES` and `MARGINALLOSS`. The report uses two years, three links and no loss data.

**The three changes that would most improve the work:**

1. **Build a realised SRA payoff ledger, then test auction prices against it.**
   - *What:* per-interval, loss-adjusted residue, summed across the parallel regulated links that make up each directional interconnector, keeping the positive part (pre-loop rules). Convert to dollars per unit using the published maximum units, reconcile to AEMO's published residue figures, and join every historical auction clearing price.
   - *Spot-check:* the June 2026 clearing prices for Q4 2026 are 41% (QLDNSW), 56% (VICNSW) and 66% (NSWQLD) of the realised per-unit payoff averaged over the last 11 complete quarters. They sit below every one of the last three Q4 outcomes (Appendix A.3).
   - *Caveat:* that is either a large risk premium or a market view that the regime is changing, for example loop settlement from November 2026. It is the single most decision-relevant fact the report could establish, and it is absent.
2. **Bring in futures and cap price history, and measure the SRA/futures relationship directly.**
   - *What:* ex-post risk premia for each regional base and cap leg, and SRA-unit "MW-equivalence" and hedge effectiveness against a 1 MW futures spread, both on average and in stress.
   - *Spot-check:* a VICNSW unit paid about 0.24 MW-equivalent of the flat NSW−VIC spread on average. In the ten highest-spread weeks it paid only 0.07 MW-equivalent (weekly R² = 0.08). A QLDNSW unit behaved like about 1.0 MW, with R² = 0.77 (Appendix A.4).
   - *Why it matters:* this is the relative-value and hedge-ratio evidence a desk needs, and it differs sharply by direction.
3. **Rebuild the historical evidence on settlement-relevant quantities.**
   - *What:*
     - split each spread into a loss-driven part and a congestion part (A.5);
     - quantify counter-price and forced-flow residues (A.2), which matter for the loop regime;
     - use all 36 months (11 complete quarters) and add Tasmania/Basslink;
     - normalise for changes in the market price cap;
     - report uncertainty and single-day fragility instead of point estimates.
   - *Why:* the current seven-quarter window leaves out the largest QLD−NSW quarter available locally (2024 Q2, −$72.53/MWh). Several quarterly spreads are dominated by a single day.

My confidence in each conclusion is given where it is made. It is high for the reproduction, arithmetic and covariance findings, all checked by rerun. It is medium for the per-unit residue proxy, which has about ±10% sensitivity to flow definition and loss share, far smaller than the gap to auction prices. It is low for the reasons behind the auction discount.

---

## 2. Methodology review

There is no standalone methodology file. I treated the following as the methodology:

- the method chapters of `research_report.md`: §3, §5, §6, §9–§16 and Appendix A;
- `analyse_history.py` as its implementation;
- `build_html.py` and `report_interactions.js` as the presentation and calculator layer.

### 2.1 Strengths

**The core accounting is exact and well chosen.** The capped decomposition P = min(P, 300) + max(P − 300, 0) mirrors the ASX base-minus-$300-cap replication. It uses identical interval weights, keeps negative prices in the energy term, and avoids the common error of averaging only sub-$300 intervals. The four-state joint-regime split is also additive. The report warns against percentage shares when the net spread is near zero, and the heatmap's |scarcity| / (|energy| + |scarcity|) measure is a sensible substitute. *Verified by rerun:* every identity closes to machine precision.

**Time semantics are handled correctly.** Intervals are assigned to quarters by the instant before the interval-ending timestamp, and partial quarters are flagged and excluded. The half-hour-averaging exercise correctly shows the convexity bias of computing caps after averaging: NSW Q4 2024 is $47.355 on five-minute prices versus $46.505 on half-hour averages. That is the right warning for any model working at half-hour resolution.

**The framing avoids the usual traps in this literature:**

- keeping the physical distribution P separate from a calibrated pricing distribution Q*;
- refusing to call a fixed-flow counterfactual causal;
- holding SRA prices out of the market calibration so they remain an independent test;
- warning that the flow proxy is "not SRA revenue";
- treating settlement as an effective-dated function with a rule-version registry.

These are the right instincts, and a senior reviewer will recognise them.

**The validation design is appropriate for a trading use.** §16 proposes:

- origins frozen at auction dates;
- scoring at the level of contract payoffs;
- block bootstraps grouped by stress episodes;
- five named baselines;
- ablations covering topology, storage state, tail dependence and loop settlement.

That is consistent with Lago et al. (2021) [S22] and with this repository's own rules.

**Provenance is good by research standards.** Price-input hashes, an audit JSON, a manifest and a QA harness are all present. My reruns reproduced the outputs exactly.

### 2.2 Weaknesses in brief

Most problems are omissions relative to the stated objective, not errors in what was done. Three are substantive methodological defects in the one piece of flow evidence, the gross flow × spread proxy:

- its independence benchmark contains a mechanical term;
- it ignores losses and the parallel links that are pooled into each SRA;
- by construction, it cannot see counter-price residues.

The historical base is also shorter than the data the repository already holds. No uncertainty is attached to any historical figure.

### 2.3 Issues log

Severity scale:

- **Critical:** blocks the stated objective.
- **Material:** changes a conclusion or a valuation input.
- **Minor:** accuracy, clarity or provenance.

| ID | Location | Description | Basis | Severity | Suggested fix |
|---|---|---|---|---|---|
| C-01 | `research_report.md` §13–§14 (L373–417), §22 (L550); `build_html.py` L139–150 | The objective is to compare model value with futures and SRA prices, but no futures or cap price series, no SRA clearing-price history (only three quotes at L409) and no realised SRA payout history are used. The SRA-versus-futures comparison is described but never carried out. The workbench takes hypothetical inputs. | Verified from files | Critical | Gap ranks 1–3 (§4). A first version needs only local dispatch data, published unit counts, AEMO auction reports and the AER's public futures series. |
| M-01 | `analyse_history.py` L55–58; report §4 L146–148; `build_html.py` L154 (Exhibit 9 caption); `report_interactions.js` L79–82 | The "independence benchmark" multiplies the mean of *spread-gated* flow by the mean positive spread. The shared indicator 1{spread > 0} creates positive covariance mechanically. VIC→NSW's reported covariance of $883/h falls to $239/h against the ungated mean flow. Conditional on a positive spread, the covariance is −$4,172/h (correlation −0.02). The Exhibit 9 claim that covariance "is often a large part" of the proxy is overstated for VNI. It holds for QLD→NSW and VIC→SA (A.1). | Verified by rerun | Material | Use ungated flow, or compute covariance conditional on the gate. Add rank and tail-conditional dependence, because covariance with heavy-tailed spreads is dominated by a few intervals. Rewrite the caption. |
| M-02 | `analyse_history.py` L11, L40, L52–61; report L146 | The proxy is lossless, uses the dispatch target `MWFLOW` and uses one asset per pair. AEMC's consultant confirms that each directional interconnector pools Heywood with Murraylink and QNI with Terranora [R1]. With losses included, the pre-loop positive residue on VNI northward is $228.7m over two years, not $267.3m (−14.5%). Murraylink adds $27.9m to VIC→SA and Terranora $22.1m to QLD→NSW (A.2). | Verified by rerun (loss share bracketed 0–1) | Material | Compute residue = P_to·(F − (1−s)·L) − P_from·(F + s·L), where s is the from-region loss share. Sum across the pooled assets and assign direction by net flow. Take the positive part per interval. Use AEMO loss-proportioning factors and metered energy for reconciliation. |
| M-03 | `analyse_history.py` L56 (`clip(lower=0)` plus gate); report §4, §6 | Counter-price flows are excluded by construction. Pre-loop, that is correct for unit value: negative residue is recovered weekly from the importing-region TNSP (NER 3.6.5(a)(4)) [R1]. But NSW→VIC carried −$105.2m of counter-price residue over two years. 47% came from 100 intervals and 52% from intervals with NSW ≥ $300, dominated by forced southward flow at negative VNI export limits while NSW sat at the market price cap (A.2). This matters for the loop regime, for VNI's value as a hedge of NSW scarcity, and for how negative-residue management (NRM) behaves. | Verified by rerun; rule treatment from source [R1] | Material | Report signed, positive and negative residue separately. Tag forced-flow intervals (negative limits) and NRM-clamped intervals. Carry them into the loop counterfactual (gap rank 9). |
| M-04 | Report §16 L448 ("only seven complete quarters"); `analyse_history.py` L10–11 | The repository already holds 36 months of `DISPATCHPRICE` (including TAS1) and `DISPATCHINTERCONNECTORRES` for all six links, 11 complete quarters in all (`data/tables/`, `data/processed/ic_5min.parquet`). The omitted 2024 Q2 had QLD−NSW −$72.53/MWh, of which −$49.04 was scarcity. The cross-quarter standard deviation of QLD−NSW doubles from $13.0 to $26.0 (A.6). | Verified by rerun | Material | Extend to 36 months now. Next, extend to October 2021 onwards (five-minute settlement) from NEMweb, with a half-hour bridge for earlier tail statistics. |
| M-05 | Report §3–§4, §11 | Spreads are never split into a loss-driven part and a congestion part. Regional prices sit exactly at the interconnector's marginal loss factor (P_to = P_from × `MARGINALLOSS`) in 47–58% of intervals. The loss component is $3.25 of VNI's $34.02 two-year mean, but 29% of NSW−VIC in 2025 Q3 and 43% of QLD−NSW in 2026 Q2 (A.5). A futures spread carries the whole loss component. In coupled intervals an SRA earns only the loss surplus, about price × losses. | Verified by rerun | Material | Add the loss/congestion split, crossed with energy/scarcity, and project it forward with AEMO's inter-regional loss equations. |
| M-06 | Report §4 tables; §16 L462 recommends block bootstraps that the report itself does not apply | No historical figure carries an interval, and single days dominate several quarters. SA−VIC 2025 Q3 is $26.53, or $6.80 without 2 July 2025. QLD−NSW 2025 Q1 flips from +$2.00 to −$7.92 without 22 January 2025. SA−VIC 2026 Q1 falls from $45.35 to $18.82 without 26 January (A.7). | Verified by rerun | Material | Add day- and episode-block bootstraps, leave-one-day-out tables and concentration statistics for spreads, not only for regional caps. |
| M-07 | Report §12 L361; §4 | History is not normalised for changes in market settings. Intervals where the market price cap binds contribute up to $8.70/MWh to a quarterly spread. The sample spans two caps, $17,500 (FY25) and $20,300 (FY26), both observed in the data. The report quotes $23,200 for FY27. | Verified by rerun (cap levels from flagged rows); FY27 figure not verified | Material | Rescale cap-binding intervals to the delivery-year cap, or treat the cap as a scenario dimension. Store cumulative price threshold and administered-price settings by date. |
| M-08 | Report §5 L160; §14 L403; §17 L490 | Unit counts are described as "different maximum counts" but never tabulated, so every $/unit ↔ $/MWh conversion stays hypothetical. The 1/1,500 in the examples is in fact the real VICNSW figure. Published maxima: VICNSW 1,500; NSWVIC 1,300; NSWQLD 550; QLDNSW 1,200; VICSA 880; SAVIC 770. NSWQLD and QLDNSW change from 2027 Q2 [R3]. | Verified from search-indexed AEMO notices (PDFs blocked) | Material | Maintain an effective-dated unit registry and use it in every conversion and example. |
| M-09 | Report §8 (L239–283); §23 | The literature review omits the most directly relevant empirical work: (a) transmission-right auction pricing against realised payoffs (US FTR/TCC, European long-term transmission rights, Nordic area-price CfDs); (b) NEM futures risk premia; (c) the AEMC/CEPA 2024 SRA review. | Verified from source (abstracts and indexes) | Material | Add [R1], [R4], [R7]–[R14] and use them to frame testable hypotheses (§4). |
| M-10 | Report §5 L164–178 | The loop regime is described carefully but never quantified, yet it applies from November 2026, the first quarter of the quoted Q4 2026 prices. An illustration (A.8) pools VNI, Heywood and Murraylink residues within each interval. That cuts positive residue by 4.8% ($477.1m → $454.3m); full netting over time would cut it by 31%. The distribution across directions changes further under net-trade allocation. | Verified by rerun (illustration only, not the AEMC method) | Material | Implement the net-trade allocation against AEMO's worked examples [S07], then re-run history as a counterfactual (gap rank 9). |
| m-01 | Report §4 L98; `analyse_history.py` L67 | The 95 rows are described as "administered-price flags". AEMO's data model defines APCFLAG as bit flags: 4 means the market price cap or floor was binding, 16 means inter-regional loss-factor price scaling. None of the 95 rows has bit 1 (administered price cap binding). The 146 "suspension" rows carry an undocumented value of 2, on 5 September 2024 and 23 March 2026. Their contribution is at most $0.11/MWh per quarter. | Verified from source [R2] and by rerun | Minor | Decode the bits and relabel. Report cap-binding intervals as a scarcity diagnostic (see M-07). |
| m-02 | Report §4 L98 ("not an independently certified series") | This caveat can be tightened. Every interval in the seven complete quarters has `PRICE_STATUS = FIRM`. The only 305 NOT FIRM rows fall in August 2026, the partial quarter. | Verified by rerun | Minor | Record `PRICE_STATUS` in the audit. Keep the caveat only for the partial quarter. |
| m-03 | Report §4 table L104–118 | The static table shows 13 of the 21 complete pair-quarters with no stated selection rule. It omits, for example, QLD−NSW 2024 Q4 (−$16.07, with scarcity −$17.68) and SA−VIC 2025 Q4 (−$0.08). | Verified from files | Minor | Show all rows or state the rule. The interactive exhibit already has them all. |
| m-04 | `analyse_history.py` L53, L68 | The flow input `screen_timeseries.parquet` is not hashed in the audit. In 12 intervals on 27 November 2024 it carries physical-run (INTERVENTION = 1) flows, which is undocumented. `MWFLOW` differs from `METEREDMWFLOW` by a mean absolute 75 / 62 / 45 MW (VNI / QNI / Heywood). | Verified by rerun | Minor | Hash every input and document the run selection. Add a metered-flow sensitivity: per-unit results move by up to about 8% (A.3). |
| m-05 | `analyse_history.py` L66 | `price_identity_max_error` tests floating-point arithmetic of min + max, not the data. It is always 0 by construction. | Verified from code | Minor | Replace it with substantive checks: RRP versus ROP, flag decoding, FIRM status, and continuity of flow and limit series. |
| m-06 | `figures/quarterly_spreads.png` | No script in the folder generates this figure. It matches the CSV visually. | Verified from files | Minor | Add the plotting code to the analysis script. |
| m-07 | `report_manifest.json` L36–39 | The recorded input hashes for `build_html.py` and `institutional.css` match neither the committed nor the working-tree files. `report_interactions.js` matches only after CRLF→LF normalisation. The output hash matches, and the HTML rebuilds byte-identically from HEAD. | Verified by rerun | Minor | Normalise line endings before hashing and regenerate the manifest. |
| m-08 | `build_html.py` L141, L149 versus report §17 L478–490 | The workbench defaults (2,208 h, $39 physical spread, $10,000 unit price, $11,600 distributions) differ from the worked example (2,160 h, $30, $15,000, $20,000). The QA asserts the workbench values. | Verified from files | Minor | Align them, or label the workbench as a separate illustration. |
| m-09 | Report §5 L158 ("$10-per-allocated-unit minimum") | I could not verify this clause (AEMO's rules PDF returned 403). CEPA's description of unit value, the positive residue per interval with negatives recovered from TNSPs, mentions no minimum [R1]. | Not verifiable here | Minor | Quote the clause verbatim with its number, and show where it binds in the payoff. |
| m-10 | `report_interactions.js` L50; `build_html.py` L143 | Implied scarcity hours are inferred from the destination cap alone, with a multiplicative loading. That is fine as an illustration, but for spread trading the report's own warning (L389) implies showing the cap *spread* and destination-only states. | Verified from code | Minor | Add a cap-spread version with explicit coincidence assumptions. |

---

## 3. Consistency check

**Report against data.** I checked every locally sourced figure in the report text against a rerun. All of the following reproduce exactly:

- the thirteen-row spread table and the five-row scarcity table;
- the SA Q2 2026 identity: 49.25 hours, 2.255%, $631.67 conditional excess, $14.24 cap payout;
- the half-hour convexity figures ($47.355 against $46.505, a $0.850 understatement, $1,878 per MW-quarter, and VIC's $0.1487 against $0.0840);
- the flow-proxy pairs (15,257 against 14,375, and 17,192 against 7,370);
- the coverage counts (210,240 timestamps, 840,960 observations, 95 and 146 flagged rows).

The illustrative arithmetic is also correct: the worked example ($34 / $18 / $16; $4,320), implied scarcity hours (6.48 and 12.96), the SRA toy conversion ($20.83/MWh), and the QA workbench values (22.08 hours, $650 per unit). The three-year `DISPATCHPRICE` and `DISPATCHINTERCONNECTORRES` tables I used for extensions reproduce the report's overlapping quarters and proxy totals to the cent. The report's event-dataset inputs and the repository's master tables are therefore consistent.

**Report against its own methodology:**

- **§6 and Appendix A (L650) against the code.** They state the identity E[f·d] = E[f]·E[d] + Cov(f, d) for directional flow f and positive spread d. The code instead uses f·1{d > 0} in the benchmark (M-01). The printed identity and the implemented benchmark are different quantities, and the difference is exactly the mechanical term.
- **§16 against the report's own evidence.** §16 requires block-bootstrap intervals "grouped by stress days or episodes". None of the report's historical tables has one (M-06). §4 says flagged intervals "should also be evaluated separately", but the code only counts them (m-01).
- **§5 against Exhibit 9 and the research brief.** §5 insists the SRA must be valued through the settlement function and that the proxy is "not SRA revenue". Exhibit 9's caption and the front matter nonetheless draw a general conclusion about flow–spread covariance from that proxy. The conclusion is route-dependent and, for VNI, largely an artefact.
- **§16 L448 against the repository.** The claim of "seven complete quarters" is true of the three event datasets the script reads. It is not true of the repository, which holds eleven (M-04).

**Report against presentation code:**

- The §17 worked example and the workbench defaults use different illustrative numbers (m-08).
- The research brief in `build_html.py` L119 says "32 external references". The QA counts 36 source entries, which is 32 external plus 4 local and therefore consistent. It says "four mainland regions", which is accurate, though Tasmania is available.
- Manifest input hashes fail for two files, while the output rebuilds byte-identically (m-07).

**Figures I could not reproduce, and why:**

1. The three June 2026 auction clearing prices ($10,000 VICNSW, $6,860.37 NSWQLD, $14,678.82 QLDNSW). AEMO's auction report returned HTTP 403 and there is no local copy, so I used them as quoted.
2. The FY27 market price cap of $23,200/MWh. I did not access the AEMC schedule. The data do confirm the FY25 ($17,500) and FY26 ($20,300) caps, and the step is plausible.
3. The "$10-per-allocated-unit minimum" and other clause-level SRA rule details (403 on the rules PDF).
4. The EnergyConnect dates (1 October and 1 November 2026) and the 16 September 2026 consultation status, which I did not access.
5. `figures/quarterly_spreads.png`, which has no generating code. It is visually consistent with the CSV.

None of the unreproduced items is a local calculation.

---

## 4. Gaps and new angles

The list is ranked by value to the research relative to effort. Effort assumes one analyst working in this repository:

- **S:** under one week.
- **M:** one to three weeks.
- **L:** more than three weeks.

"Value" is judged against the desk's question: is an SRA unit, or a futures spread, cheap or dear, and how well does each hedge the other?

Where I ran a spot-check, the result is in Appendix A. Those numbers are first-pass proxies, not settled results.

| Rank | Extension | What to do | Why it matters for valuation or trading | Data required | Effort | Value |
|---|---|---|---|---|---|---|
| 1 | Realised SRA payoff ledger (pre-loop) | For each 5-minute interval and directional interconnector: (a) compute the loss-adjusted residue, summed over the pooled assets; (b) assign direction by net flow and take the positive part; (c) deduct fees and convert to $/unit using the dated maximum units. Reconcile weekly and quarterly totals to AEMO's published residue and distribution data, with a waterfall of the unexplained differences. | This is the payoff the desk would actually buy. The spot-check (A.3) shows it is feasible, and that the report's proxy is off by 5–15% on the main directions and misses Terranora and Murraylink. | Local `DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES` (with `MWLOSSES`) and `METEREDMWFLOW`. Loss-proportioning factors (AEMO loss factor report or MMS). AEMO SRA residue and distribution tables (MMS IRAUCTION and settlement packages; check public visibility [S29]). Unit notices [R3]. | M | Very high |
| 2 | Auction clearing price vs realised payoff | Join every auction tranche (ideally since 2015; at least since October 2021) to its delivered quarter's realised payoff. Estimate the realised-minus-price premium by direction, time to delivery, season and regime, with bootstrap intervals. | This is the core relative-value test. The spot-check shows Q4 2026 prices at 41–66% of the 11-quarter mean realised payoff (A.3), which is consistent with the systematic under-pricing of transmission rights reported for New York [R11], US FTR auctions [R12–R14] and European long-term rights [R4]. Separating a stable premium from a regime-change expectation needs the full panel. | AEMO quarterly auction reports (clearing prices and units sold per tranche), or the MMS auction tables. Output of rank 1. | M | Very high |
| 3 | Futures and cap price history; ex-post premia | Assemble regional base and $300-cap settlement prices by quarter and trade date. Compute ex-post premia (futures minus realised) for each leg, for the spread and for the capped-energy combination. Measure the four-leg replication cost from bid–ask spreads. | Without this, the SRA-versus-futures comparison cannot be made. NEM futures have carried positive, seasonal, cross-correlated premia [R7], and Nordic area-price CfDs carry significant spread premia [R9, R10]. A first public version is possible from AER statistics [R6]. | AER daily base contract prices and quarterly futures pages [R6] (free, partial). ASX Energy settlement and trade data [S31] (licensed, full). | M–L (data access) | Very high |
| 4 | Loss vs congestion decomposition | Split each interval's spread into P_from·(MLF − 1) and P_to − MLF·P_from, crossed with energy/scarcity. Project the loss term forward from AEMO's inter-regional loss equations under flow scenarios. | Futures carry the whole loss spread, but in coupled intervals an SRA earns only about price × losses. In quiet quarters the loss term is 29–43% of the spread (A.5). It is structural, predictable and scales with the price level, making it the most forecastable part of the spread. | Local `MARGINALLOSS` and `MWLOSSES`. AEMO annual marginal loss factor report (equations, proportioning factors). | S | High |
| 5 | SRA hedge effectiveness vs futures spread | Regress unit payoffs on 1 MW flat-spread P&L at weekly and quarterly frequency. Report hedge ratios, R², tail-conditional ratios and expected shortfall of the residual. Then solve for minimum-variance and minimum-expected-shortfall mixes of units, base legs and caps. | The spot-check shows that direction matters enormously. A VICNSW unit is about 0.24 MW-equivalent on average but about 0.07 MW in stress weeks, a firmness failure. A QLDNSW unit is about 1.0 MW with R² = 0.77 (A.4). This tells the desk what one unit hedges, and when it does not. | Ranks 1 and 3; local data suffice for the realised version. | S (after rank 1) | High |
| 6 | Extend sample; add TAS/Basslink | Re-run everything on the 36 local months now, then on NEMweb data from October 2021. Pre-October 2021 data can inform tail frequencies only through a half-hour → five-minute bridge. Add Basslink directions: VICTAS/TASVIC units exist from July 2026 [S10], and TAS1 and `T-V-MNSP1` are already local. | Seven quarters give fewer than two observations per season. Adding four local quarters doubles the observed QLD−NSW dispersion (A.6). Basslink history, although earned as private market-network revenue, is the only prior for the new units. | Local tables; the NEMweb MMSDM archive. | S (local) / M (download) | High |
| 7 | Uncertainty and fragility of historical evidence | Add day- and episode-block bootstraps, leave-one-day-out analysis, and extremograms of joint exceedance [S19]. Report distributions, not points. | Single days drive several quarters (A.7). A desk will treat an unstable historical mean as noise, and rightly. | Local. | S | Medium–high |
| 8 | Counter-price flows, forced flows and constraint attribution | Attribute separation episodes and negative residues to binding constraint equations and outages, reusing the repository's constraint and outage (NOS) datasets. Tag NRM clamping [R5]. Distinguish system-normal from outage-driven separation. | NSW→VIC's −$105m of counter-price residue arises in NSW scarcity with forced southward flow (A.2). Separation driven by planned outages is partly forecastable from outage plans before an auction, which is a genuine information edge. | Local `data/constraint_*`, `nos_*`, `event_*` datasets; AEMO constraint library. | M | High |
| 9 | Loop-regime counterfactual | Implement the net-trade allocation and loop-level NRM using AEMO's worked examples as unit tests. Re-run history as a counterfactual, and compare per-unit payoffs for VICNSW, NSWVIC, VICSA and SAVIC under the old and new rules. | The loop rules govern every quarter from November 2026, including the quoted Q4 2026 prices. The crude pooling illustration already shifts totals by 5–31% (A.8); the allocation across directions could shift more. | AEMC determination [S06], AEMO reference paper [S07], consultation drafts [S08]; local dispatch data. How EnergyConnect flows are represented historically needs confirming: the local records hold no separate EnergyConnect (Project EnergyConnect, PEC) interconnector ID. | M–L | High |
| 10 | Market-settings normalisation | Rescale cap-binding intervals and cap payouts to the delivery-year market price cap and cumulative price threshold. Model administered pricing where the threshold would be breached. | Up to $8.70/MWh of a quarter's spread comes from cap-binding intervals (M-07). A rising cap raises the scarcity term mechanically. | Local flags; AEMC reliability settings [S28]. | S | Medium |
| 11 | Diurnal and seasonal profile | Break spreads, flow direction and residue down by hour of day and season, including the midday negative-price and evening-ramp regimes. | Payoffs depend on when flow and spread coincide. Retailers' peak and load-shaped exposures, and ASX peak products, are profiled. Cheap, and it improves scenario design. | Local. | S | Medium |
| 12 | Walk-forward valuation baselines | At each historical auction date, value units using simple, frozen rules: trailing same-season realised payoff, trailing 4/8/12-quarter means, a futures-implied scaling, and the report's hybrid once built. Score against realised outcomes. | This turns the §16 design into evidence. Simple baselines may explain most of the auction discount, and the proposed complex model must beat them on identical auction dates. | Ranks 1–3. | M | High |
| 13 | Transmission build and unit-count scenario registry | Maintain dated scenarios for Project EnergyConnect (PEC) stage 2, the QNI unit-count change from 2027 Q2 [R3], VNI West, HumeLink and Marinus, and weight them in 12-quarter-ahead valuations. | Tranches trade up to three years ahead. Unit counts, topology and transfer capability change over that horizon, and the report notes this only qualitatively. | AEMO Integrated System Plan (ISP) and transmission project updates; unit notices. | M | Medium–high |
| 14 | Spread-option benchmark | Treat the pre-loop unit as a strip of five-minute calls on the flow-weighted, loss-adjusted spread. Build a reduced-form benchmark (Margrabe/Kirk-type [R17, R18]) conditioned on flow regime to produce sensitivities to spike frequency, severity and correlation. | It gives Greeks and a sanity check on scaling. Historical and scenario simulation should remain primary, because flow is endogenous to the spread. | Outputs of ranks 1 and 4. | S–M | Medium |
| 15 | Auction microstructure and cash-flow profile | Analyse participation, reserve prices, unsold units, fees, payment instalments and credit support, and compute the internal rate of return (IRR) of unit purchases, not undiscounted margins. | A discount can be compensation for capital and credit costs. §17's undiscounted $5,000 margin is not a return. | SRA rules [S04]; auction reports. | M | Medium |
| 16 | Strategic behaviour at interconnector limits | Test whether importing-region offers become steeper when imports bind (market power under congestion), and how rebidding interacts with separation episodes. | Theory predicts that transmission rights and congestion interact with market power [R16]. AER reports document rebidding in the SA events cited [S13]. Hard to estimate cleanly. | Local offer and dispatch data; AER reports. | L | Medium |

The five most decision-relevant items can be framed as hypotheses a desk would accept:

- **H1 (ranks 1–2): a persistent discount.** SRA clearing prices are, on average, below realised per-unit payoffs, and the discount grows with time to delivery and with the direction's tail exposure. Falsified if the premium is indistinguishable from zero once fees, funding and regime changes are controlled for.
- **H2 (rank 3): the spread premium comes from the cap legs.** Futures spread premia are concentrated in the scarcity (cap) component. Falsified if the capped-energy spread carries a comparable premium.
- **H3 (rank 5): SRA units fail as hedges in stress, and the failure is direction-specific.** It is predictable from import-limit behaviour during destination-region scarcity.
- **H4 (rank 9): the loop regime lowers the value of the VIC-side units.** Loop settlement moves value away from VICNSW and NSWVIC units in intervals with forced counter-price flows.
- **H5 (rank 8): outage plans are an information edge.** Outage-plan information available at auction dates predicts part of the next quarter's separation.

---

## 5. References

### 5.1 Sources consulted in this review

**[R1] CEPA for the AEMC (2024).** *Settlements Residue Auction and Modified Load Export Cost processes*, final report, 24 May 2024. https://www.aemc.gov.au/sites/default/files/2024-06/cepa_report_-_sra_and_mlec.pdf. *Read in full text.* Used for:

- the six directional interconnectors, including the pooling of Murraylink with Heywood and QNI with Terranora;
- negative residue being recovered weekly from the importing-region TNSP rather than netted against unit value (NER 3.6.5(a)(4)–(4B));
- the SRA structure of 12 quarterly tranches per directional interconnector;
- AEMC's (2008, 2009) reasoning on firmness.

**[R2] AEMO.** *MMS Data Model Report — DISPATCHPRICE table.* https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_130.htm. *Accessed.* APCFLAG bit definitions; RRP as the settlement price; PRICE_STATUS.

**[R3] AEMO unit category data notices.** Revised 2022 Q4 v2 and revised 2027 Q1 editions. https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/auction-notices/2022/unit-category-data-2022q4-revised-v2.pdf. *The PDFs returned 403; figures are from the search index.* Maximum units and proportional entitlements, including the QNI unit change from 2027 Q2.

**[R4] Stiewe, C. (2026).** *Arbitrage and rents in European long-term transmission rights.* arXiv:2607.28790, 30 July 2026. https://arxiv.org/abs/2607.28790. *Abstract accessed.* Transmission-right auction prices have historically fallen short of forward-market spreads.

**[R5] Negative-residue management (NRM).** *Search-indexed summaries.* The −$100,000 threshold, and that under loops counter-price flows are clamped only if the loop's net residue is negative.

- AEMO (2016), *Brief on automation of negative residue management*.
- AEMO (2021), *Automation of Negative Residue Management*.
- AEMO (2025), consultation on automating NRM for transmission loops: https://www.aemo.com.au/consultations/current-and-closed-consultations/automation-of-negative-residue-management-for-the-implementation-of-transmission-loops
- WattClarity (June 2025), "AEMO launches consultation to update Negative Residue Management automation procedures".

**[R6] AER wholesale statistics.** "Daily Q1 base contract prices and traded volumes" by region; "Quarterly base futures prices and volume traded". https://www.aer.gov.au/wholesale-markets/wholesale-statistics/quarterly-base-futures-prices-and-volume-traded. *Located; data not downloaded.*

**[R7] Handika, R. and Trück, S. (2013).** *Risk Premiums in Interconnected Australian Electricity Futures Markets.* SSRN 2279945. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2279945. *Abstract.*

**[R8] Flottmann, J. H., Wild, P. and Todorova, N. (2024).** Derivatives and hedging practices in the Australian National Electricity Market. *Energy Policy* 189, 114114. https://ideas.repec.org/a/eee/enepol/v189y2024ics0301421524001344.html. *Index record.*

**[R9] Marckhoff, J. and Wimschulte, J. (2009).** Locational price spreads and the pricing of contracts for difference: Evidence from the Nordic market. *Energy Economics* 31(2), 257–268. DOI 10.1016/j.eneco.2008.10.003. *Abstract.*

**[R10] Kristiansen, T. (2004).** Pricing of Contracts for Difference in the Nordic market. *Energy Policy* 32(9), 1075–1085. https://ideas.repec.org/a/eee/enepol/v32y2004i9p1075-1085.html. *Index record.*

**[R11] Leslie, G. (2021).** Who benefits from ratepayer-funded auctions of transmission congestion contracts? Evidence from New York. *Energy Economics.* https://www.sciencedirect.com/science/article/abs/pii/S0140988320303650. *Abstract.*

**[R12] Opgrand, J., Preckel, P. V., Gotham, D. J. and Liu, A. L. (2022).** Price Formation in Auctions for Financial Transmission Rights. *The Energy Journal* 43(3). DOI 10.5547/01956574.43.3.jopg. *Index record.*

**[R13] Deng, S.-J., Oren, S. and Meliopoulos, A. P. (2010).** The inherent inefficiency of simultaneously feasible financial transmission rights auctions. *Energy Economics* 32(4). https://www.sciencedirect.com/science/article/abs/pii/S0140988310000216. *Index record.*

**[R14] Adamson, S., Noe, T. and Parker, G. (2010).** Efficiency of financial transmission rights markets in centrally coordinated periodic auctions. *Energy Economics* 32(4). https://www.sciencedirect.com/science/article/abs/pii/S0140988310000514. *Index record.*

**[R15] Han, L., Cribben, I. and Trück, S.** Extremal dependence in Australian electricity markets. *Journal of Commodity Markets* (2025). https://www.sciencedirect.com/science/article/abs/pii/S2405851325000200. *The published version of the report's [S19].*

### 5.2 Cited from the reviewer's knowledge, not accessed in this review

**[R16] Joskow, P. and Tirole, J. (2000).** Transmission rights and market power on electric power networks. *RAND Journal of Economics* 31(3), 450–487.

**[R17] Margrabe, W. (1978).** The value of an option to exchange one asset for another. *Journal of Finance* 33(1), 177–186.

**[R18] Carmona, R. and Durrleman, V. (2003).** Pricing and hedging spread options. *SIAM Review* 45(4), 627–685.

**Other background, not accessed:**

- Hogan, W. (1992). Contract networks for electric power transmission. *Journal of Regulatory Economics* 4, 211–242.
- Anderson, E., Hu, X. and Winchester, D. (2007). Forward contracts in electricity markets: the Australian experience. *Energy Policy* 35(5).
- AEMO, annual *Marginal Loss Factors* report, which contains the inter-regional loss equations and loss-proportioning factors needed for gap rank 4.

### 5.3 The report's own sources

[S01]–[S32] and [L01]–[L04] as listed in `research_report.md` §23. I did not re-verify them, except where noted above: S19 through R15, and S04 and S11 as affected by the 403 errors.

---

## Appendix A: Spot-check method and results

**Inputs.** All spot-checks read these project files:

- `data/tables/DISPATCHPRICE` (5 regions, 2023-09-01 to 2026-09-01, INTERVENTION = 0);
- `data/tables/DISPATCHINTERCONNECTORRES` (6 interconnectors; the physical run is used where INTERVENTION = 1 exists, matching the report's screen files).

Unless stated otherwise:

- the window is the report's (Sep 2024 – Aug 2026);
- flows are `MWFLOW`;
- the from-region loss share is s = 0.5, bracketed over 0 to 1;
- interval residue is r = P_to·(F − (1−s)·L) − P_from·(F + s·L) in $/interval (MW/12);
- a directional interconnector is the sum of its pooled assets, with direction set by the sign of net flow;
- the pre-loop unit payoff is the positive part per interval divided by the maximum units.

Fees, metering and settlement revisions are ignored. As a cross-check, the lossless, positive-only, single-asset variant reproduces the report's `positive_gross_proxy_dollars` exactly for all six directions.

### A.1 Covariance diagnostic: effect of the gate

Values are in $/hour, over the report window. The "benchmark" columns are what the product of means would be under independence.

| Direction | Mean product | Report benchmark (gated flow) | Report "covariance" | Ungated benchmark | Ungated covariance | Covariance given spread > 0 | Correlation given spread > 0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| VIC→NSW | 15,257 | 14,375 | 883 | 15,019 | 239 | −4,172 | −0.024 |
| NSW→VIC | 2,237 | 438 | 1,799 | 751 | 1,486 | 1,103 | 0.032 |
| NSW→QLD | 2,376 | 537 | 1,839 | 606 | 1,770 | 2,520 | 0.048 |
| QLD→NSW | 17,192 | 7,370 | 9,823 | 8,158 | 9,034 | 8,526 | 0.061 |
| VIC→SA | 9,854 | 4,198 | 5,656 | 4,834 | 5,021 | 4,829 | 0.043 |
| SA→VIC | 1,486 | 583 | 903 | 879 | 607 | −71 | −0.007 |

Two things stand out. The positive dependence on VNI northward is mostly an artefact of the gate. Where covariance survives, correlations are small (0.04–0.06): the covariance is driven by a small number of extreme intervals, not by broad co-movement. *Confidence: high.*

### A.2 Residue proxies, Sep 2024 – Aug 2026 ($m)

"Negative" means counter-price residue, which pre-loop is recovered from the TNSP rather than netted against units.

| Direction | Report proxy (lossless, positive, main link) | Loss-adjusted positive, main link | Parallel link positive | Negative residue, all links | Signed, main link: range over s ∈ [0, 1] |
|---|---:|---:|---:|---:|---:|
| VIC→NSW (VNI) | 267.3 | 228.7 | n/a | −3.8 | 210.7 to 239.0 |
| NSW→VIC (VNI) | 39.2 | 37.9 | n/a | **−105.2** | −68.5 to −66.2 |
| QLD→NSW (QNI + Terranora) | 301.2 | 284.6 | 22.1 | −10.9 | 274.1 to 285.3 |
| NSW→QLD (QNI + Terranora) | 41.6 | 34.3 | 2.3 | −6.1 | 31.2 to 35.3 |
| VIC→SA (Heywood + Murraylink) | 172.7 | 156.7 | 27.9 | −25.6 | 137.2 to 148.5 |
| SA→VIC (Heywood + Murraylink) | 26.0 | 22.5 | 3.6 | −13.3 | 17.5 to 19.2 |
| VIC→TAS (Basslink) | 150.6 | 144.6 | n/a | −0.7 | 140.7 to 147.2 |

How the NSW→VIC negative residue arises:

- 47% of the −$105.2m comes from 100 intervals.
- 52.5% comes from intervals with NSW ≥ $300.
- The worst days are 13 May 2025 (−$5.75m), 3 December 2024, 5 February 2026 and 6 December 2024.
- The largest single intervals show VNI at a *negative* export limit, i.e. forced southward flow, with NSW at $17,480–$20,300 and VIC near or below zero.
- One example: on 5 February 2026 at 14:30 the flow was −1,266 MW against an export limit of −1,266 MW, giving about −$2.1m in one five-minute interval.

Settlement uses metered energy, and `METEREDMWFLOW` differs materially in some of these intervals. The magnitude is therefore an estimate. *Confidence that the effect exists: high. Confidence in its size: medium.*

### A.3 Pre-loop per-unit payoff proxy against June 2026 clearing prices

Values are in $/unit per quarter, over the 11 complete quarters 2023 Q4 – 2026 Q2.

| Direction (max units) | Mean | Median | Min | Max | Last three Q4s (2023, 2024, 2025) | Q4 2026 clearing price, tranche 11 (June 2026) | Clearing price ÷ mean |
|---|---:|---:|---:|---:|---|---:|---:|
| VICNSW (1,500) | 18,010 | 16,438 | 9,204 | 28,035 | 16,438 / 27,867 / 20,168 | 10,000 | 0.56 |
| QLDNSW (1,200) | 35,704 | 26,487 | 12,675 | 84,933 | 15,130 / 41,438 / 26,487 | 14,679 | 0.41 |
| NSWQLD (550) | 10,444 | 8,841 | 765 | 33,432 | 20,043 / 13,248 / 8,841 | 6,860 | 0.66 |
| NSWVIC (1,300) | 5,039 | 4,287 | 1,109 | 12,826 | n/a | n/a | n/a |
| VICSA (880) | 21,450 | 16,294 | 5,971 | 62,394 | n/a | n/a | n/a |
| SAVIC (770) | 5,418 | 4,694 | 736 | 15,860 | n/a | n/a | n/a |

**Sensitivity.** Switching to `METEREDMWFLOW`, or moving s from 0 to 1, shifts the means by at most about 8–10%; VICNSW, for example, ranges from $16,848 to $20,586. That is far smaller than the 34–59% gap to clearing prices.

**Competing explanations for the gap:**

- **A genuine risk or capital premium.** This is consistent with [R4] and [R11]–[R14].
- **Anticipated regime change.** The loop allocation and loop-level NRM from November 2026, Project EnergyConnect (PEC) stage 2 adding transfer capability, and battery build shortening spikes.
- **Proxy overstatement.** Fees, metering and settlement adjustments are not modelled.
- **Tranche selection.** One tranche's marginal price is not the quarter's average price.

The data here cannot separate these explanations; rank 2 is designed to. *Confidence that clearing prices sat well below realised history: medium–high. Confidence about why: low.*

### A.4 Weekly hedge effectiveness, Sep 2023 – Aug 2026 (156 weeks)

Each unit's payoff is compared with the P&L of a 1 MW flat long-destination, short-origin spread.

| Direction | R² | Spearman ρ | Unit payoff ÷ 1 MW spread P&L, all weeks | Same ratio, ten highest-spread weeks |
|---|---:|---:|---:|---:|
| VICNSW | 0.08 | 0.42 | 0.24 | 0.07 |
| QLDNSW | 0.77 | 0.91 | 1.04 | 0.69 |
| VICSA | 0.62 | 0.80 | 0.56 | 0.34 |

A desk hedging 1 MW of NSW−VIC spread with VICNSW units would need about four units on average. In the weeks that matter most, those four units would have covered only about 0.3 MW. That quantifies the report's qualitative firmness argument (§6). *Confidence: medium–high. The pattern is robust to flow definition; the weekly aggregation is a choice.*

### A.5 Loss-driven vs congestion spread

Regional prices are treated as coupled when |P_to − MLF·P_from| ≤ max($0.01, 10⁻⁴·|P_from|).

| Two-year mean | Spread | Loss part | Congestion part | Intervals coupled at the loss factor |
|---|---:|---:|---:|---:|
| NSW − VIC (VNI) | 34.02 | 3.25 | 30.77 | 47% |
| QLD − NSW (QNI) | −14.91 | −3.51 | −11.40 | 58% |
| SA − VIC (Heywood) | 18.86 | 1.68 | 17.17 | 55% |

Quarterly examples where the loss share is large:

- NSW − VIC 2025 Q3: 3.80 of 12.92;
- QLD − NSW 2026 Q2: −3.41 of −7.97;
- QLD − NSW 2026 Q3 (partial): −8.26 of −15.69.

`MARGINALVALUE` is zero throughout for the regulated links in these public tables, so it cannot be used to detect binding. The loss-factor coupling test is the working alternative. *Confidence: high.*

### A.6 Extending to 36 months

Complete-quarter spreads not in the report, in $/MWh:

| Pair | 2023 Q4 | 2024 Q1 | 2024 Q2 | 2024 Q3 |
|---|---:|---:|---:|---:|
| NSW − VIC | 39.96 | 35.57 | 45.77 | 16.31 |
| QLD − NSW | 1.95 | 30.81 | −72.53 | −20.40 |
| SA − VIC | 6.85 | 3.41 | 7.58 | 53.60 |

Standard deviation across quarters:

| Pair | 7 quarters | 11 quarters |
|---|---:|---:|
| QLD − NSW | 13.0 | 26.0 |
| NSW − VIC | 28.6 | 23.2 |
| SA − VIC | 17.3 | 18.8 |

VIC − TAS averaged −$21.2/MWh over 11 quarters (TAS dearer), with quarters as low as −$52.2.

### A.7 Single-day fragility

Quarterly spreads with and without the most influential day:

| Pair and quarter | Spread | Without top day | Top day | Top day's share |
|---|---:|---:|---|---:|
| SA − VIC 2025 Q3 | 26.53 | 6.80 | 2 Jul 2025 | 75% |
| SA − VIC 2026 Q1 | 45.35 | 18.82 | 26 Jan 2026 | 59% |
| QLD − NSW 2024 Q4 | −16.07 | −6.25 | 27 Nov 2024 | 62% |
| QLD − NSW 2025 Q1 | 2.00 | −7.92 | 22 Jan 2025 | sign flips |
| NSW − VIC, worst case (2025 Q2) | 22.21 | 17.62 | 13 May 2025 | 22% |

### A.8 Loop pooling illustration, Sep 2024 – Aug 2026

This covers VNI, Heywood and Murraylink:

| Measure | $m | Change vs per-link sum |
|---|---:|---:|
| Sum of per-link positive parts | 477.1 | — |
| Pooled within each interval, then positive part | 454.3 | −4.8% |
| Fully netted (signed) | 329.2 | −31% |

This is not the AEMC net-trade allocation. It only bounds how much negative residue inside the loop could offset positive residue. EnergyConnect has no separate interconnector ID in the local records.

### A.9 Flags and price status

- **APCFLAG:** of the 95 rows, the values are 4 (cap or floor binding) and 16 (loss-factor price scaling); there are no bit-1 (administered price cap binding) rows.
- **Suspension flag:** value 2, on 5 September 2024 (13:55–15:10, all mainland regions) and 23 March 2026 (NSW, 82 intervals). Contribution to any quarterly spread is at most $0.11/MWh.
- **Cap-binding intervals:** these contribute at most $8.70 (NSW−VIC), $8.01 (QLD−NSW) and $7.66 (SA−VIC) per quarter.
- **Price status:** all complete-quarter intervals are FIRM. The 305 NOT FIRM rows are all in August 2026.

### A.10 Reproducibility

- **Analysis:** `analyse_history.py`, re-run from a copy with only ROOT/OUT redirected, reproduced all four CSVs and `historical_audit.json` exactly (maximum absolute difference 0.0).
- **Presentation:** `build_html.py`, run on a `git archive HEAD` copy with the bundled Node/Marked runtime, reproduced `Quarterly_Interregional_Valuation_Research.html` byte-for-byte (the output SHA-256 matches the manifest).
- **Review scripts:** the spot-check scripts are in this session's temporary scratch directory and are not saved in the repository. They can be added as a tested module when the extensions are implemented.
