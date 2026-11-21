"""Teams (3.5, D-019): named, stored plan templates.

A team is a plan written once and run many times. Each step has a name, an
instruction template (``{request}`` is replaced by the user's request), an
optional node role (``search``, ``corpus``, ``large_model``, ``reasoner``) and
dependencies on *earlier* steps only. Teams are templates, not agents: they
never choose a destination, never add a permission and never run a step on a
node the existing admission, lane/tier, egress or passage rules would refuse.

Storage is JSON under the app's data directory (``teams.json``) for the user,
and ``teams.json`` inside a project folder for teams that belong to that
project. Both files are validated on load and on save: at most ``MAX_STEPS``
steps, bounded names and instructions, known roles, unique ids and
dependencies only on earlier steps (so the graph is acyclic by construction).
Writes are atomic and private (mode 0600). Built-in example teams are shipped
in code, marked read-only and can only be duplicated.

The wire stays 0.2: a team becomes an ordinary plan and travels as ordinary
0.2 packets.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Callable

from .node_roles import NODE_ROLES

TEAMS_SCHEMA = "swarmbly.teams/1"
TEAMS_FILE = "teams.json"
MAX_STEPS = 12
MAX_TEAMS = 100
MAX_NAME = 60
MAX_STEP_NAME = 40
MAX_DESCRIPTION = 300
MAX_INSTRUCTION = 2000
REQUEST_PLACEHOLDER = "{request}"

_STEP_ID = re.compile(r"^[a-z][a-z0-9_-]{0,15}$")
_TEAM_ID = re.compile(r"^[A-Za-z0-9_-]{4,64}$")


class TeamError(ValueError):
    """A team operation refused with a stable code."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


E_TEAM_SCHEMA = "E_TEAM_SCHEMA"
E_TEAM_BUILTIN = "E_TEAM_BUILTIN"
E_TEAM_UNKNOWN = "E_TEAM_UNKNOWN"
E_TEAM_LIMIT = "E_TEAM_LIMIT"


def _text(value: Any, field: str, *, maximum: int, minimum: int = 1) -> str:
    text = str(value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise TeamError(E_TEAM_SCHEMA,
                        f"{field} must be between {minimum} and {maximum} characters")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in text) or "\x7f" in text:
        raise TeamError(E_TEAM_SCHEMA, f"{field} contains control characters")
    return text


def _new_team_id() -> str:
    return "team-" + uuid.uuid4().hex[:12]


def normalise_step(raw: Any, index: int, seen: list[str]) -> dict[str, Any]:
    """Validate one step and return the stored form (no unknown keys)."""
    if not isinstance(raw, dict):
        raise TeamError(E_TEAM_SCHEMA, f"step {index + 1} must be an object")
    step_id = str(raw.get("id") or f"s{index + 1}").strip()
    if not _STEP_ID.fullmatch(step_id):
        raise TeamError(E_TEAM_SCHEMA,
                        f"step {index + 1} id must start with a letter and use "
                        "lowercase letters, digits, '_' or '-' (max 16)")
    if step_id in seen:
        raise TeamError(E_TEAM_SCHEMA, f"step id {step_id!r} is repeated")
    name = _text(raw.get("name"), f"step {index + 1} name", maximum=MAX_STEP_NAME)
    instruction = _text(raw.get("instruction"),
                       f"step {index + 1} instruction", maximum=MAX_INSTRUCTION)
    role = str(raw.get("role") or "").strip()
    if role and role not in NODE_ROLES:
        raise TeamError(
            E_TEAM_SCHEMA,
            f"step {index + 1} role must be empty or one of "
            + ", ".join(NODE_ROLES))
    raw_deps = raw.get("depends_on")
    if raw_deps is None:
        raw_deps = raw.get("depends") or []
    if isinstance(raw_deps, str):
        raw_deps = [raw_deps]
    if not isinstance(raw_deps, list):
        raise TeamError(E_TEAM_SCHEMA,
                        f"step {index + 1} dependencies must be a list")
    depends: list[str] = []
    for dep in raw_deps:
        dep = str(dep or "").strip()
        if not dep:
            continue
        if dep == step_id:
            raise TeamError(E_TEAM_SCHEMA,
                            f"step {step_id!r} cannot depend on itself")
        if dep not in seen:
            # Only an earlier step may be a dependency, which also rules out
            # every cycle (a forward edge would be needed to close one).
            raise TeamError(
                E_TEAM_SCHEMA,
                f"step {step_id!r} depends on {dep!r}, which is not an earlier step")
        if dep not in depends:
            depends.append(dep)
    if len(depends) > MAX_STEPS:
        raise TeamError(E_TEAM_SCHEMA, "too many dependencies in one step")
    return {"id": step_id, "name": name, "instruction": instruction,
            "role": role, "depends_on": depends}


def normalise_team(raw: Any, *, team_id: str | None = None) -> dict[str, Any]:
    """Validate a team document (save and load share this function)."""
    if not isinstance(raw, dict):
        raise TeamError(E_TEAM_SCHEMA, "a team must be an object")
    name = _text(raw.get("name"), "team name", maximum=MAX_NAME)
    description = str(raw.get("description") or "").strip()
    if len(description) > MAX_DESCRIPTION:
        raise TeamError(E_TEAM_SCHEMA,
                        f"team description is longer than {MAX_DESCRIPTION} characters")
    if any(ord(ch) < 32 and ch not in "\n\t" for ch in description) \
            or "\x7f" in description:
        raise TeamError(E_TEAM_SCHEMA, "team description contains control characters")
    steps_raw = raw.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise TeamError(E_TEAM_SCHEMA, "a team needs at least one step")
    if len(steps_raw) > MAX_STEPS:
        raise TeamError(E_TEAM_SCHEMA,
                        f"a team has at most {MAX_STEPS} steps")
    steps: list[dict[str, Any]] = []
    seen: list[str] = []
    for index, item in enumerate(steps_raw):
        step = normalise_step(item, index, seen)
        seen.append(step["id"])
        steps.append(step)
    if not any(REQUEST_PLACEHOLDER in step["instruction"] for step in steps):
        raise TeamError(
            E_TEAM_SCHEMA,
            f"at least one step must contain the {REQUEST_PLACEHOLDER} placeholder")
    identifier = team_id or str(raw.get("id") or "")
    if identifier and not _TEAM_ID.fullmatch(identifier):
        raise TeamError(E_TEAM_SCHEMA, "team id has disallowed characters")
    return {"id": identifier or _new_team_id(), "name": name,
            "description": description, "steps": steps}


# ---------------------------------------------------------------------------
# Built-in examples (read-only; neutral wording)
# ---------------------------------------------------------------------------

_BUILTIN_DEFS: tuple[dict[str, Any], ...] = (
    {
        "id": "example-research-brief",
        "name": "Research brief",
        "description": "Public search, then the shared collection, then a draft "
                       "and a review.",
        "steps": [
            {"id": "s1", "name": "Public search", "role": "search",
             "instruction": "Find public, verifiable sources about: {request}. "
                            "Return the facts and their URLs; include no personal "
                            "details."},
            {"id": "s2", "name": "Shared collection", "role": "corpus",
             "depends_on": ["s1"],
             "instruction": "Look in the shared collection for material relevant "
                            "to: {request}. Quote only what the collection "
                            "contains and keep the citation it provides."},
            {"id": "s3", "name": "Draft", "role": "large_model",
             "depends_on": ["s2"],
             "instruction": "Write the answer to this request using the public "
                            "sources and the collection material above: {request}"},
            {"id": "s4", "name": "Review", "role": "reasoner",
             "depends_on": ["s3"],
             "instruction": "Review the draft against the request. Name any "
                            "unsupported claim and give the corrected final "
                            "answer. Request: {request}"},
        ],
    },
    {
        "id": "example-source-review",
        "name": "Source review",
        "description": "Answer from the shared collection and have a second "
                       "model check the claims.",
        "steps": [
            {"id": "s1", "name": "Collect material", "role": "corpus",
             "instruction": "Retrieve the passages of the shared collection that "
                            "answer: {request}"},
            {"id": "s2", "name": "Answer", "role": "large_model",
             "depends_on": ["s1"],
             "instruction": "Answer using only the collection passages above. "
                            "Say when they do not contain the answer. "
                            "Request: {request}"},
            {"id": "s3", "name": "Check", "role": "reasoner",
             "depends_on": ["s2"],
             "instruction": "Check the answer against the passages. Correct any "
                            "unsupported statement and return the final answer."},
        ],
    },
    {
        "id": "example-write-review",
        "name": "Write and review",
        "description": "A first draft by a large model, then an independent "
                       "review by a reasoning model.",
        "steps": [
            {"id": "s1", "name": "Write", "role": "large_model",
             "instruction": "Write the answer to this request: {request}"},
            {"id": "s2", "name": "Review", "role": "reasoner",
             "depends_on": ["s1"],
             "instruction": "Review the draft and return the corrected final "
                            "answer. Request: {request}"},
        ],
    },
)


def builtin_teams() -> list[dict[str, Any]]:
    """The shipped examples, validated like any other team and read-only."""
    out = []
    for raw in _BUILTIN_DEFS:
        team = normalise_team(raw, team_id=raw["id"])
        team["builtin"] = True
        team["project_id"] = ""
        out.append(team)
    return out


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

class TeamStore:
    """User-level and per-project team files, validated on every read/write."""

    def __init__(self, root: Path, *,
                 project_path: Callable[[str], Path | None] | None = None):
        self.root = Path(root)
        self.project_path = project_path or (lambda project_id: None)
        self._lock = threading.Lock()

    # -- files ---------------------------------------------------------------
    def user_file(self) -> Path:
        return self.root / TEAMS_FILE

    def project_file(self, project_id: str) -> Path | None:
        if not project_id:
            return None
        path = self.project_path(project_id)
        return Path(path) / TEAMS_FILE if path is not None else None

    def _file_for(self, project_id: str) -> Path:
        if not project_id:
            return self.user_file()
        path = self.project_file(project_id)
        if path is None:
            raise TeamError(E_TEAM_UNKNOWN, f"unknown project {project_id!r}")
        return path

    @staticmethod
    def _atomic_write(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp, path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass

    def _load_file(self, path: Path | None) -> list[dict[str, Any]]:
        if path is None or not path.is_file():
            return []
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise TeamError(E_TEAM_SCHEMA,
                            f"{path.name} cannot be read: {str(exc)[:120]}") from exc
        if not isinstance(raw, dict) or raw.get("schema") != TEAMS_SCHEMA:
            raise TeamError(E_TEAM_SCHEMA,
                            f"{path.name} is not a {TEAMS_SCHEMA} file")
        teams = raw.get("teams")
        if not isinstance(teams, list):
            raise TeamError(E_TEAM_SCHEMA, f"{path.name} has no teams list")
        if len(teams) > MAX_TEAMS:
            raise TeamError(E_TEAM_LIMIT,
                            f"{path.name} holds more than {MAX_TEAMS} teams")
        out: list[dict[str, Any]] = []
        for item in teams:
            team = normalise_team(item)
            team["builtin"] = False
            out.append(team)
        return out

    def _save_file(self, path: Path, teams: list[dict[str, Any]]) -> None:
        payload = {"schema": TEAMS_SCHEMA,
                   "teams": [{key: team.get(key) for key in
                              ("id", "name", "description", "steps")}
                             for team in teams]}
        self._atomic_write(path, payload)

    # -- reads ---------------------------------------------------------------
    def list_teams(self, project_id: str = "") -> list[dict[str, Any]]:
        with self._lock:
            user = self._load_file(self.user_file())
            project = self._load_file(self.project_file(project_id)) if project_id else []
        items = builtin_teams()
        used = {team["id"] for team in items}
        project_ids = {team["id"] for team in project}
        for team in [*user, *project]:
            if team["id"] in used:
                # A hand-edited file cannot shadow a built-in or another scope.
                raise TeamError(E_TEAM_SCHEMA,
                                f"team id {team['id']!r} is repeated")
            used.add(team["id"])
            items.append({**team,
                          "project_id": project_id if team["id"] in project_ids else ""})
        return items

    def payload(self, project_id: str = "") -> dict[str, Any]:
        teams = self.list_teams(project_id)
        return {"teams": teams, "schema": TEAMS_SCHEMA,
                "project_id": project_id,
                "storage": {"user": str(self.user_file()),
                            "project": (str(self.project_file(project_id))
                                        if project_id else "")},
                "limits": {"steps": MAX_STEPS, "name": MAX_NAME,
                           "step_name": MAX_STEP_NAME,
                           "instruction": MAX_INSTRUCTION,
                           "roles": list(NODE_ROLES)}}

    def find(self, team_id: str, project_id: str = "") -> dict[str, Any] | None:
        for team in self.list_teams(project_id):
            if team["id"] == team_id:
                return team
        return None

    def get(self, team_id: str, project_id: str = "") -> dict[str, Any]:
        team = self.find(team_id, project_id)
        if team is None:
            raise TeamError(E_TEAM_UNKNOWN, f"unknown team {team_id!r}")
        return team

    def _stored_scope(self, team_id: str, project_id: str
                      ) -> tuple[Path, list[dict[str, Any]]] | None:
        """The file and list where a stored team lives (project first)."""
        for path in (self.project_file(project_id), self.user_file()):
            teams = self._load_file(path)
            if any(team["id"] == team_id for team in teams):
                return path, teams
        return None

    # -- writes --------------------------------------------------------------
    def create(self, data: dict[str, Any], project_id: str = "") -> dict[str, Any]:
        path = self._file_for(project_id)
        with self._lock:
            teams = self._load_file(path)
            if len(teams) >= MAX_TEAMS:
                raise TeamError(E_TEAM_LIMIT,
                                f"at most {MAX_TEAMS} stored teams are allowed here")
            team = normalise_team(data)
            existing = {item["id"] for item in
                        [*builtin_teams(), *self._load_file(self.user_file()),
                         *(self._load_file(self.project_file(project_id))
                           if project_id else [])]}
            while team["id"] in existing:
                team["id"] = _new_team_id()
            teams.append(team)
            self._save_file(path, teams)
        return {**team, "builtin": False, "project_id": project_id}

    def update(self, team_id: str, data: dict[str, Any],
               project_id: str = "") -> dict[str, Any]:
        if any(team["id"] == team_id for team in builtin_teams()):
            raise TeamError(E_TEAM_BUILTIN,
                            "a built-in team is read-only; duplicate it to edit")
        with self._lock:
            found = self._stored_scope(team_id, project_id)
            if found is None:
                raise TeamError(E_TEAM_UNKNOWN, f"unknown team {team_id!r}")
            path, teams = found
            team = normalise_team(data, team_id=team_id)
            for index, item in enumerate(teams):
                if item["id"] == team_id:
                    teams[index] = team
                    break
            self._save_file(path, teams)
        scope = "project" if project_id and path == self.project_file(project_id) else ""
        return {**team, "builtin": False, "project_id": project_id if scope else ""}

    def delete(self, team_id: str, project_id: str = "") -> None:
        if any(team["id"] == team_id for team in builtin_teams()):
            raise TeamError(E_TEAM_BUILTIN,
                            "a built-in team is read-only; duplicate it to edit")
        with self._lock:
            found = self._stored_scope(team_id, project_id)
            if found is None:
                raise TeamError(E_TEAM_UNKNOWN, f"unknown team {team_id!r}")
            path, teams = found
            self._save_file(path, [team for team in teams if team["id"] != team_id])

    def duplicate(self, team_id: str, project_id: str = "",
                  name: str | None = None) -> dict[str, Any]:
        source = self.get(team_id, project_id)
        copy = {"name": (str(name or "").strip()
                         or f"{source['name']} (copy)"),
                "description": source.get("description") or "",
                "steps": json.loads(json.dumps(source["steps"]))}
        return self.create(copy, project_id=project_id)
