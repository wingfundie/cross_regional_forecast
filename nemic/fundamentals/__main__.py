"""Manual, resumable campaign entrypoint. No network access on import."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from .tracking import Ledger,DEFAULT,atomic
from .sources import inventory,acquire,coverage_audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['status','inventory','acquire','weather','coal','prepare-indexes','features','train','assess','test','report','benchmark','run'])
    parser.add_argument('--config',default=str(DEFAULT))
    parser.add_argument('--scope',choices=['CURRENT','ARCHIVE'],default='CURRENT')
    parser.add_argument('--limit',type=int,default=1,help='Archives per product; 0 requests all eligible archive files')
    parser.add_argument('--weather-run',default='2026-08-01T00:00Z')
    parser.add_argument('--connector',choices=['QNI','VNI','all'],default='QNI')
    parser.add_argument('--max-origins',type=int,help='Feature pilot only; excluded from full training')
    parser.add_argument('--workers',type=int,default=2,choices=[1,2])
    parser.add_argument('--resume',action='store_true',help='Resume verified partitions and cells')
    parser.add_argument('--table',type=Path)
    args=parser.parse_args();ledger=Ledger(args.config)
    if args.command=='status':ledger.reconcile();print((ledger.root/'STATUS.md').read_text());return
    if args.command=='inventory':print(json.dumps(inventory(ledger),indent=2));return
    if args.command=='acquire':
        if not (ledger.data/'inventory.json').exists():inventory(ledger)
        print(acquire(ledger,args.scope,args.limit));return
    if args.command=='weather':
        from .weather import acquire_weather
        print(acquire_weather(ledger,args.weather_run));return
    if args.command=='coal':
        from .coal import prepare
        print(prepare(ledger));return
    if args.command=='prepare-indexes':
        from .indexes import prepare_indexes
        print(prepare_indexes(ledger,resume=True));return
    if args.command=='features':
        from .modelling import build_table,build_tables_parallel
        if args.connector=='all':print(build_tables_parallel(args.config,('VNI','QNI'),args.max_origins,args.workers))
        else:print(build_table(ledger,args.connector,args.max_origins))
        return
    if args.command=='benchmark':
        from .benchmark import benchmark
        print(benchmark(ledger,args.workers));return
    if args.command=='train':
        from .modelling import fit_table,fit_tables_parallel
        if args.table is not None:result=fit_table(ledger,args.table)
        else:
            paths=[ledger.data/'features'/name/'table.parquet' for name in ('VNI','QNI')]
            missing=[str(p) for p in paths if not p.exists()]
            if missing:parser.error('missing verified feature tables: '+', '.join(missing))
            # Cross-connector training is never parallel: VNI completes first.
            result=[fit_table(ledger,path) for path in paths]
        print(json.dumps(result,default=str));return
    if args.command=='test':
        result=subprocess.run([sys.executable,'-m','pytest','tests/test_fundamentals_v3.py','-q'],capture_output=True,text=True)
        out=ledger.root/'logs/tests.txt';atomic(out,result.stdout+result.stderr)
        ledger.record('engineering/tests','completed' if result.returncode==0 else 'failed','Temporal/feature/tracking invariant tests',[out] if result.returncode==0 else [])
        print(result.stdout);raise SystemExit(result.returncode)
    if args.command=='report':
        from .reports import render
        print(render(ledger));return
    if args.command=='assess':
        from .assessment import assess
        print(assess(ledger));return
    from .campaign import run
    run(ledger)


if __name__=='__main__':main()
