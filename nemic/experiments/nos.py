"""Lossless snapshot change archive. Scheduled sets are not observed invocation."""
import csv
import io
import json
import re
import time
import zipfile
from urllib.parse import urljoin, urlparse

import pandas as pd

from nemic.common import session
from .core import Store, digest, fingerprint

ARCHIVE = 'https://www.nemweb.com.au/Reports/ARCHIVE/Network/'
TABLES = ('OUTAGEDETAIL', 'OUTAGECONSTRAINTSET')


def parse_snapshot(blob, name, record_cache=None):
    """Retain distinct complete raw records; row removal is not restoration."""
    stamp = re.search(r'PUBLIC_NETWORK_(\d{14})_', name)
    if not stamp:
        raise ValueError('No report timestamp')
    generated = pd.to_datetime(stamp[1], format='%Y%m%d%H%M%S')
    schemas, records = {}, {}
    cache = {} if record_cache is None else record_cache
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members = [m for m in z.infolist() if m.filename.lower().endswith('.csv')]
        if len(members) != 1 or members[0].file_size > 100_000_000:
            raise ValueError('Unexpected snapshot member count/size')
        content = z.read(members[0]).decode('utf-8-sig')
    header = next(csv.reader([content.splitlines()[0]]))
    if pd.Timestamp(header[5] + ' ' + header[6]) != generated:
        raise ValueError('Filename/header timestamp disagreement')
    for row in csv.reader(io.StringIO(content)):
        if len(row) < 4 or row[1] != 'NETWORK' or row[2] not in TABLES:
            continue
        key = (row[2], row[3])
        if row[0] == 'I':
            schemas[key] = row[4:]
        elif row[0] == 'D':
            if key not in schemas or len(row[4:]) != len(schemas[key]):
                raise ValueError('Unregistered/malformed NOS schema')
            cache_key = (tuple(schemas[key]), tuple(row))
            if cache_key in cache:
                rid, payload = cache[cache_key]
                records[rid] = payload
                continue
            data = dict(zip(schemas[key], row[4:]))
            payload = {'table': row[2], 'version': row[3], 'fields': data}
            rid = fingerprint(payload)
            records[rid] = payload
            cache[cache_key] = (rid, payload)
    if set(k[0] for k in schemas) != set(TABLES) or not records:
        raise ValueError('Incomplete snapshot; do not infer removals')
    return generated, records


def inventory_nos(c):
    response = session().get(ARCHIVE, timeout=(20, 90))
    response.raise_for_status()
    urls = sorted(set(urljoin(ARCHIVE, p) for p in re.findall(r'HREF=["\']([^"\']+)', response.text, re.I)
                      if re.search(r'PUBLIC_NETWORK_\d{8}\.zip$', p)))
    result = {'source': ARCHIVE, 'retrieved_utc': pd.Timestamp.now(tz='UTC').isoformat(),
              'urls': urls, 'claim': 'Inventory only; coverage requires parsed snapshots'}
    Store(c).json(c['_run'] / 'nos/inventory.json', result)
    return result


def recover_nos(c, limit=None):
    store = Store(c)
    inv = inventory_nos(c)
    start = time.monotonic()
    for url in inv['urls'][:limit]:
        if time.monotonic() - start > c['limits']['batch_hours'] * 3600:
            break
        if urlparse(url).hostname != 'www.nemweb.com.au':
            raise ValueError('Unexpected archive host')
        name = url.rsplit('/', 1)[-1]
        folder = store.root / 'nos/weeks' / name.removesuffix('.zip')
        ident = 'nos/' + name
        fp = fingerprint([url, 'lossless-snapshot-change-v1'])
        if store.valid(ident, fp):
            continue
        manifest_path = folder / 'manifest.json'
        if manifest_path.exists():
            prior = json.loads(manifest_path.read_text())
            if prior.get('url') == url and prior.get('artifacts') and all(
                    (store.root / item['path']).exists() and digest(store.root / item['path']) == item['sha256']
                    for item in prior['artifacts']):
                store.complete(ident, fp, manifest_path)
                continue
        scratch = store.root / 'scratch' / name
        scratch.parent.mkdir(parents=True, exist_ok=True)
        with store.reserve(c['limits']['file_bytes'] + 300_000_000):
            with session().get(url, stream=True, timeout=(20, 180)) as response:
                response.raise_for_status()
                written = 0
                with scratch.open('wb') as output:
                    for chunk in response.iter_content(1024 * 1024):
                        written += len(chunk)
                        if written > c['limits']['file_bytes']:
                            raise ValueError('Download cap exceeded')
                        output.write(chunk)
            previous, catalogue, events, reports, rejected, record_cache = set(), {}, [], [], [], {}
            with zipfile.ZipFile(scratch) as outer:
                for member in sorted(outer.infolist(), key=lambda m: m.filename):
                    if not member.filename.lower().endswith('.zip'):
                        continue
                    if member.file_size > 100_000_000:
                        raise ValueError('Oversized nested snapshot')
                    try:
                        generated, rows = parse_snapshot(outer.read(member), member.filename, record_cache)
                    except (ValueError, KeyError, IndexError) as exc:
                        rejected.append({'member': member.filename, 'reason': str(exc)})
                        continue
                    current = set(rows)
                    for rid in sorted(current - previous):
                        events.append((generated, rid, True))
                        catalogue[rid] = rows[rid]
                    for rid in sorted(previous - current):
                        events.append((generated, rid, False))
                    previous = current
                    reports.append((generated, member.filename, len(current)))
            folder.mkdir(parents=True, exist_ok=True)
            artifacts = []
            frames = {
                'changes': pd.DataFrame(events, columns=['generated_nem', 'row_id', 'present']),
                'rows': pd.DataFrame([{'row_id': k, 'table': v['table'], 'version': v['version'],
                                      'fields_json': json.dumps(v['fields'], sort_keys=True)} for k, v in catalogue.items()]),
                'reports': pd.DataFrame(reports, columns=['generated_nem', 'member', 'distinct_rows']),
            }
            for key, frame in frames.items():
                p = store.parquet(folder / (key + '.parquet'), frame)
                artifacts.append({'path': str(p.relative_to(store.root)), 'sha256': digest(p)})
            meta = {'url': url, 'raw_sha256': digest(scratch), 'raw_bytes': written,
                    'artifacts': artifacts, 'reports': len(reports), 'rejected': rejected, 'unique_rows': len(catalogue),
                    'parser_contract': 'lossless-snapshot-change-v1', 'parser_code_sha256':digest(__file__),
                    'claim': 'Original generation vintage; historical receipt unverified'}
        store.json(folder / 'manifest.json', meta)
        store.complete(ident, fp, folder / 'manifest.json')
        store.scratch_delete(scratch)
        print(name, len(reports), 'snapshots', flush=True)
    return audit_nos(c)


def audit_nos(c):
    from .validation import folds
    paths = sorted((c['_run'] / 'nos/weeks').glob('*/reports.parquet'))
    if not paths:
        raise ValueError('No parsed snapshots')
    reports = pd.concat([pd.read_parquet(p) for p in paths]).drop_duplicates('generated_nem').sort_values('generated_nem')
    available = pd.DatetimeIndex(reports.generated_nem) + pd.Timedelta(minutes=30)
    calendar = pd.DataFrame({'origin': pd.date_range(c['start'], c['end'], freq='30min', inclusive='left')})
    calendar = pd.merge_asof(calendar, pd.DataFrame({'available_nem': available}), left_on='origin', right_on='available_nem')
    calendar['fresh'] = calendar.origin.sub(calendar.available_nem).le(pd.Timedelta(minutes=90))
    cells = []
    for fold in folds(c):
        if fold.protocol != 'rolling':
            continue
        partitions = {}
        for label, (a, b) in zip(['train', 'select', 'calibrate', 'alert', 'evaluate'], fold.bounds()):
            # Matched-history NOS training begins when the archive starts; controls
            # must be refitted on this same history, not the longer calendar history.
            fitted_start = max(a, available.min().ceil('D')) if label == 'train' else a
            block = calendar[calendar.origin.ge(fitted_start) & calendar.origin.lt(b)]
            partitions[label] = {'coverage': float(block.fresh.mean()),
                                 'fitted_start': fitted_start,
                                 'covered_days': int(block.loc[block.fresh, 'origin'].dt.normalize().nunique())}
        eligible = all(p['coverage'] >= .8 for p in partitions.values()) and partitions['train']['covered_days'] >= 90
        cells.append({'fold': fold.name, 'eligible': eligible, 'partitions': partitions})
    result = {'snapshots': len(reports), 'first_generated': reports.generated_nem.min(),
              'last_generated': reports.generated_nem.max(), 'folds': cells,
              'eligible_folds': sum(x['eligible'] for x in cells),
              'historical_gate': sum(x['eligible'] for x in cells) >= 4,
              'claim': 'Generation +30 min assumption; not actual receipt; all scheduled training origins in coverage denominator'}
    Store(c).parquet(c['_run'] / 'nos/coverage.parquet', calendar)
    Store(c).json(c['_run'] / 'nos/coverage_audit.json', result)
    return result
