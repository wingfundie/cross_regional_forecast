# Public coverage of constraint inputs

- The 4 February 2026 dispatch case invoked 1,125 equations, including 117 static limits.
- The audited formulations referenced 2,206 distinct external inputs.
- For 744 of 1,008 dynamic equations, every external input had a candidate historical source.

A meter can enter many limits through a shared expression. Resolving each expression before counting the meters measures the acquisition task. Counting equations with a candidate reading for every term instead measures potential replay coverage. One unresolved meter can affect several limits simultaneously.

Public monitors offer another route when their expression contains one measurement, a known coefficient and a fixed offset. Of 54 loaded monitors, 43 permitted that inversion. Forty-one matched the independent case reading within half a published increment. The remaining two matched within one increment. An equation with multiple unknown inputs generally admits several solutions.

The other 264 dynamic equations had at least one unresolved input or choice of component or switch run. Retain the typed identifier, effective version, measurement quality and default condition for each entry. This inventory documents visibility after one dispatch run. Forecast coverage depends on the publication schedule for each changing quantity.

## Sources and evidence

- [February 2026 research record, method and supporting tables](../rhs_replay/inventory/README.md)
- [AEMO implementation guidelines, version 3 of 20 April 2023](https://aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2023/constraints-implementation-guidelines/final-constraint-implementation-guidelines-v3.pdf)
- [February EMSMASTER](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/MMSDM_2026_02/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23EMSMASTER%23FILE01%23202602010000.zip)
- [DispatchIS day archive](https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/PUBLIC_DISPATCHIS_20260204.zip)
- [AEMO equipment ratings](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/transmission-equipment-ratings)
