"""Bounded public-data inventory and immutable original report acquisition."""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import time
import zipfile
from pathlib import Path
from functools import lru_cache
from urllib.parse import urljoin

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup

from nemic.common import session
from nemic.experiments.core import ROOT, digest, fingerprint
from .tracking import Ledger, atomic, now

PRODUCTS = {'stpasa':'Short_Term_PASA_Reports', 'pdpasa':'PDPASA', 'mtpasa':'MTPASA_DUIDAvailability'}
REGIONS = ('NSW1','QLD1','VIC1','SA1','TAS1')
PARSER_VERSION = 'original-reports-v3.1-near-term-mt'
FIELDS = {'DEMAND10':'demand10','DEMAND50':'demand50','DEMAND90':'demand90',
          'SS_WIND_UIGF':'wind_uigf','SS_SOLAR_UIGF':'solar_uigf',
          'SS_WIND_CAPACITY':'wind_constrained','SS_SOLAR_CAPACITY':'solar_constrained'}


@lru_cache(maxsize=50000)
def nem_time(value):
    t=pd.Timestamp(value)
    return t.tz_localize('Australia/Brisbane') if t.tzinfo is None else t.tz_convert('Australia/Brisbane')


def listing(url):
    r=session().get(url,timeout=(15,60));r.raise_for_status()
    return sorted(set(urljoin(url,a['href']) for a in BeautifulSoup(r.text,'html.parser').find_all('a',href=True)
                      if a['href'].lower().endswith('.zip')))


def inventory(ledger):
    ident='inventory'
    with ledger.job(ident) as (artifacts, checkpoint):
        rows=[]
        for product,folder in PRODUCTS.items():
            for scope in ('CURRENT','ARCHIVE'):
                url=f'https://www.nemweb.com.au/Reports/{scope}/{folder}/'
                try:
                    urls=listing(url)
                    rows.append(dict(product=product,scope=scope,url=url,urls=urls,count=len(urls),status='available'))
                except Exception as exc:
                    rows.append(dict(product=product,scope=scope,url=url,status='unavailable',reason=str(exc)))
                checkpoint({'source':product,'scope':scope})
        local=[]
        for c in ledger.c['connectors']:
            paths=sorted((ROOT/'data'/c['study']/'months').glob('*/constraint_features_30min.parquet'))
            local.append(dict(connector=c['name'],network_months=len(paths),first=paths[0].parent.name if paths else None,last=paths[-1].parent.name if paths else None))
        payload=dict(asof=now(),sources=rows,local=local,claim='Listing inventory only; existence does not establish historical interval or publication completeness')
        out=ledger.data/'inventory.json';atomic(out,json.dumps(payload,indent=2));artifacts.append(out)
    return payload


def read_mms(raw):
    """Yield header-specific dictionaries; retain report generation as evidence."""
    headers={}; generated=None
    for row in csv.reader(io.TextIOWrapper(raw,encoding='utf-8-sig',errors='strict')):
        if not row:continue
        if row[0]=='C' and len(row)>6 and re.match(r'\d{4}/\d{2}/\d{2}',row[5]):
            generated=nem_time(row[5]+' '+row[6])
        elif row[0]=='I':headers[tuple(row[1:4])]=row[4:]
        elif row[0]=='D' and tuple(row[1:4]) in headers:
            yield row[1],row[2],row[3],dict(zip(headers[tuple(row[1:4])],row[4:])),generated


def parse_pasa(raw, product, source_hash, retrieved_at):
    records=[]
    for dataset,table,version,row,generated in read_mms(raw):
        if table not in ('REGIONSOLUTION','REGIONSOLN') or row.get('REGIONID') not in REGIONS:continue
        if row.get('RUNTYPE','LOR')!='LOR':continue
        if row.get('STUDYREGIONID','') not in ('','ALL'):continue
        if generated is None:raise ValueError('Original report generation timestamp required; monthly extracts need a separate provenance track')
        delivery=nem_time(row['INTERVAL_DATETIME']); nominal=nem_time(row['RUN_DATETIME'])
        common=dict(product=product,run_id=str(nominal),nominal_run=nominal,available_at=generated,
                    retrieved_at=pd.Timestamp(retrieved_at),delivery=delivery,region=row['REGIONID'],
                    source_hash=source_hash,provenance='report_generated_proxy',schema_version=version)
        for field,variable in FIELDS.items():
            alias=field.replace('_CAPACITY','_CLEARED')
            value=row.get(field) or row.get(alias)
            if value in ('',None):continue
            if alias!=field and row.get(field) and row.get(alias) and not np.isclose(float(row[field]),float(row[alias]),atol=.01):
                raise ValueError('Conflicting PASA CAPACITY/CLEARED aliases')
            records.append({**common,'variable':variable,'value':float(value),'units':'MW'})
    return pd.DataFrame(records)


def parse_mt(raw, source_hash, retrieved_at):
    rows=[];last_generated=None;day_limit=None
    for dataset,table,version,row,generated in read_mms(raw):
        if dataset!='MTPASA' or table!='DUIDAVAILABILITY':continue
        if generated is None:raise ValueError('Missing original MT PASA report timestamp')
        # Report contains years of daily forecasts; this campaign is seven-day.
        # Compare ISO-like date strings before allocating timestamp-rich rows.
        if generated!=last_generated:
            last_generated=generated;day_limit=(generated+pd.Timedelta(days=10)).strftime('%Y-%m-%d')
        if row['DAY'][:10].replace('/','-') > day_limit:continue
        rows.append(dict(product='mtpasa',run_id=row['PUBLISH_DATETIME'],available_at=generated,
            retrieved_at=pd.Timestamp(retrieved_at),day=nem_time(row['DAY']),region=row['REGIONID'],duid=row['DUID'],
            capacity_mw=pd.to_numeric(row.get('PASAAVAILABILITY'),errors='coerce'),
            unit_state=row.get('PASAUNITSTATE'),recall_hours=pd.to_numeric(row.get('PASARECALLTIME'),errors='coerce'),
            latest_offer=row.get('LATEST_OFFER_DATETIME'),carryover=row.get('CARRYOVERSTATUS'),
            source_hash=source_hash,provenance='report_generated_proxy',schema_version=version))
    return pd.DataFrame(rows)


def _members(z, limit, depth=0):
    if depth>1:raise ValueError('Archive nesting beyond supported original weekly report format')
    if sum(i.file_size for i in z.infolist())>limit:raise RuntimeError('Expanded archive exceeds configured cap')
    for member in z.infolist():
        if member.filename.lower().endswith('.csv'):
            with z.open(member) as raw:yield member.filename,raw
        elif member.filename.lower().endswith('.zip'):
            with z.open(member) as nested:
                with zipfile.ZipFile(io.BytesIO(nested.read())) as child:
                    yield from _members(child,limit,depth+1)


def acquire_report(ledger, product, url):
    if product not in PRODUCTS or not url.startswith('https://www.nemweb.com.au/Reports/'):
        raise ValueError('Report URL outside source allowlist')
    key=fingerprint(url);ident=f'acquire/{product}/{key[:16]}'
    out=ledger.data/'sources'/product/(key+'.parquet');meta=out.with_suffix('.json')
    if out.exists() and meta.exists():
        cached=json.loads(meta.read_text())
        if cached.get('parser_version')==PARSER_VERSION and cached.get('parsed_sha256')==digest(out):
            archive=ledger.data/'raw'/product/(key+'.zip')
            if archive.exists() and digest(archive)==cached.get('raw_sha256'):
                ledger.record(ident,'completed','Verified reusable source parser contract',[archive,out,meta])
                return out
    if ledger.valid(ident):return out
    with ledger.job(ident,acceptance='Downloaded source hash and parsed rows verified') as (artifacts,checkpoint):
        cap=ledger.c['limits']['file_bytes'];expanded=ledger.c['limits']['expanded_bytes']
        used=sum(p.stat().st_size for root in (ledger.data,ledger.root) for p in root.rglob('*') if p.is_file())
        if used+cap+expanded>ledger.c['limits']['additional_bytes'] or shutil.disk_usage(ledger.data).free-cap-expanded<ledger.c['limits']['min_free_bytes']:
            raise RuntimeError('Campaign storage or free-space reserve reached')
        archive=ledger.data/'raw'/product/(key+'.zip');archive.parent.mkdir(parents=True,exist_ok=True)
        retrieved=now()
        if not archive.exists():
            temporary=archive.with_suffix('.part');size=0
            with session().get(url,stream=True,timeout=(20,120)) as response:
                response.raise_for_status()
                if int(response.headers.get('Content-Length',0))>cap:raise RuntimeError('Archive exceeds download cap')
                with temporary.open('wb') as handle:
                    for chunk in response.iter_content(1024*1024):
                        size+=len(chunk)
                        if size>cap:raise RuntimeError('Download cap exceeded')
                        handle.write(chunk)
                        checkpoint({'bytes':size,'url':url})
            temporary.replace(archive)
        import pyarrow as pa
        import pyarrow.parquet as pq
        sha=digest(archive);members=[];writer=None;rows=0;first=None;last=None
        out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(archive) as z:
                for name,raw in _members(z,expanded):
                    f=parse_mt(raw,sha,retrieved) if product=='mtpasa' else parse_pasa(raw,product,sha,retrieved)
                    if not f.empty:
                        f=f.drop_duplicates();table=pa.Table.from_pandas(f,preserve_index=False)
                        if writer is None:writer=pq.ParquetWriter(temp,table.schema,compression='zstd')
                        else:table=table.cast(writer.schema)
                        writer.write_table(table);rows+=len(f)
                        first=min(first,f.available_at.min()) if first is not None else f.available_at.min()
                        last=max(last,f.available_at.max()) if last is not None else f.available_at.max()
                    members.append(name);checkpoint({'members':len(members),'rows':rows})
        finally:
            if writer:writer.close()
        if not rows:raise ValueError('No eligible rows; inspect schema and scenario before relaxing parser')
        temp.replace(out)
        atomic(meta,json.dumps(dict(url=url,raw_sha256=sha,parsed_sha256=digest(out),rows=rows,members=members,
                    retrieved_at=retrieved,available_min=str(first),available_max=str(last),parser_version=PARSER_VERSION,
                    interpretation='Original report generation is a publication proxy; not actual historical receipt'),indent=2))
        artifacts.extend([archive,out,meta])
    return out


def acquire(ledger, scope='CURRENT', limit=1):
    inv=json.loads((ledger.data/'inventory.json').read_text())
    acquired=[];errors=[]
    for source in inv['sources']:
        if source['scope']!=scope or source['status']!='available':continue
        urls=source['urls']
        if scope=='ARCHIVE':
            # Preserve the entire bundle for provenance; choose bundles whose label
            # intersects the requested study plus one-month boundary allowance.
            lo=(pd.Timestamp(ledger.c['start'])-pd.Timedelta(days=32)).strftime('%Y%m%d')
            hi=(pd.Timestamp(ledger.c['end'])+pd.Timedelta(days=7)).strftime('%Y%m%d')
            urls=[u for u in urls if (m:=re.search(r'_(\d{8})\.zip',u)) and lo<=m[1]<=hi]
        for url in urls[-limit:] if limit else urls:
            try:acquired.append(str(acquire_report(ledger,source['product'],url)))
            except Exception as exc:errors.append(dict(product=source['product'],url=url,error=str(exc)))
    coverage=coverage_audit(ledger)
    summary=ledger.data/'acquisition_summary.json'
    atomic(summary,json.dumps(dict(scope=scope,acquired=acquired,errors=errors,coverage=coverage),indent=2))
    # A few current samples are never equivalent to the historical acquisition stage.
    ledger.record('acquisition','completed' if coverage['historical_pasa_days']>=130 and coverage['historical_mt_days']>=130 else 'ready',
                  'Historical coverage sufficient for pilot' if coverage['historical_pasa_days']>=130 and coverage['historical_mt_days']>=130 else 'Acquisition partial; further historical backfill required before training',
                  [summary] if coverage['historical_pasa_days']>=130 and coverage['historical_mt_days']>=130 else [])
    return summary


def coverage_audit(ledger):
    rows=[];days={'stpasa':set(),'pdpasa':set(),'mtpasa':set()}
    lo=nem_time(ledger.c['start']);hi=nem_time(ledger.c['end'])
    for product in PRODUCTS:
        for p in sorted((ledger.data/'sources'/product).glob('*.parquet')):
            f=pd.read_parquet(p,columns=['available_at'])
            valid=f.available_at.ge(lo)&f.available_at.lt(hi)
            days[product].update(str(t.date()) for t in f.loc[valid,'available_at'].dt.normalize().unique())
            rows.append(dict(product=product,path=str(p.relative_to(ROOT)),rows=len(f),first_available=str(f.available_at.min()),last_available=str(f.available_at.max())))
    result=dict(partitions=rows,historical_pasa_days=len(days['stpasa']&days['pdpasa']),historical_mt_days=len(days['mtpasa']),
                historical_pasa_dates=sorted(days['stpasa']&days['pdpasa']),historical_mt_dates=sorted(days['mtpasa']),
                note='Day counts are necessary only; per-origin/lead and regional coverage still required')
    atomic(ledger.data/'coverage.json',json.dumps(result,indent=2));return result
