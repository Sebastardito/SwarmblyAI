# swarmbly-agent

Local, dependency-free agent runtime for Swarmbly AI 3.4.

[English](#english) · [Español](#español)

---

## English

`swarmbly-agent` 0.1.0 is a separate distribution inside `SwarmblyCore/agent/`.
It is the small runtime decided in D-007: a bounded local loop with a model, a
tool executor and a permission policy, all injected by the application. It has
no dependencies outside the Python standard library and no network, subprocess
or egress code. Tool calls are local in 3.4; the App supplies its broker as
`execute_tool`.

The package does not change the wire protocol and does not import the App, the
LCE or `swarmbly_v0`. It is a leaf: the App drives it, not the other way around.

### What it does

- One `Final` or `ToolRequest` per step, then a stop on the answer, a budget,
  an approval pause, or a repeated request.
- Observations enter the conversation as quoted JSON data with a label, source,
  SHA-256 and truncation flag. They never become system or user instructions,
  and the runtime never derives an action from an observation.
- Policy decisions are `Allow`, `Deny(reason)` and `NeedsApproval(reason)`.
  A denial is shown to the model as data, so it can continue. An approval pause
  returns a serialisable `RunState`; `resume(state, approved, token)` continues.
- `RunState.to_dict()` / `from_dict()` round-trip the whole run: steps, pending
  request, task, tools, counters and stop reason. There is no hidden state.

### Install and test

```bash
pip install -e SwarmblyCore/agent
cd SwarmblyCore/agent && python -m pytest -q tests
```

### Quick start

```python
from swarmbly_agent import (
    AgentRuntime, Allow, Budget, Observation, parse_json_action,
)

def generate(messages, tools):
    return parse_json_action(model_call(messages, tools))

def execute_tool(request, token):
    # The App's broker: validates the token, applies egress, returns data.
    return Observation(tool=request.tool, ok=True, content="...", source="local")

def policy(request):
    return Allow()  # or Deny("not approved") / NeedsApproval("remote tool")

runtime = AgentRuntime(generate, execute_tool, policy, Budget(max_steps=6))
state = runtime.run("Summarise the selected files.", tools)
if state.status == "awaiting_approval":
    state = runtime.resume(state, approved=True, token="one-time-token")
```

`generate` receives the conversation and the tool descriptors. `execute_tool`
receives the request and, only after an approved resume, the token. This
package never calls either on its own.

### Action protocol

Models without native tool calling answer with exactly one JSON object:

```json
{"action": "final", "text": "..."}
{"action": "tool", "tool": "echo", "arguments": {"text": "hi"}, "why": "needed"}
```

`parse_json_action` is strict about the envelope: malformed JSON, two objects,
prose around the object, duplicate keys and wrong known types all return a
`Final` carrying the original text and a `parse_note`. It never guesses a tool
call. Unknown fields are ignored, following SPEC section 3.

### Public API

- `AgentRuntime(generate, execute_tool, policy, budget, clock)` with
  `run(task, tools)` and `resume(state, approved, token)`.
- `Final(text, parse_note=None)`, `ToolRequest(tool, arguments, why)`.
- `ToolDescriptor(name, description, input_schema)`.
- `Observation(tool, ok, content, source, sha256, truncated)`.
- `Step(index, action, observation, started, ended)`.
- `Budget(max_steps, max_tool_calls, max_seconds, max_observation_chars)`.
- `RunState(status, steps, pending, stop_reason, ...)` and its serialisation.
- `Allow`, `Deny(reason)`, `NeedsApproval(reason)`.
- `parse_json_action(text)`.

The boundary is the one in the specification and in
`ADR-001_instrument_boundary.md`: a tool result is data, and only the injected
application decides what may run.

### License

AGPL-3.0-or-later. See `../LICENSE`.

---

## Español

`swarmbly-agent` 0.1.0 es una distribución separada dentro de
`SwarmblyCore/agent/`. Es el runtime pequeño que decide D-007: un bucle local
acotado con un modelo, un ejecutor de herramientas y una política de permisos,
todos inyectados por la aplicación. No tiene dependencias fuera de la
biblioteca estándar de Python ni código de red, subproceso o salida. En 3.4 las
llamadas a herramientas son locales; la App entrega su broker como
`execute_tool`.

El paquete no cambia el protocolo de red y no importa la App, el LCE ni
`swarmbly_v0`. Es una hoja: la App lo dirige a él, no al contrario.

### Qué hace

- Un `Final` o un `ToolRequest` por paso; después se detiene por respuesta,
  presupuesto, pausa de aprobación o petición repetida.
- Las observaciones entran en la conversación como datos JSON citados, con
  etiqueta, origen, SHA-256 y marca de truncado. Nunca se convierten en
  instrucciones del sistema o del usuario, y el runtime nunca deduce una acción
  a partir de una observación.
- Las decisiones de la política son `Allow`, `Deny(reason)` y
  `NeedsApproval(reason)`. Una denegación se muestra al modelo como dato, así
  que puede continuar. Una pausa de aprobación devuelve un `RunState`
  serializable; `resume(state, approved, token)` continúa.
- `RunState.to_dict()` / `from_dict()` conservan la ejecución completa: pasos,
  petición pendiente, tarea, herramientas, contadores y motivo de parada. No
  hay estado oculto.

### Instalación y pruebas

```bash
pip install -e SwarmblyCore/agent
cd SwarmblyCore/agent && python -m pytest -q tests
```

### Inicio rápido

```python
from swarmbly_agent import (
    AgentRuntime, Allow, Budget, Observation, parse_json_action,
)

def generate(messages, tools):
    return parse_json_action(model_call(messages, tools))

def execute_tool(request, token):
    # El broker de la App: valida el token, aplica egress y devuelve datos.
    return Observation(tool=request.tool, ok=True, content="...", source="local")

def policy(request):
    return Allow()  # o Deny("no aprobado") / NeedsApproval("herramienta remota")

runtime = AgentRuntime(generate, execute_tool, policy, Budget(max_steps=6))
state = runtime.run("Resume los archivos seleccionados.", tools)
if state.status == "awaiting_approval":
    state = runtime.resume(state, approved=True, token="token-de-un-uso")
```

`generate` recibe la conversación y los descriptores de herramientas.
`execute_tool` recibe la petición y, solo tras un `resume` aprobado, el token.
Este paquete nunca los llama por su cuenta.

### Protocolo de acción

Los modelos sin llamada nativa a herramientas responden con exactamente un
objeto JSON:

```json
{"action": "final", "text": "..."}
{"action": "tool", "tool": "echo", "arguments": {"text": "hola"}, "why": "hace falta"}
```

`parse_json_action` es estricto con el sobre: JSON mal formado, dos objetos,
prosa alrededor del objeto, claves duplicadas y tipos conocidos incorrectos
devuelven un `Final` con el texto original y una `parse_note`. Nunca adivina una
llamada a herramienta. Los campos desconocidos se ignoran, según la sección 3
de la especificación.

### API pública

- `AgentRuntime(generate, execute_tool, policy, budget, clock)` con
  `run(task, tools)` y `resume(state, approved, token)`.
- `Final(text, parse_note=None)`, `ToolRequest(tool, arguments, why)`.
- `ToolDescriptor(name, description, input_schema)`.
- `Observation(tool, ok, content, source, sha256, truncated)`.
- `Step(index, action, observation, started, ended)`.
- `Budget(max_steps, max_tool_calls, max_seconds, max_observation_chars)`.
- `RunState(status, steps, pending, stop_reason, ...)` y su serialización.
- `Allow`, `Deny(reason)`, `NeedsApproval(reason)`.
- `parse_json_action(text)`.

El límite es el de la especificación y el de
`ADR-001_instrument_boundary.md`: el resultado de una herramienta es un dato, y
solo la aplicación inyectada decide qué puede ejecutarse.

### Licencia

AGPL-3.0-or-later. Véase `../LICENSE`.
