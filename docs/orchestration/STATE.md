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

**Integrated:** App `main` at `1c3240f` (pushed up to `74388e3`; since then the CI fix and the agent-path injection suite over `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing, MCP settings, skills in the app, injected-instruction suite, agent adapter, author search in the chat, spreadsheets in recipe 5); Linux suite 842 passed (non-sandbox tests). Umbrella `edge`: agent runtime, recipe 4 and recipe 5 batteries, this ledger.

**In progress:** T9.3 (bank harness 1.3). Banks v4.1 and v4.2 are sealed (38 and 31 files) and wait for the harness.

**Blockers:** none.

**Next action:** review T7.5 and T9.4; resume T9.3; run the sealed banks v4.1 and v4.2 once (×3) with the harness 1.3; then the 3.4 release.
