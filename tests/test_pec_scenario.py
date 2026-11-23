"""Scenario outputs agree with their source observations and the offline tool."""

from io import StringIO
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pytest

from nemic.experiments.pec import scenario


@pytest.fixture(scope="module")
def complete_half_hours():
    times = pd.date_range("2026-10-01 00:30", periods=48 * 4, freq="30min")
    row = np.arange(len(times))
    config = np.select(
        [row < 48 * 2, row < 48 * 3],
        ["commissioning; state A", "alternate + outage | transition, single day"],
        default="Commissioning cap unverified + outage",
    )
    frame = pd.DataFrame({
        "time": times, "configuration": config,
        "nsw_sa_tight": np.where(config == "commissioning; state A", row % 10 - 5, 100.0),
        "sa_nsw_tight": np.where(config == "commissioning; state A", 0, -100.0),
        "nsw_sa_mean": np.where(config == "commissioning; state A", row % 12 + 4.0, 100.0),
        "sa_nsw_mean": np.where(config == "commissioning; state A", row % 8 + 1.0, -100.0),
        "nsw_sa_setter": np.where(row % 4 == 0, "EXCEPTION", "EXPORT_CAP"),
        "sa_nsw_setter": "IMPORT_CAP", "nsw_sa_minimum_time": times - pd.Timedelta(minutes=5),
        "sa_nsw_minimum_time": times - pd.Timedelta(minutes=15),
        "nsw_sa_episode_id": "EX0001", "sa_nsw_episode_id": "IM0001",
    })
    for index, region in enumerate(scenario.REGIONS):
        frame[f"{region}_demand"] = 800 + 20 * row + 1100 * index
        frame[f"{region}_wind"] = 100 + 2 * row + 5 * index
        frame[f"{region}_solar"] = (row % 8) * 20
        frame[f"{region}_residual"] = frame[f"{region}_demand"] - frame[f"{region}_wind"] - frame[f"{region}_solar"]
    return frame


@pytest.fixture(scope="module")
def scenario_outputs(complete_half_hours, tmp_path_factory):
    return scenario.run(complete_half_hours, tmp_path_factory.mktemp("pec_scenario"))


def test_midnight_and_each_delivery_boundary(complete_half_hours):
    observations = scenario.prepare_observations(complete_half_hours)
    midnight = observations.loc[observations.time.eq("2026-10-02 00:00")].iloc[0]
    assert midnight.study_day == "2026-10-01"
    times = pd.Series(pd.to_datetime([
        "2026-10-01 06:00", "2026-10-01 06:30", "2026-10-01 09:00", "2026-10-01 09:30",
        "2026-10-01 16:00", "2026-10-01 16:30", "2026-10-01 21:00", "2026-10-01 21:30",
    ]))
    assert scenario.delivery_period(times).tolist() == [
        "overnight", "morning", "morning", "solar", "solar", "evening", "evening", "overnight",
    ]


def test_lookup_preserves_signed_limits_and_marks_low_support(scenario_outputs):
    outputs = scenario_outputs
    lookup = pd.read_csv(outputs["conditional_limits"])
    fixed = lookup.query("direction == 'sa_nsw' and aggregation == 'tight' and configuration.str.startswith('alternate')")
    assert fixed.p10_mw.eq(-100).all()
    assert fixed.p90_mw.eq(-100).all()
    assert fixed.distinct_days.eq(1).all()
    assert fixed.p50_ci_low_mw.isna().all()
    assert fixed.support.eq("single_day_example").all()
    zero = lookup.query("direction == 'sa_nsw' and aggregation == 'tight' and configuration.str.startswith('commissioning')")
    assert zero.p10_mw.eq(0).all()
    assert zero.p90_ci_high_mw.eq(0).all()
    evidence = pd.read_csv(outputs["conditional_support"])
    assert not lookup.configuration.str.contains("unverified").any()
    unresolved = evidence[evidence.configuration.str.contains("unverified")]
    assert len(unresolved) == 96 and not unresolved.configuration_evidenced.any()
    first = evidence[evidence.time.eq("2026-10-01 00:30")]
    assert first.set_index("direction")["minimum_time"].to_dict() == {
        "nsw_sa": "2026-10-01 00:25", "sa_nsw": "2026-10-01 00:15",
    }
    assert first.set_index("direction")["episode_id"].to_dict() == {
        "nsw_sa": "EX0001", "sa_nsw": "IM0001",
    }
    relationships = pd.read_csv(outputs["conditional_relationships"])
    assert {"all_setters", "within_setter"} == set(relationships.population)
    assert relationships.loc[relationships.distinct_days.eq(1), "spearman_r"].isna().all()


def test_bootstrap_resamples_days_instead_of_individual_intervals():
    days = pd.Series(["2026-10-01"] * 48 + ["2026-10-02"] * 48)
    limit = np.r_[np.zeros(48), np.full(48, 100)]
    assert np.array_equal(scenario.day_bootstrap(limit, days), [[0, 0, 0], [100, 100, 100]])


def _csv_download(page, button_name):
    with page.expect_download() as receipt:
        page.get_by_role("button", name=button_name, exact=True).click()
    return receipt.value.path().read_text(encoding="utf-8-sig")


def _read_result(page):
    return pd.read_csv(StringIO(_csv_download(page, "Download results")))


def _compare_estimates(left, right):
    columns = ["configuration", "delivery_period", "direction", "aggregation", "p10_mw", "p50_mw",
               "p90_mw", "intervals", "distinct_days", "dominant_setter", "support"]
    order = ["direction", "aggregation"]
    pd.testing.assert_frame_equal(left[columns].sort_values(order).reset_index(drop=True),
                                  right[columns].sort_values(order).reset_index(drop=True),
                                  check_dtype=False, atol=1e-8)


def verify_offline_scenario(output_dir: Path, qa_dir: Path | None = None):
    playwright = pytest.importorskip("playwright.sync_api")
    browser_path = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
    failures = []
    fetched = []
    if qa_dir is not None:
        qa_dir.mkdir(parents=True, exist_ok=True)
    with playwright.sync_playwright() as session:
        if browser_path.exists():
            browser = session.chromium.launch(executable_path=str(browser_path), headless=True)
        elif Path(session.chromium.executable_path).exists():
            browser = session.chromium.launch(headless=True)
        else:
            pytest.skip("Requires a local Chromium browser for offline UI verification.")
        page = browser.new_page(offline=True, accept_downloads=True, viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: failures.append(str(error)))
        page.on("request", lambda request: fetched.append(request.url) if request.url.startswith(("http:", "https:")) else None)
        page.goto((output_dir / "scenario.html").resolve().as_uri())
        lookup = pd.read_csv(output_dir / "downloads/conditional_limits.csv")
        reference = _read_result(page)
        config, period = reference.loc[0, ["configuration", "delivery_period"]]
        expected = lookup[(lookup.configuration == config) & (lookup.delivery_period == period)]
        _compare_estimates(reference, expected)
        assert page.locator("#result-table tbody tr").count() == 4
        if reference.loc[0, "distinct_days"] > 1:
            rendered_bounds = page.locator("#detail table").first.locator("tbody tr").first.locator("td").all_text_contents()
            item = expected.iloc[0]
            rendered_p10 = [float(bound.replace(",", "")) for bound in rendered_bounds[2].split(" to ")]
            np.testing.assert_allclose(rendered_p10, [item.p10_ci_low_mw, item.p10_ci_high_mw], atol=0.05)
        if qa_dir is not None:
            page.screenshot(path=qa_dir / "scenario_desktop.png", full_page=True)

        presets = pd.read_csv(output_dir / "downloads/condition_presets.csv")
        sample = presets.loc[presets.preset.eq("median_residual")].iloc[0]
        page.select_option("#configuration", sample.configuration)
        page.select_option("#period", sample.delivery_period)
        page.select_option("#preset", sample.preset)
        page.get_by_role("button", name="Estimate limits", exact=True).click()
        from_conditions = _read_result(page)
        page.locator("#feature-details summary").click()
        demand = page.get_by_label("NSW demand MW", exact=True)
        demand.clear()
        demand.fill(str(sample.nsw_demand))
        assert page.locator("#preset").input_value() == "custom"
        page.get_by_role("button", name="Estimate limits", exact=True).click()
        _compare_estimates(from_conditions, _read_result(page))

        page.get_by_role("button", name="Historical day", exact=True).click()
        page.select_option("#historical-day", sample.study_day)
        path_text = _csv_download(page, "Download this input path")
        page.get_by_role("button", name="Estimate using this day", exact=True).click()
        from_history = _read_result(page)
        _compare_estimates(from_conditions, from_history[from_history.time.eq(sample.time)])

        page.get_by_role("button", name="Upload a CSV path", exact=True).click()
        page.locator("#path-file").set_input_files({
            "name": "selected-day.csv", "mimeType": "text/csv", "buffer": path_text.encode("utf-8"),
        })
        page.get_by_role("button", name="Estimate path", exact=True).click()
        page.wait_for_function("document.querySelector('#status').textContent.startsWith('Uploaded path')")
        pd.testing.assert_frame_equal(from_history, _read_result(page))

        unsupported = "time,configuration\n2026-11-23 00:30,UNSEEN_TEST_CONFIGURATION\n"
        page.locator("#path-file").set_input_files({
            "name": "unseen.csv", "mimeType": "text/csv", "buffer": unsupported.encode("utf-8"),
        })
        page.get_by_role("button", name="Estimate path", exact=True).click()
        page.wait_for_function("document.querySelector('#status').textContent.includes('1 unsupported')")
        refused = _read_result(page)
        assert refused.support.eq("unsupported").all()
        assert refused.p50_mw.isna().all()
        assert refused.intervals.eq(0).all()

        evidence = pd.read_csv(output_dir / "downloads/conditional_support.csv")
        unresolved = evidence[~evidence.configuration_evidenced].dropna(subset=["configuration"])
        if not unresolved.empty:
            example = unresolved.iloc[0]
            page.get_by_role("button", name="Historical day", exact=True).click()
            page.select_option("#historical-day", example.study_day)
            page.get_by_role("button", name="Estimate using this day", exact=True).click()
            replayed = _read_result(page)
            targets = replayed[replayed.time.eq(example.time)]
            assert len(targets) == 4 and targets.support.eq("unsupported").all()

        page.get_by_role("button", name="Regional conditions", exact=True).click()
        page.get_by_role("button", name="Estimate limits", exact=True).click()
        page.set_viewport_size({"width": 390, "height": 844})
        page.evaluate("window.scrollTo(0, 0)")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert page.locator("#result-wrap").evaluate("element => element.scrollWidth <= element.clientWidth + 1")
        assert page.locator("#result-wrap").evaluate("element => element.scrollHeight <= element.clientHeight + 1")
        if qa_dir is not None:
            page.screenshot(path=qa_dir / "scenario_mobile.png", full_page=True)
        assert failures == []
        assert fetched == []
        if qa_dir is not None:
            checks = {
                "passed": True,
                "viewports": {"desktop": [1440, 1000], "mobile": [390, 844]},
                "agreed_with_reference_csv": {"configuration": config, "delivery_period": period},
                "agreed_across_modes": {
                    "preset": sample.preset, "input_time_nem": sample.time,
                    "configuration": sample.configuration, "uploaded_path_rows": len(from_history) // 4,
                },
                "unseen_configuration": "unsupported",
                "external_requests": fetched, "browser_errors": failures,
            }
            (qa_dir / "scenario_checks.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
        browser.close()


def test_offline_modes_agree_with_downloads(scenario_outputs):
    verify_offline_scenario(scenario_outputs["scenario"].parent)
