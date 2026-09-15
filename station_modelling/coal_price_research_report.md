# NEM coal price assumptions review

## Findings

The most defensible revision is to raise Mt Piper’s provisional delivered fuel assumption from A$5.00/GJ to **A$7.50/GJ**, with an analyst range of A$5.50–8.50/GJ. Centennial’s parent, Banpu, disclosed a substantially higher Australian domestic selling price than the screenshot’s A$5/GJ would imply under ordinary black-coal energy assumptions. This remains a supplier-level proxy: the actual Mt Piper contract price, calorific value and delivered-cost adjustments are not public. [11](https://www.banpu.com/wp-content/uploads/2025/02/2024-Banpu-MDA-En.pdf)

Most other central assumptions should remain provisional rather than be replaced with apparently precise numbers inferred from incomplete contracts. Historical mine-cost disclosures support the broad scale of Loy Yang A’s assumption. Callide’s historical domestic contract terms provide a useful crosscheck. Contractor announcements help bound mine costs at Meandu, Kogan Creek and Commodore, but do not disclose the full cost of delivering coal to the station.

**None of the reviewed sources establishes a complete, current, station-specific delivered price for all charges on the requested June-2025 real-dollar basis.** The CSV therefore leaves `CURRENT_PUBLIC_STATION_PRICE_AUD_GJ` blank throughout. Its populated base prices are modelling recommendations, with evidence quality and limitations beside each row. Retained four-decimal values preserve the original input; they do not represent four-decimal measurement accuracy.

Export exposure requires a separate reconstruction. Vales Point’s approximately 50% Chain Valley supply share is a physical tonne share, while Eraring’s disclosed contracted/hedged coverage is a financial and inventory measure. Neither is an export price weight. The original `GROSS_BETA_REFERENCE` numbers have been archived, not promoted to verified weights. [5](https://announcements.asx.com.au/asxpdf/20260427/pdf/06ywbyxms9scmn.pdf), [17](https://www.deltapae.com.au/operations/chain-valley-colliery/chain-valley-colliery-environment/consolidation-project)

## Scope and interpretation

The review covers the 16 rows visible in the supplied screenshots: 15 operating-asset rows and closed Liddell. Tarong/Tarong North, Callide B/C and Loy Yang A/B remain separate rows. Operating-asset status is not a claim about real-time unit availability. The screenshots are the input record; hidden columns, formulas and the original workbook were not available. Instructions embedded in their notes, such as retaining a prior value, are treated as assertions to assess.

All recommended price inputs target **average delivered station fuel cost in real June-2025 Australian dollars**. Evidence is considered through 15 September 2026; the assumed commercial regime is the latest established in the cited sources. This is a near-term modelling set expressed in a common currency base, not a reconstruction of actual FY25 invoices and not a complete annual forecast to closure. A 2026 contract is not made into a 2025 historical contract by deflating its price.

The target includes coal acquisition or allocated captive mining cost and delivery to the station. Actual source accounting boundaries differ. Mining services may exclude owner staff, royalties, fleet costs, sustaining expenditure or conveyor operation. Accounting fuel expense may contain stockpile effects. The report does not silently combine those scopes into a purported observed price.

### Recommended inputs

All figures below are A$/GJ in June-2025 money. Ranges are deliberately broad **analyst stress scenarios**, not statistical confidence intervals or verified contractual floors and ceilings. A retained central value means evidence did not justify a more reliable replacement.

| Station | Screenshot base | Reviewed base | Reviewed low–high | Basis of decision |
|---|---:|---:|---:|---|
| Bayswater | 3.60 | 3.60 | 3.20–5.50 | Retain prior; raise upper case for contract changes |
| Eraring | 5.50 | 5.50 | 4.50–8.00 | Retain unverified prior; negotiated costs and mine mix unresolved |
| Mt Piper | 5.00 | **7.50** | 5.50–8.50 | Domestic supplier ASP proxy |
| Vales Point B | 5.00 | 5.00 | 4.00–7.50 | Physical blend partly known; component prices unknown |
| Stanwell PS | 2.55 | 2.55 | 2.20–4.50 | Legacy CSA prior; amendment and financing uncertainty |
| Tarong | 2.55 | 2.55 | 2.00–3.50 | Partial contractor-cost crosscheck |
| Tarong North | 2.55 | 2.55 | 2.00–3.50 | Same coal pool as Tarong |
| Kogan Creek | 1.70 | 1.70 | 1.20–2.20 | Captive mine; partial contractor anchor |
| Callide B | 2.00 | 2.00 | 1.40–2.50 | Historical domestic CSA crosscheck |
| Callide C | 2.00 | 2.00 | 1.40–2.50 | Same mine; current charge differences unknown |
| Loy Yang A | 0.68 | 0.68 | 0.55–0.95 | Direct historical management mine-cost disclosure |
| Loy Yang B | 0.72 | 0.72 | 0.55–1.10 | Same mine, different confidential contract |
| Yallourn | 0.8656 | 0.8656 | 0.65–1.20 | Retained prior; current full unit cost unavailable |
| Gladstone | 3.8594 | 3.8594 | 3.00–6.50 | Explicitly weak placeholder; IPPA and rail unresolved |
| Millmerran | 2.05 | 2.05 | 1.20–2.70 | Historical service cost below total-cost prior |
| Liddell | — | — | — | Closed; exclude from active fuel modelling |

Confidence is deliberately downgraded relative to labels such as “medium-high” in the screenshots. Strong evidence about which mine supplies a station is not strong evidence about its confidential tariff. Gladstone is the weakest retained central input. Eraring, Vales Point and Stanwell also warrant wide sensitivities before results are used for precise dispatch-cost comparisons.

## Price reconstruction method

### Evidence hierarchy

Preference is given to a current executed price schedule or disclosed realized station cost, then historical contract evidence, direct mine-cost disclosures and supplier domestic sales. Contractor revenue and fleet expense are crosschecks. Consultant forecasts are useful comparisons once their purpose, dollar year and contract assumptions are understood. General export benchmarks are used only when a contract or replacement-cost argument supports them.

This hierarchy does not make every court passage a current price. A judgment can reliably describe a 2016 agreement while saying little about its 2026 escalated price. Likewise, an independent transaction adviser may disclose valuation limitations rather than a usable tariff. Access status is recorded in the source register: some primary documents were available only through indexed text, and some judgments through reproductions. Such evidence is identified rather than presented as a fully inspected current contract.

### Units and dollar bases

For a price quoted per tonne, divide by the energy content on the **same moisture and calorific basis**. As-received, air-dried, gross and net values are not interchangeable. The calculations use 0.004184 GJ/t per kcal/kg where appropriate. Modern assays take precedence over historical engineering tables.

For dated monetary anchors, the diagnostic conversion is:

`June-2025 A$/GJ = historical A$/t × (June-2025 CPI / historical CPI) ÷ GJ/t`

General CPI is a transparent purchasing-power conversion, not evidence that a coal contract actually escalates with CPI. June-2025 CPI is 141.7 on the historical ABS series. The calculation file records when a quarter approximates the timing of an annual price or verbal disclosure. Forward multiyear contractor headline amounts are left on their nominal contract basis when the payment schedule is unknown. [45](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jun-quarter-2025)

### Blending and heat rates

For tonne quantities `t`, energy contents `q` and component prices per GJ `p`, the delivered blend is:

`blend price = sum(t × q × p) / sum(t × q)`

A 50/50 tonne blend is a 50/50 energy blend only if component energy contents are equal. Mine shares should refer to station consumption, with stockpile timing reconciled, rather than supplier production or exports. For example, a mine exporting 40% of its output does not establish that 40% of a domestic customer’s fuel price is export-linked.

Fuel cost per MWh is price/GJ multiplied by heat rate/GJ per MWh. Different heat rates at two stations using the same coal do not justify different coal prices/GJ. Fixed capability charges in a coal supply agreement need a separate allocation assumption if they are to be included in average fuel cost.

## Station findings

### 1. Bayswater

Peabody’s Wilpinjong technical report identifies an open-book AGL supply arrangement scheduled to finish in 2028, with flexible nominations. The historic quantity is unsuitable as a current Bayswater blend after Liddell’s closure. AGL’s disclosures also describe access to lower-energy coal and discounted additional supply, alongside rising costs as legacy arrangements change. [1](https://www.sec.gov/Archives/edgar/data/1064728/000106472826000006/btu_20251231xex962.htm), [2](https://announcements.asx.com.au/asxpdf/20250813/pdf/06mtcw5jhkzf4t.pdf)

The screenshot’s claim that A$3.60/GJ is established by fleet reconciliation is too strong. Two station prices cannot be uniquely solved from one fleet-cost total without independent fuel quantities and a cost-allocation rule. The FY25 and HY26 fleet disclosures are useful consistency checks, but neither supplies that missing identification. Retain A$3.60/GJ provisionally and widen the high case to A$5.50/GJ; obtain current Wilpinjong nominations and other supplier contract shares before assigning an export sensitivity. [3](https://www.agl.com.au/content/dam/digital/agl/documents/about-agl/company-docs/250813-2-agl-energy-limited-annual-report-2025.pdf), [4](https://www.agl.com.au/content/dam/digital/agl/documents/about-agl/news-centre/2026/260211-appendix-4d-and-fy26-half-year-report.pdf)

### 2. Eraring

Origin describes a diversified coal portfolio with substantial contracting and hedging. Myuna is physically dedicated to Eraring, while other supply includes Mandalong. The final March 2026 agreement does not publish a tariff. The A$50 million annual amount in the preceding negotiation announcement cannot be assumed to be an agreed surcharge and spread mechanically across station burn. [6](https://www.originenergy.com.au/about/investors-media/origin-and-centennial-agree-supply-from-myuna-colliery/), [7](https://www.originenergy.com.au/about/investors-media/origin-offers-myuna-end-of-life-coal-supply-agreement/), [8](https://www.aph.gov.au/Parliamentary_Business/Hansard/Hansard_Display?bid=committees%2Fcommsen%2F27922%2F&sid=0000), [9](https://www.centennialcoal.com.au/operations/mandalong?page=1)

Retain A$5.50/GJ as a low-confidence prior, with A$4.50–8.00/GJ scenarios. There is insufficient evidence to assert either that the old A$7.0161/GJ was wrong or that A$5.50/GJ is the actual current price. The disclosed FY27 coverage provides a useful hedge scenario, but the precise effective response to a Newcastle price change still requires contract slopes, quality discounts, FX treatment and hedge maturities. The 15–25% uncovered-volume complement is not inserted as an export beta.

### 3. Mt Piper

The domestic agreement spans multiple Centennial mines. Banpu’s 2024 domestic ASP excluding traded coal was A$170.52/t. Using 23 GJ/t as an explicitly assumed station-coal energy value and June-2024 CPI as an approximate annual timing anchor gives A$7.57/GJ in June-2025 dollars; rounding to the nearest A$0.50 gives the recommended A$7.50/GJ. The same price at 21–24 GJ/t gives approximately A$7.25–8.29/GJ. [10](https://www.energyaustralia.com.au//about-us/media/news/energyaustralia-accelerates-investment-energy-supply-reliability-following-2022), [11](https://www.banpu.com/wp-content/uploads/2025/02/2024-Banpu-MDA-En.pdf)

This is not proof of Mt Piper’s invoice. Banpu’s later mixed domestic/export ASPs are lower and cannot simply be substituted for the domestic figure. CLP’s latest cited annual-results discussion notes higher Mt Piper coal costs. Together these justify challenging A$5/GJ while allowing a materially lower downside for station mix and different contract terms. The wide A$5.50–8.50 range also acknowledges unknown delivery adjustments. [13](https://www.banpu.com/wp-content/uploads/2026/02/2025-Banpu-MDA-En.pdf), [14](https://market.sec.or.th/public/idisc/Download?FILEID=dat%2Fnews%2F202605%2F0148NWS120520260708158910E.pdf), [16](https://www.clpgroup.com/content/dam/clp-group/channels/investor/document/3-2-results---presentations/2025/CLP%20Holdings_2025%20Annual%20Results%20Analyst%20Briefing_Transcript.pdf.coredownload.pdf)

The amalgamation adviser report was also examined. It does not fill the contract gap: its Australian mining valuation discusses the inability to estimate certain future mine production and prices sufficiently for a DCF. This is a useful limit on what transaction documents establish, not a new price source. [15](https://www.banpupower.com/wp-content/uploads/2026/01/1313NWS070120261751295780E.pdf)

### 4. Vales Point B

Delta’s approximate 50% Chain Valley contribution supports a two-source physical structure. The 2026 approval restricts that mine’s coal to Vales Point. It does not demonstrate a 50% export-price weight for the remaining coal, or establish the screenshot’s A$3.50/GJ captive and A$6.50/GJ external prices. [17](https://www.deltapae.com.au/operations/chain-valley-colliery/chain-valley-colliery-environment/consolidation-project), [18](https://www.ipcn.nsw.gov.au/news/chain-valley-colliery-consolidation-project-approved-limited-supplying-vales-point-power)

The applicant’s hearing evidence expressly complicates the assumption that captive coal must be cheaper: supply reliability and handling logistics also matter. Retain A$5/GJ with A$4–7.50/GJ scenarios and blank reviewed component prices. The original component calculation is preserved only as unverified arithmetic in the calculations file. Mine receipts, assays and external contract prices would make this station particularly suitable for a genuine bottom-up blend. [19](https://www.ipcn.nsw.gov.au/sites/default/files/2026-02/Chain%20Valley%20Colliery%20Consolidation%20Project_Applicant%20meeting%20transcript.pdf)

### 5. Stanwell PS

The Curragh relationship supports domestic-contract economics, but the screenshot’s fixed-contract description needs updating. Coronado reports significant amendments involving prepayments, rebate treatment and additional supply; subsequent disclosures discuss reset timing and continuing deferred balances. An assumption of permanent insulation at one unchanged tariff is therefore too strong. [20](https://www.sec.gov/Archives/edgar/data/1770561/000110465926046838/tm264496d1_ars.pdf), [21](https://www.sec.gov/Archives/edgar/data/1770561/000110465926007024/tm264164d1_ex99-1.htm), [22](https://www.sec.gov/Archives/edgar/data/1770561/000156276226000094/Form10q2026q2.htm)

Retain A$2.55/GJ as a legacy-price prior and widen the upper case to A$4.50/GJ. A complete reconciliation needs the contracted delivery charge, prepayment recovery, waived or deferred rebates, inventory and any right-to-mine accounting. Dividing a financing advance by current coal burn would mix cash timing with fuel expense. Supplier-wide thermal or export shares are not a substitute for this contract analysis.

### 6. Tarong

Meandu’s dedicated supply and short conveyor strongly support a mine-cost framework. The new A$750 million, 5.5-year contractor award provides a useful partial anchor. At an assumed 6 Mtpa and historical 19.6 GJ/t, its headline annualized fee is approximately A$1.16/GJ on the contract’s forward nominal basis. This excludes important owner costs: NRW confirms a client-owned fleet. [23](https://www.stanwell.com/meandu-mine), [24](https://nrw.com.au/golding-awarded-stanwell-meandu-mine-contract/), [25](https://announcements.asx.com.au/asxpdf/20260219/pdf/06wgt7sqywy861.pdf)

Retain A$2.55/GJ rather than replace it with the contractor quotient. A$2.00–3.50/GJ spans throughput, owner cost and new-contract uncertainty. Using rated mine capacity as actual output would bias the quotient downward. Zero immediate conventional export pass-through is a reasonable model assumption, while mine inflation and capital requirements remain relevant.

### 7. Tarong North

Use the same A$2.55/GJ coal basis as Tarong because the normal supply is the same mine system. Different generating efficiency should alter the fuel quantity per MWh, not the coal price per GJ. Separate allocated mine costs would require evidence of an actual accounting or commercial distinction; no such current distinction was established. [23](https://www.stanwell.com/meandu-mine)

### 8. Kogan Creek

The A$150 million four-year mining contract is a partial cost anchor for captive coal. At an illustrative 2.5 Mtpa it implies A$15/t of contractor revenue on the headline contract basis. It does not establish total owner cost, annual expenditure timing, current coal quality or the terms after June 2026. [26](https://announcements.asx.com.au/asxpdf/20211115/pdf/452yzygjvz0n4n.pdf)

Retain A$1.70/GJ and widen the range to A$1.20–2.20/GJ. CS Energy’s mine ownership and conveyor supply support zero routine export-price pass-through as a modelling assumption. A current option-exercise announcement or replacement contract, mine output and owner operating costs are required before a more accurate total can be calculated. [27](https://www.csenergy.com.au/what-we-do/thermal-generation/kogan-creek-power-station), [28](https://www.csenergy.com.au/ArticleDocuments/191/CS%20ENERGY%20ANNUAL%20REPORT%202022%20ONLINE.pdf.aspx)

### 9. Callide B

The indexed reproduction of the 2026 Batchfire shareholder judgment describes historical domestic obligations at approximately A$27/t in the 2016 transaction context, with domestic supply priority. Rebased by general CPI and converted using Batchfire’s stated 4550 kcal/kg domestic product, this gives about A$1.84/GJ. This supports the scale of A$2/GJ but is not the actual contractual escalation formula. The primary court endpoint was restricted and the reproduction’s direct page was unavailable; that access limitation prevents treating this as fully reverified executed-contract evidence. [29](https://changeflow.com/govping/courts-legal/shareholder-oppression-claim-dismissed-20th-mar-2026-04-02), [30](https://jws.com.au/what-we-think/oppression-is-not-unlawfulness-federal-court-reinforces-boundary-between-breach-of-duty-and-statutory-oppression/), [31](https://www.batchfire.com.au/about/)

Retain A$2/GJ with A$1.40–2.50/GJ scenarios. Batchfire’s ability to export does not itself link the domestic tariff to spot exports. A zero spot-export sensitivity scenario is conditional on continuity of the described domestic contract, not a verified permanent beta.

### 10. Callide C

The same mine and historical common-bunker arrangements support using the same initial coal price as Callide B. They do not prove identical current capability charges, escalation or settlement terms. Keep A$2/GJ and the same range pending those details; apply Callide C’s own heat rate separately. Historical required supply quantities in the court discussion should not be mistaken for realized annual consumption. [32](https://www.accc.gov.au/system/files/public-registers/documents/D06%2B58398.pdf)

### 11. Loy Yang A

AGL management’s 2018 site-visit transcript gives an approximate A$4/t all-up figure. Applying CPI and the historical consultant energy assumption of 8.2 GJ/t produces about A$0.61/GJ in June-2025 money. Because the verbal cost definition and current assay are incomplete, this is a useful scale check rather than a current measured total. [36](https://www.agl.com.au/content/dam/digital/agl/documents/about-agl/investors/2018/20181023-transcript-from-webcast-loy-yang.pdf), [37](https://www.qca.org.au/wp-content/uploads/2019/05/11873_ACIL-Final-Report-Calculation-of-Energy-Costs-in-the-BRCI-for-2010-11-4.pdf)

Retain A$0.68/GJ with A$0.55–0.95/GJ scenarios. This has stronger independent support than a fleet-only reconstruction, but still needs current mining expenditure and coal energy delivered to the station. Conventional thermal-export blending is not appropriate for the brown-coal fuel stream.

### 12. Loy Yang B

Loy Yang B uses the same mine system under a separate supply arrangement. The historical statutory agreement architecture includes capability and consumption payments. It does not reveal the current annual tariff. [38](https://classic.austlii.edu.au/au/legis/vic/consol_act/lyba1992114/sch1.html)

Retain A$0.72/GJ only as a low-confidence contract proxy, with a wider A$0.55–1.10/GJ range. The A$0.04/GJ premium over Loy Yang A is not publicly established. A heat-rate difference cannot substantiate it. Accurate average pricing requires both the current volume charge and a stated treatment of fixed capability charges.

### 13. Yallourn

The historic mining extension disclosed approximately A$450 million revenue for the RTL joint venture, with A$195 million being Thiess’s share, extending operations to 2026. Its scope included overburden, coal and conveyor maintenance. Using A$195 million as the total contract cost would materially understate that particular service contract. [39](https://www.hochtief.com/news-media/press-releases/press-release/cimics-thiess-awarded-195-million-yallourn-mining-extension-1)

There is insufficient current throughput and owner-cost detail to turn this into a reliable present A$/GJ estimate. Retain A$0.8656/GJ as an explicit prior with A$0.65–1.20/GJ scenarios. The dedicated brown-coal supply supports zero conventional export blending; the planned 2028 closure means end-of-life mine costs warrant separate sensitivity. [40](https://www.clpgroup.com/en/about/our-business/assets-and-services/australia/yallourn-coal-fired-power-station-and-brown-coal-open-cut-mine.html)

### 14. Gladstone

Court material describes a more complex commercial structure than a simple purchased-coal price: coal arrangements, rail costs, stockpile definitions and IPPA allocations matter. The appeal is relevant to interpreting the historic dispute. Neither judgment supplies a usable current delivered tariff. [41](https://www.casechat.au/cases/au/gps-power-pty-ltd-v-cs-energy-ltd-2), [42](https://casechat.au/cases/au/cs-energy-limited-v-gps-power-pty-limited)

The screenshot’s A$3.8594/GJ was a peer transfer, and remains the least defensible central input. Retain it visibly as a placeholder rather than invent a replacement from an onerous-contract provision. Widen the upper case to A$6.50/GJ. Group fuel expense and the present value of IPPA losses are different quantities, neither yielding station coal cost without further schedules. [43](https://www.csenergy.com.au/ArticleDocuments/191/CS%20ENERGY%20ANNUAL%20REPORT%202025%20FULL%20COLOUR%2020250926.pdf.aspx)

### 15. Millmerran

The historical Commodore service contract and throughput provide a reproducible partial-cost check: A$286 million divided by five years, 3.6 Mtpa and 17.6 GJ/t, then CPI adjusted, gives about A$1.13/GJ. The assumptions combine a headline multiyear award, historical output and an old engineering quality value. The result excludes owner costs and does not establish successor terms after August 2024. [33](https://www.nzx.com/announcements/323414), [34](https://buma.com.au/project/commodore/), [35](https://minedocs.com/22/Queensland_Coals-Other-2003.pdf)

The A$2.05/GJ prior is consequently plausible as a conservative total-cost allowance, but not proved by the contractor disclosure. Retain it, reducing the low scenario to A$1.20/GJ while retaining A$2.70/GJ high. A current mine expenditure bridge would be needed to justify cutting the central estimate. Dedicated mine-mouth supply supports zero routine export pass-through as a near-term assumption.

### 16. Liddell

Liddell is closed and should remain excluded from active generation modelling. Blank prices are retained; replacing them with numeric zero risks treating a closed asset as free-fuel capacity. Its closure also matters for interpreting older Wilpinjong supply quantities. [1](https://www.sec.gov/Archives/edgar/data/1064728/000106472826000006/btu_20251231xex962.htm)

## Export weights and forward modelling

The companion blend CSV deliberately separates physical supply, export divertibility and contract indexation. Known normal captive supply is represented as 100% dedicated source, explicitly distinct from a metered annual blend. Zero price pass-through for captive systems is a modelling recommendation, conditional where contracts may reset. Unknown external contract weights remain blank; blank must not be converted to zero on import.

For Vales Point, the Chain Valley physical export restriction supports zero diversion for that component. It does not establish a zero negotiated-price response for every possible contract period. For Eraring, forward stock and hedges reduce residual exposure over a stated horizon, but do not reveal the underlying mine shares. No defensible station-specific mix of Newcastle 4500/5500/6000 benchmark weights was established for the remaining stations.

A forward model should use a time-dependent contract schedule: mine or supplier energy shares; fixed and indexed tariff components; benchmark specification and FX; transport; hedge and inventory coverage; renewal dates; and captive mine cost escalation. Market shocks should be applied to the contract-sensitive component. Applying an export adjustment to a base price that already embeds export-priced purchases risks double counting.

ACIL/AEMO remains a comparator. Its forecast framework and real-January-2024 base differ from observed station cash costs. In particular, a general Bayswater FY2030 expiry assumption cannot override Peabody’s specific 2028 Wilpinjong disclosure. Neither date necessarily covers every Bayswater supplier. [44](https://aemo.com.au/-/media/files/major-publications/isp/2025/acil-allen-2024-fuel-price-forecast-report.pdf)

## Remaining information with the highest value

1. **Mt Piper:** current Springvale/Airly delivered quantities, moisture/energy assays and executed tariff schedules. These would directly test the largest central revision.
2. **Gladstone:** IPPA coal and rail cost schedules, supplier invoices and allocation rules. These would replace the weakest placeholder.
3. **Eraring:** final Myuna price formula and volume allocation, other supplier discounts and hedge schedule. These would distinguish average cost from residual market exposure.
4. **Stanwell:** an accounting bridge across contracted charges, prepayments, rebates and the reset period. This would prevent a large cash-timing distortion.
5. **Vales Point:** actual energy shares and component prices, including external conveyor supplies. These would turn the approximate physical split into a price blend.
6. **Captive mines:** annual operating cost, sustaining capital policy, production and delivered energy. These would upgrade contractor-fee diagnostics to full-cost estimates.

The review's central lesson is not that every original number should move. Accuracy improves when unsupported precision, mismatched price bases and false export weights are removed. The regenerated files preserve the original assumptions, provide a usable revised scenario set, and identify exactly which additional evidence would materially improve each row.

## Sources

Full titles, dates, exact URLs, relevant locations and access limitations follow. The separate source-register CSV also records each source’s claim and limitations. Reproductions and indexed-only documents are explicitly identified; inclusion does not imply a live unrestricted download.

<!-- GENERATED SOURCE LIST -->

1. Peabody / SEC. [2025 Wilpinjong technical report summary](https://www.sec.gov/Archives/edgar/data/1064728/000106472826000006/btu_20251231xex962.htm). 2026. Sections 16.2 and 16.4. Access: PUBLIC_PRIMARY_TEXT.

2. AGL. [FY25 results presentation](https://announcements.asx.com.au/asxpdf/20250813/pdf/06mtcw5jhkzf4t.pdf). 2025-08-13. Slide 33. Access: PUBLIC_PRIMARY_TEXT.

3. AGL. [Annual Report 2025](https://www.agl.com.au/content/dam/digital/agl/documents/about-agl/company-docs/250813-2-agl-energy-limited-annual-report-2025.pdf). 2025-08-13. Operating and financial review, p.24. Access: PRIMARY_INDEXED_TEXT; large PDF not fully retrieved.

4. AGL. [FY26 half-year report](https://www.agl.com.au/content/dam/digital/agl/documents/about-agl/news-centre/2026/260211-appendix-4d-and-fy26-half-year-report.pdf). 2026-02-11. Operating review, p.7. Access: PUBLIC_PRIMARY_TEXT.

5. Origin Energy. [March 2026 quarterly report](https://announcements.asx.com.au/asxpdf/20260427/pdf/06ywbyxms9scmn.pdf). 2026-04-27. Commodity exposure, PDF p.28. Access: PUBLIC_PRIMARY_TEXT.

6. Origin Energy. [Origin and Centennial agree supply from Myuna Colliery](https://www.originenergy.com.au/about/investors-media/origin-and-centennial-agree-supply-from-myuna-colliery/). 2026-03-03. Announcement. Access: PRIMARY_INDEXED_TEXT.

7. Origin Energy. [Origin offers Myuna end-of-life coal supply agreement](https://www.originenergy.com.au/about/investors-media/origin-offers-myuna-end-of-life-coal-supply-agreement/). 2026-02-05. Negotiation announcement. Access: PRIMARY_INDEXED_TEXT.

8. Australian Parliament. [Senate committee hearing, 23 April 2024](https://www.aph.gov.au/Parliamentary_Business/Hansard/Hansard_Display?bid=committees%2Fcommsen%2F27922%2F&sid=0000). 2024-04-23. Evidence concerning Myuna. Access: PUBLIC_PRIMARY_TEXT.

9. Centennial. [Mandalong operation](https://www.centennialcoal.com.au/operations/mandalong?page=1). undated. Operation description. Access: PUBLIC_PRIMARY_TEXT.

10. EnergyAustralia. [Investment in supply reliability following 2022](https://www.energyaustralia.com.au//about-us/media/news/energyaustralia-accelerates-investment-energy-supply-reliability-following-2022). 2023. Coal supply discussion. Access: PUBLIC_PRIMARY_TEXT.

11. Banpu. [2024 Management Discussion and Analysis](https://www.banpu.com/wp-content/uploads/2025/02/2024-Banpu-MDA-En.pdf). 2025-02. Australia domestic selling price discussion. Access: PRIMARY_INDEXED_TEXT.

12. Banpu. [Annual Report 2024](https://www.banpu.com/wp-content/uploads/2025/03/Banpu-One-Report-2024_EN_14-Mar-25.pdf). 2025-03-14. p.217. Access: PRIMARY_INDEXED_TEXT.

13. Banpu. [2025 Management Discussion and Analysis](https://www.banpu.com/wp-content/uploads/2026/02/2025-Banpu-MDA-En.pdf). 2026-02. Australia mining results. Access: PRIMARY_INDEXED_TEXT.

14. Banpu / Thai SEC. [Q1 2026 Management Discussion and Analysis](https://market.sec.or.th/public/idisc/Download?FILEID=dat%2Fnews%2F202605%2F0148NWS120520260708158910E.pdf). 2026-05-12. Australia discussion, pp.9-10. Access: PUBLIC_PRIMARY_TEXT.

15. Banpu Power / independent financial adviser. [Independent financial adviser opinion on amalgamation](https://www.banpupower.com/wp-content/uploads/2026/01/1313NWS070120261751295780E.pdf). 2026-01-07. Section 5 p.100; PDF p.200. Access: PUBLIC_PRIMARY_TEXT.

16. CLP. [2025 annual results analyst briefing transcript](https://www.clpgroup.com/content/dam/clp-group/channels/investor/document/3-2-results---presentations/2025/CLP%20Holdings_2025%20Annual%20Results%20Analyst%20Briefing_Transcript.pdf.coredownload.pdf). 2026-02-26. Australia performance discussion. Access: PUBLIC_PRIMARY_TEXT.

17. Delta Electricity. [Chain Valley Colliery consolidation project](https://www.deltapae.com.au/operations/chain-valley-colliery/chain-valley-colliery-environment/consolidation-project). undated. Project overview. Access: PRIMARY_INDEXED_TEXT; direct access restricted.

18. NSW Independent Planning Commission. [Chain Valley consolidation approved, limited to Vales Point](https://www.ipcn.nsw.gov.au/news/chain-valley-colliery-consolidation-project-approved-limited-supplying-vales-point-power). 2026-04. Decision summary. Access: PUBLIC_PRIMARY_TEXT.

19. NSW Independent Planning Commission. [Chain Valley applicant meeting transcript](https://www.ipcn.nsw.gov.au/sites/default/files/2026-02/Chain%20Valley%20Colliery%20Consolidation%20Project_Applicant%20meeting%20transcript.pdf). 2026-02-09. p.8. Access: PUBLIC_PRIMARY_TEXT.

20. Coronado Global Resources / SEC. [2025 Form 10-K / annual report](https://www.sec.gov/Archives/edgar/data/1770561/000110465926046838/tm264496d1_ars.pdf). 2026. Stanwell agreements and amendments; pp.17-19; related financing notes. Access: PUBLIC_PRIMARY_TEXT.

21. Coronado Global Resources / SEC. [December 2025 quarterly report](https://www.sec.gov/Archives/edgar/data/1770561/000110465926007024/tm264164d1_ex99-1.htm). 2026-01. Stanwell coal supply agreement. Access: PUBLIC_PRIMARY_TEXT.

22. Coronado Global Resources / SEC. [Q2 2026 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1770561/000156276226000094/Form10q2026q2.htm). 2026. Stanwell / NCSA and deferred right-to-mine discount discussion. Access: PUBLIC_PRIMARY_TEXT.

23. Stanwell. [Meandu Mine](https://www.stanwell.com/meandu-mine). undated. Mine overview. Access: PUBLIC_PRIMARY_TEXT.

24. NRW Holdings. [Golding awarded Stanwell Meandu Mine contract](https://nrw.com.au/golding-awarded-stanwell-meandu-mine-contract/). 2026-01-19. Contract announcement. Access: PUBLIC_PRIMARY_TEXT.

25. NRW Holdings. [HY26 results presentation](https://announcements.asx.com.au/asxpdf/20260219/pdf/06wgt7sqywy861.pdf). 2026-02-19. p.9. Access: PUBLIC_PRIMARY_TEXT.

26. NRW Holdings. [Kogan Creek contract extension](https://announcements.asx.com.au/asxpdf/20211115/pdf/452yzygjvz0n4n.pdf). 2021-11-15. Contract terms. Access: PUBLIC_PRIMARY_TEXT.

27. CS Energy. [Kogan Creek Power Station](https://www.csenergy.com.au/what-we-do/thermal-generation/kogan-creek-power-station). undated. Fuel supply. Access: PUBLIC_PRIMARY_TEXT.

28. CS Energy. [Annual Report 2022](https://www.csenergy.com.au/ArticleDocuments/191/CS%20ENERGY%20ANNUAL%20REPORT%202022%20ONLINE.pdf.aspx). 2022. p.25. Access: PUBLIC_PRIMARY_TEXT.

29. Federal Court, reproduced by Changeflow. [Our Jim & Felicja Superfund v Lindenfels [2026] FCA 307](https://changeflow.com/govping/courts-legal/shareholder-oppression-claim-dismissed-20th-mar-2026-04-02). 2026-03-20. Paragraphs 153 and 159-160. Access: INDEXED_JUDGMENT_REPRODUCTION.

30. Johnson Winter Slattery. [Oppression is not unlawfulness](https://jws.com.au/what-we-think/oppression-is-not-unlawfulness-federal-court-reinforces-boundary-between-breach-of-duty-and-statutory-oppression/). 2026-05-26. Case discussion. Access: PUBLIC_PRIMARY_TEXT.

31. Batchfire Resources. [About Batchfire](https://www.batchfire.com.au/about/). undated. Coal products. Access: PUBLIC_PRIMARY_TEXT.

32. ACCC public register. [Callide joint coal purchasing submission](https://www.accc.gov.au/system/files/public-registers/documents/D06%2B58398.pdf). 2006. Paragraph 12.5. Access: PUBLIC_PRIMARY_TEXT.

33. Downer / NZX. [Downer awarded Commodore contract](https://www.nzx.com/announcements/323414). 2018-09-05. Contract announcement. Access: PUBLIC_PRIMARY_TEXT.

34. BUMA Australia. [Commodore project](https://buma.com.au/project/commodore/). undated. Project description. Access: PUBLIC_PRIMARY_TEXT.

35. Queensland Government; Minedocs reproduction. [Queensland Coals, 14th edition](https://minedocs.com/22/Queensland_Coals-Other-2003.pdf). 2003. Table 4, PDF p.8. Access: PUBLICATION_REPRODUCTION.

36. AGL. [Loy Yang site visit webcast transcript](https://www.agl.com.au/content/dam/digital/agl/documents/about-agl/investors/2018/20181023-transcript-from-webcast-loy-yang.pdf). 2018-10-23. PDF p.5, exchange at lines 206-209. Access: PUBLIC_PRIMARY_TEXT.

37. ACIL / Queensland Competition Authority. [Calculation of energy costs in BRCI 2010-11](https://www.qca.org.au/wp-content/uploads/2019/05/11873_ACIL-Final-Report-Calculation-of-Energy-Costs-in-the-BRCI-for-2010-11-4.pdf). 2010. Brown coal assumptions table. Access: PUBLIC_PRIMARY_TEXT.

38. Victorian legislation / AustLII. [Loy Yang B Act 1992, Schedule 1](https://classic.austlii.edu.au/au/legis/vic/consol_act/lyba1992114/sch1.html). 1992. Coal supply agreement definition. Access: PUBLIC_LEGISLATION_REPRODUCTION.

39. CIMIC / HOCHTIEF. [Thiess awarded Yallourn mining extension](https://www.hochtief.com/news-media/press-releases/press-release/cimics-thiess-awarded-195-million-yallourn-mining-extension-1). 2017-06-01. Contract announcement. Access: PUBLIC_PRIMARY_TEXT.

40. CLP. [Yallourn power station and mine](https://www.clpgroup.com/en/about/our-business/assets-and-services/australia/yallourn-coal-fired-power-station-and-brown-coal-open-cut-mine.html). undated. Asset overview. Access: PUBLIC_PRIMARY_TEXT.

41. Supreme Court of Queensland, CaseChat reproduction. [GPS Power v CS Energy [2018] QSC 294](https://www.casechat.au/cases/au/gps-power-pty-ltd-v-cs-energy-ltd-2). 2018. IPPA clause 23 and coal arrangements. Access: INDEXED_JUDGMENT_REPRODUCTION.

42. Queensland Court of Appeal, CaseChat reproduction. [CS Energy v GPS Power [2021] QCA 194](https://casechat.au/cases/au/cs-energy-limited-v-gps-power-pty-limited). 2021. Coal stockpile/IPPA dispute. Access: INDEXED_JUDGMENT_REPRODUCTION.

43. CS Energy. [Annual Report 2025](https://www.csenergy.com.au/ArticleDocuments/191/CS%20ENERGY%20ANNUAL%20REPORT%202025%20FULL%20COLOUR%2020250926.pdf.aspx). 2025-09-26. Fuel expense and Gladstone onerous contract notes. Access: PRIMARY_PDF_DOWNLOADED.

44. ACIL Allen / AEMO. [2024 fuel price forecast report](https://aemo.com.au/-/media/files/major-publications/isp/2025/acil-allen-2024-fuel-price-forecast-report.pdf). 2025-02-25. p.33 and Appendix C. Access: PUBLIC_PRIMARY_TEXT.

45. ABS. [Consumer Price Index, June quarter 2025](https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/jun-quarter-2025). 2025-07-30. All groups, weighted average eight capitals. Access: PUBLIC_PRIMARY_TEXT.

46. ABS. [Consumer Price Index, September quarter 2016](https://www.abs.gov.au/ausstats/abs@.nsf/7d12b0f6763c78caca257061001cc588/7c3192fae31616f9ca2580b20076cf0f!OpenDocument). 2016. All groups, weighted average eight capitals. Access: PUBLIC_PRIMARY_TEXT.

47. David Hardidge / Australian Treasury host. [Submission discussing CPI indexation](https://treasury.gov.au/sites/default/files/2019-04/c2019-t342318-david_hardidge.pdf). 2019. Historical CPI series. Access: PUBLIC_SECONDARY_DOCUMENT.

