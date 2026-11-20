"""Models by role (3.3).

One conversation uses models for different jobs: answering, writing a
composition from the user's sources, writing the search terms, joining the
user's sources with public evidence, and (with the recipes) verifying claims.
3.2 measured that the job matters: a 7B model answers questions about a few
paragraphs without fault, and a 27B model writing only the compositions took
their key data from 90/99 to 96/99 at about twice the time (open battery).

A role names a model, whether it may think before answering, and optionally a
server of its own. An empty model is the conversation's model; an empty
backend is the conversation's server. A role never widens what may leave the
computer: its destination is checked with the same policy as any model
(``privacy.third_party_models``, ``privacy.third_party_passages``), and when
the policy does not allow it, or the model is not there, the conversation's
model does the job and the answer says so (``meta.roles``).

Older settings keep working: ``compose.model`` is the writer,
``lce.expansion_model`` the search terms, ``evidence.fusion_model`` the fusion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import egress

ROLES = ("writer", "search_terms", "fusion", "verifier", "embeddings")
# roles that are given paragraphs of the user's documents. Embeddings always
# carry them: C1 embeds the document passages before it embeds the query.
_WITH_PASSAGES = {"writer", "fusion", "verifier", "embeddings"}
_LEGACY = {"writer": ("compose", "model"), "search_terms": ("lce", "expansion_model"),
           "fusion": ("evidence", "fusion_model")}


@dataclass
class Choice:
    """Who does a job in this answer."""
    role: str
    model: str
    backend: Any
    think: bool | None = None
    own: bool = False            # the role has a model or server of its own, and it is used
    where: str = ""              # host of a third party; "" on this computer or the user's network
    asked: str = ""              # the model the settings name, when it could not be used
    note: str = ""               # why not: "missing" or "blocked: …"
    blocked: str = ""            # host a refused call would have gone to (embeddings)

    def to_meta(self) -> dict[str, Any]:
        out: dict[str, Any] = {"model": self.model, "own": self.own}
        if self.think is not None:
            out["think"] = self.think
        if self.where:
            out["where"] = self.where
        if self.note:
            out.update(asked=self.asked, note=self.note)
        return out

    def stream_chat(self, messages: list[dict[str, str]], **kw: Any) -> Any:
        """The backend's call with this role's model and thinking setting."""
        kw.setdefault("model", self.model)
        if self.think is not None and getattr(self.backend, "accepts_think", False):
            kw.setdefault("think", self.think)
        return self.backend.stream_chat(messages, **kw)


def settings(cfg: dict[str, Any], role: str) -> dict[str, Any]:
    """The role's settings, with the older keys as a fallback for the model."""
    own = dict(((cfg.get("roles") or {}).get(role) or {}))
    if not own.get("model") and role in _LEGACY:
        section, key = _LEGACY[role]
        own["model"] = str((cfg.get(section) or {}).get(key) or "")
    return own


def _remote(backend: Any, model: str) -> str:
    fn = getattr(backend, "remote_host", None)
    try:
        return str(fn(model) or "") if callable(fn) and model else ""
    except Exception:
        return egress.cloud_host_by_name(model)


# -- embeddings (3.4, carried over from 3.3) ----------------------------------

def embeddings_configured(cfg: dict[str, Any]) -> bool:
    """True when the user chose a model or a server for the embeddings role."""
    s = settings(cfg, "embeddings")
    return bool(str(s.get("model") or "").strip() or str(s.get("backend") or "").strip())


def _legacy_embedding_client(cfg: dict[str, Any]) -> Any:
    """The app's embedder before the role existed: Ollama ``/api/embed`` at
    ``model.backend_url`` (or 127.0.0.1:11434) with ``model.embed_model``."""
    from .inference.embeddings import ollama_embedder
    model_cfg = cfg.get("model") or {}
    model = str(model_cfg.get("embed_model") or "nomic-embed-text")
    url = str(model_cfg.get("backend_url") or "") or "http://127.0.0.1:11434"
    return ollama_embedder(model, url)


def _embedding_fallback(legacy: Any, *, asked: str, note: str, blocked: str = "",
                        allow: bool = True) -> Choice:
    """Refuse the chosen destination and use the app's own embedder, or none.

    ``allow=False`` is the strict path (``AppState._embed``): the caller wants
    the refusal, not a substitute.  A third-party legacy endpoint is never
    used as a fallback: passages only leave for a destination the role chose
    and the policy authorised.
    """
    if not allow:
        return Choice("embeddings", "", None, asked=asked, note=note, blocked=blocked)
    try:
        cls, _host = egress.classify_url(legacy.endpoint)
    except Exception:
        cls = egress.THIRD_PARTY
    if cls in (egress.LOCAL, egress.OWN_NETWORK):
        return Choice("embeddings", legacy.model, legacy, own=False, asked=asked,
                      note=f"{note}; using the local embedder {legacy.model}",
                      blocked=blocked)
    return Choice("embeddings", "", None, own=False, asked=asked,
                  note=f"{note}; no local embedder configured: keyword retrieval only",
                  blocked=blocked)


def _choose_embeddings(cfg: dict[str, Any], s: dict[str, Any],
                       allow_fallback: bool = True) -> Choice:
    """A client for the embeddings role, after the destinations policy.

    A third party gets passage embeddings only with both authorisations.  The
    policy is checked before a client is even asked for its model list, so a
    refusal writes no byte.  On refusal the app's own Ollama embedder (when
    configured and local) does the job; otherwise C1 stays lexical.
    """
    from .inference.embeddings import ANTHROPIC_NO_EMBEDDINGS, EmbeddingClient
    legacy = _legacy_embedding_client(cfg)
    name = str(s.get("model") or "").strip()
    kind = str(s.get("backend") or "").strip()
    own = bool(name or kind)
    asked = name or legacy.model
    if not own and str((cfg.get("model") or {}).get("backend") or "") == "anthropic":
        # The conversation's model is Anthropic and no embeddings role was
        # chosen: its address has no embeddings route, so refuse it rather
        # than send the passages to a model API that cannot embed.
        return _embedding_fallback(legacy, asked=asked,
                                   note=f"blocked: {ANTHROPIC_NO_EMBEDDINGS}",
                                   blocked="api.anthropic.com",
                                   allow=allow_fallback)
    if not own:
        chosen = legacy
    elif kind == "anthropic":
        return _embedding_fallback(legacy, asked=asked,
                                   note=f"blocked: {ANTHROPIC_NO_EMBEDDINGS}",
                                   blocked="api.anthropic.com",
                                   allow=allow_fallback)
    elif kind == "openai_compat":
        url = str(s.get("backend_url") or "").strip()
        if not url:
            return _embedding_fallback(
                legacy, asked=asked,
                note="missing: the embeddings role's OpenAI-compatible server needs a URL",
                allow=allow_fallback)
        from .keystore import get_secret
        chosen = EmbeddingClient(
            "openai_compat", asked, url,
            api_key=get_secret("roles.embeddings.api_key") or str(s.get("api_key") or ""))
    elif kind in ("", "ollama", "auto"):
        url = str(s.get("backend_url") or "").strip() or legacy.url
        from .keystore import get_secret
        chosen = EmbeddingClient(
            "ollama", asked, url,
            api_key=get_secret("roles.embeddings.api_key") or str(s.get("api_key") or ""))
    else:
        return _embedding_fallback(legacy, asked=asked,
                                   note=f"missing: unknown embeddings backend {kind!r}",
                                   allow=allow_fallback)
    # Where does it run, and may this job go there? Checked before any call.
    cls, host = egress.classify_url(chosen.endpoint)
    remote = egress.cloud_host_by_name(chosen.model) if chosen.backend == "ollama" else ""
    if remote:
        cls, host = egress.THIRD_PARTY, remote
    if cls == egress.THIRD_PARTY:
        policy = egress.policy()
        if not policy.authorised(host):
            return _embedding_fallback(
                legacy, asked=asked,
                note=f"blocked: {chosen.model} runs at {host}, which is not authorised",
                blocked=host, allow=allow_fallback)
        if not policy.third_party_passages:
            return _embedding_fallback(
                legacy, asked=asked,
                note=f"blocked: {chosen.model} runs at {host}, authorised for questions only",
                blocked=host, allow=allow_fallback)
    return Choice("embeddings", chosen.model, chosen, own=own,
                  where=host if cls == egress.THIRD_PARTY else "")


def choose(role: str, cfg: dict[str, Any], chat_backend: Any, chat_model: str,
           registry: Any = None, passages: bool | None = None,
           allow_fallback: bool = True) -> Choice:
    """The model, server and thinking setting for ``role`` in this answer.

    ``passages`` says whether the job will carry paragraphs of the user's
    documents (by default, what the role usually carries).  For the
    ``embeddings`` role ``chat_backend``/``chat_model`` are not used: the
    fallback is the app's own embedder, or keyword retrieval when there is
    none (``allow_fallback=False`` returns the refusal instead)."""
    if role == "embeddings":
        return _choose_embeddings(cfg, settings(cfg, role), allow_fallback)
    s = settings(cfg, role)
    think = s.get("think")
    fallback = Choice(role, chat_model, chat_backend, think)
    name, kind = str(s.get("model") or ""), str(s.get("backend") or "")
    if not name and not kind:
        return fallback
    name = name or chat_model
    backend = chat_backend
    if kind:
        from .inference.registry import BackendRegistry
        from .keystore import get_secret
        try:
            backend = (registry or BackendRegistry()).build(
                kind, str(s.get("backend_url") or ""),
                api_key=get_secret(f"roles.{role}.api_key") or str(s.get("api_key") or ""),
                think=(cfg.get("model") or {}).get("think"))
        except Exception as exc:
            return Choice(role, chat_model, chat_backend, think, asked=name, note=f"missing: {exc}")
    elif name == chat_model:
        return fallback
    # is the model there? (an own server that lists nothing is taken at its word)
    try:
        listed = list(backend.list_models() or [])
    except Exception:
        listed = []
    if (listed and name not in listed) or (not listed and backend is chat_backend):
        return Choice(role, chat_model, chat_backend, think, asked=name, note="missing")
    # where does it run, and may this job go there?
    from .inference.registry import endpoint
    cls, host = egress.classify_url(endpoint(backend) or "http://127.0.0.1")
    remote = _remote(backend, name)
    if remote:
        cls, host = egress.THIRD_PARTY, remote
    if cls == egress.THIRD_PARTY:
        policy = egress.policy()
        carries = (role in _WITH_PASSAGES) if passages is None else passages
        if not policy.authorised(host):
            return Choice(role, chat_model, chat_backend, think, asked=name,
                          note=f"blocked: {name} runs at {host}, which is not authorised")
        if carries and not policy.third_party_passages:
            return Choice(role, chat_model, chat_backend, think, asked=name,
                          note=f"blocked: {name} runs at {host}, authorised for questions only")
    return Choice(role, name, backend, think, own=True,
                  where=host if cls == egress.THIRD_PARTY else "")
