# Orchestration ledger

Working memory of the development of Swarmbly AI from release 3.4 on: what is being done, what was decided and why, and what comes next. It is kept up to date as work advances and is the reference when work resumes after a pause.

| File | Content |
|---|---|
| [`STATE.md`](STATE.md) | Current objective, repositories and branches, last verified results, blockers, next action |
| [`TASKS.md`](TASKS.md) | Tasks with dependencies, status and how each was verified |
| [`DECISIONS.md`](DECISIONS.md) | Architecture and process decisions, with reasons, alternatives and when to revisit them |
| [`RISKS.md`](RISKS.md) | Open risks and how they are handled |

**How the work is organised.** The maintainer sets the goals and takes the decisions that change the project's aims or architecture. A coordinating agent plans the work, writes the task contracts, reviews every result and integrates only what passes review. A coding agent (DeepSeek Harness) carries out bounded tasks: audits, research, implementation and tests, each on its own branch (`dsh/…`). No result is integrated without an independent check: the diff is read, the tests are run and the claim is compared with the acceptance criteria. Pushes, releases and DOIs are done by the maintainer.

Agent session identifiers are kept only as references; this ledger, the commits and the release notes are the record. Results follow the project's rules: simulated results are not evidence, n = 1 is labelled as such, and the sealed benchmark banks are run once per version and never used for tuning.
