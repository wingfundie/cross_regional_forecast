"""Evaluate two public demand proxies against independent five-minute case inputs."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.rhs_regional_feed import public_regional_feed

REPORT = ROOT / "reports/rhs_replay"
OUT = REPORT / "proxies"
TOL = 0.0001  # MW, above rounding at the precision of the published solution


def episodes(data, event):
    groups = (event.ne(event.shift()) | data.interval_end.diff().ne(pd.Timedelta(minutes=5))).cumsum()
    return [group for _, group in data[event].groupby(groups[event])]


def summarize(data):
    active = data.marginal_value.abs() > 1e-5
    tight = data.official_headroom <= TOL
    runs = episodes(data, active)
    return dict(n=len(data), input_bias=data.input_error.mean(), input_mae=data.input_error.abs().mean(),
                rhs_bias=data.rhs_error.mean(), rhs_mae=data.rhs_error.abs().mean(),
                rhs_max=data.rhs_error.abs().max(), band_mw=data.band_mw.iat[0],
                covered=int((data.rhs_error.abs() <= data.band_mw + 1e-9).sum()),
                official_tight=int(tight.sum()), official_economic=int(active.sum()),
                violated=int((data.violation > TOL).sum()), economic_episodes=len(runs),
                missed_episodes=sum(g.call.eq("clear").all() for g in runs),
                confirmed_episodes=sum(g.call.eq("at risk").any() for g in runs),
                entirely_uncertain_episodes=sum(g.call.eq("uncertain").all() for g in runs),
                clear=int(data.call.eq("clear").sum()), at_risk=int(data.call.eq("at risk").sum()),
                uncertain=int(data.call.eq("uncertain").sum()),
                missed_economic=int((active & data.call.eq("clear")).sum()),
                false_alerts=int((~active & data.call.eq("at risk")).sum()),
                uncertain_economic=int((active & data.call.eq("uncertain")).sum()),
                unbanded_flips=int(((data.proxy_headroom <= TOL) != tight).sum()))


def run(refresh=False):
    cases = pd.read_csv(REPORT / "cases/replay.csv")
    cases["interval_end"] = pd.to_datetime(cases.interval_end, utc=True).dt.tz_convert(
        "Australia/Brisbane").dt.tz_localize(None)
    endpoints = cases.interval_end.unique()
    OUT.mkdir(parents=True, exist_ok=True)
    feed_path = OUT / "prior_public_reports.csv"
    if refresh or not feed_path.exists():
        aligned, sources, reports = public_regional_feed(endpoints, "NSW1")
        aligned.to_csv(feed_path, index=False)
        reports.to_csv(OUT / "dispatchis_extract.csv", index=False)
        (OUT / "regional_sources.json").write_text(json.dumps(sources, indent=2))
    feed = pd.read_csv(feed_path, parse_dates=["interval_end", "producer_time", "member_modified",
                                               "source_interval_end", "cutoff"])
    assert set(feed.interval_end) == set(endpoints)
    assert (feed[["producer_time", "member_modified"]].max(axis=1) <= feed.cutoff).all()
    assert (feed.source_interval_end < feed.interval_end).all()
    public_reports = pd.read_csv(OUT / "dispatchis_extract.csv", parse_dates=["source_interval_end"])
    rows, metrics, diagnostics, averaging = [], [], [], []
    for eq, selected in cases.dropna(subset=["demand_mw"]).groupby("equation"):
        d = selected.merge(feed, on="interval_end", validate="one_to_one").sort_values("interval_end")
        point = d.demand_spd.unique().item()
        train, tune, test = d.window.drop_duplicates()
        d = d.dropna(subset=[point, "regional_mw", "rhs_reference", "rhs_replay", "lhs"])
        calibration = d.window.eq(train)
        share = d.loc[calibration, "demand_mw"].sum() / d.loc[calibration, "regional_mw"].sum()
        same = d.merge(public_reports[["source_interval_end", point]], left_on="interval_end",
                       right_on="source_interval_end", suffixes=("", "_same"), validate="one_to_one")
        diff = same[point + "_same"] - same.demand_mw
        diagnostics.append(dict(equation=eq, point=point, recovered_observations=len(diff),
                                snapshot_max_abs_mw=diff.abs().max(), nsw_share=share,
                                regional_fit_window=train, uncertainty_window=tune, holdout=test))
        # Same-interval public snapshots above are checked only as measurements.
        # All scored public predictors below come from reports preceding the target interval.
        sign = d.relation.map({"LE": 1, "<=": 1, "GE": -1, ">=": -1})
        assert sign.notna().all()
        d["official_headroom"] = sign * (d.rhs_reference - d.lhs)
        d["exact_headroom"] = sign * (d.rhs_replay - d.lhs)
        def rhs(load):
            return d.proxy_constant + load * (d.proxy_linear + load * d.proxy_quadratic)
        assert (rhs(d.demand_mw) - d.rhs_replay).abs().max() < 0.0001
        half_hour = d.interval_end.dt.ceil("30min")
        for (window, end), block in d.groupby([d.window, half_hour]):
            if len(block) != 6 or block.interval_end.nunique() != 6:
                continue
            avg = block.demand_mw.mean()
            error = block.proxy_constant + avg * (block.proxy_linear + avg * block.proxy_quadratic) - block.rhs_replay
            averaging.append(dict(equation=eq, window=window, halfhour_end=end, n=6,
                                  average_input_mw=avg, input_mae=(block.demand_mw - avg).abs().mean(),
                                  rhs_mae=error.abs().mean(), rhs_max=error.abs().max()))
        for method, values in [("Prior public snapshot", d[point]), ("NSW demand share", d.regional_mw * share)]:
            out = d.copy()
            out["method"] = method
            out["proxy_input"] = values
            out["input_error"] = values - d.demand_mw
            out["proxy_rhs"] = rhs(values)
            out["rhs_error"] = out.proxy_rhs - d.rhs_replay
            out["proxy_headroom"] = sign * (out.proxy_rhs - d.lhs)
            band = out.loc[out.window.eq(tune), "rhs_error"].abs().max()
            assert np.isfinite(band)
            out["band_mw"] = band
            out["call"] = np.select([out.proxy_headroom - band > TOL, out.proxy_headroom + band <= TOL],
                                    ["clear", "at risk"], default="uncertain")
            for window, group in out.groupby("window", sort=False):
                metrics.append(dict(equation=eq, window=window, method=method, **summarize(group)))
            rows.append(out)
    pd.DataFrame(diagnostics).to_csv(OUT / "source_checks.csv", index=False)
    pd.DataFrame(averaging).to_csv(OUT / "halfhour_diagnostic.csv", index=False)
    pd.DataFrame(metrics).to_csv(OUT / "metrics.csv", index=False)
    pd.concat(rows, ignore_index=True).to_csv(OUT / "interval_results.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-feed", action="store_true")
    run(parser.parse_args().refresh_feed)
