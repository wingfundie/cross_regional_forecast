# Data & Online Research Sourcing Protocol

When producing a Virtual Barrels analysis piece from a mix of local datasets and online
resources, follow this evidence workflow so every number, rule, and institutional claim is
traceable and internally consistent.

---

## 1. Evidence Hierarchy

Rank and combine sources deliberately:

1. **Tier 1 — Primary Empirical & Official Sources (Anchor Every Core Claim Here):**
   - Local frozen datasets, metered telemetry, exchange clearing histories, order-book records.
   - Regulatory filings, statutory market rules, system-operator reports (e.g., OCCTO, JEPX,
     METI/ANRE, FERC, ENTSO-E, EIA, customs trade statistics, central-bank FX series, company
     10-K/annual/integrated reports, official project commissioning notices).
2. **Tier 2 — Authoritative Institutional Research (Context & Benchmarks):**
   - IEA, IMF, World Bank Pink Sheet, JOGMEC, national energy institutes, exchange educational
     guides, and peer-reviewed technical papers.
3. **Tier 3 — Trade Press & Market Commentary (Lead Discovery Only):**
   - Use Reuters, Bloomberg, Platts, Argus, or specialist industry press to surface recent events,
     outage dates, policy announcements, and contract timelines. Whenever possible, verify the
     underlying figure or date against a Tier 1 release before citing it as settled fact.

---

## 2. Reconciling Local Data with Online Resources

- **Inspect before writing:** Query local files programmatically (Python/pandas/DuckDB) to
  confirm exact date coverage, missing intervals, units, and sign conventions before drafting a
  single paragraph.
- **Never blend incompatible windows silently:** If local telemetry runs through October 2026
  while a published customs series runs through September 2026 or annual corporate filings cover
  FY2025, state each window explicitly right next to the number.
- **Explicit basis & unit alignment:** Always verify and disclose:
  - Currency and FX rate date (`¥156.4/USD` in September 2026).
  - Energy basis (`HHV` vs. `LHV`, thermal efficiency, `kWh` vs. `MWh`, `Mt/yr` vs. `bcm`).
  - Delivery basis (`FOB` vs. `DES/CIF`, day-ahead vs. intraday vs. imbalance).
  - Calendar basis (`Winter` = Dec–Feb labelled by Jan year, `FY` = April–March vs. calendar year).
- **Reconcile discrepancies openly:** If two credible sources disagree (e.g., nameplate vs.
  net dependable capacity, or connection applications vs. commissioned megawatts), explain the
  definitional difference in one calm sentence instead of hiding one source.

---

## 3. Online Search Discipline

1. **Search for specific mechanisms and official filings, not generic summaries:** Query for
   exact agency names, rule articles, tariff schedules, terminal capacities, auction clearing
   tables, and contract expiry dates.
2. **Check recency and effective dates:** Confirm whether a policy, tax, market rule, or
   capacity project is proposed, approved, under construction, or already in commercial operation.
   Label status accurately (`awarded`, `under construction`, `targeted for FY2027`, `commissioned`).
3. **Capture complete provenance while researching:** For every web source used, record:
   - Publisher / institution
   - Exact document or page title
   - Publication or effective date (and retrieval date if undated)
   - Direct URL

---

## 4. Citation & Evidence Register Format

- **Inline citations:** Use clean bracketed reference numbers (`[1]`, `[2]`) or structured
  source tags (`[S:source-id]`) when feeding a downstream report builder. Avoid cluttering
  prose with raw bare URLs inside sentences.
- **Closing Sources & Evidence section:** Group references logically (e.g., *Primary Market &
  Telemetry Datasets*, *Regulatory & System-Operator Disclosures*, *Fuel, Macro & Trade
  Benchmarks*, *Corporate Filings & Industry Reports*) and list each entry concisely:

  ```markdown
  - **[1]** Organization for Cross-regional Coordination of Transmission Operators (OCCTO). *FY2026 Interconnector Operational Capacity Outlook* (March 2026). https://...
  ```

- **Analytical Scope Note:** For formal notes or reports, include a 2–3 line scope note stating
  the data cutoff date, primary datasets used, and key methodological boundaries.
