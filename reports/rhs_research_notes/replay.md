# Reconstructing a dispatch limit

- Three equations supplied 216 independent five-minute comparisons in February 2026.
- The largest absolute discrepancy was 0.00000547 MW.
- The NSW–Queensland equation carried an economic bind in 28 of its 72 observations.

A dispatch limit belongs to a particular version of an equation and to the state accepted by the dispatch engine. Reconstruction starts with the invoked set, the dispatch run and the interval end. A plausible reading from the same asset can give a different answer if it refers to another instant.

The Sydney monitor gives a simple control. A one MW change in load passes through one for one. The NSW–Queensland stability equation combines regional demand with a signed local flow inside a squared term. Across 24 intervals, substituting the earlier public Terranora reading produced 1.02 MW mean absolute RHS error. A NSW demand share produced 2.89 MW. The other terms were observed in both comparisons.

Economic binding requires the dispatch solution. The weighted injections on the left-hand side determine proximity to the limit, while the marginal value measures the effect of relaxing it. Historical replay establishes the arithmetic. Forward use also requires evidence of when each input became available.

### Which inputs are public?

| Access question | What the evidence supports |
|---|---|
| Are the dispatch formulations public? | The public case supplies the versioned program, its operations, defaults and shared terms for this period. |
| Are historical values present? | The input register identifies values and quality flags for this case. Regional selection, switch runs and missing trader inputs can require additional work. |
| Are live equivalents public? | DispatchIS exposes selected monitors after the run. Equipment ratings also have a public AEMO product. Matching the exact sensor, rating level, run and timestamp is necessary before assuming equivalence. |
| How much does the snapshot route cover? | 41 monitor inversions agreed within half a published increment and 2 more within one increment. The register also identifies multi-input and nonlinear monitors. |

### The three independent replays

| Equation          | Rows   | Calculated   | Mean error MW   | Max error MW   | Economic bind intervals   |
|:------------------|:-------|:-------------|:----------------|:---------------|:--------------------------|
| DATASNAP_DFS_NSYD | 72     | 72           | 0.00000277      | 0.00000547     | 0                         |
| N::Q_NIL_KC       | 72     | 72           | 0.00000246      | 0.00000516     | 28                        |
| T^V_NIL_9         | 72     | 72           | 0.00000000      | 0.00000000     | 0                         |

### How much error reaches the RHS?

| Equation          | Public proxy          | Rows   | Input MAE MW   | RHS bias MW   | RHS MAE MW   | Max MW   | Band ±MW   | In band   |
|:------------------|:----------------------|:-------|:---------------|:--------------|:-------------|:---------|:-----------|:----------|
| DATASNAP_DFS_NSYD | Prior public snapshot | 24     | 38.15          | +12.88        | 38.15        | 79.90    | 137.40     | 24/24     |
| DATASNAP_DFS_NSYD | NSW demand share      | 24     | 412.27         | -412.27       | 412.27       | 550.95   | 290.91     | 0/24      |
| N::Q_NIL_KC       | Prior public snapshot | 24     | 1.39           | -0.42         | 1.02         | 3.73     | 2.58       | 22/24     |
| N::Q_NIL_KC       | NSW demand share      | 24     | 3.86           | -2.09         | 2.89         | 6.71     | 27.28      | 24/24     |

### Does the proxy change a binding decision?

| Proxy                 | Clear   | At risk   | Uncertain   | Missed bind intervals   | False alerts   | Binds uncertain   | Unbanded flips   |
|:----------------------|:--------|:----------|:------------|:------------------------|:---------------|:------------------|:-----------------|
| Prior public snapshot | 17      | 0         | 7           | 0                       | 0              | 7                 | 2                |
| NSW demand share      | 17      | 0         | 7           | 0                       | 0              | 7                 | 0                |

### Timing, limits and reproducibility

| Sampled equation | Historical replay | Exact inputs by interval start |
|---|---|---|
| Sydney demand monitor | Direct analog plus constant | Prior monitor is available on the producer timeline. Same-run monitor arrives after the cutoff. |
| NSW–Queensland stability | Exact local load, initial flow and derived regional inputs | Prior local load is measurable. The full current flow and regional input bundle has no demonstrated public receipt by the cutoff. |
| George Town status | Exact effective timer state from case XML | Current timer and changes of state have no verified independent public source at the cutoff. |

## Sources and evidence

- [February 2026 research record, method and supporting tables](../rhs_replay/study.md)
- [AEMO guide to NEMDE files](https://www.aemo.com.au/-/media/files/electricity/nem/it-systems-and-change/nemde-queue/nemde_queue_users_guide.pdf)
- [AEMO public DispatchIS archive](https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/)
- [AEMO transmission equipment ratings](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/transmission-equipment-ratings)
- [Sydney West transformer workbook](https://tapr.transgrid.com.au/transgrid_bsp_data/Sydney%20West%20132%20kV%20historical%20BSP%20load.xlsx)
