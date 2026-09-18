"""Immutable prepared indexes for bounded-memory feature construction."""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from multiprocessing import get_context

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from nemic.experiments.core import ROOT, digest, fingerprint
from .sources import REGIONS
from .tracking import atomic

PASA_VARIABLES = ('demand10','demand50','demand90','wind_uigf','solar_uigf',
                  'wind_constrained','solar_constrained')
PASA_CONTRACT = 'pasa-wide-delivery-v1'


def recorded_hash(path):
    """Use the acquisition manifest hash without rereading immutable sources."""
    meta=path.with_suffix('.json')
    if meta.exists():
        payload=json.loads(meta.read_text(encoding='utf-8'))
        if payload.get('parsed_sha256'):return payload['parsed_sha256']
    return digest(path)


def source_manifest(ledger):
    files=[p for product in ('stpasa','pdpasa') for p in sorted((ledger.data/'sources'/product).glob('*.parquet'))]
    if not files:raise ValueError('Acquire PASA vintages before preparing indexes')
    hashes={str(p.relative_to(ROOT)):recorded_hash(p) for p in files}
    generation=fingerprint(dict(contract=PASA_CONTRACT,sources=hashes))
    return files,hashes,generation


def _wide(frame):
    frame=frame.copy();frame['feature']=frame.region.astype(str)+'__'+frame.variable.astype(str)
    keys=['product','run_id','available_at','delivery']
    wide=frame.pivot_table(index=keys,columns='feature',values='value',aggfunc='first').reset_index()
    columns=keys+[r+'__'+v for r in REGIONS for v in PASA_VARIABLES]
    return wide.reindex(columns=columns)


def _prepare_pasa_file(path,destination):
    """Stream one source parquet by coherent row group into atomic date shards."""
    tmp=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.tmp');tmp.mkdir(parents=True)
    writers={};counts={};minimum=None;maximum=None
    try:
        source=pq.ParquetFile(path);columns=['product','run_id','available_at','delivery','region','variable','value']
        for number in range(source.num_row_groups):
            wide=_wide(source.read_row_group(number,columns=columns).to_pandas())
            required=[r+'__'+v for r in REGIONS for v in ('demand50','wind_uigf','solar_uigf','wind_constrained','solar_constrained')]
            wide=wide.dropna(subset=required)
            if wide.empty:continue
            lo,hi=wide.available_at.min(),wide.available_at.max()
            minimum=lo if minimum is None else min(minimum,lo);maximum=hi if maximum is None else max(maximum,hi)
            for day,part in wide.groupby(wide.delivery.dt.strftime('%Y-%m-%d'),sort=False):
                table=pa.Table.from_pandas(part,preserve_index=False)
                if day not in writers:
                    writers[day]=pq.ParquetWriter(tmp/(day+'.parquet'),table.schema,compression='zstd');counts[day]=0
                writers[day].write_table(table);counts[day]+=len(part)
        for writer in writers.values():writer.close()
        writers.clear()
        manifest=dict(contract=PASA_CONTRACT,source_sha256=recorded_hash(path),source=str(path.relative_to(ROOT)),
                      rows=sum(counts.values()),dates=counts,available_min=str(minimum),available_max=str(maximum))
        atomic(tmp/'manifest.json',json.dumps(manifest,indent=2));destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():shutil.rmtree(destination)
        os.replace(tmp,destination);return manifest
    finally:
        for writer in writers.values():writer.close()
        if tmp.exists():shutil.rmtree(tmp,ignore_errors=True)


def _prepare_worker(path,destination):
    os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    return _prepare_pasa_file(Path(path),Path(destination))


def prepare_indexes(ledger,resume=True):
    """Build content-addressed PASA indexes and a date-to-piece catalog."""
    # Short physical names keep temporary paths below legacy Windows MAX_PATH;
    # the manifest retains the complete content hashes.
    files,hashes,generation=source_manifest(ledger);root=ledger.data/'prepared/ix'/generation[:16]
    final=root/'manifest.json';ident='prepare-indexes/'+generation
    if resume and final.exists():
        payload=json.loads(final.read_text(encoding='utf-8'))
        if payload.get('contract')==PASA_CONTRACT:return final
    started=time.monotonic();by_date={};source_results=[]
    with ledger.job(ident,acceptance='Immutable date-partitioned source indexes verified') as (artifacts,checkpoint):
        resolved=[];pending=[]
        for path in files:
            key=recorded_hash(path);destination=root/'p'/key[:16];part_manifest=destination/'manifest.json'
            if resume and part_manifest.exists():resolved.append((destination,json.loads(part_manifest.read_text(encoding='utf-8'))))
            else:pending.append((path,destination))
        for destination,result in resolved:
            source_results.append(result)
            for day in result['dates']:by_date.setdefault(day,[]).append(str((destination/(day+'.parquet')).relative_to(root)))
        completed=len(resolved)
        with ProcessPoolExecutor(max_workers=2,mp_context=get_context('spawn')) as pool:
            futures={pool.submit(_prepare_worker,str(path),str(destination)):destination for path,destination in pending}
            for future in as_completed(futures):
                destination=futures[future];result=future.result();source_results.append(result);completed+=1
                for day in result['dates']:by_date.setdefault(day,[]).append(str((destination/(day+'.parquet')).relative_to(root)))
                checkpoint(dict(completed_sources=completed,total_sources=len(files),dates=len(by_date),elapsed_seconds=time.monotonic()-started,
                                workers=2,rows=sum(x['rows'] for x in source_results)))
        for stale in (root/'p').glob('*.tmp'):
            if stale.parent.resolve()==(root/'p').resolve():shutil.rmtree(stale,ignore_errors=True)
        mins=[pd.Timestamp(x['available_min']) for x in source_results];maxs=[pd.Timestamp(x['available_max']) for x in source_results]
        payload=dict(contract=PASA_CONTRACT,generation=generation,source_hashes=hashes,available_min=str(min(mins)),
                     available_max=str(max(maxs)),dates=by_date,rows=sum(x['rows'] for x in source_results),sources=source_results)
        atomic(final,json.dumps(payload,indent=2));artifacts.append(final)
    return final
