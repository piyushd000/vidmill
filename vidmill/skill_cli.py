"""CLI for editing skills: list, show, add, edit, reset, remove, check."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from . import skills
from . import util

PURPOSE = "list, read and edit reusable AI editing skills"


def add_args(p: argparse.ArgumentParser) -> None:
    sub = p.add_subparsers(dest="action", required=True)

    lp = sub.add_parser("list", help="list effective skills (bundled + user + project)")
    lp.add_argument("--json", action="store_true", help="machine-readable output")
    lp.add_argument("--all", action="store_true", help="include shadowed skill files")

    sp = sub.add_parser("show", help="print one skill's full SKILL.md")
    sp.add_argument("name")
    sp.add_argument("--json", action="store_true")

    ap = sub.add_parser("add", help="create a skill in the user (or project) scope")
    ap.add_argument("name")
    ap.add_argument("--description", help="one line: when the AI should use this skill")
    ap.add_argument("--tags", help="comma-separated tags")
    ap.add_argument("--body", help="Markdown instructions (or use --from)")
    ap.add_argument("--from", dest="from_", metavar="FILE",
                    help="read Markdown instructions from a file, or - for stdin")
    ap.add_argument("--scope", choices=list(skills.WRITE_SCOPES), default="user")
    ap.add_argument("--edit", action="store_true", help="open the new file in $EDITOR")
    ap.add_argument("--force", action="store_true", help="replace an existing skill")

    ep = sub.add_parser("edit", help="change a skill; bundled skills become user overrides")
    ep.add_argument("name")
    ep.add_argument("--description")
    ep.add_argument("--tags")
    ep.add_argument("--body")
    ep.add_argument("--from", dest="from_", metavar="FILE",
                    help="read Markdown instructions from a file, or - for stdin")
    ep.add_argument("--scope", choices=list(skills.WRITE_SCOPES), default="user")
    ep.add_argument("--edit", action="store_true", help="open the file in $EDITOR")

    rp = sub.add_parser("reset", help="remove overrides and restore the bundled skill")
    rp.add_argument("name")
    rp.add_argument("--scope", choices=["user", "project", "all"], default="all")

    dp = sub.add_parser("remove", help="delete a user or project skill")
    dp.add_argument("name")
    dp.add_argument("--scope", choices=list(skills.WRITE_SCOPES), default="user")

    cp = sub.add_parser("check", help="validate every skill file")
    cp.set_defaults(quiet=True)

    pp = sub.add_parser("path", help="show the bundled, user and project folders")
    pp.add_argument("--json", action="store_true")


def run(args: argparse.Namespace) -> None:
    try:
        if args.action == "list":
            return _list(args)
        if args.action == "show":
            return _show(args)
        if args.action == "add":
            return _add(args)
        if args.action == "edit":
            return _edit(args)
        if args.action == "reset":
            return _reset(args)
        if args.action == "remove":
            return _remove(args)
        if args.action == "check":
            return _check()
        return _path(args)
    except (ValueError, FileNotFoundError) as e:
        raise util.ToolError(str(e)) from e


# --------------------------------------------------------------------- input

def _body_arg(a) -> str | None:
    if getattr(a, "body", None) is not None and getattr(a, "from_", None) is not None:
        raise ValueError("use either --body or --from, not both")
    if getattr(a, "body", None) is not None:
        return a.body
    source = getattr(a, "from_", None)
    if not source:
        return None
    if source == "-":
        return sys.stdin.read()
    path = Path(source).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"file not found: {source}")
    return path.read_text(encoding="utf-8")


def _editor_argv() -> list[str]:
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        raise ValueError("set $EDITOR or $VISUAL to use --edit")
    argv = shlex.split(editor)
    if not argv or not shutil.which(argv[0]):
        raise ValueError(f"editor not found: {argv[0] if argv else editor}")
    return argv


def _open_editor(path: Path) -> None:
    argv = _editor_argv() + [str(path)]
    try:
        proc = subprocess.run(argv, check=False)
    except OSError as e:
        raise ValueError(f"could not start editor {argv[0]!r}: {e}") from e
    if proc.returncode != 0:
        raise ValueError(f"editor exited with status {proc.returncode}; the skill was saved but may need a fix")


def _scope_note(scope: str) -> None:
    print(f"stored in {scope} skills: {skills.roots()[scope]}")


# ----------------------------------------------------------------- commands

def _warn(warnings: list[dict]) -> None:
    for w in warnings:
        print(f"warning: {w['path']}: {w['error']}", file=sys.stderr)


def _list(a) -> None:
    if a.all:
        found, warnings = skills.scan()
        found.sort(key=lambda s: (s.name, skills.SCOPES.index(s.source)))
    else:
        found, warnings = skills.discover_with_warnings()
    _warn(warnings)
    if a.json:
        print(json.dumps([skills.summary(s) for s in found], indent=1))
        return
    if not found:
        print("no skills found")
    else:
        print(f"{len(found)} editing skill{'s' if len(found) != 1 else ''}\n")
        width = max(len(s.name) for s in found) + 2
        for s in found:
            tags = f"  [{', '.join(s.tags)}]" if s.tags else ""
            override = "  (overrides bundled)" if s.source != "bundled" and \
                skills.raw(s.name, "bundled") else ""
            print(f"  {s.name:<{width}} {s.source:<8} {s.description}{tags}{override}")
    print("\nshow one:     vmill skills show <name>")
    print("edit one:     vmill skills edit <name> --edit")
    print("add your own: vmill skills add <name> --description '...' --edit")
    print("folders:      " + "  ".join(f"{k}={v}" for k, v in skills.roots().items()))


def _show(a) -> None:
    skill = skills.load(a.name)
    if a.json:
        print(json.dumps({**skills.summary(skill), "body": skill.body}, indent=1))
        return
    print(skill.raw.rstrip())
    print(f"\n# source: {skill.source}\n# path:   {skill.path}", file=sys.stderr)


def _add(a) -> None:
    name = skills.clean_name(a.name)
    in_scope = skills.raw(name, a.scope)
    if in_scope is not None and not a.force:
        raise ValueError(f"a {a.scope} skill named {name!r} already exists — "
                         "use `vmill skills edit` or pass --force")
    existing = skills.find(name)
    body = _body_arg(a)
    if a.edit:
        _editor_argv()  # fail before writing when there is no usable editor
        description = a.description or (existing.description if existing else
                                        "One line that tells the AI when to use this skill.")
        if body is None:
            body = existing.body if existing else (
                f"# {name}\n\n"
                "When to use: describe the situation in one sentence.\n\n"
                "## Steps\n\n1. Call the relevant vidmill tool.\n2. Verify the result.\n3. Export when the user asked for a delivery file.\n\n"
                "## Rules\n\n- Keep the edit safe and reversible.\n"
            )
        skill = skills.upsert(name, description, body, a.tags, a.scope)
        _open_editor(skill.path)
        skill = skills.read_scope(name, a.scope)
        print(f"created skill {skill.name!r} ({len(skill.body)} chars)")
        _scope_note(a.scope)
        return
    if not a.description:
        raise ValueError("--description is required (or use --edit to fill it in)")
    if not body:
        raise ValueError("skill instructions are required: pass --body, --from, or --edit")
    skill = skills.upsert(name, a.description, body, a.tags, a.scope)
    print(f"created skill {skill.name!r} ({len(skill.body)} chars)")
    _scope_note(a.scope)


def _edit(a) -> None:
    name = skills.clean_name(a.name)
    existing = skills.load(name)
    body = _body_arg(a)
    if a.edit:
        _editor_argv()  # fail before writing when there is no usable editor
        description = a.description if a.description is not None else existing.description
        body = existing.body if body is None else body
        tags = existing.tags if a.tags is None else a.tags
        skill = skills.update(name, description, body, tags, a.scope)
        _open_editor(skill.path)
        skill = skills.read_scope(name, a.scope)
        print(f"updated skill {skill.name!r} ({len(skill.body)} chars)")
        _scope_note(a.scope)
        return
    if a.description is None and body is None and a.tags is None:
        raise ValueError("nothing to change — pass --description, --tags, --body or --edit")
    skill = skills.update(name, a.description, body, a.tags, a.scope)
    print(f"updated skill {skill.name!r} ({len(skill.body)} chars)")
    _scope_note(a.scope)


def _reset(a) -> None:
    name = skills.clean_name(a.name)
    scopes = skills.WRITE_SCOPES if a.scope == "all" else (a.scope,)
    removed = skills.reset(name, scopes)
    if not removed:
        effective = skills.find(name)
        if effective is not None:
            print(f"{name!r} already uses the {effective.source} skill — nothing to reset")
            return
        raise ValueError(f"no override or skill named {name!r} to reset")
    for path in removed:
        print(f"removed {path}")
    effective = skills.find(name)
    if effective is not None:
        print(f"{name!r} now resolves to the {effective.source} skill")
    else:
        print(f"{name!r} has no remaining skill file")


def _remove(a) -> None:
    name = skills.clean_name(a.name)
    path = skills.remove(name, a.scope)
    print(f"removed {path}")
    effective = skills.find(name)
    if effective is not None:
        print(f"{name!r} now resolves to the {effective.source} skill")


def _check() -> None:
    found, warnings = skills.scan()
    names = {s.name for s in found}
    print(f"checked {len(found)} skill file{'s' if len(found) != 1 else ''}: "
          f"{len(names)} unique name{'s' if len(names) != 1 else ''}")
    _warn(warnings)
    if warnings:
        raise ValueError(f"{len(warnings)} skill file(s) need attention")
    if warnings:
        raise util.ToolError(f"{len(warnings)} skill file(s) need attention")
    effective = skills.discover()
    print(f"effective skills: {', '.join(s.name for s in effective)}")


def _path(a) -> None:
    roots = skills.roots()
    if a.json:
        print(json.dumps({k: str(v) for k, v in roots.items()}, indent=1))
        return
    width = max(len(k) for k in roots)
    for scope, path in roots.items():
        print(f"  {scope:<{width}}  {path}")
    print("\nprecedence: bundled < user < project")
