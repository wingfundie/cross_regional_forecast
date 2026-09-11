"""Resume the complete research pipeline using retained downloads and checkpoints."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
STEPS=[['-m','nemic.ingest'],['-m','nemic.weather'],['-m','nemic.prepare'],
       ['-m','nemic.model'],['-m','nemic.model','validate'],['-m','nemic.backtest'],
       ['-m','nemic.benchmark_download'],['-m','nemic.aemo_benchmark'],['-m','nemic.scenario'],
       ['-m','unittest','discover','-s','tests','-v'],['scripts/verify_complete.py'],['-m','nemic.report']]
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--from-step',type=int,default=1);a=p.parse_args()
    for idx,command in enumerate(STEPS,1):
        if idx<a.from_step:continue
        print(f'STEP {idx}/{len(STEPS)} '+ ' '.join(command),flush=True)
        subprocess.run([sys.executable,*command],cwd=ROOT,check=True)
