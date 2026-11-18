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
| T2.1 | SwarmblyApp | Test command for worktrees (WP0); native Anthropic provider, always a third party; unknown backend kinds raise | — | running | — | Review |
| T2.2 | SwarmblyApp | Embeddings role through `roles.choose` | T2.1 | todo | — | — |
| T1.1 | SwarmblyApp | Broker, tool kinds in egress, approvals, receipt (WP1) | T2.1 merged | todo | — | Contract after T2.1 |
| T3.1 | SwarmblyApp, umbrella | Recipe 4 and its open fixture (WP3) | T2.1 merged | todo | — | — |
| T7.0 | outside repos | Sandbox spike: `wasi-python` 0.1.5 on macOS arm64, ten escape and function checks, latency (D-005) | D-005 | running | — | Linux and Windows legs in CI |
