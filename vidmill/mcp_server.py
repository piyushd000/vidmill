"""MCP server (stdio) — expose every vidmill tool to AI agents.

Add to an MCP client (Claude Desktop, etc.):

  {
    "mcpServers": {
      "vidmill": { "command": "vmill", "args": ["mcp"] }
    }
  }

The server speaks newline-delimited JSON-RPC 2.0 on stdin/stdout:
initialize, ping, tools/list and tools/call. Tool schemas are derived
from each tool's real CLI (add_args), so they can never drift from the
command line. Everything a tool prints is captured and returned as the
call result text; failures come back as isError with the message.

Keep stdout pure protocol — all logging goes to stderr.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys

from . import __version__, util

PURPOSE = "MCP server on stdio — every vmill tool for AI agents"
PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18")


# ------------------------------------------------------- schema derivation

def _registry():
    from .tools import REGISTRY
    return REGISTRY


def _describe(name: str, mod) -> dict:
    """Introspect a tool's argparse surface -> JSON Schema + argv mapping."""
    p = argparse.ArgumentParser(prog=f"vmill {name}", add_help=False)
    mod.add_args(p)
    props: dict = {}
    optmap: dict = {}
    positionals: list[str] = []
    required: list[str] = []

    for a in p._actions:
        if a.dest in ("help", argparse.SUPPRESS):
            continue
        is_pos = not a.option_strings
        if is_pos:
            prop = a.dest
            positionals.append(prop)
            if a.nargs is None:
                required.append(prop)
        else:
            opt = next((o for o in a.option_strings if o.startswith("--")), a.option_strings[0])
            prop = opt.lstrip("-").replace("-", "_")
            optmap[prop] = opt

        is_flag = a.nargs == 0
        is_list = isinstance(a, argparse._AppendAction)
        base = "string"
        if is_flag:
            base = "boolean"
        elif a.type is int:
            base = "integer"
        elif a.type is float:
            base = "number"

        schema: dict = {"type": "array", "items": {"type": base}} if is_list else {"type": base}
        if a.choices:
            schema["enum"] = [str(c) for c in a.choices]
        if a.help:
            schema["description"] = a.help
        if a.default not in (None, False, "", 0) and not is_list:
            schema["default"] = a.default
        props[prop] = schema
        if not is_pos and a.required:
            required.append(prop)

    return {
        "name": name,
        "description": getattr(mod, "PURPOSE", "") or name,
        "inputSchema": {"type": "object", "properties": props, "required": required},
        "_positionals": positionals,
        "_optmap": optmap,
    }


_SPECS: dict | None = None

# CLI builtins that agents also want (not part of the tool registry).
_BUILTINS = {
    "status": {
        "name": "status",
        "description": "Inspect a job's artifacts and tool history.",
        "inputSchema": {
            "type": "object",
            "properties": {"job": {"type": "string", "description": "job directory"}},
            "required": ["job"],
        },
        "_positionals": [],
        "_optmap": {"job": "--job"},
    },
    "doctor": {
        "name": "doctor",
        "description": "Check which engines are installed and usable.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "_positionals": [],
        "_optmap": {},
    },
    "skill": {
        "name": "skill",
        "description": ("Load the full instructions for one editing skill by name. "
                        "The `skills` tool lists the catalog."),
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "skill name"}},
            "required": ["name"],
        },
        "_positionals": [],
        "_optmap": {},
    },
    "skills": {
        "name": "skills",
        "description": ("List, read, add, edit, reset or remove reusable editing "
                        "skills (SKILL.md recipes). Bundled skills ship with "
                        "vidmill; user and project skills override them."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string",
                           "enum": ["list", "show", "add", "edit", "reset", "remove",
                                    "path", "check"]},
                "name": {"type": "string", "description": "skill name"},
                "description": {"type": "string",
                                "description": "one line: when the AI should use it"},
                "body": {"type": "string", "description": "Markdown instructions"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "scope": {"type": "string", "enum": ["user", "project", "all"],
                          "description": "where to read or write (default user)"},
                "json": {"type": "boolean", "description": "JSON output for list/show/path"},
            },
            "required": ["action"],
        },
        "_positionals": [],
        "_optmap": {},
    },
}


def _specs() -> dict:
    global _SPECS
    if _SPECS is None:
        _SPECS = {name: _describe(name, mod) for name, mod in _registry().items()}
        _SPECS.update(_BUILTINS)
    return _SPECS


def _public(spec: dict) -> dict:
    return {k: spec[k] for k in ("name", "description", "inputSchema")}


# ------------------------------------------------------------- tool calls

def _argv(name: str, spec: dict, args: dict) -> list[str]:
    argv: list[str] = []
    for prop in spec["_positionals"]:
        v = args.get(prop)
        if v is not None and v is not False:
            argv.append(str(v))
    for prop, val in args.items():
        if prop in spec["_positionals"]:
            continue
        opt = spec["_optmap"].get(prop)
        if not opt:
            raise util.ToolError(f"unknown argument '{prop}' for tool '{name}'")
        if val is None or val is False:
            continue
        if val is True:
            argv.append(opt)
        elif isinstance(val, list):
            for item in val:
                argv += [opt, str(item)]
        else:
            argv += [opt, str(val)]
    return argv


def _call_skill(args: dict) -> dict:
    from . import skills as skills_mod
    try:
        skill = skills_mod.load(args.get("name") or "")
    except (ValueError, FileNotFoundError) as e:
        return _error(str(e))
    text = f"# {skill.name}\n{skill.description}\n\n{skill.body}".strip()
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _call_skills(args: dict) -> dict:
    from . import skills as skills_mod
    action = str(args.get("action") or "list").lower()
    name = args.get("name")
    scope = str(args.get("scope") or "user").lower()
    try:
        if action == "list":
            found, warnings = skills_mod.discover_with_warnings()
            if args.get("json"):
                text = json.dumps({"skills": [skills_mod.summary(s) for s in found],
                                   "warnings": warnings}, indent=1)
            else:
                lines = [f"{len(found)} editing skills"]
                for s in found:
                    tags = f" [{', '.join(s.tags)}]" if s.tags else ""
                    lines.append(f"- {s.name} ({s.source}) — {s.description}{tags}")
                if warnings:
                    lines.append("")
                    lines += [f"warning: {w['path']}: {w['error']}" for w in warnings]
                text = "\n".join(lines)
        elif action == "show":
            if not name:
                return _error("skills show needs 'name'")
            skill = skills_mod.load(str(name))
            text = json.dumps({**skills_mod.summary(skill), "body": skill.body},
                              indent=1) if args.get("json") else skill.raw
        elif action == "add":
            if not name:
                return _error("skills add needs 'name'")
            if not args.get("description") or not args.get("body"):
                return _error("skills add needs 'description' and 'body'")
            skill = skills_mod.upsert(str(name), str(args["description"]),
                                      str(args["body"]), args.get("tags") or (),
                                      scope)
            text = f"created skill {skill.name!r}\n{skill.path}"
        elif action == "edit":
            if not name:
                return _error("skills edit needs 'name'")
            if (args.get("description") is None and args.get("body") is None
                    and args.get("tags") is None):
                return _error("skills edit needs description, body or tags")
            skill = skills_mod.update(str(name), args.get("description"),
                                      args.get("body"), args.get("tags"), scope)
            text = f"updated skill {skill.name!r}\n{skill.path}"
        elif action == "reset":
            if not name:
                return _error("skills reset needs 'name'")
            scopes = ("user", "project") if scope == "all" else (scope,)
            removed = skills_mod.reset(str(name), scopes)
            if not removed:
                effective = skills_mod.find(str(name))
                text = (f"{name!r} already uses the {effective.source} skill"
                        if effective else f"no skill named {name!r}")
            else:
                text = "\n".join(f"removed {p}" for p in removed)
        elif action == "remove":
            if not name:
                return _error("skills remove needs 'name'")
            text = f"removed {skills_mod.remove(str(name), scope)}"
        elif action == "path":
            roots = {k: str(v) for k, v in skills_mod.roots().items()}
            text = json.dumps(roots, indent=1) if args.get("json") else \
                "\n".join(f"{k}: {v}" for k, v in roots.items())
        elif action == "check":
            found, warnings = skills_mod.scan()
            text = f"checked {len(found)} skill files; {len(warnings)} warning(s)"
            if warnings:
                text += "\n" + "\n".join(f"- {w['path']}: {w['error']}" for w in warnings)
        else:
            return _error(f"unknown skills action {action!r}")
    except (ValueError, FileNotFoundError) as e:
        return _error(str(e))
    return {"content": [{"type": "text", "text": text or "(no output)"}], "isError": False}


def _call_builtin(name: str, args: dict) -> dict:
    if name == "skill":
        return _call_skill(args)
    if name == "skills":
        return _call_skills(args)
    from .cli import doctor_cmd, status_cmd
    if name == "status":
        job = args.get("job")
        if not job:
            return _error("status needs 'job'")
        ns, fn = argparse.Namespace(job=job), status_cmd
    else:
        ns, fn = argparse.Namespace(), doctor_cmd
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            fn(ns)
    except SystemExit:
        pass  # doctor exits non-zero when something is missing; report its text
    except util.ToolError as e:
        return _error(f"error: {e}")
    text = out.getvalue().strip()
    if err.getvalue().strip():
        text = (text + "\n\n[stderr]\n" + err.getvalue().strip()).strip()
    return {"content": [{"type": "text", "text": text or "(no output)"}], "isError": False}


def _call(name: str, args: dict) -> dict:
    specs = _specs()
    if name not in specs:
        return _error(f"unknown tool '{name}' — see tools/list")
    if name in _BUILTINS:
        return _call_builtin(name, args)
    mod = _registry().get(name)
    if mod is None:
        return _error(f"tool '{name}' is not available in this installation")
    spec = specs[name]
    try:
        argv = _argv(name, spec, args)
        p = argparse.ArgumentParser(prog=f"vmill {name}", add_help=False)
        mod.add_args(p)
        ns = p.parse_args(argv)
    except SystemExit:
        return _error(f"invalid arguments for '{name}': vmill {name} {argv}")
    except util.ToolError as e:
        return _error(str(e))

    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            mod.run(ns)
    except util.ToolError as e:
        return _error(f"error: {e}")
    except Exception as e:  # noqa: BLE001 — report, never kill the server
        return _error(f"error: {type(e).__name__}: {e}")

    text = out.getvalue().strip()
    if err.getvalue().strip():
        text = (text + "\n\n[stderr]\n" + err.getvalue().strip()).strip()
    return {"content": [{"type": "text", "text": text or "(no output)"}], "isError": False}


def _error(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": True}


# ------------------------------------------------------------- JSON-RPC

def _ok(id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _fail(id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}


def _handle(msg: dict):
    method = msg.get("method")
    id = msg.get("id")
    params = msg.get("params") or {}

    if method == "initialize":
        want = params.get("protocolVersion")
        return _ok(id, {
            "protocolVersion": want if want in PROTOCOLS else PROTOCOLS[0],
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "vidmill", "version": __version__},
        })
    if method in ("notifications/initialized", "notifications/cancelled", "initialized"):
        return None
    if method == "ping":
        return _ok(id, {}) if id is not None else None
    if method == "tools/list":
        return _ok(id, {"tools": [_public(s) for s in _specs().values()]})
    if method == "tools/call":
        name = params.get("name") or ""
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _fail(id, -32602, "arguments must be an object")
        return _ok(id, _call(name, args))
    if id is None:
        return None  # unknown notification: ignore
    return _fail(id, -32601, f"method not found: {method}")


def serve() -> None:
    tools = _specs()
    print(f"vidmill mcp: {len(tools)} tools on stdio", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            resp = _fail(None, -32700, f"parse error: {e}")
        else:
            try:
                resp = _handle(msg)
            except Exception as e:  # noqa: BLE001 — protocol must survive
                resp = _fail(msg.get("id"), -32603, f"internal error: {type(e).__name__}: {e}")
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


# ------------------------------------------------------------------- CLI

def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--check", action="store_true",
                   help="self-test: initialize + list tools, then exit")


def run(args: argparse.Namespace) -> None:
    if args.check:
        init = _handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": PROTOCOLS[0]}})
        listed = _handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = listed["result"]["tools"]
        print(f"mcp self-test OK: {len(tools)} tools, protocol {init['result']['protocolVersion']}")
        for t in tools:
            req = ", ".join(t["inputSchema"].get("required") or []) or "-"
            print(f"  {t['name']:<10} props={len(t['inputSchema']['properties']):<2} required: {req}")
        return
    serve()
