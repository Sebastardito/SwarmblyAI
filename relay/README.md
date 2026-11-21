# Swarmbly relay (prototype)

A small rendezvous and byte-splicing service for a Swarmbly trusted circle.
One member (usually the circle owner) runs it on a host with a public address;
the other members keep one outbound TLS connection to it.  The relay:

- proves each node's Ed25519 key with a fresh signed challenge;
- checks both sides of a pair against the signed circle manifest it holds;
- accepts each new signed manifest version from the owner over that
  authenticated connection (D-023), so a revocation takes effect at once;
- splices the two TCP streams byte-for-byte.

The nodes' own TLS 1.3 session and channel-bound handshake run **through** the
splice.  The relay sees who talks to whom, when, and how many bytes; it never
sees plaintext and it never stores payload.

Status: **prototype** (T10.5), with the D-023 owner push; SwarmblyApp 0.8.0
(Swarmbly AI 3.5.0) registers, pairs and pushes manifests through it.  See
[`docs/orchestration/spikes/T10.5_relay_design.md`](../docs/orchestration/spikes/T10.5_relay_design.md)
for the protocol, threat model, deployment checklist and open questions.

## Roles and what the relay stores

- **Operator:** decides which circles the relay serves.  They place the first
  signed manifest of each circle in the `--manifest` directory.  The relay
  never creates a circle from a network message.
- **Owner:** holds the circle's Ed25519 key.  After the operator bootstraps the
  circle, the owner pushes every newer signed manifest over a normal
  registered connection.
- **Member:** registers and pairs; a member cannot push a manifest.

The relay keeps the current manifest in memory and its signed JSON file in
the operator directory (so a restart keeps it), plus in-memory per-member
counters.  Logs are metadata only: circle id prefix, node id prefix, version,
member counts, close reason and time.  They never contain payloads, signatures
or the member list.  D-023 recommends keeping them for 7 days.

## Run

```bash
python -m pip install "cryptography>=41"

# A self-signed certificate is enough: members pin its SHA-256 in the manifest.
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 \
  -keyout key.pem -out fullchain.pem -days 365 -nodes -subj "/CN=swarmbly-relay"

python -m relay.server \
  --manifest /etc/swarmbly-relay/circles \
  --cert fullchain.pem --key key.pem \
  --host 0.0.0.0 --port 8765
```

`--manifest` may be repeated and may name a JSON file or a directory of
`*.json` manifests.  The relay reloads changed files before each registration
and pair request; a malformed edit is logged and ignored.  The directory that
holds a circle file must be writable by the relay user: an owner push
atomically replaces that file.  The first manifest of each circle is still
placed there by the operator.

Default limits: 4 concurrent splices per member, 2 GiB forwarded per member
per UTC day, 300 s idle timeout, 30 s pair timeout, 10 s registration timeout,
30 manifest pushes per owner per UTC hour, and a 48 KiB maximum manifest.
Change them with `--max-splices`, `--bytes-per-day`, `--idle-timeout`,
`--pair-timeout`, `--register-timeout`, `--manifest-pushes-per-hour` and
`--max-manifest-bytes`.

## Manifest view

The App owns `swarmbly_app/p2p/circles.py`; the relay only needs a signed
manifest it can verify with the owner's Ed25519 key.  This shape works:

```json
{
  "circle_id": "circle-3f2a",
  "version": 4,
  "owner": "<owner node_id: base64url Ed25519 public key>",
  "members": [
    "<node_id>",
    {"node_id": "<node_id>", "name": "Ada"}
  ],
  "expires_at": "2027-05-01T00:00:00Z",
  "relay": {
    "host": "relay.example.org",
    "port": 8765,
    "tls_cert_sha256": "<lowercase hex SHA-256 of the relay certificate DER>"
  }
}
```

The signature covers the canonical JSON of the manifest object (sorted keys,
compact separators, UTF-8).  It travels either as
`{"manifest": {...}, "sig": "<base64url>"}` or with `sig` inside the manifest.
The parser accepts `owner_node_id`/`owner_key`, string or object members,
`expiry`/`expires`, and `rendezvous`/`relay`; unknown fields are ignored.
Expired manifests are refused.

## Owner push (D-023)

Once the operator has bootstrapped a circle, its owner keeps the relay current
by pushing each new signed version over a registered connection:

```json
{"type": "manifest_update", "v": 1, "manifest": {"manifest": {}, "sig": "..."}}
```

`manifest` is the complete signed document the App already produces; the relay
does not change that format.  The relay accepts a push only when all of these
hold:

- the connection is registered for the document's `circle_id`;
- the circle is already served (bootstrap is operator-only);
- the **held** manifest's owner is the registered node (the new document's
  `owner` is never used for authority, and an owner change is refused);
- the document's Ed25519 signature verifies with `relay/manifest.py`;
- `version` is strictly greater than the held version;
- the manifest is unexpired and inside the size bound;
- the owner is under its hourly push limit.

On success the relay atomically writes the signed document over the circle's
file, installs it in memory, closes every registration and every splice of
members that disappeared from the manifest, and replies:

```json
{"type": "manifest_ack", "v": 1, "circle_id": "...", "version": 5,
 "member_count": 12}
```

A refusal is explicit and leaves the connection registered, so a fixed push can
follow:

| Code | Meaning |
|---|---|
| `unknown_circle` | the relay does not serve that circle yet |
| `circle_mismatch` | the connection is registered for another circle |
| `not_owner` | the registered node is not the held manifest's owner |
| `owner_change_refused` | the document names a different owner |
| `bad_signature` | unsigned, malformed, or the signature does not verify |
| `expired` | the pushed manifest has expired |
| `stale_version` | the version is equal to or lower than the held one |
| `too_large` | the document exceeds `--max-manifest-bytes` |
| `rate_limited` | the per-owner hourly push limit is exhausted |
| `persist_failed` | the file could not be written; memory is unchanged |

A frame above the relay's control-frame read bound (128 KiB by default) is not
buffered; the connection is closed with `bad_frame`.  The manifest bound is the
useful one.

## Client

```python
from relay.client import RelayAddress, RelayClient

client = RelayClient(address, circle_id, node_id, identity.sign)
await client.connect()                 # TLS to the relay, registered

# Owner only: push the complete signed manifest document.
ack = await client.push_manifest(signed_manifest)   # manifest_ack dict
# On refusal it raises RelayRefused with .code, e.g. "stale_version".

stream = await client.pair(peer_id)    # or: await client.accept_pair()
# stream.read / stream.write / stream.readexactly / stream.drain
```

The relay certificate is pinned with the SHA-256 from the manifest; the pin is
checked before any registration frame is sent.

## Tests

```bash
python -m pytest -q relay/tests
```

The suite covers the signed challenge, replayed registration, non-member
refusal, pairing, both-direction splicing, a real TLS 1.3 session through the
splice, the limits, and the assertion that the relay's captured bytes and logs
do not contain the inner plaintext.  For owner push it covers acceptance and
persistence across a restart, stale/equal versions, a non-owner and a forged
signature, an owner change, an unknown circle, an expired and an oversized
manifest, revocation closing a registration and an open splice immediately,
the hourly rate limit, and the metadata-only log.  See
`relay/tests/test_manifest_push.py`.

## Deployment

- `deploy/swarmbly-relay.service` — systemd unit (hardened).  The
  `circles/` directory is writable because owner pushes replace their file;
  `tls/` stays read-only.
- `Dockerfile` — image; build from the repository root:
  `docker build -f relay/Dockerfile -t swarmbly-relay .`
- Port 8765/TCP by default.  Members connect outbound, so the relay host needs
  no inbound ports other than this one.
- Keep the metadata logs for 7 days by default (D-023), and make sure the
  relay user owns or can write `circles/` so a push can be persisted.

## License

AGPL-3.0-only, the same licence as the umbrella.  See `../LICENSE`.
