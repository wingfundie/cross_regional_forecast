"""Crosswalk historical connector influence to the inspected dispatch-case inventory."""
from pathlib import Path
import hashlib,json
import pandas as pd
out=Path(__file__).resolve().parent
root=out.parents[1]
deps=root/'reports/rhs_replay/inventory/dependencies.csv'
d=pd.read_csv(deps)
sources=[deps]; rows=[]
for link in ['qni','vni']:
    source=root/f'data/constraint_{link}_2y/months/2025-09/constraint_influence.csv'
    sources.append(source)
    summary=pd.read_csv(source)
    for rec in summary.itertuples():
        eq=rec.constraint
        g=d[d.equation.eq(eq)]
        rows.append(dict(link=link,direction=rec.direction,equation=eq,leading_intervals=rec.leading_intervals,
                         contraction_episodes=rec.contraction_episodes,forced_intervals=rec.forced_intervals,
                         inventoried=not g.empty,types=' '.join(sorted(g.spd_type.unique())),
                         leaves=len(g[['spd_type','spd_id']].drop_duplicates())))
pd.DataFrame(rows).sort_values(['link','leading_intervals'],ascending=[True,False]).to_csv(out/'screen.csv',index=False)
(out/'screen_sources.json').write_text(json.dumps({str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},indent=2))
