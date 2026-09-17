"""Optional NOS/constraint scaffold with explicit as-of and effect semantics."""
import pandas as pd
import numpy as np


def candidates(outages, links, origin, delivery, connector):
    """Inputs: revisioned outages and effective, connector-specific constraint links.

    Outages: outage_id, issue, received, start, end, status, equipment.
    Links: equipment, constraint_id, connector, effective_from, effective_to, received.
    Invocation is deliberately not inferred from scheduled exposure.
    """
    origin, delivery = pd.Timestamp(origin), pd.Timestamp(delivery)
    known = outages[(outages.issue <= origin) & (outages.received <= origin)]
    known = known.sort_values(["issue", "received"]).drop_duplicates("outage_id", keep="last")
    active = known[(known.status != "cancelled") & (known.start < delivery) & (known.end > delivery - pd.Timedelta(minutes=30))]
    valid = links[(links.connector == connector) & (links.received <= origin)
                  & (links.effective_from <= delivery) & (links.effective_to > delivery)]
    result = active.merge(valid, on="equipment", suffixes=("_outage", "_link"))
    result["evidence"] = "scheduled exposure; invocation and limit setting unknown"
    return result


def rank_effects(events, minimum_events=30):
    """Matched-event estimates supplied by analysis; not raw causal claims.

    Rows: outage_id, event_id, connector, target, estimated_reduction_mw.
    """
    keys = ["outage_id", "connector", "target"]
    unique = events.groupby(keys + ["event_id"], as_index=False).estimated_reduction_mw.mean()
    result = unique.groupby(keys).estimated_reduction_mw.agg(["count", "mean", "std"]).reset_index()
    result["standard_error_mw"] = result["std"] / result["count"] ** .5
    result["evidence"] = result["count"].map(lambda n: "exploratory association" if n < minimum_events else "supported association; not causal")
    return result.sort_values("mean", ascending=False)


def equation_bound(rhs, coefficients, forecast_values, connector_term):
    """Only a complete linear equation can yield a bound; caller supplies inequality."""
    coefficient = coefficients[connector_term]
    if not coefficient:
        raise ValueError("Zero connector coefficient")
    missing = set(coefficients) - {connector_term} - set(forecast_values)
    if missing:
        raise ValueError(f"Equation unavailable: missing {sorted(missing)}")
    return (rhs - sum(v * forecast_values[k] for k, v in coefficients.items() if k != connector_term)) / coefficient


def fit_setter_ranker(frame, features):
    """Cross-fit candidate-level setter probabilities before stacking into limits.

    Rows include origin, delivery, constraint_id, is_setter and as-of numeric
    features. Unknown constraint families must be encoded by the caller's recipe.
    Initial training-only rows have no OOF probability and cannot enter stacking.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from .training import folds
    data = frame.reset_index(drop=True).copy()
    for col in ("origin", "delivery"):
        data[col] = pd.to_datetime(data[col], utc=True)
    if not set(data.is_setter.unique()) <= {0, 1}:
        raise ValueError("is_setter must be binary")
    data["oof_probability"] = np.nan
    for train, test in folds(data):
        labels = data.loc[train, "is_setter"]
        if labels.nunique() == 1:
            data.loc[test, "oof_probability"] = float(labels.iloc[0])
        else:
            model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=17))
            model.fit(data.loc[train, features], labels)
            data.loc[test, "oof_probability"] = model.predict_proba(data.loc[test, features])[:, 1]
    if data.is_setter.nunique() < 2:
        raise ValueError("Need both setter and non-setter cases for fitted ranking model")
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=500, random_state=17))
    model.fit(data[features], data.is_setter)
    return model, data
