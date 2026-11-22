"""Editing skills — reusable recipes the AI editor can load on demand.

A skill is a folder with a ``SKILL.md`` file:

  ~/.config/vidmill/skills/my-style/SKILL.md
  .vmill/skills/my-style/SKILL.md          (project scope)
  vidmill/skill_data/tight-cut/SKILL.md    (bundled)

The file starts with a small frontmatter block, followed by Markdown
instructions.  The model only sees each skill's name and description
until it calls the ``skill`` tool, so large skill libraries stay cheap.

Discovery order is bundled -> user -> project: a later skill with the
same name overrides the earlier one.  Writes always go to a writable
scope (user or project); bundled skills are never modified in place.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

SKILL_FILE = "SKILL.md"
MAX_BODY = 50000
MAX_DESCRIPTION = 400
MAX_TAGS = 12
MAX_SELECTED = 4
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
SCOPES = ("bundled", "user", "project")
WRITE_SCOPES = ("user", "project")


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    body: str
    tags: tuple[str, ...]
    path: Path
    source: str
    raw: str

    @property
    def root(self) -> Path:
        return self.path.parent.parent


# --------------------------------------------------------------------- paths

def bundled_root() -> Path:
    return Path(__file__).resolve().parent / "skill_data"


def user_root() -> Path:
    override = os.environ.get("VIDMILL_SKILLS_DIR")
    if override:
        return Path(os.path.expanduser(override)).resolve()
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return (Path(os.path.expanduser(base)) / "vidmill" / "skills").resolve()
    return (Path.home() / ".config" / "vidmill" / "skills").resolve()


def project_root() -> Path:
    override = os.environ.get("VIDMILL_PROJECT_DIR")
    base = Path(os.path.expanduser(override)).resolve() if override else Path.cwd()
    return base / ".vmill" / "skills"


def roots() -> dict[str, Path]:
    return {"bundled": bundled_root(), "user": user_root(), "project": project_root()}


def ensure_scope(scope: str) -> Path:
    if scope not in WRITE_SCOPES:
        raise ValueError(f"scope must be one of {', '.join(WRITE_SCOPES)}")
    path = roots()[scope]
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------- validation

def clean_name(value: str) -> str:
    name = str(value or "").strip().lower()
    if not NAME_RE.match(name):
        raise ValueError("skill name must be lowercase letters, digits or dashes "
                         "(1-64 characters, starting with a letter or digit)")
    return name


def clean_scope(value: str | None, default: str = "user") -> str:
    scope = str(value or default).strip().lower()
    if scope not in WRITE_SCOPES:
        raise ValueError(f"scope must be one of {', '.join(WRITE_SCOPES)}")
    return scope


def parse_tags(value) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            text = text[1:-1]
        parts = re.split(r"[,;]", text)
    else:
        parts = list(value)
    out: list[str] = []
    seen: set[str] = set()
    for part in parts:
        tag = str(part).strip().strip("#")
        if not tag:
            continue
        if len(tag) > 32:
            raise ValueError(f"tag is too long: {tag!r}")
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            out.append(tag)
    if len(out) > MAX_TAGS:
        raise ValueError(f"a skill can have at most {MAX_TAGS} tags")
    return tuple(out)


def _clean_description(value) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueError("skill description is required — say when the AI should use it")
    if len(text) > MAX_DESCRIPTION:
        raise ValueError(f"skill description is limited to {MAX_DESCRIPTION} characters")
    return text


def _clean_body(value) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("skill instructions are required — add a Markdown body")
    if len(text) > MAX_BODY:
        raise ValueError(f"skill body is limited to {MAX_BODY} characters")
    return text


# ------------------------------------------------------------- frontmatter

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing frontmatter: the file must start with ---")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() in ("---", "...")), None)
    if end is None:
        raise ValueError("frontmatter is not closed with ---")

    meta: dict = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[:1].isspace():          # nested metadata we don't need
            i += 1
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line!r}")
        key, value = line.split(":", 1)
        key, value = key.strip().lower(), value.strip()
        if value in (">", ">-", "|", "|-"):
            block: list[str] = []
            i += 1
            while i < end and (not lines[i].strip() or lines[i][:1].isspace()):
                block.append(lines[i].strip())
                i += 1
            joiner = " " if value.startswith(">") else "\n"
            meta[key] = joiner.join(x for x in block if x).strip()
            continue
        if not value and i + 1 < end and lines[i + 1].lstrip().startswith("- "):
            items: list[str] = []
            i += 1
            while i < end and (not lines[i].strip()
                               or lines[i].lstrip().startswith("- ")):
                item = lines[i].strip()
                if item.startswith("- "):
                    items.append(item[2:].strip().strip("\"'"))
                i += 1
            meta[key] = items
            continue
        if len(value) >= 2 and value[0] == value[-1] == '"':
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        elif len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1].replace("''", "'")
        meta[key] = value
        i += 1
    body = "\n".join(lines[end + 1:]).strip()
    return meta, body


def render_skill(name: str, description: str, body: str,
                 tags: tuple[str, ...] = ()) -> str:
    lines = [
        "---",
        f"name: {name}",
        "description: " + json.dumps(description, ensure_ascii=False),
    ]
    if tags:
        lines.append("tags: " + ", ".join(tags))
    lines += ["---", "", body.strip(), ""]
    return "\n".join(lines)


def _read_skill(path: Path, source: str) -> Skill:
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)
    folder = path.parent.name
    name = str(meta.get("name") or folder).strip().lower()
    if not NAME_RE.match(name):
        raise ValueError(f"invalid skill name {name!r}")
    if name != folder:
        raise ValueError(f"frontmatter name {name!r} must match folder {folder!r}")
    description = _clean_description(meta.get("description"))
    body = _clean_body(body)
    tags = parse_tags(meta.get("tags"))
    return Skill(name=name, description=description, body=body, tags=tags,
                 path=path, source=source, raw=text)


# ---------------------------------------------------------------- discovery

def _scan() -> tuple[list[Skill], list[dict]]:
    found: list[Skill] = []
    warnings: list[dict] = []
    for source in SCOPES:
        root = roots()[source]
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError as e:
            warnings.append({"path": str(root), "error": str(e)})
            continue
        for folder in entries:
            if not folder.is_dir() or folder.name.startswith("."):
                continue
            path = folder / SKILL_FILE
            if not path.is_file():
                warnings.append({"path": str(folder),
                                 "error": f"missing {SKILL_FILE}"})
                continue
            try:
                found.append(_read_skill(path, source))
            except (OSError, ValueError) as e:
                warnings.append({"path": str(path), "error": str(e)})
    return found, warnings


def scan() -> tuple[list[Skill], list[dict]]:
    """Every valid skill file, including shadowed ones, plus parse warnings."""
    return _scan()


def discover_with_warnings() -> tuple[list[Skill], list[dict]]:
    """Effective skills after overrides, plus parse warnings."""
    found, warnings = _scan()
    effective: dict[str, Skill] = {}
    for skill in found:
        effective[skill.name] = skill
    return sorted(effective.values(), key=lambda s: s.name), warnings


def discover() -> list[Skill]:
    return discover_with_warnings()[0]


def summary(skill: Skill) -> dict:
    out = {
        "name": skill.name,
        "description": skill.description,
        "tags": list(skill.tags),
        "source": skill.source,
        "path": str(skill.path),
    }
    if skill.source != "bundled":
        bundled = raw(skill.name, "bundled")
        if bundled is not None:
            out["overrides"] = "bundled"
    return out


def read_scope(name: str, scope: str) -> Skill:
    name = clean_name(name)
    if scope not in SCOPES:
        raise ValueError(f"scope must be one of {', '.join(SCOPES)}")
    path = roots()[scope] / name / SKILL_FILE
    if not path.is_file():
        raise FileNotFoundError(f"no {scope} skill named {name!r}")
    return _read_skill(path, scope)


def raw(name: str, scope: str) -> Skill | None:
    try:
        return read_scope(name, scope)
    except (OSError, ValueError, FileNotFoundError):
        return None


def find(name: str) -> Skill | None:
    name = clean_name(name)
    return next((s for s in discover() if s.name == name), None)


def load(name: str) -> Skill:
    skill = find(name)
    if skill is None:
        names = ", ".join(s.name for s in discover()) or "(none)"
        raise FileNotFoundError(f"unknown skill {name!r} — available: {names}")
    return skill


def resolve_many(names) -> list[Skill]:
    if names is None:
        return []
    if isinstance(names, str):
        names = [names]
    out: list[Skill] = []
    seen: set[str] = set()
    for value in names:
        name = str(value or "").strip()
        if not name:
            continue
        skill = load(name)
        if skill.name not in seen:
            seen.add(skill.name)
            out.append(skill)
    if len(out) > MAX_SELECTED:
        raise ValueError(f"choose at most {MAX_SELECTED} skills for one request")
    return out


# ------------------------------------------------------------------- writes

def _write(skill: Skill, scope: str) -> Skill:
    root = ensure_scope(scope)
    path = root / skill.name / SKILL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    text = render_skill(skill.name, skill.description, skill.body, skill.tags)
    tmp = path.with_name(".SKILL.md.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    return _read_skill(path, scope)


def upsert(name: str, description: str, body: str, tags=(),
           scope: str = "user") -> Skill:
    name = clean_name(name)
    scope = clean_scope(scope)
    skill = Skill(name=name, description=_clean_description(description),
                  body=_clean_body(body), tags=parse_tags(tags),
                  path=Path(), source=scope, raw="")
    return _write(skill, scope)


def update(name: str, description: str | None = None,
           body: str | None = None, tags=None, scope: str = "user") -> Skill:
    name = clean_name(name)
    scope = clean_scope(scope)
    existing = load(name)
    new_description = existing.description if description is None else _clean_description(description)
    new_body = existing.body if body is None else _clean_body(body)
    new_tags = existing.tags if tags is None else parse_tags(tags)
    skill = Skill(name=name, description=new_description, body=new_body,
                  tags=new_tags, path=Path(), source=scope, raw="")
    return _write(skill, scope)


def _remove_file(name: str, scope: str) -> Path | None:
    path = roots()[scope] / name / SKILL_FILE
    if not path.is_file():
        return None
    path.unlink()
    try:
        path.parent.rmdir()
    except OSError:
        pass
    return path


def remove(name: str, scope: str = "user") -> Path:
    name = clean_name(name)
    scope = clean_scope(scope)
    path = _remove_file(name, scope)
    if path is None:
        raise FileNotFoundError(f"no {scope} skill named {name!r}")
    return path


def reset(name: str, scopes=("user", "project")) -> list[Path]:
    name = clean_name(name)
    if isinstance(scopes, str):
        scopes = (scopes,)
    removed: list[Path] = []
    for scope in scopes:
        if scope not in WRITE_SCOPES:
            raise ValueError(f"scope must be one of {', '.join(WRITE_SCOPES)}")
        path = _remove_file(name, scope)
        if path is not None:
            removed.append(path)
    return removed
