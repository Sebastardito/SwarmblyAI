"""Persistent configuration (JSON in the data directory).

Defaults prioritize safety and stability: LOCAL tier, LAN and internet off,
no worker participation, LCE C0, nothing trains. The three general profiles
(Automatic / Custom / Advanced) select presets; every value stays user-editable
and reversible.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from .paths import DataDirs

DEFAULTS: dict[str, Any] = {
    "language": "en",                 # en | es (UI default language)
    "theme": "dark",
    "data_dir": None,                 # None -> platform default
    "output_dir": None,               # None -> <data_dir>/output
    "autostart": False,
    "log_retention_days": 30,
    "reduce_motion": False,
    "setup_completed": False,
    "api": {
        "host": "127.0.0.1",           # local-only admin interface
        "port": 8765,
    },
    "model": {
        "backend": "auto",            # auto | ollama | openai_compat
        "backend_url": "",            # e.g. http://127.0.0.1:11434 (ollama) or .../v1
        "api_key": "",                # only for OpenAI-compatible servers that need it
        "model_name": "",             # empty -> auto pick
        "max_tokens": 1024,
        "temperature": 0.2,
        "embedder": "hash",           # hash (lexical) | server (Ollama /embeddings)
        "embed_model": "nomic-embed-text",
        "max_tokens_per_fragment": 400,
        "multi_model": False,         # several local models (local consensus/workers)
        "local_models": [],           # models used for local multi-model processing
        "local_parallel": 1,          # local models generating at the same time
    },
    "swarm": {
        "mode": "local",              # local | lan | internet | auto
        "lan_enabled": False,
        "internet_enabled": False,
        "discovery_enabled": False,   # mDNS announce/browse only when LAN is on
        "worker_enabled": False,
        "worker_allow_lan": True,
        "worker_allow_internet": False,
        "worker_max_concurrent": 1,
        "worker_only_idle": False,
        "worker_max_tokens_per_task": 800,
        "worker_models": [],          # models offered to others (empty: the chat model)
        "worker_paused": False,
        "worker_only_plugged": False, # serve others only on AC power (laptops)
        "worker_max_task_seconds": 120,
        "max_concurrency": 4,         # simultaneous micro-tasks in flight (client)
        "k_min": 1,                   # replicas dispatched up front (k_epist)
        "k_max": 2,                   # ceiling incl. hedges and retries (k_avail)
        "n_fragments_max": 4,         # upper bound on N; N itself is derived
        "rho_target": None,           # v0.3: ρ is derived and reported, not set
        "tau_sem": 0.5,               # placeholder seam threshold (flagged in reports)
        "timeout_ms": 60000,
        "hedge_fallback_ms": 30000,   # hedge timer until p95 data exists
        "max_retries": 1,
        "discovery_ttl_s": 300,
        "p2p_host": "0.0.0.0",        # P2P listener (independent of the admin API)
        "p2p_port": 9765,
        "rendezvous": [],             # rendezvous endpoints (Phase 3)
        # P1 composition planner: a single composition of at least
        # composer_min_words is planned into sections by the local model.
        "composer_enabled": True,
        "composer_min_words": 400,
        "composer_max_sections": 6,
        "composer_length_factor": 0.8,  # provisional: small models overshoot (P3.2)
        # Heterogeneous swarms (P3b): models below this size (from the tag) are
        # not used while larger ones exist; batches keep ≥ N items per fragment.
        "min_model_params_b": 1.5,
        "min_items_per_fragment": 3,
        # Two batch replicas that disagree on an item get a third (P3g).
        "tie_break": True,
    },
    "privacy": {
        "tier": "LOCAL",              # GLOBAL | TRUSTED | LOCAL
        "manual_tier": None,          # authoritative manual override, never downgraded
        "trusted_nodes": [],          # node_id whitelist for TRUSTED
        "trusted_networks": [],       # CIDR list (informational; LAN != trust)
    },
    "lce": {
        "enabled": False,
        "level": "C0",                # C0..C4; v0.1 ships C0, prepares C1
        "sources_dirs": [],           # extra source folders
        # A request about the user ("mi carrera", "my papers") with C1 active is
        # answered on this device even in LAN/auto mode: the swarm would get the
        # request without the user's sources (no grounding) and with personal
        # details in it (privacy). The answer says why it stayed local.
        "keep_personal_local": True,
        "learning_enabled": False,    # I8: nothing trains without permission
        "capsules_enabled": False,
        # P2e: the local model adds English keywords to the retrieval query,
        # so a Spanish question reaches English sources (local only).
        "query_expansion": True,
        "expansion_model": "",        # "" = the default model (model.model_name)
        "retrieval_k": 6,            # P2e round 10a: 12/16 against 11 with 4
        # Hybrid retrieval: BM25 fused with vectors from model.embed_model
        # (local Ollama); falls back to BM25 alone if the model is missing.
        "dense_retrieval": True,
    },
    # P2 prototype: public evidence for batch items (only item texts are sent
    # to the provider, only for PUBLIC requests). Off until the user enables it.
    "evidence": {
        # On by default since P2e round 12: with operation-aware lookups,
        # Wikidata and subject resolution it fixed what the models lacked and
        # no longer worsened what they knew. Only item texts or entity names
        # are sent, never the request; nothing for SENSITIVE requests.
        "enabled": True,
        "provider": "wikipedia",
        "timeout_s": 4.0,
        "max_chars": 220,
        "max_items": 24,
        # P2d: topic/focus of the batch operation guide the lookup and the
        # snippet; translation batches are skipped. False = P2a/P2c behaviour.
        "operation_aware": True,
        # P2e: answers made on this device may also get public evidence; only
        # entity names (from the question, or scientific names in the local
        # passages) are sent, never the question or a passage.
        "local_answers": True,
        "local_max_entities": 3,
        "local_lang": "en",
        # P2e: model that writes the answers fusing local sources and public
        # evidence ("" = the conversation's model).
        "fusion_model": "",
        # Providers asked, in this order of trust: wikidata (structured facts),
        # wikipedia (prose), pubmed (abstracts), web (SearXNG or Google CSE,
        # only with the URL or the key below).
        "providers": ["wikidata", "wikipedia", "pubmed"],
        "searxng_url": "",
        # Set by the in-app SearXNG installer: "docker" or "native" (it then
        # starts and stops with the app); "" = not managed by the app.
        "searxng_managed": "",
        "google_cse_key": "",
        "google_cse_cx": "",
    },
    "permissions": {
        "lan_discovery": None,        # None = not asked yet; True/False = answer
        "internet": None,
        "model_downloads": None,
        "asked_at": None,
    },
    "results": {
        "auto_report": False,         # generate a report for each distributed request
        "export_dir": None,
        "export_format": "markdown",  # markdown | json | html
        "keep_stats": True,
        "report_detail": "standard",  # minimal | standard | full
    },
    "profile": "automatic",           # automatic | custom | advanced
}

_SENTINEL = object()


def _deep_merge(base: dict, update: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


class Config:
    """Thread-safe JSON config with defaults and deep-merge updates."""

    def __init__(self, dirs: DataDirs):
        self._dirs = dirs
        self._lock = threading.Lock()
        self._data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self) -> None:
        path = self._dirs.config_path()
        if path.exists():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                with self._lock:
                    self._data = _deep_merge(DEFAULTS, raw)
            except (json.JSONDecodeError, OSError) as exc:  # corrupt file -> defaults
                path.rename(path.with_suffix(".json.bak"))
                self.save()
                with self._lock:
                    self._data = copy.deepcopy(DEFAULTS)
                self._last_error = str(exc)

    def save(self) -> None:
        self._dirs.ensure()
        with self._lock:
            payload = json.dumps(self._data, indent=2, ensure_ascii=False)
            self._dirs.config_path().write_text(payload, encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            node: Any = self._data
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    return default
                node = node[part]
            return copy.deepcopy(node)

    def all(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._data)

    def update(self, changes: dict[str, Any], save: bool = True) -> dict[str, Any]:
        """Deep-merge ``changes`` (dot keys or nested dicts) and persist."""
        nested: dict[str, Any] = {}
        for key, value in changes.items():
            if "." in key:
                top, _, rest = key.partition(".")
                nested.setdefault(top, {})[rest] = value
            else:
                nested[key] = value
        with self._lock:
            self._data = _deep_merge(self._data, nested)
            merged = copy.deepcopy(self._data)
        if save:
            self.save()
        return merged

    def reset(self, section: str | None = None) -> None:
        with self._lock:
            if section is None:
                self._data = copy.deepcopy(DEFAULTS)
            elif section in DEFAULTS and isinstance(DEFAULTS[section], dict):
                self._data[section] = copy.deepcopy(DEFAULTS[section])
        self.save()


# ---------------------------------------------------------------------------
# Validation of changes coming from the UI / API
# ---------------------------------------------------------------------------

class ConfigError(ValueError):
    pass


_ENUMS = {
    "language": {"en", "es"},
    "theme": {"dark", "light"},
    "profile": {"automatic", "custom", "advanced"},
    "model.backend": {"auto", "ollama", "openai_compat"},
    "model.embedder": {"hash", "server"},
    "swarm.mode": {"local", "lan", "internet", "auto"},
    "privacy.tier": {"GLOBAL", "TRUSTED", "LOCAL"},
    "privacy.manual_tier": {None, "GLOBAL", "TRUSTED", "LOCAL"},
    "lce.level": {"C0", "C1", "C2", "C3", "C4"},
    "evidence.local_lang": {"es", "en", "pt", "fr"},
    "evidence.searxng_managed": {"", "docker", "native"},
    "results.export_format": {"markdown", "json", "html"},
    "results.report_detail": {"minimal", "standard", "full"},
}
_RANGES = {
    "model.max_tokens": (16, 32768),
    "model.max_tokens_per_fragment": (16, 8192),
    "model.temperature": (0.0, 2.0),
    "model.local_parallel": (1, 4),
    "swarm.k_min": (1, 8),
    "swarm.k_max": (1, 8),
    "swarm.n_fragments_max": (2, 16),
    "swarm.max_concurrency": (1, 64),
    "swarm.timeout_ms": (1000, 600000),
    "swarm.hedge_fallback_ms": (200, 600000),
    "swarm.max_retries": (0, 8),
    "swarm.worker_max_concurrent": (1, 16),
    "swarm.worker_max_tokens_per_task": (16, 8192),
    "swarm.worker_max_task_seconds": (5, 3600),
    "swarm.p2p_port": (1024, 65535),
    "swarm.tau_sem": (0.0, 1.0),
    "swarm.discovery_ttl_s": (30, 86400),
    "swarm.composer_min_words": (50, 20000),
    "swarm.composer_max_sections": (3, 12),
    "swarm.composer_length_factor": (0.3, 1.5),
    "swarm.min_model_params_b": (0.0, 100.0),
    "swarm.min_items_per_fragment": (1, 50),
    "evidence.timeout_s": (0.5, 30.0),
    "evidence.max_chars": (60, 1000),
    "evidence.max_items": (1, 100),
    "evidence.local_max_entities": (1, 6),
    "lce.retrieval_k": (1, 10),
    "log_retention_days": (1, 3650),
}
# Never changeable from the browser: binding the admin API elsewhere is a
# security decision made on the command line, by the machine's owner.
_LOCKED_PREFIXES = ("api.",)


def _flatten(prefix: str, value: Any, out: dict[str, Any]) -> None:
    if isinstance(value, dict) and value and prefix.split(".")[0] in DEFAULTS \
            and not _is_leaf_dict(prefix):
        for key, sub in value.items():
            _flatten(f"{prefix}.{key}" if prefix else key, sub, out)
    else:
        out[prefix] = value


def _is_leaf_dict(key: str) -> bool:
    node: Any = DEFAULTS
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return not isinstance(node, dict)


def validate_changes(changes: dict[str, Any]) -> dict[str, Any]:
    """Return flattened, validated changes or raise ConfigError."""
    flat: dict[str, Any] = {}
    for key, value in changes.items():
        _flatten(key, value, flat)
    for key, value in flat.items():
        if key.startswith(_LOCKED_PREFIXES):
            raise ConfigError(f"{key} can only be changed from the command line")
        node: Any = DEFAULTS
        parts = key.split(".")
        for part in parts[:-1]:
            if not isinstance(node, dict) or part not in node:
                raise ConfigError(f"unknown setting {key!r}")
            node = node[part]
        if not isinstance(node, dict) or parts[-1] not in node:
            raise ConfigError(f"unknown setting {key!r}")
        default = node[parts[-1]]
        if key in _ENUMS and value not in _ENUMS[key]:
            raise ConfigError(f"{key} must be one of {sorted(map(str, _ENUMS[key]))}")
        if key in _RANGES:
            lo, hi = _RANGES[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) \
                    or not lo <= value <= hi:
                raise ConfigError(f"{key} must be a number in [{lo}, {hi}]")
        elif isinstance(default, bool) and not isinstance(value, bool):
            raise ConfigError(f"{key} must be true or false")
        elif isinstance(default, list) and not isinstance(value, list):
            raise ConfigError(f"{key} must be a list")
        if key == "evidence.providers" and not set(value) <= _PROVIDERS:
            raise ConfigError(f"{key} items must be among {sorted(_PROVIDERS)}")
    return flat


_PROVIDERS = frozenset({"wikidata", "wikipedia", "pubmed", "web"})
