# Tasks · release 3.4 "Tools"

Status: `todo` · `running` · `review` · `done` · `blocked` · `dropped`. Verification says how the result was checked, not who did it.

## Phase 0 · Map and decide (read-only)

| ID | Repo | Goal | Depends on | Status | Verification | Next |
|---|---|---|---|---|---|---|
| T0.1 | SwarmblyApp | Map the App for 3.4: providers and roles, destinations policy and receipt, recipes and approval UI, search code, tables, tests; propose integration points | — | done | Spot checks of cited lines (egress, registry, test count, no eval/exec) | — |
| T0.2 | umbrella | Research: recipe 5 sandbox per OS, MCP Python client, Agent Skills format, author-search APIs | — | done | Package facts checked on PyPI (wasi-python 0.1.5, mcp 2.3.0, wasmtime 50.0.1) | D-A1, D-A2, D-A4 |
| T0.3 | umbrella | Map SwarmblyCore and the swarm batch path for the agent runtime and recipe 4; where the Anthropic provider goes | — | done | Spot checks (admission refuses attachments, Core pin, wire kind, batch limits) | D-A3 |
| T0.4 | all | Architecture of 3.4: broker interface, order of work, interface locks ([`ARCH_3.4.md`](ARCH_3.4.md)) | T0.1–T0.3 | done | Decisions D-005 to D-008 taken by the maintainer | — |

## Phase 1 · Foundations and independent packages

| ID | Repo | Goal | Depends on | Status | Verification | Next |
|---|---|---|---|---|---|---|
| T2.1 | SwarmblyApp | Test command (WP0); native Anthropic provider, always a third party; unknown backend kinds raise | — | done (`9a79c44`) | Linux checkout: 586 passed; code read (egress before every request) | — |
| T1.0 | SwarmblyApp | Python 3.11 minimum in the App (D-006) | — | done (`f54dee5`) | Suite on Linux, Python 3.11 | Installers and doctor in the umbrella |
| T1.1 | SwarmblyApp | Broker, tool kinds in egress, approvals, receipt (WP1) | T2.1 | done (`6fbc89c`) | Suite on Linux; code read | — |
| T4.1 | SwarmblyApp | Skills loader, standalone module (no wiring) | — | done (`915c819`) | 65 tests on Linux; no exec/import paths | T4.2 wiring |
| T5.1 | SwarmblyApp | MCP client core: approved local and remote servers through the broker (no UI) | T1.1 | done (`b7e8748`) | Linux, Python 3.11, mcp 2.3.0: integrated suite 729/729 (non-sandbox); code read: egress on connect and on every remote call, passages guard, env allowlist, manifest-hash suspension | T5.2 UI and chat (D-011) |
| T7.0 | outside repos | Sandbox spike: `wasi-python` 0.1.5 on macOS arm64 (D-005) | D-005 | done | 10/10 checks; [report](spikes/T7.0_wasi-python_macos.md) | — |
| T7.1 | SwarmblyApp | Sandbox runner and worker pool for recipe 5 (D-010) | T1.1, T7.0 | done (`cc23acc`), Linux leg partial | macOS: 26 sandbox tests passed. Linux (cloud, 2 CPUs): escape tests 01–04 and memory cap pass; `test_05` (deadline) fails, cause being checked | Explain test_05 on Linux; Windows disk guard (R-006) |
| T3.1 | SwarmblyApp | Recipe 4: a list on the swarm (WP3) | T2.1 | done (`bd76972`) | Branch 713/713 on Linux; integrated 729/729; code read: preview sends nothing, local never calls the swarm | T3.2 battery |
| T8.1 | umbrella (Core) | Agent runtime package `swarmbly-agent` 0.1.0 (D-007) | — | done (`d274d56` on edge) | 89/89 on Linux; no dependencies, no network or subprocess imports | T8.2 App adapter |

## Phase 2 · Wiring, batteries and remaining packages

| ID | Repo | Goal | Depends on | Status | Verification | Next |
|---|---|---|---|---|---|---|
| T3.2 | umbrella (bench) | Open battery and scorer for recipe 4 (`bench/dev_list`) | T3.1 | running | — | Review |
| T7.2 | SwarmblyApp | Recipe 5 flow: script proposal, approval with a one-time token, run through the broker, answer with script and output, up to two corrected scripts | T7.1 | running | — | Review; then T7.3 |
| T6.1 | SwarmblyApp | Author search core: ORCID, OpenAlex, PubMed through the broker, the exact name approved per run | T1.1 | running | — | T6.2 wiring |
| T2.2 | SwarmblyApp | Embeddings role through `roles.choose`; passages to a third party only with both authorisations | T2.1 | running | — | Review |
| T7.3 | umbrella (bench) | Open battery for recipe 5 with expected results computed beforehand; isolation tests listed in the exit criteria | T7.2 | todo | — | — |
| T8.2 | SwarmblyApp | Agent adapter: the runtime drives MCP tools in a conversation, each call approved by the user (D-011) | T8.1 pushed, T5.1 | todo | — | Needs `swarmbly-agent` reachable as a pinned dependency (edge pushed) |
| T5.2 | SwarmblyApp | MCP settings UI and API routes: add a server, see the exact command, approve tools, suspension notice | T5.1 | todo | — | Serialised with T7.2 (same UI files) |
| T4.2 | SwarmblyApp | Skills in the UI: offer by description, activate, body quoted in the prompt | T4.1 | todo | — | After T5.2 |
| T6.2 | SwarmblyApp | Author search in the UI with the consent box | T6.1 | todo | — | After T4.2 |
| T9.1 | all | Open battery 3.4, injected-instruction test ("a page cannot widen permissions"), CI on Linux and Windows | all | todo | — | — |
| T9.2 | maintainer | New sealed bank (confirms zero unauthorised sends, R-003) | T9.1 | todo | — | Written by the maintainer |
