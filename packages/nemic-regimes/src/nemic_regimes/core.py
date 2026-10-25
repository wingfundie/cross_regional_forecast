"""Portable analogue inference. The campaign and browser call this same module."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

CONNECTORS = {
    "QNI": ("NSW1-QLD1", "NSW1", "QLD1"),
    "Directlink": ("N-Q-MNSP1", "NSW1", "QLD1"),
    "VNI": ("VIC1-NSW1", "VIC1", "NSW1"),
    "Heywood": ("V-SA", "VIC1", "SA1"),
    "Murraylink": ("V-S-MNSP1", "VIC1", "SA1"),
    "Basslink": ("T-V-MNSP1", "TAS1", "VIC1"),
}
QUANTILES = np.array([.1, .5, .9])
NUMERIC_FEATURES = [
    "temperature_max", "source_temperature", "sink_temperature", "humidity_mean",
    "source_vre", "sink_vre", "source_demand", "sink_demand", "source_residual",
    "sink_residual", "vre_difference", "residual_difference", "source_vre_ramp_1h",
    "sink_vre_ramp_1h", "residual_difference_ramp_1h", "source_available_generation",
    "sink_available_generation", "electrical_positive_mw", "electrical_negative_mw",
    "corridor_wind_ms", "corridor_radiation_wm2", "corridor_cloud_pct",
]
CONTROL_KEYS = {
    "connector", "direction", "quarter", "half_hour", "era", "daytype", "target",
    "required_sets", "excluded_sets", "required_assets", "outage_state", "method",
    "allow_extrapolation", "origin", "delivery", "inputs", "scenario_name", "regime", "mode", "exact_sets",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def connector_name(value: str) -> str:
    for name, spec in CONNECTORS.items():
        if value in (name, spec[0]):
            return name
    raise ValueError(f"Unknown connector: {value}")


def structural_era(name: str, time: Any) -> str:
    t = pd.Timestamp(time)
    if t.tzinfo is not None:
        t = t.tz_convert("Australia/Brisbane").tz_localize(None)
    if name == "Basslink":
        return "regulated" if t >= pd.Timestamp("2026-07-01") else "mnsp"
    if name in {"VNI", "Heywood", "Murraylink"}:
        return "pec_market" if t >= pd.Timestamp("2026-10-01") else "pre_pec_market"
    return "qni_existing"


def weighted_quantiles(y, w, quantiles=QUANTILES):
    y, w = np.asarray(y, float), np.asarray(w, float)
    ok = np.isfinite(y) & np.isfinite(w) & (w > 0)
    if not ok.any():
        return np.full(len(quantiles), np.nan)
    order = np.argsort(y[ok], kind="stable")
    yy, ww = y[ok][order], w[ok][order]
    return np.interp(quantiles, (np.cumsum(ww) - .5 * ww) / ww.sum(), yy,
                     left=yy[0], right=yy[-1])


def _tokens(value) -> set[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return set()
    return set(str(value).split("|")) - {"", "nan", "None"}


def _clean(value):
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_clean(x) for x in value]
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    if isinstance(value, np.generic):
        return _clean(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


class RegimeBundle:
    """A frozen panel and training-fitted settings; targets never enter distances."""

    def __init__(self, panel: pd.DataFrame, metadata: dict, root: Path | None = None):
        self.panel = panel.copy()
        self.panel["time"] = pd.to_datetime(self.panel.time)
        self.metadata = metadata
        self.root = root
        self._groups = {key: g.reset_index(drop=True)
                        for key, g in self.panel.groupby(["connector", "direction", "era"], sort=False)}
        self._cache: dict = {}
        self._model_cache: dict = {}

    def _settings(self, name, direction):
        return self.metadata.get("settings", {}).get(f"{name}/{direction}", {})

    def _normalise(self, conditions):
        q = dict(conditions)
        q["connector"] = connector_name(q.get("connector", "VNI"))
        q.setdefault("direction", "forward")
        if q["direction"] not in {"forward", "reverse"}:
            raise ValueError("direction must be forward or reverse")
        for field, lo, hi in (("quarter", 1, 4), ("half_hour", 0, 47)):
            if field not in q or isinstance(q[field], bool) or int(q[field]) != q[field] or not lo <= int(q[field]) <= hi:
                raise ValueError(f"{field} must be an integer in {lo}..{hi}")
            q[field] = int(q[field])
        q.setdefault("target", "average")
        if q["target"] not in {"average", "tight"}:
            raise ValueError("target must be average or tight")
        q.setdefault("era", "current")
        if q["era"] == "current":
            q["era"] = structural_era(q["connector"], self.metadata.get("as_of", "2026-10-25"))
        q.setdefault("method", "auto")
        if q["method"] not in {"auto", "analogue", "unweighted", "baseline", "additive", "boosting"}:
            raise ValueError("Unknown estimation method")
        q.setdefault("mode", "scenario")
        if q["mode"] not in {"scenario", "asof"}:
            raise ValueError("mode must be scenario or asof")
        if q["mode"] == "asof":
            from .provenance import validate_inputs
            if not q.get("origin"):
                raise ValueError("asof selections require a timezone-aware origin")
            if not q.get("delivery"):
                raise ValueError("asof selections require an explicit delivery interval")
            delivery = pd.Timestamp(q["delivery"])
            if delivery.tzinfo is None:
                raise ValueError("Delivery must include a timezone")
            delivery = delivery.tz_convert("Australia/Brisbane")
            if delivery.quarter != q["quarter"] or delivery.hour*2+delivery.minute//30 != q["half_hour"] or delivery.minute % 30:
                raise ValueError("Quarter/half-hour must match the dated delivery interval")
        for field in ("required_sets", "excluded_sets", "required_assets"):
            if field in q and not isinstance(q[field], list):
                raise ValueError(f"{field} must be a list")
        if set(q.get("required_sets", [])) & set(q.get("excluded_sets", [])):
            raise ValueError("A constraint set cannot be both required and excluded")
        if q.get("outage_state", "any") not in {"any", "clear", "invoked", "partial"}:
            raise ValueError("Unknown outage_state")
        if q.get("outage_state") == "clear" and (q.get("required_sets") or q.get("required_assets")):
            raise ValueError("clear conflicts with a required outage")
        if q.get("daytype") not in (None, "weekday", "weekend"):
            raise ValueError("daytype must be weekday or weekend")
        settings = self._settings(q["connector"], q["direction"])
        regime = q.pop("regime", None)
        if regime and regime != "reference":
            definitions = settings.get("regimes", {}).get(str(q["quarter"]), {})
            if regime not in definitions:
                raise ValueError(f"Unknown named regime: {regime}")
            q = {**definitions[regime], **q}
        for key, value in q.items():
            if key not in CONTROL_KEYS and key not in NUMERIC_FEATURES:
                raise ValueError(f"Unknown condition {key}")
            if key in NUMERIC_FEATURES and value is not None:
                values = list(value.values()) if isinstance(value, dict) else [value]
                if isinstance(value, dict) and (not value or set(value) - {"min", "max"}):
                    raise ValueError(f"{key} accepts a number or min/max bounds")
                if any(isinstance(v, bool) or not np.isfinite(float(v)) for v in values):
                    raise ValueError(f"Non-finite {key}")
                if isinstance(value, dict) and value.get("min", -np.inf) > value.get("max", np.inf):
                    raise ValueError(f"Reversed bounds for {key}")
        if q["mode"] == "asof":
            validate_inputs(q.get("inputs", []), q["origin"], q)
        return q

    def _candidates(self, q):
        key = (q["connector"], q["direction"], q["era"])
        if key not in self._groups:
            return None
        g = self._groups[key]
        return g

    def select(self, conditions: dict | list | pd.DataFrame, *, details=True):
        if isinstance(conditions, pd.DataFrame):
            return pd.DataFrame([self.select(x, details=details) for x in conditions.to_dict("records")])
        if isinstance(conditions, list):
            return [self.select(x, details=details) for x in conditions]
        q = self._normalise(conditions)
        out = {"connector": q["connector"], "direction": q["direction"], "quarter": q["quarter"],
               "half_hour": q["half_hour"], "era": q["era"], "target": q["target"],
               "bundle_id": self.metadata.get("bundle_id", "unversioned"), "conditions": q,
               "interpretation": "Conditional AEMO reported dispatch limit; not secure physical capability",
               "information_class": "asof_inputs_conditional_research_model" if q["mode"] == "asof" else "user_scenario",
               "scenario_name": q.get("scenario_name"), "relaxed_conditions": []}
        g = self._candidates(q)
        if g is None or g.empty:
            return _clean({**out, "status": "unavailable", "reason": "No compatible topology/market-era history",
                           "p10_mw": None, "p50_mw": None, "p90_mw": None, "analogues": [], "stress_examples": []})
        if q["mode"] == "asof":
            origin = pd.Timestamp(q["origin"]).tz_convert("Australia/Brisbane").tz_localize(None)
            cutoff = self.metadata.get("training_cutoff", str(g.time.max()))
            if pd.Timestamp(cutoff) >= origin:
                raise ValueError("Bundle contains information from or after the asof origin; use a historical bundle")
        settings = self._settings(q["connector"], q["direction"])
        target = "capacity" if q["target"] == "average" else "tight_capacity"
        # Quarter-only baseline is deliberately independent of requested operating conditions.
        groupkey = (q["connector"], q["direction"], q["era"])
        datekey = (groupkey, "dates")
        if datekey not in self._cache:
            self._cache[datekey] = g.time.dt.normalize().to_numpy()
        dates = self._cache[datekey]
        hhkey = (groupkey, "hh", q["half_hour"])
        if hhkey not in self._cache:
            rawdist = abs(g.half_hour.to_numpy().astype(int) - q["half_hour"])
            self._cache[hhkey] = np.minimum(rawdist, 48-rawdist)
        hh_dist = self._cache[hhkey]
        basekey = (groupkey, "baseline", q["quarter"], q["half_hour"], target)
        if basekey not in self._cache:
            base = g[(g.quarter == q["quarter"]) & (g.half_hour == q["half_hour"])]
            self._cache[basekey] = weighted_quantiles(base[target], np.ones(len(base))) if len(base) else [np.nan] * 3
        baseline = self._cache[basekey]
        out["baseline"] = dict(zip(("p10_mw", "p50_mw", "p90_mw"), baseline))
        if q["method"] == "baseline" and not details:
            referencekey = (basekey, "reference_statistics")
            if referencekey not in self._cache:
                b = g[(g.quarter == q["quarter"]) & (g.half_hour == q["half_hour"])]
                threshold = settings.get("restriction_thresholds", {}).get(str(q["quarter"]))
                self._cache[referencekey] = {
                    "status": "reference" if len(b) else "unavailable", "method": "quarter_diurnal_baseline",
                    "p10_mw": baseline[0], "p50_mw": baseline[1], "p90_mw": baseline[2],
                    "restricted_share": float(b[target].lt(threshold).mean()) if threshold is not None and len(b) else None,
                    "forced_flow_share": float(b[target].lt(0).mean()) if len(b) else None,
                    "analogues": [], "stress_examples": [], "analogue_days": len(b)}
            return _clean({**out, **self._cache[referencekey]})
        strict = (g.quarter.to_numpy() == q["quarter"]) & (hh_dist <= settings.get("half_hour_radius", 2))
        if q.get("daytype"):
            strict &= g.daytype.to_numpy() == q["daytype"]
        topology = np.ones(len(g), bool)
        if q.get("exact_sets") and q["method"] != "baseline":
            signature = "|".join(sorted(q.get("required_sets", [])))
            exactkey = (groupkey, "exact_sets", signature)
            if exactkey not in self._cache:
                self._cache[exactkey] = g.active_sets.to_numpy() == signature
            topology &= self._cache[exactkey]
        if q.get("outage_state", "any") != "any" and q["method"] != "baseline":
            topology &= g.outage_state.to_numpy() == q["outage_state"]
        for col, field, excluded in (("active_sets", "required_sets", False),
                                    ("active_sets", "excluded_sets", True),
                                    ("active_assets", "required_assets", False)):
            for token in q.get(field, []):
                if q["method"] == "baseline" or (field == "required_sets" and q.get("exact_sets")):
                    continue
                cachekey = (q["connector"], q["direction"], q["era"], col, token)
                if cachekey not in self._cache:
                    self._cache[cachekey] = g[col].map(lambda s: token in _tokens(s)).to_numpy()
                hit = self._cache[cachekey]
                topology &= ~hit if excluded else hit
        requested = {k: v for k, v in q.items() if k in NUMERIC_FEATURES and v is not None} if q["method"] != "baseline" else {}
        working = np.flatnonzero(topology & (hh_dist <= settings.get("half_hour_radius", 2)))
        if not len(working) and not q.get("allow_extrapolation", False):
            return _clean({**out, "status": "unavailable", "reason": "No compatible outage/configuration analogues",
                           "p10_mw": None, "p50_mw": None, "p90_mw": None, "analogues": [], "stress_examples": []})
        condition_mask = np.zeros(len(g), bool)
        condition_mask[working] = True
        distance = np.full(len(g), np.inf)
        distance[working] = (hh_dist[working] / 2.) ** 2
        outside = []
        for field, value in requested.items():
            valuekey = (groupkey, "values", field)
            if valuekey not in self._cache:
                self._cache[valuekey] = g[field].to_numpy(float) if field in g else np.full(len(g), np.nan)
            values = self._cache[valuekey][working]
            spec = settings.get("scales", {}).get(field)
            if not spec:
                condition_mask[:] = False
                outside.append(field)
                continue
            scale = max(float(spec["scale"]), 1e-6)
            if isinstance(value, dict):
                lo, hi = float(value.get("min", -np.inf)), float(value.get("max", np.inf))
                condition_mask[working] &= np.isfinite(values) & (values >= lo) & (values <= hi)
                delta = np.maximum(lo - values, 0) + np.maximum(values - hi, 0)
                centre = (lo + hi) / 2 if np.isfinite(lo + hi) else lo if np.isfinite(lo) else hi
            else:
                centre = float(value)
                delta = values - centre
                # A numerical value is a similarity request, not an exact floating-point match.
                condition_mask[working] &= np.isfinite(values) & (abs(delta) <= scale)
            if centre < spec["min"] or centre > spec["max"]:
                outside.append(field)
            distance[working] += np.where(np.isfinite(values), (delta / scale) ** 2, 16.)
        if requested:
            distance /= 1 + len(requested)
        exact_mask = strict & topology & condition_mask
        candidate = np.flatnonzero(exact_mask)
        exact_days = len(np.unique(dates[candidate]))
        relaxed = []
        if exact_days < settings.get("min_days", 20):
            # Operational conditions can be relaxed for a labelled broader reference.
            candidate = np.flatnonzero(strict & topology)
            if requested:
                relaxed.extend(requested)
        if not len(candidate):
            candidate = np.flatnonzero(topology & (hh_dist <= settings.get("half_hour_radius", 2)))
            relaxed.extend(["quarter"] + (["daytype"] if q.get("daytype") else []))
        if not len(candidate):
            # Never remove a known outage/topology requirement to manufacture a result.
            model_name = q["method"] if q["method"] in {"additive", "boosting"} else settings.get("extrapolation_method", "boosting")
            known_components = False
            if q.get("allow_extrapolation", False):
                knownkey = (groupkey, "known_components")
                if knownkey not in self._cache:
                    self._cache[knownkey] = (set().union(*g.active_sets.map(_tokens)), set().union(*g.active_assets.map(_tokens)))
                known_sets, known_assets = self._cache[knownkey]
                known_components = set(q.get("required_sets", [])) <= known_sets and set(q.get("required_assets", [])) <= known_assets
            if known_components:
                predicted = self._predict_model(q, model_name)
                if predicted is not None:
                    out.update(status="modelled_extrapolation", method=model_name, reason="Known components in an unobserved combination; no matching historical range",
                               p10_mw=predicted[0], p50_mw=predicted[1], p90_mw=predicted[2],
                               analogue_days=0, exact_days=0, outage_episodes=0, analogues=[], stress_examples=[],
                               outside_support=["outage_combination"], model_probability_calibrated=False)
                    return _clean(out)
            out.update(status="unavailable", reason="No compatible outage/configuration analogues",
                       p10_mw=None, p50_mw=None, p90_mw=None, analogues=[], stress_examples=[])
            return _clean(out)
        if q["method"] == "baseline":
            candidate = np.flatnonzero((g.quarter.to_numpy() == q["quarter"]) & (hh_dist == 0))
            if not len(candidate):
                out.update(status="unavailable", reason="No quarter/half-hour baseline in this era",
                           p10_mw=None, p50_mw=None, p90_mw=None, analogues=[], stress_examples=[])
                return _clean(out)
        # Keep up to k independent days, and normalise each day's contribution.
        order = candidate[np.argsort(distance[candidate], kind="stable")]
        if q["method"] == "baseline":
            candidate = order
        else:
            chosen_days = pd.unique(dates[order])[:settings.get("neighbour_days", 60)]
            candidate = order[np.isin(dates[order], chosen_days)]
        selected = g.iloc[candidate]
        d = np.sqrt(distance[candidate])
        weight = np.exp(-.5 * np.minimum(d, 20) ** 2)
        if q["method"] in {"unweighted", "baseline"}:
            weight = np.ones(len(candidate))
        daycodes, daylabels = pd.factorize(dates[candidate])
        daysums = np.bincount(daycodes, weights=weight)
        # Equal episode-day exposure prevents a long, densely sampled incident dominating.
        weight = weight / np.maximum(daysums[daycodes], 1e-300)
        qs = weighted_quantiles(selected[target], weight)
        dayw = np.bincount(daycodes, weights=weight)
        effective_days = float(dayw.sum() ** 2 / np.square(dayw).sum())
        epkey = (groupkey, "episode_tokens")
        if epkey not in self._cache:
            self._cache[epkey] = g.episode_ids.map(_tokens).to_numpy()
        episode_ids = set().union(*self._cache[epkey][candidate])
        has_outage = bool(q.get("required_sets") or q.get("required_assets") or q.get("outage_state") == "invoked")
        supported = exact_days >= settings.get("min_days", 20)
        if has_outage:
            supported &= len(episode_ids) >= settings.get("min_episodes", 5)
        status = "supported_analogue" if supported and not relaxed and not outside else "broader_analogue"
        method = "weighted_analogue" if q["method"] != "unweighted" else "unweighted_analogue"
        if q["method"] == "baseline":
            method, status = "quarter_diurnal_baseline", "reference"
        # Models are optional, hash-verified and only loaded when explicitly requested or selected.
        policy = settings.get("policy", "analogue")
        requested_model = q["method"] if q["method"] in {"additive", "boosting"} else policy
        use_model = requested_model in {"additive", "boosting"} and (
            q["method"] != "auto" or not supported or outside)
        if use_model and q.get("allow_extrapolation", False):
            predicted = self._predict_model(q, requested_model)
            if predicted is not None:
                qs, method, status = predicted, requested_model, "modelled_extrapolation"
            else:
                out["model_request_status"] = "Model cannot represent all requested conditions; returned the labelled analogue reference"
        threshold = settings.get("restriction_thresholds", {}).get(str(q["quarter"]))
        total = weight.sum()
        restricted = float(np.sum(weight * (selected[target].to_numpy() < threshold)) / total) if threshold is not None and total else None
        forced = float(np.sum(weight * (selected[target].to_numpy() < 0)) / total) if total else None
        examples = selected.assign(_distance=d, _date=dates[candidate]).sort_values("_distance").drop_duplicates("_date").head(8) if details else None
        stress = selected.sort_values(target).assign(_date=selected.time.dt.normalize()).drop_duplicates("_date").head(5) if details else None
        def records(frame, stress_mode=False):
            fields = ["time", "capacity", "tight_capacity", "active_sets", "active_assets", "episode_ids"]
            result = frame[[x for x in fields if x in frame]].to_dict("records")
            for r in result:
                r["evidence"] = "Observed conditional episode; occurrence probability not estimated" if stress_mode else "Historical analogue"
            return result
        out.update(status=status, method=method, p10_mw=qs[0], p50_mw=qs[1], p90_mw=qs[2],
                   tight_p10_mw=weighted_quantiles(selected.tight_capacity, weight)[0],
                   restricted_share=restricted, forced_flow_share=forced,
                   frequency_interpretation="Weighted historical frequency; not an unconditional forecast probability",
                   restriction_threshold_mw=threshold, exact_days=int(exact_days), analogue_days=len(daylabels),
                   effective_days=effective_days, outage_episodes=len(episode_ids),
                   known_outage_state_share=float(selected.outage_state.ne("unknown").mean()),
                   observation_hours=len(candidate) / 2, mean_distance=float(np.average(d, weights=weight)),
                   outside_support=outside, relaxed_conditions=sorted(set(relaxed)),
                   analogues=records(examples) if details else [], stress_examples=records(stress, True) if details else [],
                   low_support_reason=None if supported else "Fewer than required independent days or outage episodes",
                   model_probability_calibrated=False if status == "modelled_extrapolation" else None)
        return _clean(out)

    def _predict_model(self, q, method):
        key = f"{q['connector']}/{q['direction']}/{q['era']}/{q['target']}/{method}"
        spec = self.metadata.get("models", {}).get(key)
        if not spec or self.root is None:
            return None
        if key not in self._model_cache:
            import joblib
            p = (self.root / spec["file"]).resolve()
            if not p.is_relative_to(self.root.resolve()) or sha256(p) != spec["sha256"]:
                raise ValueError("Model hash/path validation failed")
            self._model_cache[key] = joblib.load(p)
        from .models import predict_quantiles
        model = self._model_cache[key]
        if set(q.get("required_sets", [])) - set(model["families"]) or q.get("required_assets"):
            return None
        if any(field in NUMERIC_FEATURES and value is not None and field not in model["features"] for field,value in q.items()):
            return None
        return predict_quantiles(model, pd.DataFrame([q]))[0]

    def profile(self, quarter, conditions=None, **kwargs):
        q = {**(conditions or {}), **kwargs, "quarter": quarter}
        return pd.DataFrame([self.select({**q, "half_hour": h}) for h in range(48)])

    def explain(self, conditions):
        return self.select(conditions)

    def export(self, result, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".json":
            records = result.to_dict("records") if isinstance(result, pd.DataFrame) else result
            path.write_text(json.dumps(_clean(records), indent=2, allow_nan=False), encoding="utf-8")
        elif path.suffix.lower() == ".csv":
            (result if isinstance(result, pd.DataFrame) else pd.DataFrame(result if isinstance(result, list) else [result])).to_csv(path, index=False)
        else:
            raise ValueError("Export format must be CSV or JSON")
        return path


def load_bundle(path, verify=True) -> RegimeBundle:
    root = Path(path).resolve()
    metadata = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1:
        raise ValueError("Unsupported bundle schema")
    for relative, expected in metadata.get("files", {}).items():
        p = (root / relative).resolve()
        if not p.is_relative_to(root):
            raise ValueError("Bundle path escapes root")
        if verify and sha256(p) != expected:
            raise ValueError(f"Bundle hash mismatch: {relative}")
    return RegimeBundle(pd.read_parquet(root / "panel.parquet"), metadata, root)


def select(bundle, conditions):
    return bundle.select(conditions)


def profile(bundle, quarter, conditions=None, **kwargs):
    return bundle.profile(quarter, conditions, **kwargs)


def explain(bundle, conditions):
    return bundle.explain(conditions)
