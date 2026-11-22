"""Tool: vision — local visual understanding for editing.

  vmill vision check
  vmill vision scenes --job myedit
  vmill vision index  --job myedit
  vmill vision search --job myedit "hands on a keyboard"
  vmill vision tag    --job myedit
  vmill vision thumbnail --job myedit --at 12.5
  vmill vision broll  --job myedit --extract

The free path needs no model: scene cuts come from RGB frame
signatures, tags combine colour, filename and transcript context, and
search falls back to those tags. Install the optional vision extra to
add local image-text embeddings for semantic search, zero-shot tags and
transcript-to-B-roll matching. Nothing leaves the machine.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .. import job as jobmod
from .. import util
from .. import vision_backend as vb
from .. import vision_core as vc

PURPOSE = ("local scene detection, visual index/search, zero-shot tags, "
           "smart thumbnails and transcript-to-B-roll matching")

ACTIONS = ("check", "scenes", "index", "search", "tag", "thumbnail", "broll")


# ------------------------------------------------------------------- helpers

def _json_out(data) -> None:
    print(json.dumps(data, indent=1))


def _warn(message: str) -> None:
    print(f"warning: {message}", file=sys.stderr)


def _job(args) -> jobmod.Job:
    if not args.job:
        raise util.ToolError(f"vision {args.action} needs --job <dir>")
    return jobmod.Job.load(args.job)


def _parse_time(value, default=None):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return default
    if ":" in s:
        try:
            parts = [float(p) for p in s.split(":")]
        except ValueError:
            raise util.ToolError(f"bad time '{s}'")
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        raise util.ToolError(f"bad time '{s}'")
    try:
        return float(s)
    except ValueError:
        raise util.ToolError(f"bad time '{s}'")


def _labels(args) -> list[str]:
    raw = args.labels or os_labels()
    if isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        items = str(raw).replace("\n", ",").split(",")
    out = []
    for item in items:
        s = str(item).strip()
        if s and s not in out:
            out.append(s)
    return out or list(vc.DEFAULT_LABELS)


def os_labels() -> str:
    import os
    return os.environ.get("VIDMILL_VISION_LABELS", "") or ",".join(vc.DEFAULT_LABELS)


def _frame_file(job: jobmod.Job, frame: dict) -> Path:
    p = Path(frame.get("file") or "")
    return p if p.is_absolute() else job.path / p


def _scene_of(scenes: list[dict], t: float) -> int:
    for s in scenes:
        if float(s["start"]) <= t <= float(s["end"]):
            return int(s["index"])
    return 0


def _backend(args, index: dict | None = None):
    """Load the optional semantic backend, or return None for the free path."""
    if args.semantic == "off":
        return None
    idx_backend = (index or {}).get("backend") or {}
    idx_model = idx_backend.get("model")
    if index and args.model and idx_model and args.model != idx_model:
        raise util.ToolError(
            f"this index was built with {idx_model}; rebuild it with "
            f"`vmill vision index --force --model {args.model}`"
        )
    model = args.model or idx_model or vb.DEFAULT_MODEL
    try:
        return vb.VisionBackend(model=model, device=args.device).load()
    except util.ToolError as e:
        if args.semantic == "require":
            raise
        _warn(str(e) + " — using tags and transcript keywords instead")
        return None


def _record(job: jobmod.Job, action: str, artifacts: dict, **meta) -> None:
    job.record("vision", {"action": action, **meta}, artifacts)


# -------------------------------------------------------------------- scenes

def _detect(job: jobmod.Job, args) -> dict:
    src = job.current_video()
    print(f"detecting scenes in {src.name} at {args.fps:g} fps "
          f"(threshold {args.threshold:g})...")
    data = vc.detect_scenes(src, fps=args.fps, threshold=args.threshold,
                            min_scene=args.min_scene)
    util.atomic_json(job.path / vc.SCENES_FILE, data)
    return data


def _ensure_scenes(job: jobmod.Job, args, force: bool = False) -> dict:
    path = job.path / vc.SCENES_FILE
    if path.exists() and not force:
        try:
            data = util.read_json(path)
            if (vc.same_video(data, job.current_video())
                    and abs(float(data.get("threshold", -1)) - float(args.threshold)) < 1e-6
                    and abs(float(data.get("min_scene", -1)) - float(args.min_scene)) < 1e-6
                    and abs(float(data.get("sample_fps", -1)) - float(args.fps)) < 1e-6):
                return data
        except Exception:
            pass
    return _detect(job, args)


def cmd_scenes(job: jobmod.Job, args) -> None:
    data = _ensure_scenes(job, args, force=args.force)
    _record(job, "scenes", {vc.SCENES_FILE: {
        "duration": data["video"]["duration"], "scenes": len(data["scenes"]),
        "cuts": len(data["cuts"]),
    }}, threshold=data["threshold"], min_scene=data["min_scene"])
    if args.json:
        _json_out(data)
        return
    print(f"{len(data['scenes'])} scenes, {len(data['cuts'])} cuts, "
          f"{util.fmt_ts(data['video']['duration'])}")
    for s in data["scenes"]:
        print(f"  {s['index'] + 1:>3}  {util.fmt_ts(s['start'])} → "
              f"{util.fmt_ts(s['end'])}  {s['duration']:.2f}s")
    if data["cuts"]:
        print("\ncuts: " + ", ".join(f"{c['time']:.2f}s ({c['score']:.2f})"
                                     for c in data["cuts"]))
    print(f"\n{vc.SCENES_FILE}")


# --------------------------------------------------------------------- index

def _build_index(job: jobmod.Job, args) -> tuple[dict, dict]:
    src = job.current_video()
    scenes_data = _ensure_scenes(job, args, force=args.force)
    scenes = scenes_data["scenes"]
    duration = float(scenes_data["video"]["duration"])
    vinfo = util.probe_info(src)

    frames_dir = job.path / vc.FRAMES_DIR
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    emb_path = job.path / vc.EMBEDDINGS_FILE
    if emb_path.exists():
        emb_path.unlink()

    times = vc.frame_times(duration, scenes, max_frames=args.max_frames,
                           interval=args.interval)
    if not times:
        raise util.ToolError("no frames could be sampled from this video")
    transcript = vc.load_transcript(job.path)
    print(f"sampling {len(times)} frames from {src.name}...")
    frames = []
    for i, t in enumerate(times, 1):
        fid = f"f{i:04d}"
        out = frames_dir / f"{fid}.jpg"
        vc.extract_frame(src, t, out, width=640)
        stats = vc.analyze_image(out)
        dialogue = vc.transcript_context(job.path, t, t, transcript=transcript)
        tags = list(stats.get("tags") or [])
        for k in vc.keywords(dialogue, 4):
            if k not in tags:
                tags.append(k)
        frames.append({
            "id": fid,
            "time": round(t, 3),
            "scene": _scene_of(scenes, t),
            "file": f"{vc.FRAMES_DIR}/{fid}.jpg",
            "tags": tags,
            "labels": [],
            "stats": stats,
            "dialogue": dialogue,
        })

    backend = _backend(args)
    embeddings = {}
    if backend:
        print(f"embedding {len(frames)} frames with {backend.model_name} "
              f"on {backend.device}...")
        image_vectors = backend.encode_images([str(_frame_file(job, f)) for f in frames])
        labels = _labels(args)
        label_vectors = backend.encode_texts(labels)
        scored = backend.label_scores(image_vectors, label_vectors, labels)
        for f, row in zip(frames, scored):
            top = [x for x in row[:4] if x["score"] >= 0.05] or row[:1]
            f["labels"] = top
            old = set(f["tags"])
            for item in top:
                if item["label"] not in old:
                    f["tags"].append(item["label"])
                    old.add(item["label"])
            f["tags"] = f["tags"][:10]
        vectors = [[round(float(x), 6) for x in row] for row in image_vectors]
        embeddings = {
            "version": 1,
            "created": vc.now(),
            "model": backend.model_name,
            "dim": int(image_vectors.shape[1]),
            "frames": [f["id"] for f in frames],
            "vectors": vectors,
        }
        util.atomic_json(emb_path, embeddings)
    elif args.semantic == "require":
        raise util.ToolError("semantic vision was required but the backend is unavailable")

    data = {
        "version": 1,
        "created": vc.now(),
        "video": scenes_data["video"],
        "settings": {
            "max_frames": args.max_frames,
            "interval": args.interval,
            "scene_threshold": args.threshold,
            "min_scene": args.min_scene,
            "semantic": bool(backend),
        },
        "backend": backend.info() if backend else None,
        "scenes": scenes,
        "frames": frames,
        "tags": vc.tag_summary(frames),
        "source": {
            "width": vinfo.get("width"), "height": vinfo.get("height"),
            "fps": vinfo.get("fps"), "duration": duration,
        },
    }
    util.atomic_json(job.path / vc.INDEX_FILE, data)
    _record(job, "index", {
        vc.SCENES_FILE: {"duration": duration, "scenes": len(scenes),
                         "cuts": len(scenes_data["cuts"])},
        vc.INDEX_FILE: {"duration": duration, "frames": len(frames),
                        "semantic": bool(backend)},
        **({vc.EMBEDDINGS_FILE: {"frames": len(frames),
                                 "dim": embeddings.get("dim"),
                                 "model": embeddings.get("model")}}
           if embeddings else {}),
    }, max_frames=args.max_frames, semantic=bool(backend))
    return data, embeddings


def _load_or_build(job: jobmod.Job, args) -> tuple[dict, dict]:
    index = vc.load_index(job.path)
    if index and not args.force and vc.same_video(index, job.current_video()):
        return index, vc.load_embeddings(job.path)
    return _build_index(job, args)


def cmd_index(job: jobmod.Job, args) -> None:
    data, embeddings = _build_index(job, args)
    tags = list(data.get("tags", {}))
    if args.json:
        _json_out({
            "index": vc.INDEX_FILE,
            "frames": len(data["frames"]),
            "scenes": len(data["scenes"]),
            "tags": data["tags"],
            "backend": data["backend"],
        })
        return
    print(f"indexed {len(data['frames'])} frames across "
          f"{len(data['scenes'])} scenes -> {vc.INDEX_FILE}")
    if data.get("backend"):
        b = data["backend"]
        print(f"semantic: {b['model']} on {b['device']} ({b['dim']}d)")
    else:
        print("semantic: off (tags and transcript keywords only)")
    if embeddings:
        print(f"vectors: {vc.EMBEDDINGS_FILE} ({len(embeddings['frames'])} × {embeddings['dim']})")
    print("tags: " + (", ".join(tags[:16]) or "(none)"))


# -------------------------------------------------------------------- search

def cmd_search(job: jobmod.Job, args) -> None:
    query = (args.query or "").strip()
    if not query:
        raise util.ToolError('vision search needs a query, e.g. vmill vision search --job myedit "city at night"')
    index = vc.load_index(job.path)
    if not index:
        raise util.ToolError("no vision index — run `vmill vision index --job ...` first")
    embeddings = vc.load_embeddings(job.path)
    backend = None
    query_vec = None
    if args.semantic != "off" and embeddings.get("vectors") and index.get("backend"):
        backend = _backend(args, index)
        if backend:
            query_vec = backend.encode_texts([query])[0]
    elif args.semantic == "require":
        raise util.ToolError(
            "semantic search was required, but this index has no embeddings; "
            "install the vision extra and rebuild with `vmill vision index --force`"
        )

    rows = []
    for f in index.get("frames", []):
        doc = " ".join([f.get("dialogue") or "", " ".join(f.get("tags") or []),
                        Path(f.get("file") or "").stem])
        lex = vc.lexical_score(query, doc)
        row = {
            "id": f["id"], "time": f["time"], "scene": f.get("scene", 0),
            "file": f.get("file"), "tags": f.get("tags") or [],
            "dialogue": f.get("dialogue") or "", "keyword": lex,
        }
        if backend:
            vec = embeddings["vectors"][embeddings["frames"].index(f["id"])]
            sem = vc.cosine_scores(query_vec, [vec])[0]
            row["semantic"] = sem
            row["score"] = round(0.85 * max(0.0, sem) + 0.15 * lex, 5)
        else:
            row["score"] = lex
        rows.append(row)
    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:max(1, args.top)]
    method = "semantic+keywords" if backend else "keywords+tags"
    if args.json:
        _json_out({"query": query, "method": method, "results": rows})
        return
    if not rows:
        print("no visual matches")
        return
    print(f"query: {query}  ({method})")
    for i, r in enumerate(rows, 1):
        bits = [f"score {r['score']:.3f}"]
        if "semantic" in r:
            bits.append(f"visual {r['semantic']:.3f}")
            bits.append(f"words {r['keyword']:.2f}")
        tags = ", ".join(r["tags"][:6])
        print(f"\n{i:>2}. {util.fmt_ts(r['time'])}  {r['id']}  " + "  ".join(bits))
        if tags:
            print(f"    {tags}")
        if r["dialogue"]:
            print(f"    “{r['dialogue'][:140]}”")
        print(f"    {r['file']}")


# ----------------------------------------------------------------------- tag

def cmd_tag(job: jobmod.Job, args) -> None:
    index = vc.load_index(job.path)
    if not index:
        raise util.ToolError("no vision index — run `vmill vision index --job ...` first")
    frames = index["frames"]
    changed = False

    if args.labels:
        embeddings = vc.load_embeddings(job.path)
        backend = _backend(args, index)
        if not backend:
            raise util.ToolError("changing zero-shot labels needs the optional vision backend")
        labels = _labels(args)
        label_vectors = backend.encode_texts(labels)
        if embeddings.get("vectors"):
            import numpy as np
            image_vectors = np.asarray(embeddings["vectors"], dtype=np.float32)
        else:
            image_vectors = backend.encode_images([str(_frame_file(job, f)) for f in frames])
        scored = backend.label_scores(image_vectors, label_vectors, labels)
        for f, row in zip(frames, scored):
            old = {x["label"] for x in f.get("labels") or []}
            keep = [t for t in f.get("tags") or [] if t not in old]
            top = [x for x in row[:4] if x["score"] >= 0.05] or row[:1]
            f["labels"] = top
            for item in top:
                if item["label"] not in keep:
                    keep.append(item["label"])
            f["tags"] = keep[:10]
        index["backend"] = backend.info()
        changed = True
        print(f"re-tagged {len(frames)} frames with {len(labels)} labels")

    target = None
    if args.frame:
        target = next((f for f in frames if f["id"] == args.frame), None)
        if target is None:
            raise util.ToolError(f"no frame with id {args.frame!r}")
    elif args.at is not None:
        t = _parse_time(args.at)
        target = min(frames, key=lambda f: abs(float(f["time"]) - t))
        print(f"nearest frame: {target['id']} at {util.fmt_ts(target['time'])}")

    for tag in [x.strip() for x in (args.add or "").split(",") if x.strip()]:
        targets = [target] if target else frames
        for f in targets:
            if tag not in f.setdefault("tags", []):
                f["tags"].append(tag)
        changed = True
        print(f"added tag {tag!r} to {len(targets)} frame(s)")
    for tag in [x.strip() for x in (args.remove or "").split(",") if x.strip()]:
        targets = [target] if target else frames
        for f in targets:
            f["tags"] = [t for t in f.get("tags", []) if t != tag]
        changed = True
        print(f"removed tag {tag!r} from {len(targets)} frame(s)")

    if changed:
        index["tags"] = vc.tag_summary(frames)
        util.atomic_json(job.path / vc.INDEX_FILE, index)
        _record(job, "tag", {vc.INDEX_FILE: {"frames": len(frames),
                                             "semantic": bool(index.get("backend"))}})
        if args.json:
            _json_out({"tags": index["tags"]})
            return

    tags = index.get("tags") or vc.tag_summary(frames)
    if args.json:
        _json_out({"tags": tags})
        return
    if not tags:
        print("no tags yet — run `vmill vision index`")
        return
    print(f"{len(tags)} tags across {len(frames)} frames")
    for tag, ids in list(tags.items())[:max(1, args.top)]:
        times = []
        for fid in ids[:4]:
            f = next((x for x in frames if x["id"] == fid), None)
            if f:
                times.append(util.fmt_ts(f["time"]))
        print(f"  {tag:<22} {len(ids):>3}  " + ", ".join(times))


# ----------------------------------------------------------------- thumbnail

def cmd_thumbnail(job: jobmod.Job, args) -> None:
    index, embeddings = _load_or_build(job, args)
    frames = index["frames"]
    duration = float(index.get("source", {}).get("duration") or
                     index.get("video", {}).get("duration") or 0)
    if not frames:
        raise util.ToolError("the vision index has no frames")

    query = (args.query or "").strip()
    query_vec = None
    backend = None
    if query and args.semantic != "off" and embeddings.get("vectors"):
        backend = _backend(args, index)
        if backend:
            query_vec = backend.encode_texts([query])[0].tolist()
    elif query and args.semantic == "require":
        raise util.ToolError("semantic thumbnail selection was required, but the index has no embeddings")

    forced = None
    if args.at is not None:
        t = _parse_time(args.at)
        forced = min(frames, key=lambda f: abs(float(f["time"]) - t))
        print(f"using nearest indexed frame {forced['id']} at {util.fmt_ts(forced['time'])}")

    candidates = [forced] if forced else frames
    quality = {f["id"]: vc.quality_score(f.get("stats") or {}, float(f["time"]), duration)
               for f in candidates}
    sem = {}
    if query_vec and backend:
        vectors = [embeddings["vectors"][embeddings["frames"].index(f["id"])]
                   for f in candidates]
        raw = vc.cosine_scores(query_vec, vectors)
        lo, hi = min(raw), max(raw)
        span = max(1e-6, hi - lo)
        sem = {f["id"]: (r - lo) / span for f, r in zip(candidates, raw)}
        raw_by_id = {f["id"]: r for f, r in zip(candidates, raw)}
    else:
        raw_by_id = {}

    lex = {f["id"]: vc.lexical_score(query, " ".join(f.get("tags") or []) + " " +
                                     (f.get("dialogue") or "")) if query else 0.0
           for f in candidates}
    scored = []
    for f in candidates:
        fid = f["id"]
        q = quality[fid]
        if sem:
            score = 0.68 * sem[fid] + 0.32 * q
        elif query:
            score = 0.65 * lex[fid] + 0.35 * q
        else:
            score = q
        scored.append((score, q, f))
    scored.sort(key=lambda x: x[0], reverse=True)
    score, q, chosen = scored[0]

    out = Path(args.out).expanduser() if args.out else job.path / vc.THUMB_FILE
    if not out.is_absolute():
        out = job.path / out
    vc.extract_frame(job.current_video(), float(chosen["time"]), out, width=args.width)
    info = {
        "created": vc.now(),
        "file": vc.rel(job.path, out),
        "time": chosen["time"],
        "frame": chosen["id"],
        "score": round(score, 4),
        "quality": round(q, 4),
        "query": query or None,
        "semantic": (raw_by_id.get(chosen["id"]) if raw_by_id else None),
        "tags": chosen.get("tags") or [],
        "stats": chosen.get("stats") or {},
    }
    util.atomic_json(job.path / "vision/thumbnail.json", info)
    _record(job, "thumbnail", {vc.rel(job.path, out): {
        "duration": index.get("video", {}).get("duration"),
        "time": chosen["time"], "query": query or None,
    }}, width=args.width)
    if args.json:
        _json_out(info)
        return
    print(f"thumbnail: {vc.rel(job.path, out)}")
    print(f"frame {chosen['id']} at {util.fmt_ts(chosen['time'])}  "
          f"score {score:.3f} (quality {q:.3f})")
    if query:
        print(f"query: {query}")
    if chosen.get("tags"):
        print("tags: " + ", ".join(chosen["tags"][:8]))


# --------------------------------------------------------------------- broll

def _segment_window(seg: dict, duration: float, max_window: float = 5.5) -> tuple[float, float] | None:
    start = float(seg.get("start", 0) or 0)
    end = float(seg.get("end", start) or start)
    at = max(0.0, start + 0.05)
    to = min(duration, end - 0.05)
    if to - at > max_window:
        to = at + max_window
    if to - at < 1.2:
        to = min(duration, at + 1.2)
    if to - at < 0.8:
        return None
    return round(at, 3), round(to, 3)


def _candidate_summary(c: dict, job: jobmod.Job) -> dict:
    return {
        "id": c["id"],
        "kind": c["kind"],
        "path": vc.rel(job.path, Path(c["path"])) if c.get("path") else None,
        "time": c.get("time"),
        "label": c.get("label"),
        "tags": (c.get("tags") or [])[:8],
        "preview": vc.rel(job.path, Path(c["preview"])) if c.get("preview") else None,
        "start": c.get("start"),
        "end": c.get("end"),
        "dialogue": (c.get("dialogue") or "")[:160] or None,
    }


def cmd_broll(job: jobmod.Job, args) -> None:
    transcript = vc.load_transcript(job.path)
    if not transcript or not transcript.get("segments"):
        raise util.ToolError("no transcript — run `vmill transcribe --job ...` first")
    index, embeddings = _load_or_build(job, args)
    duration = float(index.get("video", {}).get("duration") or 0)
    if duration <= 0:
        raise util.ToolError("could not read the current video duration")

    candidates = vc.scene_candidates(index, job.path)
    candidates += vc.library_candidates(job, Path(args.library).expanduser() if args.library else None)
    if not candidates:
        raise util.ToolError("no B-roll candidates — import images/video or use --library")

    q_tokens = []
    segments = []
    min_dur = max(0.2, float(args.min_duration))
    for seg in transcript["segments"]:
        text = (seg.get("text") or "").strip()
        if not text or len(vc.keywords(text, 3)) == 0:
            continue
        if float(seg.get("end", 0) or 0) - float(seg.get("start", 0) or 0) < min_dur:
            continue
        win = _segment_window(seg, duration)
        if not win:
            continue
        segments.append({"start": float(seg["start"]), "end": float(seg["end"]),
                         "text": text, "window": win})
        q_tokens.append(text)
    if not segments:
        raise util.ToolError("transcript has no segments long enough to match")

    backend = None
    query_vectors = None
    vecmap: dict[str, list[float]] = {}
    if args.semantic != "off" and index.get("backend"):
        backend = _backend(args, index)
        if backend:
            if embeddings.get("vectors"):
                vecmap = {fid: vec for fid, vec in
                          zip(embeddings.get("frames", []), embeddings["vectors"])}
            missing = [c for c in candidates if c["id"].replace("frame-", "") not in vecmap]
            if missing:
                print(f"embedding {len(missing)} B-roll candidates...")
                vectors = backend.encode_images([str(c["preview"]) for c in missing])
                for c, vec in zip(missing, vectors):
                    vecmap[c["id"].replace("frame-", "")] = [round(float(x), 6) for x in vec]
            print(f"matching {len(segments)} lines with {backend.model_name}...")
            query_vectors = backend.encode_texts(q_tokens)
    elif args.semantic == "require":
        raise util.ToolError(
            "semantic B-roll matching was required, but this index has no embeddings; "
            "install the vision extra and rebuild with `vmill vision index --force`"
        )

    used: dict[str, int] = {}
    suggestions = []
    min_score = args.min_score
    if min_score is None:
        min_score = 0.18 if backend else 0.12
    last_to = 0.0
    current = job.current_video().resolve()
    for pos, seg in enumerate(segments):
        start, end = seg["start"], seg["end"]
        at, to = seg["window"]
        at = max(at, last_to + 0.15) if last_to else at
        if to - at < 1.0:
            continue
        best = None
        for c in candidates:
            # Never recommend the same moment the viewer is already watching.
            if c["kind"] == "scene":
                if float(c.get("start") or 0) < end + 0.4 and float(c.get("end") or 0) > start - 0.4:
                    continue
            try:
                if c.get("path") and Path(c["path"]).resolve() == current and c["kind"] != "scene":
                    continue
            except OSError:
                pass
            doc = vc.candidate_text(c)
            lex = vc.lexical_score(seg["text"], doc)
            sem = None
            if backend and query_vectors is not None:
                vec = vecmap.get(c["id"].replace("frame-", ""))
                if vec:
                    sem = vc.cosine_scores(query_vectors[pos], [vec])[0]
            if sem is not None:
                score = 0.8 * max(0.0, sem) + 0.2 * lex
            else:
                score = lex
            score *= 0.55 ** used.get(c["id"], 0)
            if best is None or score > best[0]:
                best = (score, sem, lex, c)
        if not best or best[0] < min_score:
            continue
        score, sem, lex, c = best
        used[c["id"]] = used.get(c["id"], 0) + 1
        last_to = to
        suggestion = {
            "segment": {
                "start": round(start, 3), "end": round(end, 3),
                "text": seg["text"],
            },
            "candidate": _candidate_summary(c, job),
            "window": {"at": at, "to": to, "duration": round(to - at, 3)},
            "score": round(score, 4),
            "semantic": round(sem, 4) if sem is not None else None,
            "keyword": lex,
            "method": "semantic+keywords" if sem is not None else "keywords+tags",
        }
        if c["kind"] == "image":
            suggestion["overlay"] = {"image": vc.rel(job.path, Path(c["path"])),
                                     "at": at, "to": to}
            suggestion["command"] = (f"vmill overlay --job {job.path} --image "
                                     f"{vc.rel(job.path, Path(c['path']))} "
                                     f"--at {at:.2f} --to {to:.2f}")
        else:
            suggestion["overlay"] = {"video": vc.rel(job.path, Path(c["path"])),
                                     "mode": args.mode, "at": at, "to": to}
            suggestion["command"] = (f"vmill overlay --job {job.path} --video "
                                     f"{vc.rel(job.path, Path(c['path']))} "
                                     f"--mode {args.mode} --at {at:.2f} --to {to:.2f}")
        suggestion["window"] = {"at": round(at, 3), "to": round(to, 3),
                                "duration": round(to - at, 3)}
        if "overlay" in suggestion:
            suggestion["overlay"]["at"] = round(at, 3)
            suggestion["overlay"]["to"] = round(to, 3)
        suggestions.append(suggestion)
        if len(suggestions) >= max(1, args.max):
            break

    if args.extract and suggestions:
        info = util.probe_info(job.current_video())
        W, H = int(info.get("width") or 1920), int(info.get("height") or 1080)
        fps = float(info.get("fps") or 30)
        specs = []
        for i, sug in enumerate(suggestions, 1):
            c = next(x for x in candidates if x["id"] == sug["candidate"]["id"])
            win = sug["window"]
            out = job.path / vc.ASSETS_DIR / f"broll_{i:02d}.mp4"
            if c["kind"] == "image":
                vc.image_clip(Path(c["path"]), win["duration"], out, W, H, fps)
            else:
                start = (float(c["start"]) + 0.2) if c["kind"] == "scene" and c.get("start") is not None \
                    else float(c.get("time") or 0)
                vc.extract_clip(Path(c["path"]), start, win["duration"], out, W, H, fps)
            sug["clip"] = vc.rel(job.path, out)
            specs.append({"video": vc.rel(job.path, out), "mode": args.mode,
                          "at": win["at"], "to": win["to"]})
        spec_path = job.path / vc.ASSETS_DIR / "overlays.json"
        util.atomic_json(spec_path, {"overlays": specs})
        _record(job, "broll-extract", {vc.rel(job.path, spec_path): {
            "overlays": len(specs), "duration": duration,
        }}, mode=args.mode)

    data = {
        "version": 1,
        "created": vc.now(),
        "video": index.get("video"),
        "backend": index.get("backend"),
        "method": "semantic+keywords" if backend else "keywords+tags",
        "suggestions": suggestions,
        "library": {
            "scenes": sum(1 for c in candidates if c["kind"] == "scene"),
            "images": sum(1 for c in candidates if c["kind"] == "image"),
            "videos": sum(1 for c in candidates if c["kind"] == "video"),
            "folder": str(Path(args.library).expanduser()) if args.library else None,
        },
    }
    util.atomic_json(job.path / vc.BROLL_FILE, data)
    _record(job, "broll", {vc.BROLL_FILE: {
        "duration": duration, "suggestions": len(suggestions),
    }}, mode=args.mode, extracted=bool(args.extract))

    if args.json:
        _json_out(data)
        return
    if not suggestions:
        print("no B-roll match above the score threshold")
        return
    print(f"{len(suggestions)} B-roll suggestions ({data['method']}) -> {vc.BROLL_FILE}")
    for i, sug in enumerate(suggestions, 1):
        seg, c, win = sug["segment"], sug["candidate"], sug["window"]
        print(f"\n{i:>2}. {util.fmt_ts(seg['start'])} → {util.fmt_ts(seg['end'])}  "
              f"{sug['score']:.3f}  {c['kind']}")
        print(f"    “{seg['text'][:150]}”")
        print(f"    {c['path']}" + (f" @ {c['time']:.2f}s" if c.get("time") else ""))
        if c.get("tags"):
            print(f"    tags: {', '.join(c['tags'][:6])}")
        print(f"    window {util.fmt_ts(win['at'])} → {util.fmt_ts(win['to'])}")
    if args.extract:
        print(f"\nclips + spec: {vc.ASSETS_DIR}/overlays.json")
        print(f"apply: vmill overlay --job {job.path} --spec {vc.ASSETS_DIR}/overlays.json")


# --------------------------------------------------------------------- check

def cmd_check(job: jobmod.Job | None, args) -> None:
    ff = shutil.which(util.FFMPEG)
    fp = shutil.which(util.FFPROBE)
    ffver = None
    if ff:
        p = util.run([util.FFMPEG, "-version"], check=False, quiet=True)
        line = (p.stdout or "").splitlines()
        ffver = line[0].split()[2] if line and len(line[0].split()) > 2 else "installed"
    st = vb.status(args.model)
    if args.load:
        backend = vb.VisionBackend(model=args.model, device=args.device).load()
        st.update(backend.info())
        st["available"] = True
        st["loaded"] = True
    libs = vb.libraries()
    data = {
        "ffmpeg": bool(ff), "ffmpeg_version": ffver, "ffprobe": bool(fp),
        "numpy": libs.get("numpy"), "pillow": libs.get("pillow"),
        "semantic": st,
    }
    if job:
        index = vc.load_index(job.path)
        scenes = {}
        sp = job.path / vc.SCENES_FILE
        if sp.exists():
            try:
                scenes = util.read_json(sp)
            except Exception:
                scenes = {}
        data["job"] = {
            "path": str(job.path),
            "video": str(job.current_video()),
            "scenes": len(scenes.get("scenes", [])),
            "frames": len(index.get("frames", [])),
            "tags": len(index.get("tags", {})),
            "indexed": bool(index),
            "index_backend": index.get("backend"),
            "thumbnail": (job.path / vc.THUMB_FILE).exists(),
            "broll": (job.path / vc.BROLL_FILE).exists(),
            "transcript": (job.path / "transcript.json").exists(),
        }
    if args.json:
        _json_out(data)
        return
    print("vision stack")
    print(f"  ffmpeg      {'OK' if ff else '--'}  {ffver or 'not found'}")
    print(f"  ffprobe     {'OK' if fp else '--'}")
    print(f"  numpy       {'OK' if libs.get('numpy') else '--'}")
    print(f"  pillow      {'OK' if libs.get('pillow') else '--'}")
    if st.get("available"):
        print(f"  semantic    OK  {st.get('model')}  device={st.get('device')}")
        print(f"  model cache {'yes' if st.get('cached') else 'no — downloads on first use'}")
    else:
        print(f"  semantic    --  {st.get('reason') or 'optional backend unavailable'}")
        print(f"              install: {st.get('install')}")
    if job:
        j = data["job"]
        print("\nthis job")
        print(f"  scenes      {j['scenes']}")
        print(f"  frames      {j['frames']} indexed, {j['tags']} tags")
        print(f"  thumbnail   {'yes' if j['thumbnail'] else 'no'}")
        print(f"  b-roll      {'yes' if j['broll'] else 'no'}")
        if j.get("index_backend"):
            b = j["index_backend"]
            print(f"  index model {b.get('model')} ({b.get('dim')}d)")
        if not j["indexed"]:
            print("  next: vmill vision scenes --job ...   then   vmill vision index --job ...")


# ----------------------------------------------------------------------- run

def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("action", nargs="?", default="check", choices=ACTIONS,
                   help="check | scenes | index | search | tag | thumbnail | broll")
    p.add_argument("query", nargs="?",
                   help="query text for search, or an optional brief for thumbnail")
    p.add_argument("--job", help="job directory (required except for check)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--threshold", type=float, default=vc.DEFAULT_THRESHOLD,
                   help="cut score 0.05..0.95 (default 0.35)")
    p.add_argument("--min-scene", type=float, default=vc.DEFAULT_MIN_SCENE,
                   help="shortest useful scene in seconds (default 0.8)")
    p.add_argument("--fps", type=float, default=vc.DEFAULT_FPS,
                   help="scene sampling rate (default 4)")
    p.add_argument("--max-frames", type=int, default=vc.DEFAULT_MAX_FRAMES,
                   help="maximum indexed frames (default 120)")
    p.add_argument("--interval", type=float, default=vc.DEFAULT_INTERVAL,
                   help="seconds between frames inside a long scene (default 5)")
    p.add_argument("--semantic", choices=["auto", "off", "require"], default="auto",
                   help="use optional image-text embeddings: auto, off or require")
    p.add_argument("--model", help="Hugging Face image-text model (optional)")
    p.add_argument("--device", default="auto", help="auto | cpu | cuda | mps")
    p.add_argument("--labels", help="comma-separated zero-shot labels")
    p.add_argument("--top", type=int, default=8, help="results or tags to show")
    p.add_argument("--at", help="timestamp for thumbnail/tag (seconds or M:SS)")
    p.add_argument("--frame", help="frame id for tag add/remove")
    p.add_argument("--add", help="add a tag (comma-separated)")
    p.add_argument("--remove", help="remove a tag (comma-separated)")
    p.add_argument("--out", help="thumbnail output path")
    p.add_argument("--width", type=int, default=1280, help="thumbnail width")
    p.add_argument("--library", help="extra folder of images/videos for B-roll")
    p.add_argument("--extract", action="store_true",
                   help="B-roll: extract clips and write an overlay spec")
    p.add_argument("--mode", choices=["cutaway", "pip"], default="cutaway",
                   help="B-roll placement (default cutaway)")
    p.add_argument("--max", type=int, default=12, help="maximum B-roll suggestions")
    p.add_argument("--min-score", type=float, help="minimum B-roll match score")
    p.add_argument("--min-duration", type=float, default=1.0,
                   help="ignore transcript lines shorter than this")
    p.add_argument("--force", action="store_true", help="rebuild scenes/index")
    p.add_argument("--load", action="store_true", help="check: load the model now")


def run(args: argparse.Namespace) -> None:
    action = args.action or "check"
    if action == "check":
        job = jobmod.Job.load(args.job) if args.job else None
        cmd_check(job, args)
        return
    job = _job(args)
    if action == "scenes":
        cmd_scenes(job, args)
    elif action == "index":
        cmd_index(job, args)
    elif action == "search":
        cmd_search(job, args)
    elif action == "tag":
        cmd_tag(job, args)
    elif action == "thumbnail":
        cmd_thumbnail(job, args)
    elif action == "broll":
        cmd_broll(job, args)
    else:
        raise util.ToolError(f"unknown vision action {action!r}")
