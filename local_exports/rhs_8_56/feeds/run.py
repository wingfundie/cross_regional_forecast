"""February 2026 original MT PASA daily outlook and NOS validation at 10, 21 and 42 days."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from zipfile import ZipFile
from datetime import datetime
import io, json, hashlib, sys, csv
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT/'local_exports/rhs_approximation_study/states'))
import study as archive

REGIONS=('NSW1','VIC1','QLD1')
LINKS={'QNI':'NSW1-QLD1','VNI':'VIC1-NSW1'}
DAYS=['2026-02-04','2026-02-11','2026-02-18','2026-02-25']
CAL=['2025-11-23','2025-11-24','2025-11-26','2025-11-28']
LEADS=[10,21,42]
SOURCE=[]

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def member_for(origin):
    # Permit a full additional calendar day for the public next-day release.
    cutoff=origin-pd.Timedelta(days=1)
    for back in range(5):
        date=cutoff.normalize()-pd.Timedelta(days=back)
        url=archive.ARCHIVE+f'MTPASA_RegionAvailability/PUBLIC_MTPASAREGIONAVAILABILITY_{date:%Y%m01}.zip'
        _,entries=archive.directory(url)
        candidates=[e for e in entries if pd.Timestamp(*e.date_time)<cutoff and
                    e.filename.startswith(f'PUBLIC_MTPASAREGIONAVAILABILITY_{date:%Y%m%d}')]
        if candidates:return url,max(candidates,key=lambda e:e.date_time).filename
    raise ValueError(f'No eligible archive at {origin}')

def capture(job):
    day,lead=job
    origin=day-pd.Timedelta(days=lead)
    url,member=member_for(origin)
    raw,modified=archive.get_member(url,member)
    records=[]; energy={}
    with ZipFile(io.BytesIO(raw)) as z, io.TextIOWrapper(z.open(z.namelist()[0]),encoding='utf-8-sig') as stream:
        rd=csv.reader(stream);head=next(rd);created=pd.Timestamp(' '.join(head[5:7]))
        assert max(created,pd.Timestamp(modified))<origin-pd.Timedelta(days=1)
        for row in rd:
            if row[2:3]!=['REGIONAVAILABILITY']:continue
            if row[0]=='I':header=row[4:];continue
            if row[0]!='D':continue
            r=dict(zip(header,row[4:]))
            if r['REGIONID'] not in REGIONS:continue
            delivery=pd.Timestamp(r['DAY'])
            if r['ENERGYREQDEMAND50'] and float(r['ENERGYREQDEMAND50'])>0:
                energy[delivery,r['REGIONID']]=float(r['ENERGYREQDEMAND50'])
            if delivery not in (day-pd.Timedelta(days=1),day):continue
            records.append(dict(origin=origin,delivery_day=day,lead=lead,run=member,
                            created=created,member_modified=modified,source_sha256=hashlib.sha256(raw).hexdigest(),
                            source_url=url,**r))
    assert len(records)==6
    for r in records:
        d=pd.Timestamp(r['DAY']); sunday=d-pd.Timedelta(days=(d.weekday()+1)%7)
        r['week_start']=sunday; r['week_gwh']=energy[sunday,r['REGIONID']]
    return records

def demand_outlook(issued):
    src=ROOT/'data/processed/regional_30min.parquet'
    hist=pd.read_parquet(src,columns=['demand']).reset_index()
    hist=hist[hist.region.isin(REGIONS)].copy()
    # 04:05-04:00 NEM trading day, with midnight labelled as the preceding delivery day's last half-hour.
    hist['trade_day']=(hist.time-pd.Timedelta(hours=4,minutes=1)).dt.normalize()
    hist['slot']=((hist.time-hist.trade_day).dt.total_seconds()/1800).astype(int)
    records=[]
    for r in issued.itertuples():
        td=pd.Timestamp(r.DAY); day=pd.Timestamp(r.delivery_day); origin=pd.Timestamp(r.origin)
        group=hist[hist.region.eq(r.REGIONID)]
        dates=[td-pd.Timedelta(days=364+x*7) for x in range(-2,3)]
        fit=group[group.trade_day.isin(dates)].copy()
        assert len(fit)==240 and fit.time.max()<origin-pd.Timedelta(days=2) and fit.demand.notna().all()
        fit['fraction']=fit.demand/fit.groupby('trade_day').demand.transform('max')
        profile=fit.groupby('slot')[['fraction','demand']].mean()
        sunday=pd.Timestamp(r.week_start)
        levels=[]
        for offset in range(-2,3):
            week_start=sunday-pd.Timedelta(days=364+7*offset)
            sampled=group[(group.trade_day>=week_start)&(group.trade_day<week_start+pd.Timedelta(days=7))]
            assert len(sampled)==336 and sampled.demand.notna().all() and sampled.time.max()<origin
            levels.append(sampled.demand.mean())
        targets=group[group.trade_day.eq(td)&group.time.gt(day)&group.time.le(day+pd.Timedelta(days=1))]
        for t in targets.itertuples():
            records.append(dict(end=t.time,origin=origin,lead=r.lead,region=r.REGIONID,delivery_day=day,
                                run=r.run,training_end=fit.time.max(),actual=t.demand,
                                clock=profile.at[t.slot,'demand'],pasa=profile.at[t.slot,'fraction']*float(r.DEMAND50),
                                pasa_weekly=profile.at[t.slot,'demand']/np.mean(levels)*r.week_gwh*1000/168,
                                offered_capacity=float(r.PASAAVAILABILITY_SCHEDULED)))
    result=pd.DataFrame(records)
    assert result.groupby(['delivery_day','region','lead']).size().eq(48).all()
    assert not result.duplicated(['end','region','lead']).any()
    result['partition']=np.where(result.delivery_day.dt.strftime('%Y-%m-%d').isin(CAL),'calibration',
                       np.where(result.delivery_day.dt.strftime('%Y-%m-%d').isin(DAYS),'routine','stress'))
    result.to_csv(OUT/'regional_forecasts.csv',index=False)
    by=result.melt(id_vars=['partition','lead','region','actual'],value_vars=['pasa','pasa_weekly','clock'],var_name='method')
    by['error']=by.value-by.actual
    met=by.groupby(['partition','lead','region','method']).error.agg(n='size',mae=lambda x:abs(x).mean(),bias='mean')
    met.to_csv(OUT/'regional_scores.csv')
    SOURCE.append(dict(source=str(src.relative_to(ROOT)),sha256=sha(src),use='historical six-interval demand profile and target'))

@lru_cache(maxsize=3)
def week(date):
    path=ROOT/'data/forecast_experiments/vni_diurnal_nos_v2/nos/weeks'/f'PUBLIC_NETWORK_{date:%Y%m%d}'
    manifest=json.loads((path/'manifest.json').read_text())
    SOURCE.append(dict(url=manifest['url'],sha256=manifest['raw_sha256'],use='original NOS source'))
    frames=[]
    for name in ('reports','changes','rows'):
        source=path/(name+'.parquet')
        expected=next(a['sha256'] for a in manifest['artifacts'] if a['path'].endswith(name+'.parquet'))
        assert sha(source)==expected
        frames.append(pd.read_parquet(source))
    return tuple(frames)

def snapshot(origin):
    cutoff=origin-pd.Timedelta(minutes=30)
    friday=cutoff.normalize()-pd.Timedelta(days=(cutoff.weekday()-4)%7)
    reports,changes,rows=week(friday)
    summary=reports[reports.generated_nem<=cutoff].sort_values('generated_nem').iloc[-1]
    state=changes[changes.generated_nem<=summary.generated_nem].sort_values('generated_nem').drop_duplicates('row_id',keep='last')
    wanted=rows[rows.row_id.isin(state.loc[state.present,'row_id'])]
    det=pd.DataFrame([json.loads(item) for item in wanted.loc[wanted.table.eq('OUTAGEDETAIL'),'fields_json']])
    mapping=pd.DataFrame([json.loads(item) for item in wanted.loc[wanted.table.eq('OUTAGECONSTRAINTSET'),'fields_json']])
    closed={'WDRAWN','CANCELLED','COMPLETE','COMPLETED','REPLACED','RESUBMIT'}
    active=det[~det.OUTAGESTATUSCODE.isin(closed)&~det.RESUBMITOUTAGEID.isin(det.OUTAGEID)].copy()
    out=active.merge(mapping,on='OUTAGEID')
    out['start']=pd.to_datetime(out.STARTTIME)
    out['end']=pd.to_datetime(out.ENDTIME)
    for field,target in [('ACTUAL_STARTTIME','start'),('ACTUAL_ENDTIME','end')]:
        actual=pd.to_datetime(out[field],errors='coerce'); out[target]=actual.where(actual<=origin,out[target])
    out['map_start']=pd.to_datetime(out.STARTINTERVAL,errors='coerce')
    out['map_end']=pd.to_datetime(out.ENDINTERVAL,errors='coerce')
    return set(mapping.GENCONSETID),out,summary

def standing(link):
    path=ROOT/f'data/constraint_{link.lower()}_2y/standing'
    tables=[]
    for name in ['GENCONSET','SPDINTERCONNECTORCONSTRAINT','GENCONSETINVOKE']:
        src=path/(name+'.parquet')
        SOURCE.append(dict(source=str(src.relative_to(ROOT)),sha256=sha(src),use=name))
        frame=pd.read_parquet(src)
        if 'EFFECTIVEDATE' in frame:
            frame['eff']=pd.to_datetime(frame.EFFECTIVEDATE)
            frame['changed']=pd.to_datetime(frame.LASTCHANGED,errors='coerce')
            frame['version']=pd.to_numeric(frame.VERSIONNO)
        else:
            frame=frame[frame.INTERVENTION.eq('N')].copy()
            frame['start']=pd.to_datetime(frame.STARTINTERVALDATETIME,errors='coerce')
            frame['end']=pd.to_datetime(frame.ENDINTERVALDATETIME,errors='coerce')
        tables.append(frame)
    return tables

def current(frame,key,origin):
    elig=frame[(frame.eff<origin)&(frame.changed<origin-pd.Timedelta(days=2))]
    newest=elig.sort_values(['eff','version']).drop_duplicates(key,keep='last')[[key,'eff','version']]
    return elig.merge(newest,on=[key,'eff','version'])

def outage_scores(days):
    stand={link:standing(link) for link in LINKS}
    fixed_names=set()
    freeze=pd.Timestamp('2025-12-15')
    assert min(days)-pd.Timedelta(days=max(LEADS))>freeze
    for date in ['2025-09-15','2025-10-15','2025-11-15','2025-12-15']:
        names,_,_=snapshot(pd.Timestamp(date))
        fixed_names.update(names)
    fixed={}
    for link,(sets,terms,_) in stand.items():
        c=current(terms,'GENCONID',freeze)
        names=set(c.loc[(c.INTERCONNECTORID==LINKS[link])&pd.to_numeric(c.FACTOR).ne(0),'GENCONID'])
        eligible=current(sets,'GENCONSETID',freeze)
        fixed[link]=fixed_names & set(eligible.loc[eligible.GENCONID.isin(names),'GENCONSETID'])
    records=[]
    details=[]
    for day,lead in [(t,l) for t in days for l in LEADS]:
        origin=day-pd.Timedelta(days=lead)
        offered,forecast,snap=snapshot(origin)
        for link,(sets,terms,inv) in stand.items():
            c=current(terms,'GENCONID',origin)
            names=set(c.loc[(c.INTERCONNECTORID==LINKS[link])&pd.to_numeric(c.FACTOR).ne(0),'GENCONID'])
            eligible=current(sets,'GENCONSETID',origin)
            currently_listed=offered & set(eligible.loc[eligible.GENCONID.isin(names),'GENCONSETID'])
            relevant=currently_listed|fixed[link]
            dayshift=7*((lead+8)//7)
            # Same weekday strictly before the origin, with >1 day gap for archive publication.
            assert dayshift-lead>=2
            times=pd.date_range(day+pd.Timedelta(minutes=5),periods=288,freq='5min')
            forecasts={}; labels={}; bases={}; origin_plans={}
            for name in relevant:
                planned=forecast[forecast.GENCONSETID==name]
                obs=inv[inv.GENCONSETID==name]
                def mask(rows,tt,projected=False):
                    values=np.zeros(len(tt),dtype=bool)
                    for row in rows.itertuples():
                        if pd.isna(row.start):continue
                        valid=(tt>row.start if projected else tt>=row.start)&(True if pd.isna(row.end) else tt<=row.end)
                        if projected:
                            if pd.notna(row.map_start):valid &= tt>=row.map_start
                            if pd.notna(row.map_end):valid &= tt<=row.map_end
                        values|=valid
                    return values.reshape(48,6).any(axis=1)
                labels[name]=mask(obs,times)
                forecasts[name]=mask(planned,times,True)
                origin_plans[name]=mask(planned,times-pd.Timedelta(days=lead),True)
                # Benchmark is prior same-weekday realised invocation, retrospectively reconstructed.
                bases[name]=mask(obs,times-pd.Timedelta(days=dayshift))
            for i,end in enumerate(times[5::6]):
                for universe,cohort in [('origin_listed',currently_listed),('fixed_december',fixed[link])]:
                    actual={n for n in cohort if labels[n][i]}
                    pred={n for n in cohort if forecasts[n][i]}
                    prior={n for n in cohort if bases[n][i]}
                    current_day={n for n in cohort if origin_plans[n][i]}
                    for method,p in [('NOS',pred),('origin_day_schedule',current_day),('retrospective_prior_weekday',prior)]:
                        records.append(dict(universe=universe,link=link,lead=lead,day=day,end=end,origin=origin,method=method,relevant=len(cohort),
                            member=snap.member,generated=snap.generated_nem,tp=len(actual&p),fp=len(p-actual),fn=len(actual-p),
                            predicted_sets='|'.join(sorted(p)),actual_sets='|'.join(sorted(actual))))
            for universe,cohort in [('origin_listed',currently_listed),('fixed_december',fixed[link])]:
                details.append(dict(universe=universe,link=link,origin=origin,count=len(cohort),set_names='|'.join(sorted(cohort))))
    raw=pd.DataFrame(records); raw.to_csv(OUT/'outage_rows.csv',index=False)
    pd.DataFrame(details).to_csv(OUT/'set_universes.csv',index=False)
    raw['partition']=np.where(raw.day.dt.strftime('%Y-%m-%d').isin(DAYS),'routine','stress')
    met=raw.groupby(['universe','partition','link','lead','method'])[['tp','fp','fn']].sum()
    met['precision']=met.tp/(met.tp+met.fp);met['recall']=met.tp/(met.tp+met.fn)
    met.to_csv(OUT/'outage_scores.csv')

if __name__=='__main__':
    stress=[s for s in sys.argv[1:] if not s.startswith('--')]
    days=sorted({pd.Timestamp(s) for s in DAYS+stress})
    all_days=sorted(set(days)|{pd.Timestamp(s) for s in CAL})
    f=OUT/'pasa_issued.csv'
    old=pd.read_csv(f) if f.exists() else pd.DataFrame()
    if 'week_gwh' not in old:old=pd.DataFrame()
    have=set(zip(pd.to_datetime(old.delivery_day,format='mixed'),old.lead)) if len(old) else set()
    jobs=[(d,l) for d in all_days for l in LEADS if (d,l) not in have]
    new=[r for rows in ThreadPoolExecutor(4).map(capture,jobs) for r in rows]
    issued=pd.concat([old,pd.DataFrame(new)],ignore_index=True)
    issued.to_csv(f,index=False)
    demand_outlook(issued)
    if '--demand' not in sys.argv:outage_scores(days)
    (OUT/'source_hashes.json').write_text(json.dumps(SOURCE,indent=2))
