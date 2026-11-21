# State

**Last updated:** 2026-11-20

**Current objective:** release 3.5, "Teams and trusted circles · private beta" ([roadmap](../ROADMAP.md), [architecture proposal](ARCH_3.5.md)). Released: Swarmbly AI 3.4.0 (10.5281/zenodo.24412216), SwarmblyApp 0.7.0 (10.5281/zenodo.24412215).

**Repositories**

| Repository | Local folder | Branch | Head at start of 3.4 |
|---|---|---|---|
| SwarmblyAI (umbrella) | `Swarmbly-AI_Clean` | `edge` (main = release) | `eb2e3a9` |
| SwarmblyApp | `SwarmblyApp` | `main` | `890254f` |
| SwarmblyLCE | `LCE` | `main` | `5eaf859` |

Last releases: Swarmbly AI 3.3.0 (10.5281/zenodo.24330451), SwarmblyApp 0.6.0 (10.5281/zenodo.24330450), SwarmblyLCE 0.2.1 (10.5281/zenodo.24330449). Prepared for publication: 3.4.0 on `release-3.4.0` (umbrella `1bd17d3`, App 0.7.0 `a1f0508`, swarmbly-agent 0.1.0), DOI pending.

**Open from 3.3:** zero unauthorised sends to be confirmed on a new sealed bank; the receipt test with people (postponed).

**Integrated:** App `main` at `890254f` (from `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing, MCP settings, skills in the app, injected-instruction suites, agent adapter, author search in the chat, spreadsheets in recipe 5, CI with extras, sandbox CI on three systems, the test seam and its Python 3.12 fix, private glossary entries); App suite 970 passed with 2 known env-only P2P family failures. Umbrella `edge` at `eb2e3a9`; release branch `release-3.4.0` at `1bd17d3`.

**In progress:** T10.7 (relay in the App). WP2, WP4, WP5 and WP6 done.

**Blockers:** none for the release. Exit criteria 1 (zero unauthorised sends) and 3 (exact result ≥ 90 %) are not met on the sealed banks and are reported as such (D-014); T9.7 stays open until a new sealed bank.

**Next action:** review WP2; then WP3 integration of the relay in the App (needs where the relay runs); the maintainer opens the signing accounts.
