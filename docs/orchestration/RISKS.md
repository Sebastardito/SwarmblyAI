# Risks

| ID | Risk | Impact | Handling | Status |
|---|---|---|---|---|
| R-001 | Recipe 5 runs code written by a model on the user's computer | Data loss, exfiltration | Sandbox with no network, limits on time, memory and files, data read-only; nothing runs without the user's yes; isolation tested in CI. Design pending (T0.2) | open |
| R-002 | Tool descriptions and results (MCP, web pages, skills) carry instructions that widen permissions ("tool poisoning") | Unauthorised sends, actions | One broker applies the destinations policy to every tool call; tool output is data, never instructions; test with injected instructions | open |
| R-003 | Zero unauthorised sends is not yet confirmed on a new sealed bank (open since 3.3) | Privacy claim unproven | A new sealed bank before the 3.4 release | open |
| R-004 | Work by the coding agent passes its own tests but not the acceptance criteria | Regressions, false claims | Independent review of every result; the open batteries run before integration | open |
