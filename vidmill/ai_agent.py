"""Tool: ai — a natural-language editor that can call any vidmill tool.

Uses OpenAI-compatible function calling. The model never sees the video:
it receives the job state and a tool list generated from the real CLI,
then drives the same tools a human would (plan, cut, overlay, captions,
export, ...). Your key stays in the environment.

  export VIDMILL_AI_KEY=sk-...            # or OPENAI_API_KEY
  export VIDMILL_AI_BASE=https://api.openai.com/v1
  export VIDMILL_AI_MODEL=gpt-4o-mini

  vmill ai --job myedit "cut the long pause at 0:42 and add a logo"
  vmill ai --job myedit --dry-run "..."   # show the request, no call
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.request

from . import job as jobmod
from . import util

PURPOSE = "AI editor: natural-language changes through any vidmill tool"
MAX_STEPS = 12
TOOL_OUTPUT_CHARS = 6000
SHOW_CHARS = 1800

SYSTEM = """\
You are vidmill's AI editing agent. You operate on a job folder through
tools; every tool reads the job's current video and writes a new
artifact which then becomes current. Nothing is uploaded except your
text instructions and the tool results you receive.

Job: {job}
Current video: {video} ({width}x{height}, {duration:.2f}s, audio={audio})

Rules:
- Work only through the tools. Do not invent paths or artifact names.
- Inspect with `status` first when unsure what exists.
- Never re-run `cut` just to apply new cuts: `cut` applies the existing
  cut_plan.json. To remove new ranges, first call `plan` with one or
  more `cut` values like "12.3:14.8" (seconds in the CURRENT video);
  then call `cut`, and afterwards `clean`, `captions`, `export` as needed.
- `plan` with no cuts re-detects silences/still frames on the current
  video; its transcript timings are remapped automatically.
- A watermark can be removed with `delogo` (explicit region or auto).
- `overlay` positions: top-left, top-right, bottom-left, bottom-right,
  center, or X:Y. Times are seconds in the current video.
- Prefer the smallest useful set of tools. If one fails, read the error
  and adapt instead of repeating the same call.
- Always finish by exporting with preset "final" unless the user asked
  for another preset. Then summarize what changed in one short list.
"""


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--job", required=True)
    p.add_argument("prompt", nargs="?", help="what to change, in plain language")
    p.add_argument("--max-steps", type=int, default=MAX_STEPS,
                   help=f"maximum tool-call rounds (default {MAX_STEPS})")
    p.add_argument("--dry-run", action="store_true",
                   help="print the request and tool list, make no API call")


def _settings() -> tuple[str, str, str]:
    base = os.environ.get("VIDMILL_AI_BASE", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("VIDMILL_AI_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("VIDMILL_AI_MODEL", "gpt-4o-mini")
    return base, key, model


def _tool_specs() -> list[dict]:
    from . import mcp_server
    specs = mcp_server._specs()  # noqa: SLF001 - same process, one source of truth
    return [s for name, s in specs.items() if name != "ai"]


def _openai_tools(specs: list[dict]) -> list[dict]:
    return [{
        "type": "function",
        "function": {
            "name": s["name"],
            "description": s["description"],
            "parameters": s["inputSchema"],
        },
    } for s in specs]


def _messages(j) -> list[dict]:
    cur = j.current_video()
    info = util.probe_info(cur)
    system = SYSTEM.format(
        job=j.path, video=cur.name, width=info["width"], height=info["height"],
        duration=info["duration"], audio=info["has_audio"],
    )
    return [{"role": "system", "content": system}]


def _post(base: str, key: str, payload: dict) -> dict:
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)


def _arg_text(text: str) -> str:
    text = (text or "").strip()
    if len(text) > SHOW_CHARS:
        text = text[:SHOW_CHARS] + "\n… (truncated in log)"
    return text


def run(args: argparse.Namespace) -> None:
    if not args.prompt:
        raise util.ToolError("tell the AI what to change: vmill ai --job <dir> \"...\"")
    if args.max_steps < 1:
        raise util.ToolError("--max-steps must be at least 1")

    j = jobmod.Job.load(args.job)
    base, key, model = _settings()
    specs = _tool_specs()
    tools = _openai_tools(specs)
    messages = _messages(j) + [{"role": "user", "content": args.prompt}]

    if args.dry_run:
        print(f"AI dry run: {model} at {base}/chat/completions")
        print(f"{len(tools)} tools available: " + ", ".join(s["name"] for s in specs))
        print("\nsystem:\n" + messages[0]["content"])
        print("\nuser:\n" + args.prompt)
        return

    if not key:
        raise util.ToolError(
            "AI editing needs an OpenAI-compatible API key.\n"
            "  export VIDMILL_AI_KEY=sk-...              # or OPENAI_API_KEY\n"
            "  export VIDMILL_AI_BASE=https://api.openai.com/v1\n"
            "  export VIDMILL_AI_MODEL=gpt-4o-mini\n"
            "The free automatic edit (vmill auto) never needs a key."
        )

    from . import mcp_server
    print(f"AI editor: {model} — up to {args.max_steps} tool rounds")
    for step in range(1, args.max_steps + 1):
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2,
        }
        try:
            body = _post(base, key, payload)
        except Exception as e:  # noqa: BLE001 — the edited job stays intact
            print(f"AI request failed ({e}) — the job is unchanged or partially edited.")
            return

        try:
            msg = body["choices"][0]["message"]
        except (KeyError, IndexError, TypeError):
            print("AI returned an unexpected response — stopped.")
            return

        content = (msg.get("content") or "").strip()
        calls = msg.get("tool_calls") or []
        if content:
            print(f"\nAI: {content}")
        if not calls:
            break

        messages.append({"role": "assistant", "content": content or None,
                         "tool_calls": calls})
        for call in calls:
            fn = call.get("function") or {}
            name = fn.get("name") or ""
            raw = fn.get("arguments")
            try:
                cargs = json.loads(raw) if isinstance(raw, str) else (raw or {})
            except json.JSONDecodeError:
                cargs = {}
            print(f"\n[tool {step}] {name} {json.dumps(cargs, ensure_ascii=False)}")
            result = mcp_server._call(name, cargs)
            text = result["content"][0]["text"]
            print(_arg_text(text))
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", ""),
                "content": text[:TOOL_OUTPUT_CHARS],
            })
    else:
        print(f"\nAI: stopped after {args.max_steps} tool rounds.")

    j = jobmod.Job.load(args.job)
    cur = j.current_video()
    if j.has("final.mp4") and cur.name == "final.mp4":
        info = util.probe_info(cur)
        print(f"\ndone — {j.apath('final.mp4')}: {info['width']}x{info['height']} "
              f"{util.fmt_ts(info['duration'])}  {util.human_size(info['size_bytes'])}")
    elif cur:
        print(f"\ncurrent video: {cur.name} (not exported yet). "
              f"Run `vmill export --job {j.path}` when it looks right.")
    else:
        print(f"\nAI finished without a usable video; run `vmill status --job {j.path}`.")
