"""Recover original AEMO forecast vintages, not overwritten monthly snapshots."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from .common import *
from .ingest import process_url

def run():
    archive=links('https://nemweb.com.au/Reports/ARCHIVE/PredispatchIS_Reports/')
    selected=[]
    for u in archive:
        m=re.search(r'_(\d{8})_(\d{8})\.zip$',u)
        if m and m[2]>='20260301' and m[1]<='20260831': selected.append(u)
    current=links('https://nemweb.com.au/Reports/CURRENT/PredispatchIS_Reports/')
    selected.extend(u for u in current if re.search(r'_202608(?:30|31)\d{4}',u) and u.endswith('.zip'))
    dump(DATA/'aemo_download_plan.json',selected)
    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks={pool.submit(process_url,u,['PREDISPATCHINTERCONNECTORRES']):u for u in selected}
        for f in as_completed(tasks):f.result()
    print('AEMO ORIGINAL VINTAGES COMPLETE',len(selected),flush=True)

if __name__=='__main__':run()
