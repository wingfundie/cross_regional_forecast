"""Check evidence against report inputs, render offline and write a verified bundle."""
import hashlib,json
from pathlib import Path
from urllib.parse import unquote,urlsplit
from zipfile import ZipFile,ZIP_DEFLATED
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parent
def frame(f):return pd.read_csv(out/f)
def verify():
    net=frame('network/predictions.csv')
    metrics=frame('network/scores.csv')
    assert set(net.lead)=={10,21,42}
    for r in metrics.itertuples():
        g=net[net.link.eq(r.link)&net.partition.eq(r.partition)&net.lead.eq(r.lead)&net.method.eq(r.method)]
        actual='actual_'+r.target.removeprefix('adjusted_')
        if r.target not in g:continue
        e=(g[r.target]-g[actual]).dropna()
        assert len(e)==r.n and np.isclose(e.abs().mean(),r.mae),(r,len(e))
    p=frame('points/coherent_predictions.csv')
    for r in frame('points/coherent_scores.csv').itertuples():
        g=p[p.phase.eq(r.phase)&p.lead.eq(r.lead)&p.method.eq(r.method)&p.point.eq(r.point)]
        assert len(g)==r.n and np.isclose((g.actual-g.forecast).abs().mean(),r.mae)
    rep=frame('points/qni_replay.csv')
    assert len(rep)==90 and rep.replay_error.abs().max()<1e-6
    for f in ['points/predictions.csv','points/coherent_predictions.csv','network/predictions.csv']:
        d=frame(f)
        assert (pd.to_datetime(d.origin)<pd.to_datetime(d.end if 'end' in d else d.day)).all()
    for f in frame('routing.csv').Evidence:assert (out/f).is_file(),f
    doc=BeautifulSoup((out/'index.html').read_text(encoding='utf8'),'html.parser')
    for a in doc.select('a[href]'):
        u=urlsplit(a['href'])
        if u.scheme:continue
        if u.path:assert (out/unquote(u.path)).is_file(),u.path
        if not u.path and u.fragment:assert doc.find(id=u.fragment),u.fragment
    with sync_playwright() as pw:
        b=pw.chromium.launch()
        for width in [390,1366]:
            page=b.new_page(viewport={'width':width,'height':850},offline=True)
            page.goto((out/'index.html').as_uri())
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth && [...document.images].every(i=>i.complete && i.naturalWidth)')
            page.screenshot(path=str(out/f'preview_{width}.png'))
            page.close()
        b.close()
    return dict(network_metric_groups=len(metrics),coherent_metric_groups=len(frame('points/coherent_scores.csv')),
                qni_native_replays=len(rep),offline_viewports=[390,1366])
def package():
    checks=verify()
    artifact=out/'report_and_evidence.zip'
    manifest=out/'manifest.json'
    paths=sorted(f for f in out.rglob('*') if f.is_file() and f not in [artifact,manifest] and '__pycache__' not in f.parts)
    records={p.relative_to(out).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
    manifest.write_text(json.dumps(dict(checks=checks,files=records),indent=2),encoding='utf8')
    with ZipFile(artifact,'w',ZIP_DEFLATED) as z:
        for p in [manifest,*paths]:z.write(p,p.relative_to(out).as_posix())
    with ZipFile(artifact) as z:
        assert z.testzip() is None
        for k,v in records.items():assert hashlib.sha256(z.read(k)).hexdigest()==v['sha256']
    print(checks,artifact.stat().st_size)
if __name__=='__main__':package()
