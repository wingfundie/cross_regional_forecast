"""As-of scheduled exposure and explicitly retrospective mapping/impact audit."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

from .core import ROOT, Store, digest


def mapping(c):
    root = ROOT / 'data' / c['connectors'][0]['study'] / 'standing'
    links = pd.read_parquet(root / 'GENCONSET.parquet')
    factors = pd.read_parquet(root / 'SPDINTERCONNECTORCONSTRAINT.parquet')
    equations = pd.read_parquet(root / 'GENCONDATA.parquet')
    factors = factors[factors.INTERCONNECTORID.eq(c['connectors'][0]['id'])]
    # Historical reconstruction only. Effective-date filtering does not prove receipt.
    # This union identifies potentially relevant set IDs. Exact effective versions
    # are resolved in MappingHistory.at for every as-of snapshot.
    merged = links[links.GENCONID.isin(set(factors.GENCONID))].copy()
    merged['effective'] = pd.to_datetime(merged.EFFECTIVEDATE)
    return merged, {'track': 'retrospective mapping; historical receipt unavailable',
                    'sources': [{'path': str(p.relative_to(ROOT)), 'sha256': digest(p)} for p in
                                [root / 'GENCONSET.parquet', root / 'SPDINTERCONNECTORCONSTRAINT.parquet', root / 'GENCONDATA.parquet']]}


class MappingHistory:
    """Resolve effective versions without pretending monthly metadata has receipt lineage."""
    def __init__(self, c):
        root = ROOT / 'data' / c['connectors'][0]['study'] / 'standing'
        self.tables = {n: pd.read_parquet(root / (n + '.parquet')) for n in
                       ['GENCONSET', 'GENCONDATA', 'SPDINTERCONNECTORCONSTRAINT']}
        f = self.tables['SPDINTERCONNECTORCONSTRAINT']
        self.tables['SPDINTERCONNECTORCONSTRAINT'] = f[f.INTERCONNECTORID.eq(c['connectors'][0]['id'])]
        for f in self.tables.values():
            f['EFFECTIVEDATE'] = pd.to_datetime(f.EFFECTIVEDATE)
            f['VERSIONNO'] = pd.to_numeric(f.VERSIONNO)
        self.tables['GENCONSET']['GENCONEFFDATE']=pd.to_datetime(self.tables['GENCONSET'].GENCONEFFDATE)
        self.tables['GENCONSET']['GENCONVERSIONNO']=pd.to_numeric(self.tables['GENCONSET'].GENCONVERSIONNO)
        self.times = np.unique(np.concatenate([f.EFFECTIVEDATE.to_numpy() for f in self.tables.values()]))
        self.cache = {}

    def at(self, origin):
        key = np.searchsorted(self.times, np.datetime64(origin), side='right')
        if key in self.cache:
            return self.cache[key]
        selected = {}
        for name, f in self.tables.items():
            group = 'GENCONSETID' if name == 'GENCONSET' else 'GENCONID'
            eligible = f[f.EFFECTIVEDATE.le(origin)]
            latest = eligible.sort_values(['EFFECTIVEDATE','VERSIONNO']).drop_duplicates(group,keep='last')[[group,'EFFECTIVEDATE','VERSIONNO']]
            selected[name] = eligible.merge(latest,on=[group,'EFFECTIVEDATE','VERSIONNO'])
        links = selected['GENCONSET'][['GENCONSETID','GENCONID','GENCONEFFDATE','GENCONVERSIONNO']]
        factor_all = self.tables['SPDINTERCONNECTORCONSTRAINT'][['GENCONID','EFFECTIVEDATE','VERSIONNO','FACTOR']]
        eq_all = self.tables['GENCONDATA'][['GENCONID','EFFECTIVEDATE','VERSIONNO','CONSTRAINTTYPE','LIMITTYPE']]
        explicit=links.GENCONEFFDATE.notna()&links.GENCONVERSIONNO.notna()
        exact = links[explicit].merge(factor_all,left_on=['GENCONID','GENCONEFFDATE','GENCONVERSIONNO'],
            right_on=['GENCONID','EFFECTIVEDATE','VERSIONNO']).merge(eq_all,
            left_on=['GENCONID','GENCONEFFDATE','GENCONVERSIONNO'],right_on=['GENCONID','EFFECTIVEDATE','VERSIONNO'])
        fallback = (links[~explicit].drop(columns=['GENCONEFFDATE','GENCONVERSIONNO'])
            .merge(selected['SPDINTERCONNECTORCONSTRAINT'][['GENCONID','FACTOR']],on='GENCONID')
            .merge(selected['GENCONDATA'][['GENCONID','CONSTRAINTTYPE','LIMITTYPE']],on='GENCONID'))
        rows=pd.concat([exact[['GENCONSETID','GENCONID','FACTOR','CONSTRAINTTYPE','LIMITTYPE']],fallback],ignore_index=True)
        result = {}
        for sid,f in rows.groupby('GENCONSETID'):
            types=set(f.LIMITTYPE.fillna('unknown').astype(str))
            factor=pd.to_numeric(f.FACTOR,errors='coerce'); inequality=f.CONSTRAINTTYPE.astype(str)
            upper=((inequality.isin(['LE','<=','<']) & factor.gt(0)) | (inequality.isin(['GE','>=','>']) & factor.lt(0))).any()
            lower=((inequality.isin(['LE','<=','<']) & factor.lt(0)) | (inequality.isin(['GE','>=','>']) & factor.gt(0))).any()
            result[sid]={'thermal':any('thermal' in t.lower() for t in types),
                         'stability':any('stability' in t.lower() for t in types),
                         'voltage':any('voltage' in t.lower() for t in types),
                         'upper':bool(upper),'lower':bool(lower)}
        self.cache[key]=result
        return result


def build_exposure(c, limit=None):
    """Incremental exact snapshot replay; preserve unknown source/mapping states."""
    store = Store(c)
    mapped, lineage = mapping(c)
    mapping_history = MappingHistory(c)
    mapped_sets = set(mapped.GENCONSETID)
    outputs, episode_rows = [], {}
    total_reports = 0
    revision_history = {}
    folders=[p for p in sorted((store.root / 'nos/weeks').glob('*')) if (p/'manifest.json').exists()]
    for folder in folders[:limit]:
        rows = pd.read_parquet(folder / 'rows.parquet')
        records = {}
        predecessors = {}
        for r in rows.itertuples():
            f=json.loads(r.fields_json);oid=f['OUTAGEID']
            if r.table=='OUTAGECONSTRAINTSET':
                if f['GENCONSETID'] not in mapped_sets:continue
                parsed={'oid':oid,'table':r.table,'set':f['GENCONSETID'],
                    'set_start':pd.to_datetime(f.get('STARTINTERVAL'),errors='coerce'),
                    'set_end':pd.to_datetime(f.get('ENDINTERVAL'),errors='coerce')}
            else:
                parsed={'oid':oid,'table':r.table,'status':f.get('OUTAGESTATUSCODE','').upper(),
                    'start':pd.to_datetime(f.get('STARTTIME'),errors='coerce'),
                    'end':pd.to_datetime(f.get('ENDTIME'),errors='coerce'),
                    'actual_start':pd.to_datetime(f.get('ACTUAL_STARTTIME'),errors='coerce'),
                    'actual_end':pd.to_datetime(f.get('ACTUAL_ENDTIME'),errors='coerce'),
                    'submitted':pd.to_datetime(f.get('SUBMITTEDDATE'),errors='coerce'),
                    'successor':str(f.get('RESUBMITOUTAGEID','')),
                    'secondary':f.get('ISSECONDARY')=='1',
                    'recall_day':pd.to_numeric(f.get('RECALLTIMEDAY'),errors='coerce'),
                    'recall_night':pd.to_numeric(f.get('RECALLTIMENIGHT'),errors='coerce'),
                    'asset':'/'.join(f.get(k,'') for k in ['SUBSTATIONID','EQUIPMENTTYPE','EQUIPMENTID'])}
                if parsed['successor']:predecessors.setdefault(parsed['successor'],set()).add(oid)
            records[r.row_id]=parsed
        changes = pd.read_parquet(folder / 'changes.parquet')
        reports = pd.read_parquet(folder / 'reports.parquet')
        active_by_outage={}; scheduled={}
        changes_by_time = {t: f for t, f in changes.groupby('generated_nem')}

        def rebuild(oid,origin):
            active=[records[rid] for rid in active_by_outage.get(oid,set())]
            links={r['set']:(r['set_start'],r['set_end']) for r in active if r['table']=='OUTAGECONSTRAINTSET'}
            details=[r for r in active if r['table']=='OUTAGEDETAIL']
            if not links or not details:
                scheduled.pop(oid,None);return
            if any(oid in active_by_outage for oid in {r['successor'] for r in details if r['successor']}):
                scheduled.pop(oid,None);return
            entry=None
            for r in details:
                start,end=r['start'],r['end']
                if pd.isna(start) or pd.isna(end) or end<=start:continue
                key=(oid,r['asset'])
                if key not in episode_rows:
                    episode_rows[key]={'outage_id':oid,'first_seen_origin':origin,'start':start,'end':end,
                        'status':r['status'],'asset':r['asset'],'sets':'|'.join(sorted(links)),
                        'secondary':r['secondary'],'successor':r['successor'],
                        'actual_start':r['actual_start'],'actual_end':r['actual_end']}
                if r['status'] in {'WDRAWN','CANCELLED','COMPLETED','COMPLETE','REPLACED','RESUBMIT'}:continue
                if entry is None:
                    entry={'start':start,'end':end,'sets':set(),'assets':set(),'secondary':True,
                        'windows':[],'status':r['status'],'submitted':r['submitted'],
                        'recall_day':r['recall_day'],'recall_night':r['recall_night']}
                entry['start']=min(entry['start'],start);entry['end']=max(entry['end'],end)
                entry['sets'].update(links);entry['assets'].add(r['asset']);entry['secondary'] &= r['secondary']
                equipment_start=r['actual_start'] if pd.notna(r['actual_start']) and r['actual_start']<=origin else start
                for sid,(sa,sb) in links.items():
                    entry['windows'].append((sid,equipment_start.value,end.value,
                        sa.value if pd.notna(sa) else None,sb.value if pd.notna(sb) else None))
            if entry is None:scheduled.pop(oid,None);return
            signature=(entry['start'],entry['end'],entry['status'])
            history=revision_history.setdefault(oid,[])
            if not history or history[-1][1]!=signature:history.append((origin,signature))
            entry['history']=history
            scheduled[oid]=entry

        for r in reports.itertuples():
            total_reports += 1
            change = changes_by_time.get(r.generated_nem)
            affected=set()
            if change is not None:
                for item in change.itertuples():
                    record=records.get(item.row_id)
                    if record is None:continue
                    oid=record['oid'];affected.add(oid);affected.update(predecessors.get(oid,set()))
                    state=active_by_outage.setdefault(oid,set())
                    (state.add if item.present else state.discard)(item.row_id)
                    if not state:active_by_outage.pop(oid,None)
            origin = (r.generated_nem + pd.Timedelta(minutes=30)).ceil('30min')
            if origin >= pd.Timestamp(c['end']):
                continue
            for oid in affected:rebuild(oid,origin)
            current_mapping = mapping_history.at(origin)
            values=[]
            for oid,v in scheduled.items():
                # Known actual completion applies only after it is present in this snapshot.
                actual_ends=[x['actual_end'] for x in (records[rid] for rid in active_by_outage.get(oid,set()))
                             if x['table']=='OUTAGEDETAIL' and pd.notna(x['actual_end'])]
                if actual_ends and min(actual_ends)<=origin:continue
                history=v['history'];v['changes24']=sum(t>=origin-pd.Timedelta(days=1) for t,_ in history[1:])
                v['revision_age']=(origin-history[-1][0]).total_seconds()/60
                v['start_shift']=(history[-1][1][0]-history[-2][1][0]).total_seconds()/60 if len(history)>1 else 0.
                v['end_shift']=(history[-1][1][1]-history[-2][1][1]).total_seconds()/60 if len(history)>1 else 0.
                v['status_changes24']=sum(history[j][0]>=origin-pd.Timedelta(days=1) and history[j][1][2]!=history[j-1][1][2] for j in range(1,len(history)))
                v['overdue']=v['end']<origin and not actual_ends
                values.append(v)
            for lead in c['leads']:
                delivery = origin + pd.Timedelta(minutes=30 * lead)
                endpoints = delivery.value - np.arange(25,-1,-5,dtype='int64')*60_000_000_000
                active=[]; exposure_sets=set(); overlap=0.
                for v in values:
                    hit=np.zeros(6,dtype=bool)
                    for sid,start,end,sa,sb in v['windows']:
                        window=(endpoints>=start)&(endpoints<end)
                        if sa is not None:window &= endpoints>=sa
                        if sb is not None:window &= endpoints<=sb
                        if window.any():exposure_sets.add(sid)
                        hit |= window
                    if hit.any():active.append(v);overlap += hit.mean()
                started = [v for v in values if origin < v['start'] <= delivery]
                ending = [v for v in values if origin < v['end'] <= delivery]
                sets = exposure_sets & set(current_mapping)
                outputs.append({'origin': origin, 'lead': lead, 'nos_count': len(active), 'nos_sets': len(sets),
                    'nos_primary': sum(not v['secondary'] for v in active), 'nos_secondary': sum(v['secondary'] for v in active),
                    'nos_starts': len(started), 'nos_ends': len(ending), 'nos_report_generated': r.generated_nem,
                    'nos_overlap':overlap, 'nos_upper_sets':sum(current_mapping[s]['upper'] for s in sets),
                    'nos_lower_sets':sum(current_mapping[s]['lower'] for s in sets),
                    'nos_thermal_sets':sum(current_mapping[s]['thermal'] for s in sets),
                    'nos_stability_sets':sum(current_mapping[s]['stability'] for s in sets),
                    'nos_voltage_sets':sum(current_mapping[s]['voltage'] for s in sets),
                    'nos_unknown_mechanism':sum(not any(current_mapping[s][k] for k in ('thermal','stability','voltage')) for s in sets),
                    'nos_changes24':sum(v['changes24'] for v in active),
                    'nos_start_shift_minutes':sum(v['start_shift'] for v in active),
                    'nos_end_shift_minutes':sum(v['end_shift'] for v in active),
                    'nos_status_changes24':sum(v['status_changes24'] for v in active),
                    'nos_revision_age_minutes':min([v['revision_age'] for v in active]+[1440.]),
                    'nos_booking_age_hours':max([(origin-v['submitted']).total_seconds()/3600 for v in active if pd.notna(v['submitted'])]+[0.]),
                    'nos_overdue':sum(v['overdue'] for v in values),
                    'nos_uncertain_status':sum(v['status'] in {'UTP','WD REQ','RESUBMIT','INFO'} for v in active),
                    'nos_recall_day':max([max(v['recall_day'],0) for v in active if np.isfinite(v['recall_day'])]+[0]),
                    'nos_recall_night':max([max(v['recall_night'],0) for v in active if np.isfinite(v['recall_night'])]+[0]),
                    'nos_mapping_track': 'retrospective'})
        print('EXPOSURE', folder.name, total_reports, flush=True)
    frame = pd.DataFrame(outputs).sort_values('nos_report_generated').drop_duplicates(['origin','lead'], keep='last')
    store.parquet(store.root / 'nos/exposure.parquet', frame)
    store.parquet(store.root / 'nos/episode_revisions.parquet', pd.DataFrame(episode_rows.values()))
    store.json(store.root / 'nos/mapping_audit.json', {**lineage, 'mapped_sets': len(mapped_sets), 'rows': len(frame),
               'limitations': ['Versioned mapping is reconstructed, not receipt-verified. Matched-impact and temporal negative-control gates must pass before NOS fitting.'],
               'historical_model_gate': bool(len(frame) and frame.nos_report_generated.add(pd.Timedelta(minutes=30)).le(frame.origin).all()),
               'operational_model_gate': False,
               'temporal_checks':{'source_available_by_origin':bool(frame.nos_report_generated.add(pd.Timedelta(minutes=30)).le(frame.origin).all()),
                   'unique_origin_lead':bool(not frame.duplicated(['origin','lead']).any()),
                   'later_actual_restoration_test':'tests/test_diurnal_v2.py'}})
    return frame


def impact_report(c):
    """Preliminary descriptive audit, never silently presented as matched effects."""
    store = Store(c)
    episodes = pd.read_parquet(store.root / 'nos/episode_revisions.parquet')
    # Last visible revision before scheduled start; late discoveries reported separately.
    known = episodes[episodes.first_seen_origin.le(episodes.start)].sort_values('first_seen_origin')
    known = known.drop_duplicates(['outage_id','asset'], keep='last')
    known = known[~known.status.isin(['WDRAWN','COMPLETE','RESUBMIT'])]
    y = pd.read_parquet(ROOT / 'data/processed/targets.parquet')
    y = y[y.ic.eq(c['connectors'][0]['id'])].set_index('time')
    rows = []
    for e in known.itertuples():
        for direction in ('export', 'import'):
            s = y[direction + '_tight']
            before = s.loc[(s.index >= e.start - pd.Timedelta(hours=2)) & (s.index < e.start)].dropna()
            after = s.loc[(s.index >= e.start) & (s.index < min(e.end, e.start + pd.Timedelta(hours=2)))].dropna()
            if len(before) >= 3 and len(after) >= 3:
                rows.append({'outage_id': e.outage_id, 'asset': e.asset, 'sets': e.sets,
                             'direction': direction, 'start': e.start, 'raw_reduction_mw': float(before.mean() - after.mean()),
                             'pre_mean': float(before.mean()), 'post_mean': float(after.mean())})
    effects = pd.DataFrame(rows)
    if len(effects):
        store.parquet(store.root / 'nos/raw_episode_effects.parquet', effects)
    report = {'status': 'descriptive only; not cleared for outcome-derived features',
              'episodes': int(known.outage_id.nunique()), 'usable_direction_asset_records': len(effects),
              'claim': 'Raw before/after associations; concurrent outages, operating state and matched-control balance not yet resolved',
              'highest_impact_verdict': 'Not established: do not rank raw changes as adjusted recurring effects'}
    store.json(store.root / 'nos/impact_status.json', report)
    return report


def matched_impacts(c, cutoff=None):
    """Training-cutoff replay or explicitly developmental full-history atlas.

    Isolated start episodes are compared with earlier calendar-matched windows.
    No satisfactory matches means unavailable, not a zero estimated effect.
    """
    from .data import connector_data,base_frame
    store=Store(c); d=connector_data(c,c['connectors'][0]);base=base_frame(d)
    revisions=pd.read_parquet(store.root/'nos/episode_revisions.parquet')
    revisions=revisions[revisions.first_seen_origin.le(revisions.start)]
    if cutoff is not None:
        revisions=revisions[revisions.start.add(pd.Timedelta(hours=24,minutes=30)).lt(pd.Timestamp(cutoff))]
    episodes=revisions.sort_values('first_seen_origin').drop_duplicates(['outage_id','asset'],keep='last')
    episodes=episodes[~episodes.status.isin(['WDRAWN','COMPLETE','RESUBMIT'])]
    coverage=pd.read_parquet(store.root/'nos/coverage.parquet').set_index('origin').fresh
    exposure=pd.read_parquet(store.root/'nos/exposure.parquet')
    exposure=exposure[exposure.lead.eq(1)].set_index('origin').nos_count
    # One episode per booking for matching; asset/set expansion happens afterwards.
    grouped=[]
    for oid,f in episodes.groupby('outage_id'):
        grouped.append({'outage_id':oid,'start':f.start.min(),'end':f.end.max(),
                        'assets':sorted(x for x in set(f.asset) if x),
                        'sets':sorted(x for x in set('|'.join(f.sets).split('|')) if x)})
    ledger=pd.DataFrame(grouped)
    if ledger.empty:
        raise ValueError('No mature prospective-known episode starts for impact analysis')
    effects=[]; exclusions=[]; curves=[]
    driver_columns=[n for n in ['flow_lag1','upper_gen_tightening','lower_gen_tightening','upper_room','lower_room'] if n in base]
    for e in ledger.sort_values('start').itertuples():
        start=pd.Timestamp(e.start).ceil('30min');duration=min((e.end-start).total_seconds()/3600,24)
        overlap=ledger[(ledger.outage_id.ne(e.outage_id)) & (ledger.start.lt(start+pd.Timedelta(hours=2))) & (ledger.end.gt(start-pd.Timedelta(hours=2)))]
        if len(overlap):
            exclusions.append({'outage_id':e.outage_id,'reason':'concurrent mapped outage: individual association not identified'})
            continue
        candidates=[start-pd.Timedelta(days=days) for days in range(7,85,7)]
        for direction in ('export','import'):
            series=d['y'][direction+'_tight']
            def observation(t):
                pre=pd.date_range(t-pd.Timedelta(hours=2),t-pd.Timedelta(minutes=30),freq='30min')
                post=pd.date_range(t,t+pd.Timedelta(hours=2)-pd.Timedelta(minutes=30),freq='30min')
                alltimes=pre.append(post)
                if coverage.reindex(alltimes).fillna(False).mean()<.8:return None
                before=series.reindex(pre);after=series.reindex(post)
                if before.notna().sum()<3 or after.notna().sum()<3:return None
                drivers=base.reindex([t])[driver_columns].iloc[0].to_numpy(dtype=float)
                return np.r_[before.mean(),before.iloc[-1]-before.iloc[0],drivers],float(after.mean()-before.mean())
            treated=observation(start)
            if treated is None:continue
            possible=[]
            for candidate in candidates:
                result=observation(candidate)
                if result is None:continue
                window=pd.date_range(candidate-pd.Timedelta(hours=2),candidate+pd.Timedelta(hours=2),freq='30min')
                context=exposure.reindex(window)
                if context.isna().any() or context.gt(0).any():continue
                possible.append((candidate,*result))
            if len(possible)<3:
                exclusions.append({'outage_id':e.outage_id,'direction':direction,'reason':'fewer than three prior unexposed matched controls'})
                continue
            reference=np.stack([p[1] for p in possible]);v=treated[0]
            scale=np.nanstd(reference,axis=0); scale=np.where(scale>1e-8,scale,1.)
            distance=np.nanmean(abs(reference-v)/scale,axis=1)
            valid=np.isfinite(distance)&(distance<=1.)
            selected=np.flatnonzero(valid)[np.argsort(distance[valid])][:5]
            if len(selected)<3:
                exclusions.append({'outage_id':e.outage_id,'direction':direction,'reason':'control balance caliper failed'})
                continue
            change=treated[1];control=np.array([possible[j][2] for j in selected])
            reduction=-(change-control.mean())
            pretrend_gap=float(v[1]-reference[selected,1].mean())
            pretrend_scale=float(max(np.nanstd(reference[:,1]),1.))
            placebo=[]
            for j in range(len(control)):
                others=np.delete(control,j)
                if len(others):placebo.append(-(control[j]-others.mean()))
            effects.append({'outage_id':e.outage_id,'direction':direction,'start':start,
                'raw_reduction_mw':-change,'adjusted_reduction_mw':reduction,
                'controls':len(selected),'balance_distance':float(distance[selected].mean()),
                'pretrend_gap_mw':pretrend_gap,'pretrend_scale_mw':pretrend_scale,
                'pretrend_pass':abs(pretrend_gap)<=pretrend_scale,
                'placebo_abs_median_mw':float(np.median(abs(np.asarray(placebo)))) if placebo else None,
                'control_times':'|'.join(str(possible[j][0]) for j in selected),'assets':'|'.join(e.assets),'sets':'|'.join(e.sets),
                'claim':'isolated-episode adjusted association, not causal effect'})
            for offset in range(-12,49):
                t=start+pd.Timedelta(minutes=30*offset)
                actual=series.get(t,np.nan)
                refs=[series.get(possible[j][0]+pd.Timedelta(minutes=30*offset),np.nan) for j in selected]
                curves.append({'outage_id':e.outage_id,'direction':direction,'hours':offset/2,
                               'actual_limit':actual,'reference_limit':float(np.nanmean(refs))})
    tag='full_development' if cutoff is None else str(pd.Timestamp(cutoff).date())
    folder=store.root/'nos/impact'/tag
    effect_frame=pd.DataFrame(effects)
    store.parquet(folder/'matched_effects.parquet',effect_frame)
    store.json(folder/'exclusions.json',exclusions)
    if curves:store.parquet(folder/'event_curves.parquet',pd.DataFrame(curves))
    ranks=[];rng=np.random.default_rng(741)
    if len(effect_frame):
        for kind in ('assets','sets'):
            expanded=effect_frame.assign(entity=effect_frame[kind].str.split('|')).explode('entity')
            expanded=expanded[expanded.entity.fillna('').ne('')]
            for (direction,entity),g in expanded.groupby(['direction','entity']):
                v=g.adjusted_reduction_mw.to_numpy();n=len(g)
                draws=np.median(rng.choice(v,(2000,n),replace=True),axis=1)
                months=g.start.dt.to_period('M').nunique()
                median=float(np.median(v));placebo=float(g.placebo_abs_median_mw.median())
                ranks.append({'kind':kind,'direction':direction,'entity':entity,'episodes':n,'months':months,
                    'median_reduction_mw':median,'p90_reduction_mw':float(np.quantile(v,.9)),
                    'ci_low':float(np.quantile(draws,.025)),'ci_high':float(np.quantile(draws,.975)),
                    'same_positive_sign_fraction':float(np.mean(v>0)),
                    'pretrend_pass_fraction':float(g.pretrend_pass.mean()),'placebo_abs_median_mw':placebo,
                    'effect_exceeds_placebo':abs(median)>placebo,
                    'supported_recurring':n>=10 and months>=3 and g.pretrend_pass.mean()>=.8 and abs(median)>placebo,
                    'uncertainty':'episode bootstrap; dependence sensitivity required for promotion'})
        # Leave one outage episode out globally, then recompute the entity rank.
        for kind in ('assets','sets'):
            expanded=effect_frame.assign(entity=effect_frame[kind].str.split('|')).explode('entity')
            expanded=expanded[expanded.entity.fillna('').ne('')]
            for direction,directional in expanded.groupby('direction'):
                entities=directional.entity.unique();positions={e:[] for e in entities}
                for outage_id in directional.outage_id.unique():
                    reduced=directional[directional.outage_id.ne(outage_id)]
                    order=reduced.groupby('entity').adjusted_reduction_mw.median().sort_values(ascending=False).index.tolist()
                    for entity in entities:
                        if entity in order:positions[entity].append(order.index(entity)+1)
                for row in ranks:
                    if row['kind']==kind and row['direction']==direction and positions.get(row['entity']):
                        values=positions[row['entity']]
                        row['loo_rank_median']=float(np.median(values));row['loo_rank_min']=int(min(values));row['loo_rank_max']=int(max(values))
    store.json(folder/'rankings.json',ranks)
    status={'cutoff':cutoff,'track':'full-history development atlas' if cutoff is None else 'training-only matched episode analysis',
            'candidate_bookings':len(ledger),'matched_direction_episodes':len(effects),'excluded_records':len(exclusions),
            'supported_recurring_entities':sum(r['supported_recurring'] for r in ranks),
            'O5_gate':False,'reason':'Outcome weights require fold-local chronological encoding and dependence/rank stability checks; not admitted by this descriptive atlas',
            'highest_impact':sorted([r for r in ranks if r['supported_recurring']],key=lambda r:r['median_reduction_mw'],reverse=True)[:20]}
    store.json(folder/'status.json',status)
    return status
