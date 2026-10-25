"""Package the explicitly approved reference outputs and full campaign data.

This builds local files only. Uploading and merging are separate operations.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TAG="conditional-regimes-v1-20261025"


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()


def build(source,output,archives):
    source,output,archives=map(lambda p:Path(p).resolve(),(source,output,archives))
    campaign=source/"data/forecast_experiments/conditional_regimes_v1"
    output.mkdir(parents=True,exist_ok=True);archives.mkdir(parents=True,exist_ok=True)
    reference=[]
    def copy(p,relative):
        q=output/relative;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
        reference.append({"path":str(relative).replace("\\","/"),"source":str(p.relative_to(source)).replace("\\","/"),"bytes":q.stat().st_size,"sha256":sha(q)})
    for report,name in (("conditional_regimes_v1","research"),("conditional_regimes_tutorial","tutorial")):
        folder=source/"reports"/report
        for p in sorted(folder.rglob("*")):
            if not p.is_file() or "qa" in p.relative_to(folder).parts or p.name=="tutorial.zip":continue
            copy(p,Path(name)/p.relative_to(folder))
    for p in sorted(campaign.glob("*.csv")):copy(p,Path("campaign_tables")/p.name)
    for p in sorted((source/"data/forecast_experiments/conditional_regimes_tutorial/example_outputs").glob("*")):
        if p.is_file():copy(p,Path("tutorial_examples")/p.name)
    groups={"campaign_data":{},"retained_inputs":{}}
    excluded={"clean_env","package_smoke_env","package_installation","github_upload","qa","__pycache__","worker_owners","publication"}
    for p in sorted(campaign.rglob("*")):
        if not p.is_file() or set(p.relative_to(campaign).parts)&excluded:continue
        if p.suffix in {".log",".jsonl",".txt"} or p.name in {"owner.json"}:continue
        groups["campaign_data"][str(p.relative_to(source)).replace("\\","/")]=p
    inventory=json.loads((campaign/"inventory.json").read_text())
    paths=[source/row["path"].replace("\\","/") for row in inventory["sources"]]
    paths += [source/"data/processed/ic_5min.parquet",source/"data/nos_regime_v1/invocation_spells.parquet",source/"results/seasonal_references.csv"]
    paths += list((source/"data/nos_binding_v1/standing").glob("*.parquet"))
    paths += list((source/"data/nos_binding_v1/dispatchload").glob("*.parquet"))
    paths += [source/f"data/constraint_{study}_2y/standing/GENCONSET.parquet" for study in ("qni","vni","directlink","vsa","murraylink","basslink")]
    for p in paths:
        if not p.is_file():raise FileNotFoundError(p)
        groups["retained_inputs"][str(p.relative_to(source)).replace("\\","/")]=p
    package_manifest={"schema":1,"built":datetime.now(timezone.utc).isoformat(),"bundle_id":"conditional-regimes-v1-b3352cb955ecbeb0",
       "scope":"All retained data for this conditional-regime campaign and its declared reused inputs; unrelated projects are excluded",
       "excluded":"Credentials, Python environments, package-install smoke directories, temporary publication files, process ownership and operational logs",
       "reference_files":reference,"archives":[]}
    for name,files in groups.items():
        filename=f"conditional-regimes-{name.replace('_','-')}-20261025.zip";archive=archives/filename
        records=[{"path":relative,"bytes":p.stat().st_size,"sha256":sha(p)} for relative,p in sorted(files.items())]
        inside={"group":name,"files":records,"restore":"Extract at the repository root; paths retain their data/ and results/ prefixes"}
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED,compresslevel=3,allowZip64=True) as z:
            for relative,p in sorted(files.items()):z.write(p,relative)
            z.writestr("DATA_MANIFEST.json",json.dumps(inside,indent=2))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            for item in records:
                with z.open(item["path"]) as f:
                    h=hashlib.sha256()
                    for block in iter(lambda:f.read(1<<20),b""):h.update(block)
                assert h.hexdigest()==item["sha256"],item["path"]
        receipt={"name":filename,"files":len(records),"uncompressed_bytes":sum(r["bytes"] for r in records),"bytes":archive.stat().st_size,"sha256":sha(archive),
                 "url":f"https://github.com/wingfundie/cross_regional_forecast/releases/download/{TAG}/{filename}","contents":records}
        package_manifest["archives"].append(receipt)
        print(json.dumps({k:v for k,v in receipt.items() if k!="contents"}),flush=True)
    (output/"dataset_manifest.json").write_text(json.dumps(package_manifest,indent=2),encoding="utf-8")
    print(json.dumps({"reference_files":len(reference),"csv_files":sum(r["path"].endswith('.csv') for r in reference),"reference_bytes":sum(r["bytes"] for r in reference),"archives":len(groups)}),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True);p.add_argument("--output",type=Path,default=ROOT/"reference/conditional_regimes_v1")
    p.add_argument("--archives",type=Path,required=True);a=p.parse_args();build(a.source,a.output,a.archives)
