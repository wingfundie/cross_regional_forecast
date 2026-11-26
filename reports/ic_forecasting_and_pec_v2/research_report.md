# Interconnector Forecasting Verdict, Clustering, and Project EnergyConnect (v2)

## Executive Overview and Reader Guide

Flagship Editions A and B dissected two years of historical constraint pressure, generator influence, and transmission-outage risk across the existing six-interconnector National Electricity Market. Flagship Edition C confronts the two forward-looking structural questions that determine how trading desks and quantitative teams deploy those findings over the next five years: first, how the commissioning of Project EnergyConnect (`NSW1-SA1`) reshapes southern-ring constraint coupling and Settlement Residue Auction (SRA) payouts under the Australian Energy Market Commission's `ERC0386` loop settlement rule; and second, where genuine issue-time interconnector predictability ends across intraday, short-term, and 1-to-90-day horizons.

This edition bridges 15,264 five-minute intervals of observed EnergyConnect commissioning telemetry (1 October to 23 November 2026) directly into the repository's exact `ERC0386` loop settlement engine across four capacity regimes (0 MW pre-EnergyConnect, observed 150 MW commissioning, observed 350 MW testing, and 800 MW Stage 2 full rating); audits 48,336 Predispatch and 17,808 ST PASA EnergyConnect forecasts; visualises all 50 long-range MT PASA horizon bands (10 of 10 historical cells retaining the baseline); synthesises 241 seven-day block-bootstrap clustering evaluations (0 of 241 surviving Holm-Bonferroni correction); and enforces strict governance boundaries across the repository's three distinct model stacks.

## Chapter 1 · Project EnergyConnect Commissioning Physics and Southern-Ring Coupling

For more than two decades, the southern mainland National Electricity Market operated as a radial chain: Victoria sat in the middle, connected northward to New South Wales via VNI and westward to South Australia via Heywood and Murraylink. Power could not flow directly between New South Wales and South Australia without crossing Victoria. Project EnergyConnect (`NSW1-SA1`), the 330 kV interconnector linking Robertstown and Bundey in South Australia to Buronga and Wagga in south-western New South Wales, closes that radial chain into a three-region alternating-current loop.

During early planning, market commentary often treated EnergyConnect as a clean 800 MW bilateral pipe that would jump directly from zero to full nameplate capacity on energisation. The actual five-minute dispatch record logged between 1 October and 23 November 2026 (15,264 five-minute dispatch intervals, or 2,544 half-hours in fixed NEM time UTC+10) reveals a far more intricate reality: staged commissioning envelopes (0 MW, 150 MW, and 350 MW), frequent forced-negative directional limits, high tight-headroom occupancy, and immediate physical coupling with the exact same thermal and stability equations that bind VNI and Heywood.

> [!TAKEAWAY] Core Operational Finding on EnergyConnect Commissioning
> Observed EnergyConnect limits are neither static nameplate caps nor electrically independent of VNI and Heywood. Across 15,264 five-minute commissioning intervals, directional headroom sat at or below 50 MW in 50.8% of NSW to SA intervals and 63.4% of SA to NSW intervals, while shared VNI and Southern NSW constraint equations directly set 31.2% of all SA to NSW bounds.

### 1.1 Observed commissioning regimes: 150 MW, 350 MW, and zero-transfer lockouts

Grouping the 2,544 half-hourly commissioning intervals by active AEMO configuration reveals four distinct operational states over the 53-day observed record.

| Commissioning regime | Half-hours (hours) | Time share (%) | NSW to SA tight median (P05 / P95 MW) | SA to NSW tight median (P05 / P95 MW) | Mean \|flow\| (P95 \|flow\| MW) | Empirical utilisation ratio | Forced neg. NSW to SA (%) | Forced neg. SA to NSW (%) | Leading forward / reverse setter |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 150 MW commissioning | 1,351 (675.5) | 53.1% | 150 (-57 / 150) | 115 (-147 / 150) | 77.4 (140.8) | 79.4% | 10.5% | 33.1% | `NS_150_DYN_TEST` / `SN_150_DYN_TEST` |
| 350 MW testing | 900 (450.0) | 35.4% | 100 (-350 / 350) | 196 (-350 / 350) | 213.7 (347.6) | 86.4% | 35.1% | 41.7% | `N^^N_NIL_LTWG` / `SN_350_DYN_TEST` |
| Zero-transfer (0 MW) | 237 (118.5) | 9.3% | 0 (0 / 0) | 0 (0 / 0) | 0.0 (0.0) | 0.0% | 0.0% | 0.0% | `NS_ZERO` / `SN_ZERO` |
| Transition / Mixed | 56 (28.0) | 2.2% | 0 (-2 / 0) | 0 (0 / 0) | 0.8 (0.0) | 0.0% | 17.9% | 28.6% | `NS_ZERO` / `SN_ZERO` |

Three physical signatures stand out immediately from the observed commissioning panel:

1. **High physical utilisation whenever the corridor is open (79.4% to 86.4%):** Whenever EnergyConnect was cleared to operate under its 150 MW commissioning envelope (53.1% of half-hours), realised dispatch flows reached a P95 magnitude of 140.8 MW with a median utilisation ratio of 79.4% of active positive ceiling. Once AEMO stepped testing up to 350 MW (35.4% of half-hours), mean absolute flow nearly tripled from 77.4 MW to 213.7 MW, P95 magnitude reached 347.6 MW (hitting the exact 350.0 MW ceiling), and median utilisation climbed to 86.4%. Regional price spreads between New South Wales and South Australia immediately pulled flow across the new link at near-full allowable utilisation.
2. **Escalating from 150 MW to 350 MW shifts the binding bottleneck onto existing AC spines:** Look closely at the `NSW to SA` tight median limit under `350 MW testing`: even though the commissioning test cap rose from 150 MW to 350 MW, the median half-hour tight NSW to SA limit actually dropped from 150 MW down to 100 MW, and forced-negative forward limits jumped from 10.5% to 35.1% (with P05 hitting -350 MW). The leading forward setter column explains why: once the 150 MW test cap lifts to 350 MW, EnergyConnect immediately hits the existing Southern NSW voltage stability boundary `N^^N_NIL_LTWG` (Lower Tumut to Wagga 330 kV), exposing the exact southern-ring AC bottlenecks documented in Flagship Edition A.
3. **One in ten commissioning hours sits locked at zero transfer:** Across the 53-day observation window, 9.3% of half-hours (118.5 hours) were locked under `NS_ZERO` / `SN_ZERO` during staged switching, line outages (such as Buronga-Bundey `6F` or Wagga-Darlington Point `6C` circuits), and test handovers, plus another 2.2% in intra-half-hour transitions.

### 1.2 Southern-ring equation taxonomy: proving the three-link triangle

Auditing the exact reported export and import setter equations across all 15,264 five-minute dispatch intervals quantifies how deeply EnergyConnect is already interlocked with VNI and Heywood.

| Ring equation category | NSW to SA intervals (share %) | NSW to SA top equations | SA to NSW intervals (share %) | SA to NSW top equations |
|---|---:|---|---:|---|
| PEC Commissioning / Test Cap | 6,899 (45.2%) | `NS_150_DYN_TEST` (4,997), `NS_350_DYN_TEST` (1,466) | 6,733 (44.1%) | `SN_150_DYN_TEST` (4,126), `SN_350_DYN_TEST` (2,428) |
| VNI / Southern NSW Ring | 2,040 (13.4%) | `N^^N_NIL_LTWG` (2,017), `N>>NIL_BUTX_BUTX_LV` (23) | 4,763 (31.2%) | `N>>NIL_060_051` (1,365), `N>>6CGH_060_051` (1,343) |
| Heywood / VIC-SA Ring | 1,948 (12.8%) | `V_S_6CGH_SA_UFLS` (1,631), `V_S_6CGH_ROCOF` (317) | 1,037 (6.8%) | `V^^V_6CGH_KGTS` (681), `V^^V_NIL_KGTS` (302) |
| PEC Zero-Transfer Lock | 1,686 (11.0%) | `NS_ZERO` (1,686) | 1,771 (11.6%) | `SN_ZERO` (1,771) |
| SA Internal Thermal | 1,386 (9.1%) | `S>>BWMP_TWPA_TPRS` (620), `S>>NIL_TWPA_TPRS` (320) | 0 (0.0%) | None |
| Other Generic Constraint | 722 (4.7%) | `NS_100_DYN` (150), `NS_100` (133) | 876 (5.7%) | `V>>N_NIL_65_051` (225), `S:VN_700_TEST` (143) |
| Negative Residue Management | 583 (3.8%) | `NRM_NSW1_SA1` (583) | 84 (0.6%) | `NRM_SA1_NSW1` (84) |

This equation taxonomy provides direct five-minute proof of physical southern-ring interdependence:

- **On SA to NSW (eastward flow into New South Wales), nearly one-third (31.2%) of all intervals are set by VNI / Southern NSW constraints:** The single largest non-test reverse setter on EnergyConnect is `N>>NIL_060_051` (1,365 intervals) alongside its outage twin `N>>6CGH_060_051` (1,343 intervals), the exact Jindera to Wodonga 330 kV thermal constraint on trip of Wagga to Lower Tumut (051) that ranked as the top shadow-rent equation on VNI in Flagship Edition A ($267.6k/MW across 17,567 binding intervals). Because power arriving from South Australia via Buronga and Darlington Point merges into the Wagga 330 kV hub alongside VNI flow, EnergyConnect eastward exports compete directly with Victorian VNI exports for the exact same Southern NSW thermal corridor.
- **On NSW to SA (westward flow into South Australia), 12.8% of intervals are set by Heywood / SA under-frequency and ROCOF islanding bounds:** Equations `V_S_6CGH_SA_UFLS` (1,631 intervals) and `V_S_6CGH_ROCOF` (317 intervals) co-constrain combined imports into South Australia across Heywood, Murraylink, and EnergyConnect, while SA internal 275 kV thermal equations (`S>>BWMP_TWPA_TPRS`, 620 intervals) add another 9.1%. Meanwhile, `NRM_NSW1_SA1` already intervened in 583 intervals (3.8%) during commissioning to clamp counter-price negative residues on the new link.

### 1.3 Worked five-minute southern-ring coupling mechanics and forced-negative limits

Why does raising EnergyConnect's commissioning ceiling from 150 MW to 350 MW cause the median tight `NSW to SA` limit to drop from 150 MW to 100 MW while forced-negative intervals triple from 10.5% to 35.1%? Tracing the linearised AC power-flow mechanics inside AEMO's dispatch engine clarifies the exact physical chain.

Consider a sunny spring afternoon in Victoria and South Australia when south-western NSW solar farms (Darlington Point, Limondale, Sunraysia, and Coleambally) are generating near nameplate while South Australia is simultaneously exporting surplus wind and solar eastward. Two coupled constraints govern the Wagga 330 kV junction:

1. **Eastward thermal competition at Wagga (`N>>NIL_060_051`):** Both northward VNI flow ($F_{\text{VN}} > 0$) and eastward EnergyConnect flow ($F_{\text{SN}} = -F_{\text{NS}} > 0$) inject power into the southern NSW 330 kV network that must traverse the Jindera, Wagga, and Lower Tumut lines northward toward Sydney. In AEMO's linearised generic constraint formulation, the LHS combines both interconnectors plus local solar output with positive shift factors:
   $$\alpha_{\text{VN}} F_{\text{VN}} + \alpha_{\text{SN}} (-F_{\text{NS}}) + \sum_{g \in \text{SW-NSW}} \beta_g P_g \le \text{RHS}_{060\_051}$$
   When VNI is already pushing +700 MW northward and south-western NSW solar generators fill the remaining thermal margin, the residual RHS available for EnergyConnect eastward flow shrinks rapidly below the 350 MW test envelope. Under the 150 MW regime, `SN_150_DYN_TEST` masked this network ceiling most of the time; once AEMO raised the test cap to 350 MW, `N>>NIL_060_051` and `N>>6CGH_060_051` immediately surfaced as the binding physical cap in 31.2% of all SA to NSW intervals.
2. **Voltage stability and forced-negative westward limits (`N^^N_NIL_LTWG`):** In the opposite direction, `N^^N_NIL_LTWG` protects voltage stability along the Lower Tumut to Wagga 330 kV corridor. When regional dispatch pushes heavy westward transfers from Snowy and Southern NSW toward South Australia alongside low synchronous reactive support at Wagga, the voltage-stability LHS forces net flow across the Wagga interface *eastward* (from SA into NSW) to maintain acceptable voltage margins. In directional limit reporting, an export limit of `EXPORTLIMIT < 0` on `NSW1-SA1` (reaching `-350 MW` at P05 during 350 MW testing) does not mean the physical wire broke; it means the dispatch engine requires EnergyConnect to import at least `|EXPORTLIMIT|` megawatts from South Australia into New South Wales to hold the voltage boundary.

From a desk risk perspective, treating forced-negative limits as zeros or clamping directional bounds at `max(limit, 0)` destroys the exact signal that predicts counter-price loop flows. When `EXPORTLIMIT` drops to `-200 MW` on `NSW1-SA1` while South Australia prices exceed New South Wales prices, EnergyConnect is physically forced to flow counter-price from the expensive region into the cheaper region, triggering `NRM_NSW1_SA1` interventions (observed in 583 intervals) and compressing southern-ring settlement residues.

### 1.4 Why southern-ring coupling changes SRA settlement rules

Because VNI, Heywood, and EnergyConnect now share the exact same binding thermal, voltage, and frequency constraints inside a closed three-region triangle, loop flows can simultaneously generate positive residue on two arms and negative residue on the third. To handle that physical loop cleanly without bankrupting individual interconnector settlement buckets, the Australian Energy Market Commission issued its final `ERC0386` net-trade loop settlement rule on 25 September 2025. Chapter 2 feeds these exact observed EnergyConnect commissioning profiles directly into the repository's verified `ERC0386` engine to quantify how southern-ring SRA payouts reallocate from 0 MW through 800 MW.

## Chapter 2 · Bridging Observed EnergyConnect Commissioning into AEMC ERC0386 Loop Settlement

Prior internal valuation research (`Interregional Valuation Research v3`) implemented the AEMC's `ERC0386` net-trade loop settlement rule on historical 2021 to 2026 dispatch data where physical flow on the New South Wales to South Australia arm was identically zero ($F_{\text{NS}} = 0$). While that pre-EnergyConnect counterfactual revealed the pass-through net-trade reallocation mechanism, trading desks preparing Settlement Residue Auction bids for 2027 and beyond need to know how the six southern-ring SRA buckets evolve as EnergyConnect actually ramps across its observed commissioning ceilings (150 MW and 350 MW) toward its Stage 2 full 800 MW rating.

This chapter bridges Chapter 1's observed EnergyConnect commissioning telemetry directly into the exact `ERC0386` loop settlement engine over the full 24-month southern-ring market panel (1 September 2024 to 31 August 2026, 210,240 five-minute intervals across NSW1, VIC1, SA1, VNI, and pooled Heywood plus Murraylink).

### 2.1 Counterfactual design and explicit fixed-price qualification

To isolate the pure accounting and reallocation mechanics of the `ERC0386` loop rule across EnergyConnect capacity steps without inventing an unverified security-constrained optimal power flow (SCOPF) redispatch model, we run a transparent historical-price counterfactual holding regional clearing prices and pre-existing VNI and Heywood+Murraylink dispatch flows fixed. Across each five-minute interval $t$, let $\Delta \pi_{\text{NS},t} = \pi_{\text{SA1},t} - \pi_{\text{NSW1},t}$ be the observed regional price spread across the new border. For each capacity regime $(C_{\text{fwd}}, C_{\text{rev}}, u)$ calibrated to Chapter 1's observed empirical ceilings and median utilisation ratios ($u_{150} = 79.4\%$, $u_{350} = 86.4\%$), counterfactual EnergyConnect dispatch flow is modelled smoothly as a price-responsive economic transfer capped strictly by the observed commissioning ceiling:

$$F_{\text{NS},t} = \begin{cases} \tanh\left(\Delta \pi_{\text{NS},t} / 35\right) \cdot C_{\text{fwd}} \cdot u, & \Delta \pi_{\text{NS},t} \ge 0 \\ \tanh\left(\Delta \pi_{\text{NS},t} / 35\right) \cdot C_{\text{rev}} \cdot u, & \Delta \pi_{\text{NS},t} < 0 \end{cases}$$

> [!WARNING] Fixed-Price Counterfactual Upper-Bound Qualification
> Because this stress test holds historical 2024 to 2026 regional clearing prices fixed, adding 150 MW, 350 MW, or 800 MW of price-responsive NSW to SA transfer does not endogenously compress the NSW minus SA price spread. In live dispatch, larger physical transfers compress regional price differentials, reducing total loop dollars below the fixed-price total. These results should therefore be read as an exact accounting map of relative bucket reallocation, negative-residue loop netting, and upper-bound gross residue scaling rather than a full redispatch price forecast.

### 2.2 Six-bucket ERC0386 loop settlement ledger across four EnergyConnect regimes

Feeding all four regimes through the repository's verified `ERC0386` net-trade engine yields exact 24-month totals (AUD millions) for every single southern-ring directional SRA bucket alongside status-quo positive IRSR and negative net-loop deficits.

| EnergyConnect regime | Mean \|F_NS\| (MW) | Status-quo pos. IRSR ($m) | ERC0386 net-trade payout ($m) | Negative net-loop deficit ($m) | VIC to NSW ($m) | NSW to VIC ($m) | VIC to SA ($m) | SA to VIC ($m) | NSW to SA ($m) | SA to NSW ($m) | PEC arm share of loop (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Pre-PEC (0 MW baseline) | 0.0 | $528.1 | $519.1 | -$126.8 | $210.6 | $21.6 | $156.3 | $11.9 | $53.8 | $65.1 | 22.9% |
| Observed 150 MW commissioning | 69.1 | $671.7 | $629.8 | -$93.8 | $222.8 | $24.3 | $177.7 | $14.0 | $86.4 | $104.7 | 30.3% |
| Observed 350 MW testing | 175.4 | $892.7 | $814.4 | -$57.5 | $237.2 | $26.9 | $201.4 | $16.8 | $149.3 | $182.8 | 40.8% |
| Stage 2 full-rated (800 MW) | 401.0 | $1,361.6 | $1,244.9 | -$19.0 | $248.8 | $27.8 | $223.5 | $20.7 | $316.1 | $407.8 | 58.2% |

Four commercially decisive results emerge from the loop settlement bridge:

1. **Even before a single megawatt flows physically on EnergyConnect, ERC0386 transfers 22.9% of southern-ring payouts to the NSW-SA arm:** Under the Pre-PEC (`0 MW`) baseline, status-quo settlement pays $267.3m to VIC to NSW, $39.2m to NSW to VIC, $196.4m to VIC to SA, $25.2m to SA to VIC, and $0 to NSW-SA (total positive status-quo IRSR $528.1m). Simply activating the AEMC `ERC0386` net-trade rule at zero physical PEC flow redistributes $118.8m (22.9%) into `NSW to SA` ($53.8m) and `SA to NSW` ($65.1m) whenever Victoria acts as a transit node passing power between New South Wales and South Australia, pulling `VIC to NSW` down from $267.3m to $210.6m (-21.2%) and `VIC to SA` down from $196.4m to $156.3m (-20.4%).
2. **Observed 150 MW and 350 MW commissioning flows expand total loop payouts while absorbing negative residues:** At observed 150 MW commissioning (mean `|F_NS| = 69.1 MW`), total 24-month ERC0386 payout rises from $519.1m to $629.8m ($315.1m/yr), and EnergyConnect's arm share climbs from 22.9% to 30.3% ($86.4m NSW to SA plus $104.7m SA to NSW). Stepping up to observed 350 MW testing (mean `|F_NS| = 175.4 MW`) pushes total payout to $814.4m ($407.5m/yr) and lifts EnergyConnect's arm share to 40.8% ($149.3m NSW to SA plus $182.8m SA to NSW). Under the parametric 800 MW Stage 2 upper bound (mean `|F_NS| = 401.0 MW`), EnergyConnect captures 58.2% of the entire southern-ring net-trade pool ($316.1m NSW to SA plus $407.8m SA to NSW).
3. **With-price EnergyConnect flow sharply shrinks net-loop negative-residue deficits:** One of the subtle benefits of AEMC's loop netting appears directly in the `Negative net-loop deficit` column. At 0 MW, the southern ring logged -$126.8m of five-minute intervals where combined VNI plus Heywood net loop residue was negative (paying zero to SRD units and passing the deficit to Transmission Network Service Providers). Adding with-price EnergyConnect transfers offsets counter-price VNI/Heywood losses inside the same five-minute interval, cutting total negative net-loop deficits by 26% at 150 MW (-$93.8m), by 55% at 350 MW (-$57.5m), and by 85% at 800 MW (-$19.0m).
4. **Why VIC to NSW and VIC to SA payouts recover inside the fixed-price loop:** Look closely at `VIC to NSW` ($210.6m at 0 MW rising to $237.2m at 350 MW) and `VIC to SA` ($156.3m at 0 MW rising to $201.4m at 350 MW). Under fixed regional prices, because with-price PEC flows shrink the intervals where negative VNI or Heywood residues wipe out the net loop pool, existing VNI and Heywood SRA buckets actually recover part of their lost loop-netting dilution as PEC scales up, even while PEC's relative share of the expanding pie grows from 22.9% to 40.8%. In live markets, however, spread compression across the SA-NSW border will push absolute VNI and Heywood dollars lower than this fixed-price ceiling, making active tracking of EnergyConnect's directional limits essential for pricing all six loop buckets.

### 2.3 Worked five-minute ERC0386 accounting examples under 350 MW testing

To make the AEMC net-trade rule concrete for desk implementation, compare two evening intervals under 350 MW testing where regional clearing prices sit identically at $\pi_{\text{VIC1}} = \$60/\text{MWh}$, $\pi_{\text{NSW1}} = \$160/\text{MWh}$, and $\pi_{\text{SA1}} = \$320/\text{MWh}$, while the relative flow balance between VNI and EnergyConnect shifts:

**Case A (Victoria is the sole net exporter; NSW remains a net importer):** Suppose physical flows clear at $F_{\text{VN}} = +500\text{ MW}$ (VIC to NSW), $F_{\text{VS}} = +300\text{ MW}$ (VIC to SA), and $F_{\text{NS}} = +300\text{ MW}$ (NSW to SA).
- Step 1 (Signed arm IRSR allocations per 5-min interval): VNI earns $500 \times (160 - 60)/12 = \$4,167$; Heywood+Murraylink earns $300 \times (320 - 60)/12 = \$6,500$; EnergyConnect earns $300 \times (320 - 160)/12 = \$4,000$. Net loop IRSR equals $\$14,667$.
- Step 2 (Net regional export positions): Victoria exports $E_{\text{VIC}} = +500 + 300 = +800\text{ MW}$; New South Wales imports $E_{\text{NSW}} = 300 - 500 = -200\text{ MW}$; South Australia imports $E_{\text{SA}} = -300 - 300 = -600\text{ MW}$.
- Step 3 (Net-trade allocation under one exporter, two importers): Because only Victoria is a net exporter, net trade links VIC to NSW (quantity $200\text{ MW}$, Step-1 amount $200 \times 100 = 20,000$) and VIC to SA (quantity $600\text{ MW}$, Step-1 amount $600 \times 260 = 156,000$), while the NSW to SA arm links two net importers and receives zero Step-1 amount in this particular interval. The entire $\$14,667$ net loop IRSR is distributed proportionally across `VIC to NSW` ($\$1,667$) and `VIC to SA` ($\$13,000$).

**Case B (VNI binds down to 200 MW; NSW flips to a net exporter):** Now suppose a Southern NSW thermal constraint (`N>>NIL_060_051`) trims VNI northward flow from $+500\text{ MW}$ to $+200\text{ MW}$, while Heywood holds $+300\text{ MW}$ and EnergyConnect pushes $+350\text{ MW}$ westward from NSW to SA.
- Step 1 (Signed arm IRSR allocations): VNI earns $200 \times 100 / 12 = \$1,667$; Heywood+Murraylink earns $300 \times 260 / 12 = \$6,500$; EnergyConnect earns $350 \times 160 / 12 = \$4,667$. Total net loop IRSR equals $\$12,833$.
- Step 2 (Net regional export positions): Victoria exports $E_{\text{VIC}} = +200 + 300 = +500\text{ MW}$; New South Wales flips to a net exporter at $E_{\text{NSW}} = 350 - 200 = +150\text{ MW}$; South Australia is the sole net importer at $E_{\text{SA}} = -300 - 350 = -650\text{ MW}$.
- Step 3 (Net-trade allocation under two exporters, one importer): Because South Australia is now the sole net importer, `VIC to NSW` drops to zero Step-1 allocation (both are exporters). Net trade links `VIC to SA` (quantity $500\text{ MW}$, Step-1 amount $500 \times 260 = 130,000$) and `NSW to SA` (quantity $150\text{ MW}$, Step-1 amount $150 \times 160 = 24,000$). Dividing $\$12,833$ proportionally assigns $\$10,833$ (84.4%) to `VIC to SA` and $\$2,000$ (15.6%) to `NSW to SA`, while `VIC to NSW` collects zero even though 200 MW flowed northward on VNI at a $\$100/\text{MWh}$ spread.

### 2.4 Commercial implications for southern-ring SRA portfolio construction

Comparing Cases A and B demonstrates why southern-ring SRA valuation under `ERC0386` can no longer be performed one interconnector at a time:

1. **Payout discontinuity at the net-export zero crossing:** Whenever New South Wales crosses from net importer ($F_{\text{NS}} < F_{\text{VN}}$) to net exporter ($F_{\text{NS}} > F_{\text{VN}}$), settlement dollars shift abruptly between the `VIC to NSW` and `NSW to SA` buckets. Similarly, whenever South Australia exports surplus midday solar simultaneously into Victoria and New South Wales, `SA to NSW` captures substantial payout share even when EnergyConnect itself is capped at 150 MW or 350 MW.
2. **Hedging Victoria-to-SA and Victoria-to-NSW books requires a multi-arm basket:** A retailer hedging NSW load with `VIC to NSW` SRA units previously suffered only from VNI outages and counter-price clamping. Under `ERC0386` and EnergyConnect, a third basis risk enters: during high-SA-price evenings, VNI constraints that flip NSW into a net exporter divert VNI's bilateral residue into the `NSW to SA` and `VIC to SA` buckets. Holding a partial sleeve of `NSW to SA` and `SA to NSW` units alongside legacy VNI and Heywood holdings restores hedge completeness across the closed three-region triangle.
3. **Why issue-time directional limit forecasts matter for valuation:** Because the exact net-export sign of every region depends on whether `NSW1-SA1` clears at 0 MW, 150 MW, 350 MW, or -350 MW, trading desks need an honest audit of how accurately Predispatch, ST PASA, and statistical challengers actually forecast EnergyConnect's tight limits. Chapter 3 audits all 66,144 issue-time forecasts logged during the commissioning window.

## Chapter 3 · Issue-Time Forecasting Audit on Project EnergyConnect

EnergyConnect provides a rare natural laboratory for testing genuine issue-time interconnector limit forecasting: every Predispatch and Short-Term PASA (ST PASA) vintage was archived strictly as published, preserving exact issue times, anchor timestamps, and AEMO's own forecast limits alongside observed five-minute tight half-hour targets (`nsw_sa_tight` and `sa_nsw_tight`, defined strictly as the minimum across the six five-minute dispatch intervals). Across 48,336 Predispatch forecast rows and 17,808 ST PASA rows (1 October to 23 November 2026), five distinct models were evaluated on identical as-of rows: `Persistence` (holding the latest pre-issue tight limit), `Delivery-Period Baseline` (time-of-day historical benchmark), `AEMO Issued Forecast` (official Predispatch or ST PASA interconnector limit), `Regional Forecast` (statistical model using issued regional demand/VRE forecasts), and `Regional + Constraints` (adding forecast constraint RHS and binding indicators).

### 3.1 Predispatch and ST PASA accuracy across directions and lead bands

| Product & direction | Lead band | Best model (MAE MW) | Persistence MAE (MW) | Delivery-Period MAE (MW) | AEMO Issued MAE (MW) | Regional + Constraints MAE (MW) | Best skill vs Persistence (%) |
|---|---|---|---:|---:|---:|---:|---:|
| Predispatch · NSW to SA | Intraday | Persistence (100.9) | 100.9 | 117.9 | 140.9 | 179.4 | 0.0% |
| Predispatch · NSW to SA | 6-24h | Delivery-Period (127.5) | 144.8 | 127.5 | 181.8 | n/a | +11.9% |
| Predispatch · NSW to SA | Day 2-3 | Delivery-Period (122.7) | 134.0 | 122.7 | n/a | n/a | +8.4% |
| Predispatch · NSW to SA | Day 4-7 | Delivery-Period (129.7) | 141.5 | 129.7 | n/a | n/a | +8.3% |
| Predispatch · SA to NSW | Intraday | Delivery-Period (109.3) | 121.4 | 109.3 | 109.8 | 140.9 | +9.9% |
| Predispatch · SA to NSW | 6-24h | Delivery-Period (104.6) | 234.1 | 104.6 | 106.3 | n/a | +55.3% |
| ST PASA · NSW to SA | 6-24h | AEMO Issued (105.5) | 144.8 | 127.5 | 105.5 | n/a | +27.1% |
| ST PASA · NSW to SA | Day 2-3 | Delivery-Period (122.7) | 134.0 | 122.7 | 130.5 | 153.6 | +8.4% |
| ST PASA · NSW to SA | Day 4-7 | Delivery-Period (129.7) | 141.5 | 129.7 | 137.2 | 205.5 | +8.3% |
| ST PASA · SA to NSW | 6-24h | AEMO Issued (93.3) | 234.1 | 104.6 | 93.3 | n/a | +60.1% |
| ST PASA · SA to NSW | Day 2-3 | AEMO Issued (95.2) | 223.9 | 113.0 | 95.2 | 154.4 | +57.5% |
| ST PASA · SA to NSW | Day 4-7 | AEMO Issued (98.1) | 232.8 | 117.8 | 98.1 | 209.1 | +57.8% |

Three sharp, counter-intuitive lessons emerge directly from this issue-time audit:

1. **AEMO ST PASA delivers strong multi-day accuracy on SA to NSW reverse limits (+57.5% to +60.1% skill over persistence):** Because SA to NSW persistence suffers severe diurnal swings (MAE 223.9 to 234.1 MW across 6-24h through day 4-7 as daytime solar pushes reverse limits down and nighttime relieves them), AEMO's official ST PASA solver cuts MAE cleanly down to 93.3 to 98.1 MW across all multi-day bands, outperforming both Delivery-Period baselines (104.6 to 117.8 MW) and statistical challengers (154.4 to 209.1 MW). Even on NSW to SA at 6-24h, AEMO ST PASA leads all models at 105.5 MW (+27.1% vs persistence).
2. **Simple baselines beat statistical regressions during discrete commissioning step-changes:** Across every single Predispatch and ST PASA cell where `Regional Forecast` and `Regional + Constraints` were scored, both statistical models lost decisively to `Persistence`, `Delivery-Period Baseline`, and `AEMO Issued Forecast` (for example, 179.4 MW vs 100.9 MW on intraday NSW to SA, and 205.5 MW vs 129.7 MW on ST PASA day 4-7). That negative result is one of the most informative lessons in the entire repository: during an active 53-day commissioning programme where AEMO steps the corridor discretely across `0 MW`, `150 MW`, and `350 MW` testing regimes, complex regression weights fitted on last week's 150 MW regime systematically overfit and extrapolate poorly the morning AEMO switches to 350 MW or locks the line to 0 MW.
3. **Intraday Predispatch AEMO limits lag simple persistence on NSW to SA (140.9 MW vs 100.9 MW):** Why did intraday Predispatch AEMO limits lose to persistence on NSW to SA? Because during staged commissioning tests, intraday discretionary caps (`NS_150_DYN_TEST`, `NS_350_DYN_TEST`, `NRM_NSW1_SA1`, and forced negative voltage stability bounds `N^^N_NIL_LTWG`) often enter the live five-minute dispatch engine faster than Predispatch updates propagate across all 48 half-hours, giving latest-observed `own_anchor` persistence a temporary short-horizon edge.

### 3.2 Severe prediction-interval under-coverage during regime transitions

Checking empirical interval coverage against the nominal 80% target exposes an equally important risk-management warning.

Across Predispatch lead bands, empirical interval coverage sits far below 80% for every single model: `Delivery-Period Baseline` reaches just 44.8% to 57.2%, `Persistence` reaches 34.8% to 53.5%, and `Regional + Constraints` collapses to 15.0% to 45.9% at day 2-7 horizons under ST PASA. Whenever an interconnector undergoes structural commissioning step-changes (jumping 150 MW or 200 MW overnight upon test-stage sign-off), rolling residual radii estimated on pre-transition history systematically understate real uncertainty.

### 3.3 Anatomy of a commissioning step-change miss and live desk playbook

To understand why `Regional + Constraints` lost by 78.5 MW on intraday NSW to SA (179.4 MW vs 100.9 MW) and by 111.0 MW on day 4-7 SA to NSW (209.1 MW vs 98.1 MW), trace what happens inside a chronological walk-forward regression across a commissioning step date.

During Weeks 1 through 4 of the observation window, EnergyConnect sat primarily inside the `150 MW commissioning` envelope (`NS_150_DYN_TEST` and `SN_150_DYN_TEST`), interspersed with `NS_ZERO` outage blocks. Any regression trained strictly on pre-origin history observes a bounded target capped at +150 MW and assigns non-zero slopes to issued SA solar, NSW demand, and forecast constraint RHS variables to explain intraday variation between -100 MW and +150 MW. The morning AEMO approves the `350 MW testing` step, two things break simultaneously:
- **Linear and tree extrapolation fails across unseen regime caps:** Tree models (`GBDT`) cannot extrapolate above the maximum target observed in training (+150 MW), capping their predictions at 150 MW on days when realised tight limits reach 350 MW (an instant 200 MW bias). Linear/ridge models extrapolate the RHS slope linearly, often overshooting wildly into +450 MW or -400 MW when a new `350_DYN_TEST` equation replaces `150_DYN_TEST`.
- **AEMO's ST PASA solver natively knows the scheduled test step:** Unlike a statistical model that has to infer structural regime changes backward from realised lags, AEMO's ST PASA engine incorporates the scheduled commissioning constraint set (`SN_350_DYN_TEST`, `N>>6CGH_060_051`, and booked `6F`/`6C` outage constraints) directly into its forward optimisation. That structural information advantage explains why ST PASA holds 93.3 to 98.1 MW MAE across Days 1 through 7 on SA to NSW while every statistical challenger deteriorates beyond 150 MW.

Until EnergyConnect completes Stage 2 commissioning and accumulates at least one full four-season steady-state dispatch year, trading desks should route short-horizon reference bounds strictly according to the empirical hierarchy below:

| Direction | Forecast horizon | Recommended desk reference | Audited MAE (MW) | Why it leads during commissioning |
|---|---|---|---|---|
| NSW to SA | Intraday (0-6h) | Latest-anchor Persistence | 100.9 | Captures live `NS_ZERO`, `NRM`, and `LTWG` shifts before Predispatch catches up |
| NSW to SA | 6-24h | AEMO ST PASA Issued | 105.5 | Incorporates scheduled commissioning test envelopes (+27.1% vs persistence) |
| NSW to SA | Day 2-7 | Delivery-Period Baseline (+ AEMO ST PASA cross-check) | 122.7 - 129.7 | Avoids regression extrapolation while tracking diurnal solar-voltage rhythm |
| SA to NSW | Intraday (0-6h) | Delivery-Period / AEMO Predispatch blend | 109.3 - 109.8 | Nearly identical accuracy (+9.9% vs persistence) with stable diurnal tracking |
| SA to NSW | 6h to Day 7 | AEMO ST PASA Issued | 93.3 - 98.1 | Dominates all baselines and regressions by +57.5% to +60.1% vs persistence |

> [!TAKEAWAY] Operational Rule for Forecasting Commissioning Interconnectors
> Never deploy regression-based statistical limit models trained on short commissioning histories onto a newly energised link while AEMO is stepping discretionary test ceilings. Use AEMO ST PASA for multi-day SA to NSW guidance (93 to 98 MW MAE), Delivery-Period plus latest-anchor Persistence for short-term NSW to SA reference bounds, and treat probabilistic interval widths as strictly uncalibrated until EnergyConnect completes Stage 2 commissioning and enters steady-state system-normal operation.

Use the searchable scorecard below to inspect every product, direction, lead band, and model across all 54 audited EnergyConnect forecast cells.

Part II now broadens the forecasting verdict from EnergyConnect's 53-day commissioning window back to the mature VNI and QNI spines, evaluating whether long-range 1-to-90-day MT PASA models and regime-clustering architectures clear genuine out-of-sample promotion gates.

## Chapter 4 · Long-Range 1-to-90-Day Forecasting Verdict Across Fifty Horizon Bands

Trading desks managing quarterly Settlement Residue Auction books and seasonal interstate swap positions routinely ask a tempting question: if short-term diurnal and NOS models add value at 1-to-7-day horizons, can feeding original-vintage Medium-Term PASA (MT PASA) regional availability and demand forecasts into ridge or gradient-boosted trees produce skilful interconnector limit and flow forecasts out to 30, 60, or 90 days?

To answer that question without hindsight contamination, the repository executed a strictly bounded long-range campaign (`qni_vni_longrange_v1`, summarised in the 5 October 2026 *Forward Forecasting Verdict*) using daily 08:00 NEM origins, strictly original-vintage MT PASA inputs, and five separate horizon bands (`1-7`, `8-14`, `15-30`, `31-60`, and `61-90` days) across all five targets (`export_tight`, `import_tight`, `export`, `import`, and `flow`) on both VNI and QNI, producing 50 horizon-band evaluations across 10 connector-by-target cells.

### 4.1 The predictability frontier: why error expands rapidly beyond two weeks

Plotting MAE trajectories across all 50 horizon bands on VNI and QNI illustrates exactly how quickly interconnector predictability erodes once initial-state memory and confirmed 7-day NOS bookings expire.

On VNI, export-tight MAE climbs from 304.6 MW in days 1-7 (calendar baseline) to 343.1 MW in days 31-60 and 396.2 MW in days 61-90, while import-tight MAE stays near 210 to 240 MW across intermediate horizons. On QNI, selection-stage ridge and boosting models trimmed raw MAE relative to simple calendar baselines on several bands (bringing QNI import-tight down near 240 MW vs 360 MW calendar), yet exhibited steep degradation relative to persistence on QNI export and wide block-bootstrap uncertainty across origins.

### 4.2 Complete ten-cell promotion verdict: 10 of 10 retained the baseline

Under the repository's strict promotion protocol, a complex challenger model earns promotion only if it beats the simple baseline on identical chronological out-of-sample rows with a statistically positive confidence interval, beats persistence cleanly, and passes interval calibration and prospective receipt-time confirmation. All ten cells were audited against those exact gates:

| Connector | Target | Selection-stage winner | Weighted skill vs calendar baseline (%) | Baseline CI strictly positive? | Weighted skill vs persistence (%) | Persistence CI strictly positive? | Official cell decision |
|---|---|---|---:|---|---:|---|---|
| VNI | `export_tight` | Calendar | 0.0% | No | +25.7% | Yes | **Retain baseline** |
| VNI | `import_tight` | Boosting | -1.3% | No | +29.3% | Yes | **Retain baseline** |
| VNI | `export` | Boosting | -4.2% | No | +29.3% | Yes | **Retain baseline** |
| VNI | `import` | Calendar | 0.0% | No | +22.9% | Yes | **Retain baseline** |
| VNI | `flow` | Boosting | +3.0% | No | +22.3% | No | **Retain baseline** |
| QNI | `export_tight` | Boosting | +17.8% | **Yes** | -42.7% | No | **Retain baseline** |
| QNI | `import_tight` | Ridge | +36.9% | No | +9.6% | No | **Retain baseline** |
| QNI | `export` | Boosting | +7.7% | No | -50.1% | No | **Retain baseline** |
| QNI | `import` | Ridge | +39.2% | No | +12.2% | No | **Retain baseline** |
| QNI | `flow` | Ridge | +6.5% | No | -26.3% | No | **Retain baseline** |

Look closely at why 10 of 10 cells retained the simple baseline despite apparent point-estimate wins on QNI:

1. **VNI challengers failed to beat the calendar baseline out of sample:** Even though VNI's simple calendar baseline outperformed naive persistence by +22.3% to +29.3% across all five targets (with individual band gains ranging from +6.3% to +34.5%), gradient boosting and ridge regression added zero or negative skill relative to the calendar baseline on four of five VNI targets (-4.2% on export, -1.3% on import-tight, 0.0% on export-tight and import, and an insignificant +3.0% on flow). Once seasonal diurnal profiles are captured, 15-to-90-day MT PASA thermal-availability aggregates contain too little spatial resolution to predict which specific 330 kV VNI line constraint will bind weeks later.
2. **QNI challengers failed dual-baseline consistency and CI significance:** On QNI, `export_tight` was the only cell out of ten where a challenger cleared a strictly positive 95% confidence interval versus the calendar baseline (+17.8%), yet on the exact same rows it lost heavily to naive persistence (-42.7% skill vs persistence, and -50.1% on `export`). Meanwhile, QNI `import_tight` (+36.9% vs calendar) and `import` (+39.2% vs calendar) posted promising point skill, yet failed statistical significance (`primary_improvement_ci_positive = False`) across the 56 test origins and showed weak persistence margins (+9.6% to +12.2%, with confidence intervals crossing zero).
3. **Calibration failed on two-thirds of the 50 horizon bands:** Across all 50 evaluated connector-target-band combinations, only 16 of 50 bands (32.0%) passed nominal interval calibration checks (for instance, VNI `export_tight` calibrated in bands 1-7 through 31-60 days with 83.9% to 90.7% empirical coverage at the 80% level, but failed at 61-90 days; VNI `import_tight` failed calibration immediately at 1-7 days with just 67.1% coverage).

### 4.3 Physical anatomy of the 14-day predictability cliff and the QNI persistence trap

Why does a gradient-boosted tree on QNI `export_tight` beat the seasonal calendar baseline by +17.8% with a statistically positive confidence interval while simultaneously losing by -42.7% to simple persistence on the exact same evaluation rows? That apparent paradox reveals a fundamental structural distinction between VNI and QNI physics across multi-week horizons.

On **VNI**, transfer limits are dominated by fast-cycling diurnal solar-voltage patterns and short, frequent transmission switching events across the Victoria–Snowy–Southern NSW mesh. Because VNI limits oscillate strongly between midday solar hours and evening peaks every single day, naive persistence (carrying forward a single origin snapshot for 30 to 60 days) suffers severe phase error, allowing a simple hour-of-day and month-of-year calendar baseline to beat persistence by +22.3% to +29.3%. Once that seasonal diurnal waveform is removed, however, remaining 15-to-90-day variance is driven by synoptic wind/cloud fronts and unscheduled line maintenance that MT PASA regional totals cannot foresee.

On **QNI**, by contrast, major export-limit depressions frequently persist for multi-week stretches during extended Northern NSW 330 kV line works (such as Liddell–Tamworth Line 84 or Armidale–Dumaresq Line 8C) and prolonged Queensland coal-unit maintenance blocks. When a major transmission derating lasts three weeks, a seasonal calendar average reverts immediately back toward the multi-year monthly mean and accumulates large systematic error. Persistence stays anchored inside the active outage state and therefore beats the calendar curve heavily across Days 1 through 30. The boosting challenger partially tracks the regime using MT PASA regional availability, beating the naive calendar baseline (+17.8%), yet still reverts too far toward historical training means relative to the live persistence anchor (-42.7%).

This structural diagnosis leads directly to a practical 15-to-90-day desk workflow that avoids both traps:
- **Do not average point ML predictions across Days 15 to 90:** Point regression forecasts compress tail risk toward the conditional mean and fail interval calibration on 34 of 50 horizon bands.
- **Anchor on calibrated seasonal distributions overlaid with confirmed NOS transmission calendars:** Start from the historical month-by-hour empirical distribution (which captures VNI's +22% to +29% diurnal skill with zero overfitting), then explicitly condition the active weeks on booked transmission outages using the calibrated NOS binding probabilities (`p_cal`) and N-1-1 overlap flags established in Flagship Edition B, discounting tentative 30-to-90-day bookings for the 31% withdrawal rate observed in NOS lifecycle logs.

> [!TAKEAWAY] Commercial Reality of 15-to-90-Day Forecasting
> At horizons beyond 14 days, unbooked transmission maintenance, booking withdrawals (31% in Flagship Edition B), synoptic weather fronts, and coal unit forced outages dominate interconnector transfer variance. Seasonal calendar baselines already capture 22% to 29% of persistence error on VNI without overfitting. Until measured-receipt prospective confirmation proves a multi-month feature set beats both seasonal baselines and persistence simultaneously, desks should anchor 15-to-90-day valuation on calibrated seasonal distributions plus confirmed NOS outage calendars rather than point ML limit forecasts.

Inspect all 50 long-range band evaluations interactively in the searchable ledger below.

Before concluding the forecasting audit, one popular machine-learning hypothesis remains to be tested: even if global models struggle across regimes, can unsupervised regime clustering (splitting hours into distinct grid states and fitting local expert models per cluster) unlock hidden forecast skill? Chapter 5 evaluates the complete leakage-controlled clustering campaign.

## Chapter 5 · Leakage-Controlled Regime Clustering and Stability Audit

Unsupervised clustering is a recurring proposal in electricity market modelling: partition historical market intervals into discrete operating regimes (such as "high-solar midday congestion," "evening peak scarcity," or "mild overnight slack") using K-means or Gaussian Mixture Models (GMM), and then train either cluster-interaction features or separate local expert regressors inside each cluster. The intuition is appealing, because Flagship Edition A proved that interconnector limits jump across qualitatively different physical constraint regimes.

Yet clustering in time-series forecasting is notoriously vulnerable to two subtle statistical illusions: in-sample look-ahead leakage (fitting cluster centroids across the entire dataset before evaluating out-of-sample folds) and multiple-testing cherry-picking (reporting a few favourable fold-horizon wins while ignoring dozens of neutral or negative folds). The repository's leakage-controlled clustering campaign (`qni_vni_clustering_v1`) eliminated both illusions by fitting all cluster partitions strictly inside pre-origin training windows across 10 chronological folds, measuring chronological stability via Adjusted Rand Index (ARI), and benchmarking every cluster model against matched control models (`boost_fundamentals`, `boost_network`, `ridge_fundamentals`, `ridge_network`, `persistence`, and seasonal baselines) with seven-day block-bootstrap p-values and Holm-Bonferroni family-wise error correction.

### 5.1 Structural state stability: only coarse two-state partitions persist chronologically

Before a cluster label can help a live forecasting pipeline, the discovered regimes must actually recur consistently across consecutive chronological folds rather than mutating randomly each month. Measuring both random-seed stability (`seed_ari`) and out-of-sample chronological block stability (`block_ari`) across $k \in \{1, 2, 3, 4, 6, 8\}$ exposes a clear structural boundary.

| Connector | Method | k = 2 block ARI (seed ARI) | k = 3 block ARI (seed ARI) | k = 4 block ARI (seed ARI) | k = 6 block ARI (seed ARI) | k = 8 block ARI (seed ARI) | Stability verdict |
|---|---|---:|---:|---:|---:|---:|---|
| VNI | K-means | **0.94** (1.00) | 0.88 (1.00) | 0.71 (0.92) | 0.87 (0.99) | 0.66 (0.96) | Coarse k=2-3 stable; decays at k>=4 |
| VNI | GMM | **0.89** (1.00) | 0.71 (0.79) | 0.61 (0.85) | 0.45 (0.67) | 0.47 (0.51) | Unstable beyond k=2 |
| QNI | K-means | **0.89** (1.00) | **0.94** (1.00) | 0.91 (1.00) | 0.87 (0.97) | 0.78 (0.92) | K-means stable to k=4 |
| QNI | GMM | 0.37 (1.00) | 0.89 (1.00) | 0.77 (0.86) | 0.71 (0.79) | 0.71 (0.77) | Erratic at k=2 and k>=6 |

Look at the telling divergence between `seed_ari` and `block_ari` on VNI: K-means achieves near-perfect seed reproducibility (0.96 to 1.00 across $k=2$ to $k=8$) when refit on the same window, yet its chronological block stability falls from 0.94 at $k=2$ down to 0.71 at $k=4$ and 0.66 at $k=8$. Gaussian Mixture Models decay even faster on VNI, dropping from 0.89 at $k=2$ to 0.45 at $k=6$ and 0.47 at $k=8$. What the algorithm cleanly recovers across time is the dominant binary day/night or solar/non-solar split ($k=2$ to $k=3$), which is already captured deterministically by simple clock-hour and solar-irradiance features. Attempting to slice the NEM into six or eight unsupervised sub-regimes mostly chases transient seasonal weather clusters that do not recur reliably in the next chronological block.

### 5.2 Forecasting accuracy versus matched controls: 0 of 241 survive Holm correction

Across all 241 seven-day block-bootstrap evaluations comparing cluster-based models (`cluster_local_experts` and `cluster_interactions`) against matched controls across VNI and QNI folds, horizon bands, and targets, the verdict is clear: 155 of 241 raw evaluations showed negative point MAE deltas (apparent gains), yet exactly 0 of 241 survived Holm-Bonferroni multiple-testing correction at the 5% significance level.

| Connector | Matched control model | Target | 7-day evaluations | Mean MAE delta (MW) | Mean MAE delta (%) | Raw point wins | Unadjusted p < 0.05 wins | Holm-Bonferroni sig. wins |
|---|---|---|---:|---:|---:|---:|---:|---:|
| VNI | `boost_fundamentals` | `flow` | 29 | -44.7 | -16.2% | 27 | 17 | **0** |
| VNI | `boost_fundamentals` | `import_tight` | 19 | -28.3 | -13.8% | 18 | 13 | **0** |
| VNI | `boost_fundamentals` | `export_tight` | 18 | -27.9 | -12.7% | 14 | 7 | **0** |
| VNI | `boost_network` | `export_tight` | 6 | +34.0 | +10.4% | 1 | 1 | **0** |
| VNI | `ridge_fundamentals` | `export_tight` | 11 | -3.9 | -2.5% | 6 | 6 | **0** |
| VNI | `ridge_fundamentals` | `import_tight` | 13 | +1.1 | +0.4% | 5 | 1 | **0** |
| QNI | `boost_fundamentals` | `import_tight` | 15 | -136.3 | -98.1% | 12 | 10 | **0** |
| QNI | `boost_fundamentals` | `export_tight` | 18 | -57.9 | -42.8% | 14 | 11 | **0** |
| QNI | `boost_fundamentals` | `flow` | 22 | -19.4 | -9.4% | 14 | 10 | **0** |
| QNI | `ridge_fundamentals` | `export_tight` | 8 | -2.1 | -0.9% | 6 | 5 | **0** |
| QNI | `ridge_fundamentals` | `flow` | 13 | +6.4 | +1.1% | 4 | 2 | **0** |

Why do cluster models appear to beat `boost_fundamentals` by 13% to 43% in raw unadjusted tables, yet shrink to roughly zero (-2.5% to +1.1%) against `ridge_fundamentals` and lose by +10.4% against `boost_network` on VNI export-tight?

The diagnostic explanation is straightforward and instructive for every quantitative team:
1. **Unconstrained gradient boosting on fundamentals alone overfits across regimes:** When a global tree model is given raw regional demand and renewable fundamentals without network-state features (`boost_fundamentals`), partitioning the data into coarse clusters acts merely as a crude regulariser.
2. **Once proper regularisation (`ridge_fundamentals`) or explicit network-state features (`boost_network`) are included in the control model, the clustering advantage evaporates:** Against `ridge_fundamentals`, mean cluster MAE changes collapse to -2.5% to +1.1% across both VNI and QNI. Against `boost_network` on VNI, clustering actively degrades accuracy by +1.4% on flow, +1.9% on import-tight, and +10.4% on export-tight because hard cluster boundaries fragment already scarce outage-regime training samples across separate local trees.

### 5.3 Why explicit physical state features outperform unsupervised clusters

The contrast between `+10.4%` MAE degradation under `cluster_local_experts` versus `boost_network` on VNI export-tight highlights an elementary bias-variance trade-off that applies across every power-system forecasting task.

Consider a two-year training window containing roughly 730 calendar days, of which only 45 to 80 days exhibit an active Southern NSW 330 kV outage regime (such as a Line 6 or Line 8 work window mapped in Flagship Edition B). If a global network-state model receives continuous, physically grounded regime descriptors directly as input features (specifically the leading active constraint family, the `setter_matched` audit flag from Flagship Edition A, signed directional headroom, and the chronologically calibrated NOS binding probability $p_{\text{cal}}$ from Flagship Edition B), every decision tree retains access to all 730 training days while splitting sharply on the exact physical outage flag whenever it turns active.

By contrast, fitting an unsupervised K-means or GMM partition on regional demand, wind, and solar splits those 730 days across $k=6$ or $k=8$ weather-driven centroids that are largely orthogonal to transmission maintenance schedules. Each local expert regressor now sees only 6 to 12 outage days inside its assigned cluster, causing severe small-sample variance and brittle boundary jumps whenever an afternoon cloud front pushes an hour across a Voronoi boundary from Cluster 3 into Cluster 5. Moreover, because cluster labels are estimated from continuous weather variables, any shift in seasonal solar output or new battery capacity shifts cluster geometry between chronological folds (driving VNI GMM `block_ari` down to 0.45 at $k=6$), whereas physical transmission constraint equations and NOS corridor tags remain anchored to the actual high-voltage topology.

> [!WARNING] Engineering Verdict on Regime Clustering
> Do not add unsupervised K-means or GMM cluster-splitting layers into operational interconnector forecasting pipelines. Explicit physical network-state features (leading constraint family, `setter_matched` flag, signed directional headroom, and calibrated NOS outage occupancy from Flagships A and B) outperform black-box unsupervised clusters without fragmenting training sample sizes or failing multiple-testing gates.

Chapter 6 now consolidates all ten registered workstreams across the entire repository into a clear three-stack governance map and defines the exact prospective receipt-time confirmation gates required before promoting any live interconnector forecast model.

## Chapter 6 · Three-Stack Architectural Governance and Prospective Confirmation Roadmap

Across three flagship research editions and ten distinct analytical workstreams, the repository has accumulated a rich body of constraint-equation telemetry, outage attribution, loop-settlement valuation, and forecasting experiments. Without strict architectural hygiene, however, organisations routinely make a fatal deployment mistake: quoting accuracy numbers from a conditional historical backtest (which sees realised future demand and weather) as if they applied to a live seven-day trading forecast, or mixing feature contracts from experimental bundles into production routing code.

This final chapter formalises the exact boundary across the repository's three distinct model stacks, maps every one of the ten registered workstreams to its permitted claims and unresolved promotion gates, and specifies the four concrete operational requirements needed to move from retrospective research to a verified live interconnector forecasting service.

### 6.1 Maintaining strict separation across the three repository model stacks

Every researcher, developer, and trading-desk consumer working with this repository must preserve the exact boundaries separating its three stacks:

1. **Stack 1 · Original Six-Interconnector Conditional Backtest (`original`):** Implemented in the top-level modules and executed via the core backtest pipeline across all six interconnectors (QNI, Directlink, VNI, Heywood, Murraylink, Basslink). This stack is fundamentals-rich (regional demand, wind, solar, temperature, humidity) and provides valuable structural understanding of how weather and fundamentals map onto directional transfer bounds. However, because its historical evaluation supplies realised future demand, renewable generation, and weather, its metrics must always be labelled strictly as conditional research performance, never as the live accuracy of an operational seven-day forecast.
2. **Stack 2 · Newer QNI/VNI, Outage, PEC, and Valuation Research Campaigns (`experiments` and `valuation`):** Houses the diurnal/NOS v2 saved bundles on VNI and QNI, the two-year six-link constraint-pressure atlas (Flagship Edition A), the NOS outage-regime and 50-line corridor handbook (Flagship Edition B), the observed EnergyConnect commissioning and loop-settlement bridge (Flagship Edition C), the 1-to-90-day long-range MT PASA campaign, and the leakage-controlled clustering study. These campaigns are network-state-rich and strictly chronological, yet remain research-only until a measured-receipt live feature feed and prospective confirmation scorecard clear every promotion gate.
3. **Stack 3 · Provider-Neutral Routing Scaffold (`production`):** Provides an offline, provider-neutral registry and routing interface designed to accept promoted model bundles once governance gates pass. Shadow collection and live forecasting schedules remain paused; this scaffold is not a deployed or scheduled production forecast service.

### 6.2 Complete ten-workstream governance register

Consolidating the repository's official Research Evidence Register lays out the exact status, permitted commercial claim, and unresolved gate for every completed campaign across all stacks.

| Workstream | Stack | Current status | Permitted claim | Unresolved promotion gates |
|---|---|---|---|---|
| Six-link conditional backtest | `original` | Completed | Conditional performance using realised future fundamentals | Live issue-time evaluation; interval calibration |
| VNI diurnal/NOS v2 | `experiments` | Completed research | Retrospective rolling development evidence | Receipt-time feed; prospective confirmation; interval calibration |
| QNI diurnal/NOS v2 | `experiments` | Completed research | Retrospective rolling development evidence | Mixed cell skill; prospective confirmation; interval calibration |
| QNI/VNI fundamentals v3 | `experiments` | Preserved report | Preserved historical report using publication proxies | Ledger stage revalidation; measured receipt; risk gates; full lead coverage |
| QNI/VNI clustering v1 | `experiments` | Validated research | Historical development using publication proxies (0/241 Holm wins) | Prospective confirmation (no promotion recommended) |
| NOS outage regimes | `experiments` | Completed research | Retrospective matched historical associations & SRA dollars | Measured receipt replay; forward incident confirmation |
| NOS mechanics & outlook | `experiments` | Completed research | Retrospective mechanics & calibrated research outlook (55/96 cells) | Forward booking reliability; unsupported-cell calibration |
| Interregional valuation v2 & v3 | `valuation` | Completed research | Historical settlement, SRA auction, loop & hedge research | Issue-time flow regimes; automatic futures history; prospective valuation |
| QNI/VNI long-range v1 | `experiments` | Completed (no promotion) | Original-vintage 1-90d test retained baseline in 10/10 cells | Prospective outcomes and scorecard |
| Production scaffold | `production` | Shadow paused | Offline provider-neutral routing scaffold | Prospective scorecard; explicit model promotion review |

### 6.3 Four mandatory promotion gates before live deployment

To convert the analytical breakthroughs delivered across Flagships A, B, and C into a genuinely promotable live forecasting and SRA-valuation service, four concrete engineering gates must be satisfied in sequence:

1. **Gate 1 · Measured-receipt live vintage ingestion (no publication-time proxies):** Every live forecast input (AEMO Predispatch, ST PASA, MT PASA, NOS booking releases, regional weather forecasts, and SCADA constraint factors) must be archived at exact observed receipt timestamp alongside issue time, run vintage, delivery interval, age, and SHA-256 content hash. Mixing vintages across regions within a single feature row or substituting post-hoc archives as live inputs invalidates promotion immediately.
2. **Gate 2 · Versioned challenger contracts with exact-match hygiene:** New features identified in this three-wave research programme (Flagship A's `setter_matched` quarantine flag, tight-headroom economic DUID aggregates, five-minute BESS impulse trackers, and 6x6 cascade indicators; Flagship B's chronologically calibrated NOS binding probabilities `p_cal` and N-1-1 regional overlap alarms; and Flagship C's EnergyConnect commissioning configuration flags) must enter through a new versioned feature contract and be evaluated as a separate challenger. Never inject future fundamentals or new columns into existing saved VNI/QNI bundle slots.
3. **Gate 3 · Dual-baseline and risk-gate dominance on identical prospective rows:** Any challenger seeking promotion on a connector, target, and lead band must beat both naive persistence and matched AEMO issued forecasts (Predispatch or ST PASA) on identical prospective rows, while simultaneously clearing interval coverage calibration (near nominal 80% and 95% coverage) and contraction-event precision/recall targets. As Chapter 4 proved on QNI `export_tight`, a +17.8% point gain over a calendar baseline never overrides a -42.7% loss against persistence or failed interval coverage.
4. **Gate 4 · Explicit EnergyConnect Stage 2 re-baselining:** Once Project EnergyConnect completes its 150 MW and 350 MW commissioning phases and transitions to steady-state Stage 2 operation (up to 800 MW), southern-ring dispatch geometry across VNI, Heywood, Murraylink, and `NSW1-SA1` will shift permanently. Historical pre-PEC models on VNI and Heywood will require explicit post-commissioning re-estimation, while SRA valuation models must run continuously under the AEMC `ERC0386` six-bucket loop settlement rules quantified in Chapter 2.

### 6.4 Shadow-mode engineering runbook for desk implementation

Turning Gates 1 through 4 into a concrete quarterly work programme requires four tightly scoped engineering deliverables that build directly on the audited modules already verified in this repository:

- **Deliverable 1 (Immutable As-Of Vintage Collector):** Deploy a lightweight scheduled collector writing raw NEMWEB Predispatch, ST PASA, MT PASA, and NOS payloads into an append-only local store keyed by `(product, run_datetime, observed_receipt_utc, sha256)`. Enforce an automated schema assertion rejecting any feature row whose input vintage timestamp exceeds `origin_time - ingestion_buffer` (default 5 minutes) or mixes incompatible regional forecast runs.
- **Deliverable 2 (Challenger Feature Contract v4):** Freeze the existing VNI and QNI v2 bundles untouched as historical reference baselines. Assemble a separate versioned `v4` feature table incorporating strictly as-of versions of Flagship A's constraint-family state and five-minute battery ramp trackers, Flagship B's chronologically calibrated NOS `p_cal` and N-1-1 concurrent-outage flags, and Flagship C's `NSW1-SA1` active commissioning cap.
- **Deliverable 3 (Prospective 90-Day Shadow Scorecard):** Run the `v4` challenger silently alongside `Persistence`, `Delivery-Period Baseline`, and `AEMO Issued` limits for one full calendar quarter across all four mainland AC spines (QNI, VNI, Heywood, and EnergyConnect). Publish an automated weekly scorecard reporting MAE skill versus both baselines, contraction recall and precision, 80% and 95% empirical interval coverage, and calibration ECE by lead band. Promote only individual `(connector, target, lead_band)` cells that clear every gate simultaneously.
- **Deliverable 4 (Stage 2 PEC Loop Re-Baselining Trigger):** Monitor observed `NSW1-SA1` tight limits continuously for sustained operation above 450 MW (indicating transition from Stage 1 testing into Stage 2 full rating). Once triggered, freeze pre-Stage-2 VNI and Heywood training windows, re-run the Chapter 2 `ERC0386` six-bucket loop valuation ledger using realised Stage 2 flow distributions alongside live spread compression, and update SRA auction bid curves accordingly.

### 6.5 Unified operational synthesis across Flagship Editions A, B, and C

Together, the three flagship Virtual Barrels editions and three compressed standalone Event Atlases v2 establish a complete, auditable institutional reference for NEM interconnector physics, outage risk, and forward valuation:

- **Flagship Edition A (`Constraint Pressure Atlas v2` + `Event Atlases v2`):** Maps all six interconnectors at full 24-month parity (44,185 sharp contractions, 1.28 million binding equation-intervals, 446 active units), proves that economic rent weighting elevates dispatchable hydro (`TUMUT3`) and grid-scale batteries (`KESSB1`, `MREHA3`, `VBB1`) over slack midday solar, isolates 70% to 95% parallel HVDC co-binding, diagnoses QNI/Heywood reconstruction error strictly to unmatched non-thermal setters, splits contractions into 43.5% equation switches versus 24.3% LHS ramps versus 32.3% RHS shifts, and maps 6x6 cascades plus -$118m in VNI/Heywood negative residues.
- **Flagship Edition B (`Outage Risk & NOS Regime Handbook v2`):** Translates 697 NOS outage family-directions into matched `$/MWh` spreads and `$/day` SRA shifts, exposes 109 super-additive N-1-1 concurrent-outage pairs compounding up to -776 MW beyond linear sums, repairs the legacy binding outlook via strictly chronological Empirical-Bayes and isotonic calibration (jumping from 14/96 to 55/96 skilful cells and slashing binding ECE seven-fold from 3.05 pp to 0.43 pp), and stabilises all 50 transmission lines across eight regional corridors including Capital-Canberra Line 6 and Dapto-Marulan Line 8.
- **Flagship Edition C (`Interconnector Forecasting Verdict, Clustering & Project EnergyConnect v2`):** Documents observed EnergyConnect commissioning physics (79.4% to 86.4% empirical utilisation, 31.2% VNI ring coupling on SA to NSW), bridges observed 150 MW and 350 MW profiles directly into the AEMC `ERC0386` loop engine (mapping PEC's share from 22.9% pass-through at 0 MW to 40.8% at 350 MW and 58.2% at 800 MW while cutting negative net-loop deficits by up to 85%), audits 66,144 EnergyConnect issue-time forecasts, and draws an honest, evidence-backed line across 1-to-90-day MT PASA horizons (10/10 retain baseline) and regime clustering (0/241 Holm wins).

## Appendix A · Mathematical Identities for EnergyConnect Loop Settlement and Forecast Evaluation

All five-minute and half-hourly market calculations are aligned to fixed NEM time (UTC+10, interval-ending). Tight directional half-hour limits equal the minimum across the six constituent five-minute dispatch intervals.

### A.1 AEMC ERC0386 net-trade loop settlement identities

Let the three southern-ring loop arms be $\text{VN} = (\text{VIC1} \to \text{NSW1})$, $\text{VS} = (\text{VIC1} \to \text{SA1}$, pooling Heywood and Murraylink), and $\text{NS} = (\text{NSW1} \to \text{SA1}$, Project EnergyConnect). In each five-minute interval $t$, let $F_{a,t}$ be the signed physical flow on arm $a \in \{\text{VN}, \text{VS}, \text{NS}\}$, and let $\pi_{r,t}$ be the regional reference price in $r \in \{\text{NSW1}, \text{VIC1}, \text{SA1}\}$.

1. **Signed arm IRSR allocation and net loop residue:**
   $$A_{a,t} = \frac{F_{a,t} \cdot (\pi_{\text{to}(a),t} - \pi_{\text{from}(a),t})}{12}, \qquad \text{NL}_t = A_{\text{VN},t} + A_{\text{VS},t} + A_{\text{NS},t}$$
   Whenever $\text{NL}_t \le 0$, zero payout is distributed to Settlement Residue Distribution (SRD) units in interval $t$ and the negative deficit is recovered through transmission network pricing.
2. **Net regional export positions:**
   $$E_{\text{NSW1},t} = F_{\text{NS},t} - F_{\text{VN},t}, \qquad E_{\text{VIC1},t} = F_{\text{VN},t} + F_{\text{VS},t}, \qquad E_{\text{SA1},t} = -F_{\text{VS},t} - F_{\text{NS},t}$$
   By conservation of flow across the lossless nodal triangle, $E_{\text{NSW1},t} + E_{\text{VIC1},t} + E_{\text{SA1},t} \equiv 0$.
3. **Net trade quantities and Step-1 amounts:** Let region $r$ be classified as net exporting if $E_{r,t} \ge 0$ and net importing if $E_{r,t} < 0$. Each arm $a$ linking an exporting region $e$ to an importing region $m$ carries net-trade quantity $q_{a,t}$ equal to $E_{e,t}$ when two regions export (one importer), or $-E_{m,t}$ when one region exports (two importers), with Step-1 amount:
   $$\text{Amt}_{a,t} = q_{a,t} \cdot (\pi_{m,t} - \pi_{e,t})$$
4. **Provisional allocation and secondary positive netting:**
   $$\text{Prov}_{a,t} = \text{NL}_t \cdot \frac{\text{Amt}_{a,t}}{\sum_{b} \text{Amt}_{b,t}}, \qquad \text{Final}_{a,t} = \mathbb{I}(\text{NL}_t > 0) \cdot \text{NL}_t \cdot \frac{\max(\text{Prov}_{a,t}, 0)}{\sum_{b} \max(\text{Prov}_{b,t}, 0)}$$
   satisfying exact payout conservation $\sum_{a} \text{Final}_{a,t} \equiv \max(\text{NL}_t, 0)$ whenever at least one arm has positive provisional allocation.

### A.2 Observed commissioning counterfactual flow response

For each commissioning regime $(C_{\text{fwd}}, C_{\text{rev}}, u)$ with empirical median utilisation ratio $u = \text{median}(|F_{\text{NS}}| / C^{\text{active}})$ measured over positive-limit half-hours ($C^{\text{active}} \ge 25\text{ MW}$), historical-price counterfactual PEC flow over the 24-month loop panel is:

$$F_{\text{NS},t} = \tanh\left(\frac{\pi_{\text{SA1},t} - \pi_{\text{NSW1},t}}{35}\right) \cdot u \cdot \Big(C_{\text{fwd}} \mathbb{I}(\pi_{\text{SA1},t} \ge \pi_{\text{NSW1},t}) + C_{\text{rev}} \mathbb{I}(\pi_{\text{SA1},t} < \pi_{\text{NSW1},t})\Big)$$

### A.3 Forecast MAE skill, interval coverage, and clustering ARI

For any forecast model $m$ and baseline $b$ evaluated on an identical set of as-of rows $\mathcal{I}$:

$$\text{MAE}_m = \frac{1}{|\mathcal{I}|}\sum_{i \in \mathcal{I}} |y_i - \hat{y}_{m,i}|, \qquad \text{Skill}_{m \text{ vs } b} = 1 - \frac{\text{MAE}_m}{\text{MAE}_b}$$

Empirical interval coverage for nominal prediction radius $r_{m,i}$ is $\text{Cov}_m = \frac{1}{|\mathcal{I}|}\sum_{i \in \mathcal{I}} \mathbb{I}(|y_i - \hat{y}_{m,i}| \le r_{m,i})$. Clustering partition agreement across random initialisations (`seed_ari`) and adjacent chronological folds (`block_ari`) is measured via the Hubert-Arabie Adjusted Rand Index ($\text{ARI} \in [-1, 1]$, where 1.0 denotes identical partitions and 0.0 denotes chance agreement), with forecast MAE differences tested via seven-day block bootstrap and Holm-Bonferroni step-down family-wise error control.

## Appendix B · Data Schema, Archive Lineage, and Reproducible Build Commands

All local parquet caches, upstream report exports, and repository code paths used in Wave 3 are listed here to keep Chapters 1 through 6 free of raw filenames while preserving deterministic auditability.

### B.1 Local archive inputs (zero new NEMWEB downloads)

| Analytical module | Local repository path | Coverage & provenance |
|---|---|---|
| C10a observed PEC telemetry | `data/pec_limits_v1/dispatch_interconnectorres.parquet` & `half_hour.parquet` | 15,264 five-minute intervals / 2,544 half-hours (`NSW1-SA1`, 1 Oct to 23 Nov 2026) |
| C10b loop settlement panel | `data/valuation_v2/panel/{prices,interconnectors}.parquet` + `nemic/valuation/loop.py` | 210,240 five-minute intervals (`2024-09-01` to `2026-08-31`) across NSW1, VIC1, SA1, VNI, Heywood, Murraylink |
| C10c PEC issue-time forecasts | `data/pec_limits_v1/forecast_rows_{predispatch,stpasa}.parquet` | 48,336 Predispatch rows + 17,808 ST PASA rows across 5 models and 4 lead bands |
| Long-range 50-band verdict | `reports/forward_forecasting_verdict_20261005/downloads/{band_metrics,cell_results}.csv` | 50 horizon-band evaluations and 10 cell promotion decisions (`qni_vni_longrange_v1`) |
| Leakage-controlled clustering | `reports/qni_vni_clustering_v1/downloads/{forecast_effects,state_stability}.csv` | 362 fold-band-target-control effects (241 seven-day block rows) and 227 stability runs |
| Three-stack register | `docs/RESEARCH_REGISTER.json` | 10 registered workstreams across `original`, `experiments`, `valuation`, and `production` stacks |

### B.2 Generated compact evidence files (`reports/ic_forecasting_and_pec_v2/evidence/`)

1. `pec_observed_configs.csv` (4 rows): observed EnergyConnect commissioning regimes, time shares, tight limit quantiles, empirical utilisation ratios, and forced-negative rates.
2. `pec_southern_ring_coupling.csv` (13 rows): 5-minute setter equation taxonomy across NSW to SA and SA to NSW directions.
3. `pec_loop_settlement_bridge.csv` (4 rows): exact AEMC `ERC0386` net-trade loop settlement totals across all 6 directional SRA buckets for 0, 150, 350, and 800 MW PEC regimes.
4. `pec_issue_time_forecast_scores.csv` (54 rows): MAE, skill vs persistence, skill vs AEMO, and empirical interval coverage across Predispatch and ST PASA.
5. `longrange_band_verdict.csv` (50 rows): complete 50-band long-range MT PASA horizon scorecard.
6. `longrange_cell_decisions.csv` (10 rows): official baseline-retention verdicts across all 10 VNI/QNI targets.
7. `clustering_vs_controls.csv` (29 rows): aggregated seven-day block-bootstrap clustering MAE effects and Holm-Bonferroni significance counts.
8. `clustering_stability_summary.csv` (22 rows): mean `seed_ari` and `block_ari` across $k = 1 \dots 8$ for K-means and GMM on VNI and QNI.
9. `model_stack_governance_register.csv` (10 rows): clean architectural status and unresolved gates across all three stacks.
10. `headline_numbers.json`: 41 verified macro strings checked by unit tests.

### B.3 Deterministic rebuild and verification commands

```powershell
# 1. Recompute all C10 and forecasting/clustering synthesis CSVs
python -m nemic.experiments.ic_forecasting_pec_v2

# 2. Assemble Flagship Edition C self-contained HTML + SHA-256 build manifest
python reports/ic_forecasting_and_pec_v2/build_html.py

# 3. Run Wave 3 unit tests and full repository regression suite
python -m pytest -q tests/test_ic_forecasting_pec_v2.py
python -m pytest -q

# 4. Run headless Playwright desktop/mobile QA
node reports/ic_forecasting_and_pec_v2/qa_report.cjs
```

## Appendix C · Sources, Regulatory References, and Scope Qualifications

### C.1 Institutional and repository references

1. **Australian Energy Market Commission (AEMC).** *Improving the Inter-Regional Settlement Residue Arrangements (ERC0386): Final Rule Determination*, 25 September 2025 (Sections 3.2.1-3.2.3 and Appendix B net-trade loop settlement algorithm implemented in `nemic/valuation/loop.py`).
2. **Australian Energy Market Operator (AEMO).** *Project EnergyConnect Commissioning and Interconnector Testing Notices* and *Predispatch / ST PASA / MT PASA Market Procedures* (governing `NSW1-SA1` 150 MW commissioning and 350 MW testing envelopes).
3. **Holm, S. (1979).** *A simple sequentially rejective multiple test procedure.* Scandinavian Journal of Statistics, 6(2), 65-70 (family-wise error control applied across all 241 seven-day clustering comparisons).
4. **Hubert, L., & Arabie, P. (1985).** *Comparing partitions.* Journal of Classification, 2(1), 193-218 (Adjusted Rand Index used to audit seed and chronological block stability).
5. **IC Flow Forecasting Research Programme.** Preserved baseline reports left completely untouched on disk: `reports/forward_forecasting_verdict_20261005/`, `reports/qni_vni_clustering_v1/`, `reports/qni_vni_longrange_v1/`, `docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md`, and `reports/interregional_valuation_research_v3/`.
6. **IC Flow Forecasting Research Programme.** Companion Flagship Editions A and B: `reports/constraint_pressure_atlas_v2/Constraint_Pressure_Atlas_v2.html` and `reports/outage_risk_handbook_v2/Outage_Risk_Handbook_v2.html`.

### C.2 Scope qualifications and permitted claims

- **Historical-price loop counterfactual:** Chapter 2's AEMC `ERC0386` loop settlement bridge holds 2024 to 2026 regional clearing prices and pre-existing VNI and Heywood+Murraylink flows fixed while injecting observed EnergyConnect commissioning capacity profiles. Because live physical transfer also compresses regional price spreads, the fixed-price totals represent an upper bound on gross loop dollars while accurately isolating bucket reallocation and negative-residue netting geometry.
- **No model promotion implied:** Neither the long-range 1-to-90-day MT PASA challengers (`10/10` retained baseline) nor the leakage-controlled clustering models (`0/241` Holm-significant wins) nor the EnergyConnect commissioning regressions (`Regional + Constraints`) are promoted for operational dispatch forecasting.
- **Strict three-stack isolation:** Consistent with `AGENTS.md`, this report keeps `original` conditional backtest claims, `experiments` retrospective research bundles, and `production` offline routing scaffolding strictly separated.
- **Dispatch-solution limits:** Every observed `NSW1-SA1`, VNI, QNI, and Heywood limit analysed in this report is an endogenous AEMO dispatch-solution output rather than maximum static physical wire capability.
