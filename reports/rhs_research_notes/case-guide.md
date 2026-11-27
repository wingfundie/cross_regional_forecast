# Three dispatch equations and their measurement boundaries

- Each equation was checked against 72 native dispatch observations.
- The Sydney monitor adds a fixed 10,000 MW to area demand.
- The two George Town timer states are separated by 244 MW.

For Sydney, subtracting the offset recovers the electrical load covering Sydney, Wollongong and Newcastle. All 72 sensor values carried a replacement flag and permission for dispatch use. Reconstructing the calculation requires the accepted reading even where another telemetry stream appears fresher.

For the NSW–Queensland stability limit, let N and Q denote the equation-specific regional demands, d the signed Terranora load and i the initial signed Directlink flow, all in MW. The limit in MW is 1,383 − 0.001(i + d)² − 0.0239N + 0.0524Q − 0.6394d. Reversing flow changes the interaction with local demand. Align the two readings to the same interval start before applying the coefficients.

At George Town the limit is 594 MW less 244 MW times the binary timer state. When that state is unresolved, retain both feasible values, 350 and 594 MW. Their midpoint describes neither operating branch.

## Sources and evidence

- [February 2026 research record, method and supporting tables](../rhs_replay/cases/case_guide.md)
- [AEMO dispatch fallback procedure](https://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Power_System_Ops/Procedures/SO_OP_3706%20Failure-of-Market-or-Market-Systems.pdf)
- [AEMO demand terms, table 4](https://www.aemo.com.au/news/-/media/Files/Electricity/NEM/Security_and_Reliability/Dispatch/Policy_and_Process/Demand-terms-in-EMMS-Data-Model.pdf)
- [AEMO February NEMDE files](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/2026/NEMDE_2026_02/NEMDE_Market_Data/NEMDE_Files/)
