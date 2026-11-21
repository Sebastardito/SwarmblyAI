# State

**Last updated:** 2026-11-21

**Current objective:** publish 3.5.0 and start the private beta ([roadmap](../ROADMAP.md), [architecture](ARCH_3.5.md)). Released: Swarmbly AI 3.4.0 (10.5281/zenodo.24412216), SwarmblyApp 0.7.0 (10.5281/zenodo.24412215).

**Repositories**

| Repository | Local folder | Branch | Head at start of 3.4 |
|---|---|---|---|
| SwarmblyAI (umbrella) | `Swarmbly-AI_Clean` | `edge` (main = release) | `eb2e3a9` |
| SwarmblyApp | `SwarmblyApp` | `main` | `890254f` |
| SwarmblyLCE | `LCE` | `main` | `5eaf859` |

Last releases: Swarmbly AI 3.4.0 (10.5281/zenodo.24412216), SwarmblyApp 0.7.0 (10.5281/zenodo.24412215), SwarmblyLCE 0.2.1 (10.5281/zenodo.24330449). Prepared for publication: 3.5.0 on `release-3.5.0` (umbrella `63dd0b6`, App 0.8.0 `cd219d0` tagged `v0.8.0` on `main`), DOIs pending.

**Open from 3.3:** zero unauthorised sends to be confirmed on a new sealed bank; the receipt test with people (postponed).

**Integrated:** App `main` at `890254f` (from `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing, MCP settings, skills in the app, injected-instruction suites, agent adapter, author search in the chat, spreadsheets in recipe 5, CI with extras, sandbox CI on three systems, the test seam and its Python 3.12 fix, private glossary entries); App suite 970 passed with 2 known env-only P2P family failures. Umbrella `edge` at `eb2e3a9`; release branch `release-3.4.0` at `1bd17d3`.

**In progress:** nothing running. WP0–WP9 done, CI green on all platforms (App `b26a826`), release 3.5.0 prepared (T10.20, D-024).

**Blockers:** none for the release. Open for the beta (D-024): sealed bank v5, the team-versus-local and node-loss batteries with real models, a circle between real machines on different networks, where the relay runs, the Apple and Windows signing accounts, the review of the beta kit drafts. From 3.4: zero unauthorised sends and the exact-result target stay unconfirmed until bank v5 (T9.7).

**Next action:** the maintainer pushes and publishes 3.5.0 (`_sync/releases_3.5/publicar_releases.sh`), then sends the DOIs for the DOI commit; the beta preparation follows.
