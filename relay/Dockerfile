# SPDX-License-Identifier: AGPL-3.0-only
# Build from the repository root:
#   docker build -f relay/Dockerfile -t swarmbly-relay .
# Run with the manifests writable (owner pushes replace their file) and the
# TLS material mounted read-only:
#   docker run --rm -p 8765:8765 \
#     -v "$PWD/circles:/etc/swarmbly-relay/circles" \
#     -v "$PWD/tls:/etc/swarmbly-relay/tls:ro" \
#     swarmbly-relay
# The process runs as UID 10001; make circles/ writable by that uid (or use a
# named volume) so pushed manifest versions survive a restart.

FROM python:3.12-slim

LABEL org.opencontainers.image.title="Swarmbly relay"
LABEL org.opencontainers.image.licenses="AGPL-3.0-only"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 swarmbly \
    && useradd --system --uid 10001 --gid 10001 \
       --home-dir /nonexistent --shell /usr/sbin/nologin swarmbly

WORKDIR /app
COPY LICENSE /app/LICENSE
COPY relay /app/relay
RUN python -m pip install --no-cache-dir "cryptography>=41"

USER 10001:10001
EXPOSE 8765

ENTRYPOINT ["python", "-m", "relay.server"]
CMD ["--manifest", "/etc/swarmbly-relay/circles", \
     "--cert", "/etc/swarmbly-relay/tls/fullchain.pem", \
     "--key", "/etc/swarmbly-relay/tls/key.pem", \
     "--host", "0.0.0.0", "--port", "8765"]
