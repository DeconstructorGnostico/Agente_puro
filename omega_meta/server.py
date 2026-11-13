"""API HTTP local (solo stdlib) en 127.0.0.1.

  GET  /health · GET /diagnostics · POST /process            (originales)
  GET  /tools                                                 (mismas herramientas que el servidor MCP)
  POST /tools/<nombre>   o   POST /<nombre>                   evaluar · verificar_afirmacion · firewall_check
  GET  /acciones_pendientes · GET /audit_verify

Las rutas de herramientas exigen `Content-Type: application/json` (una página web no puede
mandarlas como «petición simple» a tu localhost). No hay ninguna ruta que autorice efectos.
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .adapters.service import TOOLS, AgentePuroService, ToolError
from .core.engine import AgentePuro

MAX_BODY = 64 * 1024
TOOL_NAMES = {t["name"] for t in TOOLS}
GET_TOOLS = {"acciones_pendientes", "audit_verify"}


def make_handler(agent: AgentePuro, service: AgentePuroService | None = None):
    if service is None:
        service = AgentePuroService(agent)  # comparte el mismo motor
    lock = service.lock  # un solo candado: /process y las herramientas no corren en paralelo

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

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return None, (413, {"error": "BODY_SIZE"})
            try:
                return json.loads(self.rfile.read(n)), None
            except Exception:  # noqa: BLE001
                return None, (400, {"error": "INVALID_JSON"})

        def _tool(self, name, args):
            try:
                return self._send(200, service.call(name, args))
            except ToolError as e:
                return self._send(400, {"error": "INVALID_ARGUMENTS", "detail": str(e)})

        def do_GET(self):
            path = self.path.split("?", 1)[0].rstrip("/") or "/"
            if path == "/health":
                return self._send(200, {"status": "ok", "engine": "AGENTE_PURO_NRE_AMM_OMEGA"})
            if path == "/diagnostics":
                with lock:
                    return self._send(200, agent.diagnostics())
            if path == "/tools":
                return self._send(200, {"tools": TOOLS})
            name = path.removeprefix("/tools/").lstrip("/")
            if name in GET_TOOLS:
                return self._tool(name, {})
            return self._send(404, {"error": "NOT_FOUND"})

        def do_POST(self):
            path = self.path.split("?", 1)[0].rstrip("/")
            if path == "/process":
                req, err = self._body()
                if err:
                    return self._send(*err)
                if not isinstance(req, dict) or "text" not in req:
                    return self._send(400, {"error": "INVALID_JSON_OR_MISSING_TEXT"})
                with lock:  # fail-closed: process() nunca lanza; devuelve HALT ante error
                    o = agent.process(req["text"], session_id=str(req.get("session", "http")),
                                      external_data=req.get("external_data"))
                return self._send(200, o)
            name = path.removeprefix("/tools/").lstrip("/")
            if name not in TOOL_NAMES:
                return self._send(404, {"error": "NOT_FOUND"})
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self._send(415, {"error": "CONTENT_TYPE_MUST_BE_APPLICATION_JSON"})
            req, err = self._body() if int(self.headers.get("Content-Length") or 0) else ({}, None)
            if err:
                return self._send(*err)
            if not isinstance(req, dict):
                return self._send(400, {"error": "BODY_MUST_BE_A_JSON_OBJECT"})
            return self._tool(name, req)

    return H


def serve(cfg, runtime_dir="omega_runtime", port=8787, host="127.0.0.1", verifiers=None):
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("Solo se permite escuchar en 127.0.0.1")
    agent = AgentePuro(cfg, runtime_dir=runtime_dir)
    service = AgentePuroService(agent, verifiers=verifiers)
    srv = ThreadingHTTPServer((host, port), make_handler(agent, service))
    print(f"Agente Puro escuchando en http://{host}:{port}  (/health, /process, /tools, /evaluar, "
          f"/verificar_afirmacion, /firewall_check, /acciones_pendientes, /audit_verify)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return srv
