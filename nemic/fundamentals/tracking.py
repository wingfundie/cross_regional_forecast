"""Durable job ownership, verified artifacts, atomic status views and restart recovery."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from pathlib import Path
import json
import os
import sqlite3
import threading
import time
import uuid
import shutil

import psutil

from nemic.experiments.core import ROOT, Store, clean, digest, fingerprint, load_config

DEFAULT = ROOT / 'configs/experiments/qni_vni_fundamentals_v3.json'


class ReadyForResume(RuntimeError):
    """Intentional bounded-batch exit; verified checkpoints remain reusable."""
STAGES = [
    ('methodology', [], 'Written methodology and research reviews exist before implementation'),
    ('engineering', ['methodology'], 'Adapters, feature construction and tracking pass tests'),
    ('inventory', ['methodology'], 'Source and local-outcome coverage audited'),
    ('acquisition', ['inventory'], 'Historical admissible inputs downloaded, parsed and hashed'),
    ('features', ['engineering', 'acquisition'], 'Matched origin/delivery features verified'),
    ('selection', ['features'], 'Chronological feature reduction benchmark complete'),
    ('training', ['selection'], 'All configured model cells assessed or explicitly unavailable'),
    ('assessment', ['training'], 'Paired uncertainty and risk acceptance tested'),
    ('packaging', ['assessment'], 'Saved models and reload parity verified'),
    ('reports', ['inventory'], 'Offline reports built from evidence and visually checked'),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(value, encoding='utf-8')
    os.replace(temporary, path)


class Ledger:
    def __init__(self, config=DEFAULT):
        self.c = load_config(config) if not isinstance(config, dict) else config
        self.store = Store(self.c)
        self.root = self.store.tracking_root
        self.data = self.store.root
        self.methodology = self.root / 'methodology/methodology.md'
        if not self.methodology.exists():
            raise RuntimeError('Methodology must be written before implementing/executing stages')
        self.method_hash = digest(self.methodology)
        snapshot = self.root / 'methodology/versions' / (self.method_hash + '.md')
        if not snapshot.exists(): atomic(snapshot, self.methodology.read_text(encoding='utf-8'))
        self.config_hash = fingerprint({k: v for k, v in self.c.items() if not k.startswith('_')})
        self.code_hash = fingerprint([(p.relative_to(ROOT).as_posix(), digest(p)) for p in sorted((ROOT/'nemic/fundamentals').glob('*.py'))])
        with self.connection() as con:
            con.executescript('''
            CREATE TABLE IF NOT EXISTS work (
              id TEXT PRIMARY KEY, status TEXT NOT NULL, dependencies TEXT NOT NULL,
              acceptance TEXT NOT NULL, detail TEXT, started TEXT, updated TEXT,
              finished TEXT, owner TEXT, pid INTEGER, process_start REAL, heartbeat REAL,
              methodology TEXT, config_hash TEXT, code_hash TEXT, artifacts TEXT,
              checkpoint TEXT, elapsed_seconds REAL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS audit (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, job TEXT,
              status TEXT, detail TEXT, owner TEXT);
            CREATE TABLE IF NOT EXISTS api_quota (
              day TEXT, source TEXT, calls INTEGER, PRIMARY KEY(day, source));
            ''')
            for ident, deps, acceptance in STAGES:
                con.execute('INSERT OR IGNORE INTO work(id,status,dependencies,acceptance,updated) VALUES(?,?,?,?,?)',
                            (ident, 'planned', json.dumps(deps), acceptance, now()))
        atomic(self.root/'execution_plan.json', json.dumps([dict(id=i, dependencies=d, acceptance=a) for i,d,a in STAGES], indent=2))

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.store.db, timeout=60)
        con.row_factory = sqlite3.Row
        try:
            con.execute('PRAGMA busy_timeout=60000')
            yield con
            con.commit()
        except BaseException:
            con.rollback(); raise
        finally:
            con.close()

    def register(self, ident, dependencies=(), acceptance='Verified artifact'):
        with self.connection() as con:
            con.execute('INSERT OR IGNORE INTO work(id,status,dependencies,acceptance,updated) VALUES(?,?,?,?,?)',
                        (ident,'planned',json.dumps(list(dependencies)),acceptance,now()))

    def valid(self, ident):
        with self.connection() as con:
            row = con.execute('SELECT * FROM work WHERE id=?', (ident,)).fetchone()
        if not row or row['status'] != 'completed': return False
        # Layered invalidation: immutable acquired/prepared evidence is governed by
        # its own content manifest, not by prose/report edits. Computational stages
        # remain tied to configuration and code contracts.
        immutable=ident.startswith(('acquisition/','weather/','coal/','prepare-indexes/')) or ident in ('inventory','acquisition')
        if not immutable and row['config_hash'] != self.config_hash:return False
        # Feature artifacts carry their own source/config/feature-contract generation
        # and daily hashes, so unrelated campaign/report edits do not invalidate them.
        if ident.startswith(('train/','selection/','assessment/','packaging/')) and row['code_hash']!=self.code_hash:return False
        if ident.startswith(('reports','report/')) and (row['methodology']!=self.method_hash or row['code_hash']!=self.code_hash):return False
        items = json.loads(row['artifacts'] or '[]')
        return bool(items) and all((ROOT/a['path']).exists() and digest(ROOT/a['path']) == a['sha256'] for a in items)

    def _change(self, con, ident, status, detail, owner=None, artifacts=None):
        con.execute('UPDATE work SET status=?,detail=?,updated=?,finished=?,methodology=?,config_hash=?,code_hash=?,artifacts=COALESCE(?,artifacts) WHERE id=?',
                    (status,detail,now(),now() if status in ('completed','failed','blocked','skipped') else None,
                     self.method_hash,self.config_hash,self.code_hash,json.dumps(artifacts) if artifacts is not None else None,ident))
        con.execute('INSERT INTO audit(time,job,status,detail,owner) VALUES(?,?,?,?,?)',(now(),ident,status,detail,owner))

    def record(self, ident, status, detail, artifacts=()):
        if status not in {'planned','ready','completed','failed','blocked','skipped'}: raise ValueError(status)
        self.register(ident)
        manifest = [dict(path=Path(p).resolve().relative_to(ROOT).as_posix(),sha256=digest(p),bytes=Path(p).stat().st_size) for p in artifacts]
        if status == 'completed' and not manifest: raise ValueError('Completion requires verified artifacts')
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT status FROM work WHERE id=?',(ident,)).fetchone()
            if row['status']=='running': raise RuntimeError('Cannot overwrite a running job; use its owner')
            self._change(con,ident,status,detail,artifacts=manifest)
        self.export()

    def checkpoint(self, ident, owner, value):
        with self.connection() as con:
            result=con.execute('UPDATE work SET checkpoint=?,heartbeat=?,updated=? WHERE id=? AND owner=? AND status=?',
                               (json.dumps(clean(value)),time.time(),now(),ident,owner,'running'))
            if result.rowcount != 1: raise RuntimeError('Lost job ownership')
        path=self.root/'checkpoints'/f'{fingerprint(ident)}.json'
        atomic(path,json.dumps(clean(dict(job=ident,checkpoint=value)),indent=2))

    @contextmanager
    def job(self, ident, dependencies=(), acceptance='Verified artifact'):
        self.register(ident,dependencies,acceptance)
        owner=uuid.uuid4().hex; start=time.monotonic(); proc=psutil.Process()
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            row=con.execute('SELECT * FROM work WHERE id=?',(ident,)).fetchone()
            if row['status']=='running': raise RuntimeError(f'Already running: {ident}')
            for dep in json.loads(row['dependencies']):
                r=con.execute('SELECT status FROM work WHERE id=?',(dep,)).fetchone()
                if not r or r['status']!='completed': raise RuntimeError(f'Unfinished dependency: {dep}')
            self._change(con,ident,'running','Started',owner)
            con.execute('UPDATE work SET owner=?,pid=?,process_start=?,heartbeat=?,started=? WHERE id=?',
                        (owner,os.getpid(),proc.create_time(),time.time(),now(),ident))
        stop=threading.Event()
        def heartbeat():
            while not stop.wait(30):
                with self.connection() as con:
                    con.execute('UPDATE work SET heartbeat=?,updated=? WHERE id=? AND owner=? AND status=?',
                                (time.time(),now(),ident,owner,'running'))
                self.export()
        thread=threading.Thread(target=heartbeat,daemon=True);thread.start(); self.export()
        artifacts=[]
        try:
            yield artifacts, lambda v: self.checkpoint(ident,owner,v)
            manifest=[dict(path=Path(p).resolve().relative_to(ROOT).as_posix(),sha256=digest(p),bytes=Path(p).stat().st_size) for p in artifacts]
            if not manifest: raise RuntimeError('No verified artifacts produced')
            with self.connection() as con:self._change(con,ident,'completed','Verified artifacts',owner,manifest)
        except BaseException as exc:
            status='ready' if isinstance(exc,ReadyForResume) else 'failed'
            with self.connection() as con:self._change(con,ident,status,f'{type(exc).__name__}: {exc}',owner)
            raise
        finally:
            stop.set();thread.join(timeout=5)
            with self.connection() as con:con.execute('UPDATE work SET elapsed_seconds=elapsed_seconds+? WHERE id=?',(time.monotonic()-start,ident))
            self.export()

    def reconcile(self):
        with self.connection() as con:
            rows=[dict(r) for r in con.execute('SELECT * FROM work')]
        for r in rows:
            if r['status']=='running':
                try: alive=abs(psutil.Process(r['pid']).create_time()-r['process_start'])<1
                except (psutil.NoSuchProcess,psutil.AccessDenied,TypeError): alive=False
                if not alive:
                    with self.connection() as con:self._change(con,r['id'],'failed','Interrupted owner; resume from verified checkpoint')
            elif r['status']=='completed' and not self.valid(r['id']):
                self.record(r['id'],'ready','Methodology/config/artifact changed; verification and dependent work require rerun')
        # Propagate invalidated prerequisites in topological passes.
        for _ in rows:
            changed=False
            with self.connection() as con:
                states={r['id']:r['status'] for r in con.execute('SELECT id,status FROM work')}
                for r in con.execute('SELECT * FROM work').fetchall():
                    if r['status']=='completed' and any(states.get(d)!='completed' for d in json.loads(r['dependencies'])):
                        self._change(con,r['id'],'ready','Dependency invalidated');changed=True
            if not changed:break
        self.export()

    def quota(self, source, count, cap):
        day=now()[:10]
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            used=con.execute('SELECT calls FROM api_quota WHERE day=? AND source=?',(day,source)).fetchone()
            used=used['calls'] if used else 0
            if used+count>cap:raise RuntimeError('Daily free API budget exhausted; resume another quota day')
            con.execute('INSERT OR REPLACE INTO api_quota VALUES(?,?,?)',(day,source,used+count))

    def modelling_seconds(self):
        with self.connection() as con:
            rows=con.execute("SELECT elapsed_seconds,started,status FROM work WHERE id LIKE 'train/%' OR id LIKE 'selection/%'").fetchall()
        return sum(float(r['elapsed_seconds'] or 0)+(max(0,time.time()-datetime.fromisoformat(r['started']).timestamp())
                   if r['status']=='running' and r['started'] else 0) for r in rows)

    def export(self):
        # Hold a write transaction while snapshotting/exporting to prevent an old
        # writer overwriting a newer derived status file.
        with self.connection() as con:
            con.execute('BEGIN IMMEDIATE')
            rows=[dict(r) for r in con.execute('SELECT * FROM work ORDER BY id')]
            events=[dict(r) for r in con.execute('SELECT * FROM audit ORDER BY seq')]
            for row in rows:
                if row['status']=='running' and row.get('pid'):
                    try:
                        proc=psutil.Process(row['pid']);row['worker_rss_bytes']=proc.memory_info().rss
                        row['worker_cpu_percent']=proc.cpu_percent(interval=None)
                    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
            disk=shutil.disk_usage(self.data)
            payload=dict(updated=now(),campaign=self.c['campaign'],methodology=self.method_hash,
                         resources=dict(disk_free_bytes=disk.free,disk_total_bytes=disk.total,
                                        memory_available_bytes=psutil.virtual_memory().available,
                                        memory_total_bytes=psutil.virtual_memory().total),jobs=rows)
            atomic(self.root/'status.json',json.dumps(payload,indent=2))
            atomic(self.root/'events.jsonl',''.join(json.dumps(r)+'\n' for r in events))
            lines=['# Execution status','',f'Updated: {payload["updated"]}','','| Job | Status | Detail |','|---|---|---|']
            lines += [f'| {r["id"]} | {r["status"]} | {(r["detail"] or "").replace(chr(10)," ").replace("|","/")} |' for r in rows]
            atomic(self.root/'STATUS.md','\n'.join(lines)+'\n')
            body=''.join('<tr>'+''.join('<td>'+escape(str(r.get(k) or ''))+'</td>' for k in ('id','status','detail','updated'))+'</tr>' for r in rows)
            atomic(self.root/'status.html','<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Campaign execution</title><style>body{font:16px system-ui;margin:30px}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.scroll{overflow:auto}</style></head><body><h1>QNI/VNI execution</h1><p>'+escape(payload['updated'])+'</p><div class="scroll"><table><tr><th>Job</th><th>Status</th><th>Detail</th><th>Updated</th></tr>'+body+'</table></div></body></html>')
            unfinished=[r for r in rows if r['status'] not in ('completed','skipped')]
            atomic(self.root/'handoff.md','# Handoff\n\nRead methodology/methodology.md and STATUS.md before resuming.\n\n'+ '\n'.join(f'- {r["id"]}: {r["status"]}; {r["detail"] or r["acceptance"]}' for r in unfinished)+'\n\nResume: python -m nemic.fundamentals run\n')
