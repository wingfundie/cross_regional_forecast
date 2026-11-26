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

{{exhibit:c1}}

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

{{exhibit:c2}}

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
