# Changelog

## 0.8.0 — Teams and trusted circles (2026-11-21)

Swarmbly AI 3.5. Teams and trusted circles. Trusted circles with signed
membership manifests and invitations by code or QR, checked at the handshake
and at the worker gate (new installs are circle-only); a `CIRCLE` destination
class, with every peer send through the egress gate and receipts that name it;
off-LAN work through the circle's own relay (pinned TLS, end-to-end TLS through
the splice, the owner pushing each manifest version over the network); node
roles (large model, reasoner, and opt-in search and corpus executors); teams as
stored plan templates with honest partial results (complete, partial or
failed; dependent steps blocked, never guessed); reciprocity credits as signed,
non-transferable receipts, offered only to a busy worker, with double spends
detected at the issuer; first-launch sandbox preparation with a 4 GiB floor and
an explicit override (`--prepare-sandbox --force`, `{"force": true}`); a doctor
export built from an allow-list; and the leftovers of the 3.4 evaluation (MCP
suspensions shown to the user, no raw tool block, the conversation language in
every recipe, recipe 5 on the writer role with the model actually used
recorded). The P2P tests now also run on Windows. No sealed bank was run for
this version: bank v5 is prepared and runs once, by the author, before the
beta. Off-LAN runs between real machines and signed installers (Apple and
Windows accounts) are still pending.

**App leftovers from the 3.4 evaluation, WP9 (T10.17).**

- **MCP suspensions reach the user.** A tool waiting for approval, refused by
  policy, stopped by the loop guard or no longer answering now adds a plain
  note to the answer and a `TOOL` stage with the tool, the reason and what was
  done instead; `meta.suspensions` and the receipt's agent summary repeat it.
- **The loop guard never returns a raw tool block.** The App strips fenced or
  bare protocol JSON, tool tags and protocol markers from the final text; when
  no prose remains it says the tool loop was stopped instead of showing the
  model's tool call.
- **A skill no longer displaces the document passages.** Both reach the model;
  the passages come first and keep their room, and the skill body is shortened
  (with a visible marker) when the material budget is short.
- **Retrieval widens the App-side query.** Glossary equivalents and regular
  accent/inflection variants are added to the terms handed to LCE (which is
  unchanged), with an open neutral test set under `tests/fixtures/retrieval/`.
- **The conversation language reaches every recipe.** List, code and compose
  prompts take the conversation's language; a clearly English answer to a
  Spanish question is regenerated once with the language rule, and list status
  cells are localised.
- **Cancel keeps a message.** A stopped request shows the text already
  streamed plus a note that the answer was stopped, never an empty message.
- **A table header is not a list answer.** Header and separator rows are
  rejected as missing by the list parser, so a model that only echoes its
  table header gets the item marked like any other empty answer.
- **Recipe 5 records the model that wrote the script.** The script is still
  written by the `writer` model role (the conversation's model when no writer
  is configured), as designed in 3.4; the proposal, `meta.code` and the
  receipt now state the actual model and backend.

**First-launch sandbox preparation and doctor export, WP7 App part
(R-005/R-014).**

- **The sandbox cache is a first-launch step** (`sandbox/cache.py`,
  `sandbox/prepare.py`, `state.py`). After start-up, when the optional
  `[sandbox]` extra is installed and the compiled cache is missing or stale,
  the App shows a notice with the expected time and memory (about 5 s / 3.3 GB
  on Apple Silicon, about 60 s on a 2-vCPU machine) and offers **Prepare now**
  / **Later**, in the web UI and in the first-run assistant. The compile runs
  in one daemon thread (`preparing` → `ready`, or `failed` with the reason) and
  publishes `sandbox.prepare` events, so chat is never blocked. A machine with
  fewer than **4 GiB free** is refused from the automatic start and a plain
  **Prepare now**; the explicit override is the next bullet. `Later` hides the
  notice for a week. The measured wall time and peak RSS are stored next to the
  cache and never leave the computer.
- **Explicit low-memory override.** Below the 4 GiB floor the automatic start
  and a plain **Prepare now** still refuse. An explicit **Prepare anyway**
  (API `{"force": true}`, CLI `--force`) starts the compile after a one-line
  warning; the state records `forced: true` and the free memory at start, the
  `sandbox.prepare` event is marked forced, and the doctor export carries the
  boolean. The umbrella installer never passes `--force` by itself.
- **Recipe 5 never compiles inside a request.** An unprepared, stale,
  preparing, failed or memory-refused cache reports unavailable with the
  reason and the request continues without the code recipe. The one-time
  compile happens only from the notice/Settings or from the installer flag.
- **API and CLI.** `GET /api/sandbox`, `POST /api/sandbox/prepare`,
  `POST /api/sandbox/defer`; `swarmbly-app --prepare-sandbox` compiles and
  exits with stable codes (0 ready, 1 failed, 2 extra missing, 3 not enough
  free memory, 4 bad data directory) so the umbrella installer can run it at
  install time. `docs/INSTALL.md` documents the call.
- **Doctor export** (`doctor_export.py`, `recent_errors.py`, `db.recent_failures`).
  `GET /api/doctor/export/preview` returns the exact JSON and text strings;
  `POST /api/doctor/export` writes that same snapshot, and the UI shows both
  files before saving. The export contains only App/LCE/Core versions,
  OS/architecture, Python, CPU/RAM/GPU class, installed extras, Ollama
  reachability and model tags, the sandbox state and compile measurements, P2P
  counts (listening, peers, circles, relay configured, relay/push codes) and
  the last error codes with timestamps. It never carries node ids or keys,
  names, circle names or ids, member names, IPs or host names, paths under the
  user's home, project names, document titles, prompts, answers, glossary,
  memory, API keys or the relay host. A schema validator ships with the module
  and the tests. `swarmbly-app doctor-export` writes both files.
- **Docs and tests.** User guide EN/ES (first launch, doctor export),
  INSTALL (installer flag and exit codes), LIMITATIONS (what the export
  contains and never contains) and this entry. `tests/test_first_launch.py`
  covers the notice conditions, the 4 GiB refusal, background transitions, a
  request during preparation and the CLI exit codes;
  `tests/test_doctor_export.py` builds an export from a fixture full of
  private canaries, validates the schema and asserts that the preview and the
  saved files are byte-for-byte equal.

**Off-LAN through the circle relay, WP3 (D-016/D-023).**

- **Relay in the circle.** The owner sets `relay: {host, port,
  tls_cert_sha256}` in the circle card, API `POST /api/circles/{id}/relay`.
  The pin is mandatory with an address; a relay without a valid SHA-256 pin is
  refused (`E_CIRCLE_RELAY_PIN`). The optional field is signed inside the
  manifest and inside new invitations, so older nodes ignore it and a
  tampered endpoint fails the signature.
- **Owner pushes each version over the network.** The App now sends the relay's
  `manifest_update` frame (`relay_client.py`, copied from the umbrella
  protocol) on a registered connection for every new owner-signed version:
  approval, revocation, relay change, dissolve and renewal. Only the newest
  unacknowledged version is queued per target, with backoff while the relay is
  unreachable. A relay change pushes the same version to the relay named in
  the **previous** manifest too, then to the new one. The circle card shows
  the acknowledged version, pending version and refusal code with hints for
  `unknown_circle` (operator must install the first manifest),
  `rate_limited` (30 pushes per hour) and `stale_version`. The owner can sign
  a fresh version with the same members and relay via
  `POST /api/circles/{id}/renew` (or the circle card's **Renew manifest**);
  it is pushed like every other version. The existing signed file in
  `circle.relay_publish_dir` remains the operator's bootstrap copy and
  fallback; it is no longer the only update path.
- **App-side client** (`swarmbly_app/p2p/relay_client.py`, AGPL header). A
  deliberate copy of the prototype's protocol client and `MemoryBIO` inner
  TLS adapter: pinned outer TLS 1.3, signed single-use challenge, `pair` /
  `pair_incoming` / `pair_accept`, then raw splice. It also exposes the
  atomic manifest publisher.
- **Registration and pairing** (`p2p/node.py`, `p2p/transport.py`). One idle
  registered acceptor per (circle, relay) with exponential backoff, off when
  the manifest has no relay and bounded by `circle.relay_max_connections`.
  A pin mismatch stops that relay with a security warning; a refusal
  (`not_a_member`, `limit_splices`, `peer_not_connected`, …) is shown. An
  outbound pair opens a short separate connection because the prototype
  accepts one splice per connection. Direct addresses are tried first; only
  then the relay. The inner TLS 1.3 + channel-bound handshake, admission, the
  worker gate and the egress gate are unchanged for relayed peers.
  `ensure_circle_peers` makes relay-reachable members visible to placement
  before planning; a relay that is down does not stop direct peers.
- **Honest transport hop** (`engine/scheduler.py`, `egress.py`, `chat.py`,
  `web/js/monitor.js`). `Attempt`/`Peer` carry `transport` (`direct` or
  `relayed`) and the relay host; the receipt lists `saltos_relay` and marks the
  hop as metadata only (who, when, bytes; never content). The Swarm peers table
  gains a **Link** column (direct / relayed) and the circle card shows the
  relay state and pin.
- **Docs and tests.** Architecture, P2P testing guide (two machines on
  different networks), user guide EN/ES, limitations and this entry.
  `tests/test_relay.py` covers manifest/invitation fields and pins, refusal of
  an unpinned relay, owner publish on approval/revocation, wrong pin before
  any frame, a real umbrella relay end to end (no direct path, task done,
  ciphertext only), direct-first, revocation, non-members, pin-mismatch
  warning and relay-down with working LAN peers. `tests/test_relay_push.py`
  covers the network push with the real umbrella relay: approval acknowledged,
  revocation cutting an open session and blocking re-entry, `unknown_circle`
  before bootstrap, relay down/up delivering only the newest version, a relay
  change reaching old and new relays, and a non-owner never pushing.

**Reciprocity credits, WP6 (D-020/D-021).**

- **Signed, non-transferable receipts** (`swarmbly_app/p2p/credits.py`,
  `engine/scheduler.py`). When the requester accepts a verified result from a
  worker that is a member of a shared, valid circle, it signs an Ed25519
  receipt over canonical JSON: random `receipt_id`, circle, issuer, worker, a
  BLAKE2b hash of the attempt id (never task content), `tokens_out`,
  `generation_ms`, model, `issued_at` and `expires_at` (90 days by default,
  `credits.receipt_ttl_days`). Nothing is issued for the local pool, *my own
  devices*, rejected or degraded replicas, or an executor that returned
  nothing; the scheduler calls the service only after verification and the
  quality check accepted the replica.
- **Control plane** (`p2p/circles.py`, `p2p/node.py`). Three new MINOR-safe
  types on the same TLS session: `credit_receipt` (issuer → worker),
  `credit_spend` (worker → member, just before a task to a member already seen
  busy, so a receipt is never spent on an idle worker) and `credit_spent`
  (accepting worker → issuer, receipt id and spender only). An older node
  ignores them. Delivery checks signature, manifest membership of issuer and
  worker, addressee, expiry and duplicate id; spend checks the same plus
  `worker == sender` and replay. Messages and receipts are size-bounded.
- **Local wallet and spending** (`p2p/credits.py`, `p2p/worker.py`). The
  wallet is per circle under `<data>/credits/wallet.json` (0600, atomic,
  bounded to 256 receipts); only the named worker can spend, only in the same
  circle, and the spender marks the receipt spent. The spend is offered inside
  `NodeManager.dispatch_async` **after** admission and `egress.check_call`, so
  it never bypasses a gate. The worker waits for a slot only while busy and
  only for the exact attempt a valid `credit_spend` named; an uncredited
  requester is still served when a slot is free, and a large receipt buys one
  priority, not many.
- **Double-spend detection** (`p2p/credits.py`). The issuer keeps a bounded
  log under `<data>/credits/issued.json` (0600). A receipt reported spent
  twice (same or different workers) or spent by a node that is not the named
  worker is flagged in `GET /api/credits`, in the event bus
  (`credit.double_spend`) and in Swarm. It is detection, not prevention, and
  nothing is broadcast beyond the circle.
- **UI and API** (`api/__init__.py`, `web/js/monitor.js`,
  `web/i18n/*.json`). The Swarm panel gets a Reciprocity credits section: per
  circle balance/earned/spent/expiring, the issuer's flagged double spends,
  and a one-paragraph explanation in English and Spanish that credits are a
  courtesy inside a circle, not money. Daily counters are unchanged.
- **Protocol appendix and docs** (`docs/LIMITATIONS.md` item 16 and the new
  appendix there, `docs/ARCHITECTURE.md`, `docs/USER_GUIDE.md`). The appendix
  documents fields, signature, validation and MINOR safety for all three
  messages; it lives in the existing MINOR-safe extension list rather than a
  new file. Limitations state detection, not prevention, and R-010.
- **Tests** (`tests/test_credits.py`). Issuance only for an accepted circle
  result (none for local/own-devices/executor-empty and none for a rejected
  replica), forged/wrong-worker/non-member/expired/duplicate refusal, spend
  only by the named worker and circle, priority only while busy, no bypass of
  admission/egress, a requester without credits still served, double-spend
  flags, wallet bounds and 0600 modes, unknown control types ignored, the API
  read-only, and two real loopback nodes that earn, deliver, spend and report.

**Baseline hygiene (T10.3a).**

- **One canonical model family** (`swarmbly_app/models.py`, `state.py`,
  `engine/directory.py`, `p2p/worker.py`, `tests/test_hardware_models.py`,
  `tests/test_p2p_two_nodes.py`). Ollama reports `llama`/`qwen2` from
  `/api/tags`; without a running backend the code fell back to the tag
  (`llama3.2`/`qwen2.5`). The same model therefore had a different family on a
  developer machine and in CI, and `llama3.1`/`llama3.2` could count as two
  families for consensus diversity. `family_for()` now prefers the backend
  family, then the catalog, then the tag. The two P2P tests assert the
  canonical family and a unit test covers both paths.
- **Windows P2P CI** (`.github/workflows/tests.yml`,
  `tests/test_p2p_two_nodes.py`). A new `p2p-windows` job runs the handshake,
  messages, two-node P2P and worker-policy tests on `windows-latest`. The
  mDNS discovery tests skip there with a reason (GitHub Windows runners do not
  deliver multicast reliably); every loopback test still runs.

**Trusted circles, WP1 (D-015).**

- **Signed membership manifests** (`swarmbly_app/p2p/circles.py`,
  `tests/test_circles.py`). A circle is a manifest with `circle_id`, name,
  owner, members (node id, display name, endpoints), version, issue/expiry and
  the owner's Ed25519 signature over canonical JSON. Tampering, a foreign
  signature, an expired manifest and a version rollback are refused.
- **Invitations as code or QR** (`swarmbly_app/qr.py`). A signed one-time
  token (`circle_id`, owner, nonce, expiry, endpoints) is compressed and
  base64url-encoded (`SWC1.…`); the QR is generated by a small pure-Python
  Model 2 encoder (no new dependency) and served as SVG. Accepting an
  invitation sends a signed join request over the existing TLS session; the
  owner approves in the Swarm view and signs the next manifest version.
- **Admission at the handshake and at the worker gate.** In circle-only mode
  both nodes must hold a valid, unexpired manifest listing the other; the
  peer's advertised manifest version is checked too. A valid invitation opens
  a control-only bootstrap session for the join request and never receives a
  task. Revocation is a new version without the member; older versions are
  ignored, connected members receive the new version, and the revoked peer is
  dropped. The explicit *my own devices* mode keeps the 3.4 LAN behaviour.
- **Default and migration.** New installs are circle-only. An installation
  that already has a config file keeps *my own devices* and shows a notice in
  Swarm until the user chooses; Settings → Swarm → *Peer admission* changes
  it. The choice is stored under `circle.*`.
- **API and UI** (`swarmbly_app/api/__init__.py`, `web/js/monitor.js`,
  `web/js/settings.js`, `web/i18n/*.json`). Create, invite (code + QR),
  accept, approve/reject join requests, list members, revoke and leave, all
  behind the local API guard, plus a Trusted circles panel in the Swarm view.
- **Storage** under `<data>/circles/` (manifests, issued invitations, pending
  joins, outgoing requests), written atomically with mode 0600.
- **Not in WP1:** the `CIRCLE` destination class, peer sends through the
  egress gate, receipts naming the circle and member, and `circle_passages`
  are WP2. A peer still appears as `OWN_NETWORK` in the receipt today.

**Node roles, WP4a (D-018).**

- **Validated node-role schema** (`swarmbly_app/node_roles.py`,
  `swarmbly_app/p2p/handshake.py`). The signed advertisement may carry
  `roles`, a list of at most eight entries: `large_model` (a model that is
  advertised plus `params_b`), `reasoner` (an advertised model plus
  `think: true`), `search` (up to four engine short names) and `corpus` (a
  display name of at most 40 characters and size `S|M|L`, never titles,
  paths or contents). Unknown roles and roles naming a model the node does
  not advertise are dropped, not fatal; malformed known metadata is rejected
  like the rest of the advertisement.
- **What this node advertises.** Only `large_model` and `reasoner`, only
  while the worker role is on and only for models actually shared:
  `large_model` for shared models at or above
  `node_roles.large_model_min_b` (default 7 B; a tag without a parameter
  count is not guessed into the role), `reasoner` for shared models
  the user marked in `node_roles.reasoner_models` (default empty). The local
  pool derives the same roles from its own models without the "shared"
  condition. A settings change re-announces through the existing signed
  `advertisement_update`.
- **Role-aware placement** (`swarmbly_app/engine/scheduler.py`). A task may
  carry a role; only workers that advertise it are candidates and only the
  role's models are considered. Per-role outcomes are learned per node in
  memory (`RoleStats`), never from the peer's claim, and a recently failed
  role node is deprioritised. Without a role worker, `large_model`/`reasoner`
  fall back to the best generic worker and the attempt, metadata, stage and
  receipt say `role X unavailable, ran on Y`; `search`/`corpus` fail honestly.
- **Packet and worker** (`swarmbly_app/p2p/worker.py`). MINOR-safe
  `constraints.role` and `constraints.think`; a worker refuses an
  unadvertised role with `E_ROLE_UNAVAILABLE` before taking a slot or running
  anything, and passes `think` only to a backend that accepts it.
- **UI** (`web/js/settings.js`, `web/js/monitor.js`, i18n en/es). Settings →
  Swarm exposes the threshold and the reasoning-model list with one-line
  explanations; the Swarm panel shows the node's own roles and each peer's
  advertised roles.
- **Not in WP4a:** the search and corpus executors (WP4b) and teams (WP5).
  Their roles are already in the wire schema so those changes are additive.

**Search and corpus executors, WP4b (D-018).**

- **Opt-in roles** (`swarmbly_app/node_roles.py`, `config.py`, `state.py`).
  `node_roles.search.enabled` is off by default and a worker advertises
  `search` with only the engines its own configuration supports (PubMed,
  Wikipedia, and SearXNG only when a URL is configured). Corpus sharing is a
  project plus the circles allowed to read it, also off by default; only a
  display name (at most 40 characters) and a size bucket (`S|M|L`, from
  document count) are advertised. Worker-off still means no roles at all.
- **Search executor** (`p2p/worker.py`, `web_search.py`). A search task
  carries only a public query, in a packet with no Γ, predecessors or
  conversation; the requester derives it with `strip_private_details` and
  its glossary/private terms and sends nothing if that cannot be done. The
  worker accepts one short line (not a document), requires a shared trusted
  circle (not *my own devices*), checks its egress policy for each engine and
  records the query, circle and member it ran for in its own ledger. Results
  are bounded titles, URLs and snippets, signed like any result.
- **Corpus executor** (`p2p/worker.py`, `lce_adapter.py`). A corpus task is
  refused with `E_ROLE_UNAVAILABLE`, before retrieval, unless the requester
  belongs to a circle the corpus is shared with. It reads only the selected
  project's roots, returns at most five bounded passages with a neutral
  citation (document title and span id, never a path), and records the
  passages, count and bytes in the worker ledger.
- **Requester rules** (`engine/scheduler.py`, `engine/orchestrator.py`,
  `chat.py`, `egress.py`). Search sends show the public query, circle, member
  and executor kind in the receipt, and say the requester cannot verify the
  engine. Corpus results are labelled in `role_sources` with the member and
  circle the requester sent to, never the worker's claim; they stay out of
  glossary/memory. They are treated as the requester's passages for egress:
  a packet carrying them reaches only the local pool or a circle peer with
  `circle_passages` on (or the own-devices switch), and a third-party model
  only with `privacy.third_party_passages`; otherwise the dependent task runs
  locally or fails honestly.
- **UI and docs**: Settings → Swarm has the search switch and the corpus
  project/display name, each circle card has a “Share corpus with this circle”
  switch, and the Swarm panel explains that every admitted peer sees the name
  and bucket. English and Spanish strings, architecture, limitations and user
  guide were updated.
- **Tests**: `tests/test_node_executors.py` covers opt-in defaults, worker-off,
  engine lists, the private-term query guard, document-like query refusal,
  non-member/unshared-circle refusals with nothing searched or retrieved,
  worker ledgers, neutral citations, the passage gate for peers and model
  services, real loopback search and corpus in a shared circle, and the local
  pool path. Network calls are faked.

**Teams and honest partial results, WP5 (D-019).**

- **Stored plan templates** (`swarmbly_app/teams.py`, `tests/test_teams.py`).
  A team is a named list of steps with an instruction template (`{request}`),
  an optional node role and dependencies on earlier steps only. User teams
  live in `<data>/teams.json` and project teams in `<project>/teams.json`,
  validated on load and on save (at most 12 steps, bounded names and
  instructions, known roles, unique ids, no forward edge and therefore no
  cycle); writes are atomic and mode 0600. Three neutral built-in examples are
  read-only and can only be duplicated.
- **Running a team** (`engine/orchestrator.py`, `chat.py`, `api/__init__.py`).
  `Orchestrator.run(team=…)` builds the plan from the template instead of
  calling the router and the planner, substitutes the user's request and
  passes the step roles as `task_roles`. The same template runs on one node
  (local pool with every role) or across circle members by role. No new wire
  message: the task plane stays 0.2. Every gate still applies: lane/tier,
  circle admission, the egress gate, passage rules, the WP4b public-query
  guard and corpus provenance; a team never widens a permission.
- **Teams API and UI** (`api/__init__.py`, `web/js/teams.js`,
  `web/js/chat.js`, `web/index.html`, `web/i18n/*.json`). List, create, edit,
  delete, duplicate a built-in, and a composer selector that runs the chosen
  team for one message, with English and Spanish strings. The Teams view says
  what a team is and that the stored templates are local.
- **Honest partial results** (`engine/scheduler.py`,
  `engine/orchestrator.py`, `chat.py`). `run_levels` records a state per step
  (`completed`, `failed`, `blocked`), with a stable reason (`node_lost`,
  `deadline`, `policy_refusal`, `role_unavailable`, `no_worker`, `failed`).
  A failed step no longer aborts the plan: independent steps continue, and
  every dependent step is marked `blocked by <step>` and is not run. The
  answer assembles the completed steps and appends a note naming each missing
  step and why; the metadata carries `status` (`complete` / `partial` /
  `failed` when nothing usable completed), `steps` and `missing_steps`. A
  failed run goes through the normal error path and still keeps its per-step
  record. The receipt is unchanged in meaning: only what was really sent.
- **Lists** (`chat.py`, `recipes.py`). Recipe 4 keeps its per-item statuses;
  a failed wave marks its own items `failed` with the reason and later waves
  continue. The table summary and metadata report the failed count, and the
  answer names the waves that failed.
- **Stops and coordination** (`engine/scheduler.py`). A user stop cancels the
  run and stays `stopped`, never a partial answer. The requester remains the
  only coordinator: if it goes away the run ends; no plan migration.
- **Tests**: `tests/test_teams.py` covers validation (cycles, forward and
  self dependencies, unknown role, bounds, duplicate ids), read-only
  built-ins, per-user/per-project storage, the API and the en/es strings;
  `tests/test_teams_run.py` covers a team entirely on the local pool, the
  same team across two real loopback nodes in a shared circle with role
  placement, a node stopped mid-run (partial answer, missing step named,
  dependent blocked), nothing completed (`failed`, not `partial`), user stop,
  chat status, a failing recipe-4 wave that keeps the other waves, and a
  no-team regression. Network calls are faked.
- **Docs**: architecture, this changelog, the user guide (en/es) and
  limitations describe teams, partial answers and the single coordinator.

**Honest peer classification, WP2 (D-017).**

- **Destination class `CIRCLE`** (`swarmbly_app/egress.py`,
  `swarmbly_app/p2p/circles.py`). A peer send is classified by the circle
  service: a member of a valid shared manifest is `CIRCLE` with its
  `circle_id`; the explicit *my own devices* mode is `OWN_NETWORK`; a peer
  outside every circle is refused, never labelled. `Policy` admits `CIRCLE`
  only through that classification.
- **Peer sends through the egress gate** (`swarmbly_app/p2p/node.py`,
  `engine/scheduler.py`). `NodeManager.dispatch_async` calls
  `egress.check_call` with purpose `FRAGMENT` before it writes a packet; a
  refusal raises before `_write`, so no bytes leave. Attempts keep the real
  destination class for the receipt.
- **Receipts tell the truth** (`swarmbly_app/chat.py`, `web/js/chat.js`).
  The hard-coded `OWN_NETWORK` is gone: a circle send shows `CIRCLE`, the
  circle name and the member's display name plus short node id; a blocked
  peer is not counted as a send. A list wave also reports how many document
  passages reached each destination.
- **Per-circle `circle_passages`** (`swarmbly_app/p2p/circles.py`,
  `swarmbly_app/config.py`, `api/__init__.py`, `web/js/monitor.js`). Stored
  with the circle on this node, off by default, independent of
  `privacy.third_party_passages`. Recipe 4 attaches passages only to the
  peers of circles whose switch is on: in a mixed swarm the grounded wave is
  sent to those members and never to the others. *My own devices* mode uses
  the equivalent `circle.own_devices_passages` switch (also off by default).
  An existing `third_party_passages=true` does not turn either on.
- **Docs and tests.** `ARCHITECTURE.md` now states the exact rule instead of
  leaving passages unaddressed; the user guide explains the receipt classes
  and both switches. New tests cover classification per mode, the gate
  refusing a non-member before any write, the receipt naming circle and
  member, passages only with the switch on, and the migration default.

## 0.7.0 — Tools (2026-11-20)

Swarmbly AI 3.4. Tools and data with code. One broker for every tool; an MCP
client with approval per call (a local tool can be set to "don't ask again in
this project"; remote tools, the sandbox and author search always ask); skills
(`SKILL.md`, instructions only); author search with consent (ORCID, OpenAlex,
PubMed); recipe 4, a list on the swarm; recipe 5, data with code in a WASI
sandbox (`wasi-python` 0.1.5); the Anthropic provider, an embeddings role and
the `swarmbly-agent` 0.1.0 runtime; Python 3.11 as the minimum; private
glossary entries. The sealed banks v4.1 and v4.2 were run once (32 cards × 3,
`qwen2.5:7b`, harness 1.3.2, re-scored offline with 1.3.4, isolated judge):
seal OK, 0 technical failures, the eight permission counters at 0 in both
banks, approved observations 22/96 and 44/96. Two exit criteria failed: zero
unauthorised sends (the public query proposed by the App kept a fragment of a
private name: one card in v4.1 and two in v4.2, three repetitions each, each
approved by the simulated user) and exact results ≥ 90 % in código-exacto
(v4.1 0/9, v4.2 6/12). The fixes after the banks (private names removed whole
and by distinctive word, with the removed terms shown; recipe 5 reads text
documents; the list recipe uses relevant passages per item; private glossary
entries) were measured only on open batteries: recipe 4 30/36 cases
(195/201 cells; the original 11 cases 27/33, 183/189), recipe 5 39/39 cases
(57/57 numbers), the v4 self-test 24/24, 0 unauthorised sends. A new sealed
bank will confirm the privacy fix. Known limits: exact results with a 7B local
model; the 3.4 privacy fix is not yet confirmed by a sealed bank; the Windows
disk guard is watchdog-only (R-006); the first sandbox compile is slow (R-005).
Requires SwarmblyLCE 0.2.1.

- **Glossary: a private entry never reaches a public query (T9.17)**
  (`swarmbly_app/memory_capture.py`, `web_search.py`, `lce_adapter.py`,
  `local_context.py`, `projects.py`, `api/__init__.py`, `web/js/chat.js`,
  `web/i18n/*.json`, `tests/test_glossary_private.py`). A glossary line can
  now carry `| privado` (also `| private`, `| privado: sí`/`yes`/`true`, case
  and accents ignored). LCE drops that bare segment because it is not one of
  its metadata keys, so the App reads the raw lines from the same roots the
  adapter already reads. The term and its equivalents of a private entry are
  explicit private terms for the proposal: removed whole (a short code too)
  and by distinctive word, reported in `removed_terms`, never used as a
  translation in a public query and never returned by
  `public_glossary_terms`; an unmarked entry keeps today's behaviour. The
  memory card offers *Private: never used in public searches* (a `private`
  field in the API), `glossary_line` writes `| privado`, the saved list shows
  the mark, and a later edit keeps it. Local answers still use the entry;
  passages and local retrieval are unchanged.

- **Research proposal: report exactly the private terms it kept out (T9.16)**
  (`swarmbly_app/web_search.py`, `recipes.py`, `tests/test_recipes.py`). The
  proposal filtered the private run before building the offer, so EJ4-04's
  `removed_terms` named the public station "Quilén Bajo" and never the
  private "Rincón Alto". The question's capitalised private runs are now
  candidates even when they never entered the proposed query; glossary
  equivalents are public names, so they stay in the query and are never
  reported as removed; and an explicit `private` term still wins over a
  public-looking one. `removed_terms` is exactly the private terms present
  in the question, glossary translations or model keywords and absent from
  the query, and the UI's `removed` words come from those terms.

- **List recipe: a passage is attached only to the item it is about (T9.15)**
  (`swarmbly_app/recipes.py`, `chat.py`, `tests/test_recipe_list.py`). T9.12
  put the top passages of the project under every item, so a row of
  `lotes.csv` was offered to a plot-code record; the original open list
  battery fell from 27/33 cases (183/189 cells) to 21/33 (156/189). A
  passage is now kept only when the item's code or a distinctive word
  appears word-bounded in it (accents and case folded), or when a table
  row's key is a cell; a long record needs two of its words in a table. At
  most two passages are attached, prose before table rows, and an item with
  no relevant passage gets the exact pre-T9.12 prompt. The project's
  glossary entries and every document paragraph are also searched
  lexically, so a short code such as `QA` finds "QA = Quilén Alto" even
  though C1 does not index the glossary. The answer and meta still say
  whether documents were used or withheld, and receipts record only the
  passages actually given to the model.

- **List recipe reads the project documents per item (T9.12)**
  (`swarmbly_app/recipes.py`, `chat.py`, `tests/test_recipe_list.py`). The
  list path built its prompt from the operation and items only, so cards
  with “Documentos” answered from memory. Each wave now retrieves passages
  for every item with the same local retriever the chat recipe uses and
  places them under their item, with `[D…]` labels. A local list always
  uses them. A swarm list uses them only when
  `privacy.third_party_passages` is on; otherwise the passages stay home
  and the answer says the documents were not used. The receipt records the
  passages only when they were actually given to the model.

- **Recipe 5 hands the script the text documents too (T9.11)**
  (`swarmbly_app/recipes.py`, `chat.py`, `tests/test_recipe_code.py`). The
  file picker now scans the project's `sources` for Markdown, plain text and
  JSON alongside CSV/TSV/XLSX/XLSM, with the same containment checks
  (realpath inside the project, no symlinks, size cap) and a read-only copy
  into `/data`. The script proposal lists each text file by name, size and
  its first five lines, with the same cap idea as the spreadsheet sample;
  the rest of the document is not shown. A recipe-5 end-to-end test reads a
  `.md` and a `.csv` from the sandbox.

- **Research proposal: a private name is removed whole (T9.10)**
  (`swarmbly_app/web_search.py`, `recipes.py`, `api/__init__.py`, `chat.py`,
  `web/js/chat.js`, i18n). A private place name at the start of a request was
  detected only by its last word ("Rincón Alto" left "Rincón" in the offered
  query). The guard now takes a capitalised private run whole, matches whole
  terms and their fragments token by token (accents and case folded, word
  bounded, hyphens as separators), and only removes a *distinctive* word on
  its own: common place words (“norte”, “alto”, “bajo”, “río”) stay when the
  user writes them alone, but leave as part of a multi-word private term. The
  proposal returns `removed`/`removed_terms`/`empty`; the UI lists the terms
  removed and says when no public query remains. Nothing is sent by the
  proposal, and the query is still editable and approved by the user.

- **Launch-time test host map (D-013)** (`swarmbly_app/test_hosts.py`,
  `cli.py`, `egress.py`, MCP/author/HTTP clients, `web/index.html`,
  `web/js/app.js`). The sealed-bank v4 harness can now exercise third-party
  paths without weakening the policy for real users. `swarmbly-app serve
  --test-host-map FILE` (or `SWARMBLY_TEST_HOST_MAP=FILE` read once at process
  start) loads a JSON object `{"declared.host": "http://127.0.0.1:PORT"}`.
  Policy, classification, `privacy.tool_hosts`, `third_party_passages`,
  `AUTHOR_QUERY` and `personal_name` are still computed on the declared host;
  only the TCP connection is redirected, at the HTTP client factory / connect
  step (the original `Host` header is kept). Remote MCP Streamable HTTP,
  author tools and the other egress-checked HTTP clients share the same seam.
  Only listed hosts are redirected; every target must be loopback
  (`127.0.0.0/8`, `::1` or `localhost`) or the app refuses to start. A
  redirected receipt entry carries `simulado: true`, the startup log prints
  the map, and the UI shows the persistent banner “Test mode: some services
  are simulated”. The map is deliberately not a setting: it cannot be set
  from the UI, `/api/config` or the config file (unknown keys are refused by
  the settings validation), and changing it requires a new process. Checked
  for this task: `POST /api/projects` already exists with the UI's validation
  (name, folder under the default projects root unless given) behind the local
  API guard, so no duplicate project-creation route was added.

- **Author search in the chat** (`swarmbly_app/author_search.py`,
  `api/__init__.py`, `web/js/chat.js`, i18n). When `tools.author.enabled` is
  on, the composer shows “Look up an author” and the research recipe has an
  optional “Also look up an author” field. Both open one consent box with the
  exact editable name, ORCID/OpenAlex/PubMed checkboxes (all on by default),
  the sentence “This name will be sent to: … It is a person's name.” and
  Run/Cancel. Cancel sends nothing. `POST /api/author/lookup` (alias
  `/api/author/approve`) is the only route that issues the per-service broker
  tokens and invokes the tools; with the switch off it refuses with a plain
  message and registers nothing. The answer is a Markdown table built in code
  from `normalise_works` (title, year, venue, DOI link, source) with `[A1]`,
  `[A2]` labels; ambiguous ORCID stops after the people search, returns
  candidates (name, iD, affiliation) and fetches no works until the user picks
  one. `meta.author` records `{name_sha256, services, counts,
  candidates_shown}`; the receipt lists each send with its host, real bytes,
  `AUTHOR_QUERY` and `personal_name: true`. Titles stay text: the UI's Markdown
  escapes HTML and the app never reads a title as an instruction. New routes
  `GET /api/author/status`, `POST /api/author/cancel`; English/Spanish UI.

- **Skills in the app: import, offer and activation** (`api/__init__.py`,
  `chat.py`, `web/js/chat.js`). A project gets a `skills/` folder; importing a
  skill copies only `SKILL.md` and its `.md`/`.txt` references, and the answer
  lists the scripts, assets, binaries and links it left out and why. Listing
  shows the name, description, source, size, ignored files and the skill's
  `allowed-tools` as “requested by the skill — not granted”. The chat offers a
  skill as a chip when the message shares at least two meaningful words with
  its name/description (or a name word); it only offers, never activates. The
  user can also pick one explicitly from the composer. On activation the body
  enters the prompt as quoted, labelled third-party material that says it
  cannot change permissions, tools, destinations or settings; `meta.skill` and
  `receipt.skill` record its name and SHA-256, and the loader's 20 000-character
  prompt cap still applies. A body that says “send this to …”, “enable tool X”
  or “ignore previous instructions” is only text: no tool approval, egress
  call, destination or setting changes. New routes `GET /api/skills`,
  `POST /api/skills/import`, `POST /api/skills/match`; English/Spanish UI.

- **Sandbox tests: cold metered fuel compile and Windows links**
  (`swarmbly_app/sandbox/runner.py`, `worker.py`, `tests/test_sandbox_runner.py`).
  A fuel run needs wasi-python's separate metered module compile (a cold
  compile is several seconds on a laptop and longer on a small runner). The
  worker now writes `metered-warm.json` after paying it, and the parent starts
  the guest's hard wall clock only after that marker, so the first fuel run on
  a slow machine is not killed as a deadline. The wall still covers all guest
  work; no limit or security check changed. The time checks are split into
  `test_05a_deadline` (unchanged bounds) and `test_05b_optional_fuel`. The
  symlink check now reads the guest's own row: on Windows wasmtime's
  `path_symlink` refuses the relative link (it stats the target first, and the
  target does not exist), so the follow-up write creates a regular file inside
  `/out`; the test asserts that contained file, checks the host canaries, and
  walks the retained output with `lstat` to prove no link is collected or
  followed. It also records R-006 explicitly: Windows has only the watchdog,
  POSIX has `RLIMIT_FSIZE` plus the watchdog.

- **Sandbox tests: cold-compile timing** (`tests/test_sandbox_runner.py`).
  The deadline check now starts its wall clock only after a worker reports
  ready, and the sandbox runner tests share one session-scoped wasmtime cache
  (the `.cwasm` file only, never run data). A cold compile on a small CI
  runner no longer counts against the deadline assertion; the session cache
  is still outside every `/data`/`/out` grant and every run keeps its fresh
  per-run directories.

- **MCP servers in Settings** (`swarmbly_app/api/__init__.py`,
  `web/js/settings.js`). The new `/api/mcp/...` routes list, add, inspect,
  start, stop, propose and approve MCP servers per project, behind the existing
  host/origin/session-token guard. Adding or listing a server never starts it;
  only the explicit Start route does, and app shutdown stops what it started.
  Local entries show the exact command line, working folder and environment
  variable names before the first start, with the plain notice that the server
  runs with the user's own rights and is not sandboxed. Environment values are
  never accepted by the API, stored, logged or returned: the UI only shows
  whether each name is set in the environment or keychain. Remote entries are
  labelled third party and show their host, with the `privacy.tool_hosts`
  checkbox and the separate `privacy.third_party_passages` switch. Tool
  descriptions are returned as plain JSON text and rendered as quoted text
  through `textContent` (never HTML or Markdown links); approval is a subset of
  checkboxes. A suspended server shows its reason and must be proposed and
  approved again. The new Tools tab also has the `tools.author.enabled` switch
  (default off, now a validated setting) with one sentence explaining that a
  lookup sends the exact name approved for that call to ORCID, OpenAlex or
  PubMed. English and Spanish strings were added.

- **Recipe 5: data with code** (`swarmbly_app/recipes.py`, `chat.py`,
  `api/__init__.py`, web chat/i18n). The "Data with code" card lets the user
  pick project source files and ask a question. The writer model (role
  `writer`, else the conversation model, with the usual destination policy)
  receives only file names, column headers and at most five sample rows per
  table, and returns one Python script parsed defensively under a size cap.
  The UI shows the script, the files it will see, the limits and run/cancel;
  nothing runs before approval. `POST /api/recipes/code/approve` is the only
  path that issues the broker's one-time `sandbox/python` token and invokes
  the tool; cancel, missing `wasi-python`, traps (deadline, memory, output,
  disk, files) and the two-correction limit are handled explicitly. The answer
  gives the script, stdout/stderr with a truncation marker, produced files with
  name/size/SHA-256 and token-safe download links from that run's retained
  `/out`; `meta.code` records the script hash, input names, trap, elapsed time,
  `approved_by: "user"` and correction count. The receipt lists the local tool
  call and any model send, and the Windows watchdog-only disk guard is shown
  in the approval box (R-006). Recipe 5's earlier runner, extra and escape
  tests are unchanged; this adds the flow, approval and chat wiring.

- **Author search with consent** (`swarmbly_app/tools/author.py`). Three
  broker tools, `author/orcid`, `author/openalex` and `author/pubmed`, look up
  a person's public works only after the user approves the exact name string
  and the services. Each call needs a one-time token bound to those arguments,
  so a different name is refused before anything is sent. The tools are
  registered only when `tools.author.enabled` is true (absent means off). The
  name is sent exactly as approved, never stripped, and every request goes
  through the fixed `AUTHOR_QUERY` egress kind (never `PUBLIC_QUERY`); the
  receipt entry now carries `personal_name: true` and
  `nombres_personales_enviados` counts it. Results are normalised
  `{title, year, venue, doi, source, url}` lists, deduplicated by DOI and then
  by normalised title, and wrapped as quoted data by the broker. ORCID first
  searches people; when several plausible matches remain it returns
  `candidates` (name, ORCID iD, affiliation) instead of choosing one, while an
  optional ORCID iD skips the search and an optional affiliation hint narrows
  candidates locally without being sent. OpenAlex and PubMed honour
  `max_results` (up to 25), PubMed keeps DOIs, and rate limits are plain
  errors. No UI, API route or chat wiring in this step.

- **Embeddings role** (`swarmbly_app/inference/embeddings.py`, `roles.py`,
  `lce_adapter.py`, `state.py`). Retrieval over the user's sources (C1 dense
  fusion), the seam/agreement similarity of the orchestrator and direct
  embedding calls now choose their embedder through `roles.choose("embeddings")`:
  the app's previous Ollama `/api/embed` model by default, or a chosen Ollama
  model / OpenAI-compatible `/v1/embeddings` server. Anthropic has no
  embeddings endpoint, so selecting it is refused in validation and at
  runtime with that message. Every embedding request passes
  `egress.check_call` before a byte (`PASSAGES` for document batches,
  `QUESTION` for the query). A third-party destination receives passages only
  when its host is authorised **and** `privacy.third_party_passages` is on;
  otherwise the call is refused (`meta.lce.embeddings.note` and the receipt's
  `bloqueados`), the app's own local Ollama embedder takes over when
  configured, and otherwise C1 keeps keyword retrieval. Changing the embedding
  model or the vector dimension rebuilds the C1 index (a new `SourceIndex`, so
  vectors from two models never share the text-keyed cache) and says so in
  `meta.lce.embeddings` (`rebuilt`, `reason`, `previous_model`, `dimension`).
  Settings → Models gains the role's model/server/URL/key fields (en/es). The
  role's key is kept in the system keychain.

- **Recipe 4: a degenerate long wave is retried item by item** (`chat.py`,
  `recipes.py`, `engine/orchestrator.py`). The local list path sent a whole
  wave (up to 12 items) as one prompt with “responde solo ese elemento”. With
  12 near-identical records, qwen2.5:7b answered item 1 for the whole wave
  (`8` in all twelve cells), while the 6-item second wave was correct; the
  app wrote the repeated value into the table. A wave where at least four
  distinct items receive four or more identical answers is now retried one
  item per prompt as a single-row Markdown table, and `meta.list` reports
  `retries` (and each wave's `retried` flag). The parser also ignores a number
  inside an echoed item (“Ficha 2: …”) and reads a single-item table row or an
  item with its number replaced, so the retry's answer is not lost. A 4-item
  wave is unchanged; a 13-item list retries only its 12-item first wave.

- **MCP client core** (`swarmbly_app/tools/mcp.py`, `mcp_registry.py`). MCP
  servers are configured per project in `settings/mcp_servers.json` with the
  exact local command, arguments, working directory and environment-variable
  names the user sees, or a remote URL; environment values are read at start
  and never stored. A local server is spawned only when the user calls
  `start`, with the allowlisted environment and the configured cwd. A remote
  server is always a third party: it needs its host in `privacy.tool_hosts`
  and passes `egress.check_call(kind=TOOL_REMOTE)` before connecting. The
  client lists every tool with pagination, hashes the canonical manifest of
  names, descriptions and schemas, and approves only a subset; each approved
  tool is registered in the broker as `mcp:<server>/<tool>` with the broker's
  strict schema (presentation-only annotations such as Pydantic's `title` are
  ignored, validation keywords such as `pattern` still cannot be approved).
  A changed manifest on reconnect or a `tools/list_changed` notification
  suspends the server, unregisters its specs and records the reason until the
  user approves again. Calls go through `broker.invoke`; text is concatenated,
  structured content stays data, `isError` becomes `ok=False`, images, audio
  and resources are reported as `omitted: <type>`, and the broker's result cap
  applies. Remote calls whose arguments are long or contain an 8-word shingle
  of the request's retrieved passages also need `privacy.third_party_passages`.
  A local MCP server runs with the user's own rights and is not sandboxed; the
  app says so in `describe()`. The SDK is an optional `[tools]` extra
  (`mcp==2.3.0`), imported lazily with a clear error when missing.

- **Sandbox runner for recipe 5** (`swarmbly_app/sandbox/`, WebAssembly CPython
  over `wasi-python==0.1.5` / `wasmtime==50.0.1`, D-010). `SandboxRunner.run()`
  copies the selected project files into a fresh read-only `/data`, grants a
  fresh writable `/out` and nothing else (no root, mounts, host, tools,
  `import_path`, stdin or environment overlays), and returns stdout, stderr,
  file name/size/SHA-256, a trap reason and the script hash. Every run gets a
  disposable, pre-warmed child-process worker (pool size 1, one run then
  recycle); a hard wall clock kills the worker's process group, and collection
  never follows a symlink. Limits default to 10 s, 256 MiB, 4 MiB per stream,
  256 MiB / 10 000 output entries and a 384 MiB file cap: `RLIMIT_FSIZE` plus
  a soft watchdog on POSIX, watchdog only on Windows (`platform_guard:
  "watchdog"`, R-006). The one-time compile is never paid at import; call
  `warm_up()` for time and peak RSS (R-005), and `available()` degrades
  cleanly when the optional `[sandbox]` extra is absent. The broker gets the
  `sandbox/python` spec (kind `sandbox`, destination `local`, one-time token
  required), with realpath containment to the current project folder; local
  runs appear in the receipt's `tools` list and send nothing. New `sandbox`
  pytest marker and a three-OS CI job run the escape tests. Recipe 5's flow,
  approval UI and chat wiring are not part of this change.

- **Python 3.11 is the minimum** (D-006). `pyproject.toml` now declares
  `requires-python = ">=3.11"` and lists 3.11–3.13; the doctor, the launchers,
  the README/INSTALL requirements and the CI matrix no longer accept 3.10
  (security support ended on 2026-10-01, and the MCP SDK and `wasi-python`
  require 3.11).

- **Recipe 4: process a list on the swarm.** The disabled card is available:
  paste one item per line or pick a CSV file from the project's sources and a
  column (real CSV, quoted multi-line fields included), write the operation,
  and see exactly what would leave — operation, items, duplicate count and
  available nodes — before choosing "On the swarm" or "Only on this computer".
  Personal or sensitive items default to local (the user can still choose the
  swarm explicitly), and the receipt records the recipe and the choice. Waves
  are sized from `swarm.n_fragments_max` × `swarm.min_items_per_fragment`
  (default 12 items) and run sequentially through the existing batch path;
  the answer is a code-built table (#, item, answer, status) with
  answered/missing/disagreement, duplicates kept and marked, and nothing
  invented for a missing item. `recipes.list_max_items` (default 200) is
  validated in the config.

- **Tool broker foundation** (`swarmbly_app/tools/`). One entry point for tool
  calls: a strict JSON-Schema subset (no `jsonschema`, unsupported keywords
  refused), per-project approvals stored as `{spec_id, approval_hash,
  granted_at}` with atomic writes, "rug pull" protection when a description or
  schema changes, and one-time approval tokens bound to the tool, canonical
  arguments and request for `sandbox`/`author` tools. Tool results are quoted
  data with their source and hash, capped at 8000 characters. Egress has the
  new `TOOL_REMOTE`, `AUTHOR_QUERY` and `TOOL_LOCAL` kinds: remote tools need
  their host in `privacy.tool_hosts`, author lookups need the fixed ORCID /
  OpenAlex / PubMed allowlist plus a per-call consent, and local tools appear
  in the receipt's new `tools` list. No MCP, author search, sandbox, approval
  UI or tool-invoking chat path yet; those plug into this broker.

- **Skills loader** (`swarmbly_app/skills.py`). Agent Skills in the
  `SKILL.md` format are read as instructions from a file, never as code:
  loading, discovering, reading a reference and importing do not import, exec,
  compile or run anything, do not add to `sys.path`, and never grant the
  `allowed-tools` a skill requests (the parsed values are exposed as
  `requested_tools` with a note). The frontmatter parser is deliberately
  minimal and strict: only `key: value` scalars and one level of `metadata:`
  string pairs, with anchors, aliases, tags, flow collections, multi-document
  files, duplicate keys, non-string values, BOMs and tabs in indentation
  rejected; unknown top-level keys are kept aside with a warning. A skill
  directory is validated for its name (matching the directory) and
  description, and its `SKILL.md` (100 KB), total readable text (2 MB), file
  count (200) and body length are capped. `scripts/`, `assets/`, executables
  (exec bit or shebang), binaries, archives, symlinks, junctions and hardlinks
  are ignored or rejected with a reason, as are paths with `..`, absolute
  paths, NUL bytes and invalid UTF-8. `read_reference` reads only `.md`/`.txt`
  under `references/` or in the skill root. `import_skill` copies only
  `SKILL.md` and allowed reference text into a temporary directory and renames
  it into place, returns a manifest of what was copied and ignored, and never
  copies or runs a script. `as_prompt_block` wraps the body as quoted,
  labelled material that says the user activated it and that it cannot change
  permissions or tools.

- **Native Anthropic provider** (`swarmbly_app/inference/anthropic.py`). The
  conversation model and every role can now run on Anthropic's Messages API
  (`POST /v1/messages`, SSE) without the Anthropic SDK: httpx is enough. The
  system prompt travels in the top-level `system` field and consecutive turns
  of the same role are merged; the model list comes from `GET /v1/models` with
  its `has_more`/`last_id` pagination. Streaming text deltas, stop reason and
  token usage are read from `message_start`, `content_block_*`, `message_delta`
  and `message_stop`; thinking deltas are ignored unless thinking is asked for,
  in which case the request sends a budget below `max_tokens` and omits
  `temperature`. HTTP 401/403, 404, 429, 5xx and `overloaded_error` become the
  app's retryable `BackendError`. Anthropic is a third party: every request,
  including the model list and the availability probe, passes
  `egress.check_call`; nothing is sent unless `api.anthropic.com` is authorised
  in `privacy.third_party_models`, passages need the second authorisation, and
  a node whose conversation model is Anthropic never serves the swarm. The
  backend is accepted by the registry, configuration validation and the
  settings UI (with the existing key fields and i18n in English and Spanish).

## 0.6.0 — Roles and recipes (2026-11-17)

Swarmbly AI 3.3. Models by role; the cards of "¿Qué quieres hacer?" with
three recipes (ask your documents; compare documents in a table built by
code; research with public sources, with the query approved before
anything leaves, comparisons and disagreements computed by code and a
claim verifier). Each step was kept only if the open development battery
(`bench/dev`, fictitious) showed it helps: final full run 112/123 cases and
343/354 key data, no leak. Measured once on two new sealed banks (v3.1 and
v3.2, written by the author, 28 cases each), on `b149a77`: short answers
87/146 key data, compositions 0/16 passed with 70 % of their claims
supported, no passage or personal name sent, and one private site name
sent in a query the harness approved as proposed. What those runs found
was fixed afterwards and checked on the open batteries (`bench/dev`,
`bench/dev_v3`) and on confirmation runs of the same banks, which are not
blind; figures in the Swarmbly AI 3.3.0 release notes. Not fixed: a 7B
model can still read "10, not 12" as the first figure, and tables that
need sums over a CSV wait for recipe 5 (3.4). The usability test of the
privacy receipt with people (criterion of 3.1) is postponed. Requires
SwarmblyLCE 0.2.1.

- **Models by role** (`swarmbly_app/roles.py`, settings `roles.*`). A role
  names a model, whether it may reason before answering and, optionally, a
  server of its own: `writer` (compositions with the user's sources),
  `search_terms`, `fusion` (answers that join the user's sources with public
  evidence) and `verifier` (reserved for the recipes). An empty model is the
  conversation's model. The older settings keep working (`compose.model`,
  `lce.expansion_model`, `evidence.fusion_model`). A role never widens what
  may leave the computer: its destination goes through the 3.0.1 policy
  (a third party receives nothing unless authorised, the user's documents
  only with the second authorisation), and when the policy does not allow
  it, or the model is not installed, the conversation's model does the job
  and the answer says so (`meta.roles`, a chip under the answer). Reasoning
  is set per role (`roles.writer.think`), so a reasoning model can write
  compositions without thinking while the conversation's model is left as it
  is. A writer on a simulated OpenAI-compatible API is covered by tests:
  nothing sent without authorisation, no document without the second one,
  the composition and the receipt with both, questions never. Settings nest
  to any depth (`roles.writer.model`), and role keys go to the keychain.
- **Recipe 2, a table built by code** (`swarmbly_app/tables.py`,
  `compose.table_by_code`). Compositions that ask for a
  table were still annulled in the sealed banks for an invented row or a
  wrong value. Now the model does only short jobs: it writes the header the
  request asks for, and fills, for each document that bears on the request,
  the rows that document gives. The code keeps a cell only if its value is
  in that document, drops a row whose key is not there or a cell in a column
  named after an entity the document does not mention, merges the rows of
  several documents by their key, computes differences, adds a "Fuente"
  column with the paragraphs each row came from and writes "—" for what the
  sources do not give. The model then writes the text around the finished
  table; a table of its own is removed (`meta.table`). First run on the open
  battery (5 table cases × 3, qwen2.5:7b): no table built in 15 of 15. With
  a whole report of filler the model answered that the document gave no
  row; with a source table it answered the same, or copied one row of four.
  So: a table the document already has is read by code (each wanted column
  takes the source column it matches; one wanted by two lots goes to the
  lot the document mentions), the model reads only the paragraphs that bear
  on the table, and only for prose; the header loses what the model added
  on its own (a "difference" nobody asked for, units that are not the
  source's); values come back as the document writes them ("1150" →
  "1.150", "Mar 2019 - Jul 2022" → "de marzo de 2019 a julio de 2022").
  Second run (same cases, with the recipe): passed 8/15 → 15/15, key data
  99/111 → 111/111, answers with a citation 9 → 15, no unsupported cell, 9.3 s
  per answer against 7.2 s; the table was built by code in 12 of 15 (the
  yields table was not: see the next point).
  Full battery with the recipe (33 cases × 2, x33): on the 30 cases of the
  earlier run, passed 52/60 → 52/60 and key data 129/138 → 130/138; the five
  table cases passed 10 of 10 with no unsupported cell in 64, the table
  built by code in 8. The yields table was still the model's: told "one row
  for each of AB1, AB2", it wrote the header "| Lote | Sitio 1 | Sitio 2 |
  Sitio 3 | Diferencia |". The hint now goes only when the request names
  both sides of the table (single prompts, one run each: without it the
  model wrote "| Sitio | Lote AB1 | Lote AB2 | Diferencia |", and for two
  people "| Individuo | Cargo actual | Institución | … |" where the hint
  gave "| Variable | Ana Pérez | Luis Soto |"). A column named only after
  an entity ("Lote AB1") takes the source column the request asks about and
  its name ("Rendimiento medio AB1 (t/ha)"), and a document is about the
  entity its file is named after. **On by default** since that run
  (`compose.table_by_code`).
- **The notice of facts not mentioned lists less.** With the rows of tables
  visible, the notice appeared in 6 of 66 answers and none of the 8 missing
  key data was in it (x33): it listed the rows of a table for a paragraph
  that asked for a mean, the mean of another lot, and a line of a list of
  publications. A fact about another code than the ones the request names
  is left out, so is a reference line ("Revista … 12: 45–52."), and the
  rows of a table count when the request asks for a table, names what the
  rows are ("por sitio") or names the row.
- **Claim verifier, first step of recipe 3** (`swarmbly_app/verify.py`,
  `compose.verify`, on by default since the full battery was run with it). A label
  says where the model claims a sentence comes from, not that the paragraph
  supports it: read by hand, 16 of 43 labelled sentences of the open
  battery (x33) were not supported by what they cite (the figure was in
  another paragraph, the paragraph was about something else, the sentence
  added an opinion or changed a "will present" into a "presented"). Each
  labelled sentence is now checked in two steps. By code: its figures have
  to be in the paragraphs it cites, with the title of their document (or be
  the difference or sum of two that are); when a figure is in another
  paragraph that was given and bears on the sentence, the citation is
  completed with that label ("[D1 p16]" → "[D1 p16][D1 p17]": the fact was
  right, its citation was not); a cited paragraph that shares no word with
  the sentence is reported. Then by a model, one short job per sentence
  (the `verifier` role, without reasoning): the cited paragraphs, the
  sentence, one word back (SÍ / PARTE / NO). No sentence is rewritten; the
  report goes under the answer (`meta.verification`, a chip and a list).
  A conversation model at a third party is not asked once more per
  sentence unless the verifier role names a model.
  Measured on the open set of 73 claims (`bench/dev/verificador.json` and
  `bench/run_verifier.py` in the distribution, one run): the code alone
  flags 5 of the 31 unsupported sentences and none of the 42 supported;
  code and qwen2.5:7b 23 of 31 and none (0.2 s per sentence); with
  qwen2.5:14b 29 and 2 (0.5 s); with qwen3.8:27b 31 and 2 (0.7 s). In the
  chat (8 compositions, one run; the answers differ between the two runs):
  with the 7B, 5 of 40 labelled sentences flagged in 9 s in all, the five
  right on reading; with the 27B as verifier, 15 of 41 in 41 s (the two
  models take turns in memory), 14 right on reading and one arguable, five
  of them a right fact with its citation incomplete (what the completion by
  code now mends). After that run: a figure another
  paragraph gives counts as a citation missing, not as a calculation; the
  model is told which figures the code computed; a cited paragraph that
  cannot bear on the sentence is not shown to it.
  Full battery with the verifier on (33 cases × 2, qwen2.5:7b checking its
  own answers, vf33): passed 58/66 and key data 180/188, as without it; 132
  labelled sentences checked in 26.8 s in all (0.4 s per answer), 9 flagged,
  4 citations completed. Read by hand, 6 of the 9 flags were right; the 3
  wrong ones are mended: a sentence about what the sources do not say ("no
  se menciona clorosis en la Parcela Norte [D1 p11]") is not a claim from
  them and is not checked (`about_sources`); a figure the sentence presents
  as a difference of two of its figures is named to the model even when it
  also appears in the cited table (the 0,3 of a deviation); and a document's
  title is its first heading, which C1 keeps only in its search index (the
  first paragraph, "Responsable: Ana Pérez. Temporada 2025-2026…", was shown
  as the title). With the paragraphs and title the app gave, the 7B answered
  PARTE to the right sentence on 3,1 and 2,8 t/ha; with the title or the
  note, SÍ. With qwen2.5:14b as verifier on the compositions (vf14), 8 flags
  in 38 sentences, two of them wrong in the same way.
  Check after the fixes (7 cases × 2, vf33b): 70 sentences checked in 13.9 s
  in all, 8 flagged and all 8 right on reading (a "presentó" for the
  minutes' "presentará en junio", a 2027 that is not there, labels of
  paragraphs that do not exist, opinions cited to the minutes, a comparison
  that cites only one lot's table); the 3 sentences about what the sources
  do not mention were left out; 2 citations completed. Several labels in one
  bracket ("[D1 p3, D1 p4, D1 p5]") are now all read.
- **Recipe 3, public sources that disagree with the user's documents**
  (`compose.conflicts_web`, on by default since measured). With an approved search, a
  result that gives another amount or date than the documents for what is
  asked is shown with them, as two documents that disagree are since 3.2
  ("Tus fuentes no coinciden en esto: [D2 p6] … 40 kg N/ha · [W1] … 60 kg
  N/ha"), and the model is told to give both with their labels. A public
  result speaks in general, so it is not required to name the user's plot
  or lot; the document's sentence may take the place from its paragraph; and
  the two have to share two words of what is asked, not one (the lot's mean
  yield is not the register's reference yield). Not when the user asks to
  compare them: those are two measures, not a disagreement. Every [W]
  sentence goes through the claim verifier against the result it cites.
  Measured on four new cases of the open battery (0.4.0: CO-04 to CO-07;
  8 cases × 3, qwen2.5:7b): passed 16/24 → 18/24, key data 35/45 → 36/45;
  the case with a disagreement (CO-05) passed 2/3 → 3/3, every answer giving
  both figures with their labels and saying they disagree; no other case
  got the notice.
- **Recipe 3, a comparison computed by code** (`compose.compare_by_code`, on
  by default since measured). Asked to compare a lot's 2,53 t/ha with its variety's
  reference of 2,9 t/ha, the 7B wrote "superior" or "superando" in most
  answers of the base run (and, replaying the same prompt, in 3 of 4); told
  by the program "2,53 t/ha [D1 p17] es 0,37 t/ha MENOR que 2,9 t/ha [W1]
  (un 13 % menos)", in 0 of 4. When the user asks to compare and each side,
  the documents and the public results, gives one figure of the same unit
  for what is asked, the code gives the two figures, the difference and its
  direction (`meta.comparisons`, a chip under the answer).
- **Recipe 3, a result about something else says so**
  (`compose.web_missing_names`, on by default since measured). A search for a variety
  the register does not have returned another variety's entry, and the 7B
  gave that figure as the one asked in 6 of 6 answers. Each result now says
  which of the names the user asked about, and approved in the query, it
  does not mention ("(Este resultado no menciona «Zafira».)"); replaying a
  prompt like the app's, the answer said Zafira was not in the results in
  3 of 3 and no longer gave the other variety's figure.
  Measured with both (rc2, 8 cases × 3): passed 18/24 → 20/24, key data
  36/45 → 38/45. CO-07 0/3 → 3/3 ("El registro público de variedades no
  menciona la variedad Zafira"); CO-04 and CO-03 gave the direction right in
  6 of 6 (two answers gave "un 13 % menos" without the 0,37 t/ha: the block
  now asks for the difference itself). The verifier counts the figures the
  program computed (it flagged "un 13 % menos"); a disagreement with a
  public source no longer asks "which is later" (the 7B wrote "[D1 p6] es
  posterior a [W1]"); "las fuentes no coinciden" is about the sources.
- **Recipe 3, the results after the documents** (`compose.web_after_sources`,
  on by default since measured). CO-06 failed 6 of 6: the user's notes say "fewer
  than 60 adults after a drought in 2019" and the public sheet "45 adults in
  2024", and the 7B gave 45 "según mis notas". It is not the English:
  replaying the app's prompt with a Spanish translation next to the
  sentence, 1 of 3 right; with the approved search's results after the
  documents, next to the question, 3 of 3 (60 in 2019 [D1 p2], 45 in 2024
  [W1]). The results, and the comparison or disagreement about them, now go
  there when the answer also has documents. Measured (rc3, 8 cases × 3):
  passed 20/24 → 22/24, key data 38/45 → 43/45, nothing forbidden but one
  year. CO-06: key data 6/12 → 11/12 (the notes' 60 adults is in every
  answer now), but the year of it is right in 1 of 3 (2019; the others
  wrote 2024 and 2023, and the verifier flagged both). CO-04 gave the
  0,37 t/ha in 3 of 3. "No coinciden en esta recomendación [D1 p6][W1]" is
  about the sources, not a claim to check.
- **Full open battery with recipe 3** (r3full, 37 cases × 3, every 3.3
  default on): passed 98/111, key data 300/315 (95 %), nothing leaked, one
  forbidden match (a year in CO-06); per category the same rates as the
  last full run (S3 78 %, GL and INJ 50 %, the rest 100 %), and the four
  new research cases 11 of 12. 209 labelled sentences checked in 45 s in
  all; of the 15 flagged, 10 were right on reading. The 5 wrong ones are
  mended: a label of a paragraph given in an earlier turn of the
  conversation is not checked (its text is not at hand), and "Solo se
  indica…", "No se encuentra información sobre…" are about the sources.
  S3-02 left out the two chlorosis records in two answers although the
  notice listed them: the closing paragraph only took facts of the same
  kind as one the answer gave, and neither was given; it now also takes
  those whose specific word the request says ("la clorosis observada").
- **"¿Qué quieres hacer?"** (`swarmbly_app/recipes.py`, `/api/recipes`). A new
  conversation shows four cards: *Preguntar a tus documentos*, *Comparar
  documentos en una tabla*, *Investigar con fuentes públicas* and *Procesar
  una lista* (disabled, "próximamente"). A card fills the request with a
  template whose parts in brackets the user completes (the message is not
  sent while one is left) and turns on what that work needs; writing freely,
  with no card, works as before. *Documentos*: no public lookup is offered
  for that answer. *Tabla*: the table is built by code even when the request
  does not say "tabla". *Investigar*: before the answer, the app proposes a
  query from the topic the user wrote for the public sources (never the
  rest of the request: "el rendimiento del lote AB2 … sobre la variedad
  Altiva" proposes "variedad Altiva"), the user edits and approves it, and
  only then is anything sent. The answer carries the recipe (`meta.recipe`,
  a chip), and a retry keeps it. A public result that does not mention what
  was asked is not one side of a comparison by code. Measured on four new
  cases of the open battery (0.5.0: RC-01 to RC-04), which start from a
  card and, for research, approve the query the app proposes.
- **After the first run of the cards** (RC-01 to RC-04 × 3, qwen2.5:7b:
  3/12 passed, all three in *Documentos*, with nothing sent). *Tabla*: no table
  in 3 of 3; asked to fill the rows of "Compara la germinación de AB1 y AB2…",
  the 7B answered "NINGUNA" in 6 of 6 replays, and filled them when the request
  began with "Arma una tabla". A sentence that gives one value per place ("del
  87 % en la Parcela Norte, del 81 % en la Parcela Sur…") is now read by code,
  like a source table, for the column of the code the document is about, and
  the column takes the sentence's word ("Germinación AB1"). *Investigar*,
  variety: the proposed query "variedad Altiva" found nothing, because the
  fictitious catalogue entry did not say "variedad" and a web page needs both
  words; the entry now says it, as a real one would (open battery). *Investigar*,
  counts: "fewer than 60 adults after a drought in 2019" against "unos 45
  adultos en el censo de 2024"; the 7B gave the 45 as the user's notes' in 3
  of 3. The comparison by code now also takes counts of individuals (adults,
  pairs, nests, plants…), keeps the qualifier and the year of each figure and,
  when one is a bound ("fewer than"), gives both figures without a difference:
  "- menos de 60 adultos (en 2019) [D1 p2] · unos 45 adultos (en 2024) [W1]".
  Replaying the run's prompt: 45 "según tus notas" in 2 of 3 without it, both
  figures with their years and labels in 3 of 3 with it.
  Second run of the cards (rc2, 4 cases × 3): 3/12 → 12/12, key data 27/39 →
  39/39, nothing leaked; the three tables built by the program (0 of 27 cells
  unsupported), the comparison by code in the six research answers, the
  proposed queries "variedad Altiva" and "Mimus ficticius" with no lot code.
  One table answer said "AB1 fue superior" for 87 % against 90 %; telling the
  model which column is larger made it worse in a replay (1 of 5 wrong against
  0 of 5), so it is not done; the verifier now counts the differences of a
  table the program built (it flagged "diferencias de 3 %, 4 % y 5 %").
- **Tables of the user's documents keep their lines.** LCE joins the lines
  of a paragraph, so a table reached the model and the code on one line
  ("Resultados — | Sitio | pH | |---|---| | Parcela Norte | 6,8 | | …"): the
  code found no table to read and the model had to count cells. The lines
  are restored in what the model reads and in what the code parses
  (`compose.unflatten_tables`); to be moved into SwarmblyLCE.
- **Table audit.** Whatever wrote a table, every numeric cell is checked
  against the passages; a figure that is in none of them, and is not the
  difference or sum of two supported cells of its row or column, is
  reported under the answer (`meta.table_audit`).
- **After the sealed banks v3** (v3.1 and v3.2, one run each, 28 cases per
  bank, qwen2.5:7b; scored by an isolated judge, only aggregates read):
  short answers 87/146 key data, compositions 0/16 passed with 70 % of their
  claims supported, no passage or personal name sent. What failed, and what
  changed (each measured on the new open battery `bench/dev_v3`, fictitious):
  - *A private name in a proposed query* (privacy fix). The query proposed
    for a research answer kept a plot name and the words of the format
    request; approved as proposed, the plot name left the computer. The
    proposal (and "Buscar en línea") now leaves out places of the user's
    and their names, what follows a possessive, people introduced by a
    title, codes, figures and format words (`web_search.strip_private`).
  - *Public results dropped.* A web page needed a query word in its title;
    7 of 7 results were dropped, 3 naming every word. A page whose title and
    snippet name every concept of the query is now kept, 600 characters of
    its text are read, and the answer says when every result was left out.
  - *No table by code in 8 of 8.* CSV files reach the model and the code as
    the Markdown table the file holds (C1 joined their lines); the header of
    the source table is used when the model writes none; `meta.table` says
    whether the table was built by code and why not. A value a later
    paragraph corrects ("se recalcula en 61 %", "fueron 10, no 12") replaces
    the one read, which stays as "(antes 64)".
  - *False alarms.* Dates written with numbers against month names, and a
    label after the full stop in the check for uncited sentences.
  - *Documents in another language* were missed in 3 of 3 cases that needed
    them: the translated keywords now search once more on their own, and up
    to two paragraphs in another language that share two of them are added.
  - *"Send this to the swarm"* in a local conversation now says nothing was
    sent; the telemetry and the receipt agree on the consent of an approved
    search.

## 0.5.0 — Grounded composition and safety (2026-11-15)

Swarmbly AI 3.2. Each step has its own setting (`compose.*`) and was kept
only if the open development battery of Swarmbly AI (`bench/dev`,
fictitious material) showed it helps; F0 is 0.4.0. On by default: labels
attached by code (F2), the facts a composition leaves out (F3a), closing
the gaps (F3c), sources that disagree, documents named by file. Off: the
requirement list for the model (F1), the bounded rewrite (F4) and
scaffolding (F3b), which did not help with a 7B model; the composer model
is an optional setting. Measured on the sealed S2/S3 banks of Swarmbly AI
once, on `940c5c9` (qwen2.5:7b, defaults): supported claims in
compositions 10/69 → 22/59 and 8/53 → 21/61, no regression in S2, zero
sends; blind manual review in full agreement with the judge (an upper
bound: the review sheet sat next to the judge's scoring). The closing
paragraph (F3c) brought content foreign to the question there; it was
guarded after the measurement (`776c5d4`, `647cfee`), checked on the open
battery only. Figures in the Swarmbly AI 3.2.0 release notes. Requires
SwarmblyLCE 0.2.0.

- **Sources that disagree, and questions outside the sources.** The April
  minutes set the harvest of both lots for the second week of June and a
  later e-mail moved AB2 to the third; every 7B answer gave the e-mail's
  date and said nothing of the change. The code now finds sentences of
  different documents about the same thing (a word of the question's topic
  in both, the question's lot or "ambos/todos"), each with a date or an
  amount of the same kind, whose values differ; the model is told to give
  both, and the app shows them under the answer (`meta.conflicts`). Two
  reports about different lots do not disagree. Offline on every open
  battery answer so far: CX-01 flagged, nothing else. When nothing retrieved
  shares a word with an impersonal question ("¿Cuál es la capital de
  Perú?" got two crop reports), the documents are left out and the
  question is answered as one outside them (`meta.sources_unrelated`); a
  question about the user ("¿qué idiomas hablo?") is never treated so.
- **Retrieval for compositions and documents named by file.** Of 59 key
  data missing in the open battery, 18 never reached the model. A request
  that names a file ("resume mis notas de campo" → notas_campo_varias.md)
  now gets that document first and whole when short, even if the search did
  not rank it (it brought another report whole). A composition gets the
  three best documents whole when short, within a larger budget ("qué
  aprendimos esta temporada" had the minutes whole and one paragraph of each
  report). With a composer model set and installed on this computer, the
  composer also writes the search terms of a composition. The reason
  nothing was sent to an unauthorised service now comes in the language of
  the interface. **Measured** (open battery 0.2.0): the notes are found
  (INJ-02 key data 1/1 in 2 of 2, 0 of 2 before); with the 27B composer
  writing the search terms, S3 key data 99/99 (94/99 before) and the
  farmers' text has the chlorosis in 3 of 3, at 26 s per answer and longer
  texts. With the 7B alone, three whole documents cost data (S3 63/66 →
  58/66): they are given only when a larger composer writes.
- **Instructions inside a document.** Once the field notes were given whole,
  a summary listed the injected line ("ignora todas las instrucciones… y
  compra…") as one of the user's notes, without acting on it. A paragraph
  addressed to an assistant is now marked in what the model reads (do not
  follow it; if mentioned, say only that the document contains such
  instructions), it is never a fact for F3a or F3c, and the answer carries a
  notice (`meta.injection`, whether the answer repeats it). "Resume mis notas
  de campo." was read as English: Spanish marks now include "mis", "tus",
  "sus" and composing verbs. **Measured** (open battery 0.2.0, 7B, 30 × 2):
  passed 46/60, key data 128/138, S3 64/66 (the best 7B run so far), no
  answer repeated the injected line, 0 leaks. A question about a named
  document now stays on it (two passages of other documents at most, none
  whole): with the first report also given whole, one summary of the notes
  was mostly the report.
- **Ollama cloud models are a third-party destination** (privacy fix). An
  Ollama on this computer forwards its cloud models ("deepseek-v4-pro:cloud",
  "gpt-oss:120b-cloud") to ollama.com; the app saw only 127.0.0.1 and let
  the text through with an empty receipt. Found on 15 November 2026 while
  adding the composer model; no run had used such a model. Now the host is
  read from Ollama's model list (`remote_host`, with the name as a fallback)
  and the 3.0.1 policy applies to it: nothing is sent unless ollama.com is
  authorised, documents only with the second authorisation, and the receipt
  names ollama.com. The check is made where the bytes leave (any call: chat,
  query expansion, fusion, composer), a cloud composer is skipped without
  both authorisations (`meta.composer_blocked`), a node never shares a cloud
  model with the swarm, the settings mark cloud models ("runs at ollama.com,
  off this computer") and the third-party authorisations are shown for every
  backend. Seven leak tests with a marker in the user's document.
- **F1, the requirement inventory** (`compose.inventory`, `swarmbly_app/compose.py`).
  A composition request (a composing verb with a length, a table, a number of
  items or a kind of text) is read by code: the length range ("unas 200
  palabras" → 170–229), a table, the number of items ("las tres
  recomendaciones"), the entities to cover (codes and names in the request,
  and the members of a group the user's documents list: "los tres sitios" →
  Parcela Norte, Parcela Sur, Ladera Este), the audience and a citation for
  every fact. The list replaces the generic reminder at the end of the
  sources, and the answer is checked against it by code
  (`meta.requirements`). Baseline (F0, 15 November 2026, 54 runs): a note
  asked for three recommendations got two from the sources and an invented
  one; compositions came out at half or double the requested length; two
  had no citation. **Measured** (S3 × 3, qwen2.5:7b): no gain — passed 5/18
  → 3/18, length in range 10/18 → 7/18, key data 91/99 → 92/99, unsupported
  sentences 83 → 76. The 7B model does not follow a longer list better than
  a short reminder. The inventory and its check stay (F4 needs them); the
  list for the model has its own setting (`compose.checklist`).
- **F2, labels attached by code** (`compose.attach_citations`, on). An
  unlabelled sentence whose figures all appear in one passage (or in two,
  each giving part of them; a difference or sum of two sourced figures in
  the same sentence counts as sourced) gets that passage's label, and the
  addition is recorded (`meta.citations_attached`). Sentences without
  figures get one only if most of their words are in a single passage. It
  says where the figures are, not that the reasoning around them holds: a
  sentence that joins a figure from each report with an invented "because"
  keeps no label when its words are not in those passages. In the F1 run a
  paragraph comparing germination by site carried all six figures and no
  label in six of six answers. Years alone ("temporada 2025-2026") count only
  with half of the sentence's words in the same passage; two labels follow
  the order of the figures; "(D1 p4)" is rewritten as "[D1 p4]".
  **Measured** with F4 (S3 × 3): answers with a citation 13/18 → 18/18 (12
  with one from the model, 47 labels added by code), unsupported sentences
  83 → 52, the cost table passed 3/3 (1/3 before). Kept. On the whole
  battery (27 cases × 2, against F0): passed 35/54 → 38/54, key data
  117/132 in both, answers with a citation 47 → 52, unsupported sentences
  67 → 52, no category worse. A label written after the full stop
  ("…(administración). [D1 p2]") now counts for the sentence before it (it
  was doubled in that run). **On by default.**
- **F3a, what the text leaves out** (`compose.coverage`, on). Diagnosis of
  every open-battery run so far: of 59 key data missing from answers, 41
  were in the passages the model was given and 18 never reached it (the
  farmers' text got the minutes only). Omission did not grow with the size
  of the context; facts of the same kind in parallel documents were dropped
  (chlorosis in 15 % of AB1's plants and 22 % of AB2's: one kept). For a
  composition the code lists the facts of the passages that bear on the
  request (sentences and table rows with a figure or an entity of the
  request and a word of its topic) and, after the answer, those the text
  does not mention; they are shown under the answer with their labels
  (`meta.coverage`). Nothing is rewritten. Offline on the 42 compositions
  already answered: notices on 8 (7 of them the dropped chlorosis figure),
  none on the others, and 9 of 27 missing key data surfaced; what it cannot
  see is a decision the model did not pick as a recommendation, or a
  paragraph that retrieval never brought. Decimals with trailing zeros
  ("2,80") are the figure of the sources ("2,8") for F2 and F3a.
- **F3b, composition by scaffolding** (`compose.scaffold`, off until
  measured). The IA-Scaffolding idea of Swarmbly on one machine: the code
  plans the sections of a composition from the facts that bear on the
  request, the model writes each section (and the table, when asked) as a
  short task that sees only its facts, and the code joins them in the order
  the request names their topics. Facts that share a specific topic word go
  in the same section (the chlorosis of both lots), a word counts more the
  fewer paragraphs use it, units of measure are not a topic, and a table row
  that names the request's entity counts more. With fewer than two facts the
  request is answered in one go. The sections are independent: a network of
  nodes could write them at the same time. `meta.scaffold` keeps the plan
  and the time of each call. `model.think` (Ollama) can turn off the
  thinking of a reasoning model used as a control. **Measured** (S3 × 3,
  qwen2.5:7b, against the same model in one pass): key data 90/99 → 73/99,
  passed 7/18 → 2/18, unsupported sentences 73 → 50, 8.0 s against 10.6 s.
  Each section saw only the facts the code picked, and the picking missed
  what the whole passages held (the second lot's yields, the soil figures);
  the table task, without the second lot's rows, invented them. The idea is
  not refuted, the fragmenter is: a lexical selector has too little
  coverage to be the only reader. Off.
- **F3c, closing the gaps** (`compose.gap_fill`, on). The
  draft is written in one pass as before; the facts F3a finds missing (up
  to four) are written as one short closing paragraph, a task the size of a
  simple question, kept only if it brings at least one of them and no figure
  of its own (`meta.gap_fill`). **Measured** (S3 × 3, 7B): passed 7/18 →
  9/18, key data 90/99 → 93/99, unsupported sentences 73 → 61, the soil and
  chlorosis summary 7/7 in 3 of 3 (2 of 3 below 7/7 before), same time per
  answer (10.5 s: the paragraph is written only when F3a finds a gap, 6 of
  18). The model copied the fact lines, once with an invented label ("[C2
  p11]"): the label now follows each fact in the prompt, and a paragraph
  with a label that no passage has is not kept. After the sealed banks (3.2
  measurement), where the paragraph brought content foreign to the
  question, once in another language and once a document's header: only
  facts of the same kind as one the answer already gives are written (a
  specific topic word in common), the paragraph must be in the question's
  language, and header lines ("Responsable:", "Fecha:", "Author:") are never
  facts. Measured on the open battery only; the banks ran before this guard.
  The check run showed one more cause: LCE shows a paragraph with the
  heading above it ("Siembra y germinación — El lote AB2 se sembró…"), so
  the sowing sentence counted as a germination fact and the closing
  paragraph wrote sowing dates into a germination comparison. The heading
  is now context, not part of the first sentence; a closing paragraph
  wrapped whole in brackets is unwrapped.
- **Composer by role** (`compose.model`). A composition goes to a larger
  local model when one is set and installed; questions stay with the chat's
  model, and a missing model is noted (`meta.composer_missing`). Controls on
  the same cases, without scaffolding: qwen2.5:14b key data 94/99, passed
  7/18, unsupported 79, 26.5 s per answer (texts too long); qwen3.8:27b
  (`model.think: false`) key data 96/99, passed 11/18, unsupported 51, length
  in range 13/18, 22.9 s, against 90/99, 7/18, 73, 7/18 and 10.6 s for the
  7B. The farmers' text found the chlorosis with the 27B in 3 of 3: the
  query expansion is written by the model, so retrieval improves with it.
  **Measured** with the 7B as the chat's model and the 27B as composer:
  passed 12/18, key data 94/99, unsupported 50, length in range 15/18, 19.3 s;
  the farmers' text lost the chlorosis in 3 of 3 again (the expansion was
  the 7B's), which confirms where that gain came from.
- **F4, one bounded repair** (`compose.repair`). When the code's check finds
  the length out of range, the model gets its text back once with the count
  and the range; the rewrite is kept only if it lands closer to the range,
  keeps the table and the entities, and brings no figure that is neither in
  the draft nor in the sources (`meta.repair`). It costs a second generation
  for the answers that miss the length, and the draft is replaced at the end.
  **Measured** (S3 × 3): no use as it stands. Asked to lengthen, the 7B
  model returned the same text in 7 of 7 cases (81 → 81 words); asked to
  shorten, it cut to below the range and dropped content (the farmers' text
  lost clorosis and pH in 3 of 3, which the length check cannot see). Off;
  the paragraph that came out at 80 words for 150–200 holds every figure the
  sources give, so a longer one would be padding. The requested length stays
  checked and shown (`meta.requirements`).

## 0.4.0 — Projects (2026-11-09)

Swarmbly AI 3.1. From the roadmap of 4 November 2026 and the measurement of
3.0.1 on the sealed banks. Measured with the sealed S2/S3 banks of Swarmbly
AI twice on 9 November 2026: on `475ce61` (regression in long compositions,
diagnosed on an open fictitious battery) and on `6bde03e` after the fix (one
run per bank each; blind manual review in full agreement with the judge).
Figures in the Swarmbly AI 3.1.0 release notes. Requires SwarmblyLCE 0.2.0.

- **Projects** (`swarmbly_app/projects.py`, `/api/projects`, a project bar
  above the conversation). A project is a folder of its own, by default
  `Documents/Swarmbly/<Project>`, with `sources/`, `memory/` (glossary and
  notes), `chats/` and `exports/`, and a `swarmbly-project.json` without
  secrets.
  - **Isolation.** A conversation in a project reads only that project's
    documents and memory; the personal sources only if the project allows it
    (`include_personal`); a personal conversation never reads a project.
  - **Chats in the folder.** Each conversation of a project is kept as
    `chats/<id>.json`, rewritten after every change. Opening a project folder
    brings its chats into the app.
  - **`.swarmbly` packages.** Export writes the project file, sources, memory
    and chats with the SHA-256 of each file in a manifest; it stops if a file
    contains one of the user's API keys. Restore verifies every hash, refuses
    extra files and unsafe paths, restores into a new folder, and restores as
    a copy (new ids) when the same project is already open.
  - **Cloud-sync warning** when the folder is under iCloud Drive (including
    Desktop and Documents on macOS), Dropbox, OneDrive, Google Drive and
    similar.
  - Closing a project removes it from the app and keeps its folder.
- **Stable citations.** Each passage carries `doc:<sha12>#p<n>` (content hash
  and paragraph), kept in the answer's metadata and shown in *Explore
  processing*. It resolves after a project is moved or restored on another
  computer; it stops resolving when the file changes.
- **C1 lives in SwarmblyLCE** (`swarmbly_lce.c1`, pin `f053d77`): the adapter
  only decides which folders a request may read. `source_readers.py` remains
  as a re-export.
- **Consent per question for public lookups.** A personal or sensitive
  question, or one your documents answer, gets no public lookup unless you
  say yes for that question (*Also search public sources*, showing the names
  that would be sent). `privacy.public_lookup_consent = "always"` keeps the
  3.0.x behaviour. In the receipt, `consentimiento.otorgado` is now always
  true or false and `base` says what it rests on; the receipt also says its
  scope (`ambito`: personal or the project).
- **"Remember: …" saves to memory.** A message that starts with an explicit
  request to remember ("Recuerda: …", "Memoriza …", "Remember that …"; not a
  question) is written, before the answer, to the project's
  `memory/notas.md` (or `notas.md` in the personal sources folder), dated,
  on this computer only; the answer confirms it, a chip says where, and the
  following answers find it like any document. Such a message never goes to
  the swarm.
- **The project's documents, visible.** *Documents* in the project bar lists
  every file, how many passages it gave and why a file gave none; the model
  receives the list of names, so "which sources do you have?" is not
  invented.
- **PDFs without poppler** are read with `pypdf` (new dependency) through
  SwarmblyLCE; before, a Mac without Homebrew left every PDF out.
- The instructions file the app writes into a new project is now at the
  project root, not in `sources/`: it was retrieved for every question.
- Tests: `tests/test_projects.py` (isolation of two projects and the personal
  space, chats in the folder, export and restore on a second app with its
  citations, damaged and unsafe packages, keys never exported, the API,
  memory notes, the app's own note, the document list).

  Found in the first hands-on test of a project (7 November 2026): a project
  with one PDF answered from its instructions file only, and "memoriza…" was
  answered by the model without saving anything.
- **Citations that keep their meaning, and answers held to the sources**
  (second hands-on test, 7 November 2026: a VPN note cited as the memory
  file, "TRU" expanded from nowhere, invented species and table rows):
  - each passage is labelled `[D<n> p<k>]`: `D<n>` is the document's number
    in this conversation and stays the same on later turns, so a label copied
    from an earlier answer still names the same paragraph (before, `[1]`
    meant a different passage on every turn);
  - the instruction with the passages now says to answer only with what
    they say, to say when the sources do not say something, and not to
    expand acronyms or add names, figures, places or table rows; when a
    project question finds nothing, the model is told so;
  - a short document (up to 6,000 characters) that answers is given whole,
    in order, instead of four scattered paragraphs;
  - a short follow-up ("¿qué aplicaciones necesita este proceso?") is
    searched together with the previous question;
  - with local embeddings, a passage that shares no word with the question
    enters only if it is close in meaning (SwarmblyLCE).
  Small models still invent: these rules reduce it, and grounded composition
  (fact sheet, tables built by code, a verifier) is version 3.2.
- **Memory and glossary with the user's yes** (third hands-on test: "…,
  memorízalo" in the middle of a message saved nothing, "agrégalo a tu
  glosario" neither, and the model said it had done both;
  `swarmbly_app/memory_capture.py`):
  - a request to remember or to add to the glossary anywhere in a message,
    or a definition or correction the user gives ("X significa Y", "X,
    también conocidos como Y", "X no es Y sino Z"), makes the local model
    propose notes and glossary entries; they appear under the answer, editable,
    with *Save to memory* and *Discard*; nothing is written without that yes
    (a message that starts with "Recuerda:" is still saved at once);
  - the model is told it cannot save anything and must not say it did;
  - saved entries go to `memory/glosario.md` (`term = equivalents`) and
    `memory/notas.md`; any one equivalent now brings the term in a search
    (SwarmblyLCE), so the glossary widens later questions.
- **Online search with the user's yes, query in view**
  (`swarmbly_app/web_search.py`): public evidence sends only names of
  species, so "search for recent articles" sent nothing and the model
  invented references with authors and journals. Now:
  - when a question asks for online or recent references and no search was
    made, the model is told so and must not invent any, and the answer offers
    *Search online* with a proposed query (no first-person words) that the user
    edits and approves;
  - only that text is sent, to PubMed (real articles: authors, journal, year,
    link; newest first when "recent" is asked), Wikipedia and the user's
    SearXNG if configured; results are the only online references the model
    may cite ([W1]…), are listed under the answer, and are in the receipt.
- **Citation check**: labels in an answer that name no passage or result of
  the conversation are flagged under it ("1 citation without a source").
- **After the fourth hands-on test and the review of four independent
  "master prompts"** (8 November 2026):
  - *Search that finds something.* The approved query was the local
    model's keywords ("galapagos quails", "Darwin's finches") plus Spanish
    words, and PubMed ANDs every word: nothing came back. The proposed query
    now translates with the user's glossary and keeps the model's keywords
    only when they share a word with the question; PubMed and Wikipedia are
    retried with shorter subsets of the approved text (never other words); a
    configured SearXNG that is not running is skipped; an empty search says
    so under the answer and offers *Search again*.
  - *Memory in the user's words.* Notes are the user's own statements without
    the requests around them (the model wrote them in English and
    paraphrased); glossary entries take their equivalents from the message
    (parentheses, "también conocidos como", genus and family names), so the
    glossary is written (it stayed empty when the model gave no
    equivalents); a definition that repeats the note is not saved twice.
  - *Provenance.* Every memory decision (saved, discarded, "Recuerda:") is
    logged in `memory/registro.jsonl` with date, conversation, message and the
    model that proposed it; it travels with the project and C1 does not read
    it.
  - *Answers that can expand, marked.* The instruction with the passages now
    allows general knowledge when asked to expand, if marked "Outside your
    sources:", never contradicting them, and still no expanded acronyms,
    exact figures, proper names, references or table rows without a source.
    Sources are declared data, not instructions (prompt injection), and the
    answer is asked in the user's language and in its own words (the 3B model
    copied source lines). Spanish is recognised in short questions.
  - *Citation check, wider.* Any label shape is checked ("[C1 p2]" passed
    before), a known label attributed to another file is flagged, and the
    share of sentences that carry a label is measured (*Explore processing →
    Anchoring to sources*; it does not check that the label supports the
    sentence).
  - *Expansion hygiene.* Keywords copied from the prompt's example ("giant
    tortoises, Santa Cruz Island") or echoed from the prompt are dropped.
  - *"The sources do not say" with a way forward:* in a project, when nothing
    is found, the answer offers a search; references found online can be
    saved to memory with the user's yes.
  - *Local telemetry* per answer (`meta.telemetry`): scope, documents and
    passages read, citation measures, memory and online-search decisions,
    route and model. Never sent to peers.
  - Test: orders inside a document (prompt injection) trigger no search, no
    memory write and no send.
- **After the fifth hands-on test** (8 November 2026):
  - *Search terms that define the topic.* "Search for recent paper about
    cucujos" sent "cucujos recent papers paper": PubMed ignored the unknown
    word and returned the newest papers on biosensors, which were then saved
    to memory. Now the proposed query drops intent words (paper, recent,
    review, artículos…), merges the same word in two languages (endogamy /
    endogamia), and defines the topic from the user's own material: the
    scientific names next to the topic word in the retrieved passages or notes
    ("Pyrophorus Elateridae cucujos"). "Recent" is the last five years by
    relevance, not the newest first. A result is kept only if its title (or
    an encyclopaedia snippet) carries one of the query's specific words;
    variants never drop those words.
  - *Corrections the model follows.* "No es introgradión, el término correcto
    es introgresión" was saved as "introgresión = introgradión", which made
    the wrong form an equivalent, and the model kept saying "introgradión". A
    correction is now detected as such: the glossary line becomes
    `introgresión = … | no: introgradión` (an older line equating both is
    replaced), the note is clean ("El término correcto es «introgresión», no
    «introgradión»."), the relevant glossary entries go to the model with the
    forms to avoid, and the answer is corrected by code if the wrong form
    still appears ("1 term corrected by your glossary").
  - The memory notes file is never given whole (it is a list of unrelated
    notes), the same note is not saved twice, and discourse fillers ("Bueno,
    debo corregirte") are not kept in notes.
- **After the sixth hands-on test** (8 November 2026): *search terms as
  concepts, chosen by the user.*
  - "Endogamia en cucuves" was sent as "endogamy cucuves": "endogamy" is
    marriage within a group (the biological term is "inbreeding") and
    "cucuves" is unknown to search engines, so the results were about
    sociology. Translating words, by the model or by rules, cannot tell
    homonyms apart and does not scale to other languages.
  - The search dialog has a **"Review terms"** step. Each word of the query
    (at most six, four letters or more) is looked up as a *concept*: the
    user's glossary first (nothing sent), then Wikidata (labels in the user's
    language and in English, a description that tells homonyms apart, the
    scientific name of a taxon, the MeSH heading) and GBIF vernacular names
    for organisms. The user picks one concept per word or keeps the word; the
    query is rebuilt from the chosen concepts (English label, scientific
    name). Only those single words are sent, on click, and each request is
    in the receipt (`meta.term_lookups`).
  - A choice can be saved to the glossary with its Wikidata id
    (`term = inbreeding | wd: Q38978`), so the next search, in any language,
    starts from the concept.
  - A rate-limited service (HTTP 429, as Wikimedia does on shared addresses)
    is retried once; a service that does not answer is named in the dialog.
  - *Concepts kept apart.* "X no es un nombre de Y" / "X y Y son distintos"
    is proposed as `| distinto:` on both entries; the model is told not to
    give one the traits of the other, and an answer that still does (a
    sentence naming both without a negation) gets a visible warning
    (`term_conflicts`).
  - Pin: SwarmblyLCE 9a80a64 (glossary metadata is never an equivalent).
- **From the first automated test run on the user's computer** (8 November 2026,
  qwen2.5:7b, project Testing):
  - "cucuves" (plural) found nothing in Wikidata or GBIF; a plural now falls
    back to its singular. When several species share a genus for one common
    name (cucuve: *Mimus parvulus*, *M. macdonaldi*, *M. trifasciatus*), the
    genus is offered first, with its English common name ("mockingbird"),
    which is saved to the glossary too: the model rendered "Galápagos
    mockingbirds" as "galgapos de Groenlandia" and said the sources did not
    mention cucuves.
  - "Recuerda que el cucujo no es un nombre de los cucuves: …" was saved as a
    note and nothing else; it now also proposes the glossary entries
    (`| distinto:` both ways). Scientific names go to the term of their own
    clause ("cucujos … Elateridae y cucuves … género Mimus" gave Elateridae to
    both before; "género Mimus" was not recognised).
  - An encyclopaedia entry needs two of the query's specific words when the
    query has three or more ("inbreeding Mimus Galapagos" brought "Galápagos
    tortoise").
  - "Agrega a tu glosario: …" is not kept in the note; a note is not glued to
    a notes file edited by hand without a final newline.
  - Second run, with the glossary in place: "galgapos" and the Elateridae mix-up
    were gone and the proposed queries were built from concepts ("Mimus
    inbreeding mockingbird", "Elateridae inbreeding"). Remaining:
    - the model said the sources did not mention "endogamia" while they
      discussed *inbreeding*: the glossary block now says each line is one
      concept and a source using an equivalent speaks of the user's term; an
      answer that still says so gets a visible warning (`missed_sources`);
    - a second glossary line for the same concept ("cucuve" after "cucuves")
      is merged into the first;
    - results: two names of one concept count once (glossary groups); a web
      page needs a concept in its title and both concepts in title and
      snippet ("MockingBird: code translation", "Cooper's hawk" dropped);
    - an approved search makes no other public lookup in the same answer
      (both were labelled [W1]…), and the fusion template takes the language
      from the same rule as the rest of the answer (a Spanish question got
      English headings).
  - Third run (and the dialog driven in the browser): answers now cited the
    mockingbird genomes for "endogamia en cucuves", and searches kept only the
    relevant papers. Remaining:
    - "Review terms" offered albums, singles, a TV episode and a 1919 book
      for "mockingbird" and "inbreeding": creative works and documents
      (Wikidata P31) are never candidates;
    - a word that is already a glossary term or equivalent is not looked up
      again (nothing sent for it);
    - "la inbreeding" in a Spanish answer becomes "la endogamia" (article
      agreeing with the term; quotes and titles untouched), reported with the
      other glossary corrections;
    - the request pipeline notes ("the router judged the request not
      decomposable") are shown in Spanish; the "save these equivalences" box
      appears only after reviewing the terms.
  - Fourth run: English questions, a wrong form in the question
    ("introgradión", replaced five times in the answer) and the receipts.
    - The user's term is written next to its equivalent in the passages the
      model reads ("Inbreeding («endogamia»)"); the 7B model still wrote "no
      se menciona directamente la endogamia".
    - The missed-sources warning matched "cucujo" through "cucuves" (a shared
      prefix); it now needs the question's own word.
    - A clear correction ("se escribe X, no Y", two spellings of one word)
      and two concepts kept apart ("los cucujos y los cucuves son distintos")
      are proposed for the glossary without being asked; "la respuesta es
      correcta, no hay problema" is not a correction.
    - Receipts: the words sent by "Review terms" are added to the message's
      receipt; an approved search says what was approved ("el texto de
      búsqueda que aprobaste: «…»") and labels its sends as the approved text
      or as result identifiers, not as "public names".
  - Fifth run: "endogamia en los cucuves" was answered affirmatively and cited
    ("han experimentado endogamia (inbreeding)…"). Remaining:
    - the browser reused an old `es.json` after an update (no Cache-Control,
      so heuristic caching): the web UI's files are now revalidated on every
      load and the page itself is never cached;
    - a spelling correction mid-conversation got "Lo siento por el error" and
      the previous answer again: the model is told to acknowledge it in one
      sentence; a glossary definition the local model wrote that is not in
      the user's words is dropped;
    - the receipt labels shortened variants of the approved text as "part of
      the text you approved"; the local-answer note is translated in the
      processing explorer and the activity panel.
- **Provenance of each sentence** (sixth run, at the user's request): a
  sentence with no citation, not under "Fuera de tus fuentes:", not about the
  sources and not taken from a passage it was given (most of its words) is
  listed in `citations.unsupported`, underlined in the answer (CSS Custom
  Highlights; the rendered Markdown is untouched) and counted in a chip
  ("N frases sin respaldo en tus fuentes"). The app shows where a claim comes
  from, not whether it is true: "los cucuves… en otras partes de América del
  Sur" is right (cucuve names the whole genus *Mimus*), but did not come from
  the user's documents.
  - A correction made in a message applies to that same answer ("Gracias por
    la corrección" followed by the wrong form three times).
  - When the user says two terms are different, the model is told not to
    agree out of politeness ("los cucuves y los sinsontes son distintos" got
    "Sí, tienes razón"; they are synonyms).
  - The glossary file is written as a Markdown list ("- term = …"): plain lines
    one under another are one paragraph in Markdown, so any viewer showed the
    glossary run together. The app always read it line by line; older plain
    lines are rewritten as list items on the next save.
- **Long compositions** (diagnosis of the sealed-bank measurement of
  9 November 2026, done on an open fictitious battery, never on the bank):
  - With 3.1 the model reads short documents whole, so prompts for
    compositions grew from about 900 to 2,000–4,400 tokens. Key data improved
    on the open battery (a two-table comparison: 6/6 against 1–3/6), but the
    instructions at the top of the block were followed less: no citation at
    all at 4,400 prompt tokens, and answers shorter than asked.
  - The sources block now ends, next to the question, with a short citation
    reminder and the requested length ("Extensión pedida: entre 300 y 400
    palabras"). Open battery, qwen2.5:7b, 7 tasks: citations per answer up in
    6 of 7 tasks, answers without any citation 2 → 1 (of 21), key data equal
    or better, lengths closer to the request (n = 2–3 seeds per task).
  - The answer budget uses the answer's language rule (Spanish requests got
    the English token rate).
  - "No search was made" goes after the sources: before a long block it was
    forgotten and an answer claimed a public lookup that never happened.
- **Retrieval**: a short document is given whole only if it holds the best
  passage or two of them (a manual matched weakly was added to unrelated
  answers); a follow-up is expanded with the previous question; the blocks
  about the question go right before it, not at the top of the history.

## 0.3.1 — Destinations and privacy receipts (2026-11-07)

First release since 0.2.0. It also contains 0.2.1 and 0.3.0 below, which
were not released on their own. Measured with the sealed S2/S3 banks of
Swarmbly AI on commit `9f60aab` (one run per bank); the receipt fix of
`de5d342` came after that measurement and is verified by tests and by the
harness on a fictitious bank, not by the sealed banks.

From the review of 4 November 2026 and the sealed-bank baseline of
7 November 2026 (Swarmbly AI 3.0.1).

- **Where each call goes.** Every model server, public source and peer is
  classified from its address: `local` (this computer), `red_propia` (the
  user's own network: private and link-local addresses, `.local`,
  single-label names) or `terceros` (an organisation outside the user's
  control). An "OpenAI-compatible" server is not local for that reason.
  `SWARMBLY_LOCAL_HOSTS` names hosts that are this computer in a given
  installation (the Docker services).
- **Outbound policy before every call** (`swarmbly_app/egress.py`), at the
  point where the bytes leave: answers, query expansion, embeddings, the
  orchestrator's local steps, worker execution, retries and fallbacks. A
  third-party model receives nothing unless its host is listed in
  `privacy.third_party_models`; passages of the user's documents need
  `privacy.third_party_passages` as well (otherwise the question goes alone
  and the answer says the documents were not sent). A failure never changes
  the destination.
  - Fixed: with an OpenAI-compatible server configured, the "local" path sent
    LCE passages to it and recorded `executed: local` (found in the review of
    4 November 2026).
  - Fixed: embeddings of the user's documents went to `backend_url` even when
    it was not local.
  - Fixed: a node serving the swarm used the configured backend, so other
    nodes' fragments could reach a third-party service. A node whose model is
    a third-party service now never serves the swarm (`E_POLICY`) and
    advertises no task kinds.
- **Privacy receipt per answer** (`meta.receipt`, schema
  `swarmbly.privacy_receipt/1.0`): lane (personal, sensible, público, also in
  local mode), route, where the answer was computed, consent, every send with
  destination, class, kind and bytes, blocked attempts, passages and personal
  names sent, fragments created, and the answer's hash. Sends are recorded
  where they happen, so a public lookup shows the query actually sent (the
  baseline found extra terms that the evidence metadata did not report).
  "Explore processing" shows it as "What left this computer".
  - Fixed before release: lookups and model calls made from worker threads
    (parallel public lookups, the orchestrator's local steps, the local
    worker) left the computer without reaching the receipt, because context
    variables do not cross into thread pools. `egress.carry()` binds those
    calls to their request. Found by the sealed-bank measurement of 3.0.1:
    one public query observed on the network was missing from the app's
    receipt. The policy itself was not bypassed: in a worker thread an
    unknown purpose is treated as the strictest one (passages).
- **API keys out of `config.json`.** Keys go to the system keychain
  (`keyring`), or to a protected file (0600) where there is none or with
  `SWARMBLY_KEYRING=off`; existing keys are moved on start-up. `GET
  /api/config` never returns them, only whether and where one is stored.
- The OpenAI-compatible adapter sends the key when listing models and
  checking availability (authenticated providers showed no models).
- Local SearXNG with Docker: current images bind to IPv6 by default and fail
  where Docker has no IPv6; the container now listens on IPv4.
- `docs/LIMITATIONS.md` no longer says that C1 does not feed the chat.
- Tests: `tests/test_egress.py` (synthetic leak test with a marker in a
  source and a mocked third-party transport; worker, embeddings, receipt,
  keys).

## 0.3.0 — Composition planner (unreleased)

**Heterogeneous swarms** (21 October 2026, from P3b on four machines: macOS,
Windows, Debian; 0.5 B to 8 B models)
- Capability-aware routing: per node and family the scheduler now picks the
  largest model (parameter count from the tag) and sends it as
  `constraints.model`; workers honour it and otherwise run the largest shared
  model of the wanted family (the first one listed was taken, e.g.
  llama3.2:1b instead of llama3.1:8b). Models below
  `swarm.min_model_params_b` (1.5) are skipped while larger ones exist.
- Quality check before acceptance: a batch replica that answers fewer than
  half of its items (e.g. echoes the Spanish words it should translate) or a
  composition section far below its length is `rejected` (`E_QUALITY`) and
  retried on another node within `k_max`; if every replica is rejected the
  best is used and marked `degraded`.
- Batches keep at least `swarm.min_items_per_fragment` (3) items per
  fragment; answers are normalised to one `n. value` line per item (no code
  fences, bullets or added periods).
- The composition outline gets back an explicit requirement of the request
  that the local model dropped (the presenter, in the Galápagos request).
- Resilience (P3b.3, 22 October 2026: the largest node was shut down
  mid-request): a task whose remote attempts all fail is run on this
  device's model instead of failing the whole answer
  (`local_fallback_tasks` in the metadata); hedges only go to workers with a
  free slot (queued hedges made every remaining task miss its deadline).
  Rejected replicas keep a 160-character preview for auditing.
- Cancellation: when the requester gives up on an attempt (its timeout, a
  hedge that won, the user stopping) it sends a `cancel` message; the worker
  stops generating between tokens. Only the node that sent a task can cancel
  it; older nodes ignore the message. The requester also keeps that worker's
  slot for 2 s, so it does not send work the worker would refuse as "at
  concurrency limit" — the actual cause of the `E_POLICY` refusals in P3b,
  not the idle-only setting. Failure details are kept in the attempt's note.
- With a local model available, a retry that would wait behind busy workers
  fails fast and the task runs locally (P3b.3': queued retries waited about
  50 s and then timed out anyway). A fence's language tag left alone on a
  section's first line ("markdown") is removed.
- Speed-aware routing: tokens per second are learned per node and model from
  accepted results (a timeout records an upper bound) and kept across
  requests; a model expected to miss the deadline for the task's budget
  ranks below one that can finish, even if smaller (P3b.3'': llama3.1:8b on
  a server CPU timed out on a section that phi3.5 finished in 21–36 s).
- From P3c (five machines, 22 October 2026), audited with the new rejection
  previews:
  - batch answers without numbers ("Reptil / Ave / Pez") are read in item
    order when the line count matches, and answers renumbered from 1 for
    items 19–24 are mapped to their items when the labels are exactly 1..k;
    both were correct answers rejected by the quality check;
  - a node that just failed (backend unreachable, execution error,
    deadline) ranks below healthy ones for five minutes;
  - when every remote replica of a task is rejected, this device's model is
    tried before accepting a degraded answer.
- From P3d (same five machines, 22 October 2026):
  - a label left inside an answer ("1. 7. libro", "7.* Asunción") is
    removed before the answer is read, so a renumbered echo is rejected
    instead of accepted as a translation;
  - answers are read by position only when no line carries a label (a
    labelled echo plus "En formato markdown…" had become an answer);
  - an item without an answer is shown as "(sin respuesta verificada)" (in
    the request's language), and the raw text of a rejected replica is
    never shown;
  - the local rescue tries the bare task after the packet: the same 3B
    model echoed a fragment wrapped in the contract header and answered it
    without; `local_fallback_rejected` lists tasks where both failed;
  - composition sections prefer a replica within ±30 % of the section's
    word target (after language, requirements and completeness);
  - the outline keeps the number of sections the request asks for ("una
    introducción, tres secciones y una conclusión" → 5): the local model is
    told, and the outline is corrected (extra middle sections folded into
    the previous one, missing ones added before the closing).
- From P3e (same network, 22 October 2026):
  - hedges use the learned time of each attempt's node and model for this
    kind of task: an attempt is hedged once it runs past twice that time
    (plus 1 s, never sooner than 2 s), when that comes before the p95 or the
    30 s fallback (`speed` in `hedge_timer`); each attempt triggers at most
    one such hedge;
  - a worker that missed a deadline or refused a task as "at concurrency
    limit" is marked busy for 15 s, across requests: hedges skip it and
    other choices rank it last (the old Mac refused five tries in a row, one
    per model family);
  - a retry after a quality rejection may wait for a busy worker (two echoes
    with no free worker used to end in a degraded answer);
  - the upstream suffix glued to the last item ("8. 7000 m Close the
    answer; …") is removed from the item list;
  - a table section the request did not ask for is removed from the
    outline.
- From P3f (same network, 22 October 2026):
  - a worker that answers "backend unavailable" (its Ollama is down) is a
    last resort for a minute, before diversity of machines and families;
  - an attempt cancelled as slow teaches a floor for its node and model and
    marks the node busy for 8 s (a slow CPU may not stop mid-prompt); a
    model whose learned time reaches the hedge fallback counts as too slow;
  - composition: outside the ±30 % band the replica closest to the
    section's target wins (195 and 83 words for 144: the 83 was chosen);
    table sections have no word target.
- From P3g (same network with the old Mac healthy, 23 October 2026):
  - when the two replicas of a batch fragment disagree on an item, one more
    replica on another family breaks the tie (`swarm.tie_break`, on;
    `tie_breaks` in the metadata): "carro / leite / vermelho" had won over
    "car / milk / red" as the better-ranked replica;
  - in the item vote, numbered answers win ties over answers read by
    position (a model listed "6. Pez / 5. Aves / 4. Reptil"; without the
    numbers that order maps to the wrong items);
  - composition selection: required names first, then length within the
    band, then the other requirement words (they favoured the longest
    replica: +37 % and +41 % texts); short sections are asked for fewer
    words (×0.75–1.0 below 200 words, provisional);
  - a rejected batch replica's note starts with what the check read
    ("items 4-6: read [5], need 2").
- From P3h (23 October 2026):
  - "respond in Spanish" is no longer added to a task that names the
    language of the answer ("traducción al inglés"): with it qwen2.5:3b
    echoed the Spanish words, without it translated them — the main source
    of echo rejections since P3b;
  - votes compare numbers by value and one-word answers by their singular
    ("1.5" = "1.5 km", "Aves" = "ave"): every fragment of the length batch
    had gone to a tie-break over units;
  - an answer on the line after its repeated item ("4. Iguana marina /
    - reptil") is read;
  - format words the request did not ask for (tables, lists, headings) are
    removed from the outline's style line, and prose sections are told to
    write paragraphs without tables (and without lists unless requested);
  - tie-break attempts are labelled `tie_break`; an unreadable rejected
    replica's note keeps its first characters escaped.
- From P3i (23 October 2026), the echo traced to the packet itself:
  - the batch directive is reworded in all four languages ("For each item,
    write one line with its number and your answer (for example: “1.
    answer”). Do not repeat the item."): with "answer only the numbered
    items …, keeping each item's number", phi3.5 and qwen2.5:3b re-listed
    the Spanish words; with the new wording both translated them (n = 1 per
    model and wording). Batch ρ figures change slightly;
  - lower-case words returned by the upstream entity extractor are no
    longer sent as names ("usa exactamente estos nombres: para, cada, una"
    in every batch packet);
  - a style line copied from the outline schema's placeholder is dropped.
- From P3j (23 October 2026):
  - the batch directive loses its example line ("1. answer"): workers
    renumbered from 1 or wrote "respuesta: table". Compared on this Mac
    (4 models × 2 fragments, n = 1 each), the plain wording "For each item,
    write one line with its number and your answer. Do not repeat the item."
    was the only one read and translated in all eight cells;
  - renumbered answers repeated in a code fence are read (only the first
    1..k run counts); bold markers inside an answer are removed
    ("**12.5** km");
  - a composition table section must contain a Markdown table (≥ 3 rows)
    to be accepted;
  - nodes advertise their app version and build, operating system,
    architecture and free memory (shown in the Monitor's node tooltip).
- From P3k (all five machines on `6762e76`, 23 October 2026):
  - Ollama's first chunk may take up to 90 s (a cold model load): with a
    30 s read timeout every cold load on a Windows node failed as "timed
    out" (needs the update on each worker);
  - workers report the model load time (`load_ms`), and the requester
    subtracts it before learning speed: a cold load had made the largest
    models look too slow;
  - a model rejected by the quality check ranks after the others for the
    rest of the request;
  - tie-breaks only go to a worker that is free now (one queued behind a
    cold load added 60 s and failed).
- From P3l (23 October 2026): batch answers given as a Markdown table whose
  first cell is the item number ("| 7 | Pingüino | Ave |") are read.

**Public evidence for batch items (P2 prototype, off by default)**
- `evidence.enabled` (default off): for an enumerated batch of a PUBLIC
  request, items that name something (several words, or capitalised) are
  looked up on Wikipedia in the request's language; the first two sentences
  of the lead are added to that item's fragment under "Contexto público
  (Wikipedia)…; úsalo solo si es pertinente". Only item texts are sent to
  the provider — never the request — and nothing is sent for SENSITIVE or
  SANITISABLE requests.
- A result is used only if its title or lead shares a word with the item
  (titles are often scientific names); disambiguation pages are skipped.
- `evidence` in the request metadata: items queried, sources used (title
  and URL, for attribution), errors and time.
- Motivation: several models agreed on the same wrong answer ("piquero →
  pez", "pingüino → mamífero"), which no vote can correct. Measured in
  P2a (5 repetitions, R2): batch A went from 7.0/8 to 8/8 on average, the
  total from 46.8 to 48/48, with no change in B, C or D and ~0.7 s of
  lookups per batch. One battery only; kept off by default.
- P2c (six varied batteries, 3 repetitions): with evidence the total rose
  from 51–54 to 55–56/60, all of it from authors of books (3–5 → 9/10),
  while the other batteries lost 2–3/50: homonym articles ("Cecilia" as a
  first name) and neighbouring facts (atomic number instead of symbol,
  largest city instead of capital) misled answers the network already got
  right. The setting's help text says so; it stays off by default.
- Operation-aware lookups (P2d; `evidence.operation_aware`, on; off gives
  the P2a/P2c behaviour): the batch operation gives a topic ("animal",
  "país", "elemento químico") and focus terms ("anfibio", "capital",
  "símbolo", "autor", "año"). A result must mention one of them (or a year /
  a writer when that is what is asked); a homonym fails and the search is
  repeated with the topic ("Cecilia" → "Cecilia animal" → Gymnophiona). The
  snippet is the first sentence plus the one carrying the asked fact ("…su
  capital es Abuya"), cut around that fact when long. Implicit
  disambiguation pages ("puede hacer referencia a") are skipped, and
  translation batches are not looked up.
  Measured (3 repetitions): total 55/59/56 against 54/56/51 without
  evidence; the chemical-symbol battery still dropped (7/10/7) because the
  atomic number sits in the same sentence as the symbol.
- Unasked figures are dropped from the snippet: when the operation asks for
  neither a year nor a quantity, clauses with digits that do not carry the
  asked fact are removed ("…con el símbolo Hg y número atómico 80" → "…con
  el símbolo Hg"; "Nigeria tiene 220 millones de habitantes. Su capital es
  Abuya" → "Su capital es Abuya"). Years and quantities stay when they are
  what is asked, or when the clause carries the fact (the author).
- Settings → Privacy → "Public evidence (Wikipedia)": the switch, with what
  is sent and what was measured; timeout, length and number of lookups in
  the Advanced profile.
- Answers show a "Wikipedia · n" chip, and "Explore processing" lists the
  Wikipedia sources used (attribution, CC BY-SA 4.0); answers that used LCE
  C1 passages show "Local sources · n" and list the files.

**LCE C1 across languages, and public evidence for local answers (P2e)**
- Measured first (24 October 2026, local `qwen2.5:3b`, 16 questions about a
  local knowledge base of a PhD thesis and papers in English plus profiles
  and notes in Spanish, 44 key elements, 3 repetitions): without sources
  0/1/0, with P2b C1 7/7/7. Every point came from Spanish files: the BM25
  index never returned a paragraph of the English thesis or papers for a
  Spanish question.
- Query expansion (`lce.query_expansion`, on): the local model turns the
  question into English keywords and the public names it mentions (one short
  generation on this device); the keywords join the retrieval query.
- Personal glossary: any source file named `glosario*` / `glossary*` with
  lines `término = equivalent, equivalent` adds the equivalents of the terms
  present in the question (both directions; long single terms also match
  inflections, "muestrear" ~ "muestrearon"). It carries the user's own
  vocabulary across languages ("cucuve = mockingbird, Mimus") where a 3B
  model fails (it rendered "cucuve" as "cuckoo" and "rascón" as "rat" in a
  trial). Glossary files are not retrieved as passages.
- Added terms (model keywords, glossary equivalents) weigh half of the
  question's own words in BM25, so they widen the search without taking it
  over. The expansion prompt carries one worked example (a 3B model ignored
  the format without it).
- The index folds accents, drops function words (es/en/pt/fr) and plurals,
  and indexes each paragraph with its file path words, document title and
  nearest heading ("mi artículo de 2024 sobre el rascón" reaches that file);
  headings are no longer retrieved on their own, long paragraphs are cut at
  sentence ends, identical paragraphs are returned once, and the number of
  passages is `lce.retrieval_k` (4).
- Public evidence for local answers (`evidence.local_answers`, on when
  public evidence is on): up to `evidence.local_max_entities` (3) names are
  looked up on Wikipedia (`evidence.local_lang`, en): scientific names and
  the names the local model listed from the question, and as a bridge one
  scientific name from the retrieved passages; names listed by the model are
  sent only when each of their words appears in the question, the passages
  or the glossary equivalents. Only names are sent, never the
  question or a passage; the metadata lists each name and where it came
  from. The whole article is read and reduced to its first sentence plus the
  sentences carrying the question's terms (status sections sit outside the
  intro). The answer gets the local sources as [1], [2] and the public
  evidence as [W1], [W2], with the instruction to give both when they differ.

- Round 2 (same 16 questions, 3 repetitions): C1 with expansion and
  glossary 21/17/20 of 44 (the P2b C1 had 7/7/7); with public evidence
  22/18/19, but no public fact was gained: the 3B model's names were wrong
  ("Galapagos Cuckoo", "Canis", "Panthera"), the passage bridge sent
  unrelated species (a guppy from a paper's introduction, "Supernova
  assembler" → an unrelated article) and the model ignored the evidence block.
- Public names for local answers are now chosen without the model: scientific
  names in the question, common names "<term> de <Place>" rendered through the
  glossary ("cucuve de Floreana" → "Floreana mockingbird"), proper names the
  user listed in the glossary ("Proyecto Isabela = Project Isabela"), and only
  when the question names none of these, a scientific name repeated in the
  retrieved passages. The model's names are never sent (an employer named in
  a question must not leave the device). Public evidence is fetched only when
  the question asks for something public or current ("actual", "fuentes
  públicas", "current"); questions about the user's own documents send
  nothing. Two names that resolve to the same article are used once; the
  passage keeps the article's first two sentences, the focus sentences and the
  sentence after each; and the turn asks for local facts [1], public facts
  [W1] and both versions when they differ.
- Short blocks of up to four words ("Acme Labs Inc.") are headings, not
  passages; the glossary also matches Spanish gender ("extinto" ~ "extinta").

- Round 3: C1 21/20/20 of 44, with public evidence 25/25/25; public facts
  gained in 3 of the 6 questions that ask for them (current IUCN status of
  two mockingbirds; the fur seal's size and legal protection since 1934). The
  3B model cited the public evidence as "my local sources".
- Fusion template: when public evidence is present, the local passages and
  the evidence go into the user's turn under labels ("MIS DOCUMENTOS",
  "WIKIPEDIA"), followed by the question and a three-part answer (my
  documents, Wikipedia, comparison).
- Retrieval: abbreviated species names are indexed in full when the file
  spells the genus out ("M. melanotis" → "Mimus melanotis"); one file fills at
  most two of the passages; the passage bridge also counts abbreviated forms.
- Public passages: a question that asks for a year or a date ("¿en qué
  año…?") brings the article's sentences with years; glossary acronyms
  ("UICN = IUCN") are not sent as names.

- Round 4: C1 20/19/19, with public evidence 27/27/25 of 44; public facts in
  5 of the 6 questions that ask for them (with the fusion template the
  attribution was mostly right). Two passages per file cut a needed third
  passage (a course list, a paper's conclusion): the cap is now three. The
  passages shown to the model spell abbreviated genera out ("M. trifasciatus"
  → "Mimus trifasciatus"), which the 3B model otherwise skipped.

- Round 5: C1 23/21/23 of 44, with public evidence 27/26/31; the contrast
  "your thesis said X, today it is Y" appeared in 2 of 3 repetitions.
- `evidence.fusion_model` (Settings → Privacy → advanced): a larger local
  model writes only the answers that fuse local sources with public
  evidence; other answers keep the conversation's model. Query keywords now
  come from the default model (`lce.expansion_model`, "" = `model.model_name`)
  even when the conversation uses a large one: a reasoning model returned no
  keywords in 90 tokens (round 6, aborted), and the retrieval lost the
  English passages. Reasoning blocks are stripped from the expansion.

- Shared network (round 7, LAN, five machines): the 16 personal questions
  all stayed on this device (the router does not fragment single questions;
  one was classified SENSITIVE), so the network changed nothing and no local
  passage left. The public half sent as a batch (current IUCN category of
  eight Galápagos species) was distributed, but the evidence did not help:
  the Spanish Wikipedia articles carry no IUCN status, and the network
  answered "Critically Endangered" for almost every species.
- Batch evidence falls back to English Wikipedia when the article in the
  request's language lacks the asked fact: the focus terms are translated
  (`EN_FOCUS`), and an IUCN status sentence must name its assessor (IUCN,
  Red List, BirdLife), so "more vulnerable to disease" is not taken as a
  status.
- An enumerated PUBLIC batch answered on this device (too small to fragment,
  or no workers) gets the same item evidence as fragments, when the request
  could have left (PUBLIC lane, tier allowing egress).

- Round 8: with `evidence.fusion_model` set to a 27B local model (the 3B
  writes everything else), 30/32/30 of 44; the "thesis then, status now"
  contrast was right in 6 of 6 answers, no attribution error in the 15 fused
  answers, 52 s per fused answer against 1.8 s for the rest. On the network,
  the IUCN batch with the English fallback rose from 3/2/1 to 4/6/4 of 8.
  A batch of years stayed local because the lane classifier marked it
  SENSITIVE ("death of Lonesome George"): a false positive upstream.

- Hybrid retrieval (`lce.dense_retrieval`, on): BM25 is fused (reciprocal
  ranks) with vectors from the local embedding model (`model.embed_model`,
  Ollama `/api/embed`, cached per paragraph). In P2e the right paragraph was
  often 6th–26th by BM25 (a long paragraph loses to short ones sharing a
  name). Any failure falls back to BM25 for five minutes.
- Lane refinement: "legal", "abogado", "salud", "médico" (and English) put a
  request in the SENSITIVE lane only with a first-person marker in the same
  clause ("mi abogado", "tengo un problema de salud"); strong terms
  (password, card, IBAN, passport, diagnosis, salary, debt) stay SENSITIVE
  anywhere. "Inicio de la protección legal del lobo peletero" kept a public
  batch off the network (P2e round 8b).

- Round 9: the hybrid retrieval found the paragraph with the asked fact in
  11 of 16 questions in every repetition (BM25 alone: 9), and the key score
  rose from 28/28/27 to 30/33/29 of 44 with the 3B model; the parasite of the
  2021 paper is now found, so its public history is looked up. The batch of
  years now counts as PUBLIC and is distributed, but its items are event
  descriptions with no article to match (0 of 5 either way). With the
  fusion model as well: 30/29/35, and one fused answer came back empty.
- A fused answer gets twice the token budget (a reasoning model thinks
  first); if it is still empty, the conversation's model answers the same
  prompt (`fusion_fallback` in the metadata).

- Round 10a (one repetition each; the hit is deterministic): with the hybrid
  retrieval, 6 passages found the asked fact in 12 of 16 questions, 4 in 11
  and 8 in 12; the score was 33/44 with 6. `lce.retrieval_k` is now 6.
- Batch evidence for events ("Inicio del Proyecto Isabela", "Muerte del
  Solitario George"): the English fallback is searched with the item's proper
  names only (Project Isabela, Lonesome George), and a sentence counts only
  with a year and the event's verb in English (`EN_EVENT`: muerte →
  died/death, inicio → began/initiated…), so an article full of dates does
  not answer with the wrong one; without an event word nothing is added.

- More public sources (`evidence.providers`, default wikidata, wikipedia,
  pubmed): Wikidata gives structured facts in one sentence (IUCN status P141;
  dates of death, birth, inception, start, end, discovery, publication — the
  property chosen by the operation and the event word: "muerte" → date of
  death); PubMed (NCBI E-utilities) gives abstract sentences with the asked
  terms or a year; `web` uses the user's SearXNG instance (`searxng_url`,
  which queries DuckDuckGo, Google, Bing or Google Scholar) or Google Custom
  Search (`google_cse_key`, `google_cse_cx`). Batches take the Wikidata fact
  when the operation asks for a status or a date and fall back to Wikipedia;
  local answers get every provider that has something, labelled. Only names
  (and generic English focus words for PubMed and web search) are sent. In a
  dry run Wikidata had the right IUCN status for 7 of 8 Galápagos species.
  Google Scholar has no API (scraping breaks its terms), so it is reachable
  only through SearXNG.
- Round 10b: years of events with Wikipedia only, 1/1/1 of 5 (wrong years
  from articles about the island and the archipelago); IUCN statuses 4/4/3
  of 8. Round 10c: the effective-size paragraph was dropped by the per-file
  cap.
- Optional local SearXNG installed from the app (Settings → Privacy → Web
  search), with consent and only when internet access is allowed: the
  official Docker image when Docker is running, otherwise SearXNG's source in
  the data folder with its own virtual environment (Python ≥ 3.11, or `uv` to
  provide one; the system Python is never changed). It listens on 127.0.0.1
  only, with JSON output and engines DuckDuckGo, Google, Bing, Brave, Mojeek,
  Wikipedia, Google Scholar, PubMed, Semantic Scholar, OpenAlex, Crossref and
  arXiv; it starts and stops with the app (`evidence.searxng_managed`), and
  on success `searxng_url` is set and `web` is added to the providers.
  Uninstall removes it and its files. Web searches ask the `general` and
  `science` categories. "Test web search" runs one fixed public query and
  reports the results and the engines that answered. The Google Custom Search
  JSON API is closed to new customers and ends on 1 January 2027, so Google
  and Google Scholar are reached through SearXNG; an existing key still works
  until then. Tested end to end on Linux (download, environment, start, stop,
  restart).
- Round 11 (measured with `0a88555`): on the LAN, IUCN statuses went from
  4/4/3 (Wikipedia only) to 8/8/8 of 8 with Wikidata; event years 2/2/2 of 5
  (Lonesome George from Wikidata), historical years unchanged at 10/10.
  Locally (hybrid, k = 6, evidence, 27B fusion) 37 and 36 of 44, with every
  public fact labelled by its source. PubMed rarely added anything here.
- Round 11c, with the local SearXNG: web results appeared in 11 of the 12
  answers with evidence and the score stayed at 37 and 36 of 44 (graded by
  hand where the automatic key missed a correct phrasing). Half of the web
  hits were the Wikipedia article already asked, so web results from hosts
  of providers that are enabled (Wikipedia, PubMed, Wikidata) are now skipped.
  The doctor names the pinned commit when the installed one differs.
- Event years in batches: the event's subject ("cucuve de Floreana",
  "lobo peletero de Galápagos", the phrase after "del/de la…" without a
  trailing place) is looked up in the request language's Wikipedia and
  followed to its English article through the interlanguage link, only when
  every content word of the subject is in that article's title or lead
  ("Proyecto Isabela" does not follow "Provincia de Isabela"). The year comes
  from the first sentence in article order with a year and the English verb
  of the event nearest the subject ("protección" over "inicio"), so the lead's
  date wins over side events ("between 1997 and 2006, initiated…" over
  "brought into action in 1999"). Wikidata gives no date when an event noun
  without a property sits inside the item ("Inicio de la protección…"). In a
  dry run the subjects resolved to Floreana mockingbird (extirpated by 1888)
  and Galápagos fur seal (protected since 1934).
- Round 12 (LAN, three repetitions): Galápagos event years 5/5/5 of 5 with
  evidence (round 11a: 2/2/2; without evidence 1/0/0); IUCN statuses stay at
  8/8 and historical years at 10/10.
- Public evidence is now on by default (`evidence.enabled`): it fixed what
  the models lacked (IUCN statuses 8/8, event years 5/5) and no longer
  worsened what they knew (historical years 10/10). Only item texts or
  entity names leave the device, never the request or local documents, and
  nothing for SENSITIVE requests; Settings → Privacy turns it off. Saved
  configurations keep their explicit value.
- LCE C1, passages: the heading right above a paragraph is shown with it,
  stacked headings together ("Gerente de I+D (R&D Manager) — Sep 2024 ·
  NRGene Canada Inc. (NAIC) — Lideré…"): a job title in a heading was never
  shown to the model (K6). Pieces cut from a long paragraph are indexed with
  the previous piece's last sentence, an overlap as between reads ("…the two
  remnant populations of M. trifasciatus on Champion and Gardner" before
  "These two populations, Champion (Ne ~30)…", K3). "ne" is no longer a stop
  word (Ne, effective population size). Offline BM25 check: the passage with
  the fact is now among the six for 12 of 16 questions (10 before), K3 first.
  CV title lines (up to 160 characters, parts joined by dashes, no sentence
  end: "Entomólogo Jefe de I+D (Investigador Principal) — … — Nov 2022 – Sep
  2024") count as headings too, so the role is shown with the duties under
  it; author lists joined by "|" stay passages. Offline check: 13 of 16.
- Round 13 (measured with `8aac98a`): the effective-size passage is now
  retrieved for K3 in both repetitions (the thesis gives two estimates, ~14/~62
  in the results and ~30/~120 in the discussion; both answers quote one), and
  every source file is read; 12 of 16 retrieval hits, 35 and 38 of 44 by hand.
  K6 failed until the title-line change.
- Round 13c (measured with `c9b08bd`), the preregistered C1 closing check:
  the passage with the fact is among the six for 13 of 16 questions in both
  repetitions; K6 now answers "Gerente de I+D (R&D Manager)… mosca soldado
  negra (BSF)" and K3 "~30, ~120, ancestral Ne ~15 000"; 39 and 38 of 44
  (rounds 11b/11c: 37 and 36). LCE C1 is closed. Known limits: an answer is
  as good as the model that writes it, crossing languages relies on the
  glossary, and a fact in a passage that ranks seventh for its question
  (F3, F7) is missed.
- Requests about the user stay on this device: with C1 active, a first-person
  request about the user's own material ("mi carrera", "mis publicaciones",
  "my thesis") that matches the user's sources is answered locally even in
  LAN or auto mode (`lce.keep_personal_local`, on by default), with a note.
  In an October 2026 test such a request went to four nodes without the
  user's passages (which never leave the device) and came back as generic,
  invented text ("investigador de materiales"), carrying the user's name to
  other machines. A bare "me" (¿me traduces…?) does not count. "internet",
  "web", "en línea" and "busca" now also ask for public evidence.
- Chat: a swarm answer that finished while the WebSocket was down (a long
  request, sleep, a network change) only showed after a reload. Pending
  messages with no recent event are now read from the database every few
  seconds and right after a reconnection; the server's WebSocket ping
  timeout is 90 s.
- Personal requests: a possessive personal topic ("mi carrera", "mis
  publicaciones", "my thesis", "mi salud"…) keeps the request local even
  with no source folder; in the 25 Oct retest C1 was on without sources and
  the request went to the swarm again with the user's name. "Mis 3
  animales" in a batch is not a personal topic.
- Funding campaign: Settings → System shows how to support the project
  (buymeacoffee.com/swarmbly), and the README and `.github/FUNDING.yml` link
  to it. Support never buys influence over the roadmap, licence or governance.
- LCE C1, formats: Word (.docx), HTML and PDF (with `pdftotext` from poppler,
  on the PATH or in Homebrew's folders; ligatures normalised) are read, not
  only text files. Memory → Your sources lists every file with its passages,
  or why it cannot be read (no pdftotext, no text layer), shows the glossary,
  and lets the user add other folders read in place (`lce.sources_dirs`).

**LCE C1: retrieval over your sources, for local answers (P2b)**
- With LCE enabled at C1, answers produced on this device get the most
  relevant paragraphs of the user's sources (LCE source folder plus
  `lce.sources_dirs`; BM25 over ≤ 600-character paragraphs, the scoring of
  SwarmblyLCE) as a system message, and the answer is asked to cite them
  as [1], [2]. The metadata lists the sources used (`lce.sources`).
- Passages never leave the device: requests answered by the swarm do not
  use them. Projection into Γ needs digested claims (C2) and stays empty.
- Following WP LCE v0.2 §11.7–11.8 (R13): retrieval runs over raw sources,
  not over the digested wiki.

A single composition of a stated length (an essay, a speech, a report of N
words) is no longer sent whole to one model or to whole-request replicas: the
**local model plans it** and the swarm writes it section by section.

- **Outline on this device**: the local model reads the whole request and
  returns a JSON outline (title, topic, style line, 3–6 sections with purpose,
  word budget, key points, the explicit requirements that belong to each,
  prose or table). The code validates it (sections, word budgets rescaled to
  the requested length, tables never open or close the text); an unusable
  outline falls back to a deterministic one, and the monitor says which.
- **Decontextualised sections**: each packet carries Γ, the title, the topic
  and one section's brief and position — never the request, its instruction
  list or rubric. Γ's objective is the title, not the request's first
  sentence (which states the length of the whole text).
- **Transitions by the workers**: every section after the first opens with a
  transition from the previous heading; no bridges (the upstream bridge
  prompt is English). Seam similarity is still measured.
- **Requirement check**: each requirement of the outline is checked against
  the final text (lexical presence, not a quality judgement) and reported
  with the outline in the response metadata.
- Settings: `swarm.composer_enabled` (on), `swarm.composer_min_words` (400),
  `swarm.composer_max_sections` (6). Applies only when a local model and at
  least one worker (remote or local pool) are available.
- Fixes from the first live comparison (P3.2, 2026-10-16): a requested table
  is added when the outline omits it; repeated section headings are dropped;
  transitions no longer repeat the previous heading; a section cut at its
  budget loses its unfinished last sentence and stray `---` rules. Batch
  voting also matches unnumbered bullets by the item's own text.
- Second live round (P3.2b): a malformed outline is retried at temperature 0
  and an outline cut mid-section is repaired; a section's mandatory
  requirement comes first in its brief; replica selection prefers the replica
  that meets the section's requirements (e.g. the presenter's name); a table
  requirement is checked against the table itself; words asked of each
  section are scaled by `swarm.composer_length_factor` (0.8, provisional:
  sections overshot by +16 to +44 % in six runs).
- 197 tests (23 new in `tests/test_p1_composer.py`, including a two-node
  end-to-end run over real TLS).

**Windows install and a quieter terminal** (17 October 2026)
- SwarmblyLCE pin moved to `b659ac4`: the previous pin tracked 18 cache
  files whose names contained `:` (Ollama model tags), which Windows forbids,
  so `git clone` — and with it `pip install` — failed on Windows.
- The terminal no longer prints every WebSocket attempt. A browser tab left
  open from an earlier launch holds a stale session token; its reconnections
  were logged twice each, with the token in clear text. They are now dropped
  (one note a minute at most), tokens are redacted from any log line, and
  the web client reloads itself once to pick up the new token, with
  exponential back-off while the server is down.
- Network outcomes on the terminal: node found (once), connected and
  authenticated, left; authentication failures once per address; a single
  "no nodes found" line after an empty search, and a summary after
  “Search again”.

## 0.2.1 — Distributed answers that follow the request (unreleased)

Fixes from the diagnosis of 2026-10-15: a Spanish essay request came back as
mixed English/Spanish, partial answers that echoed the contract.

- **Admission**: numbered lines are a batch only when they are data items
  with a stated operation. The criteria, instructions, steps or rules of one
  task, and single compositions (essay, speech, text of N words), are no
  longer split; they run as one task. Each packet used to carry ~95 % of such
  a request, so every worker wrote the whole essay.
- **The user's closing instructions travel with every fragment**
  (`answer_sheet=False`); the English `[NN] value` directive is gone. Batches
  get a short directive in the request's language.
- **Language**: the request's language is detected on-device and carried as
  the Γ extension `lang`. Workers render the contract and task headings in
  that language; a "respond in <language>" line inside the task covers
  workers on older versions. English packets are unchanged.
- **Conversation context**: a follow-up in a distributed mode is rewritten by
  the local model into a self-contained request; the history never leaves the
  device. Without a local rewrite it is answered locally with the
  conversation.
- **Consensus for compositions**: one whole replica is selected (request
  language, then complete, then document medoid); per-unit alignment is kept
  as the divergence report. Batches vote per numbered item (majority, ties
  to the best-ranked replica); per-unit alignment had appended a second
  replica's re-listed items to the answer in a live smoke test.
- **Length**: requested lengths in words are read in es/en/pt/fr; output
  budgets follow them (whole-request replicas and the local answer included).
  Workers report `finish_reason`; truncated tasks are listed and noted.
- **Contract**: neutral audience when none is stated; capitalised verbs at
  line or bullet starts are no longer canonical entities; English default
  forbidden phrases are not sent with non-English requests.
- **Monitor**: largest share of the request carried by one packet
  (`max_packet_prompt_fraction`).
- 174 tests (34 new in `tests/test_p0_quality.py`).

## 0.2.0 — Phase 2.5: guided setup and new interface (2026-10-12)

Software DOI: [10.5281/zenodo.23322639](https://doi.org/10.5281/zenodo.23322639)
(all versions: [10.5281/zenodo.23322638](https://doi.org/10.5281/zenodo.23322638)).

**Setup that explains itself**
- Recommended configuration from measured hardware: a memory budget
  (unified memory, VRAM or RAM, with its derivation), chat model, local
  parallelism, multi-model, worker limits and LCE level. Every value says why
  and whether it is measured or estimated; applying it keeps a backup and can
  be reverted. It never turns on the network, sharing or a privacy tier.
- First-run assistant: welcome, system check, recommended configuration,
  models, permissions, memory, ready. Each step can be skipped.
- Explicit permissions for local-network discovery and model downloads,
  recorded with their date; internet swarms stay off until Phase 3.
- System check ("doctor"): Python packages (including the pinned upstream
  commits), Ollama, ports. Missing Python packages can be installed into the
  app's own virtual environment after consent; nothing system-wide.
- Model downloads through Ollama only, after the download permission and a
  per-model confirmation showing size and licence (catalog verified
  2026-10-12); progress streamed, cancellable.

**One-command launcher**
- `./launch.sh` (macOS / Linux), `Swarmbly.command` (macOS double-click) and
  `launch.bat` (Windows) run `scripts/launch.py`: Python, git, `.venv`,
  packages, Ollama and port, asking before every change; installs only inside
  `.venv`, never installs Ollama, reinstalls when requirements change, opens
  an already-running app instead of starting a second one. `--check`,
  `--setup-only`, `--headless`, `--yes`, `--port` and more.
- `scripts/dev_setup.sh` now uses the launcher.

**Fixes found by the first macOS CI run**
- mDNS announcements failed on computers whose name does not fit a DNS label
  (longer than 63 bytes, or with spaces, apostrophes or accents, e.g.
  "Sebastián's MacBook Pro"): zeroconf refused the host record and the node
  was never discovered. The host label is now sanitised and capped; identity
  is unaffected (it is the node key). Regression tests added.

**Documentation and repository**
- README rewritten with screenshots; new user guide (`docs/USER_GUIDE.md`),
  `CONTRIBUTING.md`, `SECURITY.md`, issue and pull-request templates, and a
  test workflow (Linux, Python 3.10–3.13; macOS).
- Installation guide rebuilt around the launcher (ports, data locations,
  updating, uninstalling, troubleshooting).

**Several local models**
- Multi-model mode: replicas of a request can run on different local model
  families (a local pool alongside remote workers), with the same consensus
  and reporting as the swarm. Whole requests that cannot be fragmented can
  still be answered by several local models and aligned.
- `constraints.model_family` honoured by workers when they have that family.

**Interface**
- New interface: conversation list, streaming chat with text attachments,
  mode and model per message, "How this answer was made" (pipeline as a DNA
  strand, attempts, consensus units, seams, caveats, reports), swarm map with
  real dispatch pulses, health and contribution, memory levels, settings by
  topic with profiles, light and dark themes, phone layout.
- Every readout is labelled measured, estimated or unknown.
- `scripts/ui_preview.py`: interface preview with a fake swarm on loopback
  (canned answers, never announced on the network).


## 0.1.1 — Phase 1.5 hardening (2026-10-12)

Fixes the findings of `docs/AUDIT_FASE0_ES.md`.

**Network**
- mDNS discovery rewritten on zeroconf's asyncio API: it now discovers peers
  (it never did), filters its own announcement, handles goodbyes, keeps a TTL
  cache with first-seen / last-verified / expiry, and runs an active query per
  request. Discovery starts and stops at runtime (H1, H2, H14, H15, H19, H23).
- Handshake revision 2: Ed25519 identities bound to the TLS certificate
  fingerprint; initiator advertisement authenticated; signed advertisement
  updates on live sessions (H9).
- One session per peer (deterministic tie-break); tasks served outside the
  read loop; keepalive with RTT; per-peer replay window and queue cap;
  graceful shutdown in < 1 s (H6, H26).
- TLS private key written 0600 (H27).

**Engine**
- Plan admission: only structural partitions are fragmented; inline lists are
  normalised losslessly into labelled items (H3).
- Wire packets built from fields: no session id, no complete request, minimal
  Γ; privacy self-check blocks dispatch on any leak (H4, H5).
- Asynchronous scheduler: parallel dispatch by readiness (statement edges do
  not wait), family-diverse replicas, `k_min` up front, hedges/retries up to
  `k_max`, per-worker capacity respected, results verified before assembly
  (H6, H12, H13).
- Upstream `consensus()` reused; lane classification (LCE) before dispatch;
  E_SWARM_UNKNOWN never falls back to GLOBAL; relative deadlines; worker cuts
  generation at its deadline (H11, H24, H25).
- Enumerated answers are spliced without transition bridges.

**Local API and UI**
- Host allowlist, Origin checks, per-launch session token, CSP and security
  headers; config changes validated (`api.*` is CLI-only) (H7).
- Every remote or model-provided string escaped; remote images never
  auto-loaded (H8).
- Events from the P2P thread reach the UI (H16).
- Processing reports fixed (they crashed) with minimal/standard/full detail;
  saved only on request.

**Packaging and metrics**
- The UI ships inside the Python package (wheel installs had no UI) (H17).
- CLI shutdown fixed (H18); orchestrator rebuilt on configuration changes (H20).
- Contribution separates served-to-others from consumed-locally (H22).

## 0.1.0 — Phases 1–2 (2026-10-11)

Initial local app, LAN prototype and monitor.
