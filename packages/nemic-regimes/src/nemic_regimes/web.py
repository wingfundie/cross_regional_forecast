"""Local HTML surface; calculations use the public package functions."""
from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import gzip
import socket
from pathlib import Path
from urllib.parse import urlparse
import numpy as np
from .core import NUMERIC_FEATURES, _clean


def serve(bundle,host="127.0.0.1",port=8061,input_dir=None):
    if host not in {"127.0.0.1","localhost","::1"}:raise ValueError("Selector binds to localhost")
    class Handler(BaseHTTPRequestHandler):
        def respond(self,code,payload,mime="application/json"):
            blob=payload.encode() if isinstance(payload,str) else json.dumps(_clean(payload),allow_nan=False).encode()
            compressed=len(blob)>16384 and "gzip" in self.headers.get("Accept-Encoding","")
            if compressed:blob=gzip.compress(blob)
            self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            self.send_response(code);self.send_header("Content-Type",mime+"; charset=utf-8");self.send_header("Content-Length",str(len(blob)))
            self.send_header("Connection","close")
            if compressed:self.send_header("Content-Encoding","gzip");self.send_header("Vary","Accept-Encoding")
            self.end_headers()
            for offset in range(0,len(blob),16384):self.wfile.write(blob[offset:offset+16384])
            self.wfile.flush();self.close_connection=True
        def do_GET(self):
            path=urlparse(self.path).path
            if path=="/":return self.respond(200,(Path(__file__).parent/"static/selector.html").read_text(encoding="utf-8"),"text/html")
            if path=="/api/health":return self.respond(200,{"status":"ok","bundle_id":bundle.metadata["bundle_id"]})
            if path=="/api/catalogue":
                meta=bundle.metadata
                fields={f:{"units":"C" if "temperature" in f else "%" if "humidity" in f or "cloud" in f else "m/s" if f=="corridor_wind_ms" else "W/m2" if f=="corridor_radiation_wm2" else "MW"} for f in NUMERIC_FEATURES}
                eras={n:sorted(g.era.unique()) for n,g in bundle.panel.groupby("connector")}
                sets={n:sorted({x for value in g.active_sets for x in value.split("|") if x}) for n,g in bundle.panel.groupby("connector")}
                return self.respond(200,{"bundle_id":meta["bundle_id"],"as_of":meta["as_of"],"data_end":meta["training_cutoff"],"eras":eras,
                     "current_eras":meta["current_eras"],"settings":meta["settings"],"features":fields,"sets":sets,
                     "assets":meta.get("assets",[]),"unsupported_measurements":meta.get("unsupported_measurements",[])})
            return self.respond(404,{"error":"Unknown route"})
        def do_POST(self):
            try:
                length=int(self.headers.get("Content-Length",0))
                if length>131072:raise ValueError("Request too large")
                body=json.loads(self.rfile.read(length))
                if self.path=="/api/select":result=bundle.select(body)
                elif self.path=="/api/profile":
                    q=dict(body);quarter=q.pop("quarter");q.pop("half_hour",None)
                    result=bundle.profile(quarter,q).to_dict("records")
                elif self.path in {"/api/collect/grid","/api/collect/weather"}:
                    from .collect import latest_grid,weather
                    fn=latest_grid if self.path.endswith("grid") else weather
                    result=fn(**body,output=input_dir or str((bundle.root or Path.cwd())/"collected_inputs"))
                else:return self.respond(404,{"error":"Unknown route"})
                return self.respond(200,result)
            except (ValueError,KeyError,TypeError) as exc:return self.respond(400,{"error":str(exc)})
            except Exception as exc:return self.respond(503,{"error":str(exc)})
        def log_message(self,format,*args):pass
    server=ThreadingHTTPServer((host,port),Handler)
    print(f"Conditional selector: http://{host}:{port}",flush=True)
    try:server.serve_forever()
    finally:server.server_close()
