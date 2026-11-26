"""Wave 1 Tier A analytics engine (C1-C6) for the Six-Link Constraint Pressure Atlas v2.

Computes from existing local archives only (zero new downloads):
  C1. Binding-weighted, tight-headroom (<50 MW), and congestion-rent-weighted DUID & constraint influence
  C2. Full 6-link 24-month parity (adds Basslink, Directlink, Murraylink) + parallel-link co-binding
  C3. Root-cause audit of QNI (411 MW) & V-SA (127 MW) vs VNI (7 MW) envelope reconstruction errors
  C4. Full-population LHS-ramp vs. RHS-shift vs. equation-switch contraction attribution across all 6 links
  C5. Technology-class & utility BESS fast-ramp impulse signature (5-min vs 30-min, diurnal concentration)
  C6. 6x6 cross-link contraction cascade matrix & NRM / counter-price forced-limit attribution
  +   Diurnal/seasonal capacity & headroom profiles with 7-day block-bootstrap 95% CIs
  +   headline_numbers.json binding every narrative token to audited CSV outputs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CFG_PATH = ROOT / "configs/constraint_pressure_v2.json"
OUT_DIR = ROOT / "reports/constraint_pressure_atlas_v2"
EV_DIR = OUT_DIR / "evidence"


def load_cfg() -> dict[str, Any]:
    return json.loads(CFG_PATH.read_text(encoding="utf-8"))


# ------------------------------------------------------------------ DUID technology classifier
_BESS_RE = re.compile(
    r"(?:BESS|BATT|VBB|HPR[G1L]|KESSB|BLYTHB|LDBESS|RIVNB|BHB|BALB|DALNTH|TORRB|"
    r"GANNB|WANDOB|WALLGR|WARAT|ERB0|TARB|BBATTERY|LIMBESS|QBYNB|HVBB|ORANAB|CHBESS|"
    r"GREENB|MORTB|HAZELB|CRBESS|RANGEB|TEMBESS|BUNGAB|ADPBA|WBSF.*B|CBESS)",
    re.I,
)
_HYDRO_RE = re.compile(
    r"(?:TUMUT|MURRAY|UPPTUMUT|GUTHEGA|BLOWER|SHGEN|SHOAL|KAREEYA|BARRON|WIVENHOE|"
    r"POATINA|GORDON|TUNGATIN|REECE|LIAPOOT|TREVALL|JOHN[SB]|MACKINT|BASTYAN|DEVILS|"
    r"CETHANA|FISHER|LEMON|PALOONA|TARRALE|BUTLERS|CATAGUN|MEADOWB|CLUNY|REPULSE|"
    r"WAYATIN|ROWALL|TRIBUTE|DARTM|EILDON|MCKAY|BOGONG|SNOWYP|HUME)",
    re.I,
)
_COAL_RE = re.compile(
    r"(?:^BW0|^ER0|^MP[12]$|^VP[56]$|^LYA[1-4]|^LOYYB|^YWPS|^CALL_|^GLAD|^STAN-|"
    r"^TARONG|^TNPS|^MPP_|^KPP_|^CS_|^LIDD|^VALES|^MTPIPER)",
    re.I,
)
_GAS_RE = re.compile(
    r"(?:URANQ|MORTLK|NEWPORT|JEERAL|TORR|PELICAN|OSB|BARK|BRAEMAR|DARLING|SWAN|"
    r"CONDAM|OAKY|COLONGRA|TALLAW|LAVNORTH|VALLEY|SOMERTON|ROMA|YABULU|MTSTUART|"
    r"BARKER|QUARANT|HALLETT|DRYCK|MINTARO|SNUGGER|LADBROK|ANGAST|BELLBAY|TAMAR|"
    r"SMITHF|HUNTER|KURRI|AGLSOM|AGLHAL)",
    re.I,
)
_SOLAR_RE = re.compile(r"(?:SF\d|SOLAR|PV\d|SUNRSF|LIMOSF|DARLSF|NEWENSF|KIAMSF|WEMENSF|WLWLSF|METZSF|GNNDHSF|COLEASF|AVLSF|KARSF|YATSF|CUSF|GESF|BOMENSF|ALDGASF|CLARESF|LILYSF|EMERASF|MOUSF|CLERMSF|GANNSF|BROKENH|STUBSF|WELNSF|WOLARSF|MOREESF|HILLSTN)", re.I)
_WIND_RE = re.compile(r"(?:WF\d|WIND|MUWAWF|STWF|ARWF|MOORAWF|BANN1|MACARTH|LKBONNY|RYEPARK|RYANCWF|GPWF|DUNDWF|GSWF|CLRKCWF|BRYB1WF|HORNSD|SNOWTWN|SAPHWF|WRWF|BANGOWF|MERCER|STOCKYD|COOPGWF|CULLER|GUNNING|CRUDINE|COLLECT|BOCO|SAPPH|WHITE|BALDH|WAUBRA|OAKLAND|CHALL|PORTL|STARHL|WILLOG|CLEMENTS|CATHE|GRANV|MUSSEL|WOOLN|STUDL|CATTLE)", re.I)


def build_duid_tech_map() -> dict[str, dict[str, str]]:
    """Classify every DUID using DUDETAILSUMMARY (DISPATCHTYPE=BIDIRECTIONAL) + NEM fuel patterns."""
    p = ROOT / "data/constraint_vni_2y/standing/DUDETAILSUMMARY.parquet"
    tech_map: dict[str, dict[str, str]] = {}
    if p.exists():
        df = pd.read_parquet(p, columns=["DUID", "DISPATCHTYPE", "REGIONID", "SCHEDULE_TYPE", "STATIONID"])
        df = df.drop_duplicates("DUID", keep="last")
        for r in df.itertuples(index=False):
            duid = str(r.DUID)
            dtype = str(r.DISPATCHTYPE or "").upper()
            stype = str(r.SCHEDULE_TYPE or "").upper()
            if dtype == "BIDIRECTIONAL" or _BESS_RE.search(duid):
                tech = "BESS"
            elif _HYDRO_RE.search(duid):
                tech = "Hydro"
            elif _COAL_RE.search(duid):
                tech = "Coal"
            elif _GAS_RE.search(duid):
                tech = "Gas"
            elif _SOLAR_RE.search(duid):
                tech = "Solar"
            elif _WIND_RE.search(duid):
                tech = "Wind"
            elif stype == "SEMI-SCHEDULED":
                tech = "Solar" if "S" in duid[-4:].upper() else "Wind"
            else:
                tech = "Other"
            tech_map[duid] = {"tech": tech, "region": str(r.REGIONID or ""), "dispatch_type": dtype}
    return tech_map


def classify_duid(duid: str, tech_map: dict[str, dict[str, str]]) -> str:
    if duid in tech_map:
        return tech_map[duid]["tech"]
    if _BESS_RE.search(duid):
        return "BESS"
    if _HYDRO_RE.search(duid):
        return "Hydro"
    if _COAL_RE.search(duid):
        return "Coal"
    if _GAS_RE.search(duid):
        return "Gas"
    if _SOLAR_RE.search(duid):
        return "Solar"
    if _WIND_RE.search(duid):
        return "Wind"
    return "Other"


def classify_constraint_family(cid: str | None, limittype: str | None = None) -> str:
    s = str(cid or "").strip()
    lt = str(limittype or "").strip()
    if not s or s.lower() == "none" or s.lower() == "nan":
        return "No reported setter"
    if s.startswith("#R") or "RAMP" in s.upper():
        return "Ramp / Discretionary (#R)"
    if "ROCOF" in s.upper() or "UFLS" in s.upper() or s.startswith("F_") or "FCAS" in lt.upper() or "FREQ" in lt.upper():
        return "ROCOF / UFLS / FCAS"
    if "I_6F" in s.upper() or "NRM" in s.upper() or "NEG" in s.upper() or s.startswith("I_"):
        return "NRM / System-Normal Discretionary"
    if lt and lt.lower() not in {"nan", "none", "other", ""}:
        return lt
    if "^^" in s:
        return "Voltage Stability"
    if "::" in s or ":N" in s or ":V" in s or ":S" in s or ":Q" in s:
        return "Transient Stability"
    if ">>" in s or ">" in s:
        return "Thermal"
    if "++" in s or "+" in s:
        return "FCAS / Frequency"
    return "Other"


def season_of(ts: pd.DatetimeIndex) -> np.ndarray:
    m = ts.month.to_numpy()
    return np.where(np.isin(m, [12, 1, 2]), "Summer",
           np.where(np.isin(m, [3, 4, 5]), "Autumn",
           np.where(np.isin(m, [6, 7, 8]), "Winter", "Spring")))


def diurnal_block_of(ts: pd.DatetimeIndex) -> np.ndarray:
    h = (ts - pd.Timedelta("1ns")).hour.to_numpy()
    return np.where((h >= 9) & (h < 16), "Solar Midday (09:00-15:55)",
           np.where((h >= 16) & (h < 21), "Evening Ramp (16:00-20:55)",
           np.where((h >= 6) & (h < 9), "Morning Peak (06:00-08:55)", "Overnight (21:00-05:55)")))


def load_market_panels(start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load 5-minute prices, interconnector telemetry, and settled directional SRA residues."""
    t0, t1 = pd.Timestamp(start), pd.Timestamp(end)
    pr = pd.read_parquet(ROOT / "data/valuation_v2/panel/prices.parquet", columns=["time", "REGIONID", "RRP"])
    pr = pr[(pr["time"] >= t0) & (pr["time"] <= t1)]
    P = pr.pivot_table(index="time", columns="REGIONID", values="RRP", aggfunc="last").sort_index()

    ic = pd.read_parquet(
        ROOT / "data/valuation_v2/panel/interconnectors.parquet",
        columns=["time", "INTERCONNECTORID", "MWFLOW", "EXPORTLIMIT", "IMPORTLIMIT", "EXPORTGENCONID", "IMPORTGENCONID"],
    )
    ic = ic[(ic["time"] >= t0) & (ic["time"] <= t1)].sort_values(["INTERCONNECTORID", "time"])

    st = pd.read_parquet(ROOT / "data/valuation_v2/settlement/directional_5min.parquet")
    if "time" in st.columns:
        st = st.set_index("time")
    st = st.loc[(st.index >= t0) & (st.index <= t1)].sort_index()
    return P, ic, st


def block_bootstrap_ci(vals: np.ndarray, days: np.ndarray, stat: str, n_rep: int, rng: np.random.Generator) -> tuple[float, float]:
    """Fast 7-day contiguous calendar-day block bootstrap CI."""
    mask = np.isfinite(vals)
    vals = vals[mask]
    days = days[mask]
    if len(vals) < 48:
        return np.nan, np.nan
    uniq_days, inv = np.unique(days, return_inverse=True)
    n_days = len(uniq_days)
    if n_days < 7:
        return np.nan, np.nan
    # Group per day (mean or median proxy via day sums/counts for speed when mean, else day medians)
    day_sums = np.bincount(inv, weights=vals, minlength=n_days)
    day_cnts = np.bincount(inv, minlength=n_days).astype(float)
    day_meds = np.array([np.median(vals[inv == i]) for i in range(n_days)])
    block = 7
    n_blocks = max(1, (n_days + block - 1) // block)
    starts = rng.integers(0, max(1, n_days - block + 1), size=(n_rep, n_blocks))
    offs = np.arange(block)[None, None, :]
    idx = (starts[:, :, None] + offs).reshape(n_rep, -1)[:, :n_days]
    if stat == "mean":
        est = day_sums[idx].sum(axis=1) / np.maximum(day_cnts[idx].sum(axis=1), 1.0)
    else:
        est = np.median(day_meds[idx], axis=1)
    lo, hi = np.quantile(est, [0.025, 0.975])
    return float(lo), float(hi)


def run_all() -> dict[str, Any]:
    cfg = load_cfg()
    EV_DIR.mkdir(parents=True, exist_ok=True)
    tech_map = build_duid_tech_map()
    P, ic_all, st_dir = load_market_panels(cfg["window_start"], cfg["window_end"])
    tight_mw = float(cfg["headroom_tight_mw"])
    scarc_k = float(cfg["scarcity_threshold_aud"])
    rng = np.random.default_rng(int(cfg["bootstrap_seed"]))

    parity_rows = []
    mae_audit_rows = []
    lhs_rhs_rows = []
    duid_econ_frames = []
    constraint_econ_frames = []
    bess_tech_rows = []
    nrm_rows = []
    diurnal_ci_rows = []

    # Store per-link 5-min state for C2 co-binding and C6 6x6 cascades
    link_5m_state: dict[str, pd.DataFrame] = {}
    link_onset_times: dict[str, np.ndarray] = {}
    link_dir_onset_times: dict[str, np.ndarray] = {}
    link_total_intervals: dict[str, int] = {}

    for lk in cfg["links"]:
        slug = lk["slug"]
        name = lk["name"]
        ic_id = lk["ic_id"]
        fr, to = lk["from_region"], lk["to_region"]
        mdir = ROOT / f"data/constraint_{slug}_2y/months"
        months = sorted([d for d in mdir.iterdir() if d.is_dir()])

        # Read 24 months of features, population summaries, influence events
        cf_parts, pop_parts, ev_parts = [], [], []
        for m in months:
            cf_parts.append(pd.read_parquet(
                m / "constraint_features_5min.parquet",
                columns=[
                    "time", "conditional_upper", "conditional_lower", "upper_room", "lower_room",
                    "upper_gen_tightening", "upper_gen_relief", "lower_gen_tightening", "lower_gen_relief",
                    "upper_constraint", "lower_constraint", "upper_version_key", "lower_version_key",
                    "partial_candidate_fraction", "envelope_inconsistent",
                ],
            ))
            pop_parts.append(pd.read_parquet(m / "constraint_population_summary.parquet"))
            ev_parts.append(pd.read_parquet(m / "influence_events.parquet"))

        cf = pd.concat(cf_parts, ignore_index=True).drop_duplicates("time").sort_values("time").set_index("time")
        pop = pd.concat(pop_parts, ignore_index=True)
        ev = pd.concat(ev_parts, ignore_index=True).sort_values(["direction", "time"])

        # Build constraint LIMITTYPE lookup from population summary
        c_type_map = (
            pop.dropna(subset=["CONSTRAINTID"])
            .drop_duplicates("CONSTRAINTID")
            .set_index("CONSTRAINTID")["LIMITTYPE"]
            .to_dict()
        )
        c_mv_map = (
            pop.groupby(["CONSTRAINTID", "direction"], as_index=False)
            .agg(
                binding_intervals=("binding_intervals", "sum"),
                leading_intervals=("leading_intervals", "sum"),
                near_binding_intervals=("near_binding_intervals", "sum"),
                applicable_intervals=("applicable_intervals", "sum"),
                mv_weighted=("mean_abs_marginal_value", lambda s: float(np.nanmean(s)) if len(s) else 0.0),
                limittype=("LIMITTYPE", "first"),
                description=("DESCRIPTION", "first"),
            )
        )
        # More accurate binding-weighted mean |MV|
        pop["mv_prod"] = pop["binding_intervals"].fillna(0) * pop["mean_abs_marginal_value"].fillna(0)
        c_econ = (
            pop.groupby(["CONSTRAINTID", "direction"], as_index=False)
            .agg(
                binding_intervals=("binding_intervals", "sum"),
                leading_intervals=("leading_intervals", "sum"),
                near_binding_intervals=("near_binding_intervals", "sum"),
                applicable_intervals=("applicable_intervals", "sum"),
                mv_prod=("mv_prod", "sum"),
                limittype=("LIMITTYPE", "first"),
                description=("DESCRIPTION", "first"),
            )
        )
        c_econ["link"] = name
        c_econ["slug"] = slug
        c_econ["mean_abs_mv_when_binding"] = np.where(
            c_econ["binding_intervals"] > 0, c_econ["mv_prod"] / c_econ["binding_intervals"], 0.0
        )
        # Separate genuine market-pricing shadow prices from LP infeasibility/zero-flow penalty weights (> $30k/MWh)
        c_econ["is_zero_or_penalty"] = (
            c_econ["CONSTRAINTID"].astype(str).str.contains(r"_ZERO$|_OUT$", case=False, regex=True)
            | (c_econ["mean_abs_mv_when_binding"] > 30000.0)
        )
        c_econ["shadow_rent_aud_per_mw"] = np.where(c_econ["is_zero_or_penalty"], 0.0, c_econ["mv_prod"] / 12.0)
        c_econ["family"] = [classify_constraint_family(c, lt) for c, lt in zip(c_econ["CONSTRAINTID"], c_econ["limittype"])]
        constraint_econ_frames.append(c_econ)

        # Merge telemetry & prices onto 5-minute grid
        ic_sub = ic_all[ic_all["INTERCONNECTORID"] == ic_id].drop_duplicates("time").set_index("time")
        grid = cf.join(ic_sub[["MWFLOW", "EXPORTLIMIT", "IMPORTLIMIT", "EXPORTGENCONID", "IMPORTGENCONID"]], how="outer")
        grid = grid.loc[(grid.index >= pd.Timestamp(cfg["window_start"])) & (grid.index <= pd.Timestamp(cfg["window_end"]))]
        grid["P_from"] = P[fr].reindex(grid.index)
        grid["P_to"] = P[to].reindex(grid.index)
        grid["spread_fwd"] = grid["P_to"] - grid["P_from"]
        grid["spread_rev"] = grid["P_from"] - grid["P_to"]
        grid["scarcity_any"] = (grid["P_from"] > scarc_k) | (grid["P_to"] > scarc_k)

        # Signed directional capacity & headroom (EXPORTLIMIT = upper, -IMPORTLIMIT = lower -> reverse cap = -IMPORTLIMIT!)
        # Verify sign convention from nemic/prepare.py: EXPORTLIMIT is positive forward cap; IMPORTLIMIT is lower bound in forward coords (negative when importing), so reverse_cap = -IMPORTLIMIT!
        grid["fwd_cap"] = grid["EXPORTLIMIT"]
        grid["rev_cap"] = -grid["IMPORTLIMIT"]
        grid["fwd_headroom"] = grid["fwd_cap"] - grid["MWFLOW"]
        grid["rev_headroom"] = grid["rev_cap"] + grid["MWFLOW"]
        grid["fwd_tight"] = grid["fwd_headroom"] <= tight_mw
        grid["rev_tight"] = grid["rev_headroom"] <= tight_mw
        grid["fwd_forced"] = grid["fwd_cap"] < 0
        grid["rev_forced"] = grid["rev_cap"] < 0

        # Reconstruction error: upper = |conditional_upper - EXPORTLIMIT|, lower = |conditional_lower - IMPORTLIMIT|
        grid["err_upper"] = (grid["conditional_upper"] - grid["EXPORTLIMIT"]).abs()
        grid["err_lower"] = (grid["conditional_lower"] - grid["IMPORTLIMIT"]).abs()
        grid["upper_match"] = grid["upper_constraint"].astype(str) == grid["EXPORTGENCONID"].astype(str)
        grid["lower_match"] = grid["lower_constraint"].astype(str) == grid["IMPORTGENCONID"].astype(str)

        link_5m_state[name] = grid[["MWFLOW", "fwd_cap", "rev_cap", "fwd_tight", "rev_tight", "fwd_forced", "rev_forced", "spread_fwd"]].copy()
        link_total_intervals[name] = len(grid)

        # ---- C2: Six-link parity summary (upper & lower)
        total_binding_eq_int = int(c_econ["binding_intervals"].sum())
        for d_key, dir_lab, cap_col, hr_col, tight_col, forced_col, err_col, match_col, sp_col in [
            ("upper", lk["fwd_label"], "fwd_cap", "fwd_headroom", "fwd_tight", "fwd_forced", "err_upper", "upper_match", "spread_fwd"),
            ("lower", lk["rev_label"], "rev_cap", "rev_headroom", "rev_tight", "rev_forced", "err_lower", "lower_match", "spread_rev"),
        ]:
            ev_d = ev[(ev["direction"] == d_key) & (ev["contraction_onset"].fillna(False))]
            drops = (-ev_d["limit_change_30m"]).dropna()
            valid_err = grid[err_col].dropna()
            parity_rows.append(dict(
                link=name, slug=slug, ic_id=ic_id, direction=d_key, dir_label=dir_lab,
                intervals=int(grid[cap_col].notna().sum()),
                median_flow_mw=float(grid["MWFLOW"].median()),
                median_cap_mw=float(grid[cap_col].median()),
                p05_cap_mw=float(grid[cap_col].quantile(0.05)),
                tight_headroom_pct=float(100.0 * grid[tight_col].mean()),
                forced_pct=float(100.0 * grid[forced_col].mean()),
                contraction_episodes=int(len(ev_d)),
                median_drop_mw=float(drops.median()) if len(drops) else 0.0,
                p90_drop_mw=float(drops.quantile(0.90)) if len(drops) else 0.0,
                max_drop_mw=float(drops.max()) if len(drops) else 0.0,
                setter_match_pct=float(100.0 * grid[match_col].mean()),
                recon_mae_mw=float(valid_err.mean()) if len(valid_err) else np.nan,
                recon_median_err_mw=float(valid_err.median()) if len(valid_err) else np.nan,
                recon_p90_err_mw=float(valid_err.quantile(0.90)) if len(valid_err) else np.nan,
                mean_spread_aud=float(grid[sp_col].mean()),
                mean_spread_when_tight_aud=float(grid.loc[grid[tight_col], sp_col].mean()) if grid[tight_col].any() else np.nan,
                binding_eq_intervals_total=total_binding_eq_int,
            ))

            # ---- C3: Reconstruction MAE root-cause audit by setter family & match status
            setter_col = "EXPORTGENCONID" if d_key == "upper" else "IMPORTGENCONID"
            fams = [classify_constraint_family(c, c_type_map.get(c)) for c in grid[setter_col]]
            tmp = pd.DataFrame({
                "family": fams,
                "matched": grid[match_col].to_numpy(),
                "err": grid[err_col].to_numpy(),
                "partial": grid["partial_candidate_fraction"].fillna(0).to_numpy() > 0,
            }).dropna(subset=["err"])
            for (fam, matched_flag), g in tmp.groupby(["family", "matched"]):
                if len(g) < 50:
                    continue
                mae_audit_rows.append(dict(
                    link=name, direction=d_key, setter_family=fam,
                    setter_matched=bool(matched_flag),
                    intervals=int(len(g)),
                    interval_share_pct=float(100.0 * len(g) / len(tmp)),
                    mae_mw=float(g["err"].mean()),
                    median_err_mw=float(g["err"].median()),
                    p90_err_mw=float(g["err"].quantile(0.90)),
                    err_contribution_mw=float(g["err"].sum() / len(tmp)),
                    partial_cand_pct=float(100.0 * g["partial"].mean()),
                ))

            # ---- C4: Full-population LHS-ramp vs. RHS-shift vs. equation-switch attribution
            # Align 30 minutes prior (6 intervals) on exact 5-min grid
            c_col = "upper_constraint" if d_key == "upper" else "lower_constraint"
            t_col = "upper_gen_tightening" if d_key == "upper" else "lower_gen_tightening"
            r_col = "upper_gen_relief" if d_key == "upper" else "lower_gen_relief"
            prev_c = grid[c_col].shift(6)
            ev_on = ev[(ev["direction"] == d_key) & (ev["contraction_onset"].fillna(False))].copy()
            ev_on["drop_mw"] = (-ev_on["limit_change_30m"]).clip(lower=0.0)
            ev_on["c_now"] = ev_on["time"].map(grid[c_col])
            ev_on["c_prev"] = ev_on["time"].map(prev_c)
            ev_on["lhs_tight"] = ev_on["time"].map(grid[t_col]).fillna(0.0)
            ev_on["lhs_relief"] = ev_on["time"].map(grid[r_col]).fillna(0.0)
            ev_on["lhs_net"] = ev_on["lhs_tight"] - ev_on["lhs_relief"]
            ev_on["is_switch"] = (ev_on["c_now"].astype(str) != ev_on["c_prev"].astype(str)) | ev_on["c_now"].isna() | ev_on["c_prev"].isna()
            ev_on["is_ramp_set"] = ev_on["c_now"].astype(str).str.startswith("#R")
            # For same-equation episodes, split drop into clipped LHS generator share vs RHS/Z shift
            same = ev_on[~ev_on["is_switch"]].copy()
            same["lhs_explained_mw"] = same["lhs_net"].clip(lower=0.0, upper=same["drop_mw"])
            same["rhs_shift_mw"] = (same["drop_mw"] - same["lhs_explained_mw"]).clip(lower=0.0)
            sw = ev_on[ev_on["is_switch"]]
            tot_drop = float(ev_on["drop_mw"].sum())
            sw_drop = float(sw["drop_mw"].sum())
            lhs_drop = float(same["lhs_explained_mw"].sum())
            rhs_drop = float(same["rhs_shift_mw"].sum())
            lhs_rhs_rows.append(dict(
                link=name, direction=d_key, dir_label=dir_lab,
                episodes=int(len(ev_on)),
                switch_episodes=int(len(sw)),
                same_eq_episodes=int(len(same)),
                ramp_set_episodes=int(ev_on["is_ramp_set"].sum()),
                switch_episode_pct=float(100.0 * len(sw) / max(len(ev_on), 1)),
                total_drop_mw=tot_drop,
                switch_drop_share_pct=float(100.0 * sw_drop / max(tot_drop, 1e-6)),
                lhs_gen_drop_share_pct=float(100.0 * lhs_drop / max(tot_drop, 1e-6)),
                rhs_z_drop_share_pct=float(100.0 * rhs_drop / max(tot_drop, 1e-6)),
                median_same_eq_lhs_mw=float(same["lhs_explained_mw"].median()) if len(same) else 0.0,
                median_same_eq_rhs_mw=float(same["rhs_shift_mw"].median()) if len(same) else 0.0,
                median_switch_drop_mw=float(sw["drop_mw"].median()) if len(sw) else 0.0,
            ))

            # Store contraction onset timestamps for C6 cascade matrix
            ts_int = ev_on["time"].astype("int64").to_numpy() // 10**9
            link_dir_onset_times[f"{name}:{d_key}"] = np.sort(np.unique(ts_int))

        # Union of upper/lower onset timestamps per link for 6x6 cascade matrix
        u_ts = link_dir_onset_times[f"{name}:upper"]
        l_ts = link_dir_onset_times[f"{name}:lower"]
        link_onset_times[name] = np.sort(np.unique(np.concatenate([u_ts, l_ts])))

        # ---- C6: NRM & counter-price attribution on forced-negative limits
        # When upper cap < 0 (fwd_forced), flow is forced REVERSE (MWFLOW < 0) against positive forward spread -> negative residue on sra_rev!
        # When lower cap < 0 (rev_forced), flow is forced FORWARD (MWFLOW > 0) against positive reverse spread -> negative residue on sra_fwd!
        sra_fwd, sra_rev = lk["sra_fwd"], lk["sra_rev"]
        for d_key, forced_col, opp_flow, sp_against, sra_opp, setter_col in [
            ("upper", "fwd_forced", -grid["MWFLOW"], grid["spread_fwd"], sra_rev, "EXPORTGENCONID"),
            ("lower", "rev_forced", grid["MWFLOW"], grid["spread_rev"], sra_fwd, "IMPORTGENCONID"),
        ]:
            f_mask = grid[forced_col].fillna(False)
            # Counter-price during forced direction: forced opposite flow > 5 MW moving from dearer into cheaper region (sp_against > 0)
            cp_mask = (opp_flow > 5.0) & (sp_against > 0.0)
            nrm_setter = grid[setter_col].astype(str).str.contains(r"I_6F|NRM|NEG_RES|#R", case=False, regex=True, na=False)
            neg_col = f"{sra_opp}_neg"
            sra_neg_s = st_dir[neg_col].reindex(grid.index).fillna(0.0) if neg_col in st_dir.columns else pd.Series(0.0, index=grid.index)
            nrm_rows.append(dict(
                link=name, direction=d_key,
                forced_intervals=int(f_mask.sum()),
                forced_share_pct=float(100.0 * f_mask.mean()),
                counterprice_intervals=int(cp_mask.sum()),
                forced_during_counterprice_pct=float(100.0 * (f_mask & cp_mask).sum() / max(f_mask.sum(), 1)),
                nrm_or_ramp_setter_during_forced_pct=float(100.0 * (f_mask & nrm_setter).sum() / max(f_mask.sum(), 1)),
                sra_neg_total_m=float(sra_neg_s.sum() / 1e6),
                sra_neg_during_forced_m=float(sra_neg_s[f_mask].sum() / 1e6),
            ))

        # ---- Diurnal & seasonal capacity/headroom with 7-day block-bootstrap 95% CIs
        grid_seas = season_of(grid.index)
        grid_blk = diurnal_block_of(grid.index)
        grid_day = grid.index.floor("D").astype("int64").to_numpy()
        for d_key, cap_col, tight_col in [("upper", "fwd_cap", "fwd_tight"), ("lower", "rev_cap", "rev_tight")]:
            cap_v = grid[cap_col].to_numpy(dtype=float)
            t_v = grid[tight_col].to_numpy(dtype=float)
            for s_name in ["Summer", "Autumn", "Winter", "Spring"]:
                ms = grid_seas == s_name
                for b_name in [
                    "Overnight (21:00-05:55)",
                    "Morning Peak (06:00-08:55)",
                    "Solar Midday (09:00-15:55)",
                    "Evening Ramp (16:00-20:55)",
                ]:
                    mb = ms & (grid_blk == b_name)
                    if mb.sum() < 48:
                        continue
                    c_sub = cap_v[mb]
                    t_sub = t_v[mb]
                    d_sub = grid_day[mb]
                    c_lo, c_hi = block_bootstrap_ci(c_sub, d_sub, "median", int(cfg["bootstrap_replicates"]), rng)
                    t_lo, t_hi = block_bootstrap_ci(t_sub, d_sub, "mean", int(cfg["bootstrap_replicates"]), rng)
                    diurnal_ci_rows.append(dict(
                        link=name, direction=d_key, season=s_name, block=b_name,
                        intervals=int(mb.sum()),
                        median_cap_mw=float(np.nanmedian(c_sub)),
                        cap_ci_lo=c_lo, cap_ci_hi=c_hi,
                        tight_headroom_pct=float(100.0 * np.nanmean(t_sub)),
                        tight_ci_lo=100.0 * t_lo, tight_ci_hi=100.0 * t_hi,
                    ))

        # ---- C1 & C5: Stream 24 months of unit_pressure_5min.parquet for economic DUID & BESS impulse stats
        # Join tight-headroom, directional spread, scarcity, and diurnal block onto each month's unit_pressure
        duid_acc: dict[str, dict[str, float]] = {}
        tech_acc: dict[str, dict[str, Any]] = {}
        grid_lookup = grid[["fwd_tight", "rev_tight", "spread_fwd", "spread_rev", "scarcity_any"]].copy()
        grid_lookup["hour"] = (grid_lookup.index - pd.Timedelta("1ns")).hour

        for m in months:
            up = pd.read_parquet(
                m / "unit_pressure_5min.parquet",
                columns=["time", "direction", "DUID", "tightening_mw", "contraction", "contraction_onset", "forced"],
            )
            if not len(up):
                continue
            up = up.join(grid_lookup, on="time", how="left")
            is_up = up["direction"] == "upper"
            tight = np.where(is_up, up["fwd_tight"].fillna(False), up["rev_tight"].fillna(False))
            sp_pos = np.where(is_up, up["spread_fwd"].fillna(0.0).clip(lower=0.0), up["spread_rev"].fillna(0.0).clip(lower=0.0))
            scarc = up["scarcity_any"].fillna(False).to_numpy()
            abs_t = up["tightening_mw"].abs().to_numpy(dtype=float)
            pos_t = up["tightening_mw"].clip(lower=0.0).to_numpy(dtype=float)
            contr = up["contraction"].fillna(False).to_numpy()
            onset = up["contraction_onset"].fillna(False).to_numpy()
            hr = up["hour"].fillna(0).to_numpy()
            is_eve = (hr >= 16) & (hr < 21)
            is_mid = (hr >= 9) & (hr < 16)

            # Congestion-rent-weighted pressure ($): only when headroom <= 50 MW and positive spread
            rent_aud = np.where(tight, abs_t * sp_pos / 12.0, 0.0)
            rent_tight_aud = np.where(tight, pos_t * sp_pos / 12.0, 0.0)

            up["abs_t"] = abs_t
            up["tight_abs"] = np.where(tight, abs_t, 0.0)
            up["scarc_abs"] = np.where(scarc, abs_t, 0.0)
            up["contr_pos"] = np.where(contr, pos_t, 0.0)
            up["onset_pos"] = np.where(onset, pos_t, 0.0)
            up["rent_aud"] = rent_aud
            up["rent_tight_aud"] = rent_tight_aud
            up["eve_abs"] = np.where(is_eve, abs_t, 0.0)
            up["mid_abs"] = np.where(is_mid, abs_t, 0.0)

            g = up.groupby("DUID", as_index=False).agg(
                rows=("abs_t", "size"),
                all_abs_mw_obs=("abs_t", "sum"),
                tight_abs_mw_obs=("tight_abs", "sum"),
                scarcity_abs_mw_obs=("scarc_abs", "sum"),
                contraction_pos_mw_obs=("contr_pos", "sum"),
                onset_pos_mw_obs=("onset_pos", "sum"),
                rent_weighted_aud=("rent_aud", "sum"),
                rent_tightening_aud=("rent_tight_aud", "sum"),
                eve_abs=("eve_abs", "sum"),
                mid_abs=("mid_abs", "sum"),
                max_single_mw=("abs_t", "max"),
            )
            for r in g.itertuples(index=False):
                d = duid_acc.setdefault(r.DUID, {
                    "rows": 0.0, "all_abs_mw_obs": 0.0, "tight_abs_mw_obs": 0.0,
                    "scarcity_abs_mw_obs": 0.0, "contraction_pos_mw_obs": 0.0,
                    "onset_pos_mw_obs": 0.0, "rent_weighted_aud": 0.0,
                    "rent_tightening_aud": 0.0, "eve_abs": 0.0, "mid_abs": 0.0,
                    "max_single_mw": 0.0,
                })
                d["rows"] += r.rows
                d["all_abs_mw_obs"] += r.all_abs_mw_obs
                d["tight_abs_mw_obs"] += r.tight_abs_mw_obs
                d["scarcity_abs_mw_obs"] += r.scarcity_abs_mw_obs
                d["contraction_pos_mw_obs"] += r.contraction_pos_mw_obs
                d["onset_pos_mw_obs"] += r.onset_pos_mw_obs
                d["rent_weighted_aud"] += r.rent_weighted_aud
                d["rent_tightening_aud"] += r.rent_tightening_aud
                d["eve_abs"] += r.eve_abs
                d["mid_abs"] += r.mid_abs
                if r.max_single_mw > d["max_single_mw"]:
                    d["max_single_mw"] = r.max_single_mw

            # 5-minute impulse jump per technology (C5): |tightening_t - tightening_{t-5m}| on consecutive steps
            up_s = up.sort_values(["DUID", "direction", "time"])
            up_s["tech"] = [classify_duid(u, tech_map) for u in up_s["DUID"]]
            same_grp = (up_s["DUID"] == up_s["DUID"].shift(1)) & (up_s["direction"] == up_s["direction"].shift(1))
            dt_ok = (up_s["time"] - up_s["time"].shift(1)) == pd.Timedelta(minutes=5)
            up_s["imp5"] = np.where(same_grp & dt_ok, (up_s["tightening_mw"] - up_s["tightening_mw"].shift(1)).abs(), np.nan)
            for tech, gt in up_s.groupby("tech"):
                ta = tech_acc.setdefault(tech, {
                    "duids": set(), "rows": 0, "all_abs": 0.0, "tight_abs": 0.0,
                    "contr_pos": 0.0, "onset_pos": 0.0, "rent_aud": 0.0,
                    "eve_abs": 0.0, "mid_abs": 0.0, "imp5_vals": [], "abs_vals": [],
                })
                ta["duids"].update(gt["DUID"].unique())
                ta["rows"] += len(gt)
                ta["all_abs"] += float(gt["abs_t"].sum())
                ta["tight_abs"] += float(gt["tight_abs"].sum())
                ta["contr_pos"] += float(gt["contr_pos"].sum())
                ta["onset_pos"] += float(gt["onset_pos"].sum())
                ta["rent_aud"] += float(gt["rent_aud"].sum())
                ta["eve_abs"] += float(gt["eve_abs"].sum())
                ta["mid_abs"] += float(gt["mid_abs"].sum())
                # Keep deterministic subsample for fast P95 impulse estimation
                v_imp = gt["imp5"].dropna().to_numpy()
                if len(v_imp):
                    step = max(1, len(v_imp) // 2500)
                    ta["imp5_vals"].append(v_imp[::step])
                v_ab = gt["abs_t"].to_numpy()
                if len(v_ab):
                    step2 = max(1, len(v_ab) // 2500)
                    ta["abs_vals"].append(v_ab[::step2])

        # Build per-link DUID economic influence DataFrame
        duid_df = pd.DataFrame([
            dict(link=name, slug=slug, DUID=k, tech=classify_duid(k, tech_map),
                 region=tech_map.get(k, {}).get("region", ""), **v)
            for k, v in duid_acc.items()
        ])
        if len(duid_df):
            duid_df["rank_all_mw"] = duid_df["all_abs_mw_obs"].rank(ascending=False, method="min").astype(int)
            duid_df["rank_tight_mw"] = duid_df["tight_abs_mw_obs"].rank(ascending=False, method="min").astype(int)
            duid_df["rank_rent_aud"] = duid_df["rent_weighted_aud"].rank(ascending=False, method="min").astype(int)
            duid_df["rank_shift_econ_vs_all"] = duid_df["rank_all_mw"] - duid_df["rank_rent_aud"]
            duid_df["tight_share_pct"] = 100.0 * duid_df["tight_abs_mw_obs"] / duid_df["all_abs_mw_obs"].clip(lower=1e-6)
            duid_df["eve_share_pct"] = 100.0 * duid_df["eve_abs"] / duid_df["all_abs_mw_obs"].clip(lower=1e-6)
            duid_df["midday_share_pct"] = 100.0 * duid_df["mid_abs"] / duid_df["all_abs_mw_obs"].clip(lower=1e-6)
            duid_econ_frames.append(duid_df.sort_values("rent_weighted_aud", ascending=False))

        tot_link_all = sum(v["all_abs"] for v in tech_acc.values()) or 1.0
        tot_link_rent = sum(v["rent_aud"] for v in tech_acc.values()) or 1.0
        tot_link_onset = sum(v["onset_pos"] for v in tech_acc.values()) or 1.0
        for tech, ta in tech_acc.items():
            imp_arr = np.concatenate(ta["imp5_vals"]) if ta["imp5_vals"] else np.array([0.0])
            ab_arr = np.concatenate(ta["abs_vals"]) if ta["abs_vals"] else np.array([0.0])
            bess_tech_rows.append(dict(
                link=name, tech=tech, active_duids=len(ta["duids"]), rows=int(ta["rows"]),
                all_abs_share_pct=float(100.0 * ta["all_abs"] / tot_link_all),
                rent_share_pct=float(100.0 * ta["rent_aud"] / tot_link_rent),
                onset_tightening_share_pct=float(100.0 * ta["onset_pos"] / tot_link_onset),
                mean_abs_30m_mw=float(ta["all_abs"] / max(ta["rows"], 1)),
                p95_abs_30m_mw=float(np.quantile(ab_arr, 0.95)),
                p95_impulse_5m_mw=float(np.quantile(imp_arr, 0.95)),
                eve_share_pct=float(100.0 * ta["eve_abs"] / max(ta["all_abs"], 1e-6)),
                midday_share_pct=float(100.0 * ta["mid_abs"] / max(ta["all_abs"], 1e-6)),
                rent_weighted_m=float(ta["rent_aud"] / 1e6),
            ))
        print(f"[C1-C6] Completed {name} ({len(months)} months, {len(duid_df)} DUIDs)", flush=True)

    # ---- C2 Parallel-link co-binding (QNI + Directlink, Heywood + Murraylink)
    cobind_rows = []
    for a_name, b_name, pair_lab in [("QNI", "Directlink", "QNI + Directlink (QLD-NSW)"), ("Heywood", "Murraylink", "Heywood + Murraylink (VIC-SA)")]:
        ga, gb = link_5m_state[a_name], link_5m_state[b_name]
        j = ga.join(gb, lsuffix="_a", rsuffix="_b", how="inner")
        for d_key, col in [("upper", "fwd_tight"), ("lower", "rev_tight")]:
            ta = j[f"{col}_a"].fillna(False)
            tb = j[f"{col}_b"].fillna(False)
            both = ta & tb
            cobind_rows.append(dict(
                pair=pair_lab, link_a=a_name, link_b=b_name, direction=d_key,
                intervals=int(len(j)),
                a_tight_pct=float(100.0 * ta.mean()),
                b_tight_pct=float(100.0 * tb.mean()),
                both_tight_pct=float(100.0 * both.mean()),
                p_b_given_a_pct=float(100.0 * both.sum() / max(ta.sum(), 1)),
                p_a_given_b_pct=float(100.0 * both.sum() / max(tb.sum(), 1)),
            ))

    # ---- C6: 6x6 cross-link contraction cascade matrix (±30 min window)
    win_sec = int(cfg["cascade_window_minutes"]) * 60
    link_names = [lk["name"] for lk in cfg["links"]]
    cascade_rows = []
    for src in link_names:
        s_ts = link_onset_times[src]
        for dst in link_names:
            d_ts = link_onset_times[dst]
            # Fast two-pointer searchsorted count of src onsets with any dst onset in [t - win, t + win]
            if len(s_ts) == 0 or len(d_ts) == 0:
                p_cond, base_rate, lift = 0.0, 0.0, np.nan
            else:
                lo = np.searchsorted(d_ts, s_ts - win_sec, side="left")
                hi = np.searchsorted(d_ts, s_ts + win_sec, side="right")
                hits = (hi > lo) if src != dst else ((hi - lo) > 0)
                p_cond = float(hits.mean()) if src != dst else 1.0
                # Baseline unconditional probability that any random 5-min timestamp falls within ±30m of a dst onset
                # Exact occupancy via merged intervals [t - win, t + win] divided by 2-year total seconds
                tot_sec = max(link_total_intervals[dst] * 300.0, 1.0)
                starts = d_ts - win_sec
                ends = d_ts + win_sec
                merged_sec = 0.0
                cs, ce = starts[0], ends[0]
                for ns, ne in zip(starts[1:], ends[1:]):
                    if ns <= ce:
                        ce = max(ce, ne)
                    else:
                        merged_sec += (ce - cs)
                        cs, ce = ns, ne
                merged_sec += (ce - cs)
                base_rate = float(min(merged_sec / tot_sec, 1.0))
                lift = float(p_cond / max(base_rate, 1e-6))
            cascade_rows.append(dict(
                source_link=src, target_link=dst,
                source_episodes=int(len(s_ts)), target_episodes=int(len(d_ts)),
                cond_prob_pct=100.0 * p_cond,
                baseline_prob_pct=100.0 * base_rate,
                lift_ratio=lift,
            ))

    # Write all audited compact CSVs
    parity_df = pd.DataFrame(parity_rows)
    cobind_df = pd.DataFrame(cobind_rows)
    mae_df = pd.DataFrame(mae_audit_rows).sort_values(["link", "direction", "err_contribution_mw"], ascending=[True, True, False])
    lhs_df = pd.DataFrame(lhs_rhs_rows)
    duid_all = pd.concat(duid_econ_frames, ignore_index=True)
    # Keep top 45 DUIDs per link (270 rows total — compact & comprehensive!)
    duid_compact = duid_all.groupby("link", group_keys=False).head(45)
    c_econ_all = pd.concat(constraint_econ_frames, ignore_index=True).sort_values("shadow_rent_aud_per_mw", ascending=False)
    c_econ_compact = c_econ_all.groupby("link", group_keys=False).head(40)
    bess_df = pd.DataFrame(bess_tech_rows)
    cascade_df = pd.DataFrame(cascade_rows)
    nrm_df = pd.DataFrame(nrm_rows)
    diur_df = pd.DataFrame(diurnal_ci_rows)

    parity_df.to_csv(EV_DIR / "six_link_parity_summary.csv", index=False)
    cobind_df.to_csv(EV_DIR / "parallel_link_cobinding.csv", index=False)
    mae_df.to_csv(EV_DIR / "reconstruction_mae_audit.csv", index=False)
    lhs_df.to_csv(EV_DIR / "contraction_lhs_rhs_switch.csv", index=False)
    duid_compact.to_csv(EV_DIR / "duid_economic_influence.csv", index=False)
    c_econ_compact.to_csv(EV_DIR / "constraint_economic_influence.csv", index=False)
    bess_df.to_csv(EV_DIR / "bess_ramp_signature.csv", index=False)
    cascade_df.to_csv(EV_DIR / "cross_link_cascades.csv", index=False)
    nrm_df.to_csv(EV_DIR / "nrm_clamping_attribution.csv", index=False)
    diur_df.to_csv(EV_DIR / "diurnal_seasonal_ci_profiles.csv", index=False)

    # Build headline_numbers.json for zero manual transcription in Flagship A
    N = build_headline_numbers(parity_df, cobind_df, mae_df, lhs_df, duid_all, c_econ_all, bess_df, cascade_df, nrm_df)
    (EV_DIR / "headline_numbers.json").write_text(json.dumps(N, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote 10 audited CSVs + {len(N)} headline numbers to {EV_DIR}", flush=True)
    return N


def build_headline_numbers(
    parity: pd.DataFrame,
    cobind: pd.DataFrame,
    mae: pd.DataFrame,
    lhs: pd.DataFrame,
    duid: pd.DataFrame,
    cecon: pd.DataFrame,
    bess: pd.DataFrame,
    casc: pd.DataFrame,
    nrm: pd.DataFrame,
) -> dict[str, str]:
    N: dict[str, str] = {}
    N["total_contraction_episodes_6link"] = f"{int(parity['contraction_episodes'].sum()):,}"
    N["total_binding_eq_intervals_6link"] = f"{int(cecon['binding_intervals'].sum()):,}"
    N["total_unique_duids_6link"] = f"{int(duid['DUID'].nunique()):,}"

    for _, r in parity.iterrows():
        k = f"{r['slug']}_{r['direction']}"
        N[f"cap_med_{k}"] = f"{r['median_cap_mw']:.0f}"
        N[f"tight_pct_{k}"] = f"{r['tight_headroom_pct']:.1f}%"
        N[f"forced_pct_{k}"] = f"{r['forced_pct']:.1f}%"
        N[f"ep_{k}"] = f"{int(r['contraction_episodes']):,}"
        N[f"drop_med_{k}"] = f"{r['median_drop_mw']:.0f}"
        N[f"drop_p90_{k}"] = f"{r['p90_drop_mw']:.0f}"
        N[f"match_pct_{k}"] = f"{r['setter_match_pct']:.1f}%"
        N[f"mae_{k}"] = f"{r['recon_mae_mw']:.1f}"
        N[f"sp_tight_{k}"] = f"\\${r['mean_spread_when_tight_aud']:.2f}" if np.isfinite(r["mean_spread_when_tight_aud"]) else "n/a"

    # C1 top economic vs mechanical DUIDs per link
    for lk in ["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"]:
        sub = duid[duid["link"] == lk].sort_values("rent_weighted_aud", ascending=False)
        sub_m = duid[duid["link"] == lk].sort_values("all_abs_mw_obs", ascending=False)
        sk = lk.lower()
        if len(sub):
            N[f"top_econ_duid_{sk}"] = str(sub.iloc[0]["DUID"])
            N[f"top_econ_tech_{sk}"] = str(sub.iloc[0]["tech"])
            N[f"top_econ_rent_{sk}"] = f"\\${sub.iloc[0]['rent_weighted_aud']/1e6:.1f}m"
            N[f"top_mech_duid_{sk}"] = str(sub_m.iloc[0]["DUID"])
            N[f"top_econ_shift_{sk}"] = f"{int(sub.iloc[0]['rank_shift_econ_vs_all']):+d}"
        csub = cecon[cecon["link"] == lk].sort_values("shadow_rent_aud_per_mw", ascending=False)
        if len(csub):
            N[f"top_eq_{sk}"] = str(csub.iloc[0]["CONSTRAINTID"])
            N[f"top_eq_bind_{sk}"] = f"{int(csub.iloc[0]['binding_intervals']):,}"
            N[f"top_eq_mv_{sk}"] = f"\\${csub.iloc[0]['mean_abs_mv_when_binding']:.1f}"

    # C2 co-binding
    for _, r in cobind.iterrows():
        ck = f"cobind_{r['link_a'].lower()}_{r['direction']}"
        N[ck + "_both"] = f"{r['both_tight_pct']:.1f}%"
        N[ck + "_pba"] = f"{r['p_b_given_a_pct']:.1f}%"

    # C3 MAE driver summary (top error contributor for QNI upper, V-SA upper, VNI upper)
    for lk, d_key, tag in [("QNI", "upper", "qni_up"), ("QNI", "lower", "qni_lo"), ("Heywood", "upper", "vsa_up"), ("VNI", "upper", "vni_up")]:
        sub = mae[(mae["link"] == lk) & (mae["direction"] == d_key)].sort_values("err_contribution_mw", ascending=False)
        if len(sub):
            top = sub.iloc[0]
            N[f"mae_top_fam_{tag}"] = str(top["setter_family"])
            N[f"mae_top_val_{tag}"] = f"{top['mae_mw']:.1f}"
            N[f"mae_top_contrib_{tag}"] = f"{top['err_contribution_mw']:.1f}"
        unm = mae[(mae["link"] == lk) & (mae["direction"] == d_key) & (~mae["setter_matched"])]
        tot = mae[(mae["link"] == lk) & (mae["direction"] == d_key)]
        if len(tot):
            N[f"mae_unmatched_share_{tag}"] = f"{100.0 * unm['err_contribution_mw'].sum() / max(tot['err_contribution_mw'].sum(), 1e-6):.0f}%"

    # C4 LHS/RHS/Switch aggregate across all 6 links and key links
    tot_sw = lhs["switch_episodes"].sum()
    tot_ep = lhs["episodes"].sum()
    N["c4_switch_ep_pct_all"] = f"{100.0 * tot_sw / max(tot_ep, 1):.1f}%"
    N["c4_switch_drop_pct_all"] = f"{100.0 * (lhs['total_drop_mw'] * lhs['switch_drop_share_pct'] / 100.0).sum() / max(lhs['total_drop_mw'].sum(), 1e-6):.1f}%"
    N["c4_lhs_drop_pct_all"] = f"{100.0 * (lhs['total_drop_mw'] * lhs['lhs_gen_drop_share_pct'] / 100.0).sum() / max(lhs['total_drop_mw'].sum(), 1e-6):.1f}%"
    N["c4_rhs_drop_pct_all"] = f"{100.0 * (lhs['total_drop_mw'] * lhs['rhs_z_drop_share_pct'] / 100.0).sum() / max(lhs['total_drop_mw'].sum(), 1e-6):.1f}%"
    for _, r in lhs.iterrows():
        tk = f"{r['link'].lower()}_{r['direction']}"
        N[f"c4_sw_{tk}"] = f"{r['switch_drop_share_pct']:.1f}%"
        N[f"c4_lhs_{tk}"] = f"{r['lhs_gen_drop_share_pct']:.1f}%"
        N[f"c4_rhs_{tk}"] = f"{r['rhs_z_drop_share_pct']:.1f}%"

    # C5 BESS signature
    for lk in ["VNI", "QNI", "Heywood", "Murraylink"]:
        sub = bess[(bess["link"] == lk) & (bess["tech"] == "BESS")]
        sol = bess[(bess["link"] == lk) & (bess["tech"] == "Solar")]
        sk = lk.lower()
        if len(sub):
            r = sub.iloc[0]
            N[f"bess_duids_{sk}"] = str(int(r["active_duids"]))
            N[f"bess_p95_imp5_{sk}"] = f"{r['p95_impulse_5m_mw']:.1f}"
            N[f"bess_onset_share_{sk}"] = f"{r['onset_tightening_share_pct']:.1f}%"
            N[f"bess_rent_share_{sk}"] = f"{r['rent_share_pct']:.1f}%"
            N[f"bess_eve_share_{sk}"] = f"{r['eve_share_pct']:.1f}%"
        if len(sol):
            N[f"solar_p95_imp5_{sk}"] = f"{sol.iloc[0]['p95_impulse_5m_mw']:.1f}"

    # C6 Cascades & NRM
    off_diag = casc[casc["source_link"] != casc["target_link"]].sort_values("lift_ratio", ascending=False)
    if len(off_diag):
        top_c = off_diag.iloc[0]
        N["casc_top_pair"] = f"{top_c['source_link']} → {top_c['target_link']}"
        N["casc_top_prob"] = f"{top_c['cond_prob_pct']:.1f}%"
        N["casc_top_lift"] = f"{top_c['lift_ratio']:.2f}×"
    for s, t, tag in [("VNI", "Heywood", "vni_vsa"), ("VNI", "Murraylink", "vni_ml"), ("QNI", "Directlink", "qni_dl"), ("Heywood", "Murraylink", "vsa_ml")]:
        g = casc[(casc["source_link"] == s) & (casc["target_link"] == t)]
        if len(g):
            N[f"casc_prob_{tag}"] = f"{g.iloc[0]['cond_prob_pct']:.1f}%"
            N[f"casc_lift_{tag}"] = f"{g.iloc[0]['lift_ratio']:.2f}×"
    for lk, d_key, tag in [("VNI", "lower", "vni_lo"), ("VNI", "upper", "vni_up"), ("QNI", "upper", "qni_up"), ("Heywood", "lower", "vsa_lo")]:
        g = nrm[(nrm["link"] == lk) & (nrm["direction"] == d_key)]
        if len(g):
            N[f"nrm_cp_pct_{tag}"] = f"{g.iloc[0]['forced_during_counterprice_pct']:.1f}%"
            N[f"nrm_set_pct_{tag}"] = f"{g.iloc[0]['nrm_or_ramp_setter_during_forced_pct']:.1f}%"
            N[f"nrm_neg_m_{tag}"] = f"−\\${abs(g.iloc[0]['sra_neg_total_m']):.1f}m"

    return N


if __name__ == "__main__":
    run_all()
