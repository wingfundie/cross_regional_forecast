# Selector and Excel use

## Start with the question

Choose the link, direction, calendar quarter and compatible network/market configuration. The main output is half-hour average reported limits. The tight target shows the most restrictive five-minute value within each complete half-hour. AEMO reported limits depend on dispatch and constraints; they are not physical maximum capability.

Launch the local selector through the supplied Python package. The research reports are separate standalone offline HTML files and need no running service.

```text
nemic-regimes serve --bundle path/to/bundle --port 8061
```

Open `http://127.0.0.1:8061`. Choose a named condition or enter measurable conditions under the detailed controls. Blank means unspecified. A numeric value requests similar historical values; advanced JSON can supply a range or specific equipment/constraint sets.

## Read the evidence before choosing a number

The P50 is the central historical estimate; P10–P90 describes the conditional range. Click a half-hour to inspect matched days, active sets, episode counts and restrictive examples. The dashed reference is the unconditioned quarter/half-hour distribution.

Supported analogue means the declared independent-history convention is met. Broader analogue identifies the conditions relaxed to obtain a comparison. Modelled extrapolation uses a fitted model beyond well-populated matching history and has unverified query-specific tail calibration. Unavailable means the request lacks compatible evidence or a supported mapping.

A broader quarter reference does not establish that another quarter will behave the same way. Current PEC-market and regulated Basslink histories cover fewer seasonal configurations. Choose the historical era deliberately when exploring history; do not mistake it for current operating conditions.

An outage requirement is not an additive MW deduction. Two outages can interact and change the leading constraint. Rare observed stress cases stay visible with dates but no invented occurrence probabilities.

## Automatic suggestions and manual assumptions

The public-data controls retrieve the latest observed regional AEMO state or an explicit coherent weather run. Current observations belong to their measured interval. Applying them to a different delivery time creates a named assumption. Review temperature, VRE and residual-demand units before using values.

The JSON export retains the original suggested conditions and receipt records as well as the final query. Changing controls does not overwrite an issued forecast. Unavailable storage energy, support-scheme armed status and complete current invocation cannot be inferred from generic dispatch or weather.

## Excel companion

The fresh workbook contains a selected example profile, quarterly references, named conditional profiles, validation evidence and condition/event notes. Results are typed exported values. It is a companion for analysis and downstream assumptions, not an embedded copy of the fitted engine.

New combinations require running the package and exporting/refreshing results. In-workbook summary links and chart references recalculate from their exported inputs; changing a label does not rerun a model. The data cutoff and bundle identity are printed alongside the main output.

Use the `Status`, `Days`, `Episodes`, `Conditions` and `Era` columns when filtering the catalogue. Indicative rows remain present for research but should not be treated as statistically supported ranges. Keep the source workbook intact if making your own analysis copy.

## Common interpretations

- A negative directional limit can imply forced transfer in the opposite direction. Do not take its absolute value or clamp it to zero.
- A wide band is a finding about uncertainty or mixed remaining conditions, not a formatting defect.
- A rare severe example is a stress case, not a forecast probability.
- Low wind, high demand or hot weather is insufficient without the network and geographic context.
- Strong average accuracy does not override failed calibration or extreme-regime checks.
