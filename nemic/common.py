from pathlib import Path
import json, ssl, time, hashlib, re
from urllib.parse import urljoin
import requests, certifi

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RAW = DATA / 'raw'
PROCESSED = DATA / 'processed'
RESULTS = ROOT / 'results'
MODELS = ROOT / 'models'
for path in [RAW, PROCESSED, RESULTS, MODELS]:
    path.mkdir(parents=True, exist_ok=True)

def dump(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding='utf-8')

def session():
    s = requests.Session()
    # Respect Windows trust anchors, including this workstation's enterprise CA.
    # Certificate and hostname verification remain enabled.
    if hasattr(ssl, 'enum_certificates'):
        bundle = ROOT / 'certificates.pem'
        if not bundle.exists():
            certs = [ssl.DER_cert_to_PEM_cert(c) for store in ['ROOT','CA']
                     for c, enc, trust in ssl.enum_certificates(store) if enc == 'x509_asn']
            bundle.write_text(Path(certifi.where()).read_text() + '\n' + ''.join(certs))
        s.verify = str(bundle)
    s.headers['User-Agent'] = 'NEM-IC-Research/1.0 (public-data-research; cached requests)'
    return s

def get(url, **kwargs):
    for attempt in range(5):
        try:
            r = session().get(url, timeout=(20, 180), **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 10))

def links(url):
    cache = DATA / 'listings' / (hashlib.sha256(url.encode()).hexdigest() + '.html')
    if cache.exists():
        body = cache.read_text(encoding='utf-8')
    else:
        body = get(url).text
        cache.parent.mkdir(exist_ok=True)
        cache.write_text(body, encoding='utf-8')
    return [urljoin(url, x) for x in re.findall(r'HREF=["\']([^"\']+)', body, flags=re.I)]

IC = {
    'NSW1-QLD1': dict(name='QNI', source='NSW1', sink='QLD1', label='NSW → QLD'),
    'N-Q-MNSP1': dict(name='Directlink', source='NSW1', sink='QLD1', label='NSW → QLD'),
    'VIC1-NSW1': dict(name='VNI', source='VIC1', sink='NSW1', label='VIC → NSW'),
    'V-SA': dict(name='Heywood', source='VIC1', sink='SA1', label='VIC → SA'),
    'V-S-MNSP1': dict(name='Murraylink', source='VIC1', sink='SA1', label='VIC → SA'),
    'T-V-MNSP1': dict(name='Basslink', source='TAS1', sink='VIC1', label='TAS → VIC'),
}
TARGETS = ['flow', 'export', 'import', 'export_tight', 'import_tight']
REGIONS = ['NSW1', 'QLD1', 'VIC1', 'SA1', 'TAS1']
