# State

**Last updated:** 2026-11-27

**Current objective:** the private beta of 3.5 and the design of 3.6 ([roadmap](../ROADMAP.md)). Released: Swarmbly AI 3.5.0 (10.5281/zenodo.24431442), SwarmblyApp 0.8.0 (10.5281/zenodo.24431441).

**Repositories**

| Repository | Local folder | Branch | Head at start of 3.4 |
|---|---|---|---|
| SwarmblyAI (umbrella) | `Swarmbly-AI_Clean` | `edge` (main = release) | `eb2e3a9` |
| SwarmblyApp | `SwarmblyApp` | `main` | `890254f` |
| SwarmblyLCE | `LCE` | `main` | `5eaf859` |

Last releases: Swarmbly AI 3.5.0 (10.5281/zenodo.24431442), SwarmblyApp 0.8.0 (10.5281/zenodo.24431441), SwarmblyLCE 0.2.1 (10.5281/zenodo.24330449). Signed artifacts of 3.5.0: release workflow fixed (T10.21), re-run pending.

**Open from 3.3:** zero unauthorised sends to be confirmed on a new sealed bank; the receipt test with people (postponed).

**Integrated:** App `main` at `890254f` (from `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing, MCP settings, skills in the app, injected-instruction suites, agent adapter, author search in the chat, spreadsheets in recipe 5, CI with extras, sandbox CI on three systems, the test seam and its Python 3.12 fix, private glossary entries); App suite 970 passed with 2 known env-only P2P family failures. Umbrella `edge` at `eb2e3a9`; release branch `release-3.4.0` at `1bd17d3`.

**In progress:** release 3.5.1 prepared (T11.7): App `release-0.8.1` and tag `v0.8.1` at `d703022`; umbrella `release-3.5.1` and tag `v3.5.1` at `abbec0e`, plus this ledger. The maintainer pushes and publishes. T11.5 open batteries done (0 private terms sent; code 31/39 against 25/39 on 0.8.0).

**Blockers:** none for the release. Open for the beta (D-024): sealed bank v5, the team-versus-local and node-loss batteries with real models, a circle between real machines on different networks, where the relay runs, the Apple and Windows signing accounts, the review of the beta kit drafts. From 3.4: zero unauthorised sends and the exact-result target stay unconfirmed until bank v5 (T9.7).

**Next action:** the maintainer publishes 3.5.1 and prepares sealed banks v6.1 and v6.2 (guide `ejemplobancov6.md`); bank v6 runs once on the published 3.5.1 with harness 1.4.5. Then the medium defects (3.5.2) and the 3.6 design.
