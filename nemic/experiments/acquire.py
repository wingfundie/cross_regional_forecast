"""Recover only declared DISPATCHLOAD months and relevant DUIDs, with bounded streaming."""
import csv
import io
import json
import os
import time
import zipfile
from urllib.parse import unquote,urlparse
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from .core import ROOT,Store,digest,fingerprint

KEEP=['SETTLEMENTDATE','DUID','INITIALMW','TOTALCLEARED','AVAILABILITY','RAMPUPRATE','RAMPDOWNRATE','INTERVENTION','RUNNO','LASTCHANGED']


def recovery_plan(c):
    files={};duids=set()
    for ic in c['connectors']:
        months=ROOT/'data'/ic['study']/'months'
        for p in sorted(months.glob('*/config.json')):
            cfg=json.loads(p.read_text())
            for f in cfg.get('files',[]):
                if f['table']=='DISPATCHLOAD':files[f['url']]={**f,'month':p.parent.name}
        for p in sorted(months.glob('*/unit_sensitivities.parquet')):
            duids.update(pd.read_parquet(p,columns=['DUID']).DUID.dropna().unique())
    return {'table_allowlist':['DISPATCHLOAD'],'columns':KEEP,'duids':sorted(duids),'files':sorted(files.values(),key=lambda x:x['month']),
            'reason':'Full-period unit-generation forecast and event evidence; no other MMSDM tables requested'}


def recover(c,limit=None):
    from nemic.common import session
    store=Store(c);plan=recovery_plan(c);store.json(store.root/'recovery_plan.json',plan)
    ledger=[];units=set(plan['duids']);started=time.monotonic()
    for entry in plan['files'][:limit]:
        if time.monotonic()-started>c['limits']['batch_hours']*3600:break
        out=store.root/'cache/dispatch_load'/f"{entry['month']}.parquet";meta=out.with_suffix('.json')
        ident='recover/'+entry['month'];fp=fingerprint([entry,plan['columns'],plan['duids']])
        if store.valid(ident,fp) and out.exists():ledger.append({'month':entry['month'],'status':'cached'});continue
        url=entry['url'];host=urlparse(url).hostname;name=unquote(urlparse(url).path.rsplit('/',1)[-1])
        if host!='nemweb.com.au' or '#DISPATCHLOAD#' not in name:raise ValueError('Source is outside DISPATCHLOAD allowlist')
        expected=entry['expected_bytes'];cap=c['limits']['file_bytes']
        if expected>cap:
            ledger.append({'month':entry['month'],'status':'unavailable','reason':'Declared archive exceeds file cap','bytes':expected});continue
        scratch=store.root/'scratch'/name;scratch.parent.mkdir(parents=True,exist_ok=True)
        record={'month':entry['month'],'url':url,'expected_bytes':expected,'columns':KEEP,'duid_count':len(units),'retrieved_at':pd.Timestamp.now(tz='UTC').isoformat()}
        try:
            with store.reserve(cap+c['limits']['expanded_bytes']):
                with session().get(url,stream=True,timeout=(20,180)) as response:
                    response.raise_for_status();length=int(response.headers.get('Content-Length',0))
                    if length>cap:raise RuntimeError('Actual archive exceeds file cap')
                    written=0
                    with scratch.open('wb') as f:
                        for chunk in response.iter_content(1024*1024):
                            written+=len(chunk)
                            if written>cap:raise RuntimeError('Streaming file-byte cap reached')
                            f.write(chunk)
                record.update(bytes=written,sha256=digest(scratch))
                out.parent.mkdir(parents=True,exist_ok=True);tmp=out.with_suffix('.tmp');writer=None;rows=0;members=[]
                try:
                    with zipfile.ZipFile(scratch) as z:
                        csvs=[x for x in z.infolist() if x.filename.lower().endswith('.csv')]
                        if sum(x.file_size for x in csvs)>c['limits']['expanded_bytes']:raise RuntimeError('Declared expanded members exceed batch cap')
                        for member in csvs:
                            members.append(member.filename)
                            with z.open(member) as raw:
                                text=io.TextIOWrapper(raw,encoding='utf-8-sig')
                                schema=None
                                for line in text:
                                    fields=next(csv.reader([line]))
                                    if fields and fields[0]=='I':schema=['record','dataset','table','version']+fields[4:];break
                                if schema is None or 'DUID' not in schema:continue
                                for chunk in pd.read_csv(text,names=schema,usecols=['record']+KEEP,dtype=str,chunksize=100000):
                                    f=chunk[chunk.record.eq('D')&chunk.DUID.isin(units)].drop(columns='record').copy()
                                    if f.empty:continue
                                    for col in ['SETTLEMENTDATE','LASTCHANGED']:f[col]=pd.to_datetime(f[col],errors='coerce')
                                    for col in KEEP[2:-1]:f[col]=pd.to_numeric(f[col],errors='coerce').astype('float32')
                                    table=pa.Table.from_pandas(f,preserve_index=False)
                                    if writer is None:writer=pq.ParquetWriter(tmp,table.schema,compression='zstd')
                                    writer.write_table(table);rows+=len(f)
                    if writer:writer.close();writer=None
                    if rows==0:raise RuntimeError('No eligible dispatch rows extracted')
                    check=pq.ParquetFile(tmp)
                    if check.metadata.num_rows!=rows:raise RuntimeError('Extracted row count mismatch')
                    check.close()
                    os.replace(tmp,out)
                finally:
                    if writer:writer.close()
                record.update(status='complete',rows=rows,members=members,output=str(out.relative_to(store.root)),output_sha256=digest(out))
            store.scratch_delete(scratch);record['raw_deleted']=True
            store.json(meta,record);store.complete(ident,fp,meta,{'data_hash':record['output_sha256']})
        except Exception as exc:
            import traceback
            record.update(status='unavailable',reason=repr(exc),traceback=traceback.format_exc())
            if scratch.exists():store.scratch_delete(scratch);record['partial_or_failed_raw_deleted']=True
        ledger.append(record);store.json(store.root/'recovery_status.json',ledger);print(entry['month'],record['status'],record.get('reason',''),flush=True)
    store.json(store.root/'recovery_status.json',ledger)
    return ledger
