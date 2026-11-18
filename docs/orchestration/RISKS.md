# Risks

| ID | Risk | Impact | Handling | Status |
|---|---|---|---|---|
| R-001 | Recipe 5 runs code written by a model on the user's computer | Data loss, exfiltration | Sandbox with no network, limits on time, memory and files, data read-only; nothing runs without the user's yes; isolation tested in CI. Spike passed on macOS (D-010); Linux and Windows pending in CI | open |
| R-002 | Tool descriptions and results (MCP, web pages, skills) carry instructions that widen permissions ("tool poisoning") | Unauthorised sends, actions | One broker applies the destinations policy to every tool call; tool output is data, never instructions; test with injected instructions | open |
| R-003 | Zero unauthorised sends is not yet confirmed on a new sealed bank (open since 3.3) | Privacy claim unproven | A new sealed bank before the 3.4 release | open |
| R-004 | Work by the coding agent passes its own tests but not the acceptance criteria | Regressions, false claims | Independent review of every result; the open batteries run before integration | open |
| R-005 | The first run of the sandbox compiles the WebAssembly module: about 5 s and 3.3 GB of memory on an M-series Mac, about 60 s on a 2-vCPU Linux machine with 8 GB, once, then cached | A computer with 8 GB may stall on first use | Compile at install time or on first launch with a notice; measure on an 8 GB machine | open |
| R-006 | On Windows there is no kernel file-size limit like `RLIMIT_FSIZE` | A script could fill the disk before the watchdog stops it | Job object limits plus a watchdog and a small scratch quota; tested in CI before recipe 5 is enabled on Windows | open |
| R-007 | `wasi-python` is young (one maintainer, first release October 2026) | Abandonment or a security bug without a fix | Pinned and hashed; upgrades treated as a new spike; Docker fallback kept in the design | open |
