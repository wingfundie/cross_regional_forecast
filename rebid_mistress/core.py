"""Local paths, native MMS reading and immutable-source provenance."""
from pathlib import Path
from datetime import datetime, timezone
import csv, io, json, hashlib, ssl, zipfile, re
from urllib.parse import urljoin
import certifi
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / 'config.json').read_text())
START, END, SIGNAL, SPIKE = [pd.Timestamp(CONFIG[x]) for x in ['start','end','signal','spike_interval']]
RAW = ROOT / 'data/raw'
TABLES = ROOT / 'data/tables'
RESULTS = ROOT / 'data/results'
STATE = ROOT / 'state'
REPORTS = ROOT / 'reports'

def init():
    for p in [RAW,TABLES,RESULTS,STATE,REPORTS]: p.mkdir(parents=True,exist_ok=True)

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,default=str,ensure_ascii=False),encoding='utf-8')

def session():
    s=requests.Session()
    if hasattr(ssl,'enum_certificates'):
        cert=ROOT/'cache/trust.pem';cert.parent.mkdir(exist_ok=True)
        if not cert.exists():
            extra=[ssl.DER_cert_to_PEM_cert(c) for store in ['ROOT','CA'] for c,enc,_ in ssl.enum_certificates(store) if enc=='x509_asn']
            cert.write_text(Path(certifi.where()).read_text()+'\n'+'\n'.join(extra))
        s.verify=str(cert)
    s.headers['User-Agent']='RebidMistress/1.0 (scoped public AEMO research)'
    return s

def download(url,name=None):
    init();p=RAW/(name or url.split('/')[-1].split('?')[0]);meta=p.with_suffix(p.suffix+'.json')
    if p.exists() and meta.exists():
        m=json.loads(meta.read_text())
        if m['url']==url and m['sha256']==sha(p):return p
    print('Acquire',url,flush=True)
    with session().get(url,timeout=(30,180),stream=True) as r:
        r.raise_for_status()
        temp=p.with_suffix(p.suffix+'.partial')
        with temp.open('wb') as f:
            for b in r.iter_content(1024*1024):f.write(b)
        temp.replace(p)
        write_json(meta,dict(url=url,sha256=sha(p),bytes=p.stat().st_size,retrieved_utc=datetime.now(timezone.utc).isoformat(),http_last_modified=r.headers.get('Last-Modified'),historical_receipt_time=None))
    return p

def links(url):
    r=session().get(url,timeout=90);r.raise_for_status()
    return [urljoin(url,h) for h in re.findall(r'href=[\"\x27]([^\"\x27]+)',r.text,re.I)]

def discover(folder,date):
    found=[u for u in links('https://nemweb.com.au/Reports/CURRENT/'+folder+'/') if date in u and u.lower().endswith('.zip')]
    if not found:raise FileNotFoundError(f'{folder}: {date} not published in current listing')
    return sorted(found)[-1]

def native_rows(path,wanted=None,duids=None):
    """CSV reader handles quoted commas/newlines; schema versions stay explicit."""
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.lower().endswith('.csv'):continue
            schemas={}
            with z.open(name) as raw,io.TextIOWrapper(raw,encoding='utf-8-sig',newline='') as f:
                for row in csv.reader(f):
                    if len(row)<4:continue
                    key=tuple(row[1:4])
                    if row[0]=='I':schemas[key]=row[4:];continue
                    if row[0]!='D' or key not in schemas or (wanted and key[1] not in wanted):continue
                    header=schemas[key]
                    if duids is not None and 'DUID' in header and row[4+header.index('DUID')] not in duids:continue
                    if len(row[4:])!=len(header):raise ValueError(f'Ragged native record {name} {key}')
                    record=dict(zip(header,row[4:]));record.update(_report=key[0],_table=key[1],_version=key[2],_member=name)
                    yield record

def save_table(name,df):
    init();df.to_parquet(TABLES/(name+'.parquet'),index=False)
    print(name,len(df),flush=True)

def load_table(name):return pd.read_parquet(TABLES/(name+'.parquet'))

def number(df,cols):
    for c in cols:
        if c in df:df[c]=pd.to_numeric(df[c],errors='coerce')
    return df

def times(df,cols):
    for c in cols:
        if c in df:df[c]=pd.to_datetime(df[c],errors='coerce')
    return df

def block(t):
    h=(pd.Timestamp(t)-pd.Timedelta(seconds=1)).hour
    return 'morning' if 4<=h<10 else 'daytime' if 10<=h<16 else 'evening' if 16<=h<22 else 'overnight'

def intervals():return pd.date_range(START+pd.Timedelta(minutes=5),END,freq='5min')
