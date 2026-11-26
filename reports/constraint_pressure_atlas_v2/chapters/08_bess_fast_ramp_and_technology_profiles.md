## Chapter 8 · Utility BESS Fast-Ramp Signatures and Technology Profiles

Between 2024 and 2026, grid-scale Battery Energy Storage Systems transitioned from peripheral frequency-control assets into primary drivers of five-minute interconnector constraint physics across the NEM. Unlike coal boilers limited by multi-hour thermal ramp rates, or utility solar farms whose output follows a smooth diurnal arc punctuated by passing clouds, bidirectional batteries execute full-swing reversals from maximum charging to maximum discharging within a single five-minute dispatch interval. A 200 MW battery switching from -180 MW (charging during a negative-price solar dip) to +180 MW (discharging into a tight evening ramp or FCAS contingency) injects a 360 MW net change in five minutes, instantly shifting any thermal or voltage constraint equation in which it carries a material participation factor.

Earlier constraint studies grouped bidirectional units alongside generic "Other" or thermal classes and evaluated generator moves strictly over 30-minute rolling windows. Averaging a battery over 30 minutes hides its defining physical hazard: a battery that charges hard at 17:15, discharges hard at 17:20, and returns to neutral at 17:40 shows near-zero 30-minute net movement while having abruptly rattled a tight interconnector boundary across four consecutive dispatch intervals. By explicitly identifying all bidirectional storage units from standing dispatch registrations and computing five-minute step impulse distributions alongside 30-minute exposure and congestion-rent shares, we isolate the exact BESS footprint across all six corridors.

### 8.1 Technology-class five-minute impulse severity and evening-ramp concentration

Comparing the 95th-percentile five-minute step impulse (`|Δbound|` over a single five-minute interval) and Evening Ramp exposure concentration across all seven technology classes reveals how sharply utility batteries stand apart from thermal and variable renewable fleets.

{{exhibit:a11}}

| Link | Active BESS units | BESS share of all MW-obs (%) | BESS share of rent-weighted pressure (%) | BESS share of contraction-onset tightening (%) | BESS P95 5-min impulse (MW) | Solar P95 5-min impulse (MW) | BESS Evening Ramp share (%) | BESS Solar Midday share (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| VNI | 38 | 9.9% | 7.1% | 8.4% | 24.7 | 27.6 | 30.1% | 44.3% |
| QNI | 34 | 6.8% | 5.2% | 7.6% | 18.2 | 16.2 | 32.8% | 46.6% |
| Heywood | 43 | 12.8% | **20.4%** | **15.1%** | 22.2 | 19.2 | 26.0% | 41.6% |
| Directlink | 27 | 3.0% | 5.2% | 4.0% | 17.4 | 26.9 | 29.9% | 58.8% |
| Murraylink | 41 | 10.2% | **15.9%** | 9.7% | 27.0 | 42.9 | 19.8% | 54.6% |
| Basslink | 26 | **56.4%** | **32.7%** | **55.1%** | **100.0** | 22.4 | 25.3% | 37.9% |

Three empirical findings define the operational role of BESS inside the NEM constraint stack:

#### 8.1.1 Economic punch far exceeds mechanical share on southern corridors
On Heywood (V-SA), 43 active BESS units account for 12.8% of raw mechanical MW-observations, yet generate 20.4% of all congestion-rent-weighted pressure ($22.0m) and 15.1% of all fixed-equation contraction-onset tightening. That 1.6x economic-to-mechanical multiplier reflects arbitrage timing: batteries do not drift randomly; their bidding engines actively seek out the exact tight-headroom price-separation intervals where regional spreads widen, meaning their megawatt swings disproportionately coincide with binding congestion.

The same economic amplification appears on Murraylink (41 active BESS units, 10.2% mechanical share rising to 15.9% rent-weighted share, $20.8m) and Directlink (27 BESS units, 3.0% mechanical share rising to 5.2% rent-weighted share, $22.2m). On Basslink, 26 Victorian BESS units (led by `MREHA3`, `VBB1`, `MREHA1`, `MREHA2`, and `HBESS1`) dominate the generic constraint equations outright, representing 56.4% of all mechanical MW-observations, 55.1% of contraction-onset tightening, and 32.7% of congestion-rent-weighted pressure, with a P95 five-minute impulse of 100.0 MW per step.

#### 8.1.2 Bimodal diurnal footprint: midday charging plus evening discharging
Every legacy technology in the NEM exhibits a unimodal diurnal profile: solar peaks overwhelmingly during Solar Midday (52% to 61% of its constraint pressure), gas peakers peak overwhelmingly in the Evening Ramp (52% to 60% on VNI, QNI, and Directlink), and hydro concentrates in the Evening Ramp (40% to 47% on VNI, QNI, Directlink, and Basslink). Grid-scale batteries are uniquely bimodal. Across VNI, QNI, Heywood, and Directlink, BESS units deliver 42% to 59% of their constraint pressure during Solar Midday (rapidly ramping into and out of negative-price charging as solar prices flip across $0/MWh) and a second large wave of 26% to 33% during the Evening Ramp (executing high-margin discharge ramps into regional scarcity).

Because battery charging carries a negative generation sign ($P_{i,t} < 0$), a battery entering a thermal equation on the congested exporting side actually *relieves* the interconnector limit while charging at noon, and then *double-tightens* the limit at 16:30 when it first stops charging (removing counter-flow relief) and immediately switches to discharging (adding forward loop flow). That sign reversal across zero explains why units like `KESSB1` on Heywood (P95 5-min impulse 22.2 MW, #1 economic rank), `VBB1` on Heywood and Murraylink, and `RIVNB2` / `RESS1` on VNI (#11 and #12 economic at $10.4m and $10.3m) sit at the very heart of intraday limit volatility.

### 8.2 Technology-class composition of congestion-rent pressure across all six links

Stepping back from batteries alone, comparing the full seven-technology breakdown of congestion-rent-weighted pressure across all six interconnectors exposes the distinct regional fuel mix driving economic congestion along each border.

{{exhibit:a12}}

| Link | Solar rent share (%) | Hydro rent share (%) | Wind rent share (%) | BESS rent share (%) | Coal rent share (%) | Gas rent share (%) | Total 24m rent weight ($m) |
|---|---:|---:|---:|---:|---:|---:|---:|
| VNI | **39.9%** | **26.7%** | 19.7% | 7.1% | 1.5% | 4.5% | $586.6m |
| QNI | **33.4%** | **24.2%** | 22.2% | 5.2% | 6.1% | 4.2% | $450.4m |
| Heywood | 30.5% | 2.4% | **44.6%** | **20.4%** | 0.7% | 1.0% | $107.8m |
| Directlink | **32.3%** | **26.3%** | 22.5% | 5.2% | 4.8% | 4.9% | $426.7m |
| Murraylink | **45.1%** | 6.4% | **29.3%** | **15.9%** | 0.9% | 2.2% | $130.9m |
| Basslink | 27.0% | 8.8% | 28.7% | **32.7%** | 2.0% | 0.1% | $27.7m |

Four regional economic signatures emerge cleanly from the six-link technology stack:

1. **VNI is a Solar + Hydro + Wind triad (86.3% combined):** Utility solar accounts for **39.9%** ($234.1m) of rent-weighted pressure (concentrated in the Riverina and south-western NSW solar belt: Limondale, Sunraysia, Darlington Point, Avonlie, Coleambally, Finley, Hillston), Snowy hydro contributes **26.7%** ($156.7m, led by Tumut 3 and Upper Tumut), and wind adds **19.7%** ($115.3m). Coal units account for just **1.5%** of VNI economic pressure, while gas peakers contribute **4.5%** ($26.5m, concentrated almost entirely during evening scarcity).
2. **QNI and Directlink mirror the NSW spine triad, with Queensland coal demoted economically:** On QNI, coal accounts for **20.0%** of raw mechanical MW-observations (driven by Stanwell, Gladstone, Callide, and Mount Piper ramping), yet drops to just **6.1%** ($27.4m) of congestion-rent-weighted pressure. Instead, Solar (**33.4%**, $150.5m), Hydro (**24.2%**, $109.1m), and Wind (**22.2%**, $99.9m) account for **79.8%** of QNI economic pressure, closely echoed on parallel Directlink (32.3% Solar, 26.3% Hydro, 22.5% Wind).
3. **Heywood and Murraylink are the Wind + Solar + BESS frontier (90% to 95% combined):** Along the Victoria to South Australia border, thermal coal and gas contribute less than **3.1%** of economic pressure combined. On **Heywood**, Wind (**44.6%**), Solar (**30.5%**), and BESS (**20.4%**) drive **95.5%** of all rent-weighted pressure. On **Murraylink**, Solar (**45.1%**), Wind (**29.3%**), and BESS (**15.9%**) drive **90.3%**. Any forecasting or valuation model for VIC to SA interconnector limits that treats thermal baseload as the dominant network driver is modelling the 2015 grid rather than the 2026 grid.
4. **Basslink's generic-equation pressure is split three ways across BESS (32.7%), Wind (28.7%), and Solar (27.0%):** Even though Tasmania is a hydro-dominated state, the Victorian-side AC constraint equations that intersect Basslink are overwhelmingly driven by Victorian grid-scale batteries (`MREHA3`, `VBB1`, `MREHA1`, `MREHA2`, `HBESS1`), western Victorian wind, and northern Victorian solar, with hydro contributing **8.8%** (carrying a very high 115.2 MW P95 five-minute step impulse when Tasmanian or Snowy hydro steps sharply).

### 8.3 Modelling rules for fast-ramping BESS inside limit forecasters

> [!WARNING] Why Standard 30-Minute Lag Features Miss Battery Volatility
> Incorporating BESS units into a 30-minute or half-hourly limit model via simple 30-minute rolling differences understates their risk by two mechanisms: first, intra-half-hour charge-to-discharge reversals cancel out in 30-minute averages even when they create severe five-minute price spikes; second, BESS output is state-of-charge (SOC) and price-threshold driven rather than weather driven.

Quantitative teams extending short-horizon limit forecasters on Heywood, Murraylink, VNI, and Basslink should therefore apply three targeted engineering rules:
- **Track aggregate corridor BESS net position and headroom-to-swing:** Sum active battery output $P^{\text{BESS}}_{c,t}$ inside each leading constraint equation separately from solar and wind, and track the distance to nameplate charge/discharge bounds so the model knows when local batteries have exhausted midday charging capacity and are poised to flip to discharge.
- **Monitor price-flip trigger proximity:** Because BESS units flip aggressively when regional dispatch prices cross from negative to positive (midday) or cross the $150 to $300/MWh evening-arbitrage threshold, interaction terms between battery sensitivity $\sum_{i \in \text{BESS}} |s_{c,i,t}|$ and predispatch price-ramp gradients capture onset risk far better than autoregressive output lags.
- **Retain five-minute peak-impulse metrics in tight-target evaluation:** Consistent with repository half-hour target semantics (where the tight half-hour limit is the *minimum* across all six five-minute intervals, never the mean), a single five-minute battery reversal that cuts a limit by 100 MW defines the entire half-hour tight target even if the remaining five intervals recover.

Part IV now brings together the standalone compressed Event Atlases v2 for VNI, QNI, and Heywood and specifies the exact operational feature-engineering contract bridging this constraint-pressure atlas to downstream forecasting and valuation models.
