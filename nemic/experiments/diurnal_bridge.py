"""Rerun the legacy candidate/blend policy on the corrected v2 observations."""
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .core import Store,load_config,digest,fingerprint
from .data import connector_data,base_frame,design
from .models import Candidate,grid,forecast_pressure
from .runner import POINT_RECIPES,save_model
from .validation import folds
from .diurnal import origin_weights,metrics
from .diurnal_runner import CONFIG,frame


def run_bridge(config_path=CONFIG):
    c=load_config(config_path);store=Store(c)
    d=connector_data(c,c['connectors'][0]);d['base']=base_frame(d)
    with threadpool_limits(limits=2):
        for fold in folds(c):
            for target in ('export_tight','import_tight'):
                folder=store.root/'bridge'/fold.name/target
                ident=str(folder.relative_to(store.root)); fp=fingerprint([fold.dict(),target,digest(__file__)])
                if store.valid(ident,fp):continue
                _,meta,masks=frame(c,c['connectors'][0],fold,0,target)
                o=d['y'].index.get_indexer(meta.origin);h=meta.lead.to_numpy()
                forecast=forecast_pressure(d,fold,4)
                recipes={r:design(d,o,h,r,forecast) for _,_,r in POINT_RECIPES}
                tr,va,te=[masks[n] for n in ('train','select','evaluate')]
                actual=meta.actual.to_numpy();anchor=meta.anchor.to_numpy()
                predictions={};selections=[]
                rng=np.random.default_rng(741)
                origin_choice=dict(zip(meta.origin.unique(),rng.choice([1,2,4,8,12],meta.origin.nunique())))
                sampled=np.array([lead==origin_choice[origin] for origin,lead in zip(meta.origin,h)])
                for sampling in ('one_lead','all_leads'):
                    fitted={};validation={};policy_predictions={}
                    train=tr & sampled if sampling=='one_lead' else tr
                    weights=origin_weights(meta.loc[train,'origin'])
                    for name,family,recipe in POINT_RECIPES:
                        best=None
                        for parameters in grid(family,c):
                            model=Candidate(family,parameters)
                            model.fit(recipes[recipe].loc[train],actual[train]-anchor[train],sample_weight=weights)
                            p=anchor+model.predict(recipes[recipe])
                            loss=float(np.average(abs(actual[va]-p[va]),weights=origin_weights(meta.loc[va,'origin'])))
                            if best is None or loss<best[0]:best=(loss,model,p,parameters)
                        validation[name]=best[0];fitted[name]=(best[1],recipe);policy_predictions[name]=best[2]
                    simple=min([n for n in fitted if not n.startswith('boost')],key=validation.get)
                    boosted=min([n for n in fitted if n.startswith('boost')],key=validation.get)
                    weight=min([0,.25,.5,.75,1],key=lambda w:np.average(abs(actual[va]-(w*policy_predictions[simple][va]+(1-w)*policy_predictions[boosted][va])),weights=origin_weights(meta.loc[va,'origin'])))
                    policy_predictions['blend']=weight*policy_predictions[simple]+(1-weight)*policy_predictions[boosted]
                    validation['blend']=float(np.average(abs(actual[va]-policy_predictions['blend'][va]),weights=origin_weights(meta.loc[va,'origin'])))
                    policy_predictions['persistence']=anchor;validation['persistence']=float(np.average(abs(actual[va]-anchor[va]),weights=origin_weights(meta.loc[va,'origin'])))
                    winner=min(validation,key=validation.get)
                    predictions[sampling]=policy_predictions[winner][te]
                    selections.append({'sampling':sampling,'winner':winner,'validation':validation,
                                       'scores':metrics(actual[te],predictions[sampling]),'train_pairs':int(train.sum())})
                    save_model(store,folder/(sampling+'.joblib'),{'models':fitted,'winner':winner,'blend_weight':weight,'simple':simple,'boost':boosted})
                evaluated=meta.loc[te].copy()
                for name,p in predictions.items():evaluated[name]=p
                store.parquet(folder/'predictions.parquet',evaluated)
                store.json(folder/'result.json',{'fold':fold.dict(),'target':target,'selection':selections,
                    'claim':'Legacy fixed-grid candidate/blend procedure refitted with corrected maturity; one-lead/all-lead sampling bridge'})
                store.complete(ident,fp,folder/'result.json')
                print('BRIDGE',fold.name,target,flush=True)


if __name__=='__main__':run_bridge()
