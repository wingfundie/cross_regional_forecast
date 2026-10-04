# Use interconnector research in NEMPy

**Forecast design for the next seven days and the month ahead**

Report date: 4 October 2026. Most historical results end in August 2026. This report does not contain new market forecasts.

This report uses the points in the [original assessment](../nempy_forward_forecast_design_20261004/Forward_Forecast_with_NEMPy.md). It adds charts, data tables, process diagrams, and a controlled term list.

The language target is ASD-STE100 Issue 9. Short sentences, active voice, and consistent technical terms control the text. A full dictionary review remains open. Section 20 gives the language review limits.

## 1. Recommended design

**Start with forecast bounds. Then add complete constraint equations.** Keep both models available for comparison.

Your first idea gives a practical first model. The research model supplies forecast bounds for each interconnector. NEMPy calculates generation, flow, and regional prices within those bounds.

Your second idea gives a stronger method for some network changes. Use the outage schedule and historical regimes to prepare constraint scenarios. NEMPy calculates dispatch for each scenario. The result shows which constraints are binding.

A combined model can use both methods. However, each restriction needs one clear representation. Do not add the same restriction twice.

For days 8–30, use a separate scenario model. Include outage timing, generation availability, demand, and weather uncertainty. Do not extend the saved seven-day models beyond their supported horizon.

<!-- visual:routes -->

| Model | Main input | Main benefit | Main limit |
|---|---|---|---|
| Bound model | Forecast lower and upper flow bounds | Fast first comparison | Bounds depend on the reference dispatch |
| Equation model | Complete equations and future RHS values | Generation can change transfer headroom | Some future inputs are unavailable |
| Combined model | Separate model results or separate restrictions | Can use the strengths of both models | Can count the same restriction twice |

The first decision is about forecast value. Compare each model with simple methods on the same intervals. A successful solver run does not prove better forecasts.

## 2. Use the research evidence correctly

The project contains three separate model systems. Each system has its own inputs, results, and status.

| System | Current meaning | Use in this design |
|---|---|---|
| Original six-link model | Conditional research with some actual future inputs | Reference for conditional tests |
| QNI/VNI research models | Historical models with network and calendar inputs | First sources of forecast bounds |
| Production scaffold | Registry, input, and route software | Reusable software structure |

The production scaffold is not a live forecast service. The saved QNI/VNI models also need verified input receipt times before live approval.

VNI has stronger results than QNI in the saved tight-limit tests. The difference supports a VNI-first trial. It does not support one model for every link and direction.

<!-- visual:skill -->

Positive skill means lower mean absolute error than persistence. Negative skill means higher error. Persistence uses the latest permitted target value as the forecast.

These scores describe tight directional limits. They do not measure flow or price accuracy. AEMO reported limits are dispatch results, not maximum secure physical transfer capability.

<!-- visual:mae -->

The absolute errors are also important. A useful percentage gain can still leave a large error in MW. Keep both measures in the decision report.

The QNI short-horizon export result has a small positive gain. Its reported confidence interval includes zero. Do not treat this result as a proven general improvement.

Sources: [VNI results](../../docs/VNI_DIURNAL_NOS_RESULTS.md) and [QNI results](../../docs/QNI_DIURNAL_NOS_RESULTS.md). The charts retain the source populations and target definitions.

The newer clustering evidence needs a separate review. The cached report contains one pilot forecast comparison. Later execution records and report status do not give one consistent completion record.

The fundamentals-v3 assessment also keeps promotion restrictions. Do not use either campaign as proof of live forecast performance. Their execution guides remain the source for campaign status.

## 3. Correct the uncertainty before use

The saved prediction intervals contain fewer outcomes than their nominal levels require. Their uncertainty ranges are too narrow for those labels.

<!-- visual:coverage -->

The chart combines targets and lead bands. It does not prove correct coverage for a particular direction or hour. Check those groups separately.

Use separate data for model selection, calibration, alert thresholds, and final evaluation. Calibration adjusts a forecast distribution against earlier errors. Final evaluation checks the result on later data.

Keep the complete joint scenario when you calculate a result. Independent low bounds on every link do not form a known probability event.

The median input does not always give the median output. A small input change can change the binding constraint. It can also change the dispatched unit and regional price.

Calculate dispatch for each scenario first. Then calculate flow, price, and event distributions from the results.

## 4. Separate bookings, active equations, and binding constraints

An outage booking is a planned event. The actual event can start late, end late, change, or stop. The booking can also have no active constraint set.

A constraint set contains equations for a network condition. AEMO puts the applicable equations into dispatch. An included equation does not always become binding.

The reported limit setter is another result. It identifies an equation that sets a reported directional limit. It need not be a binding constraint.

<!-- visual:outage_chain -->

The outage research shows why these distinctions matter. The outage set often has a small median share of binding intervals.

<!-- visual:nos_medians -->

Each bar is a median across supported family-directions. Each underlying share uses five-minute intervals during actual invocation. The chart is not a probability for a new booking.

Some outage families have large effects. The QNI study reports own-set binding shares of 82%, 81%, and 61% for three specific northbound outage families. These shares apply during actual invocation.

The normal equations often remain important. Keep them in the candidate library during an outage. Do not replace every normal equation with the named outage set.

<!-- visual:layer_agreement -->

The joint shares above use averages across supported families. They do not use the median calculation in the previous chart. Do not combine their denominators.

The point-model studies and the descriptive outage study also use different support tests. The strict v2 matched audits found no supported recurring entity. The broader descriptive study supports some family-directions.

Source: [NOS mechanics and outlook](../../execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md).

## 5. Use NOS as a scenario input

NOS can help identify future network conditions. It does not justify one fixed reduction for every booked outage.

<!-- visual:nos_limits -->

The outlook improves Brier score in 23 of 96 comparison cells. Other cells need a simpler reference or an explicit scenario label.

One well-populated forecast bin gives 36% binding against 15% actual binding. This result shows excessive forecast probability in that bin. It is not a summary of all bins.

Missing booking links cause another problem. Among 1,175 bookings with a later set invocation, the first inferred family is correct in 19%. The first three families reach 22%.

The wider unlinked-booking sample contains 2,781 bookings. Its first-family hit rate is 8%. Many of those bookings do not invoke a set.

Use direct booking-to-set links first. If the link is missing, keep several possible families. Mark weak links as uncertain.

Prepare separate scenarios for these events:

- The outage starts and ends on time.
- The outage starts late.
- The outage ends late.
- The outage does not proceed.
- Another outage overlaps the first outage.
- An unplanned outage occurs.

Keep each scenario consistent across time and regions. Do not add individual MW reductions without a supported rule for the combined network condition.

For overlapping outages, use a known joint configuration when possible. Otherwise, mark the combination as an exploratory scenario. An unsupported combination needs no invented probability.

Use earlier records to estimate booking reliability. Keep status, lead time, revisions, equipment, and outage family in that calculation.

Historical effects are associations unless a separate method supports a causal claim. Weather, other outages, and generation changes can affect the same intervals.

## 6. Define the forecast products

Use a different input contract for each horizon. Show the forecast basis in every output interval.

<!-- visual:horizons -->

| Horizon | Main output | Input basis | Main check |
|---|---|---|---|
| Next hour | Flow and state changes | Current state and short forecasts | Receipt delay and ramps |
| 0.5–6 hours | Flow, spread, and congestion risk | Forecast bounds and imminent outages | Direction and event accuracy |
| 6.5–24 hours | Dispatch scenarios | Demand, VRE, offers, and outage timing | Joint uncertainty |
| 24.5–72 hours | Risk ranges | Wider weather and availability scenarios | Coverage by regime |
| 72.5–168 hours | Seven-day outlook | Supported long leads and simple alternatives | Source age and model drift |
| Days 8–14 | Daily and weekly ranges | Verified extended forecasts or historical analogs | Independent horizon results |
| Days 15–30 | Weekly and monthly exposure | Joint seasonal and outage scenarios | Long events and energy budgets |

The saved bundles stop at 336 half-hour leads. That is seven days. A new input table does not extend their supported range.

For days 8–30, start with seasonal bounds and supported outage scenarios. Then compare a new statistical model with that reference.

Use an extended weather forecast only within its verified coverage. After that point, use coherent historical weather paths or a separately checked extended forecast product.

Do not repeat the last forecast day through the month. Keep regional weather relationships, long hot periods, and renewable droughts in the scenario paths.

Daily generation availability gives a capacity condition. It does not give each half-hour offer or dispatch value. Keep that distinction in the model inputs.

## 7. Build the bound model

Use all five NEM regions in the first market model. QNI and VNI share NSW. South Australia and Tasmania also change the Victorian balance.

Keep parallel links separate. QNI and Directlink are different links. Heywood and Murraylink are also different links.

Check the effective network records for the delivery date. The historical six-link list is not a permanent topology guarantee.

### 7.1 Keep the signs correct

| Link | Positive flow | Negative flow |
|---|---|---|
| QNI | NSW to Queensland; northbound | Queensland to NSW; southbound |
| VNI | Victoria to NSW; northbound | NSW to Victoria; southbound |

The repository stores the import target as the negative of raw `IMPORTLIMIT`. Use the equations below to set signed bounds.

```text
E = forecast export target
I = forecast import target
U = E
L = -I
L <= signed flow <= U
```

<!-- visual:signed_bounds -->

If E is 800 MW and I is 500 MW, the signed range is −500 to +800 MW.

If I is −100 MW, L is +100 MW. The range then requires positive flow. Do not change the negative import target to zero.

If E is −50 MW and I is 500 MW, the range is −500 to −50 MW. The range requires negative flow.

Source: [target preparation](../../nemic/prepare.py). Keep negative values, target names, and interval definitions unchanged.

### 7.2 Keep the time resolution correct

The ordinary directional targets are half-hour means. The tight targets are the minimum of six five-minute directional values. These targets describe different quantities.

Use mean targets for the first half-hour dispatch comparison. Use tight targets for a separate persistent-restriction scenario.

A tight limit does not mean the restriction lasts for the full half-hour. That assumption can change price and flow results.

Tight bounds can cross even when every five-minute interval is feasible. One interval can require positive flow. A later interval can require negative flow.

```text
First interval:  +100 <= flow <= +300 MW
Later interval:  -300 <= flow <= -100 MW
Constant-flow intersection: L = +100 MW, U = -100 MW
```

No constant flow meets both ranges. This case can show a real change of direction. It does not always show bad source data.

For five-minute forecasts, use five-minute targets or a checked path model. Make sure that each path gives the required mean and minimum values.

Do not average incomplete target intervals. The repository requires all six native observations for a complete half-hour target.

### 7.3 Understand the model limit

Reported limits depend on the solved dispatch. A different generation pattern can change the appropriate flow bound.

Separate bounds can also miss joint restrictions. A real equation can contain QNI, VNI, and several generators together.

The bound model remains useful as a forecast approximation. Its value depends on later flow and price tests. It does not prove secure physical transfer capability.

## 8. Build the equation model

A complete equation lets dispatch change transfer headroom. The solver can change generator output and interconnector flow together.

```text
sum(a_j × flow_j) + sum(b_g × generation_g)
    + sum(c_s × FCAS_s) <= RHS
```

The left-hand side contains the modeled dispatch variables. The right-hand side contains a value for the scenario.

For one positive flow coefficient, a conditional bound has this form:

```text
flow_j <= (RHS - other terms) / a_j
```

If the coefficient is negative, reverse the inequality. Keep equality constraints separate. Very small coefficients need a declared numerical tolerance.

### 8.1 Keep a complete candidate library

Include normal equations, supported outage equations, and credible alternatives. A rare equation can become important in an unusual scenario.

A candidate rank can reduce calculation work. It must not remove a known applicable restriction only because the estimated binding probability is low.

After the first solve, check the result against the larger eligible library. Add violated omitted equations. Then calculate dispatch again.

Record omissions and violations. This check cannot find an equation that is absent from the library.

### 8.2 Give each RHS a clear source

| RHS method | Required input | Required label or check |
|---|---|---|
| AEMO forecast RHS | Original forecast version and receipt time | AEMO-assisted model |
| Structural calculation | Complete formula and forward drivers | Formula and input checks |
| Statistical RHS | Earlier labels and permitted predictors | Separate chronological evaluation |
| Historical analog | Similar eligible network states | Support and uncertainty checks |
| Analyst assumption | Explicit value or range | Scenario only, unless probability evidence exists |
| Unavailable | Missing essential terms | Alternative model or unavailable result |

The equation name does not supply the future RHS. Some RHS formulas need line measurements, reactive power, ratings, and plant states.

Feedback equations also need a consistent reference state. Do not change a generator term without checking the related RHS inputs.

A headroom forecast is a different input contract. It can already include the effect of generator terms. Do not subtract those terms a second time.

The inspected NEMPy installation is version 3.0.3. It includes RHS calculation tools. Those tools do not create unavailable future measurements.

Sources: [NEMPy input tools](https://nempy.readthedocs.io/en/latest/historical.html) and [AEMO constraint guidance](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq).

## 9. Check the effect of redispatch

The following example uses synthetic inputs. It explains the method. It is not a forecast accuracy result.

A southern generator supplies a northern demand of 1,000 MW. Its offer is cheaper than the northern generator offer. The example has no southern demand or losses.

```text
Network equation: F + 0.5 × P <= 700 MW
Reference generator output: P = 600 MW
Reference flow bound: F <= 400 MW
Future scenario: P = F
Future equation: 1.5 × F <= 700 MW
```

The fixed reference bound permits 400 MW. The complete equation permits 466.67 MW after redispatch. Both constraints together still permit only 400 MW.

<!-- visual:toy -->

The extra 66.67 MW comes from a changed generation condition. It does not come from a changed equation rating.

<!-- visual:geometry -->

The shaded area meets the network inequality in this example. The diagonal line also meets the southern balance condition. Their intersection gives the maximum northbound flow.

<!-- visual:calculator -->

Use the controls to change the synthetic RHS and reference output. The calculation keeps the future balance condition `P = F`. It does not represent a real QNI or VNI equation.

The example shows one possible error direction. A fixed bound can cause a different error in another system state. Use actual forecast tests to measure the effect.

Source: [saved synthetic NEMPy results](../nempy_forward_forecast_design_20261004/toy_results.csv).

## 10. Combine the models without duplicate restrictions

Start with separate bound and equation results. Compare them on the same rows and input versions.

The simplest combined model selects or combines their output forecasts. Select the rule with calibration data. Keep the rule fixed during final evaluation.

An average across different topology scenarios is a forecast summary. It need not describe one executable dispatch plan. Keep the complete scenario results as well.

A more detailed combined model divides the restrictions. Complete equations describe known mechanisms. A separate statistical model describes the remaining restrictions.

The remaining restriction needs a valid target definition. The difference between two unrelated scalar limits does not establish that target.

Use a restriction register with these fields:

- Restriction identity and purpose.
- Equation identity and effective version.
- Model and representation.
- Reference dispatch state.
- Evidence for any additional statistical bound.
- Duplicate-restriction status.

True equipment bounds can remain with generic equations. An all-in statistical bound usually needs a different role in the equation model.

Soft statistical bounds are a later research option. Their penalty changes the optimization and can change prices. Keep that penalty separate from AEMO constraint-violation costs.

## 11. Use regimes and generator information

A regime is a defined operating condition. It is useful when it changes the forecast or error distribution in a repeatable way.

Start with simple regimes. Examples include normal operation, an imminent outage, forced flow, high residual demand, and low demand with high solar output.

Use regimes to select candidate equations, historical analogs, and error samples. They can also help select a model when input quality changes.

Do not use the actual future regime in a forward test. Calculate regime probabilities from permitted inputs. Alternatively, calculate the regime within each scenario.

Keep regime duration and transitions realistic. Independent regime draws can create a different network condition every half-hour without a physical cause.

Compare clustering with a model that uses the same continuous inputs. Otherwise, extra information can explain the apparent gain.

Fit thresholds, scaling, clusters, and feature selection on earlier data only. Descriptive bins from the complete history are not valid forecast inputs without this change.

For a fixed equation, generator sensitivity is `−b_g / a_j`. This value describes a local mathematical effect. Another equation can become limiting after the change.

Use these sensitivities to select important generator detail. A regional supply block cannot always replace a generator with a different network coefficient.

Keep controllable generation as a dispatch variable where possible. Supply availability, offers, ramps, and energy budgets. Do not supply actual future generator output.

## 12. Supply consistent market inputs

NEMPy needs more than network limits. Demand, generation, offers, losses, and stored energy can dominate forecast error.

| Input | Required treatment | Common error |
|---|---|---|
| Demand | One declared demand definition | Subtract VRE twice |
| Regional VRE | Consistent regional forecast version | Mix unrelated forecast runs |
| Unit VRE | Allocation that preserves regional totals | Treat regional output as unit output |
| Generation availability | Capacity and timing scenarios | Treat available MW as dispatched MW |
| Offers | Permitted historical inputs or explicit offer scenarios | Use later public bids before their receipt |
| Battery energy | State of charge and energy balance | Repeat discharge without an energy limit |
| Hydro energy | Water or energy budgets and offer assumptions | Treat every interval as independent |
| Thermal units | Initial state, ramps, and commitment assumptions | Start each interval from actual future dispatch |

Use a declared rooftop-PV and scheduled-load treatment. If VRE remains a supply input, do not subtract the same VRE from demand.

Carry simulated state from one interval to the next. This includes ramps, battery energy, and relevant plant state.

Use a separate scheduling model when a single-interval calculation cannot represent the required energy decisions. Check the effect of simplified schedules before claiming price accuracy.

Historical archive access does not prove earlier public availability. Check the visibility and actual receipt time of each product.

Use actual future offers only in a labeled conditional test. That test can show the value of better offer forecasts.

## 13. Create an auditable input record

Every run needs an immutable input snapshot. Keep the information that proves what the system knew at the forecast origin.

<!-- visual:provenance -->

| Field | Purpose |
|---|---|
| Source and product | Identify the provider and data product |
| Issue time | Identify when the provider produced the forecast |
| Publication time | Identify when the source released the data |
| Receipt time | Identify when this system received the data |
| Forecast version | Keep one consistent forecast run |
| Delivery interval | Identify the interval that the value describes |
| Ensemble member | Keep related scenario values together |
| Units and time zone | Prevent incorrect conversions |
| Age and content hash | Check freshness and unchanged content |

Publication and receipt must occur no later than the forecast origin. A later file modification time cannot prove earlier availability.

Use fixed NEM time, UTC+10, for market calculations. Keep raw timestamps and source metadata as well.

Keep coherent versions within each regional input block. Different products can have different update times. The selection rule must explain each choice.

Keep the saved feature contracts unchanged. The `own_anchor` value is target-specific at origin minus 30 minutes under the research contract.

New demand, weather, or availability inputs need a new feature contract. Do not place them in old lag columns.

Sources: [VNI bundle guide](../../docs/VNI_SAVED_MODEL_GUIDE.md), [QNI bundle guide](../../docs/QNI_SAVED_MODEL_GUIDE.md), and [production guide](../../docs/PRODUCTION_PIPELINE_GUIDE.md).

## 14. Connect the inputs to NEMPy

Keep the new dispatch work in a separate research package. Use explicit adapters for existing bundles and the production scaffold.

| Input or result | NEMPy interface |
|---|---|
| Market and units | `markets.SpotMarket` |
| Offer volumes | `set_unit_volume_bids` |
| Offer prices | `set_unit_price_bids` |
| Demand | `set_demand_constraints` |
| Signed link bounds | `set_interconnectors` |
| Link losses | `set_interconnector_losses` |
| Equation type and RHS | `set_generic_constraints` |
| Unit coefficients | `link_units_to_generic_constraints` |
| Link coefficients | `link_interconnectors_to_generic_constraints` |
| Regional service coefficients | `link_regions_to_generic_constraints` |
| Dispatch calculation | `dispatch` |
| Flow and price results | `get_interconnector_flows`, `get_energy_prices` |

The interface field `set` identifies one generic restriction row. Keep a separate row for each AEMO equation. Do not convert a complete AEMO constraint set into one inequality.

Keep the many-to-many relation between equations and sets. Keep equation versions, dates, and all left-hand-side terms.

If an equation contains FCAS terms, model those terms or supply a declared conditional service scenario. Do not delete them silently.

Model losses and market-network services at the detail that the experiment requires. A simple bidirectional link is an approximation.

Calculate equation slack from the complete solved terms. Define a numerical binding tolerance. Check shadow values or small perturbations before claiming an economic effect.

Separate physical dispatch from pricing runs during interventions. Also record material constraint relaxation and solver reruns.

Source: [NEMPy market interfaces](https://nempy.readthedocs.io/en/latest/markets.html). The earlier report checked these interfaces against local version 3.0.3.

## 15. Run the forecast in a fixed sequence

<!-- visual:run_flow -->

Use the following procedure for each run.

1. Set the forecast origin and supported delivery range.
2. Save the input snapshot, code version, configuration, and hashes.
3. Check the input contract and source age.
4. Select the model or its approved alternative.
5. Create joint scenario paths.
6. Check each restriction for duplicate representation.
7. Calculate dispatch in time order.
8. Check balances, violations, and solver status.
9. Calculate output distributions from complete scenarios.
10. Save the forecast before actual outcomes become available.
11. Add the actual outcomes later.
12. Calculate the evaluation results.

Give every requested interval a status. Use complete, alternative, or unavailable. Do not remove failed intervals from the coverage record.

Keep checkpoints for long historical tests. Use one healthy worker for each owned stage. Check the ledger before a restart.

Report changes should use cached results. Do not train models again for a chart or text change.

The cache key needs the data, code, configuration, feature contract, equation library, model package, and solver version.

## 16. Check the forecast with three test types

Separate engine checks from forecast accuracy. Use three named test types.

<!-- visual:test_lanes -->

**Historical replay** uses actual inputs to check the engine. Check signs, balances, losses, equation terms, and difficult states. Replay accuracy is not forward forecast accuracy.

**Conditional research** replaces one forecast input with its actual future value. This test can show which input needs better forecasts. Keep its scores separate.

**Issue-time evaluation** uses only information available and received by the forecast origin. Use later outcomes for scoring. If historical receipt is unknown, state that limit.

Use rolling or out-of-fold forecasts for upstream model outputs. Do not use fitted training predictions as inputs to a downstream model.

Keep chronological partitions for training, selection, calibration, alert thresholds, and evaluation. Remove samples whose future targets cross a forbidden boundary.

Use common rows for paired model comparisons. Also report coverage on the full requested population. Missing forecasts must remain visible.

### 16.1 Required comparisons

| ID | Comparison | Decision |
|---|---|---|
| B0 | Direct persistence and seasonal forecasts | Does dispatch add useful information? |
| B1 | NEMPy with fixed or seasonal bounds | What does the basic market model achieve? |
| B2 | NEMPy with persistence bounds | What does current network state add? |
| E1 | NEMPy with out-of-fold mean bounds | Do forecast bounds improve flow and spread results? |
| E2 | E1 with joint uncertainty | Do probabilities and risk ranges improve? |
| N1 | E2 with NOS scenarios | Does NOS add value on common rows? |
| C1 | Complete equation scenarios | Does redispatch improve useful results? |
| H1 | Selected or combined model outputs | Does combination improve the result? |
| A1 | Matched AEMO forecasts | Does the extra work beat an available forecast? |

Check separate results by link, target, lead band, season, delivery period, and regime. Include unusual equations and incomplete inputs as separate groups.

Use time blocks and outage episodes for uncertainty estimates. Adjacent five-minute records are not independent observations.

Keep ordinary flow, metered flow, mean limits, and tight limits as separate targets. A target change needs its own comparison.

### 16.2 Required measures

| Result | Measures |
|---|---|
| Limits | MAE, RMSE, bias, excessive limits, and forced-flow errors |
| Flow | MAE, direction accuracy, ramps, and counter-price flow |
| Prices and spreads | Error, bias, quantile loss, and extreme-event results |
| Events | Recall, precision, false alerts, duration, and independent event count |
| Constraint outcomes | Candidate recall, binding probability, and limit-setter accuracy |
| Uncertainty | Coverage, width, interval score, and path-event probability |
| Engine | Balance error, violations, infeasibility, and runtime |
| Coverage | Complete, alternative, and unavailable forecast counts |

Do not select a model only because its average MAE is lower. Failed risk, uncertainty, or provenance checks can prevent approval.

Use matched AEMO versions only where the product supports the required horizon and target. Check product changes and historical coverage.

## 17. Prepare the month-ahead output

Use one 30-day calendar with two input contracts. Days 1–7 use the supported short-range methods. Days 8–30 use the separate scenario model.

Keep the day-seven change visible in the forecast basis. Check artificial changes in level, uncertainty, and scenario relationships. Do not smooth away a real outage start.

Each month-ahead scenario needs a complete time path. Include outage duration, unit return dates, weather periods, and energy budgets.

Representative days can reduce calculation work. Their weights must preserve the calendar and outage exposure. A sample of normal days can miss important tails.

Compare scenario reduction with a larger reference ensemble. Check long restrictions, energy depletion, and scarcity cases.

Publish four output levels:

- Half-hour paths for individual scenarios.
- Daily peak and off-peak summaries.
- Weekly distributions.
- Monthly exposure measures.

Aggregate each scenario before you calculate quantiles. The average of half-hour P90 values is not the P90 of the monthly average.

The first report should show expected congested hours and directional restriction exposure. It should also show spread ranges and the bookings that cause most uncertainty.

Do separate tests for days 8–14 and days 15–30. Compare each group with seasonal and outage-based references.

Refresh the origin and source snapshot for each new issue. Never use a later booking revision to change an earlier issued forecast.

## 18. Implementation plan and approval checks

<!-- visual:roadmap -->

| Stage | Deliverable | Required decision |
|---|---|---|
| 1 | Input, sign, and time contract | Can the required issue-time inputs be proved? |
| 2 | Synthetic checks and limited historical replay | Does the engine represent the stated problem? |
| 3 | Bound-model comparison | Do forecast bounds improve downstream forecasts? |
| 4 | Joint uncertainty and NOS scenarios | Do event and probability results improve? |
| 5 | Complete-equation pilot | Does redispatch justify the extra data work? |
| 6 | Separate month-ahead pilot | Does it beat seasonal and outage references? |
| 7 | Fixed routes and shadow forecasts | Do live receipt and outcome checks support approval? |

The month-ahead pilot can start after the shared contract and bound model. It need not wait for every equation mechanism.

Use ordinary network conditions and important outage families in the equation pilot. A sample of extreme outages cannot establish general performance.

Set approval thresholds before the final evaluation. Base thresholds on MW error, false alerts, source coverage, and acceptable delay.

Approve individual link, target, and lead cells when evidence supports them. Keep simpler methods for the other cells.

| Failure | Required action |
|---|---|
| Missing or old input | Use a checked alternative or report unavailable |
| Missing equation term | Stop use of that equation model |
| New equation version | Mark the new state and check its definition |
| Crossed bounds | Check signs, target meaning, and changes within the interval |
| Infeasible solution | Find the cause and record any explicit relaxation |
| Constraint violation | Show its size, cause, and effect on price |
| Unsupported outage overlap | Use an exploratory label without invented probability |

Do not swap crossed bounds silently. Do not delete negative values. A repair method needs its own evaluation and adjustment record.

Measure runtime before selecting the issue frequency. With 100 scenarios, one seven-day half-hour branch needs 33,600 interval solves. Five-minute resolution needs 201,600 solves.

These counts exclude internal reruns. They are workload calculations, not measured runtime estimates.

## 19. Additional experiments

**AEMO forecast correction.** Use issue-known AEMO forecasts as a separate starting point. Add the project network information only if common-row results improve.

**Model disagreement.** Compare the bound model with the complete equation model. Check whether large differences identify large later errors.

**Value of better inputs.** In conditional tests, replace one input group with actual values. Use the result to select the next data investment.

**Constraint sensitivity.** Change an RHS by a small amount and calculate dispatch again. Check larger changes separately because another equation can become limiting.

**Mechanism-based analogs.** Select historical paths with similar network coefficients and operating states. Compare this method with calendar-only analogs.

**Decision-specific selection.** After general accuracy checks, add a defined use case such as congestion-hours prediction. Keep all general accuracy and risk measures visible.

## 20. Sources, terms, and verification

### 20.1 Evidence status

This report uses saved research results. It does not download new market history or train forecast models. All measured claims retain their original research limits.

The numerical example uses synthetic NEMPy results. The interactive controls use the same algebraic example. They do not run a live market forecast.

The charts use source values or explicit calculations from those values. Every chart provides a table and a CSV download. Design diagrams contain no estimated accuracy scores.

The HTML contains its charts, styles, controls, and data downloads. It works without an internet connection. External source links still need internet access.

### 20.2 Controlled terms

Use the same term for the same quantity throughout the report.

<!-- visual:glossary -->

Technical identifiers remain unchanged. Examples include `IMPORTLIMIT`, `own_anchor`, and NEMPy method names. Mathematical symbols retain their stated meanings.

### 20.3 Language review

The review uses ASD-STE100 Issue 9 as its language target. The automated checks use a stricter limit of 20 words for ordinary prose sentences.

The review also checks paragraph length, contractions, selected complex wording, and consistent technical terms. Code, equations, identifiers, and source titles have separate treatment.

The official public guidance and indexed rule extracts were available. Direct access to the full standard PDF returned an access restriction.

The review therefore cannot confirm every approved word, grammatical role, and meaning. This report does not claim full ASD-STE100 conformity. The language record identifies this open check.

Sources: [official STE guidance](https://www.asd-ste100.org/STE_faq.html) and [Issue 9 reference](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf).

### 20.4 Research sources

- [Original design assessment](../nempy_forward_forecast_design_20261004/Forward_Forecast_with_NEMPy.md).
- [VNI model results](../../docs/VNI_DIURNAL_NOS_RESULTS.md).
- [QNI model results](../../docs/QNI_DIURNAL_NOS_RESULTS.md).
- [NOS mechanism results](../../execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md).
- [VNI constraint study](../../docs/VNI_TWO_YEAR_CONSTRAINT_STUDY.md).
- [QNI constraint study](../../docs/QNI_TWO_YEAR_CONSTRAINT_STUDY.md).
- [Original conditional backtest](../../BACKTEST_REPORT.md).
- [Data and feature definitions](../../docs/RESULTS_DATA_AND_FEATURES.md).
- [Clustering research report](../qni_vni_clustering_v1/Clustering_Research.md).
- [Fundamentals-v3 execution guide](../../execution/qni_vni_fundamentals_v3/README.md).

### 20.5 Report files

The [manifest](manifest.json) records source and output hashes. The [language record](language_review.json) records the automated checks and review limits.

The [verification record](verification.json) records links, hashes, controls, and browser checks. The [evidence file](data/research_evidence.json) contains the chart data and source references.

Use the report build command to create the HTML again:

```text
python scripts/build_nempy_visual_ste_report.py
```

The build uses local evidence. It does not retrain models or refresh market data.
