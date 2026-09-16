"""Run the fixed split without replacing the rolling campaign inventory."""
import json
from concurrent.futures import ProcessPoolExecutor

from .core import Store,clean,digest,fingerprint,load_config
from .data import inventory
from .diurnal_runner import _job,job

CONFIG='configs/experiments/vni_diurnal_nos_v2_fixed.json'


def run_fixed(config_path=CONFIG):
    c=load_config(config_path);inv=inventory(c,save=False);store=Store(c)
    source_fp=fingerprint({'sources':inv['sources'],'configuration':inv['configuration'],
        'data_adapter':digest(__file__.replace('diurnal_fixed.py','data.py'))})
    jobs=[(config_path,'fixed',0,target,source_fp) for target in ('export_tight','import_tight')]
    store.json(store.root/'fixed_inventory.json',inv)
    store.json(store.root/'fixed_primary_manifest.json',{'jobs':jobs,'objective':'mae','source_fingerprint':source_fp})
    with ProcessPoolExecutor(max_workers=c['limits']['workers']) as pool:
        for result in pool.map(job,jobs):print(json.dumps(clean(result)),flush=True)


if __name__=='__main__':run_fixed()
