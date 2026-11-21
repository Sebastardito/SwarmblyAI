# Architecture of release 3.5 · Teams and trusted circles · private beta

**Status:** proposal, 2026-11-21. Decisions marked *proposed* wait for the maintainer; they become D-015… in [`DECISIONS.md`](DECISIONS.md) when taken.
**Inputs:** the read-only map T10.1 (network layer, roles, teams, off-LAN, installers, credits, tests), [`ROADMAP.md`](../ROADMAP.md) row 3.5 and decision 8, the 3.4 ledger.

## 1. Where 3.5 starts

Today's swarm is **LAN-only, requester-central, authenticated but not authorised**:

- **Identity:** persistent Ed25519 node key; TLS 1.3 with a self-signed certificate bound to the key by the handshake (SSH host-key model, not mutual TLS).
- **Discovery:** mDNS (IPv4) plus a manual `host:port`.
- **Admission:** any peer that completes the handshake is accepted. `privacy.trusted_nodes` exists in the config but nothing reads it.
- **Dispatch:** the requester plans, the scheduler dispatches signed packets to peers or to the local multi-model pool, retries, rescues locally and verifies signed results.
- **Receipts:** peers are hard-coded as `OWN_NETWORK`, and peer sends bypass `egress.check_call`.
- **Missing:** node roles, a team object, membership, invitations, off-LAN transport, credits, signed installers.

3.5 is mostly **new control-plane and trust work around the existing task plane**, not a rewrite of dispatch.

## 2. Goals and exit criteria (ROADMAP 3.5)

**Goals:**
- nodes announce roles (search, large model, reasoner, corpus);
- the same team runs on one node or several;
- trusted circles by invitation (code or QR), also beyond the LAN through direct addresses or an overlay network;
- non-transferable reciprocity credits;
- signed installers;
- a private beta with 20–50 volunteers in 3–5 circles.

**Exit criteria:**
- team versus equivalent local run, measured;
- losing a node leaves honest partial results;
- ≥ 90 % successful installs;
- no severe bug open for two weeks.

**Carried from 3.4:**
- a new sealed bank confirms the privacy fix (R-003);
- the exact-result target;
- R-005 and R-006;
- remaining App defects (T9.9);
- harness follow-ups (T9.6, T9.10).

## 3. Proposed design

### 3.1 Circle, membership and invitation (*proposed* D-015, D-016)

**The circle:**
- A **circle** is a signed **membership manifest**: `circle_id`, owner key, member `node_id`s with display names, expiry, version and an optional endpoint hint per member.
- It is signed with Ed25519 over canonical JSON, reusing `identity` and `messages.canonical_bytes`/`verify_signature`.

**The invitation:**
- An invitation is a short signed token: `circle_id`, owner, a one-time nonce, expiry, endpoints.
- It travels as a file, a short text code or a QR.
- On acceptance, the newcomer's `node_id` is added by the owner, who signs a new manifest version that peers fetch on the control plane.

**Admission:**
- At handshake and again at the worker gate, a peer is admitted **only** if both nodes hold a valid manifest of a common circle that lists them.
- Outside a circle, the LAN behaviour of 3.4 stays available as «my own devices». The **default for new installs is circle-only**.
- Revocation is a new manifest version without the member; the version number makes older manifests stale.

**Limits:**
- Mutual TLS and the SPEC's `TRUSTED` tier stay out of 3.5; circle work keeps tier `GLOBAL`, lane `PUBLIC`.
- A circle CA is reconsidered in 3.6.

### 3.2 Beyond the LAN (*proposed* D-017)

The App **dials an address**; it does not manage the network. Two ways are supported and documented:
- **(a) a direct address** with a forwarded port;
- **(b) an overlay of the circle's choice** (self-hosted Headscale/WireGuard recommended; Tailscale or Nebula work the same way), dialled by overlay hostname or IP.

Endpoints travel in the manifest or in the invitation. mDNS stays the LAN path.

Native rendezvous, relay and NAT traversal remain 3.6, as the roadmap says.

### 3.3 Honest classification and the egress gate (*proposed* D-018)

- **A new destination class `CIRCLE`:** between `OWN_NETWORK` (my own devices) and `THIRD_PARTY`.
- **Peer sends go through `egress.check_call`** like every other outbound call, with purpose `FRAGMENT`.
- **The receipt names the circle and the member:** a peer outside every circle is refused, not labelled.
- **Passages to peers:** a new per-circle switch `circle_passages`, off by default, separate from `privacy.third_party_passages` (whose name is about model services). Recipe 4 uses it.
- **Docs:** `ARCHITECTURE.md` is corrected where it says passages go "nowhere".

### 3.4 Roles (*proposed* D-019)

- The signed advertisement gains `roles`: `search`, `large_model`, `reasoner`, `corpus`. Each role has a small, validated metadata block:
  - large model: the model and its parameter count;
  - reasoner: think support;
  - corpus: a name and a size bucket only, never titles or contents;
  - search: the engines it can reach.
- Roles are **self-declared**. The scheduler uses them for placement and records per-role success, so a role that fails is avoided; no reputation is trusted from the advertiser.
- New local executors so that roles are real on one node: a search executor (public search on the worker, query-only, through its own egress policy), a corpus executor (retrieval on the worker's own LCE, answering only with what the circle may see) and a reasoner flag carried in the packet.

### 3.5 Teams and honest partial results (*proposed* D-020)

**Teams:**
- A **team** is a named, stored plan template: roles, steps, dependencies. It runs with the existing **requester-central** scheduler.
- Role-aware placement picks circle members by role, or the local pool when one node has every role. This is the substrate the map confirmed ("the same plan runs on remote workers or on the local pool").

**Node loss:**
- Today a task that cannot be completed fails the whole request.
- 3.5 assembles a **partial answer**: completed steps, missing steps named, and why. Recipe 4 keeps its per-item statuses, and a failed wave no longer aborts the whole list.
- A coordinator that disappears is the requester itself, so a lost coordinator ends the run; no plan migration in 3.5.

### 3.6 Credits (*proposed* D-021)

- **Earning:** each accepted task yields a **signed, non-transferable credit receipt**, signed by the requester for the worker: task id, circle, worker, tokens and time, model, timestamp, expiry.
- **The wallet:** the worker's wallet is local. It is spendable only by submitting work to the **same circle**, and expires.
- **Verification:** a requester verifies spent receipts it issued itself, or that a circle member issued. Double spending inside a circle is detected by the issuer's receipt log, exchanged on the control plane.
- No transfer, no market and no global ledger, as SPEC §18 and GOVERNANCE require. The existing daily counters stay as the dashboard.

### 3.7 Wire (*proposed* D-022)

- The task plane stays **wire 0.2**.
- Circle control (manifest fetch, invitation acceptance, credit-receipt exchange) uses **new message types on the same TLS session**, MINOR-safe, so older nodes ignore them.
- They are documented as an appendix to the SPEC with conformance tests. The 0.3 bump waits for 3.6, when relay and rendezvous arrive.

### 3.8 Signed installers (*proposed* D-023, needs the maintainer's accounts)

- **macOS:** a Developer ID-signed and notarised `.pkg` (or app bundle), produced in CI from secrets the maintainer provides.
- **Windows:** an Authenticode-signed installer (an OV certificate or Azure Trusted Signing).
- **Linux and Docker:** minisign or Sigstore signatures and published SHA-256 checksums.
- **Without the accounts, the fallback** is Sigstore/minisign plus checksums on every platform, and the notes say the OS will still warn.
- **Also in this work:**
  - fix the installer's Python minimum (3.10 accepted while the App needs 3.11);
  - make the first sandbox compile a first-launch step with a notice (R-005);
  - run an installer-success telemetry-free checklist for the beta.

### 3.9 Beta programme

- **Per circle:** an invitation kit (installer, invitation, two-page guide), a consent form and privacy notice, and a feedback form.
- **Health checks:** a «doctor» export with no personal data that a volunteer can send when something fails.
- **Bug tracking:** severe bugs are tracked in the umbrella issues with a «beta» label; the two-week criterion counts from the last severe bug closed.

## 4. Measurement

1. **Team versus local:**
   - a pre-registered open battery (`bench/dev_team`) runs the same team on one node (local pool) and on 2–3 nodes;
   - it measures time, completion and agreement;
   - it runs on the maintainer's machines.
2. **Node loss:** a battery that kills a node mid-run (real machine, or a process on another host) and checks the partial answer and its statuses.
3. **Peer-aware privacy:**
   - the harness gains a two-node mode: a second App instance on loopback as a circle member, and a non-member that must be refused;
   - receipts must show `CIRCLE` and every passage sent.
4. **Sealed bank v5 (written by the maintainer):** confirms the 3.4 privacy fix and adds circle cards (admission, passages, credits, partial results). It runs once, as always.
5. **Installs:** the beta records install outcomes per OS from the volunteers' checklists; the target is ≥ 90 %.

## 5. Work packages and order

| WP | Content | Depends on |
|---|---|---|
| WP0 | Baseline hygiene: the 2 P2P family tests, Windows P2P CI, installer Python 3.11, CHANGELOG/ARCHITECTURE drift | — |
| WP1 | Circle manifest, invitation (file/code/QR), admission at handshake and worker | D-015, D-016 |
| WP2 | Destination class `CIRCLE`, peer sends through the egress gate, receipts, `circle_passages` | WP1, D-018 |
| WP3 | Off-LAN dialling: endpoints in manifest/invitation, overlay guide, address handling (IPv6, hostnames) | WP1, D-017 |
| WP4 | Roles in the advertisement, role-aware placement, search/corpus/reasoner executors | WP2, D-019 |
| WP5 | Teams (stored templates) and honest partial results | WP4, D-020 |
| WP6 | Credit receipts, local wallet, control-plane exchange | WP2, D-021, D-022 |
| WP7 | Signed installers, first-launch sandbox compile, beta kit | D-023 |
| WP8 | Batteries: team vs local, node loss, two-node privacy harness; guide for bank v5 | WP2–WP6 |
| WP9 | Leftovers from 3.4: T9.9 rest, T9.6/T9.10, glossary scan cache | — |

## 6. New risks

| ID | Risk | Mitigation |
|---|---|---|
| R-008 | A peer outside any circle receives tasks (admission is open today) | Circle-only admission by default (WP1), tested with a non-member |
| R-009 | Off-LAN peers mislabelled as own network; peer sends bypass the egress gate | `CIRCLE` class and gate (WP2) before any off-LAN work |
| R-010 | Membership without mutual TLS: a stolen node key impersonates a member | Manifest versions and revocation; key at rest unencrypted today; mTLS or a per-circle key in 3.6 |
| R-011 | Self-declared roles mislead placement | Per-role success tracking; roles never widen permissions |
| R-012 | Credit receipts gamed or double-spent | Requester-signed receipts, issuer logs, expiry, circle-scoped |
| R-013 | Signing depends on paid accounts and CI secrets | Fallback with Sigstore/minisign; secrets only in the maintainer's CI |
| R-014 | The beta collects personal data by accident | No telemetry; doctor export reviewed for personal data; consent form |
