"""Wave 2 analytical engine (C7-C9) for Flagship B: Outage Risk & NOS Regime Handbook v2.

Computes from verified local archives (zero new NEMWEB downloads):
- C7a: NOS outage economic $/MWh regional price spread and $/day settled SRA residue impact
       with 7-day block-bootstrap 95% confidence intervals across all six interconnectors.
- C7b: Strictly chronological expanding-origin Empirical-Bayes + occurrence-hazard + isotonic
       calibrated NOS binding/setter outlook scored against raw outlook, normal, and last-year
       baselines across all 96 (layer x lead_band x link x direction) cells on identical rows.
- C8:  N-1-1 concurrent-outage super-additivity quantifying non-linear capacity and spread
       compounding when two outage families overlap simultaneously vs additive standalone sum.
- C9:  Hierarchical Empirical-Bayes corridor pooling across all 50 transmission lines
       (including dedicated Capital-Canberra Line 6 and Dapto-Marulan Line 8 deep dives)
       combining continuous spread, limit contraction, and binding |MV| severity.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[2]

LINKS = [
    {"ic": "VIC1-NSW1", "name": "VNI", "send": "VIC1", "recv": "NSW1", "sra_fwd": "VICNSW", "sra_rev": "NSWVIC"},
    {"ic": "NSW1-QLD1", "name": "QNI", "send": "NSW1", "recv": "QLD1", "sra_fwd": "NSWQLD", "sra_rev": "QLDNSW"},
    {"ic": "V-SA", "name": "Heywood", "send": "VIC1", "recv": "SA1", "sra_fwd": "VICSA", "sra_rev": "SAVIC"},
    {"ic": "N-Q-MNSP1", "name": "Directlink", "send": "NSW1", "recv": "QLD1", "sra_fwd": "NSWQLD", "sra_rev": "QLDNSW"},
    {"ic": "V-S-MNSP1", "name": "Murraylink", "send": "VIC1", "recv": "SA1", "sra_fwd": "VICSA", "sra_rev": "SAVIC"},
    {"ic": "T-V-MNSP1", "name": "Basslink", "send": "TAS1", "recv": "VIC1", "sra_fwd": "TASVIC", "sra_rev": "VICTAS"},
]
LINK_BY_IC = {x["ic"]: x for x in LINKS}


def _block_bootstrap_mean(values: np.ndarray, days: np.ndarray, n_boot: int = 150, block_days: int = 7, seed: int = 42) -> tuple[float, float, float]:
    """7-day calendar-block bootstrap mean and 95% confidence interval."""
    mask = np.isfinite(values)
    v = values[mask]
    d = days[mask]
    if len(v) == 0:
        return np.nan, np.nan, np.nan
    point = float(np.mean(v))
    d0 = int(d.min())
    blk = (d - d0) // block_days
    uniq = np.unique(blk)
    if len(uniq) < 3:
        return point, point, point
    # Precompute block sums & counts for fast exact cluster bootstrap
    b_sums = np.array([v[blk == u].sum() for u in uniq], dtype=float)
    b_cnts = np.array([(blk == u).sum() for u in uniq], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n_boot, len(uniq)))
    means = b_sums[idx].sum(axis=1) / np.maximum(b_cnts[idx].sum(axis=1), 1.0)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return point, float(lo), float(hi)


def _load_30min_market_panels(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build 30-minute aligned prices, settled directional SRA residues, and IC limits."""
    prices = pd.read_parquet(ROOT / cfg["inputs"]["prices_parquet"], columns=["time", "REGIONID", "RRP"])
    prices["time"] = pd.to_datetime(prices["time"])
    # NEM interval-ending 30-minute alignment: ceil to 30min (e.g., 00:05..00:30 -> 00:30)
    prices["hh"] = prices["time"].dt.ceil("30min")
    piv_p = prices.groupby(["hh", "REGIONID"], as_index=False)["RRP"].mean().pivot(index="hh", columns="REGIONID", values="RRP")

    sra = pd.read_parquet(ROOT / cfg["inputs"]["settlement_parquet"])
    if "time" not in sra.columns:
        sra = sra.reset_index()
    sra["time"] = pd.to_datetime(sra["time"])
    sra["hh"] = sra["time"].dt.ceil("30min")
    tags = ["VICNSW", "NSWVIC", "NSWQLD", "QLDNSW", "VICSA", "SAVIC", "TASVIC", "VICTAS"]
    sra_net = pd.DataFrame({"hh": sra["hh"]})
    for tg in tags:
        if f"{tg}_pos" in sra.columns and f"{tg}_neg" in sra.columns:
            sra_net[tg] = sra[f"{tg}_pos"].fillna(0.0) + sra[f"{tg}_neg"].fillna(0.0)
    piv_sra = sra_net.groupby("hh", as_index=True).sum()

    ics = pd.read_parquet(
        ROOT / cfg["inputs"]["interconnectors_parquet"],
        columns=["time", "INTERCONNECTORID", "MWFLOW", "EXPORTLIMIT", "IMPORTLIMIT"],
    )
    ics["time"] = pd.to_datetime(ics["time"])
    ics["hh"] = ics["time"].dt.ceil("30min")
    ics["rev_cap"] = -ics["IMPORTLIMIT"]
    # Half-hour tight directional limits = minimum across the 6 five-minute intervals (per AGENTS.md)
    hh_ic = ics.groupby(["hh", "INTERCONNECTORID"], as_index=False).agg(
        fwd_cap_min=("EXPORTLIMIT", "min"),
        rev_cap_min=("rev_cap", "min"),
        fwd_cap_mean=("EXPORTLIMIT", "mean"),
        rev_cap_mean=("rev_cap", "mean"),
        flow_mean=("MWFLOW", "mean"),
    )
    return piv_p, piv_sra, hh_ic


def compute_c7a_nos_economics(cfg: dict[str, Any], piv_p: pd.DataFrame, piv_sra: pd.DataFrame) -> pd.DataFrame:
    """C7a: Matched-pair $/MWh spread and $/day SRA residue impact for every supported NOS family."""
    pairs_dir = ROOT / cfg["inputs"]["nos_pairs_dir"]
    dl_dir = ROOT / cfg["inputs"]["nos_downloads_dir"]
    fam_eff = pd.read_csv(dl_dir / "nos_family_effects.csv")
    mv_df = pd.read_csv(dl_dir / "nos_binding_marginal_value.csv")
    min_hh = int(cfg["parameters"]["min_matched_hh_c7a"])
    n_boot = int(cfg["parameters"]["bootstrap_iters"])
    seed = int(cfg["parameters"]["seed"])

    rows = []
    for meta in LINKS:
        ic = meta["ic"]
        pfile = pairs_dir / f"pairs__{ic}.parquet"
        if not pfile.exists():
            continue
        pf = pd.read_parquet(pfile, columns=["kind", "level", "direction", "GENCONSETID", "t_time", "c_time"])
        pf = pf[(pf["kind"] == "actual") & (pf["level"] == "K2")].drop_duplicates(
            subset=["direction", "GENCONSETID", "t_time", "c_time"]
        )
        if pf.empty:
            continue
        pf["t_time"] = pd.to_datetime(pf["t_time"])
        pf["c_time"] = pd.to_datetime(pf["c_time"])
        send, recv = meta["send"], meta["recv"]
        fwd_spread = piv_p[recv] - piv_p[send]
        sra_fwd = piv_sra[meta["sra_fwd"]] if meta["sra_fwd"] in piv_sra.columns else pd.Series(dtype=float)
        sra_rev = piv_sra[meta["sra_rev"]] if meta["sra_rev"] in piv_sra.columns else pd.Series(dtype=float)

        for d_key in ("forward", "reverse"):
            sub_d = pf[pf["direction"] == d_key].copy()
            if sub_d.empty:
                continue
            sp_ser = fwd_spread if d_key == "forward" else -fwd_spread
            sra_ser = sra_fwd if d_key == "forward" else sra_rev
            sub_d["t_sp"] = sub_d["t_time"].map(sp_ser)
            sub_d["c_sp"] = sub_d["c_time"].map(sp_ser)
            sub_d["d_sp"] = sub_d["t_sp"] - sub_d["c_sp"]
            if len(sra_ser):
                sub_d["t_sra_day"] = sub_d["t_time"].map(sra_ser) * 48.0
                sub_d["c_sra_day"] = sub_d["c_time"].map(sra_ser) * 48.0
                sub_d["d_sra_day"] = sub_d["t_sra_day"] - sub_d["c_sra_day"]
            else:
                sub_d["t_sra_day"] = np.nan
                sub_d["c_sra_day"] = np.nan
                sub_d["d_sra_day"] = np.nan
            sub_d["day_int"] = (sub_d["t_time"] - pd.Timestamp("2024-09-01")).dt.days.astype(int)

            for fam, g in sub_d.groupby("GENCONSETID"):
                if len(g) < min_hh:
                    continue
                sp_eff, sp_lo, sp_hi = _block_bootstrap_mean(g["d_sp"].to_numpy(float), g["day_int"].to_numpy(int), n_boot=n_boot, seed=seed)
                sra_eff, sra_lo, sra_hi = _block_bootstrap_mean(g["d_sra_day"].to_numpy(float), g["day_int"].to_numpy(int), n_boot=n_boot, seed=seed + 1)
                rows.append({
                    "ic": ic,
                    "link": meta["name"],
                    "direction": d_key,
                    "GENCONSETID": fam,
                    "matched_hh": int(len(g)),
                    "treated_days": int(g["day_int"].nunique()),
                    "treated_spread_aud": float(np.nanmean(g["t_sp"])),
                    "control_spread_aud": float(np.nanmean(g["c_sp"])),
                    "spread_effect_aud": sp_eff,
                    "spread_ci_lo": sp_lo,
                    "spread_ci_hi": sp_hi,
                    "spread_ci_excl_zero": bool((sp_lo > 0) or (sp_hi < 0)) if np.isfinite(sp_lo) else False,
                    "sra_day_effect_aud": sra_eff,
                    "sra_day_ci_lo": sra_lo,
                    "sra_day_ci_hi": sra_hi,
                    "sra_ci_excl_zero": bool((sra_lo > 0) or (sra_hi < 0)) if np.isfinite(sra_lo) else False,
                    "treated_sra_day_aud": float(np.nanmean(g["t_sra_day"])),
                })

    out = pd.DataFrame(rows)
    # Merge capacity & flow effects from nos_family_effects.csv and MV severity from nos_binding_marginal_value.csv
    fe_cols = [c for c in ["ic", "direction", "GENCONSETID", "effect_capacity", "ci_lo_capacity", "ci_hi_capacity", "effect_headroom", "tier", "episodes"] if c in fam_eff.columns]
    if "GENCONSETID" in fam_eff.columns:
        out = out.merge(fam_eff[fe_cols].drop_duplicates(["ic", "direction", "GENCONSETID"]), on=["ic", "direction", "GENCONSETID"], how="left")
    mv_cols = [c for c in ["ic", "direction", "GENCONSETID", "treated_binding_intervals", "treated_median_abs_mv", "treated_share_gt_100"] if c in mv_df.columns]
    if "GENCONSETID" in mv_df.columns:
        out = out.merge(mv_df[mv_cols].drop_duplicates(["ic", "direction", "GENCONSETID"]), on=["ic", "direction", "GENCONSETID"], how="left")
    out["abs_sra_day_effect"] = out["sra_day_effect_aud"].abs()
    out = out.sort_values(["abs_sra_day_effect", "matched_hh"], ascending=[False, False]).drop(columns=["abs_sra_day_effect"]).reset_index(drop=True)
    return out


def compute_c7b_calibrated_outlook(cfg: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """C7b: Strictly chronological expanding-origin EB + hazard + isotonic calibration across all 96 cells."""
    bs = pd.read_parquet(ROOT / cfg["inputs"]["nos_outlook_scored"])
    bs["as_of"] = pd.to_datetime(bs["as_of"])
    origins = sorted(bs["as_of"].unique())

    # Chronological expanding-window out-of-sample predictions for origins[1:]
    # For each test origin t_k (k >= 1), fit strictly on origins[:k] with ZERO future leakage!
    oos_frames = []
    for k in range(1, len(origins)):
        tr = bs[bs["as_of"] < origins[k]].copy()
        te = bs[bs["as_of"] == origins[k]].copy()

        # 1. Empirical-Bayes hierarchical shrinkage of raw family binding rate toward (layer, name, direction, lead_band) prior
        grp_prior = tr.groupby(["layer", "name", "direction", "lead_band"], as_index=False).agg(
            prior_y=("y", "mean"), prior_n=("y", "size"), prior_occ=("occurred", "mean")
        )
        fam_stats = tr.groupby(["layer", "name", "direction", "family"], as_index=False).agg(
            fam_y=("y", "mean"), fam_n=("y", "size")
        )
        # Lead-band occurrence/cancellation hazard factor (realised y / raw p_outlook ratio shrunk smoothly)
        lead_occ = tr.groupby(["layer", "lead_band"], as_index=False).agg(
            lb_y=("y", "mean"), lb_p=("p_outlook", "mean"), lb_occ=("occurred", "mean")
        )
        lead_occ["hazard_scale"] = np.clip((lead_occ["lb_y"] + 0.01) / (lead_occ["lb_p"] + 0.01), 0.15, 1.2)

        def _make_raw_score(df_in: pd.DataFrame) -> np.ndarray:
            m = df_in[["layer", "name", "direction", "lead_band", "family", "p_outlook", "p_normal", "family_probability"]].merge(
                grp_prior, on=["layer", "name", "direction", "lead_band"], how="left"
            ).merge(
                fam_stats, on=["layer", "name", "direction", "family"], how="left"
            ).merge(
                lead_occ[["layer", "lead_band", "hazard_scale", "lb_y"]], on=["layer", "lead_band"], how="left"
            )
            prior_y = m["prior_y"].fillna(m["lb_y"]).fillna(0.05).to_numpy(float)
            # Shrink raw p_outlook scaled by lead-band occurrence hazard toward Empirical-Bayes family & cell prior
            p_adj = np.clip(m["p_outlook"].to_numpy(float) * m["hazard_scale"].fillna(0.5).to_numpy(float), 0.0, 1.0)
            fam_n = m["fam_n"].fillna(0.0).to_numpy(float)
            fam_y_raw = m["fam_y"].to_numpy(float)
            fam_y = np.where(np.isfinite(fam_y_raw), fam_y_raw, prior_y)
            # EB pseudo-count m0 = 25 bookings
            m0 = 25.0
            eb_fam = (fam_n * fam_y + m0 * prior_y) / (fam_n + m0)
            # Blend hazard-adjusted outlook, EB family rate, and p_normal smoothly
            # Weight on p_adj scales with family_probability (confidence in family inference)
            fp = m["family_probability"].fillna(0.5).clip(0.1, 1.0).to_numpy(float)
            raw_blend = 0.45 * fp * p_adj + (1.0 - 0.45 * fp) * eb_fam
            # Anchored gently with p_normal when p_normal > 0
            p_norm = m["p_normal"].fillna(0.0).to_numpy(float)
            return np.clip(0.82 * raw_blend + 0.18 * p_norm, 0.0, 1.0)

        tr_score = _make_raw_score(tr)
        te_score = _make_raw_score(te)

        # 2. Monotonic Isotonic Calibration fitted per (layer, lead_band) strictly on past training origins
        te_cal = np.zeros(len(te), dtype=float)
        for (lay, lb), idx_te in te.groupby(["layer", "lead_band"]).groups.items():
            mask_tr = (tr["layer"] == lay) & (tr["lead_band"] == lb)
            pos_te = te.index.get_indexer(idx_te)
            if mask_tr.sum() >= 50:
                iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
                iso.fit(tr_score[mask_tr.to_numpy()], tr.loc[mask_tr, "y"].to_numpy(float))
                te_cal[pos_te] = iso.predict(te_score[pos_te])
            else:
                te_cal[pos_te] = te_score[pos_te]

        te["p_eb_raw"] = te_score
        te["p_cal"] = te_cal
        oos_frames.append(te)

    oos = pd.concat(oos_frames, ignore_index=True)

    # Evaluate across all 96 (layer x lead_band x name x direction) cells on identical OOS rows
    cell_rows = []
    for (lay, lb, name, d), g in oos.groupby(["layer", "lead_band", "name", "direction"]):
        y = g["y"].to_numpy(float)
        b_raw = float(np.mean((g["p_outlook"].to_numpy(float) - y) ** 2))
        b_cal = float(np.mean((g["p_cal"].to_numpy(float) - y) ** 2))
        b_norm = float(np.mean((g["p_normal"].to_numpy(float) - y) ** 2))
        b_ly = float(np.mean((g["p_lastyear"].to_numpy(float) - y) ** 2))
        b_clim = float(np.mean((np.mean(y) - y) ** 2)) if len(y) else np.nan
        sk_raw_norm = 1.0 - b_raw / b_norm if b_norm > 0 else np.nan
        sk_cal_norm = 1.0 - b_cal / b_norm if b_norm > 0 else np.nan
        sk_raw_ly = 1.0 - b_raw / b_ly if b_ly > 0 else np.nan
        sk_cal_ly = 1.0 - b_cal / b_ly if b_ly > 0 else np.nan
        raw_skilful = bool((b_raw < b_norm) and (b_raw < b_ly))
        cal_skilful = bool((b_cal < b_norm) and (b_cal < b_ly))
        cell_rows.append({
            "layer": lay,
            "lead_band": lb,
            "link": name,
            "direction": d,
            "oos_rows": int(len(g)),
            "oos_bookings": int(g["OUTAGEID"].nunique()),
            "oos_origins": int(g["as_of"].nunique()),
            "mean_y": float(np.mean(y)),
            "brier_raw": b_raw,
            "brier_cal": b_cal,
            "brier_normal": b_norm,
            "brier_lastyear": b_ly,
            "skill_raw_vs_normal": sk_raw_norm,
            "skill_cal_vs_normal": sk_cal_norm,
            "skill_raw_vs_lastyear": sk_raw_ly,
            "skill_cal_vs_lastyear": sk_cal_ly,
            "brier_reduction_pct": float(100.0 * (b_raw - b_cal) / b_raw) if b_raw > 0 else 0.0,
            "raw_skilful": raw_skilful,
            "cal_skilful": cal_skilful,
            "cal_beats_raw": bool(b_cal < b_raw),
        })
    cells_df = pd.DataFrame(cell_rows).sort_values(["layer", "lead_band", "link", "direction"]).reset_index(drop=True)

    # Reliability curves (raw vs calibrated) on identical OOS rows
    bins = [-0.001, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50, 0.70, 1.001]
    bin_labels = ["0-2%", "2-5%", "5-10%", "10-20%", "20-30%", "30-50%", "50-70%", "70-100%"]
    rel_rows = []
    for lay in ("binding", "setter"):
        g = oos[oos["layer"] == lay]
        for model_name, col in [("raw_outlook", "p_outlook"), ("calibrated_eb_iso", "p_cal")]:
            bcut = pd.cut(g[col], bins=bins, labels=bin_labels)
            for bl in bin_labels:
                sub = g[bcut == bl]
                if len(sub) == 0:
                    continue
                rel_rows.append({
                    "layer": lay,
                    "model": model_name,
                    "bin": bl,
                    "n": int(len(sub)),
                    "p_mean": float(sub[col].mean()),
                    "y_mean": float(sub["y"].mean()),
                    "abs_cal_err": float(abs(sub[col].mean() - sub["y"].mean())),
                })
    rel_df = pd.DataFrame(rel_rows)

    # Compute overall ECE (Expected Calibration Error) and Brier summary
    summary = {}
    for lay in ("binding", "setter"):
        g = oos[oos["layer"] == lay]
        y = g["y"].to_numpy(float)
        summary[f"brier_raw_{lay}"] = float(np.mean((g["p_outlook"] - y) ** 2))
        summary[f"brier_cal_{lay}"] = float(np.mean((g["p_cal"] - y) ** 2))
        summary[f"brier_norm_{lay}"] = float(np.mean((g["p_normal"] - y) ** 2))
        summary[f"brier_ly_{lay}"] = float(np.mean((g["p_lastyear"] - y) ** 2))
        for mname in ("raw_outlook", "calibrated_eb_iso"):
            sub_r = rel_df[(rel_df["layer"] == lay) & (rel_df["model"] == mname)]
            ece = float((sub_r["n"] * sub_r["abs_cal_err"]).sum() / max(sub_r["n"].sum(), 1))
            summary[f"ece_{mname}_{lay}"] = ece

    # Apply full-history fitted isotonic map to live 12-month forward bookings (if available)
    live_rows = []
    live_gz = ROOT / cfg["inputs"]["nos_outlook_live_csv_gz"]
    if live_gz.exists():
        lv = pd.read_csv(live_gz)
        # Fit final isotonic map on all 12 origins for binding & setter layers
        iso_bind = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(
            bs.loc[bs["layer"] == "binding", "p_outlook"].to_numpy(float),
            bs.loc[bs["layer"] == "binding", "y"].to_numpy(float),
        )
        iso_set = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(
            bs.loc[bs["layer"] == "setter", "p_outlook"].to_numpy(float),
            bs.loc[bs["layer"] == "setter", "y"].to_numpy(float),
        )
        p_col = "top_binding_p" if "top_binding_p" in lv.columns else ("p_binding" if "p_binding" in lv.columns else None)
        if p_col is not None:
            lv["p_binding_raw"] = pd.to_numeric(lv[p_col], errors="coerce").fillna(0.0)
            lv["p_binding_cal"] = iso_bind.predict(lv["p_binding_raw"].to_numpy(float))
            s_col = "top_setter_p" if "top_setter_p" in lv.columns else None
            if s_col is not None:
                lv["p_setter_raw"] = pd.to_numeric(lv[s_col], errors="coerce").fillna(0.0)
                lv["p_setter_cal"] = iso_set.predict(lv["p_setter_raw"].to_numpy(float))
            keep_c = [c for c in ["OUTAGEID", "name", "direction", "asset", "region", "family", "booked_start", "booked_end", "lead_band", "largest_reduction_mw", "p_binding_raw", "p_binding_cal", "p_setter_raw", "p_setter_cal"] if c in lv.columns]
            live_df = lv[keep_c].sort_values("p_binding_cal", ascending=False).head(150).reset_index(drop=True)
        else:
            # Summarize live snapshot by lead_band/area if probability columns live in weekly table
            wk = pd.read_csv(ROOT / cfg["inputs"]["nos_downloads_dir"] / "nos_outlook_weekly.csv")
            wk["top_binding_p_raw"] = pd.to_numeric(wk["top_binding_p"], errors="coerce").fillna(0.0)
            wk["top_binding_p_cal"] = iso_bind.predict(wk["top_binding_p_raw"].to_numpy(float))
            live_df = wk.sort_values(["top_binding_p_cal", "largest_reduction_mw"], ascending=[False, True]).head(150).reset_index(drop=True)
    else:
        live_df = pd.DataFrame(live_rows)

    return cells_df, rel_df, live_df, summary


def compute_c8_n11_superadditivity(cfg: dict[str, Any], piv_p: pd.DataFrame, hh_ic: pd.DataFrame) -> pd.DataFrame:
    """C8: Concurrent N-1-1 outage family overlap super-additivity vs sum of standalone effects."""
    fc = pd.read_parquet(ROOT / cfg["inputs"]["nos_family_coverage"])
    fc.index = pd.to_datetime(fc.index)
    fc_bool = (fc > 0)
    min_ov = int(cfg["parameters"]["min_overlap_hh_c8"])
    min_sa = int(cfg["parameters"]["min_standalone_hh_c8"])
    n_boot = int(cfg["parameters"]["bootstrap_iters"])
    seed = int(cfg["parameters"]["seed"])

    # Use nos_family_effects.csv to map each link to its relevant outage families (avoid testing irrelevant interstate pairs)
    fe = pd.read_csv(ROOT / cfg["inputs"]["nos_downloads_dir"] / "nos_family_effects.csv")
    rows = []
    for meta in LINKS:
        ic = meta["ic"]
        sub_ic = hh_ic[hh_ic["INTERCONNECTORID"] == ic].set_index("hh").reindex(fc.index)
        send, recv = meta["send"], meta["recv"]
        fwd_sp = (piv_p[recv] - piv_p[send]).reindex(fc.index)
        days_idx = (fc.index - pd.Timestamp("2024-09-01")).days.to_numpy(int)

        # Top relevant families for this link that exist in fc_bool
        rel_fams = (
            fe[fe["ic"] == ic]
            .groupby("GENCONSETID")["effect_capacity"]
            .apply(lambda s: s.abs().max())
            .sort_values(ascending=False)
        )
        cand_fams = [f for f in rel_fams.index if f in fc_bool.columns and int(fc_bool[f].sum()) >= (min_ov + min_sa)][:28]
        if len(cand_fams) < 2:
            continue

        mat = fc_bool[cand_fams].to_numpy(bool)
        # Find pairs with >= min_ov simultaneous half-hours and >= min_sa standalone half-hours each
        pair_list = []
        n_f = len(cand_fams)
        for i in range(n_f):
            a = mat[:, i]
            for j in range(i + 1, n_f):
                b = mat[:, j]
                ab = a & b
                ov = int(ab.sum())
                if ov < min_ov:
                    continue
                a_only = a & (~b)
                b_only = b & (~a)
                if int(a_only.sum()) < min_sa or int(b_only.sum()) < min_sa:
                    continue
                pair_list.append((i, j, ov, int(a_only.sum()), int(b_only.sum())))

        for d_key, cap_col, sp_sign in [("forward", "fwd_cap_min", 1.0), ("reverse", "rev_cap_min", -1.0)]:
            cap = sub_ic[cap_col].to_numpy(float)
            sp = (fwd_sp.to_numpy(float)) * sp_sign
            for i, j, ov, na, nb in pair_list:
                a = mat[:, i]
                b = mat[:, j]
                ab = a & b
                a_only = a & (~b)
                b_only = b & (~a)
                neither = (~a) & (~b)
                base_cap = float(np.nanmean(cap[neither]))
                base_sp = float(np.nanmean(sp[neither]))
                da = float(np.nanmean(cap[a_only])) - base_cap
                db = float(np.nanmean(cap[b_only])) - base_cap
                dab = float(np.nanmean(cap[ab])) - base_cap
                additive_cap = da + db
                super_cap = dab - additive_cap  # negative = worse (more capacity lost than linear sum)

                sa_sp = float(np.nanmean(sp[a_only])) - base_sp
                sb_sp = float(np.nanmean(sp[b_only])) - base_sp
                sab_sp = float(np.nanmean(sp[ab])) - base_sp
                super_sp = sab_sp - (sa_sp + sb_sp)

                # Bootstrap CI on joint dab minus fixed (da + db) across overlap days
                ov_deltas = (cap[ab] - base_cap) - additive_cap
                _, ci_lo, ci_hi = _block_bootstrap_mean(ov_deltas, days_idx[ab], n_boot=n_boot, seed=seed)
                rows.append({
                    "ic": ic,
                    "link": meta["name"],
                    "direction": d_key,
                    "family_a": cand_fams[i],
                    "family_b": cand_fams[j],
                    "overlap_hh": ov,
                    "a_only_hh": na,
                    "b_only_hh": nb,
                    "baseline_cap_mw": base_cap,
                    "effect_a_mw": da,
                    "effect_b_mw": db,
                    "additive_sum_mw": additive_cap,
                    "observed_joint_mw": dab,
                    "super_additivity_mw": super_cap,
                    "super_ci_lo_mw": ci_lo,
                    "super_ci_hi_mw": ci_hi,
                    "is_compounding": bool(super_cap < -20.0 and ci_hi < 0.0),
                    "effect_a_spread_aud": sa_sp,
                    "effect_b_spread_aud": sb_sp,
                    "observed_joint_spread_aud": sab_sp,
                    "super_additivity_spread_aud": super_sp,
                })

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values("super_additivity_mw", ascending=True).reset_index(drop=True)
    return out


def _assign_corridor(row: pd.Series) -> str:
    reg = str(row["region"])
    txt = f"{row['asset']} {row['description']}".upper()
    if reg == "NSW1":
        if any(k in txt for k in ["CANBERRA", "MARULAN", "DAPTO", "YASS", "TUMUT", "WAGGA", "STOCKDIL", "SNOWY", "BANNABY", "COLLECTOR", "KANGAROO"]):
            return "NSW Southern & Snowy 330/500 kV"
        if any(k in txt for k in ["ARMIDALE", "TAMWORTH", "LISMORE", "DUMARESQ", "LIDDELL", "MUSWELL", "SAPPHIRE", "KOOLKHAN", "COFFS"]):
            return "NSW Northern & QNI 330 kV"
        return "NSW Central & Sydney Ring"
    if reg == "VIC1":
        if any(k in txt for k in ["APD", "HEYWOOD", "MOORABOOL", "TERANG", "HORSHAM", "KERANG", "RED CLIFF", "BENDIGO", "SHEPPARTON", "DEDERANG"]):
            return "VIC Western & Border 220/500 kV"
        return "VIC Metro & Latrobe 500 kV"
    if reg == "SA1":
        return "SA Heywood & Mid-North 275 kV"
    if reg == "QLD1":
        return "QLD Central & Southern 275 kV"
    if reg == "TAS1":
        return "TAS North-South 220 kV"
    return f"{reg} Other"


def compute_c9_50_line_corridor_pooling(cfg: dict[str, Any], piv_p: pd.DataFrame, hh_ic: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """C9: Hierarchical Empirical-Bayes corridor pooling + continuous risk across all 50 transmission lines."""
    ldir = ROOT / cfg["inputs"]["line_downloads_dir"]
    coh = pd.read_csv(ldir / "cohort.csv")
    ev = pd.read_csv(ldir / "event_summary.csv")
    events_df = pd.read_csv(ldir / "events.csv")
    mech = pd.read_csv(ldir / "mechanism_summary.csv")
    fals = pd.read_csv(ldir / "falsification.csv")
    ic_resp = pd.read_csv(ldir / "interconnector_event_response.csv")

    coh["corridor"] = coh.apply(_assign_corridor, axis=1)

    # Map each NEM region to its primary interconnector & direction for continuous limit & spread evaluation
    REG_IC = {
        "NSW1": ("VIC1-NSW1", "VIC1", "NSW1"),
        "VIC1": ("VIC1-NSW1", "VIC1", "NSW1"),
        "QLD1": ("NSW1-QLD1", "NSW1", "QLD1"),
        "SA1": ("V-SA", "VIC1", "SA1"),
        "TAS1": ("T-V-MNSP1", "TAS1", "VIC1"),
    }
    # Build complete 30-min panel indexed by hh with season x half-hour-of-day baseline keys
    p_panel = piv_p.copy()
    p_panel["season"] = p_panel.index.month.map(lambda m: "Summer" if m in (12, 1, 2) else ("Autumn" if m in (3, 4, 5) else ("Winter" if m in (6, 7, 8) else "Spring")))
    p_panel["hod"] = p_panel.index.hour * 2 + (p_panel.index.minute // 30)

    ic_piv = {}
    for ic_id in ["VIC1-NSW1", "NSW1-QLD1", "V-SA", "T-V-MNSP1"]:
        sub_i = hh_ic[hh_ic["INTERCONNECTORID"] == ic_id].set_index("hh").reindex(p_panel.index)
        ic_piv[ic_id] = sub_i

    # Compute exact same-season, same-time-of-day matched continuous deltas for every single one of the 50 lines
    events_df["start"] = pd.to_datetime(events_df["start"])
    events_df["end"] = pd.to_datetime(events_df["end"])
    line_stats = []
    for _, row in coh.iterrows():
        asset = row["asset"]
        reg = row["region"]
        ic_id, send_r, recv_r = REG_IC.get(reg, ("VIC1-NSW1", "VIC1", "NSW1"))
        a_evs = events_df[events_df["asset"] == asset]
        t_mask = np.zeros(len(p_panel), dtype=bool)
        for _, er in a_evs.iterrows():
            t_mask |= ((p_panel.index >= er["start"]) & (p_panel.index <= er["end"]))
        n_t = int(t_mask.sum())
        reg_p = p_panel[reg].to_numpy(float)
        sp_arr = (p_panel[recv_r] - p_panel[send_r]).to_numpy(float)
        fwd_cap = ic_piv[ic_id]["fwd_cap_min"].to_numpy(float)
        rev_cap = ic_piv[ic_id]["rev_cap_min"].to_numpy(float)

        # Compute season x hod control means strictly on non-outage half-hours for this line
        ctrl_df = pd.DataFrame({
            "season": p_panel["season"].to_numpy(),
            "hod": p_panel["hod"].to_numpy(),
            "p": reg_p, "sp": sp_arr, "fc": fwd_cap, "rc": rev_cap,
            "treated": t_mask,
        })
        ctrl_means = ctrl_df[~ctrl_df["treated"]].groupby(["season", "hod"], as_index=False).agg(
            c_p=("p", "mean"), c_sp=("sp", "mean"), c_fc=("fc", "mean"), c_rc=("rc", "mean")
        )
        tr_df = ctrl_df[ctrl_df["treated"]].merge(ctrl_means, on=["season", "hod"], how="left")
        if len(tr_df) > 0:
            dp = (tr_df["p"] - tr_df["c_p"]).to_numpy(float)
            dsp = (tr_df["sp"] - tr_df["c_sp"]).to_numpy(float)
            dfc = (tr_df["fc"] - tr_df["c_fc"]).to_numpy(float)
            drc = (tr_df["rc"] - tr_df["c_rc"]).to_numpy(float)
            days_a = (p_panel.index[t_mask] - pd.Timestamp("2024-09-01")).days.to_numpy(int)

            def _cluster_mean_se(arr: np.ndarray) -> tuple[float, float]:
                ok = np.isfinite(arr)
                if not ok.any():
                    return np.nan, np.nan
                vals = arr[ok]
                ds = days_a[ok]
                mu = float(np.mean(vals))
                # Day-clustered SE
                day_means = pd.Series(vals).groupby(ds).mean()
                if len(day_means) >= 2:
                    se = float(day_means.std(ddof=1) / np.sqrt(len(day_means)))
                else:
                    se = float(np.std(vals, ddof=1) / np.sqrt(max(len(vals) / 12.0, 1.0))) if len(vals) > 1 else abs(mu) * 0.5 + 10.0
                return mu, max(se, 1.0)

            p_mu, p_se = _cluster_mean_se(dp)
            sp_mu, sp_se = _cluster_mean_se(dsp)
            fc_mu, fc_se = _cluster_mean_se(dfc)
            rc_mu, rc_se = _cluster_mean_se(drc)
            # Pick worst (most negative) directional capacity impact on primary IC
            if np.isfinite(fc_mu) and np.isfinite(rc_mu):
                if fc_mu <= rc_mu:
                    cap_mu, cap_se, cap_dir = fc_mu, fc_se, "forward_capacity"
                else:
                    cap_mu, cap_se, cap_dir = rc_mu, rc_se, "reverse_capacity"
            else:
                cap_mu, cap_se, cap_dir = fc_mu, fc_se, "forward_capacity"
            spike300_rate = float(np.nanmean(tr_df["p"] >= 300.0) - np.nanmean(ctrl_df.loc[~ctrl_df["treated"], "p"] >= 300.0))
        else:
            p_mu = p_se = sp_mu = sp_se = cap_mu = cap_se = spike300_rate = np.nan
            cap_dir = "forward_capacity"

        line_stats.append({
            "asset": asset,
            "primary_ic": ic_id,
            "primary_cap_dir": cap_dir,
            "matched_hh_c9": n_t,
            "raw_price_eff": p_mu,
            "price_se": p_se,
            "raw_spike300_eff": spike300_rate,
            "raw_cap_eff_mw": cap_mu,
            "cap_se": cap_se,
            "raw_spread_eff_aud": sp_mu,
            "spread_se": sp_se,
        })
    ls_df = pd.DataFrame(line_stats)

    # Mechanism binding severity per asset (filtering extreme >$30k LP penalty artefacts in median |MV|)
    mech_clean = mech.copy()
    mech_clean["clean_mv"] = np.where(mech_clean["median_abs_mv"].abs() <= 30000.0, mech_clean["median_abs_mv"].abs(), np.nan)
    mech_agg = mech_clean.groupby("asset", as_index=False).agg(
        binding_constraints=("constraint", "nunique"),
        total_binding_intervals=("binding_intervals", "sum"),
        max_median_abs_mv=("clean_mv", "max"),
        mean_binding_share=("binding_share", "mean"),
    )
    ev_agg = ev.groupby("asset", as_index=False).agg(
        total_outage_hours=("hours", "sum"),
        mean_event_price=("mean_price", "mean"),
        max_event_price=("max_price", "max"),
        multi_equip_share=("multi_equipment", "mean"),
    )
    fals_agg = fals.groupby("asset", as_index=False).agg(
        fals_max_smd=("max_smd", "mean"),
        fals_placebo_m7=("placebo_minus7", "mean"),
    )

    d50 = (
        coh[["asset", "description", "region", "corridor", "voltage_kv", "owner", "events", "verified_rows", "withdrawn_rows", "importance_candidate", "selection_route"]]
        .merge(ev_agg, on="asset", how="left")
        .merge(ls_df, on="asset", how="left")
        .merge(mech_agg, on="asset", how="left")
        .merge(fals_agg, on="asset", how="left")
    )

    # Hierarchical Empirical-Bayes partial pooling within each corridor:
    # Posterior EB estimate: theta_hat_i = w_i * theta_i + (1 - w_i) * mu_c, where w_i = tau_c^2 / (tau_c^2 + s_i^2)
    for raw_col, se_col, eb_col, w_col in [
        ("raw_price_eff", "price_se", "eb_price_eff_aud", "eb_price_weight"),
        ("raw_cap_eff_mw", "cap_se", "eb_cap_eff_mw", "eb_cap_weight"),
        ("raw_spread_eff_aud", "spread_se", "eb_spread_eff_aud", "eb_spread_weight"),
    ]:
        d50[eb_col] = np.nan
        d50[w_col] = np.nan
        for corr, idx in d50.groupby("corridor").groups.items():
            sub = d50.loc[idx]
            y = sub[raw_col].to_numpy(float)
            se = sub[se_col].to_numpy(float)
            valid = np.isfinite(y)
            if valid.sum() == 0:
                continue
            med_se = float(np.nanmedian(se[valid & np.isfinite(se) & (se > 0)])) if (valid & np.isfinite(se) & (se > 0)).any() else 15.0
            se_clean = np.where(np.isfinite(se) & (se > 0), se, med_se * 1.5)
            # Finite-sample degrees-of-freedom penalty for low-event lines (n <= 4)
            n_ev = np.maximum(sub["events"].fillna(1).to_numpy(float), 1.0)
            se_adj = se_clean * np.sqrt(np.maximum(1.0, 6.0 / n_ev))
            var_i = se_adj ** 2
            prec = np.where(valid, 1.0 / np.maximum(var_i, 1e-6), 0.0)
            mu_c = float(np.sum(prec * np.nan_to_num(y)) / np.maximum(np.sum(prec), 1e-9))
            obs_var = float(np.nanvar(y[valid])) if valid.sum() > 1 else (med_se ** 2)
            tau2 = max(obs_var - float(np.mean(var_i[valid])), 0.30 * obs_var, 4.0)
            w = tau2 / (tau2 + var_i)
            eb = np.where(valid, w * np.nan_to_num(y) + (1.0 - w) * mu_c, mu_c)
            d50.loc[idx, eb_col] = eb
            d50.loc[idx, w_col] = np.where(valid, w, 0.0)

    # Composite economic outage risk score (combining |EB cap drop|, |EB spread eff|, and log binding |MV|)
    d50["composite_risk_score"] = (
        d50["eb_cap_eff_mw"].fillna(0.0).abs() / 100.0
        + d50["eb_spread_eff_aud"].fillna(0.0).abs() / 25.0
        + np.log1p(d50["max_median_abs_mv"].fillna(0.0)) / 3.0
    )
    d50 = d50.sort_values("composite_risk_score", ascending=False).reset_index(drop=True)

    # Corridor summary table
    corr_df = d50.groupby("corridor", as_index=False).agg(
        lines=("asset", "count"),
        total_events=("events", "sum"),
        median_events_per_line=("events", "median"),
        low_n_lines_le3=("events", lambda s: int((s <= 3).sum())),
        total_outage_hours=("total_outage_hours", "sum"),
        mean_raw_price_eff=("raw_price_eff", "mean"),
        mean_eb_price_eff=("eb_price_eff_aud", "mean"),
        mean_eb_cap_eff_mw=("eb_cap_eff_mw", "mean"),
        mean_eb_spread_eff_aud=("eb_spread_eff_aud", "mean"),
        total_binding_intervals=("total_binding_intervals", "sum"),
        max_median_abs_mv=("max_median_abs_mv", "max"),
    ).sort_values("mean_eb_cap_eff_mw", ascending=True).reset_index(drop=True)

    # Dedicated forensic table for Line 6 (CANBERRA/LINE/6) and Line 8 (DAPTO/LINE/8) + Snowy/Southern NSW peers
    focus_assets = ["CANBERRA/LINE/6", "DAPTO/LINE/8", "MARULAN/LINE/5", "CANBERRA/LINE/07", "STOCKDIL/LINE/3C"]
    dd = d50[d50["asset"].isin(focus_assets)].copy()
    vni_resp = ic_resp[(ic_resp["ic"] == "VIC1-NSW1") & (ic_resp["asset"].isin(focus_assets))]
    if not vni_resp.empty:
        vr_piv = vni_resp.pivot_table(index="asset", columns="state", values=["mean_forward_limit_mw", "mean_reverse_capacity_mw", "mean_flow_mw"], aggfunc="mean")
        vr_piv.columns = [f"vni_{a}_{b}" for a, b in vr_piv.columns]
        dd = dd.merge(vr_piv.reset_index(), on="asset", how="left")
    return corr_df, d50, dd


def run_all(config_path: Path | None = None) -> dict[str, Any]:
    cfg_path = config_path or (ROOT / "configs/outage_risk_v2.json")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    ev_dir = ROOT / cfg["outputs"]["evidence_dir"]
    ev_dir.mkdir(parents=True, exist_ok=True)

    print("[Wave 2] Loading 30-min market panels (prices, settled SRA, interconnectors)...", flush=True)
    piv_p, piv_sra, hh_ic = _load_30min_market_panels(cfg)

    print("[C7a] Computing matched-pair $/MWh spread and $/day SRA impacts across all 6 links...", flush=True)
    c7a = compute_c7a_nos_economics(cfg, piv_p, piv_sra)
    c7a.to_csv(ev_dir / "nos_economic_effects.csv", index=False)

    print("[C7b] Running strictly chronological EB + hazard + isotonic calibration across 96 cells...", flush=True)
    c7b_cells, c7b_rel, c7b_live, c7b_sum = compute_c7b_calibrated_outlook(cfg)
    c7b_cells.to_csv(ev_dir / "nos_outlook_calibration.csv", index=False)
    c7b_rel.to_csv(ev_dir / "nos_reliability_curves.csv", index=False)
    c7b_live.to_csv(ev_dir / "nos_live_outlook_calibrated.csv", index=False)

    print("[C8] Computing N-1-1 concurrent-outage super-additivity across 6 links...", flush=True)
    c8 = compute_c8_n11_superadditivity(cfg, piv_p, hh_ic)
    c8.to_csv(ev_dir / "nos_n11_superadditivity.csv", index=False)

    print("[C9] Computing hierarchical Empirical-Bayes corridor pooling for 50 transmission lines...", flush=True)
    c9_corr, c9_d50, c9_dd = compute_c9_50_line_corridor_pooling(cfg, piv_p, hh_ic)
    c9_corr.to_csv(ev_dir / "line_corridor_pooled_risk.csv", index=False)
    c9_d50.to_csv(ev_dir / "line_50_directory.csv", index=False)
    c9_dd.to_csv(ev_dir / "line_deep_dives_6_8.csv", index=False)

    # Copy compact booking reliability summary for Chapter 2
    bk = pd.read_csv(ROOT / cfg["inputs"]["nos_downloads_dir"] / "nos_booking_reliability.csv")
    bk.to_csv(ev_dir / "nos_booking_reliability_summary.csv", index=False)

    # Build single-source-of-truth headline_numbers.json
    N: dict[str, Any] = {}
    c7a["well_supported"] = (c7a["treated_days"] >= 5) & (c7a["matched_hh"] >= 96) & (c7a["tier"].isin(["supported", "indicative"]))
    c7a.to_csv(ev_dir / "nos_economic_effects.csv", index=False)
    c7a_ws = c7a[c7a["well_supported"]]
    N["c7a_supported_family_dirs"] = f"{len(c7a):,}"
    N["c7a_well_supported_dirs"] = f"{len(c7a_ws):,}"
    N["c7a_unique_families"] = f"{c7a['GENCONSETID'].nunique():,}"
    N["c7a_spread_sig_count"] = f"{int(c7a['spread_ci_excl_zero'].sum()):,}"
    N["c7a_sra_sig_count"] = f"{int(c7a['sra_ci_excl_zero'].sum()):,}"
    if not c7a_ws.empty:
        top_pos = c7a_ws.sort_values("sra_day_effect_aud", ascending=False).iloc[0]
        top_neg = c7a_ws.sort_values("sra_day_effect_aud", ascending=True).iloc[0]
        N["c7a_top_gain_fam"] = str(top_pos["GENCONSETID"])
        N["c7a_top_gain_link"] = f"{top_pos['link']} ({top_pos['direction']})"
        N["c7a_top_gain_sra"] = f"+\\${top_pos['sra_day_effect_aud']/1e3:,.1f}k/day"
        N["c7a_top_gain_spread"] = f"+\\${top_pos['spread_effect_aud']:,.1f}/MWh"
        N["c7a_top_loss_fam"] = str(top_neg["GENCONSETID"])
        N["c7a_top_loss_link"] = f"{top_neg['link']} ({top_neg['direction']})"
        N["c7a_top_loss_sra"] = f"-\\${abs(top_neg['sra_day_effect_aud'])/1e3:,.1f}k/day"
        N["c7a_top_loss_spread"] = f"\\${top_neg['spread_effect_aud']:,.1f}/MWh"

    # C7b headline metrics
    N["c7b_total_cells"] = str(len(c7b_cells))
    N["c7b_raw_skilful"] = str(int(c7b_cells["raw_skilful"].sum()))
    N["c7b_cal_skilful"] = str(int(c7b_cells["cal_skilful"].sum()))
    N["c7b_cal_beats_raw"] = str(int(c7b_cells["cal_beats_raw"].sum()))
    N["c7b_brier_raw_bind"] = f"{c7b_sum['brier_raw_binding']:.4f}"
    N["c7b_brier_cal_bind"] = f"{c7b_sum['brier_cal_binding']:.4f}"
    N["c7b_brier_red_bind"] = f"{100.0*(c7b_sum['brier_raw_binding']-c7b_sum['brier_cal_binding'])/c7b_sum['brier_raw_binding']:.1f}%"
    N["c7b_brier_raw_set"] = f"{c7b_sum['brier_raw_setter']:.4f}"
    N["c7b_brier_cal_set"] = f"{c7b_sum['brier_cal_setter']:.4f}"
    N["c7b_brier_red_set"] = f"{100.0*(c7b_sum['brier_raw_setter']-c7b_sum['brier_cal_setter'])/c7b_sum['brier_raw_setter']:.1f}%"
    N["c7b_ece_raw_bind"] = f"{100.0*c7b_sum['ece_raw_outlook_binding']:.2f} pp"
    N["c7b_ece_cal_bind"] = f"{100.0*c7b_sum['ece_calibrated_eb_iso_binding']:.2f} pp"
    N["c7b_ece_raw_set"] = f"{100.0*c7b_sum['ece_raw_outlook_setter']:.2f} pp"
    N["c7b_ece_cal_set"] = f"{100.0*c7b_sum['ece_calibrated_eb_iso_setter']:.2f} pp"

    # C8 headline metrics
    N["c8_pairs_tested"] = f"{len(c8):,}"
    N["c8_compounding_pairs"] = f"{int(c8['is_compounding'].sum()):,}" if not c8.empty else "0"
    if not c8.empty:
        w = c8.iloc[0]
        N["c8_worst_pair"] = f"{w['family_a']} + {w['family_b']}"
        N["c8_worst_link"] = f"{w['link']} ({w['direction']})"
        N["c8_worst_super_mw"] = f"{w['super_additivity_mw']:,.0f} MW"
        N["c8_worst_joint_mw"] = f"{w['observed_joint_mw']:,.0f} MW"
        N["c8_worst_add_mw"] = f"{w['additive_sum_mw']:,.0f} MW"

    # C9 headline metrics
    N["c9_total_lines"] = str(len(c9_d50))
    N["c9_total_corridors"] = str(len(c9_corr))
    N["c9_total_events"] = f"{int(c9_d50['events'].sum()):,}"
    N["c9_low_n_lines"] = str(int((c9_d50["events"] <= 3).sum()))
    for tag, aid in [("line6", "CANBERRA/LINE/6"), ("line8", "DAPTO/LINE/8")]:
        r = c9_d50[c9_d50["asset"] == aid]
        if not r.empty:
            row = r.iloc[0]
            N[f"c9_{tag}_events"] = str(int(row["events"]))
            N[f"c9_{tag}_raw_price"] = f"\\${row['raw_price_eff']:,.2f}/MWh" if pd.notna(row["raw_price_eff"]) else "n/a"
            N[f"c9_{tag}_eb_price"] = f"\\${row['eb_price_eff_aud']:,.2f}/MWh" if pd.notna(row["eb_price_eff_aud"]) else "n/a"
            N[f"c9_{tag}_raw_cap"] = f"{row['raw_cap_eff_mw']:,.0f} MW" if pd.notna(row["raw_cap_eff_mw"]) else "n/a"
            N[f"c9_{tag}_eb_cap"] = f"{row['eb_cap_eff_mw']:,.0f} MW" if pd.notna(row["eb_cap_eff_mw"]) else "n/a"
            N[f"c9_{tag}_weight"] = f"{100.0*row['eb_price_weight']:.0f}%" if pd.notna(row["eb_price_weight"]) else "n/a"

    # Booking reliability averages
    N["bk_total_episodes"] = f"{int(bk['episodes'].sum()):,}"
    N["bk_mean_withdrawn_pct"] = f"{100.0*bk['withdrawn_share'].mean():.1f}%"
    N["bk_mean_invoked_pct"] = f"{100.0*bk['invoked_share'].mean():.1f}%"

    (ev_dir / "headline_numbers.json").write_text(json.dumps(N, indent=2), encoding="utf-8")
    print(f"[Wave 2] Wrote 9 audited CSVs + {len(N)} headline numbers to {ev_dir}", flush=True)
    return N


if __name__ == "__main__":
    run_all()
