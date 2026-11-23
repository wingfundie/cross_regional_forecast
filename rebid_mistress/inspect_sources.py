"""Small development/source audit command; no modelling or inference."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rebid_mistress.core import *

SOURCES={
 'offers': 'https://nemweb.com.au/Reports/CURRENT/Next_Day_Offer_Energy_SPARSE/PUBLIC_NEXT_DAY_OFFER_ENERGY_SPARSE_20261010_0000000542258391.zip',
 'bidmove': 'https://nemweb.com.au/Reports/CURRENT/Bidmove_Complete/PUBLIC_BIDMOVE_COMPLETE_20261010_0000000542258387.zip',
 'dispatch': 'https://nemweb.com.au/Reports/CURRENT/Next_Day_Dispatch/PUBLIC_NEXT_DAY_DISPATCH_20261010_0000000542254634.zip',
 'predispatch': 'https://nemweb.com.au/Reports/CURRENT/Next_Day_PreDispatch/PUBLIC_NEXT_DAY_PREDISPATCH_20261010_0000000542258398.zip',
 'prices':'https://nemweb.com.au/Reports/CURRENT/Public_Prices/PUBLIC_PRICES_202610100000_20261011040512.zip',
 'signal':'https://nemweb.com.au/Reports/CURRENT/DispatchIS_Reports/PUBLIC_DISPATCHIS_202610100720_0000000542102384.zip'
}
if __name__=='__main__':
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:paths=list(pool.map(lambda kv:download(kv[1],kv[0]+'.zip'),SOURCES.items()))
    for name,p in zip(SOURCES,paths):
        seen=set();rows=[]
        for r in native_rows(p):
            key=r['_table']+'|'+r['_version']
            if key not in seen:seen.add(key);rows.append(r)
        write_json(STATE/(name+'_schemas.json'),rows)
        print(name,[(r['_table'],r['_version']) for r in rows])
    reg='https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/participate-in-the-market/registration'
    print('REGISTRATION', [u for u in links(reg) if 'xls' in u.lower()])
