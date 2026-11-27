"""Audit selected anonymous sources for the February 2026 RHS study.

Run from the project root with python -m scripts.rhs_sydney_sources.
Network payloads and uncompressed workbook streams remain in memory.
"""

import csv
import json
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO, StringIO, TextIOWrapper
from statistics import median
from zipfile import ZipFile

from openpyxl import load_workbook

from nemic.common import ROOT, session


OUT = ROOT / 'reports/rhs_replay/sydney_sources.csv'
EMS = ('https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/'
       'MMSDM_2026_02/MMSDM_Historical_Data_SQLLoader/DATA/'
       'PUBLIC_ARCHIVE%23EMSMASTER%23FILE01%23202602010000.zip')
PORTAL = 'https://tapr.transgrid.com.au/'
BSP = PORTAL + 'transgrid_bsp_data/Sydney%20West%20132%20kV%20historical%20BSP%20load.xlsx'
LINE = PORTAL + 'transgrid_historical_load_trace_data/Line%2030%20historical%20load%20trace.xlsx'
CATALOG = 'https://data.endeavourenergy.com.au/api/explore/v2.1/catalog/datasets?limit=100'


def fetch(url):
    with session().get(url, stream=True, timeout=(15, 60)) as response:
        response.raise_for_status()
        buf = BytesIO()
        for chunk in response.iter_content(65536):
            if buf.tell() + len(chunk) > 8_000_000:
                raise ValueError(f'Public source exceeded its per-request limit: {url}')
            buf.write(chunk)
        raw = buf.getvalue()
        return raw, dict(url=url, retrieved_utc=datetime.now(timezone.utc).isoformat(),
                         http_status=response.status_code, bytes=len(raw),
                         last_modified=response.headers.get('Last-Modified', ''),
                         sha256=sha256(raw).hexdigest())


def main():
    audit = []
    raw, info = fetch(EMS)
    with ZipFile(BytesIO(raw)) as z, z.open(z.namelist()[0]) as source:
        rows = list(csv.reader(TextIOWrapper(source, encoding='cp1252')))
    for row in rows:
        if row[0] == 'D' and row[4] in {'N_SYDNEY_LOAD', 'MWS_SW_30', 'TERRANORA_LOAD',
                                        'Q_DIRLK_MW', 'Q_DIRLK_T174TA757_758', 'Q_T174_TRA_LOAD'}:
            audit.append(dict(info, field=row[4], detail=f'{row[5]} | {row[6]} | {row[7]}'))

    for url, sheetname, value_col in [(BSP, 'Avg', 'TOT_TX'), (LINE, 'MW', 'SYW')]:
        raw, info = fetch(url)
        book = load_workbook(BytesIO(raw), read_only=True, data_only=True)
        try:
            rows = iter(book[sheetname].values)
            header = next(rows)
            idx = header.index(value_col)
            months = {key: [] for key in ['2025-02', '2025-06', '2025-07', '2026-02']}
            for row in rows:
                stamp = row[0]
                if isinstance(stamp, datetime) and (key := stamp.strftime('%Y-%m')) in months:
                    months[key].append((stamp, row[idx]))
            for key, records in months.items():
                values = [value for _, value in records if isinstance(value, (float, int))]
                gaps = sum((b[0] - a[0]).total_seconds() != 1800 for a, b in zip(records, records[1:]))
                detail = (f'{key}; timestamps={len(records)}; nonnull={len(values)}; '
                          f'non_half_hour_steps={gaps}; min={min(values):.6f}; '
                          f'median={median(values):.6f}; max={max(values):.6f}; '
                          f'first={records[0][0].isoformat()},{records[0][1]}')
                audit.append(dict(info, field=f'{sheetname}.{value_col}', detail=detail))
        finally:
            book.close()

    raw, info = fetch(CATALOG)
    catalog = json.loads(raw)
    audit.append(dict(info, field='dataset_id', detail=' | '.join(sorted(
        item['dataset_id'] for item in catalog['results']))))
    textbuf = StringIO(newline='')
    writer = csv.DictWriter(textbuf, fieldnames=list(audit[0]))
    writer.writeheader()
    writer.writerows(audit)
    payload = textbuf.getvalue().encode('utf-8')
    if len(payload) > 100_000:
        raise ValueError('Unexpected evidence-file size')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(payload)


if __name__ == '__main__':
    main()
