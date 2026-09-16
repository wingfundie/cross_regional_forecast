import argparse
import json
from .core import load_config,DEFAULT,clean

def main():
    p=argparse.ArgumentParser(description='Replicable interconnector forecasting experiments')
    p.add_argument('command',choices=['inventory','plan','run','report','shadow','score-shadow','recover',
        'inventory-nos','recover-nos','audit-nos','analyse-nos-impacts','audit-nos-feasibility','run-diurnal','run-diurnal-risk',
        'run-nos-models','run-nos-risk','run-diurnal-fixed','run-diurnal-extensions','run-diurnal-curves','run-diurnal-refinements','run-diurnal-bridge','explain-diurnal','explain-nos','refit-diurnal','diurnal-statistics'])
    p.add_argument('--config',default=str(DEFAULT));p.add_argument('--kind',default='all',choices=['all','numeric','events'])
    p.add_argument('--ic');p.add_argument('--fold');p.add_argument('--limit',type=int)
    p.add_argument('--stage',choices=['primary','extensions'],default='primary')
    args=p.parse_args();c=load_config(args.config)
    if args.command in ('inventory-nos','recover-nos','audit-nos'):
        from .nos import inventory_nos,recover_nos,audit_nos
        if c.get('schema_version')!=2:raise ValueError('NOS stages require an explicit v2 configuration')
        d={'inventory-nos':lambda:inventory_nos(c),'recover-nos':lambda:recover_nos(c,args.limit),'audit-nos':lambda:audit_nos(c)}[args.command]()
        print(json.dumps(clean(d),indent=2))
    elif args.command=='analyse-nos-impacts':
        from .nos_analysis import build_exposure,impact_report,matched_impacts
        build_exposure(c);impact_report(c);print(json.dumps(clean(matched_impacts(c)),indent=2))
    elif args.command=='audit-nos-feasibility':
        from .nos_feasibility import build_feasibility
        print(json.dumps(clean(build_feasibility(args.config)),indent=2))
    elif args.command=='run-diurnal':
        from .diurnal_runner import run
        run(args.config,args.stage,args.fold)
    elif args.command=='run-diurnal-risk':
        from .diurnal_risk import run_risk
        run_risk(args.config)
    elif args.command=='run-nos-models':
        from .nos_runner import run_nos
        run_nos(args.config)
    elif args.command=='run-nos-risk':
        from .nos_risk import run_nos_risk
        run_nos_risk(args.config)
    elif args.command=='run-diurnal-extensions':
        from .diurnal_extensions import run_extensions
        run_extensions(args.config,args.fold)
    elif args.command=='run-diurnal-fixed':
        from .diurnal_fixed import run_fixed
        run_fixed(args.config)
    elif args.command=='run-diurnal-refinements':
        from .diurnal_refinements import run_refinements
        run_refinements(args.config)
    elif args.command=='run-diurnal-curves':
        from .diurnal_curves import run_curves
        run_curves(args.config)
    elif args.command=='run-diurnal-bridge':
        from .diurnal_bridge import run_bridge
        run_bridge(args.config)
    elif args.command=='explain-diurnal':
        from .diurnal_explain import run
        run(args.config)
    elif args.command=='explain-nos':
        from .nos_explain import run
        run(args.config)
    elif args.command=='refit-diurnal':
        from .diurnal_export import refit_final
        refit_final(args.config)
    elif args.command=='diurnal-statistics':
        from .diurnal_statistics import run_statistics
        run_statistics(args.config)
    elif args.command=='inventory':
        from .data import inventory
        d=inventory(c);print(json.dumps(clean({k:v for k,v in d.items() if k not in ['sources','code']}),indent=2))
    elif args.command=='plan':
        from .data import inventory,registry
        from .validation import folds
        d=inventory(c,False);print(json.dumps(clean({'connectors':d['capabilities'],'folds':[x.dict() for x in folds(c)],'registry':registry(),'numeric_jobs':len(c['connectors'])*len(folds(c))*len(c['bands']),'event_jobs':len(c['connectors'])*len(folds(c)),'additional_bytes':c['limits']['additional_bytes']}),indent=2))
    elif args.command=='run':
        if c.get('schema_version')==2:raise ValueError('Use run-diurnal for schema v2; the legacy runner preserves v1 semantics')
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
