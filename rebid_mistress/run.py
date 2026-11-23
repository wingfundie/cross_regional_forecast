"""Run/rebuild the local event study. No publishing or forecast routing."""
import sys,argparse,json,os,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rebid_mistress.core import *

def stage_dependencies(stage):
    names={'acquire':['acquire.py','context.py','inspect_sources.py'],
           'reconstruct':['reconstruct.py','enrich.py'],
           'analyse':['analyse.py'],
           'report':['report.py','cases.py','portfolio_digest.py','explorer.js','report_extra.css','theme/report_theme.py','theme/report.css'],
           'validate':['validate.py','browser_qa.py']}
    paths=[ROOT/p for p in ['core.py','config.json','METHODOLOGY.md']+names[stage]]
    if stage=='acquire':paths+=list(RAW.glob('*.json'))
    if stage in ['reconstruct','analyse']:paths+=list(TABLES.glob('*.parquet'))
    if stage=='analyse':paths+=[RESULTS/(n+'.parquet') for n in ['segments','revisions','effective','snapshots']]
    if stage in ['report','validate']:paths+=list(RESULTS.glob('*'))+[TABLES/'inventory.parquet',TABLES/'headers.parquet']
    if stage=='report':paths+=list((ROOT/'data/arrays').glob('*.npz'))+[STATE/(n+'.json') for n in ['analysis','reconstruction','forecast','registry_sources','enrichment','market_notices']]
    if stage=='validate':paths+=list(REPORTS.glob('*'))+[STATE/(n+'.json') for n in ['report_manifest','browser_qa','repository_tests']]
    return {str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file()}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--stage',choices=['all','acquire','reconstruct','analyse','report','validate'],default='all');parser.add_argument('--force',action='store_true');args=parser.parse_args()
    init();lock=STATE/'worker.json'
    import psutil
    if lock.exists():
        owner=json.loads(lock.read_text())
        if psutil.pid_exists(owner['pid']):
            p=psutil.Process(owner['pid'])
            if abs(p.create_time()-owner['created'])<1:raise SystemExit('A healthy study worker already owns the runner')
    write_json(lock,dict(pid=os.getpid(),created=psutil.Process().create_time()))
    try:
        for stage in (['acquire','reconstruct','analyse','report','validate'] if args.stage=='all' else [args.stage]):
            from importlib import import_module
            module=import_module('rebid_mistress.'+stage)
            dependencies=stage_dependencies(stage)
            signature=hashlib.sha256(json.dumps(dependencies,sort_keys=True).encode()).hexdigest()
            checkpoint=STATE/(stage+'_checkpoint.json')
            if checkpoint.exists() and not args.force:
                old=json.loads(checkpoint.read_text())
                if old.get('signature')==signature and all(Path(p).exists() and sha(p)==h for p,h in old.get('outputs',{}).items()):
                    print(stage,'verified cached stage',flush=True);continue
            write_json(STATE/'status.json',dict(stage=stage,status='active',pid=os.getpid(),started_utc=datetime.now(timezone.utc).isoformat()))
            print('STAGE',stage,flush=True)
            (module.acquire if stage=='acquire' else module.run)()
            if stage=='acquire':
                from rebid_mistress.context import run as context_run
                context_run()
            if stage=='reconstruct':
                from rebid_mistress.enrich import run as enrich_run
                enrich_run()
            output_dir=TABLES if stage=='acquire' else REPORTS if stage=='report' else RESULTS
            outputs={str(p):sha(p) for p in output_dir.glob('*') if p.is_file()}
            write_json(checkpoint,dict(signature=signature,dependencies=dependencies,outputs=outputs,completed_utc=datetime.now(timezone.utc).isoformat()))
            write_json(STATE/'status.json',dict(stage=stage,status='completed',completed_utc=datetime.now(timezone.utc).isoformat()))
    except Exception as exc:
        write_json(STATE/'status.json',dict(stage=stage,status='failed',error=str(exc)));raise
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':main()
