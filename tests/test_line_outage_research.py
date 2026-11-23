import numpy as np
import pandas as pd

from nemic.experiments.line_outages.analysis import bh_adjust, effect, match_pairs
from nemic.experiments.line_outages.core import interval_mask, merge_events
from nemic.experiments.line_outages.data import equipment_identity, price_features
from nemic.experiments.line_outages.mechanics import exact_definitions, set_members_at


def test_equipment_and_invocation_have_different_start_conventions():
    t=pd.date_range("2025-01-01",periods=4,freq="5min")
    w=pd.DataFrame({"start":[t[1]],"end":[t[2]]})
    assert interval_mask(t,w).tolist()==[False,False,True,False]
    assert interval_mask(t,w,inclusive_start=True).tolist()==[False,True,True,False]


def test_independent_events_merge_alias_records_but_not_restoration_gaps():
    f=pd.DataFrame({"asset":["a"]*3,"OUTAGEID":["1","2","3"],
      "start":pd.to_datetime(["2025-01-01 01:00","2025-01-01 02:00","2025-01-01 05:00"]),
      "end":pd.to_datetime(["2025-01-01 02:00","2025-01-01 03:00","2025-01-01 06:00"])})
    e=merge_events(f)
    assert len(e)==2 and e.iloc[0].outage_ids=="1|2"


def test_price_movement_does_not_bridge_missing_interval_or_use_future_thresholds():
    f=pd.DataFrame({"time":pd.to_datetime(["2024-12-01 00:05","2024-12-01 00:10","2024-12-01 00:20","2025-12-01 00:05"]),"RRP":[-10.,10.,20.,10000.]})
    out,q=price_features(f,"2025-09-01")
    assert out.price_change.iloc[1]==20
    assert np.isnan(out.price_change.iloc[2])
    assert q.p99.max()<100
    assert out.tail99.iloc[-1]==1


def test_exact_constraint_version_join_rejects_latest_version_substitution():
    b=pd.DataFrame({"CONSTRAINTID":["x","x"],"EFFECTIVEDATE":pd.to_datetime(["2024-01-01","2024-01-01"]),"VERSIONNO":[1,3]})
    d=pd.DataFrame({"GENCONID":["x","x"],"EFFECTIVEDATE":pd.to_datetime(["2024-01-01","2024-01-01"]),"VERSIONNO":[1,2],"DESCRIPTION":["old","new"]})
    out=exact_definitions(b,d)
    assert out.DESCRIPTION.iloc[0]=="old" and pd.isna(out.DESCRIPTION.iloc[1])


def test_equipment_identity_rejects_description_outside_its_validity_and_wrong_alias():
    rows=pd.DataFrame({"ELEMENTID":["1"]*3,"SUBSTATIONID":["a","a","wrong"],"EQUIPMENTTYPE":"LINE","EQUIPMENTID":"6",
                       "start":pd.to_datetime(["2025-01-01","2023-01-01","2025-01-01"]),
                       "end":pd.to_datetime(["2025-01-02","2023-01-02","2025-01-02"]),"DESCRIPTION":"fallback","VOLTAGE":330.})
    equipment=pd.DataFrame({"ELEMENTID":["1"],"SUBSTATIONID":["a"],"EQUIPMENTTYPE":["LINE"],"EQUIPMENTID":["6"],
                           "VALIDFROM":["2024/01/01 00:00:00"],"VALIDTO":["9999/12/31 00:00:00"],
                           "DESCRIPTION":["verified"],"VOLTAGE":["330"],"LASTCHANGED":["2024/01/01 00:00:00"]})
    out=equipment_identity(rows,equipment)
    assert out.identity_valid.tolist()==[True,False,False]
    assert out.DESCRIPTION.iloc[0]=="verified"


def test_set_version_removal_is_respected():
    m=pd.DataFrame({"GENCONSETID":["s"]*3,"EFFECTIVEDATE":["2024-01-01","2024-01-01","2025-01-01"],"VERSIONNO":[1,1,2],"GENCONID":["a","b","b"]})
    assert set(set_members_at(m,"s","2024-06-01").GENCONID)=={"a","b"}
    assert set(set_members_at(m,"s","2025-06-01").GENCONID)=={"b"}


def test_native_period_parser_filters_unit_service_and_delivery_date(tmp_path):
    import zipfile
    from nemic.experiments.line_outages.offers import stream_selected
    path=tmp_path/"period.zip"
    native='C,report\nI,BIDS,BIDPEROFFER_D,3,DUID,BIDTYPE,INTERVAL_DATETIME,BANDAVAIL1\n'
    native+='D,BIDS,BIDPEROFFER_D,3,A,ENERGY,2025/01/02 00:05:00,50\n'
    native+='D,BIDS,BIDPEROFFER_D,3,B,ENERGY,2025/01/02 00:05:00,99\n'
    native+='D,BIDS,BIDPEROFFER_D,3,A,RAISE6SEC,2025/01/02 00:05:00,20\n'
    native+='D,BIDS,BIDPEROFFER_D,3,A,ENERGY,2025/01/03 00:05:00,70\nC,END OF REPORT,6\n'
    with zipfile.ZipFile(path,'w') as z:z.writestr('native.csv',native)
    out=stream_selected(path,{'A'},{'2025-01-02'},'BIDPEROFFER_D')
    assert len(out)==1 and out.BANDAVAIL1.iloc[0]=='50'
    assert not path.with_suffix('.selected-scan.csv').exists()


def test_offer_summary_does_not_pool_another_cases_dates():
    from types import SimpleNamespace
    from nemic.experiments.line_outages.offers import case_offer_rows
    e=SimpleNamespace(start=pd.Timestamp('2025-01-10 08:00'),end=pd.Timestamp('2025-01-10 18:00'))
    f=pd.DataFrame({'DUID':['a']*3,'INTERVAL_DATETIME':['2025/01/10 08:05:00','2025/01/25 08:05:00',None],
                    'SETTLEMENTDATE':[None,None,'2025/01/09 00:00:00']})
    assert case_offer_rows(f,{'a'},e).index.tolist()==[0,2]


def test_offer_output_reuse_requires_verified_hashes_and_identical_scope(tmp_path):
    import json
    from nemic.experiments.line_outages.offers import verified_prior_offers,prior_offer_part
    from nemic.experiments.line_outages.core import sha
    directory=tmp_path/'data';directory.mkdir()
    execution=tmp_path/'execution';(execution/'manifests').mkdir(parents=True)
    rows=directory/'offer_revisions.parquet';metadata=directory/'offer_sources.json'
    frame=pd.DataFrame({'source_month':['2025-01'],'source_table':['BIDDAYOFFER_D'],
                        'source_sha256':['raw-hash'],'DUID':['A']})
    frame.to_parquet(rows,index=False)
    source={'month':'2025-01','table':'BIDDAYOFFER_D','sha256':'raw-hash','status':'parsed',
            'days':['2025-01-02'],'duids':['A'],'selected_rows':1}
    metadata.write_text(json.dumps({'sources':[source],'parser_contract':'native-sample-v2'}),encoding='utf-8')
    (execution/'manifests/offers.json').write_text(json.dumps({'outputs':{str(p):sha(p) for p in [metadata,rows]}}),encoding='utf-8')
    sources,previous=verified_prior_offers({'_execution':execution,'_data':directory})
    job={'days':{'2025-01-02'},'duids':{'A'}}
    record,part=prior_offer_part(sources,previous,'2025-01','BIDDAYOFFER_D',job)
    assert record['verified_output_cache'] and part.DUID.tolist()==['A']
    assert prior_offer_part(sources,previous,'2025-01','BIDDAYOFFER_D',dict(job,duids={'B'})) is None
    # A genuinely empty selected table remains a resolved zero-row sample, not a parser failure.
    empty=dict(source,selected_rows=0)
    assert prior_offer_part({('2025-01','BIDDAYOFFER_D'):empty},pd.DataFrame(),'2025-01','BIDDAYOFFER_D',job)[1].empty
    frame.assign(DUID='tampered').to_parquet(rows,index=False)
    assert verified_prior_offers({'_execution':execution,'_data':directory})[0]=={}


def test_scoped_source_cache_reuses_only_a_verified_superset(tmp_path,monkeypatch):
    import json
    import pytest
    from nemic.experiments.line_outages import acquire
    from nemic.experiments.line_outages.core import sha
    monkeypatch.setattr(acquire,'ROOT',tmp_path/'isolated-sources')
    directory=tmp_path/'supplements';directory.mkdir()
    target=directory/'GENCONDATA_2025-01.parquet'
    pd.DataFrame({'GENCONID':['a','b'],'DESCRIPTION':['required','unrelated']}).to_parquet(target,index=False)
    meta={'sha256':sha(target),'request_signature':'old','requested_values':[['a','b']],'selected_rows':2}
    target.with_suffix('.json').write_text(json.dumps(meta))
    c={'_data':tmp_path,'limits':{'minimum_free_bytes':0,'download_file_bytes':1000000}}
    wanted={'a'};records=[]
    result=acquire.fetch(c,'GENCONDATA','2025-01',lambda r:r.get('GENCONID') in wanted,records)
    assert result.GENCONID.tolist()==['a'] and sha(target)==meta['sha256']
    assert records[0]['analysis_selected_rows']==1
    monkeypatch.setattr(acquire,'download_entry',lambda *args:(_ for _ in ()).throw(RuntimeError('new scope needs source')))
    wanted={'c'}
    with pytest.raises(RuntimeError,match='new scope needs source'):
        acquire.fetch(c,'GENCONDATA','2025-01',lambda r:r.get('GENCONID') in wanted,records)


def test_episode_weighting_avoids_long_outage_dominating_estimate():
    f=pd.DataFrame({"y":[10.]*100+[100.,0.]})
    pairs=pd.DataFrame({"treated":list(range(101)),"control":[101]*101,"event_id":["long"]*100+["short"]})
    out,_=effect(f,pairs,"y",{"seed":1,"bootstrap_replicates":100})
    assert out["effect"]==55 and out["episodes"]==2


def test_multiple_testing_keeps_missing_values_and_monotonic_adjustment():
    out=bh_adjust([.01,.02,.9,np.nan])
    assert np.allclose(out[:3],[.03,.03,.9]) and np.isnan(out[3])


def test_exact_matching_removes_only_the_actual_asset_from_other_outage_signature():
    import hashlib
    t=pd.date_range("2025-01-01 00:05",periods=288*45,freq="5min")
    window=pd.DataFrame({"start":[pd.Timestamp("2025-01-20")],"end":[pd.Timestamp("2025-01-21")],"event_id":["e"]})
    actual=interval_mask(t,window)
    h=hashlib.sha256(b"a").digest()
    f=pd.DataFrame({"time":t,"REGIONID":"NSW1","season":0,"demand":100.,"temperature":20.,"physical_intervention":0,
                    "co_sig1":np.where(actual,np.uint64(int.from_bytes(h[:8],"little")),np.uint64(0)),
                    "co_sig2":np.where(actual,np.uint64(int.from_bytes(h[8:16],"little")),np.uint64(0)),"outage_count":actual.astype(int)})
    c={"selection_end":"2025-09-01","match_days":21,"max_controls":5}
    pairs=match_pairs(c,f,f,window,"a","selection")
    assert pairs.treated.nunique()==288
    shifted=window.copy();shifted.start+=pd.Timedelta(days=7);shifted.end+=pd.Timedelta(days=7)
    placebo=match_pairs(c,f,f,shifted,"a","selection",excluded=actual)
    assert placebo.treated.nunique()==288
    assert not actual[placebo.control].any()
