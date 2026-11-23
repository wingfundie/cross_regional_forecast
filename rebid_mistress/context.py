"""Original public forecast and network context, with release proxies preserved."""
from concurrent.futures import ThreadPoolExecutor
from .core import *

def issued(path):
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:r=next(csv.reader([f.readline().decode('utf-8-sig')]))
    return pd.to_datetime(r[5]+' '+r[6])

def run():
    rows=[]
    for folder,prefix,table,lookback in [('P5_Reports','P5MIN','REGIONSOLUTION',2),('PredispatchIS_Reports','PREDISPATCHIS','REGION_SOLUTION',6)]:
        candidates=[]
        for u in links('https://nemweb.com.au/Reports/CURRENT/'+folder+'/'):
            m=re.search(prefix+r'_(\d{12})_',u)
            if m and SIGNAL-pd.Timedelta(hours=lookback)<=pd.to_datetime(m[1],format='%Y%m%d%H%M')<=SIGNAL+pd.Timedelta(minutes=10):candidates.append(u)
        with ThreadPoolExecutor(max_workers=4) as pool:paths=list(pool.map(download,candidates))
        for p in paths:
            for r in native_rows(p,{table}):
                if r.get('REGIONID') in CONFIG['regions']:
                    r['file_generated_at']=str(issued(p));r['source_file']=p.name;rows.append(r)
    save_table('forecast_context',pd.DataFrame(rows))
    notices=[]
    urls=links('https://nemweb.com.au/Reports/CURRENT/Market_Notice/')
    selected=[u for u in urls if '20261010.' in u or '20261011.' in u]
    with ThreadPoolExecutor(max_workers=3) as pool:paths=list(pool.map(download,selected))
    for p in paths:
        text=p.read_text(errors='replace')
        notices.append(dict(file=p.name,text=text,url=json.loads(p.with_suffix(p.suffix+'.json').read_text())['url']))
    write_json(STATE/'market_notices.json',notices)
    write_json(STATE/'context.json',dict(forecast_rows=len(rows),notice_files=len(notices)))

if __name__=='__main__':run()
