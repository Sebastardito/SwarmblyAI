# Architecture of release 3.4 · Tools

Status: accepted, 2026-11-18 (decisions D-005 to D-008). Built from three read-only audits (T0.1 App, T0.2 research, T0.3 Core and swarm batches). Open points are marked **[decision]** and listed at the end.

## Principles that do not change

- Local by default; a third party is an explicit choice per project and per role, with a receipt.
- Every byte that leaves goes through `egress.check_call` and appears in the privacy receipt. Local tool activity is recorded too.
- Text that comes from a tool (MCP results and descriptions, web pages, skills, author records) is data, never instructions; it cannot widen permissions.
- Nothing runs without the user's yes: no MCP server starts by itself, importing a skill never runs anything, and recipe 5's script runs only after approval, in a sandbox.
- No wire-protocol change in 3.4: tools and agent steps run on the user's computer. A new task kind on the wire needs a SWIP and a version decision.

## Components

### 1. Tool broker (App, `swarmbly_app/tools/broker.py`)

One entry point for every tool call: `broker.invoke(call) -> ToolResult`.

- `ToolSpec`: `id` (`<provider>/<name>`), provider kind (`builtin`, `mcp_local`, `mcp_remote`, `author`, `sandbox`), destination (URL or `local`), input schema, the hash of the description and schema the user approved.
- `ToolCall`: spec id, arguments, request id, purpose, approval token.
- Before a call: the spec is approved and its hash unchanged; the arguments validate against the stored schema; the approval token matches when the tool needs a yes per call (sandbox, author search).
- During a call: `egress.purpose(kind)`; remote destinations go through `egress.check_call` with new kinds `TOOL_REMOTE` and `AUTHOR_QUERY` (never `PUBLIC_QUERY`, which is always allowed); local tools are recorded with `egress.record` (today `check_call` returns before recording a local destination); work in threads uses `egress.carry`.
- After a call: the result is wrapped as quoted data with its source and hash, sized, and attached to `meta.tools`; the receipt lists the call.
- Approvals are stored per project: `{spec_id, hash, granted_at}`; a one-time token per run for actions that need a yes each time.

### 2. MCP client (App, `swarmbly_app/tools/mcp.py`)

- Official `mcp` SDK (MIT). Local servers: the user adds a server and sees the exact command, arguments, folder and environment; it starts only when the user runs it from the app, never at launch. Remote servers (Streamable HTTP): always a third party, authorised per host like a model server.
- On connect: list every tool; the user approves a subset; the manifest hash is stored. A change in the list suspends the server until the user approves again.
- **[D-008]** "Effective permissions equal declared ones" is enforced at the tool level (allowlist, schema, manifest hash, destinations). A local MCP server still runs with the user's own rights; the app says so.

### 3. Skills (App, `swarmbly_app/skills.py`)

- Agent Skills format (`SKILL.md`, frontmatter `name` and `description`). Only `SKILL.md` and `.md`/`.txt` references are read; `scripts/`, executables, links, archives and large files are ignored. `allowed-tools` is shown and never granted.
- A skill is offered by its description and activated by the user; its body enters the prompt as quoted, labelled material.

### 4. Author search (App, through the broker)

- ORCID, OpenAlex and PubMed, reusing `engine.providers._get` and `web_search._pubmed`. The author's name is the payload, so it is never stripped: the user approves the exact name and the services before anything is sent, and the receipt marks it as a personal name.

### 5. Recipe 5, data with code (App)

- Flow: the model writes a short Python script for the user's table or file; the app shows it; the user approves it; it runs in the sandbox with the data read-only and a scratch folder; the answer gives the result, the script and its output.
- `SandboxRunner` interface: `run(script, inputs, limits) -> {stdout, stderr, files, trapped}`. Limits: time, memory, output size; no network; writes only to scratch.
- **[D-005]** Backend: WebAssembly CPython (`wasi-python` over wasmtime) as the primary candidate, gated by a spike; Docker as fallback; SQL-only as degraded mode. Audit hooks, RestrictedPython and plain subprocesses are not a boundary.
- An open battery with expected results computed beforehand, and isolation tests on each supported system (network canary, read-only data hash, writes outside scratch, time, memory, output, approval token).

### 6. Recipe 4, a list on the swarm (App)

- The user pastes a list or picks a CSV column and writes the operation for each item; the existing batch path (`Orchestrator.run`, admission, scheduler, item vote) runs unchanged; a table is built by code from the item votes, with a status column (answered, missing, disagreement). Agreement is reported as agreement, not correctness.
- Before anything goes to other nodes, the user sees what leaves (the items and the operation) and chooses LAN swarm or this computer. Long lists are cut into waves under a ceiling.
- An open fixture with expected cells and a scorer for coverage, order and duplicates.

### 7. Anthropic provider and embeddings role (App)

- `inference/anthropic.py` implementing `StreamBackend` over the Messages API, with `egress.check_call` before each request; registered in `BackendRegistry.resolve` and `build` (which must stop falling back to Ollama for an unknown kind). Always a third party; key in the keychain; a node with this model never serves the swarm.
- An `embeddings` role routed through `roles.choose`, carrying passages; served by a local or OpenAI-compatible server (Anthropic has no embeddings endpoint).

### 8. Agent runtime (SwarmblyCore)

- **[D-007]** A separate Core package. A small runtime with a bounded loop (plan step → model or tool → observation → stop), built from injected callables (`generate`, `execute_tool`, `policy`, `budget`); no import of App code, no egress inside Core. Steps and tools are local in 3.4. The App supplies the broker as `execute_tool`.

## Work packages and order

| WP | Content | Depends on | Repo |
|---|---|---|---|
| WP0 | Test environment for worktrees; Python 3.11 minimum **[D-006]** | — | App |
| WP1 | Broker, tool kinds in egress, approvals, receipt | WP0 | App |
| WP2 | Anthropic provider; embeddings role | WP0 | App |
| WP3 | Recipe 4 and its fixture | WP0 | App, umbrella bench |
| WP4 | Skills loader | WP1 | App |
| WP5 | MCP client | WP1, D-A4 | App |
| WP6 | Author search | WP1 | App |
| WP7 | Sandbox spike → runner → recipe 5 → battery and isolation tests | D-A1; runner needs WP1 | App, umbrella bench |
| WP8 | Agent runtime in Core; App adapter | D-A3; adapter needs WP1 | umbrella (Core), App |
| WP9 | Open battery 3.4, a new sealed bank (written by the maintainer), release | all | all |

App changes that touch the same files (`chat.py`, `config.py`, `egress.py`, `recipes.py`, `web/js/chat.js`) are serialised; independent packages run in parallel on their own branches.

## Decisions taken by the maintainer (2026-11-18)

D-A1 → D-005 (wasi-python after a spike), D-A2 → D-006 (Python 3.11), D-A3 → D-007 (separate Core package), D-A4 → D-008 (tool level). The options as presented:

- **D-A1** Sandbox for recipe 5: `wasi-python` (cross-platform, no network by construction, pandas included; but version 0.1.x, first released 2026-10-17, one maintainer, about 250 MB) after a spike, with Docker as fallback; or native sandboxes per system; or SQL-only in 3.4.
- **D-A2** Python 3.11 as the minimum (3.10 lost security support on 2026-10-01; the MCP SDK documents 3.11+; `wasi-python` requires 3.11).
- **D-A3** Where the agent runtime lives in Core: inside `swarmbly_v0` (forces a new App pin, mixes with the measurement harness that ADR-001 keeps apart) or a separate Core package.
- **D-A4** Meaning of "effective permissions equal declared ones" for MCP: tool level in 3.4, or also the operating system (each server in a sandbox).
