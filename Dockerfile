# syntax=docker/dockerfile:1
# Swarmbly AI — container image of the integrated distribution
# (SwarmblyCore + SwarmblyLCE + SwarmblyApp). Models run in a separate Ollama
# container; see compose.yaml and docs/DOCKER.md.
FROM python:3.12-slim-bookworm

ARG SWARMBLY_VERSION=3.0.1
LABEL org.opencontainers.image.title="Swarmbly AI" \
      org.opencontainers.image.description="Decentralized AI that fragments the problem, not the model: local orchestrator, private memory and a peer-to-peer swarm of small models" \
      org.opencontainers.image.source="https://github.com/Sebastardito/SwarmblyAI" \
      org.opencontainers.image.documentation="https://github.com/Sebastardito/SwarmblyAI/blob/main/docs/DOCKER.md" \
      org.opencontainers.image.licenses="AGPL-3.0-or-later" \
      org.opencontainers.image.version="${SWARMBLY_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SWARMBLY_DATA_DIR=/data

# No keychain inside a container: API keys go to /data/secrets.json (0600).
# The compose services (and the computer that runs Docker) count as this
# computer in the privacy receipt, not as third parties.
ENV SWARMBLY_KEYRING=off \
    SWARMBLY_LOCAL_HOSTS=ollama,searxng,host.docker.internal

# Projects (3.1) live in the data volume, so they survive the container.
ENV SWARMBLY_PROJECTS_DIR=/data/projects

# pdftotext reads PDF sources; tini forwards signals so the app stops cleanly.
RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils tini \
 && rm -rf /var/lib/apt/lists/*

# The source stays in the image: it is the corresponding source that the
# AGPL asks to offer to users of a network service (see NOTICE).
WORKDIR /opt/swarmbly
COPY LICENSE NOTICE components.lock ./
COPY installer/ installer/
COPY SwarmblyCore/ SwarmblyCore/
COPY SwarmblyLCE/ SwarmblyLCE/
COPY SwarmblyApp/ SwarmblyApp/

# Same order as the installer: Core and LCE from their folders, the app
# without its git pins (so pip does not fetch other copies), then the app's
# remaining dependencies, read from its pyproject by the installer itself.
RUN pip install ./SwarmblyCore ./SwarmblyLCE \
 && pip install --no-deps ./SwarmblyApp \
 && python -c "import sys; sys.path.insert(0, 'installer'); import install; print('\n'.join(install._app_dependencies()))" > /tmp/app-deps.txt \
 && pip install -r /tmp/app-deps.txt \
 && rm /tmp/app-deps.txt \
 && python -c "import swarmbly_app, swarmbly_lce, swarmbly_v0"

COPY docker/entrypoint.py /usr/local/bin/swarmbly-entrypoint
RUN chmod 0755 /usr/local/bin/swarmbly-entrypoint \
 && useradd --create-home --uid 1000 swarmbly \
 && mkdir -p /data /documents \
 && chown swarmbly:swarmbly /data

USER swarmbly
VOLUME ["/data"]
# 8765: web interface (publish on 127.0.0.1 only). 9765: peer-to-peer (LAN).
EXPOSE 8765 9765

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=4)"

ENTRYPOINT ["/usr/bin/tini", "--", "swarmbly-entrypoint"]
CMD ["serve"]
