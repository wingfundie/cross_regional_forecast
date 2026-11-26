## Chapter 7 · Economic Versus Mechanical Generator and Constraint Influence

A persistent flaw in legacy constraint-pressure research is the megawatts-without-dollars disconnect. Ranking generators by summing every five-minute move $|s_{c,i,t} \Delta P_{i,t}|$ across two years treats a 100 MW cloud ripple on a midday solar farm during an unconstrained $2/MWh afternoon identically to a 100 MW evening ramp on a Snowy hydro turbine during a binding $450/MWh peak. Similarly, ranking constraint equations by how many intervals they sat as the tightest non-binding leader conflates harmless idle ceilings with the handful of thermal, voltage, and stability equations that carry hundreds or thousands of dollars per megawatt-hour in binding shadow prices.

Re-weighting the exact same two-year five-minute unit-pressure and constraint-population panels by tight-headroom congestion rent ($H_{k,t} \le 50\text{ MW}$ multiplied by positive directional regional price spread divided by 12) and cumulative binding shadow rent reshuffles the leaderboard on every single interconnector in the NEM.

### 7.1 How economic weighting reshuffles the generator leaderboard

Across all 446 active participating generating units, weighting mechanical constraint moves by concurrent tight-headroom congestion rent produces dramatic rank promotions for dispatchable hydro, gas peakers, utility batteries, and wind farms situated behind high-spread evening bottlenecks, while demoting slack-hour solar and baseload units whose mechanical movements occur mostly when regional prices are converged.

| Interconnector | #1 Mechanical unit (all MW-obs) | #1 Economic unit (rent-weighted) | Tech | Rent-weighted pressure ($m) | Rank shift (econ vs mech) | Tight-headroom share (%) | Evening Ramp share (%) |
|---|---|---|---|---:|---:|---:|---:|
| VNI | `MURRAY` (Hydro) | `TUMUT3` | Hydro | $103.7m | +2 (#3 to #1) | 45.9% | 63.0% |
| QNI | `NEWENSF2` (Solar) | `TUMUT3` | Hydro | $82.4m | +5 (#6 to #1) | 62.5% | 54.5% |
| Heywood | `KIAMSF1` (Solar) | `KESSB1` | BESS | $6.0m | +4 (#5 to #1) | 56.6% | 18.1% |
| Directlink | `METZSF1` (Solar) | `TUMUT3` | Hydro | $85.8m | +1 (#2 to #1) | 89.9% | 46.4% |
| Murraylink | `MURRAY` (Hydro) | `LIMOSF11` | Solar | $5.8m | +2 (#3 to #1) | 90.9% | 19.2% |
| Basslink | `MREHA3` (BESS) | `MREHA3` | BESS | $3.0m | +0 (#1 to #1) | 28.3% | 22.3% |

{{exhibit:a9}}

The structural reshuffling inside each of the three flagship AC corridors illustrates why trading desks cannot rely on unweighted mechanical counts:

#### 7.1.1 VNI: Tumut 3 and Upper Tumut overtake Murray, while gas peakers and NSW wind jump 25 to 64 ranks
On a pure mechanical basis, `MURRAY` (Snowy Hydro's Victorian-side power station) sits at #1 on VNI with 9.40 million cumulative MW-observations, ahead of `LIMOSF11` (#2) and `TUMUT3` (#3). Once weighted by tight-headroom congestion rent, `MURRAY` drops thirteen places to #14 ($9.76m), because only 18.6% of Murray's mechanical constraint movement occurs during tight-headroom intervals. By contrast, `TUMUT3` surges to #1 with $103.7m (nearly three times larger than #2 `UPPTUMUT` at $34.8m and #3 `LIMOSF11` at $29.4m), because 45.9% of Tumut 3's movement occurs under tight headroom and 63.0% concentrates inside the high-spread Evening Ramp (16:00 to 20:55).

Even sharper rank jumps appear among southern New South Wales wind farms, gas peakers, and grid-scale batteries that enter outage and evening-peak equations:
- `RYEPARK1` (wind) jumps +45 ranks from #52 mechanical to #7 economic ($13.8m), with 68.8% of its moves inside tight headroom and 41.4% in the Evening Ramp.
- `COLWF01` (wind) climbs +52 ranks (#67 to #15, $9.1m) and `BOCORWF1` climbs +64 ranks (#92 to #28, $5.5m).
- The Uranquinty gas peakers (`URANQ13`, `URANQ11`, `URANQ14`, `URANQ12`) jump +23 to +31 ranks into the top 30 economic drivers ($5.2m to $7.5m each), driven by 56% to 66% Evening Ramp concentration precisely when NSW minus VIC spreads spike.
- Meanwhile, Victorian-side wind farms that sit on slack equations suffer steep demotions: `MUWAWF1` falls -34 ranks (#8 to #42, $3.1m), `MOORAWF1` falls -25 ranks (#20 to #45, $2.8m), and `KIAMSF1` falls -22 ranks (#11 to #33, $4.9m).

#### 7.1.2 QNI and Directlink: NSW spine hydro and wind displace New England solar
On QNI, unweighted mechanical rankings placed the New England solar farms `NEWENSF2` (#1), `NEWENSF1` (#2), `SAPHWF1` (#3), and `METZSF1` (#5) at the top of the table. Economic weighting demotes `NEWENSF2` by -7 places to #8 ($7.9m), `NEWENSF1` by -8 places to #10 ($7.3m), `METZSF1` by -14 places to #19 ($5.7m), and `SAPHWF1` by -31 places to #34 ($3.5m), because only 18% to 25% of their solar midday oscillations coincide with tight QNI headroom.

In their place, `TUMUT3` rises +5 places to #1 on QNI ($82.4m) and `UPPTUMUT` rises +10 places to #2 ($22.3m), followed by NSW wind farms `RYEPARK1` (+27 ranks to #3, $14.9m) and `COLWF01` (+48 ranks to #4, $12.2m) and south-west NSW solar `DARLSF1` (+33 ranks to #5, $10.8m). The reason Snowy and southern NSW units dominate QNI economic rent is subtle and commercially decisive: when NSW evening scarcity binds both NSW borders simultaneously via system-wide NSW stability and voltage equations, Snowy hydro and southern NSW generation shifts directly govern the high-spread intervals on QNI and Directlink (`TUMUT3` is also #1 economic on Directlink at $85.8m, with 89.9% tight-headroom coincidence).

#### 7.1.3 Heywood, Murraylink, and Basslink: grid-scale batteries take the #1 spot
Along the southern and subsea borders, battery energy storage systems have already overtaken legacy solar and wind farms as the #1 economic constraint influencers. On Heywood (V-SA), `KESSB1` (Koorangie / Kerang-corridor BESS) jumps +4 places from #5 mechanical to #1 economic ($6.0m) ahead of `KIAMSF1` (#2, $4.7m), `WEMENSF1` (#3, $4.3m), `BANN1` (#4, $4.2m), and `MUWAWF1` (#5, $4.1m), while `VBB1` (Victorian Big Battery) leaps +16 places to #7 ($3.5m), `LIMBESS1` leaps +42 places to #13 ($2.7m), and South Australian `TB2B1` leaps +63 places to #18 ($2.0m). On Basslink, the Melbourne Renewable Energy Hub battery units `MREHA3` (#1, $3.0m), `VBB1` (#2, $1.4m), `MREHA1` (#3, $1.2m), and `MREHA2` (#5, $1.1m) occupy four of the top five economic slots ahead of `MURRAY` (#6, $0.85m). On Murraylink, south-western NSW solar (`LIMOSF11` #1 at $5.8m, `CUSF1` #2 at $5.5m) shares the top tier with `MURRAY` (#3, $5.0m) and Victorian batteries `KESSB1` (#4, +20 ranks, $4.6m) and `VBB1` (#6, +45 ranks, $3.9m).

{{interactive:duidDirectory}}

### 7.2 The shadow-rent constraint register: separating real bottlenecks from paper leaders

Applying the same economic discipline to constraint equations (ranking by cumulative 24-month binding shadow rent, equal to binding intervals multiplied by mean absolute marginal value divided by 12, after removing synthetic zero-flow linear-programme penalty constraints) reveals an equally stark divergence from non-binding leader counts.

{{exhibit:a10}}

| Link | Top shadow-rent constraint ID | Direction | Category | Binding intervals | Leading intervals | Mean \|MV\| ($/MWh) | 24m shadow rent ($k/MW) | Physical bottleneck |
|---|---|---|---|---:|---:|---:|---:|---|
| Directlink | `N_X_MBTE_3A` | Reverse | Other / MNSP | 13,115 | 0 | $3,939.3 | $4,305k | Northern NSW Directlink transfer bound |
| Murraylink | `SVML_ROC_80` | Reverse | ROCOF / HVDC | 3,059 | 0 | $12,325.5 | $3,142k | SA-VIC Murraylink rate-of-change bound |
| Murraylink | `V^SML_BUDP_3` | Forward | Voltage Stab. | 4,688 | 8,152 | $2,261.8 | $884k | Buronga-Balranald/Darlington Pt 220 kV outage voltage collapse |
| QNI | `N^^Q_TW_330_BUS1_B1` | Reverse | Voltage Stab. | 810 | 0 | $7,307.6 | $493k | Tamworth 330 kV Bus 1 outage voltage limit |
| Murraylink | `S>NIL_MHNW1_MHNW2` | Reverse | Thermal | 42,794 | 0 | $132.6 | $473k | Monash to North West Bend 132 kV system-normal thermal |
| VNI | `N>>NIL_060_051` | Reverse | Thermal | 17,567 | 594 | $182.8 | $268k | Jindera-Wodonga (60) 330 kV for trip of Wagga-Lower Tumut (051) |
| Heywood | `V::S_SETB_TBSE_2` | Forward | Transient Stab. | 2,580 | 0 | $873.7 | $188k | South East-Tailem Bend 275 kV outage transient stability |
| Heywood | `VS_600_TEST` | Forward | Other / Test | 8,048 | 19,876 | $271.0 | $182k | Heywood 600 MW upgrade testing cap |
| VNI | `N>>BDBU_970_051` | Forward | Thermal | 4,865 | 5,266 | $381.3 | $155k | Bundey-Buronga (6F) outage; Burrinjuck-Yass (970) thermal |
| Basslink | `V_T_NIL_FCSPS` | Reverse | Other / FCSPS | 27,936 | 0 | $44.5 | $104k | Basslink VIC to TAS FCSPS load-enabled cap |
| QNI | `NRM_QLD1_NSW1` | Reverse | NRM | 752 | 7 | $1,542.1 | $97k | Negative Residue Management QLD to NSW clamp |
| QNI | `QN+RAISE_NIL` | Reverse | FCAS | 1,700 | 48,446 | $682.0 | $97k | QLD to NSW FCAS raise enablement for loss of 750 MW NSW unit |

Look closely at the contrast between the `Binding intervals` and `Leading intervals` columns in the table above. On QNI, `QN+RAISE_NIL` led the conditional envelope for 48,446 intervals, yet it actually bound in only 1,700 intervals, generating $96.6k/MW of shadow rent. Meanwhile, the Tamworth 330 kV Bus 1 voltage outage equation `N^^Q_TW_330_BUS1_B1` bound for only 810 intervals (less than 0.4% of the two-year sample), yet carried a mean marginal value of $7,307.6/MWh, generating $493.3k/MW of shadow rent, more than five times higher than the perennial leader `QN+RAISE_NIL`.

The exact same asymmetry governs VNI and Heywood:
- On VNI, system-normal `N>>NIL_060_051` (Jindera-Wodonga thermal) generated $267.6k/MW across 17,567 binding intervals, followed by the Bundey-Buronga 6F outage thermal equation `N>>BDBU_970_051` ($154.6k/MW, $381.3/MWh mean `|MV|`), the Lower Tumut-Yass (03) outage transient-stability equation `N::N_LTYS_2` ($69.2k/MW, $1,503.7/MWh mean `|MV|` in just 552 intervals), and system-normal Wagga-Lower Tumut voltage stability `N^^N_NIL_WGLT` ($32.7k/MW across 12,576 binding intervals).
- On Heywood, the EnergyConnect commissioning discretionary cap `I_6F_SN_150` (150 MW Bundey to Buronga 6F limit) led the reverse envelope for 73,858 intervals, yet bound for 3,442 intervals ($59.2k/MW), whereas the South East to Tailem Bend 275 kV outage transient-stability equation `V::S_SETB_TBSE_2` bound for 2,580 intervals at $873.7/MWh mean `|MV|` to generate $187.8k/MW, and the Heywood 600 MW test cap `VS_600_TEST` generated $181.7k/MW across 8,048 binding intervals.

{{interactive:constraintDirectory}}

> [!TAKEAWAY] Commercial Principle for Desk Monitoring
> Frequent non-binding leaders tell engineers which boundary sits closest to normal dispatch; cumulative shadow rent tells traders which equations pay or cost real money. Outage-specific voltage and transient stability equations (`N^^Q_TW_330_BUS1_B1`, `V^SML_BUDP_3`, `N>>BDBU_970_051`, `V::S_SETB_TBSE_2`, `N::N_LTYS_2`) routinely generate more shadow rent in 500 to 4,800 outage intervals than system-normal thermal leaders accumulate in 50,000 intervals.

One asset class in the economic leaderboard deserves its own dedicated forensic chapter because its rapid five-minute operational profile breaks the traditional 30-minute ramping assumptions baked into legacy NEM models: utility-scale Battery Energy Storage Systems (BESS). Chapter 8 isolates that exact fast-ramp signature.
