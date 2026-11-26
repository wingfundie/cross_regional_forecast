"""Wave 3 analytical engine (C10 + Forecasting/Clustering Synthesis) for Flagship C:
Interconnector Forecasting Verdict, Clustering & Project EnergyConnect (v2).

Computes strictly from verified local archives (zero new NEMWEB downloads):
- C10a: Observed Project EnergyConnect (NSW1-SA1) commissioning configurations, directional
        envelopes, and southern-ring shared constraint-setter taxonomy (15,264 five-minute
        intervals, 1 October to 23 November 2026).
- C10b: Observed EnergyConnect commissioning limits & utilisation profiles bridged directly
        into the AEMC ERC0386 loop settlement engine (nemic.valuation.loop.net_trade) over
        the 24-month 2024-2026 southern-ring panel across 4 capacity regimes (0 MW pre-PEC,
        observed 150 MW commissioning, observed 350 MW testing, and 800 MW Stage 2 full).
- C10c: Issue-time Predispatch & ST PASA forecast audit across all 5 PEC models and 4 lead bands.
- Synthesis: Audited scorecards for the 50 long-range MT PASA bands (10/10 retain baseline),
        362 leakage-controlled clustering comparisons + 227 state-stability runs, and the
        repository's 3-stack governance register (original vs experiments vs production).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from nemic.valuation.loop import net_trade

ROOT = Path(__file__).resolve().parents[2]


def _classify_pec_regime(cfg_str: str) -> str:
    s = str(cfg_str)
    if "Zero-transfer" in s and ("150 MW" in s or "350 MW" in s):
        return "Transition / Mixed"
    if "Zero-transfer" in s:
        return "Zero-transfer (0 MW)"
    if "350 MW" in s:
        return "350 MW testing"
    if "150 MW" in s:
        return "150 MW commissioning"
    return "Other commissioning"


def _classify_setter_ring(eq: str) -> str:
    s = str(eq).upper()
    if s in ("", "NAN", "NONE"):
        return "Unreported / None"
    if "DYN_TEST" in s or "NS_150" in s or "SN_150" in s or "NS_350" in s or "SN_350" in s or "I_6F" in s:
        return "PEC Commissioning / Test Cap"
    if "ZERO" in s:
        return "PEC Zero-Transfer Lock"
    if "NRM" in s:
        return "Negative Residue Management (NRM)"
    if "060_051" in s or "WGLT" in s or "LTWG" in s or "CNCW" in s or s.startswith("N>>") or s.startswith("N^^") or s.startswith("N::"):
        return "VNI / Southern NSW Ring"
    if "UFLS" in s or "KGTS" in s or "V_S_" in s or "V^^V" in s or s.startswith("V::"):
        return "Heywood / VIC-SA Ring"
    if s.startswith("S>>") or s.startswith("S>"):
        return "SA Internal Thermal"
    return "Other Generic Constraint"


def compute_c10_pec_observed_and_coupling(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """C10a: Characterise observed NSW1-SA1 commissioning regimes and southern-ring equation coupling."""
    hh = pd.read_parquet(ROOT / cfg["inputs"]["pec_half_hour"])
    di = pd.read_parquet(ROOT / cfg["inputs"]["pec_dispatch_ic"])
    for c in ("EXPORTLIMIT", "IMPORTLIMIT", "MWFLOW", "METEREDMWFLOW"):
        di[c] = pd.to_numeric(di[c], errors="coerce")
    di["rev_cap"] = -di["IMPORTLIMIT"]
    di["fwd_headroom"] = di["EXPORTLIMIT"] - di["MWFLOW"]
    di["rev_headroom"] = di["rev_cap"] + di["MWFLOW"]

    hh["regime"] = hh["configuration"].map(_classify_pec_regime)
    reg_order = ["150 MW commissioning", "350 MW testing", "Zero-transfer (0 MW)", "Transition / Mixed", "Other commissioning"]
    rows = []
    for reg in reg_order:
        g = hh[hh["regime"] == reg]
        if g.empty:
            continue
        fwd_tight = g["nsw_sa_tight"].to_numpy(float)
        rev_tight = g["sa_nsw_tight"].to_numpy(float)
        fl = g["dispatch_flow_mean"].to_numpy(float)
        # Empirical utilisation ratio |flow| / max(active ceiling, 1) during positive-cap intervals
        pos_cap = np.where(fl >= 0, np.maximum(fwd_tight, 0.0), np.maximum(rev_tight, 0.0))
        valid_u = pos_cap >= 25.0
        util = float(np.median(np.abs(fl[valid_u]) / pos_cap[valid_u])) if valid_u.any() else 0.0
        rows.append({
            "regime": reg,
            "half_hours": int(len(g)),
            "hours": float(len(g) / 2.0),
            "share_pct": float(100.0 * len(g) / len(hh)),
            "fwd_tight_med_mw": float(np.nanmedian(fwd_tight)),
            "fwd_tight_p05_mw": float(np.nanpercentile(fwd_tight, 5)),
            "fwd_tight_p95_mw": float(np.nanpercentile(fwd_tight, 95)),
            "rev_tight_med_mw": float(np.nanmedian(rev_tight)),
            "rev_tight_p05_mw": float(np.nanpercentile(rev_tight, 5)),
            "rev_tight_p95_mw": float(np.nanpercentile(rev_tight, 95)),
            "flow_mean_mw": float(np.nanmean(fl)),
            "flow_abs_mean_mw": float(np.nanmean(np.abs(fl))),
            "flow_p95_abs_mw": float(np.nanpercentile(np.abs(fl), 95)),
            "median_utilisation_ratio": util,
            "forced_fwd_neg_pct": float(100.0 * np.mean(fwd_tight < 0.0)),
            "forced_rev_neg_pct": float(100.0 * np.mean(rev_tight < 0.0)),
            "top_fwd_setter": str(g["nsw_sa_setter"].value_counts().index[0]) if g["nsw_sa_setter"].notna().any() else "n/a",
            "top_rev_setter": str(g["sa_nsw_setter"].value_counts().index[0]) if g["sa_nsw_setter"].notna().any() else "n/a",
        })
    cfg_df = pd.DataFrame(rows)

    # Empirical utilisation & cap parameters to feed C10b loop bridge
    util_map = {
        "u150": float(cfg_df.loc[cfg_df["regime"] == "150 MW commissioning", "median_utilisation_ratio"].iloc[0]) if (cfg_df["regime"] == "150 MW commissioning").any() else 0.65,
        "u350": float(cfg_df.loc[cfg_df["regime"] == "350 MW testing", "median_utilisation_ratio"].iloc[0]) if (cfg_df["regime"] == "350 MW testing").any() else 0.65,
        "fwd_cap_150": float(cfg_df.loc[cfg_df["regime"] == "150 MW commissioning", "fwd_tight_p95_mw"].iloc[0]),
        "rev_cap_150": float(cfg_df.loc[cfg_df["regime"] == "150 MW commissioning", "rev_tight_p95_mw"].iloc[0]),
        "fwd_cap_350": float(cfg_df.loc[cfg_df["regime"] == "350 MW testing", "fwd_tight_p95_mw"].iloc[0]),
        "rev_cap_350": float(cfg_df.loc[cfg_df["regime"] == "350 MW testing", "rev_tight_p95_mw"].iloc[0]),
        "n_5m_intervals": int(len(di)),
        "n_hh_intervals": int(len(hh)),
        "tight_fwd_pct": float(100.0 * np.mean(di["fwd_headroom"] <= 50.0)),
        "tight_rev_pct": float(100.0 * np.mean(di["rev_headroom"] <= 50.0)),
        "forced_fwd_pct": float(100.0 * np.mean(di["EXPORTLIMIT"] < 0.0)),
        "forced_rev_pct": float(100.0 * np.mean(di["rev_cap"] < 0.0)),
        "max_flow_mw": float(di["MWFLOW"].abs().max()),
    }

    # Southern-ring constraint coupling taxonomy across 15,264 5-min intervals
    coup_rows = []
    for d_lbl, col in [("NSW -> SA (forward)", "EXPORTGENCONID"), ("SA -> NSW (reverse)", "IMPORTGENCONID")]:
        vc = di[col].fillna("").astype(str).value_counts()
        ring_ser = di[col].fillna("").astype(str).map(_classify_setter_ring)
        r_vc = ring_ser.value_counts()
        for ring_name, cnt in r_vc.items():
            # Top 2 equations inside this ring category
            sub_eqs = di.loc[ring_ser == ring_name, col].fillna("").astype(str).value_counts().head(2)
            examples = ", ".join(f"{k} ({v:,})" for k, v in sub_eqs.items() if k)
            coup_rows.append({
                "direction": d_lbl,
                "ring_category": ring_name,
                "intervals_5m": int(cnt),
                "share_pct": float(100.0 * cnt / len(di)),
                "top_equations": examples or "None",
            })
    coup_df = pd.DataFrame(coup_rows).sort_values(["direction", "intervals_5m"], ascending=[True, False]).reset_index(drop=True)
    return cfg_df, coup_df, util_map


def compute_c10_loop_settlement_bridge(cfg: dict[str, Any], util_map: dict[str, float]) -> pd.DataFrame:
    """C10b: Feed observed EnergyConnect commissioning profiles directly into nemic.valuation.loop.net_trade.

    Historical-price counterfactual holding regional prices and existing VN/VS flows fixed over
    the 24-month southern-ring window (2024-09-01 to 2026-08-31), comparing 4 PEC capacity regimes:
      0. Pre-PEC baseline (0 MW)
      1. Observed 150 MW commissioning envelope (scaled by observed empirical utilisation)
      2. Observed 350 MW testing envelope (scaled by observed empirical utilisation)
      3. Stage 2 Full-Rated (800 MW) parametric upper bound
    """
    t0 = pd.Timestamp(cfg["study_window"]["loop_panel_start"])
    t1 = pd.Timestamp(cfg["study_window"]["loop_panel_end"])

    pr = pd.read_parquet(ROOT / cfg["inputs"]["prices_parquet"], columns=["time", "REGIONID", "RRP"])
    pr["time"] = pd.to_datetime(pr["time"])
    pr = pr[(pr["time"] >= t0) & (pr["time"] <= t1) & (pr["REGIONID"].isin(["NSW1", "VIC1", "SA1"]))]
    piv_p = pr.pivot(index="time", columns="REGIONID", values="RRP").sort_index().ffill()

    ics = pd.read_parquet(
        ROOT / cfg["inputs"]["interconnectors_parquet"],
        columns=["time", "INTERCONNECTORID", "MWFLOW"],
    )
    ics["time"] = pd.to_datetime(ics["time"])
    ics = ics[(ics["time"] >= t0) & (ics["time"] <= t1) & (ics["INTERCONNECTORID"].isin(["VIC1-NSW1", "V-SA", "V-S-MNSP1"]))]
    piv_f = ics.pivot(index="time", columns="INTERCONNECTORID", values="MWFLOW").reindex(piv_p.index).fillna(0.0)

    # Pooled border flows: VN = VIC1-NSW1; VS = Heywood (V-SA) + Murraylink (V-S-MNSP1)
    f_vn = piv_f["VIC1-NSW1"]
    f_vs = piv_f["V-SA"] + piv_f["V-S-MNSP1"]
    sp_vn = piv_p["NSW1"] - piv_p["VIC1"]
    sp_vs = piv_p["SA1"] - piv_p["VIC1"]
    sp_ns = piv_p["SA1"] - piv_p["NSW1"]  # positive => SA priced higher than NSW => NSW -> SA flow earns +IRSR

    # Signed IRSR allocations per 5-min interval ($ = MW * $/MWh / 12)
    alloc_vn = f_vn * sp_vn / 12.0
    alloc_vs = f_vs * sp_vs / 12.0

    # Observed commissioning flow responsiveness calibrated to observed utilisation ratio
    # Smooth hyperbolic-tangent price response bounded strictly by the observed regime ceiling
    u_150 = np.clip(util_map.get("u150", 0.65), 0.35, 0.90)
    u_350 = np.clip(util_map.get("u350", 0.65), 0.35, 0.90)
    regimes = [
        ("Pre-PEC (0 MW baseline)", 0.0, 0.0, 0.0),
        ("Observed 150 MW commissioning", util_map["fwd_cap_150"], util_map["rev_cap_150"], u_150),
        ("Observed 350 MW testing", util_map["fwd_cap_350"], util_map["rev_cap_350"], u_350),
        ("Stage 2 full-rated (800 MW)", 800.0, 800.0, u_350),
    ]

    bridge_rows = []
    years = (piv_p.index.max() - piv_p.index.min()).total_seconds() / (365.25 * 86400.0)
    for label, cap_fwd, cap_rev, u_scale in regimes:
        if cap_fwd <= 0.0:
            f_ns = pd.Series(0.0, index=piv_p.index)
        else:
            # Price-responsive economic transfer capped strictly at observed commissioning limit * utilisation scale
            raw_sig = np.tanh(sp_ns.to_numpy(float) / 35.0)
            f_ns_arr = np.where(raw_sig >= 0.0, raw_sig * cap_fwd * u_scale, raw_sig * cap_rev * u_scale)
            f_ns = pd.Series(f_ns_arr, index=piv_p.index)
        alloc_ns = f_ns * sp_ns / 12.0
        flows = pd.DataFrame({"VN": f_vn, "VS": f_vs, "NS": f_ns}, index=piv_p.index)
        allocs = pd.DataFrame({"VN": alloc_vn, "VS": alloc_vs, "NS": alloc_ns}, index=piv_p.index)
        res = net_trade(piv_p, flows, allocs)

        sq_tot = float((res["sq_VICNSW"] + res["sq_NSWVIC"] + res["sq_VICSA"] + res["sq_SAVIC"] + res["sq_NSWSA"] + res["sq_SANSW"]).sum() / 1e6)
        lp_tot = float((res["loop_VICNSW"] + res["loop_NSWVIC"] + res["loop_VICSA"] + res["loop_SAVIC"] + res["loop_NSWSA"] + res["loop_SANSW"]).sum() / 1e6)
        net_pos = float(res["net_loop"].clip(lower=0.0).sum() / 1e6)
        net_neg = float(res["net_loop"].clip(upper=0.0).sum() / 1e6)
        bridge_rows.append({
            "regime": label,
            "cap_fwd_mw": float(cap_fwd),
            "cap_rev_mw": float(cap_rev),
            "utilisation_scale": float(u_scale),
            "mean_abs_ns_flow_mw": float(f_ns.abs().mean()),
            "sq_total_pos_m": sq_tot,
            "loop_total_payout_m": lp_tot,
            "net_loop_pos_m": net_pos,
            "net_loop_neg_m": net_neg,
            "loop_VICNSW_m": float(res["loop_VICNSW"].sum() / 1e6),
            "loop_NSWVIC_m": float(res["loop_NSWVIC"].sum() / 1e6),
            "loop_VICSA_m": float(res["loop_VICSA"].sum() / 1e6),
            "loop_SAVIC_m": float(res["loop_SAVIC"].sum() / 1e6),
            "loop_NSWSA_m": float(res["loop_NSWSA"].sum() / 1e6),
            "loop_SANSW_m": float(res["loop_SANSW"].sum() / 1e6),
            "sq_VICNSW_m": float(res["sq_VICNSW"].sum() / 1e6),
            "sq_NSWVIC_m": float(res["sq_NSWVIC"].sum() / 1e6),
            "sq_VICSA_m": float(res["sq_VICSA"].sum() / 1e6),
            "sq_SAVIC_m": float(res["sq_SAVIC"].sum() / 1e6),
            "sq_NSWSA_m": float(res["sq_NSWSA"].sum() / 1e6),
            "sq_SANSW_m": float(res["sq_SANSW"].sum() / 1e6),
            "pec_arm_share_of_loop_pct": float(100.0 * (res["loop_NSWSA"].sum() + res["loop_SANSW"].sum()) / max(res[["loop_VICNSW", "loop_NSWVIC", "loop_VICSA", "loop_SAVIC", "loop_NSWSA", "loop_SANSW"]].sum().sum(), 1.0)),
            "annualised_loop_m_yr": float(lp_tot / max(years, 1e-6)),
        })
    return pd.DataFrame(bridge_rows)


def compute_c10_pec_forecast_scores(cfg: dict[str, Any]) -> pd.DataFrame:
    """C10c: Issue-time Predispatch & ST PASA MAE, skill, and coverage across 5 PEC models."""
    models = [
        ("persistence", "Persistence"),
        ("delivery_period", "Delivery-Period Baseline"),
        ("aemo", "AEMO Issued Forecast"),
        ("regional_forecast", "Regional Forecast"),
        ("regional_plus_constraints", "Regional + Constraints"),
    ]
    rows = []
    for prod_lbl, key in [("Predispatch", "pec_predispatch"), ("ST PASA", "pec_stpasa")]:
        df = pd.read_parquet(ROOT / cfg["inputs"][key])
        for d_col, d_lbl in [("nsw_sa_tight", "NSW -> SA (tight)"), ("sa_nsw_tight", "SA -> NSW (tight)")]:
            for lb, g in df.groupby("lead_band"):
                y = pd.to_numeric(g[d_col], errors="coerce").to_numpy(float)
                p_pers = pd.to_numeric(g[f"persistence_{d_col}"], errors="coerce").to_numpy(float)
                p_aemo = pd.to_numeric(g[f"aemo_{d_col}"], errors="coerce").to_numpy(float)
                valid_base = np.isfinite(y) & np.isfinite(p_pers)
                mae_pers = float(np.mean(np.abs(y[valid_base] - p_pers[valid_base]))) if valid_base.any() else np.nan
                valid_aemo = np.isfinite(y) & np.isfinite(p_aemo)
                mae_aemo = float(np.mean(np.abs(y[valid_aemo] - p_aemo[valid_aemo]))) if valid_aemo.any() else np.nan
                for m_key, m_lbl in models:
                    col = f"{m_key}_{d_col}"
                    rcol = f"{col}_radius"
                    pred = pd.to_numeric(g[col], errors="coerce").to_numpy(float)
                    rad = pd.to_numeric(g[rcol], errors="coerce").to_numpy(float) if rcol in g.columns else np.full(len(g), np.nan)
                    ok = np.isfinite(y) & np.isfinite(pred)
                    if not ok.any():
                        continue
                    err = np.abs(y[ok] - pred[ok])
                    mae = float(np.mean(err))
                    cov = float(100.0 * np.mean(err <= rad[ok])) if np.isfinite(rad[ok]).any() else np.nan
                    rows.append({
                        "product": prod_lbl,
                        "direction": d_lbl,
                        "lead_band": str(lb),
                        "model": m_lbl,
                        "rows": int(ok.sum()),
                        "mae_mw": mae,
                        "skill_vs_persistence_pct": float(100.0 * (1.0 - mae / mae_pers)) if mae_pers > 0 else np.nan,
                        "skill_vs_aemo_pct": float(100.0 * (1.0 - mae / mae_aemo)) if mae_aemo > 0 else np.nan,
                        "interval_coverage_pct": cov,
                    })
    return pd.DataFrame(rows).sort_values(["product", "direction", "lead_band", "mae_mw"]).reset_index(drop=True)


def compute_forecast_clustering_synthesis(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Extract clean scorecards for Long-Range 50-band verdict, Clustering vs Controls, and 3-Stack Register."""
    bm = pd.read_csv(ROOT / cfg["inputs"]["verdict_band_metrics"])
    cr = pd.read_csv(ROOT / cfg["inputs"]["verdict_cell_results"])
    fe = pd.read_csv(ROOT / cfg["inputs"]["cluster_effects"])
    ss = pd.read_csv(ROOT / cfg["inputs"]["cluster_stability"])
    rr = json.loads((ROOT / cfg["inputs"]["research_register"]).read_text(encoding="utf-8"))

    # Clustering summary (7-day block bootstrap rows only to avoid 7d/14d duplicate counting)
    fe7 = fe[fe["block_days"] == 7].copy()
    fe7["sig_holm"] = fe7["holm_p_value"].fillna(1.0) < 0.05
    fe7["sig_unadj"] = fe7["p_value"].fillna(1.0) < 0.05
    fe7["improves_mae"] = fe7["effect_mae"] < 0.0
    fe_sum = fe7.groupby(["connector", "control_model", "target"], as_index=False).agg(
        comparisons=("effect_mae", "count"),
        mean_effect_mae=("effect_mae", "mean"),
        mean_effect_pct=("effect_percent", "mean"),
        wins_raw=("improves_mae", "sum"),
        sig_unadj_wins=("sig_unadj", lambda s: int((s & fe7.loc[s.index, "improves_mae"]).sum())),
        sig_holm_wins=("sig_holm", lambda s: int((s & fe7.loc[s.index, "improves_mae"]).sum())),
    ).sort_values(["connector", "control_model", "mean_effect_pct"]).reset_index(drop=True)

    # State stability summary by connector x method x k
    ss_sum = ss.groupby(["connector", "method", "k"], as_index=False).agg(
        folds=("fold", "nunique"),
        mean_seed_ari=("seed_ari", "mean"),
        mean_block_ari=("block_ari", "mean"),
        recurring_rate=("recurring", "mean"),
    ).sort_values(["connector", "method", "k"]).reset_index(drop=True)

    # 3-stack governance register
    reg_rows = []
    for e in rr["entries"]:
        reg_rows.append({
            "workstream": str(e.get("name", "")),
            "stack": str(e.get("stack", "")),
            "status": str(e.get("status", "")),
            "evidence_exists": bool(e.get("evidence_exists", False)),
            "permitted_claim": str(e.get("claim", "")),
            "unresolved_gate": str(e.get("unresolved", "")),
        })
    reg_df = pd.DataFrame(reg_rows)
    return bm, cr, fe_sum, ss_sum, reg_df


def run_all(config_path: Path | None = None) -> dict[str, Any]:
    cfg_path = config_path or (ROOT / "configs/ic_forecasting_pec_v2.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    ev_dir = ROOT / cfg["outputs"]["evidence_dir"]
    ev_dir.mkdir(parents=True, exist_ok=True)

    print("[C10a] Computing observed EnergyConnect commissioning configs & southern-ring coupling...", flush=True)
    pec_cfg, pec_coup, util_map = compute_c10_pec_observed_and_coupling(cfg)
    pec_cfg.to_csv(ev_dir / "pec_observed_configs.csv", index=False)
    pec_coup.to_csv(ev_dir / "pec_southern_ring_coupling.csv", index=False)

    print("[C10b] Bridging observed EnergyConnect commissioning regimes into AEMC ERC0386 loop.py...", flush=True)
    loop_df = compute_c10_loop_settlement_bridge(cfg, util_map)
    loop_df.to_csv(ev_dir / "pec_loop_settlement_bridge.csv", index=False)

    print("[C10c] Auditing EnergyConnect issue-time Predispatch & ST PASA forecasts...", flush=True)
    pec_fc = compute_c10_pec_forecast_scores(cfg)
    pec_fc.to_csv(ev_dir / "pec_issue_time_forecast_scores.csv", index=False)

    print("[Synthesis] Compiling 50-band long-range verdict, clustering controls, and 3-stack register...", flush=True)
    bm, cr, fe_sum, ss_sum, reg_df = compute_forecast_clustering_synthesis(cfg)
    bm.to_csv(ev_dir / "longrange_band_verdict.csv", index=False)
    cr.to_csv(ev_dir / "longrange_cell_decisions.csv", index=False)
    fe_sum.to_csv(ev_dir / "clustering_vs_controls.csv", index=False)
    ss_sum.to_csv(ev_dir / "clustering_stability_summary.csv", index=False)
    reg_df.to_csv(ev_dir / "model_stack_governance_register.csv", index=False)

    # Single-source-of-truth headline numbers
    N: dict[str, Any] = {}
    N["pec_5m_intervals"] = f"{util_map['n_5m_intervals']:,}"
    N["pec_hh_intervals"] = f"{util_map['n_hh_intervals']:,}"
    N["pec_max_flow_mw"] = f"{util_map['max_flow_mw']:.0f}"
    N["pec_tight_fwd_pct"] = f"{util_map['tight_fwd_pct']:.1f}%"
    N["pec_tight_rev_pct"] = f"{util_map['tight_rev_pct']:.1f}%"
    N["pec_forced_fwd_pct"] = f"{util_map['forced_fwd_pct']:.1f}%"
    N["pec_forced_rev_pct"] = f"{util_map['forced_rev_pct']:.1f}%"
    N["pec_u150_pct"] = f"{100.0 * util_map['u150']:.1f}%"
    N["pec_u350_pct"] = f"{100.0 * util_map['u350']:.1f}%"

    # Ring coupling shares
    vni_rev = pec_coup[(pec_coup["direction"] == "SA -> NSW (reverse)") & (pec_coup["ring_category"] == "VNI / Southern NSW Ring")]["share_pct"].sum()
    hey_fwd = pec_coup[(pec_coup["direction"] == "NSW -> SA (forward)") & (pec_coup["ring_category"] == "Heywood / VIC-SA Ring")]["share_pct"].sum()
    N["pec_vni_ring_rev_share"] = f"{vni_rev:.1f}%"
    N["pec_heywood_ring_fwd_share"] = f"{hey_fwd:.1f}%"

    # C10b Loop settlement bridge numbers
    r0 = loop_df.iloc[0]
    r150 = loop_df.iloc[1]
    r350 = loop_df.iloc[2]
    r800 = loop_df.iloc[3]
    N["loop_sq_pre_pec_m"] = f"\\${r0['sq_total_pos_m']:.1f}m"
    N["loop_net_pre_pec_m"] = f"\\${r0['loop_total_payout_m']:.1f}m"
    N["loop_net_150_m"] = f"\\${r150['loop_total_payout_m']:.1f}m"
    N["loop_net_350_m"] = f"\\${r350['loop_total_payout_m']:.1f}m"
    N["loop_net_800_m"] = f"\\${r800['loop_total_payout_m']:.1f}m"
    N["loop_pec_share_150"] = f"{r150['pec_arm_share_of_loop_pct']:.1f}%"
    N["loop_pec_share_350"] = f"{r350['pec_arm_share_of_loop_pct']:.1f}%"
    N["loop_pec_share_800"] = f"{r800['pec_arm_share_of_loop_pct']:.1f}%"
    N["loop_vicnsw_pre_m"] = f"\\${r0['loop_VICNSW_m']:.1f}m"
    N["loop_vicnsw_350_m"] = f"\\${r350['loop_VICNSW_m']:.1f}m"
    N["loop_vicsa_pre_m"] = f"\\${r0['loop_VICSA_m']:.1f}m"
    N["loop_vicsa_350_m"] = f"\\${r350['loop_VICSA_m']:.1f}m"
    N["loop_nswsa_350_m"] = f"\\${r350['loop_NSWSA_m']:.1f}m"
    N["loop_sansw_350_m"] = f"\\${r350['loop_SANSW_m']:.1f}m"

    # C10c PEC forecast headline (intraday Predispatch AEMO vs Persistence vs Regional+Constraints)
    pd_intra = pec_fc[(pec_fc["product"] == "Predispatch") & (pec_fc["lead_band"] == "intraday") & (pec_fc["direction"] == "NSW -> SA (tight)")]
    for mkey, nkey in [("Persistence", "pec_pd_intra_pers_mae"), ("AEMO Issued Forecast", "pec_pd_intra_aemo_mae"), ("Regional + Constraints", "pec_pd_intra_rc_mae")]:
        sub_m = pd_intra[pd_intra["model"] == mkey]
        N[nkey] = f"{sub_m['mae_mw'].iloc[0]:.1f}" if not sub_m.empty else "n/a"

    # Long-range 50-band verdict numbers
    N["lr_total_bands"] = str(len(bm))
    N["lr_total_cells"] = str(len(cr))
    N["lr_retained_baseline"] = str(int((cr["decision"] == "retain_baseline").sum()))
    N["lr_cal_bands"] = str(int(bm["calibrated"].sum()))
    N["lr_pos_ci_cells"] = str(int(cr["primary_improvement_ci_positive"].sum()))
    N["lr_vni_cal_vs_pers_min"] = f"{100.0 * bm[bm['connector'] == 'VNI']['skill_vs_persistence'].min():.1f}%"
    N["lr_vni_cal_vs_pers_max"] = f"{100.0 * bm[bm['connector'] == 'VNI']['skill_vs_persistence'].max():.1f}%"

    # Clustering verdict numbers
    fe7 = pd.read_csv(ROOT / cfg["inputs"]["cluster_effects"])
    fe7 = fe7[fe7["block_days"] == 7]
    N["cl_total_7d_evals"] = str(len(fe7))
    N["cl_holm_sig_wins"] = str(int(((fe7["holm_p_value"].fillna(1.0) < 0.05) & (fe7["effect_mae"] < 0)).sum()))
    N["cl_raw_wins"] = str(int((fe7["effect_mae"] < 0).sum()))
    N["cl_vni_k2_block_ari"] = f"{ss_sum[(ss_sum['connector'] == 'VNI') & (ss_sum['method'] == 'kmeans') & (ss_sum['k'] == 2)]['mean_block_ari'].iloc[0]:.2f}"
    N["cl_vni_k4_block_ari"] = f"{ss_sum[(ss_sum['connector'] == 'VNI') & (ss_sum['method'] == 'kmeans') & (ss_sum['k'] == 4)]['mean_block_ari'].iloc[0]:.2f}"
    N["rr_total_workstreams"] = str(len(reg_df))

    (ev_dir / "headline_numbers.json").write_text(json.dumps(N, indent=2), encoding="utf-8")
    print(f"[Wave 3] Wrote 9 audited CSVs + {len(N)} headline numbers to {ev_dir}", flush=True)
    return N


if __name__ == "__main__":
    run_all()
