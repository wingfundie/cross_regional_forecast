import unittest,json
import numpy as np
import pandas as pd
from nemic.common import *
from nemic.model import Design,IDS,TARGETS,band
from nemic.prepare import TRAIN_END,TEST_START,END
from nemic.scenario import template,run_scenario

class ResearchIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.d=Design()

    def test_all_connectors_complete_five_minute_grid(self):
        t=pd.read_parquet(PROCESSED/'targets.parquet')
        self.assertEqual(set(t.ic),set(IDS))
        self.assertEqual(len(t),315648)
        self.assertTrue((t.n5==6).all())
        self.assertFalse(t[TARGETS].isna().any().any())
        self.assertTrue((t.export_tight<=t['export']+1e-4).all())
        self.assertTrue((t.import_tight<=t['import']+1e-4).all())

    def test_signs_and_aggregation_from_raw(self):
        raw=pd.read_parquet(PROCESSED/'ic_5min.parquet')
        self.assertTrue(np.allclose(raw['import'],-raw.IMPORTLIMIT))
        self.assertTrue((raw['export']<0).any())
        pick=raw[(raw.INTERCONNECTORID=='N-Q-MNSP1')&(raw.time>'2026-03-01 00:00')&(raw.time<='2026-03-01 00:30')]
        row=self.d.targets['N-Q-MNSP1'].loc['2026-03-01 00:30']
        self.assertAlmostEqual(row.flow,pick.MWFLOW.mean(),places=4)
        self.assertAlmostEqual(row.import_tight,-pick.IMPORTLIMIT.max(),places=4)

    def test_training_pairs_and_information_cutoff(self):
        d=self.d;ci,oi,h=d.pairs('2023-09-01',TRAIN_END,training=True)
        self.assertTrue((d.time[oi+h]<=TRAIN_END).all())
        self.assertTrue((h>=1).all() and (h<=336).all())
        self.assertTrue((oi-336>=0).all())
        self.assertTrue(set(band(h))=={0,1,2,3})
        ci,oi,h=d.pairs(TEST_START,END)
        self.assertTrue((d.time[oi]>=TEST_START).all())
        self.assertTrue((d.time[oi+h]>TEST_START).all())
        self.assertTrue((d.time[oi+h]<=END).all())

    def test_future_outcomes_never_enter_features(self):
        d=self.d;o=d.time.get_loc('2026-05-01 00:00');ci=np.array([0]);oi=np.array([o]);h=np.array([48])
        x=d.features(ci,oi,h)
        previous=d.y[:,o:o+337].copy();state=d.state[:,o:o+337].copy()
        try:
            d.y[:,o:o+337]=999999;d.state[:,o:o+337]=999999
            self.assertTrue(np.allclose(x,d.features(ci,oi,h),equal_nan=True))
        finally:d.y[:,o:o+337]=previous;d.state[:,o:o+337]=state
        self.assertFalse(any('price' in c.lower() or 'rrp' in c.lower() for c in d.network_cols))

    def test_delayed_publication_is_censored(self):
        d=self.d;o=d.time.get_loc('2024-09-05 14:00')
        x=d.features(np.array([0]),np.array([o]),np.array([1]))
        self.assertTrue(np.isnan(x[0,d.network_cols.index('lag1_flow')]))
        self.assertTrue(np.isnan(x[0,d.network_cols.index('origin_flow_NSW1-QLD1')]))

    def test_reference_uses_training_positive_limits_only(self):
        t=pd.read_parquet(PROCESSED/'targets.parquet');train=t[t.time<=TRAIN_END]
        ref=train.groupby(['ic','season'])[['export','import']].agg(lambda x:x[x>0].median())
        saved=pd.read_csv(RESULTS/'seasonal_references.csv').set_index(['ic','season'])
        self.assertTrue(np.allclose(ref,saved))
        self.assertTrue((saved>0).all().all())

    def test_scenario_rejects_invalid_grid(self):
        data=template();
        with self.assertRaisesRegex(ValueError,'336'):run_scenario('2026-08-24',data.iloc[:-1],d=Design())

    def test_scenario_rejects_future_origin_without_history(self):
        with self.assertRaisesRegex(ValueError,'observed network history'):run_scenario('2026-09-11',template(),d=Design())

if __name__=='__main__':unittest.main()
