# QNI/VNI long-range forecast improvement methodology

Frozen before the first model comparison. The primary goal is measured forecast improvement, weighted 75% to days 1–7 and 25% to days 8–14. A 90-day path is retained, but later bands cannot offset failure in the primary horizon.

The campaign compares a seasonal calendar control and issue-known target persistence with a compact original-vintage MT PASA availability challenger. VNI runs first; QNI uses the same frozen procedure. Point models are a regularized linear correction and one fixed shallow absolute-error boosting model. There is no open-ended tuning search.

Historical MT PASA report generation is a publication proxy rather than measured receipt. The campaign is development evidence until the frozen procedure is evaluated on prospective received-at data. All source runs remain coherent. Training, selection, calibration and evaluation are chronological, and a row is usable only when its delivery outcome has matured before the next boundary.

Prospective shadow selection requires completed receipt before the 08:00 NEM origin and a source publication no more than 42 hours old. The 42-hour ceiling admits the observed weekend publication gap while rejecting older runs; every forecast records the chosen run, receipt eligibility and age.

Directional imports retain the repository sign convention. Mean and tight limits are separate targets. AEMO reported limits remain dispatch-solution outputs rather than maximum secure transfer capability.

Success for a proposed point replacement requires at least 2% matched MAE improvement against both calendar and persistence, with positive dependence-aware confidence bounds against both in each primary lead band. Nominal 80%/95% intervals may be called calibrated only when held-out coverage is at least 77%/92%. Negative and inconclusive results retain the operational calendar fallback and continue to show the persistence benchmark.

The first run deliberately excludes future realised weather, dispatch, setters and constraints. NOS scenarios and additional forecast fundamentals are subsequent ablations after this minimal availability challenger is measured.
