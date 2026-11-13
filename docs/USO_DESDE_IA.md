# Usar Agente Puro desde cualquier IA

Agente Puro se puede invocar de tres formas, todas sin dependencias nuevas:

| Vía | Para | Arranque |
|---|---|---|
| **MCP (stdio)** | Claude Desktop, Claude Code, Cursor, Grok/otros clientes MCP | `agente-puro-mcp` o `python -m omega_meta.mcp` |
| **HTTP local** | Cualquier programa o IA con *function calling* | `omega-meta --serve` → `http://127.0.0.1:8787` |
| **CLI** | Scripts o copiar y pegar en IAs sin herramientas | `python pure_agent.py --text ... --evidence ...` |

Las instrucciones para la IA (cuándo llamar y cómo obedecer el veredicto) están en
[`skills/agente-puro/SKILL.md`](../skills/agente-puro/SKILL.md), en formato estándar de *Agent Skill*.

## Herramientas

| MCP | HTTP | Función del motor |
|---|---|---|
| `evaluar` | `POST /evaluar` (`/tools/evaluar`) | `AgentePuro.process` + `ingest_evidence` |
| `verificar_afirmacion` | `POST /verificar_afirmacion` | `AgentePuro.ingest_evidence` / `assess_claim` (Truth Engine) |
| `firewall_check` | `POST /firewall_check` | `firewall.validate` sobre `compile_instruction` |
| `acciones_pendientes` | `GET /acciones_pendientes` | registro del adaptador de decisiones `PENDING_AUTHORIZATION` de NEXUS |
| `audit_verify` | `GET /audit_verify` | `verify_audit` + `root.root_hash` vs. línea base |

`GET /tools` devuelve los mismos esquemas JSON que `tools/list` de MCP. Las rutas originales
(`/health`, `/process`, `/diagnostics`) no cambian.

## Garantías del adaptador (con prueba en `tests/test_adapters.py`)

- La IA cliente es `ai_client`: **nunca** fuente ni revisora. No puede registrarse como verificadora y
  su evidencia con revisores no registrados no cuenta (`test_unregistered_or_missing_review_is_not_fact`).
- Los verificadores solo se registran al arrancar (`--verifiers`), decisión de la persona.
- **No existe** herramienta ni ruta para autorizar efectos: quedan en `PENDING_AUTHORIZATION`
  (`test_adapter_never_authorizes_side_effects`).
- Auditoría manipulada ⇒ `audit_verify.valid = false` y las siguientes peticiones dan `HALT`
  (`test_tampered_audit_halts`).
- HTTP solo en `127.0.0.1`, y las rutas de herramientas exigen `Content-Type: application/json`
  para que una página web no pueda llamarlas como «petición simple».
- Fail-closed: un error interno devuelve `HALT`.

## Protocolo MCP implementado

JSON-RPC 2.0, un mensaje por línea en stdin/stdout: `initialize` (versiones `2025-06-18`,
`2025-03-26`, `2024-11-05`), `notifications/initialized`, `ping`, `tools/list`, `tools/call`
(con `content` de texto y `structuredContent`). No implementa recursos, prompts ni transporte
HTTP/SSE de MCP; para HTTP usa la API local.

## Límites

- El veredicto es obligatorio solo si el cliente obliga a la IA a pedirlo antes de actuar.
  Agente Puro clasifica; no intercepta por sí mismo las herramientas de otra app.
- `acciones_pendientes` vive en memoria del proceso del servidor: se vacía al reiniciarlo
  (el historial completo queda en la auditoría si usas `--runtime-dir`).
- Un mismo `runtime_dir` debe usarlo un solo proceso a la vez (otro proceso escribiendo se ve como
  manipulación). Usa uno distinto para el servidor MCP y para la CLI.
