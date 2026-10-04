import pandas as pd

from nemic.production.daily_risk import group_windows, score_daily_bulletins, threshold_for_budget


def test_daily_exposure_uses_issued_bulletins_not_half_hour_frequency():
    issue = pd.Timestamp("2026-01-01T08:00:00+10:00")
    windows = pd.DataFrame([
        dict(connector="VNI", direction="export", event_type="low_limit", issue=issue,
             start=issue + pd.Timedelta(hours=2), end=issue + pd.Timedelta(hours=3), probability=.8),
        dict(connector="VNI", direction="export", event_type="contraction", issue=issue,
             start=issue + pd.Timedelta(hours=2, minutes=30), end=issue + pd.Timedelta(hours=4), probability=.7),
    ])
    events = pd.DataFrame([dict(connector="VNI", direction="export",
                                start=issue + pd.Timedelta(hours=3), end=issue + pd.Timedelta(hours=3, minutes=30))])
    score = score_daily_bulletins(windows, events, .5, [issue])
    assert score["exposure_days"] == 1
    assert score["alerts"] == 1
    assert score["true_positive_episodes"] == 1
    assert score["recall"] == 1
    assert score["false_alert_hours"] == 0


def test_daily_warning_types_share_episode_budget_and_report_duration():
    issue = pd.Timestamp("2026-01-01T08:00:00+10:00")
    windows = pd.DataFrame([
        dict(connector="QNI", direction="import", event_type=event_type, issue=issue,
             start=issue + pd.Timedelta(hours=hour), end=issue + pd.Timedelta(hours=hour + 1), probability=.9)
        for hour, event_type in ((1, "low_limit"), (1, "contraction"), (6, "low_limit"))
    ])
    grouped = group_windows(windows)
    assert len(grouped) == 2
    score = score_daily_bulletins(windows, pd.DataFrame(columns=["connector", "direction", "start", "end"]), .5, [issue])
    assert score["false_positive_episodes"] == 2
    assert score["false_episodes_per_day"] == 2
    assert score["false_alert_hours"] == 2


def test_threshold_selection_respects_daily_budget():
    issue = pd.Timestamp("2026-01-01T08:00:00+10:00")
    windows = pd.DataFrame([
        dict(connector="VNI", direction="export", event_type="low_limit", issue=issue,
             start=issue + pd.Timedelta(hours=hour * 2), end=issue + pd.Timedelta(hours=hour * 2 + 1), probability=prob)
        for hour, prob in enumerate((.2, .4, .6, .8))
    ])
    events = pd.DataFrame(columns=["connector", "direction", "start", "end"])
    result = threshold_for_budget(windows, events, [.1, .5, .9], budget=3, eligible_issues=[issue])
    assert result["false_episodes_per_day"] <= 3


def test_unobservable_bulletins_do_not_enter_alert_exposure():
    issue = pd.Timestamp("2026-01-01T08:00:00+10:00")
    windows = pd.DataFrame([
        dict(connector="VNI", direction="export", event_type="low_limit", issue=issued,
             start=issued+pd.Timedelta(hours=1), end=issued+pd.Timedelta(hours=2), probability=.9)
        for issued in (issue, issue+pd.Timedelta(days=1))
    ])
    events = pd.DataFrame(columns=["connector", "direction", "start", "end"])
    score = score_daily_bulletins(windows, events, .5, eligible_issues=[issue])
    assert score["eligible_bulletins"] == 1
    assert score["alerts"] == 1
