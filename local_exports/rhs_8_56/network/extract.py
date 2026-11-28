"""Stream existing AEMO monthly archives; retain only four named, non-intervention rows."""
from pathlib import Path
from zipfile import ZipFile
import csv
import hashlib
import io
import json
import re
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
IDS=['N>>NIL_85_86_S','V^^N_NIL_1','N::Q_NIL_KC','DATASNAP_TE_967_1']
MONTHS=['202509','202510','202511','202512','202601','202602']

def extract(month):
    path=next((ROOT/'data/line_outage_risk_v1/raw/supplements').glob(f'*DISPATCHCONSTRAINT*{month}*'))
    pat=re.compile(rb',1,(?:'+b'|'.join(re.escape(k.encode()) for k in IDS)+rb'),')
    with ZipFile(path) as z,z.open(z.namelist()[0]) as f:
        header=next(csv.reader([f.readline().decode()]))
        fields=next(csv.reader([f.readline().decode()]))
        rows=[];tail=b''
        while chunk:=f.read(8*1024**2):
            chunk=tail+chunk
            end=chunk.rfind(b'\n')+1
            tail=chunk[end:];chunk=chunk[:end]
            for m in pat.finditer(chunk):
                lo=chunk.rfind(b'\n',0,m.start())+1;hi=chunk.find(b'\n',m.end())
                rows.append(chunk[lo:hi].decode())
    d=pd.DataFrame(csv.reader(rows),columns=fields)
    d=d[d.INTERVENTION.eq('0')].loc[:,['SETTLEMENTDATE','CONSTRAINTID','GENCONID_EFFECTIVEDATE','GENCONID_VERSIONNO','RHS','LHS','MARGINALVALUE']]
    d['released']=str(pd.Timestamp(' '.join(header[5:7])))
    d.to_parquet(OUT/f'{month}.parquet',index=False)
    with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(month=month,sha256=digest,original_header=header,rows=len(d),available=d.released.iloc[0],source=str(path.relative_to(ROOT)))

if __name__=='__main__':
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(3) as pool: log=list(pool.map(extract,MONTHS))
    (OUT/'archive_sources.json').write_text(json.dumps(log,indent=2))
