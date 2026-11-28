"""Compact fixed-clock dispatch case extraction and pre-origin benchmarks."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import io,json,struct,sys,zlib
from zipfile import ZipFile
from lxml import etree
import numpy as np
import pandas as pd
import requests

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT/'local_exports/rhs_forward_feb26'))
import study as reader

POINTS='MW_AR_TX3 MVAR_AR_TX3 MVA_AR_86 MW_DP_99N MVA_BAN_9GL MORTLAKE_INERTIA APDLOAD_MVAR BU_SH1_LINE_220KV BL_PREVDI_TARGET MUSWELL_LOAD MW_JINDABYN GTOWN_FL_TIMER BAN_CB_C_STAT TAMWORTH_CAP1_STATUS TAMWORTH_CAP2_STATUS TAMWORTH_R1_STATUS'.split()
POINTS+=['ART_CB_F_STAT','STL_CB_B_STAT','MVA_ART_STL','PTWF_CNS_CB_STAT']
RATING='NRATCN_BANYS9GL'
UNITS=['BANGOWF1','GOONSF1','JEMALNG1','PARSF1','TARBESS1','SHPUMP']
PROGRAM=pd.read_csv(ROOT/'reports/rhs_replay/inventory/terms.csv')
QNI='N^^Q_NIL_MAXGEN'
FAR='X_NSW_FARNTH_LOAD_DS'
EQUATIONS={k:PROGRAM[PROGRAM.owner_id.eq(k)] for k in [QNI,FAR]}
LEAVES=pd.concat(EQUATIONS.values())
EXTRA_POINTS=set(LEAVES[LEAVES.spd_type.isin(['A','S'])].spd_id)
EXTRA_UNITS=set(LEAVES[LEAVES.spd_type.eq('T')].spd_id)

def qni(row):
    def value(k):return row.get(k,np.nan)
    groups={}
    far=sum(t.multiplier*(abs(value(t.spd_id)) if t.operation=='ABS' else value(t.spd_id)) for t in EQUATIONS[FAR].itertuples())
    top=EQUATIONS[QNI]
    for group,terms in top.dropna(subset=['group_term']).groupby('group_term'):
        vals=[t.multiplier*value(t.spd_id) for t in terms.itertuples()]
        groups[group]=np.max(vals) if terms.operation.eq('MAX').all() else sum(vals)
    return sum(t.multiplier*(1 if t.spd_type=='C' else groups[t.term_id] if t.spd_type=='G' else far if t.spd_type=='X' else value(t.spd_id)) for t in top[top.group_term.isna()].itertuples())

def capture(day):
    cached=OUT/(day.strftime('%Y%m%d')+'.csv')
    if cached.exists() and 'examined_corridor' in pd.read_csv(cached,nrows=0):return
    if cached.with_suffix('.excluded.txt').exists():return
    url=f'https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/{day:%Y}/NEMDE_{day:%Y_%m}/NEMDE_Market_Data/NEMDE_Files/NemSpdOutputs_{day:%Y%m%d}_loaded.zip'
    start,cat=reader.directory(url)
    picks=[e for e in cat if e.filename in {f'NEMSPDOutputs_{day:%Y%m%d}{j:03d}00.loaded' for j in range(73,79)}]
    if len(picks)!=6:
        cached.with_suffix('.excluded.txt').write_text(url+'\nIncomplete standard non-OCD half-hour.\n')
        return
    low=start+picks[0].header_offset
    high=start+cat[cat.index(picks[-1])+1].header_offset-1
    block,head=reader.fetch(url,f'{low}-{high}');assert head.startswith(f'bytes {low}-')
    rows=[]
    for e in picks:
        off=start+e.header_offset-low
        n,m=struct.unpack_from('<HH',block,off+26); pos=off+30+n+m
        raw=block[pos:pos+e.compress_size]
        if e.compress_type==8:raw=zlib.decompress(raw,-15)
        assert zlib.crc32(raw)==e.CRC
        if raw.startswith(b'PK'):
            with ZipFile(io.BytesIO(raw)) as arch:raw=arch.read(arch.namelist()[0])
        doc=etree.fromstring(raw); inp=doc.find('NemSpdInputs')
        p=inp.find('.//Period'); t=pd.Timestamp(p.get('PeriodID')).tz_localize(None)
        r=dict(end=t,url=url,member=e.filename,sha256=reader.sha(raw),modified=datetime(*e.date_time),intervention=inp.find('Case').get('Intervention'))
        for item in inp.iter('ScadaValues'):
            key=item.get('SpdID')
            if (key in POINTS or key in EXTRA_POINTS) and item.get('Can_Use_Value')=='True':r[key]=float(item.get('Value'))
        for trader in inp.iter('Trader'):
            if trader.get('TraderID') in UNITS or trader.get('TraderID') in EXTRA_UNITS:
                initial=trader.find('.//TraderInitialCondition[@InitialConditionID="InitialMW"]')
                if initial is not None:r[trader.get('TraderID')]=float(initial.get('Value'))
        for typ,key in [('EnteredValuePeriod',RATING),('EnteredValuePeriod','VRAT15_RCWE')]:
            entry=p.find(f'.//{typ}[@SpdID="{key}"]')
            if entry is not None:r[key]=float(entry.get('Value'))
        for tag in ['NSW1','VIC1']:
            reg=inp.find(f'.//Region[@RegionID="{tag}"]')
            if reg is not None:
                ini=reg.find('.//RegionInitialCondition[@InitialConditionID="InitialDemand"]')
                if ini is not None:r[tag]=float(ini.get('Value'))
        for offer in p.findall('.//InterconnectorPeriod[@InterconnectorID="T-V-MNSP1"]//MNSPOffer'):
            r['offer_'+offer.get('RegionID')]=float(offer.get('MaxAvail'))
        sol=doc.find('.//ConstraintSolution[@ConstraintID="N>999_9GL_NIL"][@Intervention="0"]')
        if sol is not None:r.update(bango=float(sol.get('RHS')),version=sol.get('Version'))
        sol=doc.find(f'.//ConstraintSolution[@ConstraintID="{QNI}"][@Intervention="0"]')
        r.update(QNI_solution=float(sol.get('RHS')) if sol is not None else np.nan,
                 QNI_version=sol.get('Version') if sol is not None else '')
        rows.append(dict(r,examined_corridor=True))
    pd.DataFrame(rows).to_csv(cached,index=False)

def capture_retry(day):
    for attempt in range(3):
        try:
            return capture(day)
        except requests.exceptions.RequestException:
            if attempt==2:raise

def run():
    dates=pd.date_range('2025-08-06','2026-02-25',freq='7D').union(pd.to_datetime(['2026-02-19','2026-02-22']))
    with ThreadPoolExecutor(3) as pool:list(pool.map(capture_retry,dates))
    obs=pd.concat([pd.read_csv(f) for f in sorted(OUT.glob('20*.csv'))],ignore_index=True)
    obs['end']=pd.to_datetime(obs.end);obs['day']=obs.end.dt.normalize()
    assert obs.end.is_unique
    obs=obs[~obs.intervention.astype(str).str.lower().eq('true')].copy()
    pointcols=[c for c in [*POINTS,RATING,'VRAT15_RCWE',*UNITS,'offer_TAS1','offer_VIC1'] if c in obs]
    forecasts=[]
    for day in dates[dates>=pd.Timestamp('2025-12-01')]:
        target=obs[obs.day.eq(day)].sort_values('end')
        if len(target)!=6:continue
        for lead in (10,21,42):
            origin=day+pd.Timedelta(hours=10)-pd.Timedelta(days=lead)
            past=obs[(obs.day+pd.Timedelta(days=2)<=origin)&(pd.to_datetime(obs.modified)<origin)]
            daily=past.groupby('day')[pointcols].mean()
            if len(daily)<5:continue
            # Forecast topology as a complete historical vector. Use an adjacent sampled
            # week's same-clock topology as the observed pattern available at issue.
            states=['TAMWORTH_CAP1_STATUS','TAMWORTH_CAP2_STATUS','TAMWORTH_R1_STATUS','BAN_CB_C_STAT']
            latest=daily.index[-1]
            distance=(daily[states]-daily.loc[latest,states]).abs().sum(axis=1,min_count=len(states))
            analog=distance.dropna().sort_index(ascending=False).sort_values(kind='stable').head(3).index
            for method,days in [('carry',[latest]),('clock',daily.index),('topology',analog)]:
                hist=past[past.day.isin(days)]
                for _,row in target.iterrows():
                    h=hist[hist.end.dt.minute.eq(row.end.minute)]
                    pred=h[pointcols].median()
                    # Keep statuses, offers and timer jointly attainable in a single reference case.
                    restricted=[k for k in pointcols if k in states or k.endswith(('TIMER','_STAT','_STATUS')) or k.startswith('offer_')]
                    if len(h):
                        dist=(h[restricted]-pred[restricted]).abs().div(h[restricted].abs().max().clip(lower=1)).sum(axis=1)
                        pred[restricted]=h.loc[dist.idxmin(),restricted].astype(float)
                    quantities={k:(pred[k],row.get(k,np.nan)) for k in pointcols}
                    if row.get('version')=='20251202000000_1':
                        def rhs(z):return 1.197*(z[RATING]-z['MVA_BAN_9GL']-10)+sum(z[k]*v for k,v in zip(UNITS,[1,.266,.375,.266]))
                        if pd.notna(rhs(row)):
                            assert abs(rhs(row)-row.bango)<2e-5
                            quantities['Bango dispatch RHS']=(rhs(pred),row.bango)
                    for k,(forecast,actual) in quantities.items():
                        if pd.notna(forecast) and pd.notna(actual):
                            forecasts.append((day,row.end,origin,lead,method,k,forecast,actual,latest))
    f=pd.DataFrame(forecasts,columns=['day','end','origin','lead','method','point','forecast','actual','latest_sample_day'])
    f['phase']=np.select([f.day.dt.month.eq(12),f.day.dt.month.eq(1),f.day.dt.day.isin([19,22])],['cal','unused','stress'],default='routine')
    f['error']=f.forecast-f.actual
    f.to_csv(OUT/'predictions.csv',index=False)
    block=f.groupby(['phase','day','origin','lead','method','point']).agg(n=('error','size'),error=('error','mean')).reset_index().query('n==6')
    block['absolute']=block.error.abs()
    grp=['lead','method','point']
    cal=block[block.phase.eq('cal')].copy()
    results=[]
    for key,g in block[block.phase.isin(['routine','stress'])].groupby(['phase',*grp]):
        eligible=cal[(cal.lead==key[1])&(cal.method==key[2])&(cal.point==key[3])&(cal.day+pd.Timedelta(days=2)<g.origin.min())]
        band=eligible.absolute.max()
        results.append([*key,len(g),g.absolute.mean(),g.error.mean(),g.absolute.max(),len(eligible),band,(g.absolute<=band).mean() if len(eligible) else np.nan])
    pd.DataFrame(results,columns=['phase',*grp,'half_hours','mae','bias','max_abs','cal_n','band','coverage']).to_csv(OUT/'scores.csv',index=False)
if __name__=='__main__':run()
