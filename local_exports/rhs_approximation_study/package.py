"""Hash and package compact local evidence after building and verifying the report."""
from pathlib import Path
import hashlib
import json
from zipfile import ZipFile,ZIP_DEFLATED

out=Path(__file__).resolve().parent
archive=out/'report_and_evidence.zip'
manifest=out/'manifest.json'
def include(p):
    return (p.is_file() and p not in (archive,manifest)
            and '__pycache__' not in p.parts and p.suffix.lower() in
            {'.csv','.tsv','.json','.md','.py','.html','.png'})
files=sorted(p for p in out.rglob('*') if include(p))
member_info=[dict(path=p.relative_to(out).as_posix(),bytes=p.stat().st_size,
                  sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files]
manifest.write_text(json.dumps({'market_time':'UTC+10 interval ending','files':member_info},indent=2),encoding='utf8')
with ZipFile(archive,'w',compression=ZIP_DEFLATED) as bundle:
    for p in [*files,manifest]:bundle.write(p,p.relative_to(out).as_posix())
with ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    for meta in member_info:
        assert hashlib.sha256(bundle.read(meta['path'])).hexdigest()==meta['sha256']
print(len(files),'hashed deliverables;',archive.stat().st_size,'packaged bytes')
