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
| R-008 | A peer outside any circle receives tasks (admission is open today) | Private data or work reaches a stranger | Circle-only admission by default (WP1), tested with a non-member | open |
| R-009 | Off-LAN peers are labelled own network and peer sends bypass the egress gate | Misleading receipts, unchecked sends | CIRCLE class and the gate (WP2) before any off-LAN work | open |
| R-010 | Membership without mutual TLS: a stolen node key impersonates a member | A stranger joins a circle | Manifest versions and revocation; key at rest is unencrypted today; mTLS or a per-circle key in 3.6 | open |
| R-011 | Self-declared roles mislead placement | Worse answers, wasted work | Per-role success tracking; roles never widen permissions | open |
| R-012 | Credit receipts gamed or double-spent | Unfair reciprocity | Requester-signed receipts, issuer logs, expiry, circle scope | open |
| R-013 | Signing depends on paid accounts and CI secrets | Unsigned installers, fewer successful installs | Accounts opened by the maintainer; Sigstore/minisign fallback | open |
| R-014 | The beta collects personal data by accident | Privacy harm to volunteers | No telemetry; doctor export reviewed; consent form | open |
| R-015 | The relay is a new public service: abuse, denial of service, metadata exposure, a bug that lets a non-member pair | Exposure of members, outage | Members only, limits per member, no payload storage, end-to-end TLS through the splice, its own test suite, external port scan before the beta | open |
