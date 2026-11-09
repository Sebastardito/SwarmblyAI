"""Projects (3.1): a folder of your own for each piece of work.

A project is an ordinary folder, by default ``Documents/Swarmbly/<Project>``::

    <Project>/
      swarmbly-project.json   identity and settings (no secrets, ever)
      sources/                the project's documents (C1 reads them)
      memory/                 the project's memory: glossary, notes
      chats/                  one JSON file per conversation, kept up to date
      exports/                .swarmbly packages of this project

The folder is the project: copying it, or exporting it as a ``.swarmbly``
package and restoring it on another computer, keeps its chats, sources and
memory, and the citations of old answers still resolve (they name a file by
the hash of its content, not by its path).

Isolation: a conversation in a project reads only that project's ``sources``
and ``memory``; the personal sources are added only if the project says so
(``include_personal``), and a personal conversation never reads a project.

The app's database is the live index; the ``chats/`` files are what travels.
When a project is opened, its chats missing from the database are imported.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

PROJECT_FILE = "swarmbly-project.json"
PROJECT_SCHEMA = "swarmbly.project/1"
CHAT_SCHEMA = "swarmbly.chat/1"
PACKAGE_SCHEMA = "swarmbly.package/1"
PACKAGE_SUFFIX = ".swarmbly"
MANIFEST = "manifest.json"
SUBFOLDERS = ("sources", "memory", "chats", "exports")
PACKED = ("sources", "memory", "chats")          # exports/ never goes into a package
MAX_PACKAGE_BYTES = 2 * 1024 ** 3


APP_NOTE = (
    "Put this project's documents in sources/ (text, Markdown, Word, HTML, PDF).\n"
    "memory/ holds what the project remembers: notes saved from the chat, and a glossary.\n"
    "Pon los documentos de este proyecto en sources/ (texto, Markdown, Word, HTML, PDF).\n"
    "memory/ guarda lo que el proyecto recuerda: notas guardadas desde el chat y un glosario.\n")
MEMORY_NOTES = "notas.md"            # memory/notas.md: notes saved from the chat


def is_app_note(path: Path) -> bool:
    """The instructions file the app wrote into sources/ in 0.4.0 dev builds:
    not one of the user's documents (it was retrieved for every question)."""
    if path.name != "LEEME.txt" or path.parent.name != "sources":
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:80]
    except OSError:
        return False
    return head.startswith(("Put this project's documents here", "Put this project's documents in"))


def save_note(folder: Path, text: str, title: str = "Memoria") -> Path:
    """Append one note to ``folder/notas.md`` as its own paragraph, dated.
    Written locally only; C1 reads it back like any other document."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / MEMORY_NOTES
    note = " ".join(text.split())
    if note and note[-1] not in ".!?…":
        note += "."
    stamp = time.strftime("%Y-%m-%d")
    if path.is_file() and f" · {note}\n" in path.read_text(encoding="utf-8"):
        return path                   # the same note is not saved twice (4th test: refs x2)
    with open(path, "a", encoding="utf-8") as fh:
        if path.stat().st_size == 0:
            fh.write(f"# {title}\n\n")
        elif not path.read_text(encoding="utf-8").endswith("\n"):
            fh.write("\n\n")        # a file edited by hand may end without a newline
        fh.write(f"{stamp} · {note}\n\n")
    return path


GLOSSARY_FILE = "glosario.md"


def _gloss_key(line: str) -> str:
    """The concept a glossary line is about: its term, without accents, case
    or a plural ending."""
    import unicodedata
    if " = " not in line or line.lstrip().startswith("#"):
        return ""
    term = line.split(" = ", 1)[0].strip().lower()
    term = "".join(c for c in unicodedata.normalize("NFKD", term) if not unicodedata.combining(c))
    return term[:-1] if len(term) > 4 and term.endswith("s") else term


def _parse_gloss(line: str) -> tuple[str, list[str], dict[str, list[str]]]:
    term, _, right = line.partition(" = ")
    parts = [x.strip() for x in right.split("|")]
    eqs = [e.strip() for e in parts[0].split(",") if e.strip()]
    meta: dict[str, list[str]] = {}
    for seg in parts[1:]:
        key, _, val = seg.partition(":")
        meta.setdefault(key.strip(), [])
        meta[key.strip()] += [v.strip() for v in val.split(",") if v.strip()]
    return term.strip(), eqs, meta


def _merge_gloss(old: str, new: str) -> str:
    """Both lines' equivalents and metadata, under the older line's term."""
    term, eqs, meta = _parse_gloss(old)
    _, eqs2, meta2 = _parse_gloss(new)
    key = _gloss_key(old)
    out = [e for e in dict.fromkeys([*eqs, *eqs2]) if _gloss_key(f"{e} = x") != key] or [term]
    for k, vals in meta2.items():
        if k == "wd" and meta.get("wd"):
            continue                       # the first chosen item stays
        meta[k] = list(dict.fromkeys([*meta.get(k, []), *vals]))
    line = f"{term} = {', '.join(out)}"
    for k, vals in meta.items():
        if vals:
            line += f" | {k}: {', '.join(vals)}"
    return line


_BULLET = re.compile(r"^\s*[-*]\s+")


def _is_entry(line: str) -> bool:
    return " = " in line and not line.lstrip().startswith("#")


def save_glossary(folder: Path, lines: list[str], title: str = "Glosario") -> Path:
    """Add ``term = equivalents`` entries to ``folder/glosario.md`` (the format
    C1 reads), one Markdown list item per entry.

    Plain lines one under another are a single paragraph in Markdown, so a
    viewer (Finder, Obsidian, GitHub) showed the whole glossary run together
    (sixth test); "- term = …" keeps one entry per line everywhere, and C1
    reads both. Older plain lines are rewritten as list items."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / GLOSSARY_FILE
    raw = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    # every line, with entries kept bare ("term = …") while they are compared
    doc = [(_BULLET.sub("", ln).strip(), True) if _is_entry(ln) else (ln, False) for ln in raw]
    have = [ln for ln, entry in doc if entry]
    new = []
    for ln in lines:
        bare = _BULLET.sub("", ln or "").strip()
        if bare and bare not in have and bare not in new:
            new.append(bare)
    # a correction replaces an older line that equated the wrong form with the term
    # ("introgresión = introgradión" before "| no:" existed, 4th test)
    def stale(ln: str) -> bool:
        for nl in new:
            if " | no: " not in nl:
                continue
            term = nl.split(" = ", 1)[0].strip().lower()
            wrong = {w.strip().lower() for w in nl.split(" | no: ", 1)[1].split(",")}
            left, _, right = ln.partition(" = ")
            if left.strip().lower() == term and " | no: " not in ln and \
                    {w.strip().lower() for w in right.split(",")} & wrong:
                return True
        return False
    doc = [(ln, entry) for ln, entry in doc if not (entry and stale(ln))]
    # one line per concept: "cucuve = Mimus, mockingbird" joins "cucuves = Mimus |
    # distinto: cucujo" instead of becoming a second line (sixth test)
    for nl in new:
        key = _gloss_key(nl)
        at = next((i for i, (ln, entry) in enumerate(doc)
                   if entry and key and _gloss_key(ln) == key), None)
        if at is None:
            doc.append((nl, True))
        else:
            doc[at] = (_merge_gloss(doc[at][0], nl), True)
    if not any(ln.lstrip().startswith("#") for ln, entry in doc if not entry):
        doc = [(f"# {title}", False), ("", False), *doc]
    out = [f"- {ln}" if entry else ln for ln, entry in doc]
    path.write_text("\n".join(out).rstrip("\n") + "\n", encoding="utf-8")
    return path


class ProjectError(ValueError):
    """A request about projects that cannot be done; the message says why."""


# ---------------------------------------------------------------------------
# Where projects live, and whether a cloud service syncs that place
# ---------------------------------------------------------------------------

def default_parent() -> Path:
    """``Documents/Swarmbly`` in the user's home (``SWARMBLY_PROJECTS_DIR`` overrides)."""
    override = os.environ.get("SWARMBLY_PROJECTS_DIR")
    if override:
        return Path(override).expanduser()
    home = Path.home()
    for name in ("Documents", "Documentos", "Documenti", "Dokumente"):
        if (home / name).is_dir():
            return home / name / "Swarmbly"
    return home / "Documents" / "Swarmbly"


_CLOUD_MARKERS = (
    ("Mobile Documents", "iCloud Drive"), ("iCloud", "iCloud Drive"),
    ("CloudStorage", "a cloud service (Google Drive, OneDrive, Dropbox…)"),
    ("Dropbox", "Dropbox"), ("OneDrive", "OneDrive"), ("Google Drive", "Google Drive"),
    ("GoogleDrive", "Google Drive"), ("pCloud", "pCloud"), ("Box Sync", "Box"),
    ("Nextcloud", "Nextcloud"), ("Sync.com", "Sync.com"),
)


def cloud_sync(path: Path, home: Path | None = None) -> str:
    """The service that syncs ``path``, or "" if none is detected.

    A synced folder can be emptied to save space (the files stay "in the
    cloud" until opened) and can get conflicting copies ("chat 2.json"):
    both break a project that is open in the app. The check is by path; on
    macOS it also detects Desktop and Documents synced by iCloud.
    """
    path = Path(path).expanduser()
    parts = [p.lower() for p in path.parts]
    for marker, service in _CLOUD_MARKERS:
        if marker.lower() in parts or any(marker.lower() in p for p in parts):
            return service
    home = home or Path.home()
    if sys.platform == "darwin":
        icloud = home / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
        for name in ("Documents", "Desktop"):
            try:
                inside = path.resolve().is_relative_to((home / name).resolve())
            except (OSError, ValueError):
                inside = False
            if inside and (icloud / name).is_dir():
                return "iCloud Drive (Desktop and Documents)"
    return ""


def cloud_warning(path: Path) -> str:
    service = cloud_sync(path)
    if not service:
        return ""
    return (f"This folder is synced by {service}. The service may move files to the cloud "
            "to save space or create duplicate copies (\"name 2\"), and an open project can "
            "break. Prefer a folder that is not synced, or keep this one always on this "
            "computer.")


# ---------------------------------------------------------------------------
# One project
# ---------------------------------------------------------------------------

_SAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def folder_name(name: str) -> str:
    clean = " ".join(_SAFE_NAME.sub(" ", name).split()).strip(" .")
    return clean[:80] or "Project"


@dataclass
class Project:
    id: str
    name: str
    path: Path
    created_at: float = field(default_factory=time.time)
    include_personal: bool = False
    description: str = ""

    # -- layout ------------------------------------------------------------
    @property
    def sources(self) -> Path:
        return self.path / "sources"

    @property
    def memory(self) -> Path:
        return self.path / "memory"

    @property
    def chats(self) -> Path:
        return self.path / "chats"

    @property
    def exports(self) -> Path:
        return self.path / "exports"

    def roots(self) -> list[Path]:
        """Folders C1 reads in this project (its documents and its memory)."""
        return [self.sources, self.memory]

    # -- file ----------------------------------------------------------------
    def to_file(self) -> dict[str, Any]:
        return {"schema": PROJECT_SCHEMA, "id": self.id, "name": self.name,
                "created_at": self.created_at, "include_personal": self.include_personal,
                "description": self.description}

    def save(self) -> None:
        self.path.mkdir(parents=True, exist_ok=True)
        for sub in SUBFOLDERS:
            (self.path / sub).mkdir(exist_ok=True)
        _write_json(self.path / PROJECT_FILE, self.to_file())

    @classmethod
    def load(cls, path: Path) -> "Project":
        path = Path(path).expanduser()
        try:
            data = json.loads((path / PROJECT_FILE).read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ProjectError(f"{path} is not a Swarmbly project (no {PROJECT_FILE})") from None
        except (OSError, ValueError) as exc:
            raise ProjectError(f"{path / PROJECT_FILE} cannot be read: {exc}") from None
        if data.get("schema") != PROJECT_SCHEMA or not data.get("id"):
            raise ProjectError(f"{path / PROJECT_FILE} is not a project file this version reads")
        return cls(id=str(data["id"]), name=str(data.get("name") or path.name), path=path,
                   created_at=float(data.get("created_at") or time.time()),
                   include_personal=bool(data.get("include_personal", False)),
                   description=str(data.get("description") or ""))

    def describe(self) -> dict[str, Any]:
        out = {key: v for key, v in asdict(self).items() if key != "path"}
        out["path"] = str(self.path)
        out["available"] = (self.path / PROJECT_FILE).is_file()
        out["cloud_warning"] = cloud_warning(self.path)
        return out

    # -- chats -----------------------------------------------------------------
    def chat_file(self, conversation_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", conversation_id):
            raise ProjectError("invalid conversation id")
        return self.chats / f"{conversation_id}.json"

    def write_chat(self, conversation: dict[str, Any], messages: list[dict[str, Any]]) -> Path:
        path = self.chat_file(str(conversation["id"]))
        self.chats.mkdir(parents=True, exist_ok=True)
        _write_json(path, {"schema": CHAT_SCHEMA, "project_id": self.id,
                           "conversation": conversation, "messages": messages})
        return path

    def read_chats(self) -> Iterable[dict[str, Any]]:
        if not self.chats.is_dir():
            return
        for path in sorted(self.chats.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if data.get("schema") == CHAT_SCHEMA and isinstance(data.get("conversation"), dict):
                yield data


def _write_json(path: Path, data: Any) -> None:
    """Write through a temporary file, so a crash never leaves half a file."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# The projects this app knows about
# ---------------------------------------------------------------------------

class ProjectRegistry:
    """Projects registered in this app (their folders), kept in the config
    under ``projects``: ``{"items": [{"id", "path"}], "active": ""}``."""

    def __init__(self, config_get: Callable[[], dict[str, Any]],
                 config_update: Callable[[dict[str, Any]], Any]):
        self._get = config_get
        self._update = config_update

    def _state(self) -> dict[str, Any]:
        state = (self._get().get("projects") or {})
        return {"items": list(state.get("items") or []), "active": str(state.get("active") or "")}

    def _save(self, items: list[dict[str, str]], active: str) -> None:
        self._update({"projects.items": items, "projects.active": active})

    def list(self) -> list[Project | dict[str, Any]]:
        out: list[Project | dict[str, Any]] = []
        for item in self._state()["items"]:
            try:
                out.append(Project.load(Path(item["path"])))
            except ProjectError as exc:
                out.append({"id": item.get("id", ""), "path": item.get("path", ""),
                            "name": Path(item.get("path", "")).name, "available": False,
                            "error": str(exc)})
        return out

    def describe(self) -> list[dict[str, Any]]:
        return [p.describe() if isinstance(p, Project) else p for p in self.list()]

    def get(self, project_id: str) -> Project | None:
        if not project_id:
            return None
        for item in self._state()["items"]:
            if item.get("id") == project_id:
                try:
                    return Project.load(Path(item["path"]))
                except ProjectError:
                    return None
        return None

    def require(self, project_id: str) -> Project:
        project = self.get(project_id)
        if project is None:
            raise ProjectError(f"unknown or unavailable project {project_id!r}")
        return project

    @property
    def active_id(self) -> str:
        return self._state()["active"]

    def set_active(self, project_id: str) -> None:
        state = self._state()
        if project_id and not any(i.get("id") == project_id for i in state["items"]):
            raise ProjectError(f"unknown project {project_id!r}")
        self._save(state["items"], project_id)

    def register(self, project: Project) -> Project:
        state = self._state()
        for item in state["items"]:
            if item.get("id") == project.id:
                if Path(item["path"]).expanduser() != project.path:
                    raise ProjectError(
                        f"a project with the same identity is already open here "
                        f"({item['path']}); restore it as a copy")
                return project
        state["items"].append({"id": project.id, "path": str(project.path)})
        self._save(state["items"], state["active"])
        return project

    def create(self, name: str, parent: str | Path | None = None,
               include_personal: bool = False) -> Project:
        name = " ".join((name or "").split())
        if not name:
            raise ProjectError("a project needs a name")
        base = Path(parent).expanduser() if parent else default_parent()
        path = _unique(base / folder_name(name))
        project = Project(id=uuid.uuid4().hex[:16], name=name, path=path,
                          include_personal=include_personal)
        project.save()
        (project.path / "LEEME.txt").write_text(APP_NOTE, encoding="utf-8")
        return self.register(project)

    def open(self, path: str | Path) -> Project:
        return self.register(Project.load(Path(path)))

    def forget(self, project_id: str) -> None:
        """Remove from this app; the folder and its files stay where they are."""
        state = self._state()
        items = [i for i in state["items"] if i.get("id") != project_id]
        self._save(items, "" if state["active"] == project_id else state["active"])

    def update(self, project_id: str, **changes: Any) -> Project:
        project = self.require(project_id)
        if "name" in changes and str(changes["name"]).strip():
            project.name = " ".join(str(changes["name"]).split())
        if "include_personal" in changes:
            project.include_personal = bool(changes["include_personal"])
        if "description" in changes:
            project.description = str(changes["description"] or "")[:2000]
        project.save()
        return project


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    for n in range(2, 1000):
        candidate = path.with_name(f"{path.name} ({n})")
        if not candidate.exists():
            return candidate
    raise ProjectError(f"no free folder name near {path}")


# ---------------------------------------------------------------------------
# .swarmbly packages: export and restore
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _packed_files(project: Project) -> list[Path]:
    files = []
    for sub in PACKED:
        root = project.path / sub
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            rel = path.relative_to(project.path)
            if path.is_file() and not any(p.startswith(".") for p in rel.parts) \
                    and not path.is_symlink():
                files.append(path)
    return files


def export_package(project: Project, out: Path | None = None,
                   secrets: Iterable[str] = (), app_version: str = "") -> dict[str, Any]:
    """Write ``<Project>.swarmbly`` (a zip): the project file, sources,
    memory and chats, and a manifest with the SHA-256 of every file.

    ``secrets`` are the user's stored keys: if any file contains one, the
    export stops and names the file, so a package never carries a key.
    """
    files = _packed_files(project)
    keys = [s.encode("utf-8") for s in secrets if s and len(s) >= 8]
    entries, total = [], 0
    for path in [project.path / PROJECT_FILE, *files]:
        data_size = path.stat().st_size
        total += data_size
        if total > MAX_PACKAGE_BYTES:
            raise ProjectError("the project is larger than 2 GB; export its documents separately")
        if keys:
            blob = path.read_bytes()
            if any(k in blob for k in keys):
                raise ProjectError(f"{path.relative_to(project.path)} contains one of your API "
                                   "keys; remove it before exporting (nothing was written)")
        entries.append({"path": path.relative_to(project.path).as_posix(),
                        "sha256": _sha256(path), "bytes": data_size})
    manifest = {"schema": PACKAGE_SCHEMA, "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "app_version": app_version, "project": {"id": project.id, "name": project.name},
                "files": entries, "secrets": "none (API keys stay in this computer's keychain)"}
    if out is None:
        project.exports.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out = project.exports / f"{folder_name(project.name)}-{stamp}{PACKAGE_SUFFIX}"
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2))
        for entry in entries:
            zf.write(project.path / entry["path"], entry["path"])
    os.replace(tmp, out)
    return {"path": str(out), "files": len(entries), "bytes": out.stat().st_size,
            "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()}


def _safe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return (bool(name) and not p.is_absolute() and ".." not in p.parts and "\\" not in name
            and not re.match(r"^[A-Za-z]:", name))


def inspect_package(path: Path) -> dict[str, Any]:
    """Read and verify a package without unpacking it: every file of the
    manifest is present, with its hash, and nothing else is inside."""
    try:
        zf = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectError(f"not a .swarmbly package: {exc}") from None
    with zf:
        names = zf.namelist()
        if MANIFEST not in names:
            raise ProjectError("not a .swarmbly package: no manifest")
        try:
            manifest = json.loads(zf.read(MANIFEST).decode("utf-8"))
        except ValueError:
            raise ProjectError("the package manifest is not valid JSON") from None
        if manifest.get("schema") != PACKAGE_SCHEMA:
            raise ProjectError("this package was written by a version this app does not read")
        listed = {e["path"]: e for e in manifest.get("files") or []}
        if PROJECT_FILE not in listed:
            raise ProjectError("the package has no project file")
        extra = [n for n in names if n != MANIFEST and n not in listed and not n.endswith("/")]
        if extra:
            raise ProjectError(f"the package contains files its manifest does not list: {extra[:3]}")
        bad = []
        for name, entry in listed.items():
            if not _safe_member(name) or PurePosixPath(name).parts[0] not in (*PACKED, PROJECT_FILE):
                raise ProjectError(f"unsafe path in the package: {name!r}")
            if name not in names:
                bad.append(f"{name} (missing)")
                continue
            h = hashlib.sha256()
            with zf.open(name) as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    h.update(block)
            if h.hexdigest() != entry.get("sha256"):
                bad.append(f"{name} (hash differs)")
        if bad:
            raise ProjectError("the package is damaged or was modified: " + ", ".join(bad[:5]))
    chats = sum(1 for n in listed if n.startswith("chats/"))
    sources = sum(1 for n in listed if n.startswith("sources/"))
    return {"manifest": manifest, "files": len(listed), "chats": chats, "sources": sources}


def import_package(path: Path, registry: ProjectRegistry, parent: str | Path | None = None,
                   as_copy: bool = False) -> tuple[Project, dict[str, str]]:
    """Restore a verified package into a new folder and register it.

    If a project with the same identity is already open in this app, it is
    restored as a copy: new project id and new conversation ids (returned as
    ``{old: new}``), so nothing is merged into the existing one.
    """
    info = inspect_package(Path(path))
    manifest = info["manifest"]
    project_id = str(manifest["project"]["id"])
    name = str(manifest["project"].get("name") or "Project")
    clash = any(i.get("id") == project_id for i in registry._state()["items"])
    copy = as_copy or clash
    base = Path(parent).expanduser() if parent else default_parent()
    target = _unique(base / folder_name(name + (" (copy)" if copy else "")))
    target.mkdir(parents=True)
    with zipfile.ZipFile(path) as zf:
        for entry in manifest["files"]:
            dest = target / PurePosixPath(entry["path"])
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(entry["path"]) as src, open(dest, "wb") as fh:
                for block in iter(lambda: src.read(1 << 20), b""):
                    fh.write(block)
    project = Project.load(target)
    renamed: dict[str, str] = {}
    if copy:
        project.id = uuid.uuid4().hex[:16]
        project.name = name + " (copy)"
        for data in list(project.read_chats()):
            old = str(data["conversation"]["id"])
            new = uuid.uuid4().hex
            renamed[old] = new
            data["conversation"]["id"] = new
            data["project_id"] = project.id
            for m in data.get("messages") or []:
                m["conversation_id"] = new
                m["id"] = uuid.uuid4().hex
            (project.chats / f"{old}.json").unlink(missing_ok=True)
            _write_json(project.chats / f"{new}.json", data)
    project.save()
    for sub in SUBFOLDERS:
        (project.path / sub).mkdir(exist_ok=True)
    return registry.register(project), renamed
