"""Invoke with python -I to check an independently installed wheel."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import runpy
import sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("installed",type=Path)
parser.add_argument("bundle",type=Path)
parser.add_argument("output",type=Path)
parser.add_argument("--wheel",type=Path)
args=parser.parse_args()
sys.path.insert(0,str(args.installed.resolve()))
import nemic_regimes
import pandas as pd

assert Path(nemic_regimes.__file__).is_relative_to(args.installed.resolve())
bundle=nemic_regimes.load_bundle(args.bundle)
q={"connector":"VNI","direction":"forward","era":"pre_pec_market","quarter":1,"half_hour":24,"method":"table"}
single=bundle.select(q)
assert single["status"]=="supported_table"
profile=bundle.profile(1,q)
assert len(profile)==48
assert profile.loc[24,"p50_mw"]==single["p50_mw"]
assert len(bundle.select(pd.DataFrame([q,q])))==2
assert len(bundle.select([q,q]))==2
assert nemic_regimes.select(bundle,q)==single
assert bundle.explain(q)["p50_mw"]==single["p50_mw"]
model=bundle.select({**q,"method":"additive","allow_extrapolation":True})
assert model["status"]=="modelled_extrapolation" and model["p50_mw"] is not None
boosted=bundle.select({**q,"method":"boosting","allow_extrapolation":True})
assert boosted["status"]=="modelled_extrapolation" and boosted["p50_mw"] is not None
args.output.mkdir(parents=True,exist_ok=True)
bundle.export(profile,args.output/"installed_profile.csv")
bundle.export(profile,args.output/"installed_profile.json")
query=args.output/"cli_query.json";query.write_text(json.dumps(q),encoding="utf-8")
sys.argv=["nemic-regimes","select","--bundle",str(args.bundle.resolve()),"--conditions",str(query.resolve()),"--output",str((args.output/"cli_result.json").resolve())]
runpy.run_module("nemic_regimes",run_name="__main__")
assert json.loads((args.output/"cli_result.json").read_text())["status"]=="supported_table"
result={"passed":True,"completed":datetime.now(timezone.utc).isoformat(),"version":nemic_regimes.__version__,
        "installed_module":str(Path(nemic_regimes.__file__).resolve()),"bundle_id":bundle.metadata["bundle_id"],
        "checks":["isolated import from installed wheel","bundle hashes","strict table","48 half-hours","DataFrame and JSON batches","public helpers","explanation","additive and boosted extrapolation","CSV and JSON export","CLI shares evidence layer"],
        "runtime_versions":{name:importlib.metadata.version(name) for name in ("numpy","pandas","pyarrow","scikit-learn","lightgbm","joblib")},
        "wheel_sha256":hashlib.sha256(args.wheel.read_bytes()).hexdigest() if args.wheel else None,
        "manifest_sha256":hashlib.sha256((args.bundle/"manifest.json").read_bytes()).hexdigest()}
(args.output.parent/"package_smoke.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
