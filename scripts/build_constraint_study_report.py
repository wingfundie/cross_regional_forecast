"""Build reproducible Markdown and standalone HTML reports from a completed IC study."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

import markdown
import pandas as pd
import plotly.express as px
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "report_theme"))
from report_theme import VERSION, finding, hero, metric, render_page, style_plotly  # noqa: E402

from nemic.constraint_ingest import load_config, study_paths  # noqa: E402


def md_table(frame):
    return frame.to_markdown(index=False).replace("nan", "—")


def fmt(value, digits=2):
    return "—" if pd.isna(value) else f"{value:,.{digits}f}"


def active_sets(tables, leading_versions, start, end):
    membership = pd.read_parquet(tables / "GENCONSET.parquet").copy()
    for column in ["EFFECTIVEDATE", "GENCONEFFDATE"]:
        membership[column] = pd.to_datetime(membership[column], errors="coerce")
    for column in ["VERSIONNO", "GENCONVERSIONNO"]:
        membership[column] = pd.to_numeric(membership[column], errors="coerce")
    invoke = pd.read_parquet(tables / "GENCONSETINVOKE.parquet").copy()
    invoke["STARTINTERVALDATETIME"] = pd.to_datetime(invoke.STARTINTERVALDATETIME, errors="coerce")
    invoke["ENDINTERVALDATETIME"] = pd.to_datetime(invoke.ENDINTERVALDATETIME, errors="coerce")
    invoked = set(invoke.loc[
        (invoke.STARTINTERVALDATETIME <= end)
        & (invoke.ENDINTERVALDATETIME.isna() | (invoke.ENDINTERVALDATETIME >= start)),
        "GENCONSETID",
    ].dropna())
    # Set change rows often leave GENCONEFFDATE/GENCONVERSIONNO blank, so map
    # membership by constraint ID while retaining exact versions elsewhere.
    matched = leading_versions[["CONSTRAINTID"]].drop_duplicates().merge(
        membership[["GENCONID", "GENCONSETID"]].drop_duplicates(),
        left_on="CONSTRAINTID", right_on="GENCONID", how="left")
    return (matched.groupby("CONSTRAINTID").GENCONSETID
            .agg(lambda values: ", ".join(sorted({str(x) + (" (invoked)" if x in invoked else "")
                                                   for x in values.dropna()})))
            .to_dict()), invoked


def build(config_path):
    config_path = Path(config_path).resolve()
    config = load_config(config_path)
    pilot, _, tables = study_paths(config)
    start, end = pd.Timestamp(config["start"]), pd.Timestamp(config["end"])
    summary = json.loads((pilot / "influence_summary.json").read_text())
    audit = json.loads((pilot / "feature_audit.json").read_text())
    scores = json.loads((pilot / "pilot_scores.json").read_text())["targets"]
    downloads = json.loads((pilot / "download_audit.json").read_text())
    dependency = json.loads((pilot / "dependency_audit.json").read_text())
    influence = pd.read_csv(pilot / "generator_influence.csv")
    constraints = pd.read_csv(pilot / "constraint_influence.csv")
    features = pd.read_parquet(pilot / "constraint_features_5min.parquet")
    equations = pd.read_parquet(pilot / "equation_state.parquet")
    sensitivity = pd.read_parquet(pilot / "unit_sensitivities.parquet")

    states = []
    for direction in ["upper", "lower"]:
        part = features[[f"{direction}_constraint", f"{direction}_version_key"]].copy()
        part.columns = ["CONSTRAINTID", "version_key"]
        part["direction"] = direction
        states.append(part)
    leading = pd.concat(states).dropna(subset=["CONSTRAINTID", "version_key"])
    key_counts = leading.groupby(["direction", "CONSTRAINTID", "version_key"]).size().rename("version_intervals").reset_index()
    version_meta = equations[["version_key", "CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO", "ic_factor",
                              "LIMITTYPE", "DESCRIPTION"]].drop_duplicates("version_key")
    leading_versions = key_counts.merge(version_meta, on=["version_key", "CONSTRAINTID"], how="left")
    set_map, invoked_sets = active_sets(tables, leading_versions, start, end)

    equation_rows = constraints.dropna(subset=["constraint"]).merge(
        leading_versions.groupby(["direction", "CONSTRAINTID"], as_index=False).agg(
            versions=("version_key", "nunique"), ic_factor_min=("ic_factor", "min"),
            ic_factor_max=("ic_factor", "max"), limit_type=("LIMITTYPE", "first"),
            description=("DESCRIPTION", "first")),
        left_on=["direction", "constraint"], right_on=["direction", "CONSTRAINTID"], how="left")
    equation_rows["sets"] = equation_rows.constraint.map(set_map).fillna("")
    eq_display = equation_rows[["direction", "constraint", "leading_intervals", "versions",
                                "ic_factor_min", "ic_factor_max", "limit_type",
                                "contraction_episodes", "reversal_events", "forced_intervals", "sets"]].copy()
    eq_display.columns = ["Direction", "Constraint", "Leading intervals", "Versions", "a min", "a max",
                          "Type", "Contraction episodes", "Reversals", "Forced intervals", "Sets"]
    for col in ["a min", "a max"]:
        eq_display[col] = eq_display[col].map(lambda x: fmt(x, 4))

    leading_keys = set(leading.version_key)
    factor_stats = (sensitivity[sensitivity.version_key.isin(leading_keys)]
                    .groupby("DUID", as_index=False).agg(
                        leading_versions=("version_key", "nunique"), factor_min=("FACTOR", "min"),
                        factor_mean=("FACTOR", "mean"), factor_max=("FACTOR", "max"),
                        sensitivity_mean=("sensitivity", "mean"),
                        sensitivity_abs_max=("sensitivity", lambda x: x.abs().max())))
    generators = influence.merge(factor_stats, on="DUID", how="left").sort_values("overall_rank")
    gen_display = generators.head(25)[[
        "overall_rank", "DUID", "active_state_intervals", "leading_versions", "factor_min", "factor_mean",
        "factor_max", "sensitivity_mean", "sensitivity_abs_max", "total_abs_impact_mw_observations",
        "mean_abs_bound_impact_mw", "p95_abs_bound_impact_mw", "contraction_rank", "reversal_rank", "forced_rank"]].copy()
    gen_display.columns = ["Rank", "DUID", "Active rows", "Leading versions", "b min", "b mean", "b max",
                           "Mean s", "Max abs s", "Exposure MW-observations", "Mean abs impact MW",
                           "P95 abs impact MW", "Contraction rank", "Reversal rank", "Forced rank"]
    for col in ["b min", "b mean", "b max", "Mean s", "Max abs s", "Mean abs impact MW", "P95 abs impact MW"]:
        gen_display[col] = gen_display[col].map(lambda x: fmt(x, 3))
    gen_display["Exposure MW-observations"] = gen_display["Exposure MW-observations"].map(lambda x: fmt(x, 0))
    for col in ["Rank", "Contraction rank", "Reversal rank", "Forced rank"]:
        gen_display[col] = gen_display[col].map(lambda x: "—" if pd.isna(x) else str(int(x)))

    contraction_display = generators.dropna(subset=["contraction_rank"]).sort_values("contraction_rank").head(10)[[
        "contraction_rank", "DUID", "contraction_contribution_rows", "contraction_mean_tightening_mw",
        "contraction_positive_share"]].copy()
    contraction_display.columns = ["Rank", "DUID", "Rows", "Mean tightening MW", "Tightening share"]
    contraction_display["Rank"] = contraction_display.Rank.astype(int)
    contraction_display["Mean tightening MW"] = contraction_display["Mean tightening MW"].map(lambda x: fmt(x, 2))
    contraction_display["Tightening share"] = contraction_display["Tightening share"].map(lambda x: f"{x:.1%}")
    reversal_display = generators.dropna(subset=["reversal_rank"]).sort_values("reversal_rank").head(10)[[
        "reversal_rank", "DUID", "reversal_contribution_rows", "reversal_mean_abs_impact_mw",
        "reversal_flow_alignment"]].copy()
    reversal_display.columns = ["Rank", "DUID", "Rows", "Mean abs impact MW", "Flow alignment"]
    reversal_display["Rank"] = reversal_display.Rank.astype(int)
    reversal_display["Mean abs impact MW"] = reversal_display["Mean abs impact MW"].map(lambda x: fmt(x, 2))
    reversal_display["Flow alignment"] = reversal_display["Flow alignment"].map(lambda x: f"{x:.1%}")
    forced_display = generators.dropna(subset=["forced_rank"]).sort_values("forced_rank").head(10)[[
        "forced_rank", "DUID", "forced_contribution_rows", "forced_mean_abs_impact_mw"]].copy()
    forced_display.columns = ["Rank", "DUID", "Rows", "Mean abs impact MW"]
    forced_display["Rank"] = forced_display.Rank.astype(int)
    forced_display["Mean abs impact MW"] = forced_display["Mean abs impact MW"].map(lambda x: fmt(x, 2))

    weights = leading.groupby("version_key").size().rename("leading_intervals")
    term_rows = sensitivity[sensitivity.version_key.isin(leading_keys)].merge(weights, on="version_key")
    term_rows["weighted_sensitivity"] = term_rows.sensitivity.abs() * term_rows.leading_intervals
    key_direction = leading.drop_duplicates("version_key").set_index("version_key").direction
    term_rows["direction"] = term_rows.version_key.map(key_direction)
    dominant_constraints = equation_rows.dropna(subset=["constraint"]).nlargest(10, "leading_intervals").constraint
    dominant = (term_rows[term_rows.GENCONID.isin(dominant_constraints)]
                .sort_values("weighted_sensitivity").groupby("GENCONID", as_index=False).tail(5)
                .sort_values(["leading_intervals", "GENCONID", "weighted_sensitivity"], ascending=[False, True, False]))
    dominant_display = dominant[["direction", "GENCONID", "DUID", "leading_intervals", "ic_factor", "FACTOR", "sensitivity"]].copy()
    dominant_display.columns = ["Direction", "Constraint", "DUID", "Leading intervals", "a IC", "b unit", "s = -b/a"]
    for col in ["a IC", "b unit", "s = -b/a"]:
        dominant_display[col] = dominant_display[col].map(lambda x: fmt(x, 4))

    stable = generators[generators.active_state_intervals >= 1000].head(10).DUID.tolist()
    episodic = generators[generators.active_state_intervals < 1000].head(8).DUID.tolist()
    score_by_target = {row["target"]: row for row in scores}
    exp = score_by_target["export_tight"]
    imp = score_by_target["import_tight"]
    compressed = downloads["compressed_bytes"]

    report = f"""# QNI generator influence and constraint-feature study

## Research question and result

This rerun asks which generators most strongly and persistently moved the constraint-derived `NSW1-QLD1` (QNI) directional bounds during February 2026, including sharp limit contractions, flow reversals and forced-direction limits. It also tests whether 14 compact network-state features improve a one-step persistence benchmark.

The strongest broad-coverage candidates are **{', '.join(stable)}**. The highest exposure ranks also contain episodic units—**{', '.join(episodic)}**—whose large impacts occur across fewer than 1,000 active rows. These should enter a forecast as regime-conditioned signed pressures, not as unconditional raw-generation features.

The one-month model result is mixed. Import-limit MAE improved by {imp['mae_improvement']:.2f} MW ({imp['relative_improvement']:.2%}), while export-limit MAE worsened by {abs(exp['mae_improvement']):.2f} MW ({abs(exp['relative_improvement']):.2%}). QNI’s reconstructed limit MAE is {audit['upper_reconstruction_mae_mw']:.2f} MW export and {audit['lower_reconstruction_mae_mw']:.2f} MW import. This is adequate for feature exploration but requires equation-eligibility and setter-attribution work before an operational claim.

## Scope and headline evidence

| Item | Result |
|---|---:|
| Study period | 1–28 February 2026 |
| Native resolution | 5 minutes |
| Intervals | {summary['five_minute_intervals']:,} |
| Generators with valid sensitivities | {summary['generator_count']:,} |
| Constraints leading an envelope | {summary['leading_constraint_count']:,} |
| Flow reversal events | {summary['flow_reversal_events']:,} |
| Upper contractions: intervals / episodes | {summary['upper_contraction_intervals']:,} / {summary['upper_contraction_episodes']:,} |
| Lower contractions: intervals / episodes | {summary['lower_contraction_intervals']:,} / {summary['lower_contraction_episodes']:,} |
| Forced upper / lower intervals | {summary['upper_forced_intervals']:,} / {summary['lower_forced_intervals']:,} |
| Envelope coverage, upper / lower | {audit['upper_coverage']:.2%} / {audit['lower_coverage']:.2%} |
| Exact-version equation coverage | {audit['exact_version_match_fraction']:.2%} |

This is a descriptive mechanical-attribution study. Dispatch changes, constraint coefficients and the active envelope are observed together. The rankings do not identify independent causal effects because dispatch responds to prices, regional balance and the same constraints being studied.

## Method

For each solved generic constraint and exact effective version, the study isolates QNI from AEMO’s published solved left-hand side:

```text
a * QNI + sum(b_i * P_i) + other terms <= RHS
conditional QNI bound = observed QNI + (RHS - solved LHS) / a
unit sensitivity s_i = -b_i / a
30-minute unit bound impact = s_i * delta P_i
```

Positive `a` is treated as an upper QNI bound and negative `a` as a lower signed-flow bound. At each interval, the minimum valid upper bound and maximum valid lower bound form the directional envelope. The pipeline also retains the runner-up gap, coefficient-weighted tightening and relief, available ramp-limited relief, completeness flags, and the exact leading equation/version.

A contraction is a 30-minute directional-limit fall in the worst 10% of positive drops: at least {summary['upper_contraction_threshold_mw']:.2f} MW for the upper direction or {summary['lower_contraction_threshold_mw']:.2f} MW for the lower direction. Consecutive contraction intervals are grouped into episodes. A reversal is one crossing of the last non-zero observed flow sign. A forced state occurs when a directional capacity is negative.

## Generator influence ranking

`Exposure MW-observations` is the sum of absolute coefficient-weighted 30-minute impacts while the unit appears in the leading equation. It rewards persistence and magnitude. Mean and P95 impact separate intensity from persistence. Event ranks require at least 20 contribution rows.

{md_table(gen_display)}

The leading raw rank is not automatically the best compact feature. Tumut 3, for example, ranks first but appears in only 238 active rows and four leading versions; its mean impact is amplified by QNI coefficients between roughly 0.17 and 0.36 in those equations. That makes it a useful outage/regime indicator and tail-pressure feature, but weak evidence for a stable unconditional QNI driver. The broad-coverage group should anchor the first compact panel, while episodic hydro/solar units can be pooled into a tail-pressure feature or activated by constraint family.

### Sharp limit contractions

{md_table(contraction_display)}

Mean tightening preserves sign: a positive value means the unit movement mechanically reduced capacity in the relevant direction. The tightening share shows how often the contribution had that sign; large means with modest shares indicate asymmetric tails rather than a universal directional rule.

### Flow reversals

{md_table(reversal_display)}

Flow alignment compares the sign of the coefficient-weighted bound impact with the observed 30-minute flow move. Values around 50% reinforce that regional balance, losses, other constraints and simultaneous unit movements still determine actual QNI direction.

### Forced-direction limits

{md_table(forced_display)}

These ranks describe intervals where an export or import directional capacity was negative. They identify units exposed to the equations forcing QNI into one direction; they do not prove the unit independently caused the forced-flow state.

## Leading constraint equations and invoked sets

The table includes all equations that led either directional envelope. `a` is the exact QNI coefficient range across leading versions. Set labels marked `(invoked)` had an invocation overlapping the study month; a blank set field means no matching set membership was found in the downloaded standing-data vintages.

{md_table(eq_display)}

## Dominant unit terms in the main equations

For the ten most frequent leading equations, the following are the five unit terms with the largest absolute sensitivity weighted by that equation’s leading-interval count.

{md_table(dominant_display)}

## Compact feature recommendation

Keep the production candidate near 20–25 numeric variables:

1. Upper/lower conditional bound, flow room and runner-up switch gap.
2. Upper/lower aggregate generator tightening, relief and 30-minute pressure change.
3. Upper/lower ramp-and-availability-limited relief.
4. Candidate count, pressure completeness, crossed-envelope flag and a compact constraint-family encoding.
5. Four to eight frozen signed unit-pressure features chosen across training months. Start the broad panel with {', '.join(stable[:8])}. Pool episodic units such as {', '.join(episodic[:5])} by regime until repeated months establish persistence.

For a forecast horizon, replace realised `delta P` with lagged dispatch plus generator scenarios or dispatch forecasts. Carry base/up/down pressure paths through the current candidate envelope so a different constraint can take over. Raw generator output without `s_i`, direction and constraint regime loses the topology-dependent sign.

## Model comparison

| Target | Rows | Persistence MAE | Compact-feature MAE | Improvement | Relative |
|---|---:|---:|---:|---:|---:|
| Export tight limit | {exp['test_rows']:,} | {exp['baseline_mae']:.2f} MW | {exp['candidate_mae']:.2f} MW | {exp['mae_improvement']:.2f} MW | {exp['relative_improvement']:.2%} |
| Import tight limit | {imp['test_rows']:,} | {imp['baseline_mae']:.2f} MW | {imp['candidate_mae']:.2f} MW | {imp['mae_improvement']:.2f} MW | {imp['relative_improvement']:.2%} |

This split is a retrospective feasibility comparison: 895 earlier half-hours train the model and 447 later half-hours test it. It is neither an untouched multi-month holdout nor an issue-time backtest. The export result says the current compact block should not be adopted wholesale without ablation and regime refinement.

## Data guard and reproducibility

The run requested only the 25 explicit table archives inherited by `configs/constraint_qni_pilot.json`: eight February standing/metadata tables, two February interval tables, and small historical standing-data supplements needed for exact equation versions. It did not download a full MMSDB snapshot or enumerate an archive directory. The audited compressed total was {compressed / 1024**2:.1f} MiB against a 2 GiB cap; all 25 files were reused from the integrity-checked cache. Extraction retained {dependency['constraint_count']:,} QNI-linked/setter constraint IDs and {dependency['mapped_duid_count']:,} mapped DUIDs. Raw and derived data stay under ignored `data/` paths and are not committed.

Rebuild commands:

```powershell
python run_constraint_pilot.py --config configs/constraint_qni_pilot.json
python scripts/build_constraint_study_report.py --config configs/constraint_qni_pilot.json
python scripts/build_docs_html.py
python -m unittest discover -s tests -v
```

## Limitations and next tests

- Exact QNI-factor coverage is {audit['exact_version_match_fraction']:.2%}; 14 observed setter IDs were absent from the base February factor archive, and older version supplements do not resolve every dispatch row.
- Setter agreement is {audit['upper_setter_match_fraction']:.1%} upper and {audit['lower_setter_match_fraction']:.1%} lower. Numeric reconstruction, eligibility rules, ties and omitted non-energy terms need investigation before using the reconstructed leader as definitive attribution.
- Ten connection points were unmapped to active DUID records in the extracted standing data. Their influence remains outside unit rankings.
- The rankings share common dispatch and equation regimes and should not be read as independent causal effects.
- Repeat non-contiguous seasonal and outage months, freeze generator selection on training months, run feature-block ablations, then evaluate a final untouched chronological holdout with issue-time-valid inputs.
"""

    markdown_path = ROOT / "docs" / "QNI_GENERATOR_INFLUENCE_STUDY.md"
    markdown_path.write_text(report, encoding="utf-8")

    top_chart = generators.head(20).copy()
    fig1 = px.bar(top_chart.sort_values("total_abs_impact_mw_observations"), x="total_abs_impact_mw_observations",
                  y="DUID", orientation="h", color="active_state_intervals",
                  labels={"total_abs_impact_mw_observations": "Absolute impact (MW-observations)",
                          "active_state_intervals": "Active rows", "DUID": "Generator"})
    style_plotly(fig1, "Top generator exposure under QNI-leading equations", height=650)
    fig2_data = constraints.dropna(subset=["constraint"]).head(15).sort_values("leading_intervals")
    fig2 = px.bar(fig2_data, x="leading_intervals", y="constraint", orientation="h", color="direction",
                  labels={"leading_intervals": "Five-minute leading intervals", "constraint": "Constraint"})
    style_plotly(fig2, "Most frequent QNI envelope-setting constraints", height=620)
    nav = '<nav><a href="#findings">Findings</a><a href="#generators">Generators</a><a href="#equations">Equations</a><a href="#methods">Methods and limits</a></nav>'
    metrics = '<div class="metrics">' + ''.join([
        metric("Intervals", f"{summary['five_minute_intervals']:,}", "February 2026 at five-minute resolution"),
        metric("Generators", f"{summary['generator_count']:,}", "Units with valid equation sensitivities"),
        metric("Leading equations", f"{summary['leading_constraint_count']:,}", "Set an upper or lower envelope"),
        metric("Input archives", "25", f"{compressed / 1024**2:.1f} MiB cached; 2 GiB guard"),
    ]) + '</div>'
    findings = '<section id="findings"><div class="section-kicker">KEY FINDINGS</div><div class="findings">' + ''.join([
        finding(1, "Broad and episodic influence differ", f"{', '.join(stable[:5])} have broad exposure. Tumut 3 leads total exposure across only 238 rows, so it belongs in a regime-conditioned tail feature."),
        finding(2, "Import gains are marginal", f"Import MAE improves {imp['mae_improvement']:.2f} MW, while export MAE worsens {abs(exp['mae_improvement']):.2f} MW in the one-month test."),
        finding(3, "Attribution still needs tightening", f"Envelope coverage is near complete, but reconstruction MAE is {audit['upper_reconstruction_mae_mw']:.1f}/{audit['lower_reconstruction_mae_mw']:.1f} MW and setter match is {audit['upper_setter_match_fraction']:.0%}/{audit['lower_setter_match_fraction']:.0%}."),
    ]) + '</div></section>'
    rendered = markdown.markdown(report, extensions=["tables", "fenced_code"])
    rendered = rendered.replace("<table>", '<div class="table-wrap" tabindex="0"><table>').replace("</table>", "</table></div>")
    body = (hero("NEM · CONSTRAINT-DERIVED NETWORK STATE", "Which generators move QNI?", "A February 2026 rerun",
                 "Exact-version constraint reconstruction, generator sensitivities, event influence and a compact-feature feasibility test for NSW1–QLD1.",
                 ["Data cutoff: 28 Feb 2026", "Built: 11 Sep 2026", "5-minute dispatch", "Offline report"])
            + nav + metrics + findings
            + '<section id="generators"><div class="section-kicker">GENERATOR EXPOSURE</div>'
            + '<figure><figcaption>Persistence-weighted mechanical influence</figcaption><div class="chart-scroll">'
            + pio.to_html(fig1, full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Colour shows the number of active leading-equation rows; low-row high-impact units are episodic.</p></figure></section>'
            + '<section id="equations"><div class="section-kicker">CONSTRAINT REGIMES</div><figure><figcaption>Leading equation frequency</figcaption><div class="chart-scroll">'
            + pio.to_html(fig2, full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Counts are five-minute intervals; direction uses the sign of the QNI coefficient.</p></figure></section>'
            + '<section id="methods" class="method">' + rendered + '</section>'
            + f'<footer>Generated from ignored local study outputs. Theme {VERSION}. Rebuild with <code>python scripts/build_constraint_study_report.py --config configs/constraint_qni_pilot.json</code>.</footer>')
    html_path = ROOT / "docs" / "html" / "qni_generator_influence_study.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_page("QNI generator influence study", body, plotly=True, accent="blue"), encoding="utf-8")
    manifest = {
        "config": str(config_path.relative_to(ROOT)),
        "config_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "inputs": {name: hashlib.sha256((pilot / name).read_bytes()).hexdigest() for name in [
            "feature_audit.json", "pilot_scores.json", "influence_summary.json", "generator_influence.csv",
            "constraint_influence.csv", "download_audit.json"]},
        "theme_version": VERSION,
        "command": f"python scripts/build_constraint_study_report.py --config {config_path.relative_to(ROOT)}",
        "offline": True,
    }
    (ROOT / "docs" / "html" / "qni_generator_influence_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(markdown_path)
    print(html_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    build(args.config)
