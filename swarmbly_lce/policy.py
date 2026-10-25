"""Learning policy (SPEC 5.2, invariant I8).

The policy is the written record of what the user allows the system to learn
from each source. Rules are matched by longest path prefix; a source that no
rule covers falls back to ``defaults``, whose own default is
``reference_only = true``: **what is not declared does not train**.

Policies are stored as JSON (always available) or YAML (when PyYAML is
installed). Unknown keys are rejected so a typo cannot silently widen what is
trained on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .errors import PolicyError

__all__ = ["SourceRule", "LearningPolicy"]

_FIELDS = {
    "authored_by_user",
    "wiki",
    "learn_style",
    "learn_procedure",
    "learn_preference",
    "retain_episodic",
    "train",
    "reference_only",
}


@dataclass(frozen=True)
class SourceRule:
    """Effective permissions for one source."""

    authored_by_user: bool = False
    wiki: bool = True
    learn_style: bool = False
    learn_procedure: bool = False
    learn_preference: bool = False
    retain_episodic: bool = False
    train: bool = True
    reference_only: bool = True

    @property
    def trainable(self) -> bool:
        """Whether any claim from this source may ever reach TRAINABLE."""
        return self.train and not self.reference_only

    def allows_type(self, claim_type: str) -> bool:
        """Whether a behavioural claim of ``claim_type`` may become TRAINABLE."""
        if not self.trainable:
            return False
        if claim_type == "style":
            return self.learn_style and self.authored_by_user
        if claim_type == "procedure":
            return self.learn_procedure
        if claim_type == "preference":
            return self.learn_preference or self.learn_style or self.learn_procedure
        return False


def _rule_from(raw: Mapping[str, Any], base: SourceRule) -> SourceRule:
    unknown = set(raw) - _FIELDS
    if unknown:
        raise PolicyError(f"unknown policy keys: {sorted(unknown)}")
    for k, v in raw.items():
        if not isinstance(v, bool):
            raise PolicyError(f"policy key {k!r} must be boolean, got {type(v).__name__}")
    rule = replace(base, **dict(raw))
    # Declaring any learning permission implies the source is not reference-only,
    # unless the user said so explicitly.
    if "reference_only" not in raw and any(raw.get(k) for k in ("learn_style", "learn_procedure", "learn_preference")):
        rule = replace(rule, reference_only=False)
    if raw.get("train") is False:
        rule = replace(rule, reference_only=True)
    return rule


@dataclass
class LearningPolicy:
    """Longest-prefix policy over source paths (POSIX-style, relative)."""

    defaults: SourceRule = field(default_factory=SourceRule)
    rules: dict[str, SourceRule] = field(default_factory=dict)
    version: str = "0.1"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LearningPolicy":
        root = data.get("learning_policy", data)
        if not isinstance(root, Mapping):
            raise PolicyError("learning_policy must be a mapping")
        allowed = {"v", "defaults", "sources"}
        unknown = set(root) - allowed
        if unknown:
            raise PolicyError(f"unknown top-level policy keys: {sorted(unknown)}")
        defaults = _rule_from(root.get("defaults", {}) or {}, SourceRule())
        rules: dict[str, SourceRule] = {}
        for prefix, raw in (root.get("sources", {}) or {}).items():
            if not isinstance(raw, Mapping):
                raise PolicyError(f"rule for {prefix!r} must be a mapping")
            # Each rule starts from a conservative base, not from the defaults,
            # so a permissive default cannot leak into a narrowly declared folder.
            rules[_norm(prefix)] = _rule_from(raw, SourceRule())
        return cls(defaults=defaults, rules=rules, version=str(root.get("v", "0.1")))

    @classmethod
    def load(cls, path: str | Path) -> "LearningPolicy":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        if p.suffix in {".yaml", ".yml"}:
            try:
                import yaml  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise PolicyError("YAML policy requires PyYAML; use JSON instead") from exc
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(text)
        return cls.from_mapping(data)

    def rule_for(self, source: str) -> SourceRule:
        s = _norm(source)
        best, best_len = self.defaults, -1
        for prefix, rule in self.rules.items():
            if (s == prefix or s.startswith(prefix.rstrip("/") + "/") or prefix == "") and len(prefix) > best_len:
                best, best_len = rule, len(prefix)
        return best

    def fingerprint(self, source: str) -> str:
        """Stable string of the effective rule, recorded in the dependency graph."""
        r = self.rule_for(source)
        return json.dumps(r.__dict__, sort_keys=True)


def _norm(path: str) -> str:
    p = str(PurePosixPath(path.replace("\\", "/")))
    return "" if p == "." else p.lstrip("/")
