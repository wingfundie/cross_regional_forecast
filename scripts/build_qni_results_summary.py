"""Build the Markdown handoff for the completed QNI diurnal/NOS campaign."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from nemic.experiments.diurnal import origin_weights


ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'data/forecast_experiments/qni_diurnal_nos_v2'


def nos_scores() -> pd.DataFrame:
    grouped={}
    for path in sorted((RUN/'nos_models').glob('*/*/result.json')):
        result=json.loads(path.read_text(encoding='utf-8'))
        frame=pd.read_parquet(path.parent/'predictions.parquet')
        local=frame.loc[frame.nos_known,['origin','actual','T6_O0']].copy()
        local['selected']=frame.loc[frame.nos_known,result['winner']].to_numpy()
        grouped.setdefault(result['target'],[]).append(local)
    rows=[]
    for target,pieces in grouped.items():
        frame=pd.concat(pieces,ignore_index=True);weights=origin_weights(frame.origin)
        selected=float(np.average(abs(frame.actual-frame.selected),weights=weights))
        control=float(np.average(abs(frame.actual-frame.T6_O0),weights=weights))
        rows.append({'Target':target,'Selected NOS MAE (MW)':selected,'T6 O0 MAE (MW)':control,
                     'Skill vs O0 (%)':100*(1-selected/control),'Rows':len(frame)})
    return pd.DataFrame(rows)


def build() -> Path:
    performance=pd.read_csv(RUN/'report/downloads/research_performance.csv')
    tight=performance.loc[performance.target.isin(['export_tight','import_tight'])].copy()
    tight['Target']=tight.target.map({'export_tight':'Export minimum','import_tight':'Import minimum'})
    tight['Band']=tight.band.map({0:'0.5–6 h',1:'6.5–24 h',2:'24.5–72 h',3:'72.5–168 h'})
    tight['Selected MAE (MW)']=tight.selected_mae.round(1)
    tight['MAPE |actual|≥50 (%)']=tight.selected_mape.round(1)
    tight['Persistence MAE (MW)']=tight.persistence_mae.round(1)
    tight['T0 MAE (MW)']=tight.t0_mae.round(1)
    tight['Skill vs persistence (%)']=(100*tight.skill_persistence).round(1)
    tight['Skill vs T0 (%)']=(100*tight.skill_t0).round(1)
    display=tight[['Target','Band','Selected MAE (MW)','MAPE |actual|≥50 (%)','Persistence MAE (MW)','T0 MAE (MW)','Skill vs persistence (%)','Skill vs T0 (%)']]

    catalogue=json.loads((RUN/'final/catalogue.json').read_text(encoding='utf-8'))
    routes=pd.DataFrame([{'Target':r['target'],'Band':int(r['band']),'Winner':r['winner']} for r in catalogue])
    routes['Band']=routes.Band.map({0:'0.5–6 h',1:'6.5–24 h',2:'24.5–72 h',3:'72.5–168 h'})
    stats=json.loads((RUN/'statistics.json').read_text(encoding='utf-8'))
    comparisons=pd.DataFrame([r for r in stats['comparisons'] if r.get('block_days')==7])
    comparisons['Target']=comparisons.target.map({'export_tight':'Export minimum','import_tight':'Import minimum'})
    comparisons['Control']=comparisons.control.map({'persistence':'Persistence','T0_mae':'T0 shared ridge'})
    comparisons['Improvement (MW)']=comparisons.improvement_mw.round(1)
    comparisons['95% block CI']=comparisons.apply(lambda r:f"[{r.ci_low:.1f}, {r.ci_high:.1f}]",axis=1)
    comparisons['Holm p']=comparisons.apply(lambda r:round(r.get('holm_p_family',r.get('holm_p_vni_family')),4),axis=1)
    impact=json.loads((RUN/'nos/impact/full_development/status.json').read_text(encoding='utf-8'))
    nos=nos_scores();importance=pd.read_csv(RUN/'report/downloads/research_feature_importance.csv')
    top=(importance.sort_values(['target','mae_degradation'],ascending=[True,False]).groupby('target').first().reset_index())
    top['MAE degradation (MW)']=top.mae_degradation.round(2)
    primary=display.loc[display.Band.eq('0.5–6 h')].set_index('Target')
    export=primary.loc['Export minimum']; imported=primary.loc['Import minimum']

    text=f'''# QNI diurnal and NOS modelling results

Run date: 16 September 2026. Outcomes extend through August 2026 in NEM time (UTC+10). These are historical development results on reconstructed network information, not prospective performance.

## Verdict

The frozen QNI policy improves band-0 minimum-export MAE by **{export['Skill vs persistence (%)']:.1f}%** versus persistence and minimum-import MAE by **{imported['Skill vs persistence (%)']:.1f}%**. Model routing is target- and horizon-specific and is listed below; it is not copied from the VNI verdict.

Scheduled NOS point-model skill is evaluated on the source-common population and remains a separately identifiable challenger. The matched pre-model audit contains **{impact['candidate_bookings']:,}** candidate bookings, **{impact['matched_direction_episodes']:,}** matched direction episodes and **{impact['supported_recurring_entities']:,}** supported recurring entities. Unsupported assets or sets are not labelled as highest-impact.

## Rolling model results

MAE is the selection objective. MAPE is assessment-only and is reported where `|actual| ≥ 50 MW`.

{display.to_markdown(index=False)}

## Paired statistical evidence

Positive improvement favors the selected policy. Confidence intervals use paired seven-day moving blocks; the run also preserves fourteen-day results and 90% model-confidence sets in `statistics.json`.

{comparisons[['Target','Control','Improvement (MW)','95% block CI','Holm p']].to_markdown(index=False)}

## Final saved-bundle routing

{routes.to_markdown(index=False)}

All sixteen bundles have catalogue hashes, exact ordered schemas, fitted parameters, residual calibration and reload-parity checks. They remain `operationally_eligible: false`.

## Feature evidence

The largest average grouped-permutation effect for each primary direction is:

{top[['target','group','MAE degradation (MW)']].to_markdown(index=False)}

Permutation importance and SHAP are predictive-dependence diagnostics, not causal generator or constraint effects. Full rankings are in the report downloads and cell-level explanation artifacts.

## NOS point-model evidence

{nos.round(2).to_markdown(index=False)}

NOS burden, transitions, mapped mechanisms, revisions/recall and restricted operating-state interactions are tested cumulatively only after the historical source and feasibility gates. Risk-model results remain distinct from point forecasts.

## Reproduction and handoff

- Full paper: [QNI research paper](../reports/qni_diurnal_nos_v2/qni_research_paper.html)
- Report centre: [QNI report suite](../reports/qni_diurnal_nos_v2/index.html)
- Execution guide: [QNI execution guide](QNI_DIURNAL_NOS_EXECUTION.md)
- Saved bundles: `data/forecast_experiments/qni_diurnal_nos_v2/final/`
- Configuration: `configs/experiments/qni_diurnal_nos_v2.json`

Re-run the complete resumable workflow with `python scripts/run_qni_diurnal_nos_campaign.py`. Use `python scripts/build_qni_report_suite.py` for report-only rebuilding.
'''
    output=ROOT/'docs/QNI_DIURNAL_NOS_RESULTS.md';output.write_text(text,encoding='utf-8');return output


if __name__=='__main__':print(build())
