import argparse
import json
from .core import load_config,DEFAULT,clean

def main():
    p=argparse.ArgumentParser(description='Replicable interconnector forecasting experiments')
    p.add_argument('command',choices=['inventory','plan','run','report','shadow','score-shadow','recover'])
    p.add_argument('--config',default=str(DEFAULT));p.add_argument('--kind',default='all',choices=['all','numeric','events'])
    p.add_argument('--ic');p.add_argument('--fold');p.add_argument('--limit',type=int)
    args=p.parse_args();c=load_config(args.config)
    if args.command=='inventory':
        from .data import inventory
        d=inventory(c);print(json.dumps(clean({k:v for k,v in d.items() if k not in ['sources','code']}),indent=2))
    elif args.command=='plan':
        from .data import inventory,registry
        from .validation import folds
        d=inventory(c,False);print(json.dumps(clean({'connectors':d['capabilities'],'folds':[x.dict() for x in folds(c)],'registry':registry(),'numeric_jobs':len(c['connectors'])*len(folds(c))*len(c['bands']),'event_jobs':len(c['connectors'])*len(folds(c)),'additional_bytes':c['limits']['additional_bytes']}),indent=2))
    elif args.command=='run':
        from .runner import run
        run(c,args.kind,args.ic,args.fold)
    elif args.command=='report':
        from .reports import build
        build(c)
    elif args.command=='recover':
        from .acquire import recover
        recover(c,args.limit)
    else:
        from .shadow import run_shadow,score_shadow
        (run_shadow if args.command=='shadow' else score_shadow)(c)

if __name__=='__main__':main()
