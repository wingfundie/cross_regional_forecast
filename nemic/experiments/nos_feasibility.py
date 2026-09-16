"""Pre-model historical NOS support and paired recall-power audit."""
import json
import numpy as np
import pandas as pd

from .core import Store,load_config
from .data import connector_data
from .diurnal import mature_masks
from .diurnal_runner import CONFIG
from .events import detect,incidents,match
from .validation import folds


def paired_power(n,baseline,gain,correlation,replicates=4000,seed=741):
    candidate=min(baseline+gain,.99)
    independent=baseline*candidate
    maximum=min(baseline,candidate)
    overlap=independent+correlation*(maximum-independent)
    p10=candidate-overlap;p01=baseline-overlap
    probabilities=[overlap,p10,p01,max(0.,1-overlap-p10-p01)]
    rng=np.random.default_rng(seed+int(n*13+baseline*100+gain*1000+correlation*10))
    draws=rng.multinomial(n,probabilities,size=replicates)
    discordant=draws[:,1]+draws[:,2]
    statistic=np.divide(draws[:,1]-draws[:,2],np.sqrt(discordant),out=np.zeros(replicates),where=discordant>0)
    return float(np.mean(statistic>1.96))


def build_feasibility(config_path=CONFIG):
    c=load_config(config_path);store=Store(c)
    coverage=json.loads((store.root/'nos/coverage_audit.json').read_text())
    eligible={r['fold']:r for r in coverage['folds'] if r['eligible']}
    exposure=pd.read_parquet(store.root/'nos/exposure.parquet')
    exposure=exposure[exposure.lead.eq(4)].drop_duplicates('origin').set_index('origin')
    d=connector_data(c,c['connectors'][0]);idx=d['y'].index
    known=exposure.nos_report_generated.reindex(idx).notna()
    generated=exposure.nos_report_generated.reindex(idx)
    known &= generated.add(pd.Timedelta(minutes=30)).le(idx)
    known &= (idx-generated-pd.Timedelta(minutes=30))<=pd.Timedelta(minutes=90)
    support=[]
    for fold in folds(c):
        if fold.name not in eligible:continue
        masks=mature_masks(idx,idx+pd.Timedelta(minutes=120),fold)
        for direction in ('export','import'):
            detector,_=detect(d['raw'][direction],fold.train_start,fold.train_end)
            catalogue=incidents(detector)
            row={'fold':fold.name,'direction':direction,'common_source_fraction':float(known[masks['evaluate']].mean())}
            for partition in ('train','select','calibrate','alert','evaluate'):
                origins=idx[masks[partition]&np.asarray(known)]
                row[partition+'_incidents']=match(origins,np.zeros(len(origins)),1.,catalogue)['incidents']
                row[partition+'_origins']=len(origins)
            support.append(row)
    design_n={direction:int(sum(r['select_incidents']+r['calibrate_incidents']+r['alert_incidents']
        for r in support if r['direction']==direction)) for direction in ('export','import')}
    power=[]
    for direction,n in design_n.items():
        for baseline in (.2,.4,.6):
            for correlation in (0.,.5):
                for gain in (.05,.1,.15,.2,.25,.3):
                    power.append({'direction':direction,'incidents':n,'baseline_recall':baseline,
                        'gain_pp':int(gain*100),'discordance_dependence':correlation,
                        'power':paired_power(n,baseline,gain,correlation)})
    minimum_detectable=[]
    for (direction,baseline,dependence),f in pd.DataFrame(power).groupby(['direction','baseline_recall','discordance_dependence']):
        good=f[f.power.ge(.8)]
        minimum_detectable.append({'direction':direction,'baseline_recall':baseline,
            'discordance_dependence':dependence,'minimum_detectable_gain_pp':int(good.gain_pp.min()) if len(good) else None})
    positive=exposure.nos_count.fillna(0).gt(0)
    chains=int((positive&~positive.shift(fill_value=False)).sum())
    payload={'historical_gate':coverage['historical_gate'],'eligible_folds':len(eligible),'support':support,
        'pre_evaluation_design_incidents':design_n,'independent_scheduled_exposure_chains':chains,
        'risk_floor':{d:('passes descriptive 30-incident floor' if n>=30 else 'exploratory: below 30 incidents') for d,n in design_n.items()},
        'power_grid':power,'minimum_detectable_gain_80pct':minimum_detectable,
        'power_method':'Paired multinomial detection simulation; one-sided normal McNemar statistic at alpha 0.025; selection+calibration+alert incidents only; 4,000 draws.',
        'forward_fundamentals_interaction':{'status':'unavailable','reason':'Original issue vintages for scheduled generator availability and the required full-period generation forecast stream are not established.'},
        'claim':'Design feasibility only. Evaluation incident counts are descriptive and do not set the power assumptions.'}
    store.json(store.root/'nos/nos_feasibility.json',payload)
    return payload


if __name__=='__main__':print(json.dumps(build_feasibility(),indent=2))
