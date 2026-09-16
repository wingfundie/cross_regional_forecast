"""Cached NEMWEB downloads and lossless table extraction."""
import csv, io, zipfile, hashlib, json, re
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from .common import *

TABLES = ['DISPATCHINTERCONNECTORRES', 'DISPATCHREGIONSUM', 'DISPATCHPRICE', 'ROOFTOP_PV_ACTUAL']
IDENTITY = {
    ('DISPATCH','INTERCONNECTORRES'): TABLES[0],
    ('DISPATCH','REGIONSUM'): TABLES[1],
    ('DISPATCH','PRICE'): TABLES[2],
    ('ROOFTOP','ACTUAL'): TABLES[3],
    ('PREDISPATCH','INTERCONNECTORRES'): 'PREDISPATCHINTERCONNECTORRES',
    ('PREDISPATCH','INTERCONNECTOR_SOLN'): 'PREDISPATCHINTERCONNECTORRES',
    ('NETWORK','OUTAGEDETAIL'): 'NETWORK_OUTAGEDETAIL',
    ('NETWORK','OUTAGECONSTRAINTSET'): 'NETWORK_OUTAGECONSTRAINTSET',
}

def archive_dir(month):
    return f'https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{month.year}/MMSDM_{month.year}_{month.month:02d}/MMSDM_Historical_Data_SQLLoader/DATA/'

def is_table(url, table):
    name = unquote(url.split('/')[-1])
    return ('#'+table+'#' in name or bool(re.match(r'PUBLIC_DVD_'+re.escape(table)+r'_(?:D_)?\d{12}\.zip$',name)))

def download(url):
    filename = unquote(url.split('/')[-1])
    path = RAW / filename
    if not path.exists():
        r = get(url)
        tmp = path.with_suffix('.partial')
        tmp.write_bytes(r.content)
        # Reject server error pages before making a cached file authoritative.
        with zipfile.ZipFile(tmp) as z:
            if not z.namelist(): raise ValueError('Empty archive: '+url)
        tmp.replace(path)
    record = dict(url=url, file=filename, bytes=path.stat().st_size,
                  sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    dump(DATA/'manifest_records'/f'{filename}.json', record)
    return path

def members(blob):
    with zipfile.ZipFile(blob) as z:
        for name in z.namelist():
            if name.lower().endswith('.zip'):
                yield from members(io.BytesIO(z.read(name)))
            elif name.lower().endswith('.csv'):
                yield z.read(name)

def extract(path, wanted=None):
    wanted = set(wanted or TABLES)
    buckets, schemas = {}, {}
    prefixes=tuple(kind+','+a+','+b+',' for (a,b),t in IDENTITY.items() if t in wanted for kind in ['I','D'])
    for content in members(path):
        # A daily report may contain many unrelated constraint rows. Keep only
        # requested table records, preserving each table version's own schema.
        decoded=content.decode('utf-8-sig')
        first=next(csv.reader([decoded.splitlines()[0]]))
        issued=first[5]+' '+first[6] if len(first)>6 and first[2]=='PREDISPATCHIS' else ''
        relevant=(line for line in io.StringIO(decoded) if line.startswith(prefixes))
        for row in csv.reader(relevant):
            if len(row)<4 or row[0] not in ('I','D'): continue
            table = IDENTITY.get((row[1],row[2]))
            if table is None:
                table = row[2] if row[2] in wanted else row[1]+'_'+row[2]
            if table not in wanted: continue
            key = (table,row[3])
            if row[0]=='I': schemas[key] = row[4:]+(['ISSUED_AT'] if table=='PREDISPATCHINTERCONNECTORRES' else [])
            elif key in schemas:
                buckets.setdefault(key,[]).append(row[4:]+([issued] if table=='PREDISPATCHINTERCONNECTORRES' else []))
    output = {}
    for key, rows in buckets.items():
        n = len(schemas[key])
        df = pd.DataFrame([r[:n]+['']*max(0,n-len(r)) for r in rows], columns=schemas[key])
        output.setdefault(key[0],[]).append(df)
    return {k:pd.concat(v,ignore_index=True) for k,v in output.items()}

def process_url(url, wanted=None):
    path = download(url)
    tag = path.stem
    done = DATA/'extracted'/f'{tag}.json'
    if done.exists(): return json.loads(done.read_text())
    frames = extract(path, wanted)
    info = {}
    for table, df in frames.items():
        out = DATA/'tables'/table/f'{tag}.parquet'
        out.parent.mkdir(parents=True,exist_ok=True)
        df.to_parquet(out,index=False,compression='zstd')
        info[table] = {'rows':len(df),'columns':list(df.columns)}
    dump(done,info)
    print('EXTRACT',path.name, {k:v['rows'] for k,v in info.items()},flush=True)
    return info

def run():
    # Monthly archive lag is covered by daily originals for the latest month.
    months = pd.date_range('2023-09-01','2026-07-01',freq='MS')
    urls=[]
    availability=[]
    for m in months:
        found=links(archive_dir(m))
        selected=[u for u in found if any(is_table(u,t) for t in TABLES)]
        availability.append({'month':str(m.date()),'tables':{t:sum(is_table(u,t) for u in selected) for t in TABLES}})
        urls.extend(selected)
    for folder in ['DispatchIS_Reports','ROOFTOP_PV/ACTUAL']:
        found=links('https://nemweb.com.au/Reports/ARCHIVE/'+folder+'/')
        selected=[u for u in found if u.lower().endswith('.zip') and ('202608' in u or '20260901' in u or (folder.startswith('ROOFTOP') and '20260730' in u))]
        urls.extend(selected)
        availability.append({'daily_folder':folder,'files':len(selected)})
    current=links('https://nemweb.com.au/Reports/CURRENT/ROOFTOP_PV/ACTUAL/')
    urls.extend(u for u in current if 'MEASUREMENT' in u and any(d in u for d in ['20260828','20260829','20260830','20260831','20260901']) and u.endswith('.zip'))
    dump(DATA/'availability.json',availability)
    dump(DATA/'download_plan.json',urls)
    print('DOWNLOAD PLAN',len(urls),'archives',flush=True)
    failures=[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(process_url,u):u for u in urls}
        for f in as_completed(pending):
            try:f.result()
            except Exception as e:
                failures.append({'url':pending[f],'error':str(e)})
                print('FAILED',pending[f],str(e),flush=True)
    records=[json.loads(p.read_text()) for p in (DATA/'manifest_records').glob('*.json')]
    dump(DATA/'manifest.json',records)
    dump(DATA/'download_failures.json',failures)
    if failures: raise RuntimeError(f'{len(failures)} downloads/extractions failed; rerun resumes safely')
    print('INGEST COMPLETE',len(records),'archives',sum(x['bytes'] for x in records),'bytes',flush=True)

if __name__=='__main__':run()
