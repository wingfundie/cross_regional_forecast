"""Specific-outage lookup: publish each outage asset at the most specific supported key level (METHODOLOGY §4.3)."""
from __future__ import annotations

import pandas as pd

ORDER = ["K1xK2", "K1", "K2", "K3", "K4"]
TIER_RANK = {"supported": 0, "indicative": 1, "unsupported": 2}


def backoff(asset_row: dict, effects: pd.DataFrame) -> dict | None:
    """Choose the first level in ORDER with a supported row for this asset (falls back to indicative).

    asset_row: {"ic", "direction", "asset", "substation", "area_key", "families": set}
    effects: rows with columns level, key, ic, direction, tier (+ asset/GENCONSETID for K1xK2).
    """
    e = effects[(effects.ic == asset_row["ic"]) & (effects.direction == asset_row["direction"])]
    candidates = {
        "K1xK2": e[(e.level == "K1xK2") & (e.get("asset", pd.Series(index=e.index, dtype=object)) == asset_row["asset"])],
        "K1": e[(e.level == "K1") & (e.key == asset_row["asset"])],
        "K2": e[(e.level == "K2") & e.key.isin(asset_row["families"])],
        "K3": e[(e.level == "K3") & (e.key == asset_row["substation"])],
        "K4": e[(e.level == "K4") & (e.key == asset_row["area_key"])],
    }
    for wanted in ("supported", "indicative"):
        for level in ORDER:
            c = candidates[level]
            c = c[c.tier == wanted]
            if len(c):
                best = c.assign(_abs=c.effect_capacity.abs()).sort_values(["_abs"], ascending=False).iloc[0].to_dict()
                best["published_level"] = level
                return best
    return None


def build_lookup(key_effects: pd.DataFrame, family_effects: pd.DataFrame, keys: pd.DataFrame,
                 episode_sets: pd.DataFrame, relevance: pd.DataFrame, k5: pd.DataFrame) -> pd.DataFrame:
    effects = pd.concat([key_effects, family_effects.assign(level="K2")], ignore_index=True)
    effects = effects[effects.get("n_treated").notna()] if "n_treated" in effects else effects
    rows = []
    rel = relevance[relevance.relevant]
    eps = keys[~keys.primary_asset_is_na].merge(episode_sets[["OUTAGEID", "GENCONSETID"]], on="OUTAGEID")
    for ic, rfam in rel.groupby("ic"):
        fams = set(rfam.GENCONSETID)
        e = eps[eps.GENCONSETID.isin(fams)]
        for asset, g in e.groupby("primary_asset"):
            first = g.iloc[0]
            for direction in ("forward", "reverse"):
                row = {"ic": ic, "direction": direction, "asset": asset, "substation": first.primary_substationid,
                       "area_key": first.area_key, "families": set(g.GENCONSETID)}
                best = backoff(row, effects)
                near = k5[(k5.ic == ic) & k5.GENCONSETID.isin(row["families"])].sort_values("sensitivity", key=abs, ascending=False)
                rows.append({"ic": ic, "direction": direction, "asset": asset, "asset_description": first.primary_description,
                             "voltage_kv": first.primary_voltage, "substation": first.substation_name, "region": first.region,
                             "area_label": first.area_label, "families": "|".join(sorted(row["families"])),
                             "episodes_listed": g.OUTAGEID.nunique(),
                             "electrically_near": "; ".join(f"{d} ({s:+.2f})" for d, s in near.drop_duplicates("DUID")[["DUID", "sensitivity"]].head(6).itertuples(index=False)),
                             "plants_within_50km": first.plants_within_50km,
                             "published_level": best["published_level"] if best else "none",
                             "published_key": best["key"] if best else None,
                             "tier": best["tier"] if best else "unsupported",
                             **{k: (best or {}).get(k) for k in ["effect_capacity", "effect_capacity_pct", "ci_lo_capacity", "ci_hi_capacity",
                                                                "effect_at_limit", "effect_directional_flow", "effect_headroom",
                                                                "treated_capacity", "control_capacity", "treated_hours", "episodes", "match_rate"]}})
    return pd.DataFrame(rows)
