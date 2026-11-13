"""Tool: music — no-copyright music & sound effects catalog.

  vmill music list [--mood calm] [--type sfx] [--json]
  vmill music get <id> --job <dir>          download a track into the job
  vmill music mix <id> --job <dir> [--volume 0.15]   mix it under the video

The catalog ships in vidmill/assets/music.json: every entry has a
verified direct-download URL and a commercial-safe license (CC0 /
Public Domain / CC BY). CC BY entries carry the attribution line your
video description needs — `get` and `mix` print it.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

from .. import job as jobmod
from .. import util

PURPOSE = "list, download and mix no-copyright music & sounds (commercial-safe)"

CATALOG = Path(__file__).resolve().parent.parent / "assets" / "music.json"
UA = {"User-Agent": "vidmill/0.1 (github.com/piyushd000/vidmill)"}


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", nargs="?", default="list", choices=["list", "get", "mix"])
    p.add_argument("id", nargs="?", help="track id (for get / mix)")
    p.add_argument("--job", help="job directory (for get / mix)")
    p.add_argument("--mood", choices=["calm", "happy", "tense", "ambient", "ambience", "reaction"])
    p.add_argument("--type", dest="type_", choices=["music", "sfx"])
    p.add_argument("--volume", type=float, default=0.15, help="music volume under the voice (default 0.15)")
    p.add_argument("--in", dest="in_artifact", help="video to mix into (default: current)")
    p.add_argument("--json", action="store_true", help="machine-readable list output")


def _tracks(args) -> list[dict]:
    data = util.read_json(CATALOG)
    out = data["tracks"]
    if args.mood:
        out = [t for t in out if t["mood"] == args.mood]
    if args.type_:
        out = [t for t in out if t["type"] == args.type_]
    return out


def run(args: argparse.Namespace) -> None:
    if args.action == "list":
        return _list(args)
    if not args.id:
        raise util.ToolError(f"music {args.action} needs a track id — see `vmill music list`")
    if not args.job:
        raise util.ToolError(f"music {args.action} needs --job")
    track = next((t for t in _tracks(args) if t["id"] == args.id), None)
    if not track:
        raise util.ToolError(f"unknown track '{args.id}' — see `vmill music list`")
    if args.action == "get":
        return _get(track, args)
    return _mix(track, args)


def _list(args) -> None:
    tracks = _tracks(args)
    if args.json:
        print(json.dumps(tracks, indent=1))
        return
    print(f"{len(tracks)} tracks (commercial-safe: CC0 / Public Domain / CC BY)\n")
    for t in tracks:
        dur = f"{t['duration']}s" if t.get("duration") else "~"
        print(f"  {t['id']:<26} {t['type']:<5} {t['mood']:<9} {dur:>6}  "
              f"{t['title']}  [{t['license']}]")
    print("\ndownload into a job:  vmill music get <id> --job <dir>")


def _download(track: dict, dest: Path, attempts: int = 3) -> Path:
    import time
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(track["url"], headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
                f.write(r.read())
            if dest.exists() and dest.stat().st_size > 1000:
                return dest
        except Exception as e:
            wait = 20 * (attempt + 1)
            if attempt < attempts - 1:
                print(f"download hiccup ({e}) — retrying in {wait}s...")
                time.sleep(wait)
                continue
            raise util.ToolError(
                f"could not download {track['url']} ({e}). The source may be "
                f"rate-limiting this network — try again in a few minutes.") from e
    raise util.ToolError(f"download failed: {track['url']}")


def _ext(url: str) -> str:
    return Path(url).suffix or ".mp3"


def _get(track: dict, args) -> None:
    j = jobmod.Job.load(args.job)
    dest = j.apath(f"audio_{track['id']}{_ext(track['url'])}")
    _download(track, dest)
    info = util.probe_info(dest)
    j.record("music.get", {"track": track["id"]},
             {dest.name: {"duration": round(info["duration"], 1), "track": track["id"]}})
    print(f"saved {dest.name}  {util.human_size(info['size_bytes'])}  {util.fmt_ts(info['duration'])}")
    _print_attribution(track)


def _mix(track: dict, args) -> None:
    j = jobmod.Job.load(args.job)
    src = j.apath(args.in_artifact) if args.in_artifact else j.current_video()
    music = j.apath(f"audio_{track['id']}{_ext(track['url'])}")
    if not music.exists():
        music = _download(track, music)
        print(f"downloaded {music.name}")
    info = util.probe_info(src)
    fade = min(4.0, max(1.0, info["duration"] - 1))
    out = j.apath("mixed.mp4")
    util.run_ffmpeg(
        src,
        ["-stream_loop", "-1", "-i", str(music),
         "-filter_complex",
         (f"[1:a]volume={args.volume},afade=t=out:st={max(0.0, info['duration'] - fade)}:d={fade}[m];"
          f"[0:a][m]amix=inputs=2:duration=first:dropout_transition=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]"),
         "-map", "0:v", "-map", "[aout]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest"],
        out)
    out_info = util.probe_info(out)
    j.record("music.mix", {"track": track["id"], "volume": args.volume},
             {"mixed.mp4": {"duration": round(out_info["duration"], 2), "track": track["id"]}})
    print(f"mixed.mp4  {util.fmt_ts(out_info['duration'])}  music='{track['title']}' at {args.volume}")
    _print_attribution(track)


def _print_attribution(track: dict) -> None:
    if track.get("attribution"):
        print(f"keep this credit in your video description:\n  {track['attribution']}")
    else:
        print("license: no attribution required "
              f"({track['license']} — safe for commercial videos)")
