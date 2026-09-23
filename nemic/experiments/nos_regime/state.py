"""S3/S4: invocation spells, envelope leaders, relevance filter and half-hour family state panels."""
from __future__ import annotations

import numpy as np
import pandas as pd

from nemic.common import IC

from .common import DATA, END, MONTHS, ROOT, START, STUDY, nem_time, write_parquet

LEAD_MIN = 12          # five-minute leading intervals required for relevance (METHODOLOGY 3.3)
ALWAYS_ON = 0.95       # invoked share above which a family is treated as configuration
GRID5 = pd.date_range(START + pd.Timedelta(minutes=5), END, freq="5min")
GRID30 = pd.date_range(START + pd.Timedelta(minutes=30), END, freq="30min")


def standing(name: str) -> pd.DataFrame:
    frames = [pd.read_parquet(ROOT / f"data/constraint_{s}_2y/standing/{name}.parquet") for s in STUDY.values()]
    return pd.concat(frames, ignore_index=True).drop_duplicates()


def set_members() -> pd.DataFrame:
    g = standing("GENCONSET")[["GENCONSETID", "GENCONID"]].drop_duplicates()
    return g


def invocation_spells() -> pd.DataFrame:
    inv = standing("GENCONSETINVOKE").drop_duplicates("INVOCATION_ID")
    inv["start"] = nem_time(inv.STARTINTERVALDATETIME)
    end = inv.ENDINTERVALDATETIME.astype(str).str.replace(r"^9999.*", "2262/04/01 00:00:00", regex=True)
    inv["end"] = nem_time(end).fillna(pd.Timestamp("2262-04-01"))
    inv = inv[inv.start.notna() & (inv.end >= inv.start) & (inv.end > START) & (inv.start <= END)]
    inv["end"] = inv.end.clip(upper=END)
    inv["start"] = inv.start.clip(lower=START + pd.Timedelta(minutes=5))
    return inv[["GENCONSETID", "start", "end", "INVOCATION_ID", "SYSTEMNORMAL", "INTERVENTION"]].reset_index(drop=True)


def merge_spells(spells: pd.DataFrame) -> pd.DataFrame:
    """Merge overlapping/adjacent spells per family (inclusive interval-ending bounds)."""
    out = []
    for fam, g in spells.sort_values(["GENCONSETID", "start"]).groupby("GENCONSETID", sort=False):
        s, e = g.start.to_numpy(), g.end.to_numpy()
        cs, ce = s[0], e[0]
        for a, b in zip(s[1:], e[1:]):
            if a <= ce + np.timedelta64(5, "m"):
                ce = max(ce, b)
            else:
                out.append((fam, cs, ce)); cs, ce = a, b
        out.append((fam, cs, ce))
    return pd.DataFrame(out, columns=["GENCONSETID", "start", "end"])


def covered(merged: pd.DataFrame, times: np.ndarray) -> np.ndarray:
    s, e = merged.start.to_numpy(), merged.end.to_numpy()
    idx = np.searchsorted(s, times, side="right") - 1
    ok = idx >= 0
    out = np.zeros(len(times), bool)
    out[ok] = times[ok] <= e[idx[ok]]
    return out


def leaders(ic: str) -> pd.DataFrame:
    parts = []
    for month in MONTHS:
        p = ROOT / f"data/constraint_{STUDY[ic]}_2y/months/{month}/constraint_features_5min.parquet"
        f = pd.read_parquet(p, columns=["time", "upper_constraint", "lower_constraint"])
        parts.append(f)
    f = pd.concat(parts, ignore_index=True)
    f = f[(f.time > START) & (f.time <= END)].drop_duplicates("time")
    long = pd.concat([f[["time", "upper_constraint"]].rename(columns={"upper_constraint": "constraint"}).assign(direction="forward"),
                      f[["time", "lower_constraint"]].rename(columns={"lower_constraint": "constraint"}).assign(direction="reverse")])
    return long.dropna(subset=["constraint"])


def build_state() -> dict:
    spells = invocation_spells()
    merged = merge_spells(spells)
    write_parquet(DATA / "invocation_spells.parquet", spells)
    write_parquet(DATA / "invocation_merged.parquet", merged)
    members = set_members()
    t5 = GRID5.to_numpy()
    by_family = {f: g.reset_index(drop=True) for f, g in merged.groupby("GENCONSETID")}
    share = {f: covered(g, t5).mean() for f, g in by_family.items()}

    rel_rows, lead_rows = [], []
    for ic in IC:
        lead = leaders(ic)
        ex = lead.merge(members, left_on="constraint", right_on="GENCONID", how="inner")
        for fam, g in ex.groupby("GENCONSETID"):
            if fam not in by_family:
                continue
            times = g.time.to_numpy()
            ok = covered(by_family[fam], times)
            if not ok.any():
                continue
            hit = g[ok]
            lead_rows.append(hit[["time", "direction", "GENCONSETID", "constraint"]].assign(ic=ic))
        leads = pd.concat([x for x in lead_rows if x.ic.iat[0] == ic]) if any(x.ic.iat[0] == ic for x in lead_rows) else pd.DataFrame()
        counts = leads.groupby(["GENCONSETID", "direction"]).size().unstack(fill_value=0) if len(leads) else pd.DataFrame()
        for fam in counts.index:
            fwd = int(counts.loc[fam].get("forward", 0)); rev = int(counts.loc[fam].get("reverse", 0))
            reason = ""
            if fam.startswith("#"):
                reason = "ramp/discretionary (#)"
            elif share.get(fam, 0) > ALWAYS_ON:
                reason = f"invoked >{ALWAYS_ON:.0%} of window"
            elif max(fwd, rev) < LEAD_MIN:
                reason = f"led <{LEAD_MIN} intervals"
            rel_rows.append({"ic": ic, "name": IC[ic]["name"], "GENCONSETID": fam, "lead_forward": fwd, "lead_reverse": rev,
                             "invoked_share": share.get(fam, np.nan), "relevant": reason == "", "excluded_reason": reason})
        print(ic, "families leading", len(counts), flush=True)
    relevance = pd.DataFrame(rel_rows)
    write_parquet(DATA / "set_relevance.parquet", relevance)
    leads = pd.concat(lead_rows, ignore_index=True)
    leads["time30"] = leads.time.dt.ceil("30min")
    write_parquet(DATA / "leading_5min.parquet", leads)

    # Half-hour coverage (0..6 invoked intervals) for every family relevant to any connector
    fams = sorted(set(relevance.loc[relevance.relevant, "GENCONSETID"]))
    cov = {}
    for fam in fams:
        c = covered(by_family[fam], t5).reshape(-1, 6).sum(axis=1).astype(np.int8)
        cov[fam] = c
    coverage = pd.DataFrame(cov, index=GRID30)
    coverage.index.name = "time"
    coverage.to_parquet(DATA / "family_coverage_30min.parquet")
    lead30 = (leads[leads.GENCONSETID.isin(fams)].groupby(["ic", "direction", "time30", "GENCONSETID"]).size()
              .rename("lead_intervals").reset_index())
    write_parquet(DATA / "family_leading_30min.parquet", lead30)
    return {"spells": len(spells), "families_invoked": len(by_family),
            "relevant_by_ic": relevance[relevance.relevant].groupby("name").size().to_dict(),
            "excluded_by_reason": relevance.excluded_reason.replace("", "relevant").value_counts().to_dict(),
            "relevant_union": len(fams)}
