"""
Storyboard IR helpers for the game CG pipeline.

The public schema stays JSON-friendly, but model-facing prompts are compiled
from structured fields before Qwen/LTX see them.
"""

from __future__ import annotations

import json
import math
import subprocess
import textwrap
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont


DEFAULT_FRAME_RATE = 24.0
DEFAULT_MIN_FRAME_GAP = 4
DEFAULT_TAIL_FRAMES = 6


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(_clean(v) for v in value if _clean(v))
    return str(value).strip()


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _flatten_legacy(data: Any) -> dict:
    """Convert legacy list/group forms into a storyboard dict."""
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "shots" in data[0]:
            shots = [s for group in data for s in group.get("shots", [])]
            first = data[0]
            return {
                "video_prompt": first.get("video_prompt", ""),
                "duration_sec": first.get("duration_sec"),
                "shots": shots,
            }
        return {"video_prompt": "", "shots": data}
    if not isinstance(data, dict):
        raise TypeError(f"storyboard must be a dict or list, got {type(data).__name__}")
    return deepcopy(data)


def normalize_storyboard(storyboard: Any, frame_rate: float = DEFAULT_FRAME_RATE) -> dict:
    """
    Normalize legacy and v2 storyboard forms into a stable IR.

    Defaults:
      - shot 0 ref=original; later shots ref=previous
      - missing segment_id -> 0
      - missing transition -> transition
      - missing time_sec/frame_idx -> cumulative legacy duration_sec
    """
    data = _flatten_legacy(storyboard)
    raw_shots = data.get("shots") or []
    if not isinstance(raw_shots, list):
        raise TypeError("storyboard['shots'] must be a list")

    normalized: dict[str, Any] = {
        "schema_version": data.get("schema_version", "game_cg_storyboard_v2_minimal"),
        "video_prompt": _clean(data.get("video_prompt")),
        "character_prompt": _clean(data.get("character_prompt")),
        "style_prompt": _clean(data.get("style_prompt")),
        "duration_sec": data.get("duration_sec"),
        "shots": [],
    }

    cumulative_sec = 0.0
    for idx, raw in enumerate(raw_shots):
        if not isinstance(raw, dict):
            raise TypeError(f"shot {idx} must be a dict")

        shot = deepcopy(raw)
        shot_id = _as_int(shot.get("shot_id"), idx)
        description = _clean(shot.get("description"))

        has_frame = "frame_idx" in shot and shot.get("frame_idx") is not None
        has_time = "time_sec" in shot and shot.get("time_sec") is not None

        if has_frame:
            frame_idx = _as_int(shot.get("frame_idx"), 0)
            time_sec = frame_idx / frame_rate
        elif has_time:
            time_sec = _as_float(shot.get("time_sec"), cumulative_sec)
            frame_idx = max(0, round(time_sec * frame_rate))
        else:
            time_sec = cumulative_sec
            frame_idx = max(0, round(time_sec * frame_rate))

        if not has_frame:
            shot.pop("frame_idx", None)

        shot.update(
            {
                "shot_id": shot_id,
                "beat_role": _clean(shot.get("beat_role")) or f"beat_{idx}",
                "segment_id": _as_int(shot.get("segment_id"), 0),
                "transition": _clean(shot.get("transition")) or "transition",
                "time_sec": float(time_sec),
                "resolved_frame_idx": int(frame_idx),
                "ref": _clean(shot.get("ref")) or ("original" if idx == 0 else "previous"),
                "strength": _as_float(
                    shot.get("strength"),
                    1.0 if idx in (0, len(raw_shots) - 1) else 0.9,
                ),
                "camera": _clean(shot.get("camera")),
                "subject": _clean(shot.get("subject")) or description,
                "vfx": _clean(shot.get("vfx")),
                "description": description,
                "image_prompt": _clean(shot.get("image_prompt")),
                "motion_prompt": _clean(shot.get("motion_prompt")),
            }
        )
        normalized["shots"].append(shot)
        cumulative_sec = time_sec + _as_float(raw.get("duration_sec"), 1.0)

    if normalized["duration_sec"] is None:
        if normalized["shots"]:
            last = max(s["time_sec"] for s in normalized["shots"])
            normalized["duration_sec"] = round(last + 1.0, 3)
        else:
            normalized["duration_sec"] = 0.0
    normalized["duration_sec"] = _as_float(normalized["duration_sec"], 0.0)
    return normalized


def _join_prompt(parts: Iterable[tuple[str, Any]]) -> str:
    lines = []
    for label, value in parts:
        text = _clean(value)
        if text:
            lines.append(f"{label}: {text}.")
    return " ".join(lines)


def _compile_image_prompt(storyboard: dict, shot: dict) -> str:
    base = _join_prompt(
        [
            ("Static keyframe goal", shot.get("image_prompt") or shot.get("description")),
            ("Beat role", shot.get("beat_role")),
            ("Character continuity", storyboard.get("character_prompt")),
            ("Camera and composition", shot.get("camera")),
            ("Subject pose and action", shot.get("subject")),
            ("VFX state", shot.get("vfx")),
            ("Visual style", storyboard.get("style_prompt")),
        ]
    )
    constraints = (
        "Create one crisp cinematic keyframe, not a storyboard panel. Preserve the "
        "same character identity, face, straw hat, red vest, clothing details, body "
        "proportions, and pose intent. If the requested beat changes the pose, change "
        "the pose decisively instead of copying the reference pose. Emphasize readable "
        "silhouette, AAA game CG lighting, clean anatomy, no text, no watermark."
    )
    return f"{base} {constraints}".strip()


def _compile_motion_prompt(storyboard: dict, shot: dict) -> str:
    base = _join_prompt(
        [
            ("Timeline cue", f"at {shot.get('time_sec', 0.0):.2f}s"),
            ("Beat role", shot.get("beat_role")),
            ("Shot motion intent", shot.get("motion_prompt") or shot.get("description")),
            ("Camera movement", shot.get("camera")),
            ("Character movement", shot.get("subject")),
            ("VFX evolution", shot.get("vfx")),
            ("Transition mode", shot.get("transition")),
            ("Segment", shot.get("segment_id")),
        ]
    )
    return (
        f"{base} Keep the motion physically continuous around this keyframe and "
        "preserve character identity, costume, scale, and screen direction."
    ).strip()


def compile_storyboard_prompts(storyboard: dict) -> dict:
    """Compile structured IR into Qwen image prompts and a chronological LTX prompt."""
    data = deepcopy(storyboard)
    shots = sorted(data.get("shots", []), key=lambda s: (s.get("time_sec", 0.0), s.get("shot_id", 0)))
    compiled_motion = []
    for shot in data.get("shots", []):
        shot["image_prompt"] = _compile_image_prompt(data, shot)
        shot["motion_prompt"] = _compile_motion_prompt(data, shot)
    for shot in shots:
        compiled_motion.append(f"{shot['time_sec']:.2f}s {shot['beat_role']}: {shot['motion_prompt']}")

    header = _join_prompt(
        [
            ("Video objective", data.get("video_prompt")),
            ("Style", data.get("style_prompt")),
            ("Character", data.get("character_prompt")),
        ]
    )
    data["compiled_video_prompt"] = (
        f"{header} Chronological motion plan: " + " ".join(compiled_motion)
    ).strip()
    return data


def validate_storyboard_timing(
    storyboard: dict,
    frame_rate: float = DEFAULT_FRAME_RATE,
    min_frame_gap: int = DEFAULT_MIN_FRAME_GAP,
    tail_frames: int = DEFAULT_TAIL_FRAMES,
    print_rows: bool = True,
) -> list[str]:
    """Validate timing and return warning strings. Raises ValueError on invalid IR."""
    shots = storyboard.get("shots") or []
    if not shots:
        raise ValueError("storyboard must contain at least one shot")

    duration_sec = _as_float(storyboard.get("duration_sec"), 0.0)
    if duration_sec <= 0:
        raise ValueError("duration_sec must be greater than 0")

    rows: list[str] = []
    warnings: list[str] = []
    prev_time = -math.inf
    prev_frame = -1
    prev_segment = None
    closed_segments: set[int] = set()
    seen_times: set[float] = set()
    seen_frames: set[int] = set()

    for idx, shot in enumerate(shots):
        segment_id = _as_int(shot.get("segment_id"), 0)
        if prev_segment is not None and segment_id != prev_segment:
            closed_segments.add(prev_segment)
        if segment_id in closed_segments and segment_id != prev_segment:
            raise ValueError(
                f"segment_id {segment_id} is not contiguous; shots in the same segment must be adjacent"
            )
        prev_segment = segment_id

        has_frame = "frame_idx" in shot and shot.get("frame_idx") is not None
        has_time = "time_sec" in shot and shot.get("time_sec") is not None
        if has_frame and has_time:
            warning = (
                f"shot {shot.get('shot_id', idx)} has both frame_idx and time_sec; "
                "frame_idx takes priority"
            )
            warnings.append(warning)
            print(f"[storyboard warning] {warning}")

        if has_frame:
            frame_idx = _as_int(shot.get("frame_idx"), 0)
            time_sec = frame_idx / frame_rate
        else:
            time_sec = _as_float(shot.get("time_sec"), 0.0)
            frame_idx = max(0, round(time_sec * frame_rate))
        shot["resolved_frame_idx"] = frame_idx

        rounded_time = round(time_sec, 6)
        if rounded_time in seen_times:
            raise ValueError(f"duplicate time_sec at shot {shot.get('shot_id', idx)}: {time_sec}")
        if frame_idx in seen_frames:
            raise ValueError(f"duplicate resolved frame_idx at shot {shot.get('shot_id', idx)}: {frame_idx}")
        if time_sec <= prev_time:
            raise ValueError("time_sec must be strictly increasing")
        if idx > 0 and frame_idx - prev_frame < min_frame_gap:
            raise ValueError(
                f"adjacent keyframes too close: frame {prev_frame} -> {frame_idx}; "
                f"minimum gap is {min_frame_gap} frames"
            )
        if time_sec >= duration_sec:
            raise ValueError(
                f"last/effective time_sec must be less than duration_sec; got {time_sec} >= {duration_sec}"
            )

        seen_times.add(rounded_time)
        seen_frames.add(frame_idx)
        prev_time = time_sec
        prev_frame = frame_idx

        row = (
            "[storyboard] "
            f"shot_id={shot.get('shot_id', idx)} "
            f"beat_role={shot.get('beat_role', '')} "
            f"segment_id={segment_id} "
            f"time_sec={time_sec:.3f} "
            f"frame_idx={frame_idx} "
            f"ref={shot.get('ref', '')} "
            f"strength={shot.get('strength', '')}"
        )
        rows.append(row)
        if print_rows:
            print(row)

    total_frames = max(1, round(duration_sec * frame_rate))
    if total_frames - prev_frame < tail_frames:
        raise ValueError(
            f"duration_sec={duration_sec} does not leave a reasonable tail after "
            f"last keyframe frame {prev_frame}; need at least {tail_frames} frames"
        )
    return warnings


def write_resolved_storyboard(storyboard: dict, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(storyboard, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _load_font(size: int = 16):
    for candidate in ("DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def build_contact_sheet(
    storyboard: dict,
    image_paths: list[str],
    output_path: str | Path,
    thumb_width: int = 360,
    label_height: int = 156,
    columns: int = 2,
) -> str:
    """Create a labeled contact sheet for generated storyboard frames."""
    shots = storyboard.get("shots") or []
    if len(shots) != len(image_paths):
        raise ValueError(f"{len(shots)} shots but {len(image_paths)} images")

    font = _load_font(15)
    small = _load_font(13)
    thumbs = []
    for path in image_paths:
        img = Image.open(path).convert("RGB")
        ratio = thumb_width / img.width
        thumb_height = max(1, int(img.height * ratio))
        thumbs.append(img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS))

    cell_h = max(t.height for t in thumbs) + label_height
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * thumb_width, rows * cell_h), "white")
    draw = ImageDraw.Draw(sheet)

    for i, (shot, thumb) in enumerate(zip(shots, thumbs)):
        x = (i % columns) * thumb_width
        y = (i // columns) * cell_h
        sheet.paste(thumb, (x, y))
        label_y = y + thumb.height + 6
        label_lines = [
            f"shot {shot.get('shot_id')} | {shot.get('beat_role')} | seg {shot.get('segment_id')}",
            f"t={shot.get('time_sec'):.2f}s | f={shot.get('resolved_frame_idx')} | ref={shot.get('ref')}",
            shot.get("subject") or shot.get("description") or "",
        ]
        wrapped = []
        for label in label_lines:
            wrapped.extend(textwrap.wrap(label, width=44) or [""])
        for line in wrapped[:7]:
            draw.text((x + 8, label_y), line, fill=(20, 20, 20), font=font if label_y < y + thumb.height + 28 else small)
            label_y += 18

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return str(out)


def get_git_summary(repo_root: str | Path) -> dict:
    root = Path(repo_root)

    def run(args: list[str]) -> str:
        result = subprocess.run(args, cwd=root, text=True, capture_output=True)
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()

    return {
        "commit": run(["git", "rev-parse", "HEAD"]),
        "status_short": run(["git", "status", "--short"]).splitlines(),
        "diff_stat": run(["git", "diff", "--stat"]),
    }


def build_run_manifest(
    storyboard_input: str,
    storyboard: dict,
    output_files: dict,
    cfg: dict,
    params: dict,
    started_at: float,
    repo_root: str | Path,
    run_command: str | None = None,
) -> dict:
    shots = storyboard.get("shots") or []
    return {
        "storyboard_input": storyboard_input,
        "normalized_storyboard": storyboard,
        "compiled_prompts": [
            {
                "shot_id": shot.get("shot_id"),
                "image_prompt": shot.get("image_prompt"),
                "motion_prompt": shot.get("motion_prompt"),
                "ref": shot.get("ref"),
            }
            for shot in shots
        ],
        "outputs": output_files,
        "seed": params.get("seed"),
        "fps": params.get("frame_rate"),
        "height": params.get("height"),
        "width": params.get("width"),
        "models": {
            "gen_image_model": cfg.get("gen_image_model"),
            "ltx_root": cfg.get("ltx_root"),
            "gemma_root": cfg.get("gemma_root"),
        },
        "offload": cfg.get("offload", "none"),
        "quantization": cfg.get("quantization"),
        "git": get_git_summary(repo_root),
        "run_command": run_command,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started_at)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runtime_sec": round(time.time() - started_at, 3),
    }


def write_run_manifest(manifest: dict, output_path: str | Path) -> str:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)
