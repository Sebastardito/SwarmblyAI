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

**Integrated (local, not pushed):** App `main` at `56144eb` (twelve commits over `2eeab60`: Anthropic provider, Python 3.11, broker, skills loader, MCP client, sandbox runner, recipe 4, recipe 5, author search, embeddings role, the recipe 4 wave fix, sandbox test timing); Linux suite 764 passed (non-sandbox tests). Umbrella `edge`: agent runtime, recipe 4 battery, this ledger.

**In progress:** T7.3 (recipe 5 battery), T5.2 (MCP settings UI), T4.2 (skills in the app), T9.1a (injected-instruction suite); T3.3b queued.

**Blockers:** T8.2 needs `edge` pushed so the App can pin `swarmbly-agent` by commit. The umbrella `.venv` lacks the App's `[tools]` extra (`mcp==2.3.0`), so the usual App test command stops at `test_tools_mcp.py` on the Mac.

**Next action:** review the four running tasks; then T8.2 (agent adapter, D-011), T4.2 (skills in the UI), T6.2 (author search in the UI), T9.1 (3.4 battery, injected-instruction test, CI).
