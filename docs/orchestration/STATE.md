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

**Integrated (local, not pushed):** App `main` at `bd76972` (seven commits over `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4); umbrella `edge` with the agent runtime (`d274d56`). Integrated App suite on Linux: 729 passed (non-sandbox tests).

**In progress:** T3.2 (recipe 4 battery), T7.2 (recipe 5 flow), T6.1 (author search core), T2.2 (embeddings role). Decision D-011 taken (approval per tool call).

**Blockers:** none. T8.2 needs `edge` pushed so the App can pin `swarmbly-agent`.

**Next action:** review T3.2, T7.2, T6.1 and T2.2 as they finish; explain `test_05` on Linux; then T5.2, T8.2, T4.2, T6.2 in that order (they share UI files).
