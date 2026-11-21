# Swarmbly relay (prototype)

A small rendezvous and byte-splicing service for a Swarmbly trusted circle.
One member (usually the circle owner) runs it on a host with a public address;
the other members keep one outbound TLS connection to it.  The relay:

- proves each node's Ed25519 key with a fresh signed challenge;
- checks both sides of a pair against the signed circle manifest it holds;
- splices the two TCP streams byte-for-byte.

The nodes' own TLS 1.3 session and channel-bound handshake run **through** the
splice.  The relay sees who talks to whom, when, and how many bytes; it never
sees plaintext and it never stores payload.

Status: **spike prototype for T10.5**, not wired into the App yet.  See
[`docs/orchestration/spikes/T10.5_relay_design.md`](../docs/orchestration/spikes/T10.5_relay_design.md)
for the protocol, threat model, deployment checklist and open questions.

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
and pair request; a malformed edit is logged and ignored.

Default limits: 4 concurrent splices per member, 2 GiB forwarded per member
per UTC day, 300 s idle timeout, 30 s pair timeout, 10 s registration timeout.
Change them with `--max-splices`, `--bytes-per-day`, `--idle-timeout`,
`--pair-timeout` and `--register-timeout`.

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

## Client

```python
from relay.client import RelayAddress, RelayClient

client = RelayClient(address, circle_id, node_id, identity.sign)
await client.connect()                 # TLS to the relay, registered
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
do not contain the inner plaintext.

## Deployment

- `deploy/swarmbly-relay.service` — systemd unit (hardened, read-only).
- `Dockerfile` — image; build from the repository root:
  `docker build -f relay/Dockerfile -t swarmbly-relay .`
- Port 8765/TCP by default.  Members connect outbound, so the relay host needs
  no inbound ports other than this one.

## License

AGPL-3.0-only, the same licence as the umbrella.  See `../LICENSE`.
