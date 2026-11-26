## Chapter 2 · Full Six-Link Parity and Parallel Co-Binding

Prior constraint-pressure reporting concentrated almost exclusively on the three primary alternating-current interconnectors (VNI, QNI, and Heywood), relegating Directlink, Murraylink, and Basslink to secondary notes despite two full years of native five-minute attribution archives sitting on disk. Treating those three HVDC links as an afterthought creates a blind spot for both settlement-residue desks and grid modellers. Under the NEM settlement rules, Directlink flows and residues are pooled directly into the Queensland to New South Wales Settlement Residue Auction (SRA) buckets alongside QNI, while Murraylink flows and residues are pooled directly into the Victoria to South Australia SRA buckets alongside Heywood. Basslink, while outside the SRA scheme, governs the entire hydroelectric exchange between Tasmania and mainland Victoria and experiences the highest forced-limit frequency in the market.

Across the full 24-month study window from 1 September 2024 to 31 August 2026 (210,240 five-minute intervals per link, or 1,261,440 link-intervals in total), the six-link system logged 44,185 sharp 30-minute directional contraction episodes, 1,284,417 binding constraint equation-intervals, and 446 unique participating generating units. Placing all six interconnectors side by side exposes sharp structural differences between meshed AC corridors and regulated or market-network HVDC links.

### 2.1 Structural comparison across all twelve directional corridors

| Link | Direction | Median cap (MW) | P05 cap (MW) | Tight headroom (%) | Forced limit (%) | Contractions (24m) | Median drop (MW) | Mean spread when tight ($/MWh) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| VNI | VIC to NSW | 755 | -272 | 42.5% | 12.8% | 4,029 | 350 | $87.04 |
| VNI | NSW to VIC | 450 | -10 | 17.6% | 5.3% | 3,455 | 317 | -$33.34 |
| QNI | NSW to QLD | 557 | -46 | 11.8% | 7.9% | 3,122 | 168 | $49.64 |
| QNI | QLD to NSW | 957 | 153 | 29.9% | 1.0% | 4,300 | 173 | $65.06 |
| Heywood | VIC to SA | 401 | -119 | 31.7% | 9.6% | 3,859 | 236 | $73.04 |
| Heywood | SA to VIC | 350 | -217 | 23.3% | 14.6% | 3,867 | 258 | $20.85 |
| Directlink | NSW to QLD | 47 | -59 | 42.9% | 21.2% | 4,395 | 59 | $1.82 |
| Directlink | QLD to NSW | 81 | -61 | 32.3% | 11.0% | 4,354 | 62 | $52.48 |
| Murraylink | VIC to SA | 107 | -131 | 61.8% | 17.9% | 3,740 | 90 | $31.25 |
| Murraylink | SA to VIC | 9 | -168 | 51.2% | 40.9% | 3,365 | 98 | -$14.66 |
| Basslink | TAS to VIC | -17 | -258 | 27.0% | 50.1% | 2,625 | 185 | -$19.80 |
| Basslink | VIC to TAS | 183 | -227 | 48.1% | 22.7% | 3,074 | 175 | $35.63 |

The six-link comparison immediately overturns the informal assumption that small HVDC links are lightly loaded backup pathways. On a frequency-of-tightness basis, Murraylink is the most persistently constrained interconnector in the entire NEM: forward Victoria to South Australia headroom sits at or below 50 MW in 61.8% of all five-minute intervals, and reverse South Australia to Victoria headroom sits at or below 50 MW in 51.2% of intervals, with a median reverse transfer ceiling of just 9 MW and forced forward-flow requirements in 40.9% of all intervals. Directlink displays a similar pattern along the northern border, clearing at tight headroom in 42.9% of forward (NSW to QLD) intervals and 32.3% of reverse (QLD to NSW) intervals, while posting more monthly P90 contraction episodes (4,395 forward and 4,354 reverse) than any other link in the market.

On the large AC corridors, economic tightness concentrates along the dominant north-to-south and west-to-east scarcity axes. VNI forward transfer from Victoria into New South Wales operates at tight headroom in 42.5% of intervals, and during those tight intervals the Victoria to New South Wales price spread averages $87.04/MWh (compared with $34.02/MWh unconditionally). QNI reverse transfer from Queensland into New South Wales operates at tight headroom in 29.9% of intervals with an average tight-interval spread of $65.06/MWh, while Heywood forward transfer from Victoria into South Australia clears tight in 31.7% of intervals at an average spread of $73.04/MWh.

{{exhibit:a1}}

Basslink occupies a category of its own. Because Basslink operates as a long-distance subsea HVDC cable subject to frequency-control system protection scheme (FCSPS) constraints, thermal cable de-ratings, and Tasmania-side dynamic stability bounds, its median forward (Tasmania to Victoria) upper limit over the two-year window was actually -17 MW, meaning reverse import flow into Tasmania was forced in 50.1% of all five-minute intervals during the 2024 to 2026 hydroelectric storage management cycle. Reverse Victoria to Tasmania transfer operated within 50 MW of its limit in 48.1% of intervals at a mean tight spread of $35.63/MWh (Tasmania above Victoria).

### 2.2 Negative tight-headroom spreads: diagnosing counter-price flow regimes

A notable feature of the table above is that three directional corridors display negative average price spreads during tight-headroom intervals: VNI reverse (NSW to VIC, -$33.34/MWh), Murraylink reverse (SA to VIC, -$14.66/MWh), and Basslink forward (TAS to VIC, -$19.80/MWh). Those negative figures are not data anomalies; they are the signature of forced counter-price binding.

On VNI reverse, for instance, a tight lower headroom ($H^{\text{lower}}_t \le 50\text{ MW}$) frequently arises not because New South Wales is exporting cheap surplus power into an expensive Victoria, but because the reverse limit has been clamped down to a small positive or negative number while Victoria is already exporting heavily into a higher-priced New South Wales, or because loop flows from Snowy and southern New South Wales solar farms push flow southward against a positive NSW minus VIC spread. Whenever the directional price spread has the opposite sign to physical flow, tight headroom marks a negative-residue trap rather than a positive-residue rent opportunity. Chapter 6 quantifies the exact dollar toll of these counter-price regimes.

### 2.3 Parallel HVDC co-binding and SRA bucket dilution

For traders and risk analysts evaluating Settlement Residue Auction units, the primary commercial reason to integrate Directlink and Murraylink into the constraint atlas is parallel co-binding. Under the NEM settlement formula, a buyer of QLD to NSW SRA units receives a pro-rata share of the combined settlement residue generated across both QNI and Directlink, while a buyer of VIC to SA or SA to VIC SRA units receives a pro-rata share of combined residue across Heywood and Murraylink. If the parallel HVDC link retained ample spare headroom whenever the main AC link constrained, price separation could be partially relieved by rerouting flow across the DC link. The empirical evidence shows the exact opposite.

| Pooled corridor pair | Direction | Main link tight (%) | Parallel HVDC tight (%) | Both tight simultaneously (%) | P(HVDC tight given Main tight) | P(Main tight given HVDC tight) |
|---|---|---:|---:|---:|---:|---:|
| QNI + Directlink (QLD-NSW) | Forward (NSW to QLD) | 11.8% | 42.9% | 11.3% | 95.4% | 26.3% |
| QNI + Directlink (QLD-NSW) | Reverse (QLD to NSW) | 29.9% | 32.3% | 21.0% | 70.3% | 64.9% |
| Heywood + Murraylink (VIC-SA) | Forward (VIC to SA) | 31.7% | 61.8% | 27.4% | 86.5% | 44.4% |
| Heywood + Murraylink (VIC-SA) | Reverse (SA to VIC) | 23.3% | 51.2% | 20.3% | 87.2% | 39.6% |

Whenever QNI operates at tight headroom in the forward NSW to QLD direction, Directlink is simultaneously tight 95.4% of the time (11.3% of all intervals overlap out of 11.8% total QNI forward tightness). In the economically dominant QLD to NSW southward direction, Directlink is simultaneously tight in 70.3% of tight QNI intervals. Along the southern border, whenever Heywood hits tight headroom, Murraylink is simultaneously tight 86.5% of the time in the VIC to SA direction and 87.2% of the time in the SA to VIC direction.

{{exhibit:a2}}

The asymmetry in the two conditional probabilities explains the physical hierarchy of each border. Because the parallel HVDC links have much smaller nominal capacities (180 MW on Directlink, 220 MW on Murraylink) and sit embedded inside constrained regional sub-networks (northern New South Wales 132 kV lines around Lismore and Mullumbimby for Directlink; the Riverland 132 kV and North West Victoria 220 kV corridor around Red Cliffs, Monash, and Buronga for Murraylink), they hit local thermal or voltage limits frequently even when the main AC spine still has room to move. Thus $P(\text{Main tight} \mid \text{HVDC tight})$ is moderate (26.3% on Directlink forward and 39.6% to 44.4% on Murraylink). Once regional price separation becomes large enough to drive the main AC corridor into tight headroom, however, economic dispatch almost always saturates the parallel HVDC link first, leaving effectively zero unpriced parallel relief.

> [!WARNING] Implication for Pooled SRA Valuation
> Modelling QNI or Heywood limits in isolation overstates diversification across parallel links. In 70% to 95% of main-corridor binding intervals, the paired HVDC link is already saturated or forced-clamped. Moreover, during periods when Murraylink or Directlink is forced to flow counter-price by local 132 kV or 220 kV voltage constraints while the main AC corridor flows with the price spread, the negative residue accrued on the HVDC leg directly dilutes the pooled SRA payout for the entire border.

This structural co-binding finding sets up the next analytical question: how accurately can an external analyst reconstruct each link's published limit envelope from standing generic constraint equations, and why did earlier studies observe seemingly puzzling reconstruction errors on QNI and Heywood? Chapter 3 audits that exact discrepancy.
