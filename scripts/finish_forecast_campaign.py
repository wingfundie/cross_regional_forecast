"""Finish a running experiment campaign and rebuild its presentation.

This is a one-shot continuation, not a scheduled task. It can attach only to
the explicitly supplied experiment process. It never publishes or deploys.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import psutil
    from nemic.experiments.core import load_config, Store
    from nemic.experiments.data import inventory
    from nemic.experiments.runner import run
    from nemic.experiments.benchmarks import aemo, pooled
    from nemic.experiments.reports import build, collect
    from nemic.experiments.validation import folds
    parser=argparse.ArgumentParser();parser.add_argument('--wait-pid',type=int)
    args=parser.parse_args();c=load_config();store=Store(c)
    expected=len(c['connectors'])*len(folds(c))*(len(c['bands'])+1)
    def status(stage,**extra):
        store.json(store.root/'continuation_status.json',{'stage':stage,**extra})
        print(stage,extra,flush=True)
    try:
        if args.wait_pid:
            try:
                proc=psutil.Process(args.wait_pid)
                command=' '.join(proc.cmdline())
                if '-m nemic.experiments run' not in command:
                    raise ValueError('Supplied PID is not an experiment campaign')
                status('waiting_for_existing_campaign',pid=args.wait_pid)
                refresh=time.monotonic()+300
                while proc.is_running() and proc.status()!=psutil.STATUS_ZOMBIE:
                    try:proc.wait(timeout=30);break
                    except psutil.TimeoutExpired:pass
                    if time.monotonic()>=refresh:
                        build(c)
                        status('waiting_for_existing_campaign',pid=args.wait_pid,
                            completed=len(collect(c)[0]),expected=expected)
                        refresh=time.monotonic()+300
            except psutil.NoSuchProcess:pass
        # A 12-hour checkpoint or a failed job is resumed. Three attempts bound
        # repeated deterministic failures; checksum-valid trials are skipped.
        for attempt in range(3):
            trials,stale,_=collect(c)
            if len(trials)==expected:break
            status('resuming_model_campaign',attempt=attempt+1,completed=len(trials),expected=expected)
            try:run(c)
            except RuntimeError as exc:status('model_batch_failed',error=str(exc))
        trials,stale,inv=collect(c)
        if len(trials)!=expected:
            build(c);raise RuntimeError(f'Only {len(trials)}/{expected} model jobs completed; inspect batch_summary.json')
        status('aemo_benchmarks');aemo(c)
        status('pooled_linear_challenger');pooled(c,inv)
        status('building_reports');build(c)
        status('model_campaign_and_reports_complete',completed=len(trials),expected=expected,
            remaining_extensions=['individual-generator forecast integration','100 deep forecast cases per connector',
                'historical publication-vintage verification','matured live shadow evaluation'])
    except Exception as exc:
        status('failed',error=repr(exc));raise


if __name__=='__main__':main()
