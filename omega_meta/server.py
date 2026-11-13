"""API HTTP local (solo stdlib) en 127.0.0.1:  GET /health · GET /diagnostics · POST /process"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core.engine import AgentePuro

MAX_BODY = 64 * 1024


def make_handler(agent: AgentePuro):
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # silencioso; todo queda en la auditoría
            pass

        def do_GET(self):
            if self.path == "/health":
                return self._send(200, {"status": "ok", "engine": "AGENTE_PURO_NRE_AMM_OMEGA"})
            if self.path == "/diagnostics":
                with lock:
                    return self._send(200, agent.diagnostics())
            return self._send(404, {"error": "NOT_FOUND"})

        def do_POST(self):
            if self.path != "/process":
                return self._send(404, {"error": "NOT_FOUND"})
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return self._send(413, {"error": "BODY_SIZE"})
            try:
                req = json.loads(self.rfile.read(n))
                text = req["text"]
            except Exception:  # noqa: BLE001
                return self._send(400, {"error": "INVALID_JSON_OR_MISSING_TEXT"})
            with lock:  # fail-closed: process() nunca lanza; devuelve HALT ante error
                o = agent.process(text, session_id=str(req.get("session", "http")),
                                  external_data=req.get("external_data"))
            return self._send(200, o)

    return H


def serve(cfg, runtime_dir="omega_runtime", port=8787, host="127.0.0.1"):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Solo se permite escuchar en 127.0.0.1")
    agent = AgentePuro(cfg, runtime_dir=runtime_dir)
    srv = ThreadingHTTPServer((host, port), make_handler(agent))
    print(f"Agente Puro escuchando en http://{host}:{port}  (/health, /process, /diagnostics)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return srv
