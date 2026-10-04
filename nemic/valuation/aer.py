"""Loader for manually downloaded AER base-futures chart exports (data/external/aer_futures/).

AER chart exports vary in layout. The loader accepts CSV/XLSX tables in long form
(region, contract, date, price) or wide form (a date column plus one column per region or
contract) and normalises them to: region, contract_quarter, date, price, source_file, sha256.
Anything it cannot interpret is listed in the status, not guessed.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .config import ROOT, sha256

FOLDER = ROOT / 'data/external/aer_futures'
REGION_ALIASES = {'NSW': 'NSW1', 'NEW SOUTH WALES': 'NSW1', 'QLD': 'QLD1', 'QUEENSLAND': 'QLD1', 'VIC': 'VIC1', 'VICTORIA': 'VIC1',
                  'SA': 'SA1', 'SOUTH AUSTRALIA': 'SA1', 'TAS': 'TAS1', 'TASMANIA': 'TAS1'}
QPAT = re.compile(r"Q([1-4])[\s\-_']*(?:20)?(\d{2})|(20\d{2})[\s\-_]*Q([1-4])", re.I)


def _region(text: str) -> str | None:
    t = str(text).upper()
    for k, v in sorted(REGION_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf'\b{k}\b', t):
            return v
    return None


def _quarter(text: str) -> str | None:
    m = QPAT.search(str(text))
    if not m:
        return None
    if m.group(1):
        return f'20{m.group(2)}Q{m.group(1)}'
    return f'{m.group(3)}Q{m.group(4)}'


def _frames(p: Path):
    if p.suffix.lower() == '.csv':
        yield p.name, pd.read_csv(p)
    elif p.suffix.lower() in ('.xlsx', '.xls'):
        for name, df in pd.read_excel(p, sheet_name=None).items():
            yield f'{p.name}:{name}', df


def load() -> tuple[pd.DataFrame, dict]:
    files = sorted([p for p in FOLDER.glob('*') if p.suffix.lower() in ('.csv', '.xlsx', '.xls')]) if FOLDER.exists() else []
    rows, status = [], {'observed': bool(files), 'files': [], 'unparsed': []}
    for p in files:
        h = sha256(p)
        region_hint, quarter_hint = _region(p.stem.replace('-', ' ')), _quarter(p.stem)
        status['files'].append({'file': p.name, 'sha256': h})
        for label, df in _frames(p):
            df = df.dropna(how='all').dropna(axis=1, how='all')
            cols = {c: str(c).strip().lower() for c in df.columns}
            date_col = next((c for c, l in cols.items() if 'date' in l or 'day' in l), None)
            price_col = next((c for c, l in cols.items() if 'price' in l or '$/mwh' in l), None)
            got = 0
            if date_col is not None and price_col is not None:  # long form
                reg_col = next((c for c, l in cols.items() if 'region' in l or 'state' in l), None)
                con_col = next((c for c, l in cols.items() if 'contract' in l or 'quarter' in l or 'product' in l), None)
                for _, r in df.iterrows():
                    reg = _region(r[reg_col]) if reg_col else region_hint
                    q = _quarter(r[con_col]) if con_col else quarter_hint
                    if reg and q and pd.notna(r[price_col]):
                        rows.append(dict(region=reg, contract_quarter=q, date=pd.to_datetime(r[date_col], dayfirst=True, errors='coerce'),
                                         price=pd.to_numeric(r[price_col], errors='coerce'), source_file=label, sha256=h)); got += 1
            elif date_col is not None:  # wide form: one column per region or contract
                for c in df.columns:
                    if c == date_col:
                        continue
                    reg = _region(c) or region_hint
                    q = _quarter(c) or quarter_hint
                    if not (reg and q):
                        continue
                    for d, v in zip(df[date_col], df[c]):
                        v = pd.to_numeric(v, errors='coerce')
                        if pd.notna(v):
                            rows.append(dict(region=reg, contract_quarter=q, date=pd.to_datetime(d, dayfirst=True, errors='coerce'), price=v, source_file=label, sha256=h)); got += 1
            if not got:
                status['unparsed'].append(label)
    out = pd.DataFrame(rows, columns=['region', 'contract_quarter', 'date', 'price', 'source_file', 'sha256'])
    out = out.dropna(subset=['date', 'price']).drop_duplicates(['region', 'contract_quarter', 'date'], keep='last')
    status['rows'] = len(out)
    status['contracts'] = int(out[['region', 'contract_quarter']].drop_duplicates().shape[0]) if len(out) else 0
    return out, status
