"""Open the local selector against the retained conditional research bundle."""
from pathlib import Path
import argparse
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"packages/nemic-regimes/src"))
from nemic_regimes import load_bundle
from nemic_regimes.web import serve

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=8061)
    parser.add_argument("--bundle",type=Path,default=ROOT/"data/forecast_experiments/conditional_regimes_v1/bundle")
    args=parser.parse_args()
    serve(load_bundle(args.bundle),port=args.port)
