import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nemic.common import links, get, RAW, dump, DATA
import zipfile, io, csv
from urllib.parse import unquote

base = 'https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/MMSDM_2026_07/MMSDM_Historical_Data_SQLLoader/DATA/'
items = links(base)
terms = ['DISPATCHINTERCONNECTORRES','DISPATCHREGIONSUM','DISPATCH_UNIT_SCADA','DUDETAIL','GENUNITS','DUALLOC','ROOFTOP','INTERCONNECTOR','PREDISPATCHINTERCONNECTOR','DISPATCHPRICE','CONSTRAINT','BIDPEROFFER']
selected = [u for u in items if any(t in u.split('/')[-1] for t in terms)]
dump(DATA/'source_inventory.json', selected)
for u in selected:
    print(u.split('/')[-1], flush=True)
for name in ['DISPATCHINTERCONNECTORRES','DISPATCHREGIONSUM','DUDETAIL','GENUNITS','DUALLOC','INTERCONNECTOR']:
    urls = [u for u in items if '#'+name+'#' in unquote(u.split('/')[-1])]
    if not urls:
        continue
    u = urls[0]
    p = RAW/u.split('/')[-1]
    if not p.exists(): p.write_bytes(get(u).content)
    with zipfile.ZipFile(p) as z:
        with z.open(z.namelist()[0]) as f:
            print('\nSCHEMA',name)
            for i in range(4): print(f.readline().decode('utf-8-sig').strip())
print('RECENT ARCHIVE', links('https://nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/')[:4])
