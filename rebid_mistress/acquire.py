"""Bounded AEMO acquisition, registry selection and native table extraction."""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from urllib.parse import unquote
import shutil
import numpy as np
from .core import *
from .inspect_sources import SOURCES

def inventory():
    # Reuse retained original AEMO registration archives, recording their hashes.
    frames={};sources=[]
    for name in ['GENUNITS','DUALLOC','DUDETAIL']:
        paths=sorted((ROOT.parent/'data/raw').glob('*'+name+'*'))
        paths=[p for p in paths if p.suffix=='.zip']
        if not paths:raise FileNotFoundError('Retained AEMO standing archive missing: '+name)
        p=paths[-1];dst=RAW/p.name
        if not dst.exists():shutil.copy2(p,dst)
        frames[name]=pd.DataFrame(native_rows(dst,{name}))
        sources.append(dict(table=name,retained_source=str(p),sha256=sha(dst),snapshot='2026-07',limitation='Historical effective registration; cross-checked against event bids/dispatch'))
    p=ROOT.parent/'data/constraint_qni_2y/standing/DUDETAILSUMMARY.parquet'
    d=pd.read_parquet(p).drop_duplicates()
    d=d[d.START_DATE.le('2026/10/10 04:00:00')].sort_values(['DUID','START_DATE','LASTCHANGED']).drop_duplicates('DUID',keep='last')
    d=d[d.END_DATE.gt('2026/10/10 04:00:00')&d.REGIONID.isin(CONFIG['regions'])].copy()
    sources.append(dict(table='DUDETAILSUMMARY',retained_source=str(p),sha256=sha(p),snapshot='2026-09-04',limitation='Later registrations/control changes require event cross-check'))
    g=frames['GENUNITS'].sort_values('LASTCHANGED').drop_duplicates('GENSETID',keep='last')
    a=frames['DUALLOC'];a=a[a.EFFECTIVEDATE.le('2026/10/10 04:00:00')].copy();number(a,['VERSIONNO'])
    a=a[a.EFFECTIVEDATE.eq(a.groupby('DUID').EFFECTIVEDATE.transform('max'))]
    a=a[a.VERSIONNO.eq(a.groupby('DUID').VERSIONNO.transform('max'))].drop_duplicates(['DUID','GENSETID']).merge(g[['GENSETID','CO2E_ENERGY_SOURCE']],on='GENSETID',how='left')
    fuels=a.groupby('DUID').CO2E_ENERGY_SOURCE.agg(lambda s:' | '.join(sorted(set(s.dropna())-{''})))
    d['fuel']=d.DUID.map(fuels).fillna('')
    d['technology']=d.fuel.map(lambda s:'coal' if s.lower() in ['black coal','brown coal'] else 'gas' if any(k in s.lower() for k in ['natural gas','coal seam methane','coal mine waste gas','biogas']) else '')
    d.loc[d.DISPATCHTYPE.eq('BIDIRECTIONAL')|d.fuel.str.contains('Battery',case=False),'technology']='battery'
    # Station-level pairing retains old separate battery LOAD DUIDs.
    battery_stations=set(d.loc[d.technology.eq('battery'),'STATIONID'])
    d.loc[d.STATIONID.isin(battery_stations)&d.DISPATCHTYPE.eq('LOAD'),'technology']='battery'
    detail=frames['DUDETAIL'];detail=detail[detail.EFFECTIVEDATE.le('2026/10/10 04:00:00')].copy();number(detail,['VERSIONNO','REGISTEREDCAPACITY','MAXSTORAGECAPACITY'])
    detail=detail.sort_values(['EFFECTIVEDATE','VERSIONNO','LASTCHANGED']).drop_duplicates('DUID',keep='last').set_index('DUID')
    d['registered_mw']=d.DUID.map(detail.REGISTEREDCAPACITY)
    d['storage_capacity_native']=d.DUID.map(detail.MAXSTORAGECAPACITY)
    save_table('registry_all',d)
    d=d[d.technology.ne('')].copy()
    d['plant']=d.STATIONID
    names={'MP':'Mount Piper','TALLAWAR':'Tallawarra','YALLOURN':'Yallourn','BAYSW':'Bayswater','ERARING':'Eraring','LOYYANGA':'Loy Yang A','LOYYB':'Loy Yang B','VP':'Vales Point','CALLIDE':'Callide B','CALLIDEC':'Callide C','G/STONE':'Gladstone','COLONGRA':'Colongra','TARONG':'Tarong','TARONGN':'Tarong North','STANWELL':'Stanwell','SWANBANK':'Swanbank E','BRAEMARA':'Braemar A','B2PS':'Braemar B','VPGS':'Valley Power','JEERA':'Jeeralang A','JEERB':'Jeeralang B','NEWPORT':'Newport','MORTLK':'Mortlake','AGLSOM':'Somerton','URANQ':'Uranquinty','DDPS1':'Darling Downs','KOGANCK':'Kogan Creek','MILLMERN':'Millmerran'}
    d['plant']=d.STATIONID.map(names).fillna(d.STATIONID)
    station_url='https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2026/MMSDM_2026_07/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23STATION%23FILE01%23202607010000.zip'
    stations=pd.DataFrame(native_rows(download(station_url),{'STATION'})).sort_values('LASTCHANGED').drop_duplicates('STATIONID',keep='last').set_index('STATIONID')
    unknown=d.plant.eq(d.STATIONID)
    d.loc[unknown,'plant']=d.loc[unknown,'STATIONID'].map(stations.STATIONNAME).replace('',np.nan).fillna(d.loc[unknown,'STATIONID'])
    d['controller']=d.PARTICIPANTID;d['owner']='Unverified';d['control_source']='AEMO registered participant; ultimate trading rights unresolved'
    # Only explicit, sourced corporate grouping. Remaining legal participants stay separate.
    maps={'TRUDW':'EnergyAustralia','TALL':'EnergyAustralia','YALLOURN':'EnergyAustralia','ECOGEN':'EnergyAustralia','MACQGEN':'AGL','LOYYANGA':'AGL','OERARING':'Origin','BORAL':'Origin','SNOWY':'Snowy Hydro','STANWELL':'Stanwell','CLEANCO':'CleanCo','CSENERGY':'CS Energy'}
    urls={'EnergyAustralia':'https://www.energyaustralia.com.au/about-us/what-we-do/generating-energy','AGL':'https://www.agl.com.au/about-agl/operations','Origin':'https://www.originenergy.com.au/about/who-we-are/what-we-do/generation/','Snowy Hydro':'https://www.snowyhydro.com.au/our-energy/generation/','Stanwell':'https://www.stanwell.com/our-energy-assets','CleanCo':'https://cleancoqueensland.com.au/our-portfolio/','CS Energy':'https://www.csenergy.com.au/what-we-do'}
    # Corporate owner labels do not claim that every PPA transfers dispatch rights.
    for participant,company in maps.items():
        mask=d.PARTICIPANTID.eq(participant);d.loc[mask,'controller']=company
        d.loc[mask,'control_source']=urls[company]+'; registered participant mapping'
    for plant,company in [('Somerton','AGL')]:
        mask=d.plant.eq(plant);d.loc[mask,'controller']=company;d.loc[mask,'control_source']=urls[company]
    for company in ['EnergyAustralia','AGL','Origin']:
        d.loc[d.controller.eq(company),'owner']=company
    d['registry_status']='Historical AEMO registry, checked against event accepted participant'
    save_table('inventory',d)
    write_json(STATE/'registry_sources.json',dict(sources=sources,registration_workbook_status='9 October workbook identified but direct download blocked by AEMO website; retained AEMO registration tables used',scope='All identifiable registered coal/gas/battery DUIDs; unregistered behind-meter assets not observable'))
    return d

def parse_file(name,wanted,duids=None):
    buckets=defaultdict(list)
    for r in native_rows(RAW/(name+'.zip'),wanted,duids):
        if r.get('BIDTYPE','ENERGY')!='ENERGY':continue
        buckets[r['_table']].append(r)
    for table,rows in buckets.items():save_table(name+'_'+(table or 'prices'),pd.DataFrame(rows))

def acquire():
    init()
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda kv:download(kv[1],kv[0]+'.zip'),SOURCES.items()))
    d=inventory();duids=set(d.DUID)
    for name,wanted in [('offers',{'BIDDAYOFFER','BIDOFFERPERIOD_SPARSE'}),('bidmove',{'BIDDAYOFFER_D','BIDPEROFFER_D'}),('dispatch',{'UNIT_SOLUTION','LOCAL_PRICE','OFFERTRK','CONSTRAINT'}),('predispatch',{'UNIT_SOLUTION','OFFERTRK'}),('prices',None),('signal',None)]:
        expected=TABLES/(name+'_'+({'offers':'BIDDAYOFFER','bidmove':'BIDPEROFFER_D','dispatch':'UNIT_SOLUTION','predispatch':'UNIT_SOLUTION','prices':'prices','signal':'PRICE'}[name])+'.parquet')
        if not expected.exists():parse_file(name,wanted,duids if name not in ['prices','signal'] else None)
    # Five-minute SCADA files are small; bounded to the exact day plus baseline observations.
    candidates=links('https://nemweb.com.au/Reports/CURRENT/Dispatch_SCADA/')
    chosen=[]
    for u in candidates:
        m=re.search(r'DISPATCHSCADA_(\d{12})_',u)
        if m and START<=pd.to_datetime(m[1],format='%Y%m%d%H%M')<=END+pd.Timedelta(minutes=5):chosen.append(u)
    if not (TABLES/'scada.parquet').exists():
        with ThreadPoolExecutor(max_workers=6) as pool:paths=list(pool.map(download,chosen))
        rows=[]
        for p in paths:rows.extend(native_rows(p,None,duids))
        save_table('scada',pd.DataFrame(rows))
    # Pre-signal short-horizon forecast vintages: two hours, plus one just after the event.
    candidates=links('https://nemweb.com.au/Reports/CURRENT/P5_Reports/')
    chosen=[]
    for u in candidates:
        m=re.search(r'P5MIN_(\d{12})_',u)
        if m and SIGNAL-pd.Timedelta(hours=2)<=pd.to_datetime(m[1],format='%Y%m%d%H%M')<=SIGNAL+pd.Timedelta(minutes=10):chosen.append(u)
    if not (TABLES/'p5min_energy.parquet').exists():
        with ThreadPoolExecutor(max_workers=4) as pool:paths=list(pool.map(download,chosen))
        rows=[]
        for p in paths:
            for r in native_rows(p):
                if r['_table']=='REGIONSOLUTION' and r.get('REGIONID') in CONFIG['regions']:
                    r['source_file']=p.name;rows.append(r)
        save_table('p5min_energy',pd.DataFrame(rows))
    write_json(STATE/'acquisition.json',dict(inventory_duids=len(d),scada_files=len([p for p in RAW.glob('*DISPATCHSCADA*.zip')]),sources=[json.loads(p.read_text()) for p in RAW.glob('*.json')]))
