# Decisions

- 2026-09-17: User authorized implementation of the full revised plan. Dedicated execution directory is authoritative; large artifacts remain under data/forecast_experiments.
- 2026-09-17: BOM preferred, ECMWF fallback and longer hindcast history explicitly exploratory. GFS excluded.
- 2026-09-17: Implementation follows written methodology v1.0; a failed source or insufficient overlap does not justify invented training inputs or unsupported improvement claims.
- 2026-09-17: Methodology v1.1 adds bounded streaming of monthly reports and near-horizon MT normalized extraction before implementing that optimization. Original reports retain all source data. Measured original monthly ST/MT archives are approximately 197/212 MB each.
- 2026-09-17: Methodology v1.2 explicitly labels the coal 04:00 trading-day alignment as a research assumption; midnight sensitivity and metadata-vintage verification remain promotion gates.
- 2026-09-17: Methodology v1.3 precedes manual resumable orchestration, compact PASA indexing and content-keyed daily feature checkpoints. Daily 00 UTC weather is the initial research cadence, not an intraday-refresh comparison. Resource and quota stops preserve work without marking the full campaign complete.
