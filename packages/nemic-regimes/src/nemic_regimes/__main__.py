from __future__ import annotations
import argparse
import json
from pathlib import Path
from . import load_bundle


def main():
    parser=argparse.ArgumentParser(description="Conditional NEM reported-limit analogues")
    parser.add_argument("command",choices=["select","profile","serve","collect-grid","collect-weather"])
    parser.add_argument("--bundle",type=Path)
    parser.add_argument("--conditions",type=Path)
    parser.add_argument("--quarter",type=int,default=1)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--port",type=int,default=8061)
    parser.add_argument("--connector",default="VNI")
    parser.add_argument("--direction",default="forward")
    parser.add_argument("--run")
    parser.add_argument("--delivery")
    args=parser.parse_args()
    if args.command.startswith("collect-"):
        from .collect import latest_grid,weather
        fn=latest_grid if args.command=="collect-grid" else weather
        kwargs={"connector":args.connector,"direction":args.direction,"output":str(args.output or "regime_inputs")}
        if args.command=="collect-weather":kwargs.update(run=args.run,delivery=args.delivery)
        print(json.dumps(fn(**kwargs),indent=2));return
    if not args.bundle:parser.error("--bundle is required")
    bundle=load_bundle(args.bundle)
    if args.command=="serve":
        from .web import serve
        serve(bundle,port=args.port);return
    conditions=json.loads(args.conditions.read_text(encoding="utf-8")) if args.conditions else {"connector":args.connector,"direction":args.direction}
    result=bundle.profile(args.quarter,conditions) if args.command=="profile" else bundle.select(conditions)
    if args.output:bundle.export(result,args.output)
    else:
        if hasattr(result,"to_dict"):result=result.to_dict("records")
        print(json.dumps(result,indent=2,allow_nan=False))


if __name__=="__main__":main()
