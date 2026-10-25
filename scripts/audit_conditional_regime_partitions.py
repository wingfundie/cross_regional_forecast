"""Check resubmission-collapsed incidents across all realised campaign partitions."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/"packages/nemic-regimes/src"))
import json
from itertools import combinations
from nemic.experiments.conditional_regimes.common import DATA,write_json,digest
from nemic.experiments.conditional_regimes.research import usable_panel,folds,partitions

if __name__=="__main__":
    metadata=json.loads((DATA/"bundle/manifest.json").read_text(encoding="utf-8"))
    links=metadata["episode_links"];panel=usable_panel();rows=[]
    for (name,direction),frame in panel.groupby(["connector","direction"]):
        codes={text:{links.get(i,{}).get("canonical_id",i) for i in text.split("|") if i}-{None} for text in frame.episode_ids.unique()}
        for fold in folds(panel):
            split,_=partitions(frame,fold)
            present={part:set().union(*(codes[text] for text in f.episode_ids.unique())) for part,f in split.items()}
            for a,b in combinations(present,2):
                overlap=present[a]&present[b]
                if overlap:rows.append({"connector":name,"direction":direction,"fold":fold["id"],"partitions":[a,b],"overlapping_canonical_episodes":sorted(overlap)})
    result={"passed":not rows,"partition_pairs_with_overlap":len(rows),"overlaps":rows,
            "panel_sha256":digest(DATA/"panel.parquet"),"manifest_sha256":digest(DATA/"bundle/manifest.json"),
            "claim":"Audit of final-state resubmission links; independent of numerical model accuracy"}
    write_json(DATA/"canonical_partition_audit.json",result)
    print(json.dumps({"passed":not rows,"overlapping_pairs":len(rows),"examples":rows[:3]},indent=2))
