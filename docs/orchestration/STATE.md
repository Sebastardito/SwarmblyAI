# State

**Last updated:** 2026-11-25

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

**In progress:** T11.3 (App 0.8.1 follow-ups) and T11.4 (harness 1.4.5), delegated to DSH. The v5.2 repeat measured the 0.8.1 candidate by mistake (App imported from the standalone repo) and is reported as a non-blind confirmation run.

**Blockers:** none for the release. Open for the beta (D-024): sealed bank v5, the team-versus-local and node-loss batteries with real models, a circle between real machines on different networks, where the relay runs, the Apple and Windows signing accounts, the review of the beta kit drafts. From 3.4: zero unauthorised sends and the exact-result target stay unconfirmed until bank v5 (T9.7).

**Next action:** review T11.3/T11.4; open batteries on 0.8.1; release 3.5.1 stating the bank results of 0.8.0 (criteria 1 and 5 not met) and the confirmation run apart.
