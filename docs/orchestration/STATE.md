# State

**Last updated:** 2026-11-18

**Current objective:** release 3.4, "Tools" ([roadmap](../ROADMAP.md)): one tool broker; MCP client; skills (`SKILL.md`, instructions only); author search with consent; recipe 5, data with code, in a sandbox. Carried over from 3.3: the Anthropic provider and an embeddings role, recipe 4 (a list on the swarm), the agent runtime in SwarmblyCore.

**Repositories**

| Repository | Local folder | Branch | Head at start of 3.4 |
|---|---|---|---|
| SwarmblyAI (umbrella) | `Swarmbly-AI_Clean` | `edge` (main = release) | `5897250` |
| SwarmblyApp | `SwarmblyApp` | `main` | `2eeab60` |
| SwarmblyLCE | `LCE` | `main` | `5eaf859` |

Last releases: Swarmbly AI 3.3.0 (10.5281/zenodo.24330451), SwarmblyApp 0.6.0 (10.5281/zenodo.24330450), SwarmblyLCE 0.2.1 (10.5281/zenodo.24330449).

**Open from 3.3:** zero unauthorised sends to be confirmed on a new sealed bank; the receipt test with people (postponed).

**Integrated:** App `main` at `ec3d206` (from `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing, MCP settings, skills in the app, injected-instruction suites, agent adapter, author search in the chat, spreadsheets in recipe 5, CI with extras, sandbox CI on three systems, the test seam and its Python 3.12 fix); Linux suite 916 passed with the extras. Umbrella `edge`: agent runtime, recipe 4 and recipe 5 batteries, bank harness 1.3 with the v4 self-test bank, this ledger.

**In progress:** none. Harness 1.3 is done; banks v4.1 and v4.2 (sealed, 38 and 31 files) wait for the maintainer's run.

**Blockers:** none.

**Next action:** the maintainer runs `--check` and then ×3 on banks v4.1 and v4.2 with harness 1.3; an isolated judge scores the S2/S3 rubric; then the 3.4 release (versions and timing with the maintainer).
