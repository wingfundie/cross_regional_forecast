"""Manual, immutable, first-received live baseline recorder.

Retrospective model bundles are deliberately ineligible for this recorder.
"""
import hashlib
import io
import json
import re
import uuid
import zipfile
from urllib.parse import urljoin, urlparse
import pandas as pd
from .core import Store, ROOT, digest


def record(c, frame, received, source):
    received=pd.Timestamp(received)
    if received.tzinfo is None:raise ValueError('First-received timestamp must have a timezone')
    now_nem=received.tz_convert('Etc/GMT-10').tz_localize(None)
    origin=now_nem.ceil('30min')
    frame=frame.copy();frame['SETTLEMENTDATE']=pd.to_datetime(frame.SETTLEMENTDATE)
    frame=frame[frame.SETTLEMENTDATE.le(now_nem)]
    if frame.empty:raise ValueError('No observation available by first-received time')
    rows=[]
    for ic in c['connectors']:
        f=frame[frame.INTERCONNECTORID.eq(ic['id'])].copy()
        if f.empty:continue
        for col in ['RUNNO','INTERVENTION']:
            f[col]=pd.to_numeric(f[col],errors='coerce') if col in f else 0
        f=f.sort_values(['SETTLEMENTDATE','INTERVENTION','RUNNO']);r=f.iloc[-1]
        if now_nem-r.SETTLEMENTDATE>pd.Timedelta(minutes=30):raise ValueError('Latest dispatch is more than 30 minutes old')
        values={'flow':float(r.MWFLOW),'export':float(r.EXPORTLIMIT),'import':float(r.IMPORTLIMIT)}
        for lead in range(1,337):
            for target,value in values.items():
                rows.append({'origin':origin,'delivery':origin+pd.Timedelta(minutes=30*lead),'lead':lead,
                    'ic':ic['id'],'target':target,'prediction':value,'observed_at':r.SETTLEMENTDATE,
                    'received_at_utc':received.tz_convert('UTC'),'model':'live_latest_dispatch_persistence',
                    'claim':'Latest five-minute dispatch persisted; future target is half-hour mean'})
    if not rows:raise ValueError('No configured interconnector in source')
    store=Store(c);key=received.strftime('%Y%m%dT%H%M%S%f')+'_'+uuid.uuid4().hex[:8]
    path=store.root/'shadow'/key/'forecasts.parquet'
    if path.exists():raise FileExistsError('Immutable forecast already exists')
    store.parquet(path,pd.DataFrame(rows))
    store.json(path.with_suffix('.json'),{'source':source,'received_at_utc':received.tz_convert('UTC'),
        'origin_nem':origin,'forecast_sha256':digest(path),'rows':len(rows),'operational_model':'baseline only',
        'unavailable':['learned model with verified publication lineage','live calibrated contraction classifier']})
    return path


def run_shadow(c):
    from nemic.common import session
    from nemic.ingest import extract
    store=Store(c);base='https://nemweb.com.au/Reports/CURRENT/DispatchIS_Reports/'
    s=session();response=s.get(base,timeout=(20,60));response.raise_for_status()
    urls=[urljoin(base,x) for x in re.findall(r'HREF=["\']([^"\']+)',response.text,re.I)]
    urls=[u for u in urls if urlparse(u).hostname=='nemweb.com.au' and re.search(r'PUBLIC_DISPATCHIS_\d+.*\.zip$',u,re.I)]
    if not urls:raise ValueError('No current dispatch archive in public listing')
    url=sorted(urls)[-1];cap=20_000_000
    with store.reserve(cap*5):
        with s.get(url,stream=True,timeout=(20,60)) as r:
            r.raise_for_status();chunks=[];size=0
            for chunk in r.iter_content(262144):
                size+=len(chunk)
                if size>cap:raise ValueError('Live dispatch archive exceeded 20 MB cap')
                chunks.append(chunk)
        blob=b''.join(chunks);received=pd.Timestamp.now(tz='UTC')
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            if sum(x.file_size for x in z.infolist())>80_000_000:raise ValueError('Expanded live archive exceeded 80 MB cap')
            if any(x.filename.lower().endswith('.zip') for x in z.infolist()):raise ValueError('Nested live archives unsupported')
        f=extract(io.BytesIO(blob),['DISPATCHINTERCONNECTORRES']).get('DISPATCHINTERCONNECTORRES')
        if f is None:raise ValueError('Missing dispatch interconnector table')
        # Source contents are not retained; the parsed observations and hash are retained.
    path=record(c,f,received,{'url':url,'bytes':size,'sha256':hashlib.sha256(blob).hexdigest(),'raw_retained':False})
    store.parquet(path.parent/'source_observations.parquet',f)
    print(json.dumps({'status':'recorded','path':str(path),'model':'live persistence baseline; no learned model promoted'}),flush=True)


def score_shadow(c):
    from .validation import regression_score
    store=Store(c);targets=ROOT/'data/processed/targets.parquet';rows=[]
    y=pd.read_parquet(targets).set_index(['time','ic'])
    for path in sorted((store.root/'shadow').glob('*/forecasts.parquet')):
        p=pd.read_parquet(path)
        for (ic,target),group in p.groupby(['ic','target']):
            actual=y[target].reindex(pd.MultiIndex.from_arrays([group.delivery,group.ic])).to_numpy()
            rows.append({'record':path.parent.name,'ic':ic,'target':target,**regression_score(actual,group.prediction.to_numpy())})
    store.json(store.root/'shadow_scores.json',{'scores':rows,'target_source':str(targets),'target_sha256':digest(targets),
        'limitation':'Only outcomes present in the retained target dataset are scored; immature or absent outcomes are not fabricated.'})
    print(json.dumps({'records':len(rows),'scored_pairs':sum(r['n'] for r in rows)}),flush=True)
