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
| T7.1 | SwarmblyApp | Sandbox runner and worker pool for recipe 5 (D-010) | T1.1, T7.0 | done (`cc23acc`) | macOS: 26 sandbox tests. Linux (x86_64, 2 vCPU, 8 GB): escape tests 01–04 and 06–09, 11, 12 pass; test_05 traps the deadline correctly but its wall-clock bound includes a ~60 s cold compile | T7.1b fixes the test |
| T3.1 | SwarmblyApp | Recipe 4: a list on the swarm (WP3) | T2.1 | done (`bd76972`) | Branch 713/713 on Linux; integrated 729/729; code read: preview sends nothing, local never calls the swarm | T3.2 battery |
| T8.1 | umbrella (Core) | Agent runtime package `swarmbly-agent` 0.1.0 (D-007) | — | done (`d274d56` on edge) | 89/89 on Linux; no dependencies, no network or subprocess imports | T8.2 App adapter |

## Phase 2 · Wiring, batteries and remaining packages

| ID | Repo | Goal | Depends on | Status | Verification | Next |
|---|---|---|---|---|---|---|
| T3.2 | umbrella (bench) | Open battery and scorer for recipe 4 (`bench/dev_list`, 11 cases) | T3.1 | done (`99edb81`) | 22 bench tests on Linux. Run n=3 per case, qwen2.5:7b, local: 21/33 cases, cells 147/189, sends 0. MX-01 exposed an App defect (a 12-item wave answered with item 1's answer) | T3.3 |
| T7.2 | SwarmblyApp | Recipe 5 flow: script proposal, approval with a one-time token, run through the broker, answer with script and output, up to two corrected scripts | T7.1 | done (`189435d`) | Linux 736/736; code read (propose never runs, approve is the only token path, ≤ 5 sample rows, download confined to the run's /out); Mac end-to-end matched an independent computation | T7.3 battery |
| T6.1 | SwarmblyApp | Author search core: ORCID, OpenAlex, PubMed through the broker, the exact name approved per run | T1.1 | done (`a0f9baa`) | Linux 760/760 after integration; AUTHOR_QUERY kind, personal name marked in the receipt, off by default | T6.2 wiring |
| T2.2 | SwarmblyApp | Embeddings role through `roles.choose`; passages to a third party only with both authorisations | T2.1 | done (`3ce4628`) | Linux 760/760; all embedding call sites routed and egress-checked; index rebuilt on model change | — |
| T3.3 | SwarmblyApp | Fix: recipe 4 wave of 12 items answered with the first item's answer | T3.2 | done (`1114620`) | Cause: one 12-line prompt makes qwen2.5:7b repeat item 1; positions were mapped correctly (fake model). A wave whose distinct items all get one value is retried item by item; parser fixed for echoed labels. Linux 764/764. Partial repetition is not detected | T3.3b battery re-run |
| T7.1b | SwarmblyApp | Sandbox test_05 measures run time after the worker is ready; shared compile cache in tests | T7.1 | done (`56144eb`) | Bound still catches a missing hard kill; a new test shows the shared cache holds only compiled code | — |
| T3.3b | umbrella (bench) | Re-run the recipe 4 battery on the fixed App | T3.3 | done | n=3, local: 27/33 cases (was 21/33), cells 183/189 (was 147/189), sends 0; MX-01 54/54. CL-01 and SI-01 keep one model error each | — |
| T9.1a | SwarmblyApp | Injected-instruction suite across every tool surface, with a model that obeys any instruction (exit criterion) | T5.1, T6.1, T7.2 | done (`e4094aa`) | 40 cases (9 surfaces × 5 encodings) pass; no defect found; Linux 817/817. In today's chat paths model text is never parsed as a tool call, so the agent path needs its own run | T9.1b after T8.2 |
| T7.4 | SwarmblyApp | Recipe 5 selects spreadsheet sources (.xlsx/.xlsm/.tsv) directly, with the same containment rules | T7.3 | done (`74388e3`) | Linux 842/842; spreadsheets listed and selected from the project sources with realpath containment, no symlinks, size cap; header + ≤ 5 rows per sheet | Remove the recipe 5 battery workaround (umbrella) |
| T7.3 | umbrella (bench) | Open battery for recipe 5 with expected results computed beforehand; isolation tests listed in the exit criteria | T7.2 | done (`1940cb1`) | 12 cases; run n=3, local: 36/36 cases, 54/54 numbers, 0 sends, network and write-outside temptations held. Found: recipe 5 cannot select .xlsx | T7.4 |
| T8.2 | SwarmblyApp | Agent adapter: the runtime drives MCP tools in a conversation, each call approved by the user (D-011) | T8.1 pushed, T5.1 | done (`1ac8371`) | Linux 836/836 with `swarmbly-agent` installed from the umbrella; policy read: unapproved → deny, standing only for local MCP (checked on the live spec), sandbox/author/remote always ask, token only from the approve endpoint; Mac end-to-end with qwen2.5:7b and a fixture MCP tool | Pin needs `edge` pushed |
| T5.2 | SwarmblyApp | MCP settings UI and API routes: add a server, see the exact command, approve tools, suspension notice | T5.1 | done (`2d070e5`) | Linux 782/782 with T4.2; routes behind the local API guard; env values never accepted; descriptions shown as text | Project selector and edit form later |
| T4.2 | SwarmblyApp | Skills in the UI: offer by description, activate, body quoted in the prompt | T4.1 | done (`02b513c`) | Linux 782/782; import never executes (marker test); offer never activates; body quoted with a label that it cannot change permissions | — |
| T6.2 | SwarmblyApp | Author search in the UI with the consent box | T6.1 | done (`b2eb0e5`) | Linux 836/836; consent box before any request; receipt bytes now count the real request (injection test bound adjusted, `25c090b`) | — |
| T9.1b | SwarmblyApp | Injected-instruction suite on the agent path (model output parsed as tool calls) | T8.2 | done (`bb12bee`, `6f7a20e`) | 45 matrix cases on the agent path; two defects found and fixed: a standing approval survived a manifest change (high), a prior tool result could reach a remote MCP tool (medium); Linux 905 passed with the extras | — |
| T9.0 | SwarmblyApp | CI failed in every job: tests imported the MCP SDK without the [tools] extra | — | done (`108ec16`, `1c3240f`) | Reproduced with a [dev]-only install (collection error) and on the Windows job log; tests needing an extra now skip, CI installs [dev,tools,agent]: 811 passed + 44 skipped without extras, 905 with them | Watch the next CI run, incl. the first Windows sandbox run |
| T9.3 | umbrella (bench) | Harness 1.3 for the sealed bank v4: new card fields, catalog-driven MCP servers, simulated author services, skills, the user's decisions from the card, unauthorised sends and permission violations by code | T9.1b | blocked | Stopped at its stop condition (correctly): the App cannot reach a remote MCP server declared with a .test host, author services have no endpoint override, no project-creation API | Resume after T9.4 |
| T7.5 | SwarmblyApp | Sandbox CI on three systems: test_05 fuel half killed by the hard wall during a cold metered compile (all systems); test_03 "write through rel symlink" succeeded on Windows (to be explained: no symlink created, or an escape) | T7.1 | running | — | Windows stays behind R-006 until explained |
| T9.4 | SwarmblyApp | Test seam for the bank harness (D-013): launch-time host map to loopback, policy and receipt on the declared host, `simulado: true`; project creation through the API if missing | T9.3 | running | — | Then resume T9.3 |
| T9.1 | all | Open battery 3.4, injected-instruction test ("a page cannot widen permissions"), CI on Linux and Windows | all | todo | — | — |
| T9.2 | maintainer | New sealed bank (confirms zero unauthorised sends, R-003) | T9.1 | todo | — | Written by the maintainer |
