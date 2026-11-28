"""Replay the effective SA MAXG expression using independent dispatch XML labels."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
import pandas as pd
from lxml import etree
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT))
from scripts.rhs_cases import selected_files,BASE
EQ="V::S_NIL_MAXG_1"
SHARED=['X_SA_TOTAL_DPV','X_SA_MAXG_ST_DS','X_SA_METG_ST_DS','X_SA_DAY','SA_METRO_GEN_ON']
def rhs(row, pv=None, **changed):
    r=dict(row);r.update(changed)
    asefs=r['SA_ASEFS2'] if pv is None else pv
    override=r['SA_ASEFS2_DEF_HDRESS']
    override=(override if override<10000 else 0)*r['PERIOD_ID_01']
    dpv=override if override>0 else asefs*(1+65/2228)+r['SA_SAPN_CONTRL_PV']
    metro=(1.2*r['metro_max']+.36*dpv)*r['day_gate']*r['metro_gate']
    plant=1.2*r['state_max']
    if r['NO_OF_BLKRG_CAP_IS']<=1:return 10000,'capacitor bypass',dpv
    return r['linear_base']-max(plant,metro),('metro' if metro>plant else 'state'),dpv
def readcase(raw,name,url):
    xml=etree.fromstring(raw)
    i=xml.find('NemSpdInputs');out=xml.find('NemSpdOutputs')
    period=i.find('.//Period')
    sol=out.find(f'.//ConstraintSolution[@ConstraintID="{EQ}"][@Intervention="0"]')
    if sol is None:return
    assert sol.get('Version')=='20251208000000_1' and i.find('Case').get('Intervention')=='False'
    sc={s.get('SpdID'):float(s.get('Value')) for s in i.iter('ScadaValues') if s.get('Can_Use_Value')=='True'}
    en={s.get('SpdID'):float(s.get('Value')) for s in period.iter('EnteredValuePeriod') if s.get('Value') is not None}
    trader={x.get('TraderID'):float(x.find('.//TraderInitialCondition[@InitialConditionID="InitialMW"]').get('Value')) for x in i.iter('Trader') if x.find('.//TraderInitialCondition[@InitialConditionID="InitialMW"]') is not None}
    ic={x.get('InterconnectorID'):float(x.find('.//InterconnectorInitialCondition[@InitialConditionID="InitialMW"]').get('Value')) for x in i.iter('Interconnector')}
    equations={x.get('EquationID'):x for x in i.iter('GenericEquation') if x.get('EquationID') in SHARED}
    inputs={'T':trader,'I':ic,'A':sc,'E':en}
    def largest(id):
        stack=[0]
        for s in equations[id].iter('RHSTerm'):
            t=s.get('SpdType');op=s.get('Operation');tag=s.get('SpdID')
            if t=='U':
                assert op=='MAX';v=stack.pop();stack[-1]=max(stack[-1],v);continue
            factor=float(s.get('Multiplier'));v=factor if t=='C' else factor*inputs[t].get(tag,float(s.get('Default')))
            if op=='PUSH':stack.append(v)
            elif op=='MAX':stack[-1]=max(stack[-1],v)
            else:
                assert op is None;stack[-1]+=v
        assert len(stack)==1;return stack[0]
    r=dict(end=period.get('PeriodID'),source=url,member=name,xml_sha256=hashlib.sha256(raw).hexdigest(),published_rhs=float(sol.get('RHS')),marginal=float(sol.get('MarginalValue')),state_max=largest(SHARED[1]),metro_max=largest(SHARED[2]))
    r.update({k:en[k] for k in ['PERIOD_ID_01','SA_ASEFS2']})
    r.update({k:sc[k] for k in ['NO_OF_BLKRG_CAP_IS','SA_SAPN_CONTRL_PV','SA_ASEFS2_DEF_HDRESS']})
    r['metro_gate']=int(any(trader.get(x.get('SpdID'),0)>0 for x in equations[SHARED[4]].iter('RHSTerm') if x.get('SpdType')=='T'))
    r['day_gate']=int(any(sc.get(x,0)>0 for x in ['BNGSF1_IRAD_H','BNGSF2_IRAD_H','TBSF1_IRAD_H','NO_TBSF1_INV']))
    r['linear_base']=898+sc['MW_BU_6F']+2.13*sc['SE_SUMLOAD_MW']-.14*sum(trader.get(x,0) for x in ['TB2SF1','TB2B1','TBSF1'])-.17*sum(trader[x] for x in ['LADBROK1','LADBROK2'])-25+27.42+147.7
    r['calculated_rhs'],r['active_branch'],r['dpv']=rhs(r)
    for field in ['SA_ASEFS2','SA_SAPN_CONTRL_PV','PERIOD_ID_01','SA_ASEFS2_DEF_HDRESS']:
        r[field+'_plus_one_effect']=rhs(r,**{field:r[field]+1})[0]-r['calculated_rhs']
    for label,lookup in [('force_500_override',{'SA_ASEFS2_DEF_HDRESS':500,'PERIOD_ID_01':1}),('disable_metro',{'metro_gate':0}),('one_capacitor',{'NO_OF_BLKRG_CAP_IS':1}),('joint_PV100_controlled10',{'SA_ASEFS2':r['SA_ASEFS2']+100,'SA_SAPN_CONTRL_PV':r['SA_SAPN_CONTRL_PV']+10})]:
        r[label]=rhs(r,**lookup)[0]-r['calculated_rhs']
    return r
if __name__=='__main__':
    rows=[]
    for day,start in [('20260201',1),('20260215',97),('20260219',73)]:
        url=BASE+f'NemSpdOutputs_{day}_loaded.zip'
        rows.extend(readcase(raw,name,url) for name,raw in selected_files(day,range(start,start+24)))
    d=pd.DataFrame([r for r in rows if r]);d.to_csv(OUT/'case_replays.csv',index=False)
    print(d.groupby('active_branch').agg(n=('end','size'),sun=('day_gate','sum')))
    err=(d.calculated_rhs-d.published_rhs).abs()
    print(d[['end','published_rhs','calculated_rhs','state_max','metro_max','day_gate','metro_gate','dpv']][err>0.00005].head());print(err.max())
    assert len(d)==72 and err.max()<0.00005
