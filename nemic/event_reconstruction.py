"""Selected-window equation reconstruction with explicit switch and residual accounting."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .common import DATA, PROCESSED, dump
from .event_atlas import settings, save, deduplicate, log, digest, DEFAULT


def standing_frame(c,name):
    p=c['standing']/f'{name}.parquet';f=pd.read_parquet(p)
    if 'EFFECTIVEDATE' in f:f['EFFECTIVEDATE']=pd.to_datetime(f.EFFECTIVEDATE)
    if 'VERSIONNO' in f:f['VERSIONNO']=pd.to_numeric(f.VERSIONNO)
    if 'FACTOR' in f:f['FACTOR']=pd.to_numeric(f.FACTOR)
    log(c,{'kind':'standing_reuse','path':str(p),'sha256':digest(p)})
    return f.drop_duplicates()


def reconstruct(c):
    root=c['root'];ic=pd.read_parquet(root/'screen_timeseries.parquet').set_index('time')
    events=pd.read_parquet(root/'event_catalogue.parquet');selected=events[events.selected]
    factors=standing_frame(c,'SPDINTERCONNECTORCONSTRAINT')
    cp=standing_frame(c,'SPDCONNECTIONPOINTCONSTRAINT')
    cp=cp[cp.BIDTYPE.fillna('ENERGY').eq('ENERGY')]
    meta=standing_frame(c,'GENCONDATA')
    target=factors[factors.INTERCONNECTORID.eq(c['interconnector'])].rename(columns={'GENCONID':'CONSTRAINTID','FACTOR':'ic_factor'})
    keys=['CONSTRAINTID','EFFECTIVEDATE','VERSIONNO']
    target=target[keys+['ic_factor']].drop_duplicates(keys)
    meta=meta.rename(columns={'GENCONID':'CONSTRAINTID'})
    target=target.merge(meta[keys+['CONSTRAINTTYPE','DESCRIPTION','LIMITTYPE']].drop_duplicates(keys),on=keys,how='left')
    allstates=[];alldispatch=[]
    for md in sorted((root/'evidence').iterdir()):
        dp=md/'DISPATCHLOAD.parquet';sp=md/'DISPATCHCONSTRAINT.parquet'
        if not dp.exists() or not sp.exists():
            if c.get('pilot'):continue
            raise RuntimeError(f'Incomplete evidence month {md.name}')
        dispatch=pd.read_parquet(dp);dispatch['time']=pd.to_datetime(dispatch.SETTLEMENTDATE)
        dispatch=deduplicate(dispatch,'DUID')
        for col in ['TOTALCLEARED','INITIALMW','AVAILABILITY','RAMPUPRATE','RAMPDOWNRATE']:
            dispatch[col]=pd.to_numeric(dispatch[col],errors='coerce')
        states=pd.read_parquet(sp);states['time']=pd.to_datetime(states.SETTLEMENTDATE)
        states=deduplicate(states,'CONSTRAINTID')
        for col in ['RHS','LHS','MARGINALVALUE','VIOLATIONDEGREE','GENCONID_VERSIONNO']:
            states[col]=pd.to_numeric(states[col],errors='coerce')
        states['EFFECTIVEDATE']=pd.to_datetime(states.GENCONID_EFFECTIVEDATE)
        states['VERSIONNO']=states.GENCONID_VERSIONNO
        states=states.merge(target,on=keys,how='left',validate='many_to_one')
        states['flow']=states.time.map(ic.flow)
        states['bound']=states.flow+(states.RHS-states.LHS)/states.ic_factor
        # Inequality direction is determined by relation and coefficient together.
        multiplier=np.where(states.CONSTRAINTTYPE.isin(['>=','>']),-1.,1.)
        states['direction']=np.where(states.ic_factor*multiplier>0,'upper','lower')
        states['supported_relation']=states.CONSTRAINTTYPE.isin(['<=','<','>=','>'])
        states['exact_version']=states.ic_factor.notna() & states.ic_factor.abs().gt(1e-8)
        states.loc[~(states.supported_relation & states.exact_version),'bound']=np.nan
        states['binding']=states.MARGINALVALUE.abs().gt(1e-6)
        states['ic_slack_mw']=(states.RHS-states.LHS)*multiplier/states.ic_factor.abs()
        states['near_binding']=states.ic_slack_mw.between(0,50)
        states['version_key']=states.CONSTRAINTID+'|'+states.EFFECTIVEDATE.astype(str)+'|'+states.VERSIONNO.astype(str)
        allstates.append(states);alldispatch.append(dispatch)
        print('RECONSTRUCT',md.name,len(states),'states',len(dispatch),'unit rows',flush=True)
    states=pd.concat(allstates,ignore_index=True).sort_values('time').drop_duplicates(['time','CONSTRAINTID'])
    dispatch=pd.concat(alldispatch,ignore_index=True).sort_values('time').drop_duplicates(['time','DUID'])
    if c.get('pilot'):
        present=set(dispatch.time)
        selected=selected[selected.time.map(lambda t:all(x in present for x in pd.date_range(t-pd.Timedelta(hours=2),t+pd.Timedelta(hours=2),freq='5min')))]
        print('PROVISIONAL reconstruction smoke check',len(selected),'events',flush=True)
    save(states,root/'constraint_states.parquet');save(dispatch,root/'unit_dispatch.parquet')
    # Effective mappings come from each dispatch row, not a timeless DUID/point cross join.
    dispatch_index={t:g for t,g in dispatch.groupby('time')}
    cp_index={k:g for k,g in cp.groupby(['GENCONID','EFFECTIVEDATE','VERSIONNO'])}
    state_index=states.set_index(['time','CONSTRAINTID'],drop=False)
    contributions=[];steps=[];summaries=[];equations=[]
    for ev in selected.itertuples():
        points=pd.date_range(ev.baseline_time,ev.trough_time,freq='5min')
        direction=ev.direction;capcol='export' if direction=='upper' else 'import'
        settercol='EXPORTGENCONID' if direction=='upper' else 'IMPORTGENCONID'
        sign=1. if direction=='upper' else -1.
        eqids=set();exact=0;ns=0
        for prev,t in zip(points[:-1],points[1:]):
            obs_delta=ic.at[t,capcol]-ic.at[prev,capcol]
            if not np.isfinite(obs_delta):continue
            ids=[ic.at[prev,settercol],ic.at[t,settercol]]
            ss=[]
            for tt,k in zip([prev,t],ids):
                if pd.notna(k):eqids.add(k)
                ss.append(state_index.loc[(tt,k)] if (tt,k) in state_index.index else None)
            old,new=ss;ns+=1
            row=dict(event_id=ev.event_id,time=t,observed_tightening_mw=-obs_delta,
                generator_tightening_mw=0.,rhs_tightening_mw=0.,other_lhs_tightening_mw=0.,
                switch_composite_mw=0.,unresolved_mw=-obs_delta,exact=False,complete_generator_terms=False)
            if old is not None and new is not None and np.isfinite(old.bound) and np.isfinite(new.bound):
                exact+=1;row['exact']=True
                bounddelta=sign*(new.bound-old.bound)
                row['unresolved_mw']=-obs_delta+bounddelta
                if old.version_key!=new.version_key:
                    row['switch_composite_mw']=-bounddelta
                else:
                    a=float(new.ic_factor)
                    row['rhs_tightening_mw']=-sign*(new.RHS-old.RHS)/a
                    key=(new.CONSTRAINTID,new.EFFECTIVEDATE,new.VERSIONNO)
                    terms=cp_index.get(key,pd.DataFrame())
                    p0=dispatch_index.get(prev,pd.DataFrame());p1=dispatch_index.get(t,pd.DataFrame())
                    gdelta=0.;complete=True
                    if not terms.empty:
                        for term in terms.itertuples():
                            if p0.empty or p1.empty:complete=False;continue
                            d0=p0[p0.CONNECTIONPOINTID.eq(term.CONNECTIONPOINTID)].set_index('DUID')
                            d1=p1[p1.CONNECTIONPOINTID.eq(term.CONNECTIONPOINTID)].set_index('DUID')
                            if d0.empty or set(d0.index)!=set(d1.index):complete=False;continue
                            for duid in d0.index:
                                delta=d1.at[duid,'TOTALCLEARED']-d0.at[duid,'TOTALCLEARED']
                                if not np.isfinite(delta):complete=False;continue
                                impact=sign*float(term.FACTOR)/a*delta
                                contributions.append(dict(event_id=ev.event_id,time=t,DUID=duid,constraint=new.CONSTRAINTID,
                                    version_key=new.version_key,connection_point=term.CONNECTIONPOINTID,factor=float(term.FACTOR),
                                    ic_factor=a,sensitivity=-float(term.FACTOR)/a,delta_mw=delta,
                                    initial_target_mw=d0.at[duid,'TOTALCLEARED'],final_target_mw=d1.at[duid,'TOTALCLEARED'],
                                    tightening_mw=impact,binding=bool(new.binding)))
                                gdelta+=float(term.FACTOR)*delta
                    row['generator_tightening_mw']=sign*gdelta/a
                    # This term explicitly absorbs all unrepresented LHS movements and missing generator terms.
                    other_delta=(new.LHS-old.LHS)-a*(new.flow-old.flow)-gdelta
                    row['other_lhs_tightening_mw']=sign*other_delta/a
                    row['complete_generator_terms']=complete
            steps.append(row)
        sf=pd.DataFrame([r for r in steps if r['event_id']==ev.event_id])
        summary=dict(event_id=ev.event_id,steps=ns,exact_step_share=exact/ns if ns else np.nan,
                     equation_count=len(eqids),evidence_tier='C-partial',
                     limitation='Other LHS terms are an aggregate residual; switch composite is not causal attribution.')
        if len(sf):
            for col in ['observed_tightening_mw','generator_tightening_mw','rhs_tightening_mw','other_lhs_tightening_mw','switch_composite_mw','unresolved_mw']:
                summary[col]=sf[col].sum()
            summary['complete_terms_share']=sf.complete_generator_terms.mean()
            summary['reconciliation_error_mw']=summary['observed_tightening_mw']-sum(summary[k] for k in ['generator_tightening_mw','rhs_tightening_mw','other_lhs_tightening_mw','switch_composite_mw','unresolved_mw'])
        summaries.append(summary)
        for k in eqids:
            sub=states[states.CONSTRAINTID.eq(k)&states.time.between(ev.time-pd.Timedelta(hours=2),ev.time+pd.Timedelta(hours=2))]
            for r in sub.drop_duplicates('version_key').itertuples():
                terms=cp_index.get((r.CONSTRAINTID,r.EFFECTIVEDATE,r.VERSIONNO),pd.DataFrame())
                expression=f'{r.ic_factor:g} * F_VIC_to_NSW' if pd.notna(r.ic_factor) else 'unknown IC factor * F'
                if len(terms):expression+=' '+' '.join(f'{x.FACTOR:+g} * P[{x.CONNECTIONPOINTID}]' for x in terms.itertuples())
                other=factors[(factors.GENCONID==k)&(factors.EFFECTIVEDATE==r.EFFECTIVEDATE)&(factors.VERSIONNO==r.VERSIONNO)&~factors.INTERCONNECTORID.eq(c['interconnector'])]
                if len(other):expression+=' '+' '.join(f'{x.FACTOR:+g} * F[{x.INTERCONNECTORID}]' for x in other.itertuples())
                expression+=f' + Z_unrepresented {r.CONSTRAINTTYPE} RHS(t)'
                equations.append(dict(event_id=ev.event_id,constraint=k,version_key=r.version_key,
                    equation=expression,description=r.DESCRIPTION,limit_type=r.LIMITTYPE,
                    exact_version=bool(r.exact_version),Z_note='Z includes unsupported non-energy/region terms if present; not assumed zero'))
    save(pd.DataFrame(contributions),root/'generator_contributions.parquet')
    save(pd.DataFrame(steps),root/'attribution_steps.parquet')
    save(pd.DataFrame(summaries),root/'event_attribution.parquet')
    save(pd.DataFrame(equations),root/'event_equations.parquet')
    dump(root/'reconstruction_quality.json',{'selected_events':len(selected),'events_reconstructed':len(summaries),
        'constraint_rows':len(states),'dispatch_rows':len(dispatch),'contribution_rows':len(contributions),
        'exact_version_share':float(states.exact_version.mean()),
        'maximum_accounting_error_mw':float(pd.DataFrame(summaries).reconciliation_error_mw.abs().max()),
        'not_claimed':['causal price attribution','full security constrained dispatch replay','separate identification of every residual LHS term']})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(DEFAULT));a=p.parse_args();reconstruct(settings(a.config))
