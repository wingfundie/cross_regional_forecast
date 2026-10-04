import json

import pandas as pd

from nemic.production.outage_scenarios import apply_local_edits, standard_scenarios, write_scenarios


def outages():
    origin = pd.Timestamp("2026-01-02T08:00:00+10:00")
    return origin, pd.DataFrame([
        dict(outage_id="planned", equipment="line-a", issue=origin-pd.Timedelta(days=2),
             received=origin-pd.Timedelta(days=2)+pd.Timedelta(minutes=5), start=origin+pd.Timedelta(hours=1),
             end=origin+pd.Timedelta(hours=5), status="planned"),
        dict(outage_id="forced", equipment="line-b", issue=origin-pd.Timedelta(hours=2),
             received=origin-pd.Timedelta(hours=1), start=origin-pd.Timedelta(hours=1),
             end=origin+pd.Timedelta(hours=2), status="forced"),
    ])


def test_standard_outage_scenarios_preserve_baseline_and_extend_planned():
    origin, frame = outages()
    scenarios = standard_scenarios(frame, origin)
    assert set(scenarios) == {"baseline", "no_planned_outages", "planned_extended_24h"}
    assert set(scenarios["no_planned_outages"].outage_id) == {"forced"}
    base_end = scenarios["baseline"].set_index("outage_id").loc["planned", "end"]
    extended_end = scenarios["planned_extended_24h"].set_index("outage_id").loc["planned", "end"]
    assert extended_end - base_end == pd.Timedelta(hours=24)


def test_local_edits_are_explicit_and_manifested(tmp_path):
    origin, frame = outages()
    baseline = standard_scenarios(frame, origin)["baseline"]
    edits = pd.DataFrame([dict(action="cancel", outage_id="planned")])
    local = apply_local_edits(baseline, edits, origin, "desk_case")
    assert set(local.outage_id) == {"forced"}
    manifest = write_scenarios(frame, origin, tmp_path / "scenarios", edits, "desk_case")
    payload = json.loads(manifest.read_text())
    assert {row["scenario"] for row in payload["scenarios"]} == {
        "baseline", "no_planned_outages", "planned_extended_24h", "desk_case"}
