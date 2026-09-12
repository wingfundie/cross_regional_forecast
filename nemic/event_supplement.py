"""Recover a demonstrated MMS archive gap from scoped next-day dispatch ZIP members."""
import csv
import io
import json
import zipfile
import hashlib
import pandas as pd
from .event_atlas import settings, log, guard, save, digest
from .common import session


class RangeReader(io.RawIOBase):
    def __init__(self,url,c):
        self.url=url;self.c=c;self.pos=0;self.client=session();self.reads=[]
        r=self.client.head(url,timeout=45);r.raise_for_status();self.size=int(r.headers['Content-Length'])
    def readable(self):return True
    def seekable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        return self.pos
    def read(self,n=-1):
        n=self.size-self.pos if n<0 else min(n,self.size-self.pos)
        if n<=0:return b''
        if n>600_000_000:raise RuntimeError('Supplement range cap')
        guard(self.c,n)
        with self.client.get(self.url,headers={'Range':f'bytes={self.pos}-{self.pos+n-1}'},stream=True,timeout=(20,90)) as r:
            if r.status_code!=206:raise RuntimeError('Range request unsupported; whole-archive transfer refused')
            data=r.content
        if len(data)!=n:raise RuntimeError('Incomplete range response')
        self.reads.append({'offset':self.pos,'bytes':n,'sha256':hashlib.sha256(data).hexdigest()});self.pos+=n
        return data


def run(c):
    root=c['root'];month='2025-09';target=root/'evidence'/month/'DISPATCHLOAD.parquet'
    f=pd.read_parquet(target)
    e=pd.read_parquet(root/'event_catalogue.parquet')
    cases=e[e.selected & e.time.dt.strftime('%Y-%m-%d').eq('2025-09-30')]
    wanted=set()
    for t in cases.time:wanted.update(pd.date_range(t-pd.Timedelta(hours=2),t+pd.Timedelta(hours=2),freq='5min'))
    if wanted.issubset(set(pd.to_datetime(f.SETTLEMENTDATE))):print('Supplement already complete',flush=True);return
    details=pd.read_parquet(c['standing']/'DUDETAILSUMMARY.parquet')
    deps=json.loads((c['standing']/'dependencies.json').read_text())
    ids=set(deps['duids'])|set(details.loc[details.REGIONID.isin(c['regions']),'DUID'])
    wanted_str={t.strftime('%Y/%m/%d %H:%M:%S') for t in wanted};rows=[]
    for parent_date in ['20250901','20251001']:
        url=f'https://nemweb.com.au/Reports/ARCHIVE/Next_Day_Dispatch/PUBLIC_NEXT_DAY_DISPATCH_{parent_date}.zip'
        reader=RangeReader(url,c)
        with zipfile.ZipFile(reader) as outer:
            names=outer.namelist()
            selected=[n for n in names if '20250930' in n or '20251001' in n]
            print('SUPPLEMENT MEMBERS',parent_date,selected,flush=True)
            for name in selected:
                content=outer.read(name)
                log(c,{'kind':'supplement_member','url':url,'member':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),
                       'scope':'Only the missing 2025-09-30 event window and required DUIDs'})
                if name.lower().endswith('.zip'):
                    inner=zipfile.ZipFile(io.BytesIO(content))
                    sources=[inner.open(m) for m in inner.namelist() if m.lower().endswith('.csv')]
                else:sources=[io.BytesIO(content)]
                for raw in sources:
                    schema=None;eligible=False
                    for row in csv.reader(io.TextIOWrapper(raw,encoding='utf-8-sig')):
                        if not row:continue
                        if row[0]=='I':
                            schema=row[4:];eligible='DUID' in schema and 'TOTALCLEARED' in schema and 'SETTLEMENTDATE' in schema
                            continue
                        if row[0]!='D' or not eligible:continue
                        record=dict(zip(schema,row[4:]))
                        if record['SETTLEMENTDATE'] in wanted_str and record['DUID'] in ids:rows.append(record)
        log(c,{'kind':'supplement_ranges','url':url,'parent_bytes':reader.size,'ranges':reader.reads,'transferred_bytes':sum(x['bytes'] for x in reader.reads)})
    if not rows:
        log(c,{'kind':'unresolved_source_gap','month':month,'table':'DISPATCHLOAD','intervals':len(wanted),'attempt':'Next-day dispatch scoped archive members'})
        raise RuntimeError('Supplement did not contain missing event rows')
    new=pd.DataFrame(rows)
    # Direct next-day sources may omit the connection point. Recover only unique effective mappings.
    if 'CONNECTIONPOINTID' not in new:new['CONNECTIONPOINTID']=None
    details['start']=pd.to_datetime(details.START_DATE);details['end']=pd.to_datetime(details.END_DATE,errors='coerce')
    mapping={}
    for duid,g in details.groupby('DUID'):
        active=g[g.start.le(max(wanted))&(g.end.isna()|g.end.gt(min(wanted)))]
        points=active.CONNECTIONPOINTID.dropna().unique()
        if len(points)==1 and active.start.min()<=min(wanted):mapping[duid]=points[0]
    absent=new.CONNECTIONPOINTID.isna()|new.CONNECTIONPOINTID.eq('')
    new.loc[absent,'CONNECTIONPOINTID']=new.loc[absent,'DUID'].map(mapping)
    new=new.reindex(columns=f.columns,fill_value='')
    result=pd.concat([f,new],ignore_index=True).drop_duplicates();save(result,target)
    m=target.with_suffix('.json');metadata=json.loads(m.read_text());metadata.update(retained_rows=len(result),retained_sha256=digest(target),
        supplement='Scoped next-day dispatch member recovery; see source_manifest.jsonl')
    m.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    log(c,{'kind':'supplement_output','output':str(target),'sha256':digest(target),'retained_rows':len(result),
        'added_rows':len(new),'mapping':'Unique connection point over selected window when absent from source'})
    missing=wanted-set(pd.to_datetime(result.SETTLEMENTDATE))
    print('SUPPLEMENT ROWS',len(new),'remaining missing intervals',len(missing),flush=True)
    if missing:raise RuntimeError('Partial supplement coverage')


if __name__=='__main__':run(settings())
