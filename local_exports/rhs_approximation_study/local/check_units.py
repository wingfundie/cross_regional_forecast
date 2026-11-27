"""Compare signed public unit SCADA with the dispatch solution's INITIALMW."""
import hashlib
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

out = Path(__file__).resolve().parent
root = out.parents[2]
source = next((root/'data/constraint_pilot/raw').glob('*DISPATCHLOAD*202602*'))
units = ['CAPTL_WF', 'CULLRGWF', 'BANGOWF1', 'GOONSF1', 'ORABESS1', 'TARBESS1']
obs = pd.read_csv(out/'observed_inputs.csv')
obs = obs[['end', *units]].melt('end', var_name='DUID', value_name='SCADA')
obs['SETTLEMENTDATE'] = pd.to_datetime(obs.end).dt.strftime('%Y/%m/%d %H:%M:%S')
fields = ['SETTLEMENTDATE', 'RUNNO', 'DUID', 'INTERVENTION', 'INITIALMW']
matches = []
with ZipFile(source) as archive, archive.open(archive.namelist()[0]) as stream:
    for frame in pd.read_csv(stream, skiprows=1, usecols=fields, chunksize=150000):
        selected = frame[frame.DUID.isin(units) & frame.RUNNO.eq(1) & frame.INTERVENTION.eq(0)]
        matches.append(selected[selected.SETTLEMENTDATE.isin(obs.SETTLEMENTDATE)])
matched = obs.merge(pd.concat(matches), how='left', validate='one_to_one')
matched['abs_diff'] = (matched.SCADA-matched.INITIALMW).abs()
result = matched.groupby('DUID').abs_diff.agg(scada_rows='size', dispatch_matches='count',
                                              mean_abs_mw='mean', max_abs_mw='max')
with source.open('rb') as stream:
    result['source_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
result.to_csv(out/'unit_crosscheck.csv')
print(result.iloc[:, :4])
