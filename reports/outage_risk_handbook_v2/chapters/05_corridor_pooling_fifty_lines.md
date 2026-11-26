## Chapter 5 · Hierarchical Corridor Pooling Across Fifty Transmission Lines

Asset-specific outage research faces an unavoidable statistical dilemma: the transmission lines that matter most to regional security and market risk rarely fail or go on outage dozens of times per year. Across the 50-line transmission cohort audited in the prior line-outage campaign (631 verified outage events spanning NSW, VIC, QLD, SA, and TAS), individual lines range from 35 to 69 events (such as Alcoa Portland-Heywood 500 kV Line 2 and Mt Beauty-West Kiewa 220 kV) down to just 2 to 5 events (such as Capital-Canberra Line 6 with 2 events, Stockdill-Canberra 3C with 4 events, and Cowra-Forbes 998 with 5 events).

In the legacy line-outage study, enforcing ultra-strict exact-matching gates on binary extreme-price indicators (`spike300`, `tail99`) left almost every mainland line with withheld estimates (`match_rate = 0.0`, `effect = NaN`), reducing the deliverable to descriptive tables without quantitative cross-line ranking. Conversely, relying on unshrunk raw averages for low-event lines invites severe small-sample noise: if one of a line's four outages happened to coincide with a $17,500/MWh evening scarcity spike, its raw average price effect jumps to +$398/MWh even if the line itself barely moved interconnector headroom.

### 5.1 Electrically coherent regional corridors and Empirical-Bayes partial pooling

To achieve complete 50-line analytical coverage while respecting finite-sample uncertainty, we replace binary withheld screens with continuous same-season, same-time-of-day matched outcomes across all 50 lines (regional price delta in $/MWh, primary interconnector worst directional capacity delta in MW, primary border spread delta in $/MWh, and clean binding marginal value severity excluding synthetic linear-programme penalty rows above $30,000/MWh), and then apply hierarchical Empirical-Bayes (James-Stein) partial pooling inside eight electrically coherent regional corridors.

{{diagram:corridorPooling}}

Within each corridor $c$, every line $i$ with raw continuous estimate $\hat{\theta}_i$ and day-clustered standard error $s_i$ (scaled by finite-sample degrees-of-freedom factor $\sqrt{\max(1, 6/n_i)}$ for low-event lines) is shrunk toward the inverse-variance-weighted corridor mean $\mu_c$:

$$\hat{\theta}^{\text{EB}}_i = w_i \hat{\theta}_i + (1 - w_i) \mu_c, \qquad w_i = \frac{\tau_c^2}{\tau_c^2 + s_{i,\text{adj}}^2}$$

where $\tau_c^2$ is the empirical between-line variance within corridor $c$. Lines with high event counts and tight standard errors receive weights $w_i$ of 0.85 to 0.99 and retain their individual physical signature; noisy low-event lines receive smaller weights and borrow statistical strength cleanly from their immediate electrical neighbours on the same regional backbone.

### 5.2 Eight-corridor risk hierarchy across the NEM

Aggregating the 50 monitored transmission lines into eight regional corridors reveals a sharp physical separation between corridors that slash interconnector capacity deepest and corridors that separate regional prices widest.

| Regional transmission corridor | Lines | Total events | Outage hours | Mean EB Cap delta (MW) | Mean EB Spread delta ($/MWh) | Mean EB Regional price delta ($/MWh) | Total binding intervals | Max clean median \|MV\| ($/MWh) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| SA Heywood & Mid-North 275 kV | 6 | 94 | 2,992 | **-179** | **+$17.4** | -$4.1 | 18,564 | $1,218 |
| VIC Metro & Latrobe 500 kV | 5 | 114 | 420 | -174 | -$17.5 | -$30.8 | 0 | n/a |
| NSW Central & Sydney Ring | 4 | 45 | 4,006 | -157 | **+$16.4** | **+$29.2** | 2,293 | $1,084 |
| NSW Northern & QNI 330 kV | 5 | 58 | 1,939 | -156 | +$3.9 | -$12.4 | 7,577 | $1,222 |
| NSW Southern & Snowy 330/500 kV | 11 | 67 | 4,855 | -125 | -$15.5 | -$33.8 | 10,971 | $1,383 |
| TAS North-South 220 kV | 8 | 82 | 2,194 | -104 | -$28.2 | -$2.1 | 78 | $155 |
| VIC Western & Border 220/500 kV | 2 | 43 | 499 | -81 | -$14.9 | -$14.9 | 2,635 | $1,084 |
| QLD Central & Southern 275 kV | 9 | 128 | 5,756 | -70 | +$0.1 | -$6.5 | 20,986 | $1,178 |

{{exhibit:b8}}

Three structural takeaways stand out from the eight-corridor synthesis:

1. **SA Heywood & Mid-North 275 kV is the single sharpest physical and spread-widening corridor (-179 MW, +$17.4/MWh spread):** Anchored by Tailem Bend-South East 275 kV Lines 1 and 2 (`S_EAST/LINE/TABSES_1` with 24 events and -263 MW EB cap drop / +$63.9/MWh EB spread widening; `S_EAST/LINE/TABSES_2` with 18 events and -279 MW EB cap drop), this six-line South Australian spine logged 18,564 binding constraint intervals with clean median shadow prices up to $1,218/MWh.
2. **NSW Central & Sydney Ring and NSW Northern & QNI 330 kV drive positive regional price risk:** Across NSW Central & Sydney Ring (4 lines, 4,006 outage hours), Empirical-Bayes pooled regional prices average **+$29.2/MWh** and border spreads **+$16.4/MWh**, while NSW Northern & QNI 330 kV (led by `ARMIDALE/LINE/86` at -184 MW EB cap drop / +$19.1/MWh spread and `ARMIDALE/LINE/87` at -187 MW EB cap drop) averages -156 MW capacity contraction across 7,577 binding intervals.
3. **NSW Southern & Snowy 330/500 kV carries the highest binding marginal value ($1,383/MWh) alongside mild-season scheduling bias:** Across 11 Southern NSW lines (4,855 outage hours and 10,971 binding intervals), average EB capacity drops reach **-125 MW**, led by `MARULAN/LINE/5` (-219 MW EB cap drop, +$18.6/MWh EB spread widening, 5,941 binding intervals) and `CANBERRA/LINE/07` (-163 MW EB cap drop, 2,136 binding intervals). Notice that the corridor mean regional price delta is negative (-$33.8/MWh), reflecting the strong shoulder-season and daytime maintenance scheduling effect discussed in Chapter 1, even while individual binding constraints carry $1,000 to $1,383/MWh shadow prices when evening load or wind swings collide with the outage.

### 5.3 How Empirical-Bayes shrinkage rescues noisy outliers

Comparing raw single-line estimates against Empirical-Bayes corridor-pooled estimates across all 50 transmission lines demonstrates exactly why hierarchical shrinkage outperforms both unshrunk point estimates and wholesale data withholding.

{{exhibit:b9}}

Two concrete examples from the 50-line register prove the point:
- **`COWRA/LINE/998` (5 events, 46.3 outage hours):** Because one single 46-hour window coincided with a $17,500/MWh NSW price spike, its raw regional price effect surged to **+$397.6/MWh** (with a large day-clustered standard error of $474.1/MWh) and its raw VNI capacity delta hit -482 MW. Empirical-Bayes pooling automatically assigns a low 2.7% weight to the noisy price spike, shrinking it to a realistic **+$19.7/MWh**, while keeping a 63.3% weight on the much tighter capacity drop (**-355 MW**).
- **`STOCKDIL/LINE/3C` (4 events, 29.1 outage hours):** One $17,500/MWh spike inflated its raw NSW price effect to **+$120.0/MWh** (SE $116.0/MWh) and raw capacity drop to -488 MW (SE 127.9 MW). Corridor pooling assigns just 5.4% price weight and 33.5% capacity weight, pulling the estimate cleanly back to **-$39.0/MWh** and **-236 MW**.
- By contrast, high-precision, multi-event backbone lines such as `S_EAST/LINE/TABSES_1` (24 events, 91.0% capacity weight, -263 MW EB vs -269 MW raw) and `MARULAN/LINE/5` (11 events, 94.8% capacity weight, -219 MW EB vs -225 MW raw) barely move at all, preserving their exact asset-specific physical signatures.

Use the searchable 50-line directory below to inspect every line's region, corridor, event count, raw versus Empirical-Bayes pooled capacity drop, spread delta, and maximum clean binding marginal value.

{{interactive:line50Directory}}

Chapter 6 now zooms directly into the two mandatory focus assets inside the Southern NSW 330 kV corridor: Capital-Canberra Line 6 and Dapto-Marulan Line 8.
