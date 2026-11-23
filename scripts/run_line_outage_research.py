"""Resumable asset-specific outage campaign. See execution/line_outage_risk_v1."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from nemic.experiments.line_outages import acquire, analysis, data, mechanics
from nemic.experiments.line_outages.core import BIND, OLD, REGIONS, STUDIES, config, run_stage


def stages(c):
    d=c["_data"]
    def outputs(*names):return [d/(n+".parquet") for n in names]
    stage_map={
      "audit":(data.audit,[OLD/(n+".parquet") for n in ["episodes","episode_assets","outage_keys","episode_sets"]]+list((OLD/"raw/mmsdm").glob("NETWORK_*DETAIL_*.parquet")),outputs("asset_register","outage_ledger","events","asset_sets","equipment_events","equipment_register")+[d/"sources.json",d/"aliases.json"]),
      "panel":(data.panel,outputs("equipment_register","equipment_events")+[ROOT/"data/valuation_v2/panel/prices.parquet",ROOT/"data/valuation_v2/panel/interconnectors.parquet",ROOT/"data/processed/weather_30min.parquet"]+list((ROOT/"data/tables/DISPATCHREGIONSUM").glob("*.parquet")),outputs(*["panel_"+r for r in REGIONS],*["ic_"+r for r in STUDIES],"daily_prices","price_thresholds")+[d/"coverage.json"]),
      "select":(data.select,outputs("asset_register","events",*["panel_"+r for r in REGIONS])+[d/"aliases.json"],outputs("cohort","selection_screen")+[d/"selection_freeze.json"]),
      "supplement":(acquire.supplement,outputs("cohort","asset_sets","outage_ledger","events")+[BIND/"equation_scope.parquet"]+[p for s in STUDIES.values() for p in (ROOT/f"data/constraint_{s}_2y/standing").glob("GENCON*.parquet")],outputs("complete_set_members","supplement_invocations","supplement_GENCONDATA","supplement_SPDINTERCONNECTORCONSTRAINT","supplement_SPDCONNECTIONPOINTCONSTRAINT","supplement_constraint_observations")+[d/"supplement_sources.json"]),
      "mechanics":(mechanics.mechanics,outputs("cohort","outage_ledger","asset_sets","events","complete_set_members","supplement_invocations","supplement_GENCONDATA","supplement_SPDINTERCONNECTORCONSTRAINT","supplement_SPDCONNECTIONPOINTCONSTRAINT","supplement_constraint_observations")+[OLD/"invocation_spells.parquet"]+list((BIND/"binding_panel").glob("*.parquet"))+list((BIND/"standing").glob("*.parquet"))+[p for s in STUDIES.values() for p in (ROOT/f"data/constraint_{s}_2y/standing").glob("*.parquet")],outputs("asset_constraint_crosswalk","asset_set_audit","constraint_observations","equation_ic_terms","equation_cp_terms","mechanism_summary","event_constraint_observations")),
      "setters":(mechanics.setters,outputs("cohort","events","asset_sets","complete_set_members")+[p for s in STUDIES.values() for p in (ROOT/f"data/constraint_{s}_2y/months").glob("*/constraint_features_5min.parquet")],outputs("setter_summary")),
      "compare":(analysis.compare,outputs("cohort","events",*["panel_"+r for r in REGIONS],*["ic_"+r for r in STUDIES]),outputs("price_effects","network_effects","falsification")),
      "events":(mechanics.events,outputs("cohort","events","mechanism_summary","asset_constraint_crosswalk","equation_cp_terms",*["panel_"+r for r in REGIONS],*["ic_"+r for r in STUDIES])+[BIND/"standing/DUDETAILSUMMARY.parquet"]+list((BIND/"dispatchload").glob("*.parquet")),outputs("event_summary","case_selection","generation_response","interconnector_event_response")),
    }
    from nemic.experiments.line_outages import outlook, offers, report
    stage_map["offers"]=(offers.run,outputs("case_selection","equation_cp_terms","asset_constraint_crosswalk")+[BIND/"standing/DUDETAILSUMMARY.parquet"],outputs("offer_revisions","offer_summary")+[d/"offer_sources.json"])
    stage_map["outlook"]=(outlook.run,outputs("cohort","asset_sets","price_effects","events",*["panel_"+r for r in REGIONS])+[d/"sources.json"],outputs("outlook_bookings","outlook_replay","outlook_price_backtest","outlook_backtest_scores")+[d/"outlook_provenance.json"])
    stage_map["report"]=(report.build,[p for p in d.glob("*.parquet")]+list((d/"timelines").glob("*.parquet"))+[d/"sources.json",d/"coverage.json",d/"outlook_provenance.json",d/"offer_sources.json",d/"supplement_sources.json",ROOT/"execution/line_outage_risk_v1/reference_notes.json",ROOT/"scripts/report_theme/report_theme.py",ROOT/"scripts/report_theme/report.css",ROOT/"requirements-line-outages.txt",ROOT/"requirements.txt"], [c["_report"]/"index.html",c["_report"]/"REPORT.md",c["_report"]/"manifest.json"])
    stage_map["validate"]=(report.validate,[c["_report"]/"index.html",c["_report"]/"REPORT.md",c["_report"]/"manifest.json"], [d/"validation.json"])
    qa=c["_execution"]/"report_qa.json"
    if qa.exists():stage_map["validate"][1].append(qa)
    return stage_map


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",choices=["all","audit","panel","select","supplement","mechanics","setters","compare","events","offers","outlook","report","validate"],required=True)
    parser.add_argument("--config",type=Path,default=ROOT/"configs/experiments/line_outage_risk_v1.json")
    parser.add_argument("--force",action="store_true")
    args=parser.parse_args();c=config(args.config)
    c["_data"].mkdir(parents=True,exist_ok=True)
    mapping=stages(c)
    for name in (mapping if args.stage=="all" else [args.stage]):
        fun,inputs,outputs=mapping[name]
        inputs+=[ROOT/"execution/line_outage_risk_v1/METHODOLOGY.md"]
        run_stage(c,name,fun,inputs,outputs,args.force)
    return 0


if __name__=="__main__":raise SystemExit(main())
