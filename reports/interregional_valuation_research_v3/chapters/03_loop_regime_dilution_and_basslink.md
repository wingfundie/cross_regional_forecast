## 3 Loop settlement, unit dilution, and regulated Basslink

Every settled dollar analysed in Chapter 2 was generated on an open-tree mainland network where Victoria sat as a radial junction between New South Wales and South Australia. Between October 2026 and June 2028, three simultaneous structural regime breaks rewrite the mapping from physical flows to SRA unit cashflows: the closure of the NSW-Victoria-South Australia transmission loop via Project EnergyConnect, the expansion of maximum QNI unit counts in `2027 Q2`, and the transition of Basslink from a market network service provider to a regulated interconnector carrying auctioned `VICTAS` and `TASVIC` units. A valuation framework calibrated naively to 2021–2026 unit payoffs will systematically misprice post-2026 auctions on all three fronts.

### 3.1 Project EnergyConnect and the AEMC Net-Trade Loop Rules

Project EnergyConnect creates a direct 330 kV transmission link between Robertstown in South Australia and Wagga Wagga in New South Wales, closing the mainland southern transmission ring (`NSW1–VIC1–SA1–NSW1`). Once a transmission loop closes, Kirchhoff's laws allow power scheduled between any two regions to split across parallel physical paths. Under the legacy single-asset settlement methodology, parallel loop flows create a severe accounting distortion: power moving from South Australia to New South Wales can flow physically through Victoria, generating positive settlement residue on `SAVIC` and `VICNSW` while simultaneously generating negative residue on the direct `SANSW` arm if regional prices do not align monotonically around the ring.

To eliminate cross-subsidies and whole-loop negative-residue distortions, the Australian Energy Market Commission's final determination `ERC0386` (25 September 2025) replaces asset-by-asset pooling on the southern triangle with a net-trade loop settlement regime [S06, R19]. AEMO's Project EnergyConnect Market Integration schedule fixes 1 October 2026 as the dispatch representation effective date and 1 November 2026 as the settlement effective date for loop residue allocation, accompanied by whole-loop negative residue management [S07, S08, S09].

{{diagram:loopAllocation}}

The loop calculation executes in four deterministic steps during every five-minute interval $t$ across the three southern loop regions (`NSW1`, `VIC1`, `SA1`):

1. Arm-level residue and net loop pool: Compute the standard loss-adjusted settlement residue on each of the three triangle arms (`VIC1-NSW1`, `V-SA` plus `V-S-MNSP1`, and the new `NSW1-SA1` EnergyConnect arm). Sum all three signed arm residues to obtain the total net loop residue $R_{\text{loop},t}$. If $R_{\text{loop},t} \le 0$, no positive residue is distributed to any loop SRA category; the net deficit is recovered through importing-region network charges under whole-loop negative residue management.
2. Net regional trade balance: Calculate each loop region's net export position across the two arms connected to it. When one region acts purely as a pass-through conduit (for example, importing 400 MW from South Australia and simultaneously exporting 400 MW into New South Wales), its net regional trade is zero. Under the new rule, only regions with nonzero net exports and nonzero net imports generate notional directional trade allocations.
3. Provisional directional split: Assign notional interregional trade strictly from net exporting regions to net importing regions, weight each notional trade by its regional price spread, and scale the provisional allocations proportionally so they sum identically to the positive net loop residue $R_{\text{loop},t}$.
4. Secondary netting across loop arms: If any provisional directional allocation is negative (for instance, because a net exporter exports into a lower-priced net importer on one leg while the triangle as a whole remains net positive), that negative provisional amount is deducted proportionally from the positive provisional allocations on the remaining loop arms rather than funded by network customers. SRA unit holders still never face a negative cash call, but positive loop arms absorb the internal cross-arm deficit before distribution.

This four-step algorithm is implemented and verified bit-for-bit against AEMC `ERC0386` Figure 3.1 and Appendix B Example 4 inside the repository's settlement test suite.

### 3.2 Three-Way Attribution Waterfall: Where the Legacy Pool Goes

Applying the verified AEMC loop algorithm directly to the nineteen historical quarters (`2021 Q4` to `2026 Q2`) while holding historical prices and flows fixed (zero physical EnergyConnect transfer) isolates the pure accounting-rule shock before any physical dispatch response occurs. Separating the transition from status-quo payouts into three sequential accounting stages shows exactly which mechanism drives the repricing of existing units:

- Stage 1 (Negative-residue netting across arms): Netting simultaneous negative arms inside the loop against positive arms before distribution, rather than charging negative arms separately to networks.
- Stage 2 (Pass-through reallocation): Stripping pass-through volume out of `VICNSW`, `NSWVIC`, `VICSA`, and `SAVIC` and crediting it directly to the two new `NSWSA` and `SANSW` categories whenever Victoria sits in the middle of a `SA ↔ NSW` transfer.
- Stage 3 (Secondary netting): Absorbing residual negative provisional allocations inside positive loop arms.

{{exhibit:n20}}

{{exhibit:v2}}

Holding historical dispatch fixed, pass-through reallocation accounts for the overwhelming majority of the redistribution (Exhibit 3.1 and Exhibit 3.2). Across the nineteen quarters, Victoria acted as a pass-through region in {{loop_pass_through}} of all five-minute intervals, secondary netting triggered in {{loop_secondary}} of intervals, and the whole loop finished net-negative in {{loop_net_negative}} of intervals.

| Loop category | Status quo 19q total | Stage 1: Neg. arm netting | Stage 2: Pass-through reallocation | Stage 3: Secondary netting | Post-loop 19q total | Aggregate change | Quarterly haircut range (min / med / max) | Status quo $/unit | Post-loop $/unit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `VICNSW` | {{lw_sq_VICNSW}} | {{lw_neg_VICNSW}} | {{lw_pt_VICNSW}} | {{lw_sec_VICNSW}} | {{lw_fin_VICNSW}} | {{loop_change_VICNSW}} | {{lw_qmin_VICNSW}} / {{lw_qmed_VICNSW}} / {{lw_qmax_VICNSW}} | {{lw_pu_sq_VICNSW}} | {{lw_pu_fin_VICNSW}} |
| `NSWVIC` | {{lw_sq_NSWVIC}} | {{lw_neg_NSWVIC}} | {{lw_pt_NSWVIC}} | {{lw_sec_NSWVIC}} | {{lw_fin_NSWVIC}} | {{loop_change_NSWVIC}} | {{lw_qmin_NSWVIC}} / {{lw_qmed_NSWVIC}} / {{lw_qmax_NSWVIC}} | {{lw_pu_sq_NSWVIC}} | {{lw_pu_fin_NSWVIC}} |
| `VICSA` | {{lw_sq_VICSA}} | {{lw_neg_VICSA}} | {{lw_pt_VICSA}} | {{lw_sec_VICSA}} | {{lw_fin_VICSA}} | {{loop_change_VICSA}} | {{lw_qmin_VICSA}} / {{lw_qmed_VICSA}} / {{lw_qmax_VICSA}} | {{lw_pu_sq_VICSA}} | {{lw_pu_fin_VICSA}} |
| `SAVIC` | {{lw_sq_SAVIC}} | {{lw_neg_SAVIC}} | {{lw_pt_SAVIC}} | {{lw_sec_SAVIC}} | {{lw_fin_SAVIC}} | {{loop_change_SAVIC}} | {{lw_qmin_SAVIC}} / {{lw_qmed_SAVIC}} / {{lw_qmax_SAVIC}} | {{lw_pu_sq_SAVIC}} | {{lw_pu_fin_SAVIC}} |
| `NSWSA` | {{lw_sq_NSWSA}} | {{lw_neg_NSWSA}} | {{lw_pt_NSWSA}} | {{lw_sec_NSWSA}} | {{lw_fin_NSWSA}} | New pool | n/a | {{lw_pu_sq_NSWSA}} | {{lw_pu_fin_NSWSA}} |
| `SANSW` | {{lw_sq_SANSW}} | {{lw_neg_SANSW}} | {{lw_pt_SANSW}} | {{lw_sec_SANSW}} | {{lw_fin_SANSW}} | New pool | n/a | {{lw_pu_sq_SANSW}} | {{lw_pu_fin_SANSW}} |

The table exposes three critical valuation consequences for trading desks:

1. **Legacy unit haircuts are large and quarter-dependent:** Even before EnergyConnect carries a single megawatt of physical power, the accounting rule cuts `VICNSW` by {{loop_change_VICNSW}} in aggregate (reducing mean per-unit value from {{lw_pu_sq_VICNSW}} to {{lw_pu_fin_VICNSW}}), with individual quarterly haircuts ranging from {{lw_qmax_VICNSW}} to {{lw_qmin_VICNSW}}. `VICSA` drops {{loop_change_VICSA}} (ranging {{lw_qmax_VICSA}} to {{lw_qmin_VICSA}}), `NSWVIC` drops {{loop_change_NSWVIC}}, and `SAVIC` suffers a severe {{loop_change_SAVIC}} collapse (up to {{lw_qmin_SAVIC}} in quarters dominated by South Australian solar transit through Victoria toward New South Wales).
2. **Pass-through reallocation creates a $315.8m synthetic pool on day one:** Reallocating pass-through flows creates {{loop_new_categories}} of combined nineteen-quarter residue for the two new EnergyConnect categories (`SANSW` at {{lw_fin_SANSW}} and `NSWSA` at {{lw_fin_NSWSA}}, equivalent to {{lw_pu_fin_SANSW}} and {{lw_pu_fin_NSWSA}} per unit at an illustrative 800-unit baseline). Negative-arm netting (`−$21.2m` across all four legacy links) and secondary netting (`$0.0m` net across the ring, shifting small amounts across arms) are second-order compared with pass-through reallocation (`$317.1m` shifted out of the four Victorian arms into `NSWSA`/`SANSW`).
3. **Post-loop hedge firmness degrades on legacy Victorian links:** Stripping pass-through volume out of `VICNSW` and `VICSA` weakens their linear correlation with regional spreads. As detailed in Chapter 8, post-loop weekly variance explained falls from `20%` to {{loop_hr2_VICNSW}} on `VICNSW` (with stress-period MW equivalent dropping from `0.15` to {{loop_hstress_VICNSW}} MW per unit) and from `58%` to {{loop_hr2_VICSA}} on `VICSA`. Meanwhile, the synthetic `NSWSA` and `SANSW` categories start at just {{loop_hr2_NSWSA}} and {{loop_hr2_SANSW}} weekly $R^2$ under fixed dispatch because their notional pool activates only when Victoria is in pass-through state rather than continuously.

### 3.3 Parametric EnergyConnect Transfer and Spread-Compression Sensitivities

The fixed-dispatch counterfactual above intentionally holds physical EnergyConnect flow at zero (`0 MW`) and regional prices unchanged. In live operation, EnergyConnect ramps first through its Stage 1 commissioning release (approximately `150 MW` transfer capability) toward its full Stage 2 rated capacity (`800 MW` nominal transfer capability). Adding physical parallel transfer between South Australia and New South Wales pulls in two opposing directions: higher physical megawatts transferred across the `NSW1–SA1` border expand the gross loop residue pool, while relieving south-to-north congestion simultaneously compresses regional price spreads across `SA1`, `VIC1`, and `NSW1`.

Because a full security-constrained economic dispatch counterfactual requires a nodal network model (built in Stage 3 of the Chapter 12 roadmap), a transparent parametric stress grid bounds the valuation envelope across EnergyConnect transfer capability (`0 MW`, `150 MW`, `800 MW`, dispatched proportionally to the signed `NSW − SA` spread) crossed with uniform loop spread compression (`0%` and `20%`):

| Parametric PEC scenario | `VICNSW` 19q total | `VICSA` 19q total | `NSWSA` 19q total | `SANSW` 19q total | Economic interpretation |
|---|---:|---:|---:|---:|---|
| Status quo (pre-loop baseline) | {{lw_sq_VICNSW}} | {{lw_sq_VICSA}} | {{lw_sq_NSWSA}} | {{lw_sq_SANSW}} | Historical open-tree settlement |
| 0 MW PEC, 0% compression (pure rule) | {{pec_0_0_VICNSW}} | {{pec_0_0_VICSA}} | {{pec_0_0_NSWSA}} | {{pec_0_0_SANSW}} | Pure accounting pass-through shift |
| 150 MW PEC, 0% compression | {{pec_150_0_VICNSW}} | {{pec_150_0_VICSA}} | {{pec_150_0_NSWSA}} | {{pec_150_0_SANSW}} | Stage 1 physical flow without price relief |
| 150 MW PEC, 20% spread compression | {{pec_150_20_VICNSW}} | {{pec_150_20_VICSA}} | {{pec_150_20_NSWSA}} | {{pec_150_20_SANSW}} | Stage 1 with realistic congestion relief |
| 800 MW PEC, 0% compression (upper bound) | {{pec_800_0_VICNSW}} | {{pec_800_0_VICSA}} | {{pec_800_0_NSWSA}} | {{pec_800_0_SANSW}} | Non-equilibrium capacity upper bound |
| 800 MW PEC, 20% spread compression | {{pec_800_20_VICNSW}} | {{pec_800_20_VICSA}} | {{pec_800_20_NSWSA}} | {{pec_800_20_SANSW}} | Stage 2 with moderate spread compression |

Two structural insights emerge immediately from the parametric grid. First, even at `150 MW` of direct transfer with `20%` spread compression, `VICNSW` remains deeply impaired ({{pec_150_20_VICNSW}} versus {{lw_sq_VICNSW}} status quo, a `−22%` reduction), showing that Stage 1 physical relief does not bail out legacy `VICNSW` unit holders. Second, under full `800 MW` transfer, the gross `SANSW` and `NSWSA` pools expand dramatically, **only** if spreads do not collapse faster than flow grows; under `40%` spread compression at `800 MW`, `VICNSW` drops further to `$504.8m` and `SANSW` falls from `$1,508.6m` to `$872.0m`. Desks bidding on post-November 2026 `NSWSA`, `SANSW`, `VICNSW`, and `VICSA` tranches should treat the `0 MW` pure-rule figure as a lower structural bound for EnergyConnect categories and the `800 MW / 0%` column strictly as an unachievable upper ceiling until Stage 3 dispatch simulations quantify actual congestion relief.

### 3.4 Live Catalyst 1: 2027 Q2 QNI Unit-Count Dilution

Loop settlement is not the only structural discontinuity embedded in the live 2026–2028 auction forward curve. Effective **`2027 Q2`**, AEMO's revised unit-category schedule increases maximum auctioned unit counts on the Queensland-New South Wales interconnector to reflect QNI Minor upgrade transfer capacity [S05, R3]:

- **`NSWQLD` (northbound into Queensland):** Maximum units increase from **550 units** to **750 units** (+36.4% more units sharing the same directional pool), imposing a pure mechanical per-unit dilution of **{{dil_pct_NSWQLD}}** holding total residue fixed.
- **`QLDNSW` (southbound into New South Wales):** Maximum units increase from **1,200 units** to **1,300 units** (+8.3% more units), imposing a mechanical per-unit dilution of **{{dil_pct_QLDNSW}}**.

Cross-checking AEMO's live forward auction clearing prices before and after the `2027 Q2` boundary tests whether market participants have already priced this dilution into the forward strip or left a structural mispricing on the table:

| QNI direction | Pre-`2027 Q2` max units | Post-`2027 Q2` max units | Mechanical dilution | Mean price (`2026 Q2–2027 Q1`) | Mean price (`2027 Q2+`) | Same-season Q2 check (`2026 Q2` vs. `2027–28 Q2`) |
|---|---:|---:|---:|---:|---:|---:|
| `NSWQLD` | 550 | 750 | {{dil_pct_NSWQLD}} | {{dil_pre_NSWQLD}} | {{dil_post_NSWQLD}} | $4,569 vs. $3,408 (−25.4%) |
| `QLDNSW` | 1,200 | 1,300 | {{dil_pct_QLDNSW}} | {{dil_pre_QLDNSW}} | {{dil_post_QLDNSW}} | $32,196 vs. $30,042 (−6.7%) |

The live market pricing check delivers a remarkably clean verdict. Comparing identical Q2 autumn delivery quarters across the step change removes seasonal confounding: `NSWQLD` clearing prices step down by `−25.4%` (`$4,569` in `2026 Q2` to `$3,408` across `2027 Q2` and `2028 Q2`) against a `−26.7%` mechanical dilution, while `QLDNSW` steps down by `−6.7%` (`$32,196` to `$30,042`) against a `−7.7%` mechanical dilution. Market participants have already priced the denominator expansion almost to the percentage point. Consequently, any valuation model that feeds historical `2021–2026` per-unit QNI payoffs directly into a `2027 Q2+` forecast without rescaling by the effective-dated unit denominator ($U_{d,q}^{\text{hist}} / U_{d,q}^{\text{target}}$) will generate a spurious `+36%` apparent buy signal on `NSWQLD` and `+8%` on `QLDNSW` that is pure denominator error.

### 3.5 Live Catalyst 2: Regulated Basslink Pro-Forma Backcast

On 30 April 2026, AEMO finalised expedited rules introducing two brand-new regulated SRA categories across Bass Strait: **`VICTAS`** (southbound from Victoria into Tasmania) and **`TASVIC`** (northbound from Tasmania into Victoria), each structured around a 500-unit nominal allocation, with initial forward tranches appearing in the June 2026 auction report [S10, S11]. Because Basslink operated as an unregulated market network service provider (`MNSP`) throughout the `2021 Q4–2026 Q2` historical window, AEMO's settled SRA ledger records **$0** of historical SRA distributions for `VICTAS` and `TASVIC` ({{pos_total_VICTAS}} and {{pos_total_TASVIC}}).

To give trading desks a disciplined empirical anchor for early Basslink auctions without pretending that historical MNSP behaviour equals future regulated dispatch, we construct a **pro-forma regulated Basslink backcast** across all nineteen complete quarters using actual five-minute `T-V-MNSP1` dispatch and metered flows, dated Basslink marginal loss equations, and a 500-unit allocation:

| Pro-forma Basslink direction (500 units) | 19-quarter pro-forma positive residue | Mean quarterly value ($/unit) | Median quarterly value ($/unit) | Peak quarter ($/unit) | Trough quarter ($/unit) |
|---|---:|---:|---:|---:|---:|
| `VICTAS` (VIC → TAS) | {{bl_tot_disp_VICTAS}} | {{bl_mean_disp_VICTAS}} | {{bl_med_disp_VICTAS}} | $102,299 (`2025 Q1`) | $9,445 (`2022 Q2`) |
| `TASVIC` (TAS → VIC) | {{bl_tot_disp_TASVIC}} | {{bl_mean_disp_TASVIC}} | {{bl_med_disp_TASVIC}} | $61,764 (`2023 Q2`) | $1,537 (`2026 Q1`) |

> [!WARNING]
> **Critical Caveat: MNSP Bidding Behaviour Versus Regulated Free-Flow Dispatch**
> The pro-forma Basslink numbers above ({{bl_mean_disp_VICTAS}} mean on `VICTAS` and {{bl_mean_disp_TASVIC}} mean on `TASVIC`) are an **indicative historical scale check, not a direct regulated forecast**. Under MNSP operation, Basslink bid strategically into NEMDE to maximise its own merchant arbitrage revenue, deliberately withholding capacity during low-spread or negative-residue hours and keeping counter-price losses near zero. Once converted to a regulated interconnector, Basslink dispatches automatically down to zero marginal spread subject to thermal and dynamic cable limits, which will simultaneously increase flow volume during moderate-spread hours (raising gross transfer energy), tighten regional price convergence between Victoria and Tasmania (compressing spreads), and expose the link to occasional counter-price negative residues subject to NRM clamping. Treat the pro-forma backcast strictly as a starting diagnostic while calibrating explicit regulated dispatch elasticity in Stage 3.
