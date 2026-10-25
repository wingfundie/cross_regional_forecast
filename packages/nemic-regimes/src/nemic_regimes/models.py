"""Training-fitted conditional quantile challengers, optional inference dependency."""
from __future__ import annotations
import numpy as np
import pandas as pd

from .core import NUMERIC_FEATURES, QUANTILES


def design(frame, features, families):
    f = frame.copy()
    output = []
    for field in features:
        def val(x):
            if isinstance(x, dict):
                values = [float(v) for v in x.values()]
                return np.mean(values)
            return float(x) if x is not None else np.nan
        values = f[field].map(val).to_numpy() if field in f else np.full(len(f), np.nan)
        output.append(values)
    hh = pd.to_numeric(f.get("half_hour", pd.Series(24, index=f.index))).to_numpy()
    quarter = pd.to_numeric(f.get("quarter", pd.Series(1, index=f.index))).to_numpy()
    output.extend([np.sin(2*np.pi*hh/48), np.cos(2*np.pi*hh/48),
                   np.sin(2*np.pi*(quarter-1)/4), np.cos(2*np.pi*(quarter-1)/4)])
    states = f.get("outage_state", pd.Series("unknown", index=f.index))
    output.extend([(states == s).to_numpy(float) for s in ("clear", "invoked", "partial", "unknown")])
    for family in families:
        if "active_sets" in f:
            output.append(f.active_sets.fillna("").map(lambda v: float(family in set(v.split("|")))).to_numpy())
        else:
            output.append(f.get("required_sets", pd.Series([[] for _ in range(len(f))], index=f.index)).map(lambda v: float(family in v)).to_numpy())
    return np.column_stack(output).astype(float)


def fit_quantiles(train, target="capacity", method="boosting", max_rows=6000, seed=741):
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler
    features = [c for c in NUMERIC_FEATURES if c in train and train[c].notna().mean() >= .2 and train[c].nunique() > 1]
    family_count = train.active_sets.fillna("").str.split("|").explode().value_counts()
    families = [f for f in family_count.index if f][:20]
    # Deterministic evenly spaced sample preserves time-of-day and event variety without target-based oversampling.
    budget = min(max_rows, 1800 if method == "additive" else max_rows)
    if len(train) > budget:
        train = train.iloc[np.linspace(0, len(train)-1, budget, dtype=int)]
    x = design(train, features, families)
    imputer = SimpleImputer(strategy="median", keep_empty_features=True)
    scaler = StandardScaler()
    x = scaler.fit_transform(imputer.fit_transform(x))
    if method == "additive":
        # Piecewise additive terms; no interaction expansion or hidden dispatch reconstruction.
        x = np.column_stack([x, np.maximum(x-1, 0), np.maximum(-x-1, 0)])
    estimators = []
    for q in QUANTILES:
        if method == "additive":
            from scipy.optimize import minimize
            from scipy.special import expit
            y=train[target].to_numpy(float)
            centre=float(np.median(y));scale=max(float(np.quantile(y,.75)-np.quantile(y,.25)),1.)
            yy=(y-centre)/scale
            xx=np.column_stack([np.ones(len(x)),x])
            epsilon=.005;alpha=.05
            def objective(beta):
                residual=yy-xx@beta
                penalty=alpha*np.dot(beta[1:],beta[1:])/2
                value=np.mean(epsilon*np.logaddexp(0,-residual/epsilon)+q*residual)+penalty
                gradient=xx.T@(expit(-residual/epsilon)-q)/len(xx)
                gradient[1:]+=alpha*beta[1:]
                return value,gradient
            initial=np.zeros(xx.shape[1]);initial[0]=float(np.quantile(yy,q))
            fitted=minimize(objective,initial,jac=True,method="L-BFGS-B",options={"maxiter":500,"ftol":1e-10,"gtol":1e-6})
            if not fitted.success and np.max(abs(fitted.jac))>.002:
                raise RuntimeError("Additive quantile solver did not converge: "+str(fitted.message))
            estimators.append({"coefficients":fitted.x,"centre":centre,"scale":scale,"epsilon":epsilon,
                               "regularisation":alpha,"converged":bool(fitted.success),"gradient_max":float(np.max(abs(fitted.jac)))})
            continue
        else:
            from lightgbm import LGBMRegressor
            model = LGBMRegressor(objective="quantile", alpha=q, n_estimators=100,
                                  learning_rate=.05, num_leaves=7, max_depth=3,
                                  min_child_samples=60, reg_lambda=10, verbosity=-1,
                                  n_jobs=2, random_state=seed)
        model.fit(x, train[target].to_numpy(float))
        estimators.append(model)
    return {"method": method, "features": features, "families": families,
            "imputer": imputer, "scaler": scaler, "estimators": estimators,
            "calibration": [0., 0., 0.], "training_rows": len(train),
            "training_end": str(train.time.max())}


def predict_quantiles(model, frame):
    x = design(frame, model["features"], model["families"])
    x = model["scaler"].transform(model["imputer"].transform(x))
    if model["method"] == "additive":
        x = np.column_stack([x, np.maximum(x-1, 0), np.maximum(-x-1, 0)])
    result = np.column_stack([(np.column_stack([np.ones(len(x)),x])@est["coefficients"])*est["scale"]+est["centre"] if isinstance(est,dict)
                              else est.booster_.predict(x, num_threads=2) if hasattr(est, "booster_") else est.predict(x) for est in model["estimators"]])
    result += np.asarray(model.get("calibration", [0.,0.,0.]))
    return np.sort(result, axis=1)


def calibrate(model, frame, target="capacity"):
    prediction = predict_quantiles(model, frame)
    residual = frame[target].to_numpy(float)[:,None] - prediction
    model["calibration"] = [float(np.quantile(residual[:,i], q)) for i,q in enumerate(QUANTILES)]
    return model
