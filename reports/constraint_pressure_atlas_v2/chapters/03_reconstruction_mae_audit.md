## Chapter 3 · Root-Cause Audit of Envelope Reconstruction Error

Before using constraint-equation sensitivities to attribute generator pressure or engineer forecasting features, a quantitative team must know when the reconstructed linear-programme envelope matches AEMO's published interconnector limits and when it diverges. Early multi-link diagnostics revealed an unsettling disparity: across the two-year sample, VNI forward limit reconstruction achieved a mean absolute error (MAE) of just 6.8 MW (with a median error effectively indistinguishable from floating-point zero at $2.3 \times 10^{-13}\text{ MW}$), yet QNI forward limits exhibited a reconstruction MAE of 409.8 MW, QNI reverse showed 248.4 MW, and Heywood showed 126.8 MW forward and 129.3 MW reverse. On the HVDC links, the gap grew wider still, reaching 8,737.7 MW on Directlink forward and 3,515.0 MW on Basslink forward.

Without a formal root-cause audit, a desk analyst might reasonably worry that the reconstruction pipeline contains a sign error, a broken unit factor, or corrupted SCADA inputs on QNI and Heywood. A systematic interval-by-interval audit across all 1,261,440 link-intervals resolves the mystery completely and produces a clean, actionable reliability rule for downstream modelling.

### 3.1 The decisive binary split: matched versus unmatched setter equations

In every five-minute dispatch interval, AEMO reports not only the numerical export and import limit but also the identity of the specific constraint equation that set each directional bound (the reported setter equation). Auditing reconstruction error conditional on whether that exact reported setter equation is present and matched in the reconstructed standing-equation candidate set reveals a striking binary result:

- **When the reported setter equation matches the reconstructed candidate set (`setter_matched = True`):** Reconstruction error collapses to numerical machine precision across *every single interconnector and every constraint family*. On VNI, matched thermal, voltage stability, transient stability, and ramp equations all record MAE below **0.00002 MW**. On QNI, matched thermal equations (36,213 forward intervals and 49,258 reverse intervals) record MAE of **0.000006 MW** and **0.000004 MW** respectively. Even on Heywood, Murraylink, Directlink, and Basslink, matched intervals show MAE under **0.0013 MW**.
- **When the reported setter equation is absent from the reconstructed candidate set (`setter_matched = False`):** **100%** of the material reconstruction MAE on VNI, QNI, Heywood, Directlink, Murraylink, and Basslink arises exclusively inside unmatched intervals.

There is no algebraic bug in the linear-programme factor reconstruction. Rather, the MAE disparity across links reflects exact structural differences in how often AEMO sets each corridor's published bound using equations outside the standard single-interconnector energy-equation formulation.

### 3.2 Decomposing MAE across all six interconnectors by setter family

| Link & direction | Setter match rate (%) | Total MAE (MW) | Median error (MW) | Leading unmatched setter family | Family interval share (%) | Family conditional MAE (MW) | Family MAE contribution (MW) |
|---|---:|---:|---:|---|---:|---:|---:|
| VNI forward | 94.8% | 6.8 | 0.0 | Voltage Stability | 0.7% | 399.0 | 2.7 |
| VNI reverse | 95.2% | 22.6 | 0.0 | NRM / Discretionary | 2.7% | 808.1 | 22.2 |
| QNI forward | 21.7% | 409.8 | 284.1 | Transient Stability | 48.1% | 365.1 | 175.5 |
| QNI reverse | 33.2% | 248.4 | 96.7 | ROCOF / UFLS / FCAS | 19.7% | 726.0 | 143.2 |
| Heywood forward | 71.5% | 126.8 | 0.0 | ROCOF / UFLS / FCAS | 6.5% | 922.6 | 60.2 |
| Heywood reverse | 75.4% | 129.3 | 0.0 | ROCOF / UFLS / FCAS | 7.5% | 1,044.2 | 78.1 |
| Directlink forward | 0.9% | 8,737.7 | 10,228.1 | Other (MNSP / cable) | 51.8% | 9,044.3 | 4,689.3 |
| Directlink reverse | 12.0% | 279.5 | 204.8 | Other (MNSP / cable) | 80.3% | 306.8 | 246.3 |
| Murraylink forward | 28.2% | 72.1 | 66.6 | Other (MNSP / local) | 43.9% | 121.1 | 53.2 |
| Murraylink reverse | 30.3% | 94.8 | 71.7 | Other (MNSP / local) | 63.8% | 146.8 | 93.6 |
| Basslink forward | 0.0% | 3,515.0 | 831.9 | Other (MNSP / cable) | 60.0% | 5,271.8 | 3,165.4 |
| Basslink reverse | 0.7% | 3,439.7 | 1,023.8 | Other (MNSP / cable) | 52.0% | 5,275.0 | 2,740.9 |

{{exhibit:a3}}

Examining each corridor's unmatched residuals reveals four distinct operational mechanisms that explain the entire error profile:

#### 3.2.1 VNI: high structural fidelity (95% matched), isolated NRM and stability misses
VNI achieves exact setter matching in 94.8% of forward intervals and 95.2% of reverse intervals. On VNI forward, the tiny 6.8 MW aggregate MAE splits almost entirely between 0.7% unmatched voltage-stability intervals (contributing 2.7 MW), 3.1% unmatched transient-stability intervals (2.6 MW), and 0.7% unmatched thermal intervals (1.2 MW). On VNI reverse, 98% of the 22.6 MW MAE comes from a single narrow bucket: 5,738 unmatched NRM and system-normal discretionary intervals (2.7% of the sample, averaging 808.1 MW residual error when AEMO invokes dynamic negative-residue clamping whose live right-hand side is overridden inside the dispatch engine outside standard standing energy factors). Excluding those 2.7% discretionary overrides, VNI's constraint envelope is reconstructed to near-exact precision across the two-year horizon.

#### 3.2.2 QNI: coupled FCAS/ROCOF equations and dynamic stability overrides
Why does QNI's exact setter match rate fall to 21.7% forward and 33.2% reverse? Three specific equation families account for over 94% of QNI's reconstruction error:

1. **Unmatched Transient Stability equations on QNI forward (48.1% of intervals, 175.5 MW MAE contribution):** Nearly half of all five-minute intervals on QNI forward are governed by Queensland-NSW transient stability formulations (including dynamic headroom and parallel-flow equations) whose effective interconnector factor or multi-interconnector coupling is not captured by a single-link energy equation without co-solving Directlink and Queensland inertia states.
2. **Unmatched ROCOF, UFLS, and FCAS co-optimisation equations (19.7% of QNI reverse intervals contributing 143.2 MW MAE; 10.0% of QNI forward intervals contributing 114.9 MW MAE):** Joint energy-and-FCAS constraints include both interconnector flow $F_t$ and regional Raise/Lower FCAS enablement terms inside the same inequality (for example, protecting Queensland against credible islanding events by capping transfer as a function of available fast-raise FCAS). Because the energy-only reconstruction treats FCAS terms as part of a residual $Z$-term rather than co-optimising the FCAS simplex, the implied energy-only conditional bound diverges systematically by 726 MW to 1,154 MW whenever a coupled FCAS equation sets the published QNI limit.
3. **Unmatched Voltage Stability equations (38.8% of QNI reverse intervals contributing 78.1 MW MAE; 16.5% of QNI forward intervals contributing 94.3 MW MAE):** Many Queensland-NSW voltage stability equations depend on dynamic synchronous-condenser, reactive-power, or multi-bus voltage indices whose standing LHS records differ from the live dispatch version or couple QNI with Directlink.

Crucially, whenever QNI is bounded by standard Thermal equations (17.3% of forward intervals and 23.5% of reverse intervals), exact setter match is achieved over 96% of the time and reconstruction error drops to 0.000005 MW.

#### 3.2.3 Heywood: 71% to 75% exact match, with ROCOF and transient stability driving the residual
Heywood sits cleanly between VNI and QNI. Exact setter matching reaches 71.5% forward and 75.4% reverse, leaving a 0.0 MW median error in both directions. Over 70% of the 126.8 MW forward MAE and 129.3 MW reverse MAE stems from just two unmatched buckets: South Australian ROCOF / UFLS / FCAS islanding constraints (6.5% forward share contributing 60.2 MW MAE; 7.5% reverse share contributing 78.1 MW MAE) and Transient Stability formulations (14.1% forward share contributing 31.1 MW MAE; 12.1% reverse share contributing 15.7 MW MAE), including South East to Tailem Bend series-capacitor dynamic limits and synchronous-generator count rules in South Australia. When Heywood operates under matched thermal, voltage-stability, or standard discretionary bounds, reconstruction is exact to five decimal places.

#### 3.2.4 Directlink, Murraylink, and Basslink: why HVDC MAE rises sharply to 3,500 to 8,700 MW
The multi-thousand-megawatt MAE numbers on Directlink forward (8,737.7 MW) and Basslink (3,515.0 MW forward, 3,439.7 MW reverse) illustrate a vital modelling lesson rather than a pipeline defect. HVDC cables are not passive alternating-current impedance paths; their transfer limits are frequently governed by Market Network Service Provider (MNSP) energy bids, cable thermal ratings, inverter runback logic, or FCSPS protection rules rather than generic AC constraint equations. When no generic AC equation with an active interconnector coefficient restricts flow, the solver's default generic-equation envelope defaults to a large unconstrained ceiling (typically 10,000 MW or the sum of non-binding AC constraints), whereas AEMO's published export or import limit reflects the physical 180 MW Directlink or 478 to 594 MW Basslink cable cap. Subtracting a 10,000 MW unconstrained generic-equation ceiling from a 47 MW cable limit immediately creates an 8,700 MW residual.

Murraylink shows a hybrid profile (28.2% to 30.3% exact match, 72.1 to 94.8 MW MAE) because it operates as a regulated HVDC link whose local 132 kV and 220 kV thermal and voltage limits frequently appear as standard generic constraints alongside non-generic cable and runback caps.

### 3.3 Operational quarantine rule for forecasting and attribution

> [!TAKEAWAY] Practical Rule for Quant and Desk Workflows
> Never feed raw reconstructed envelope bounds blindly into a forecasting feature matrix or generator attribution ranking on QNI, Heywood, Directlink, or Basslink. Always propagate the binary `setter_matched` flag and setter-family label alongside every five-minute interval:
> 1. Tier 1 (Exact linear-programme attribution): Use exact generator sensitivities $s_{c,i,t} = -b_{c,i,t}/a_{c,t}$ strictly on intervals with `setter_matched = True` (95% of VNI, 72% to 75% of Heywood, 22% to 33% of QNI, and 28% to 30% of Murraylink).
> 2. Tier 2 (Published-limit regime modelling): On unmatched ROCOF/FCAS, dynamic stability, and HVDC cable intervals, model AEMO's published directional limit directly using system-state predictors (synchronous unit counts, inertia, FCAS enablement, cable availability, and NRM flags) rather than attempting single-link linear-programme reconstruction.

With the reliability boundary of every corridor cleanly mapped, Part II turns to the physical and seasonal dynamics of the published directional limits themselves: diurnal regimes with formal uncertainty bounds, full-population contraction decomposition, and cross-corridor contagion.
