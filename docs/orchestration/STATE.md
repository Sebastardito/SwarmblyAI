# State

**Last updated:** 2026-11-20

**Current objective:** release 3.4, "Tools" ([roadmap](../ROADMAP.md)): one tool broker; MCP client; skills (`SKILL.md`, instructions only); author search with consent; recipe 5, data with code, in a sandbox. Carried over from 3.3: the Anthropic provider and an embeddings role, recipe 4 (a list on the swarm), the agent runtime in SwarmblyCore.

**Repositories**

| Repository | Local folder | Branch | Head at start of 3.4 |
|---|---|---|---|
| SwarmblyAI (umbrella) | `Swarmbly-AI_Clean` | `edge` (main = release) | `eb2e3a9` |
| SwarmblyApp | `SwarmblyApp` | `main` | `890254f` |
| SwarmblyLCE | `LCE` | `main` | `5eaf859` |

Last releases: Swarmbly AI 3.3.0 (10.5281/zenodo.24330451), SwarmblyApp 0.6.0 (10.5281/zenodo.24330450), SwarmblyLCE 0.2.1 (10.5281/zenodo.24330449). Prepared for publication: 3.4.0 on `release-3.4.0` (umbrella `1bd17d3`, App 0.7.0 `a1f0508`, swarmbly-agent 0.1.0), DOI pending.

**Open from 3.3:** zero unauthorised sends to be confirmed on a new sealed bank; the receipt test with people (postponed).

**Integrated:** App `main` at `890254f` (from `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing, MCP settings, skills in the app, injected-instruction suites, agent adapter, author search in the chat, spreadsheets in recipe 5, CI with extras, sandbox CI on three systems, the test seam and its Python 3.12 fix, private glossary entries); App suite 970 passed with 2 known env-only P2P family failures. Umbrella `edge` at `eb2e3a9`; release branch `release-3.4.0` at `1bd17d3`.

**In progress:** T9.18 in review: release 3.4 prepared as local commits on `release-0.7.0` (App) and `release-3.4.0` (umbrella); the maintainer reviews and publishes.

**Blockers:** none for the release. Exit criteria 1 (zero unauthorised sends) and 3 (exact result ≥ 90 %) are not met on the sealed banks and are reported as such (D-014); T9.7 stays open until a new sealed bank.

**Next action:** maintainer reviews both release branches, pushes in order, tags `v0.7.0` (App) and `v3.4.0` (umbrella), publishes and sends the DOIs; then T9.2, a new sealed bank, measures the fixes.
