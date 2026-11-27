"""Read the archived public regional report available before each case cutoff.

All times are naive fixed NEM time (UTC+10). Source ZIPs live only in memory.
"""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from nemic.common import session

SNAPSHOTS = {"DATASNAP_DFS_NSYD": "N_SYDNEY_LOAD", "DATASNAP_TE_967_1": "TERRANORA_LOAD"}

def public_regional_feed(intervals, region):
    """Return the most recent eligible previous-interval NSW (or other region) row."""
    requested = sorted({pd.Timestamp(t).tz_convert("Australia/Brisbane").tz_localize(None).to_pydatetime()
                        if pd.Timestamp(t).tzinfo else pd.Timestamp(t).to_pydatetime() for t in intervals})
    prior_ends = {end - timedelta(minutes=n) for end in requested for n in (5, 10, 15)}
    published = []
    sources = []
    wanted = prior_ends | set(requested)
    for day in sorted({end.date() for end in wanted}):
        url = ("https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/"
               f"PUBLIC_DISPATCHIS_{day:%Y%m%d}.zip")
        payload = io.BytesIO()
        with session().get(url, timeout=(15, 90), stream=True) as response:
            response.raise_for_status()
            for chunk in response.iter_content(1024 * 1024):
                if payload.tell() + len(chunk) > 32_000_000:
                    raise ValueError("Unexpected daily report size")
                payload.write(chunk)
        sources.append(dict(url=url, bytes=payload.tell(),
                            sha256=hashlib.sha256(payload.getbuffer()).hexdigest(),
                            retrieved_utc=datetime.now(timezone.utc).isoformat()))
        with ZipFile(payload) as daily:
            for member in daily.infolist():
                if not member.filename.upper().startswith("PUBLIC_DISPATCHIS_"):
                    continue
                stamp = datetime.strptime(Path(member.filename).stem.split("_")[2], "%Y%m%d%H%M")
                if stamp not in wanted:
                    continue
                raw = daily.read(member)
                with ZipFile(io.BytesIO(raw)) as inner:
                    with inner.open(inner.namelist()[0]) as stream:
                        records = csv.reader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
                        header = next(records)
                        if header[:1] != ["C"] or header[2:5] != ["DISPATCHIS", "AEMO", "PUBLIC"]:
                            raise ValueError(f"Unexpected public header in {member.filename}")
                        created = datetime.strptime(" ".join(header[5:7]), "%Y/%m/%d %H:%M:%S")
                        fields = {}
                        record = dict(source_interval_end=stamp, producer_time=created,
                                      member_modified=datetime(*member.date_time), archive=url,
                                      member=member.filename, member_sha256=hashlib.sha256(raw).hexdigest())
                        for row in records:
                            if len(row) < 4 or row[1] != "DISPATCH" or row[2] not in {"REGIONSUM", "CONSTRAINT"}:
                                continue
                            if row[0] == "I":
                                fields[row[2]] = row[4:]
                            elif row[0] == "D":
                                values = dict(zip(fields[row[2]], row[4:]))
                                if values["INTERVENTION"] != "0":
                                    continue
                                assert pd.Timestamp(values["SETTLEMENTDATE"]) == stamp
                                if row[2] == "REGIONSUM" and values["REGIONID"] == region:
                                    record.update(region=region, regional_mw=float(values["TOTALDEMAND"]))
                                if row[2] == "CONSTRAINT" and values["CONSTRAINTID"] in SNAPSHOTS:
                                    if (pd.Timestamp(values["GENCONID_EFFECTIVEDATE"]) == pd.Timestamp("2024-07-11")
                                            and values["GENCONID_VERSIONNO"] == "1"):
                                        point = SNAPSHOTS[values["CONSTRAINTID"]]
                                        record[point] = float(values["RHS"]) - 10000
                        published.append(record)
    aligned = []
    for end in requested:
        cutoff = end - timedelta(minutes=5)
        candidates = [r for r in published if r["source_interval_end"] <= cutoff
                      and max(r["producer_time"], r["member_modified"]) <= cutoff
                      and r["source_interval_end"] >= cutoff - timedelta(minutes=10)]
        aligned.append(dict(interval_end=end, cutoff=cutoff, **(
            max(candidates, key=lambda r: (r["source_interval_end"], r["producer_time"]))
            if candidates else {"region": region})))
    return pd.DataFrame(aligned), sources, pd.DataFrame(published)
