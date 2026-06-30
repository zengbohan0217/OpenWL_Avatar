"""
gen_cg_video.py — Build LTX keyframes from storyboard and run ONE generation.

Storyboard schema (timing-aware):
    {
        "video_prompt":  "<global cinematic narrative>",
        "duration_sec":  <total video length, optional — defaults to last keyframe time>,
        "shots": [
            {
                "shot_id":     0,
                "image_prompt": "...",
                "time_sec":    0.0,        # WHEN this keyframe appears (seconds)
                "strength":    0.9,        # optional, default 1.0 for first/last, 0.9 otherwise
                # OR you can use the legacy fields:
                "frame_idx":   0,          # absolute frame index (wins over time_sec)
                "duration_sec": 1.0,       # back-compat: per-shot duration → cumulative time
                ...
            },
            ...
        ]
    }

Resolution priority for each shot's frame position:
    1. shot["frame_idx"]                    — explicit frame index
    2. shot["time_sec"] * frame_rate        — explicit time in seconds
    3. cumulative shot["duration_sec"]      — legacy fallback
"""

import os
import shlex
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Optional, List

from ltx_pipelines.utils.args import ImageConditioningInput

from models.gen_video.ltx import LTXModel, snap_frames, DEFAULT_FPS
from operators.gen_game_cg.funcs.storyboard_ir import validate_storyboard_timing


def _resolve_positions(shots: list, frame_rate: float) -> List[int]:
    """
    Resolve each shot's frame_idx using the priority:
        frame_idx > time_sec*frame_rate > cumulative duration_sec.
    """
    positions: List[int] = []
    cum_seconds = 0.0
    for i, shot in enumerate(shots):
        if "resolved_frame_idx" in shot:
            positions.append(int(shot["resolved_frame_idx"]))
        elif "frame_idx" in shot:
            positions.append(int(shot["frame_idx"]))
        elif "time_sec" in shot:
            positions.append(max(0, round(float(shot["time_sec"]) * frame_rate)))
        else:
            # Legacy: cumulative duration_sec → start of next shot
            if i == 0:
                positions.append(0)
            else:
                positions.append(max(0, round(cum_seconds * frame_rate)))
            cum_seconds += float(shot.get("duration_sec", 3.0))
    return positions


def _resolve_total_frames(storyboard: dict, shots: list,
                          positions: List[int], frame_rate: float) -> int:
    """Resolve total num_frames in this priority:
        storyboard["num_frames"] > storyboard["duration_sec"]*fps >
        last shot frame_idx + 1, or last cumulative duration.
    """
    if "num_frames" in storyboard:
        return snap_frames(int(storyboard["num_frames"]))
    if "duration_sec" in storyboard:
        return snap_frames(max(9, round(float(storyboard["duration_sec"]) * frame_rate)))

    # Try sum of per-shot duration_sec (legacy)
    if all("duration_sec" in s for s in shots):
        total_sec = sum(float(s["duration_sec"]) for s in shots)
        return snap_frames(max(9, round(total_sec * frame_rate)))

    # Fallback: last keyframe position + 1 second of tail
    last = (max(positions) if positions else 0) + int(round(frame_rate))
    return snap_frames(max(9, last))


def _build_keyframes(storyboard: dict, shot_images: List[str],
                     frame_rate: float) -> tuple:
    """Build (keyframes, total_num_frames) from a timing-aware storyboard."""
    shots = storyboard.get("shots", [])
    if len(shots) != len(shot_images):
        raise ValueError(f"{len(shots)} shots but {len(shot_images)} images.")

    positions = _resolve_positions(shots, frame_rate)
    total = _resolve_total_frames(storyboard, shots, positions, frame_rate)

    # Clamp positions into [0, total-1]
    positions = [max(0, min(p, total - 1)) for p in positions]

    keyframes = []
    for i, (shot, img, idx) in enumerate(zip(shots, shot_images, positions)):
        is_anchor = (i == 0) or (i == len(shots) - 1)
        default_strength = 1.0 if is_anchor else 0.9
        strength = float(shot.get("strength", default_strength))
        keyframes.append(ImageConditioningInput(
            path=img, frame_idx=idx, strength=strength,
        ))
    return keyframes, total


def _build_keyframes_for_segment(
    segment_storyboard: dict,
    segment_images: List[str],
    positions: List[int],
    total_frames: int,
) -> tuple:
    shots = segment_storyboard.get("shots", [])
    keyframes = []
    for i, (shot, img, idx) in enumerate(zip(shots, segment_images, positions)):
        is_anchor = (i == 0) or (i == len(shots) - 1)
        default_strength = 1.0 if is_anchor else 0.9
        keyframes.append(ImageConditioningInput(
            path=img,
            frame_idx=max(0, min(idx, total_frames - 1)),
            strength=float(shot.get("strength", default_strength)),
        ))
    return keyframes, snap_frames(total_frames)


def _prompt_for_segment(storyboard: dict, shots: list) -> str:
    header = storyboard.get("compiled_video_prompt") or storyboard.get("video_prompt", "")
    motion = " ".join(
        f"{shot.get('time_sec', 0.0):.2f}s {shot.get('beat_role', '')}: {shot.get('motion_prompt', '')}"
        for shot in shots
    )
    return f"{header} Segment motion focus: {motion}".strip()


def _find_ffmpeg(ffmpeg_path: Optional[str] = None) -> str:
    if ffmpeg_path:
        return ffmpeg_path
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError("ffmpeg is required for segment concat") from exc


def _concat_clips(clips: list[str], output_path: str, ffmpeg_path: Optional[str] = None) -> str:
    if not clips:
        raise ValueError("no clips to concat")
    ffmpeg = _find_ffmpeg(ffmpeg_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    list_path = out.parent / "concat_list.txt"
    list_root = list_path.parent.resolve()
    with open(list_path, "w", encoding="utf-8") as f:
        for clip in clips:
            clip_path = Path(clip).resolve()
            clip_entry = os.path.relpath(clip_path, start=list_root)
            f.write(f"file {shlex.quote(clip_entry)}\n")
    cmd = [ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", str(list_path), "-c", "copy", str(out)]
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed:\n{result.stderr}")
    return str(out)


def _segment_groups(storyboard: dict, shot_images: List[str], frame_rate: float):
    shots = storyboard.get("shots", [])
    positions = _resolve_positions(shots, frame_rate)
    total = _resolve_total_frames(storyboard, shots, positions, frame_rate)

    groups = []
    current = None
    closed_segments = set()
    for idx, (shot, image, pos) in enumerate(zip(shots, shot_images, positions)):
        segment_id = shot.get("segment_id", 0)
        if current is None or current["segment_id"] != segment_id:
            if segment_id in closed_segments:
                raise ValueError(
                    f"segment_id {segment_id} is not contiguous; shots in the same segment "
                    "must be adjacent"
                )
            if current is not None:
                closed_segments.add(current["segment_id"])
            current = {"segment_id": segment_id, "items": []}
            groups.append(current)
        current["items"].append((idx, shot, image, pos))
    return groups, total


def _generate_segmented(
    storyboard: dict,
    shot_images: List[str],
    model: LTXModel,
    output_path: str,
    frame_rate: float,
    height: int,
    width: int,
    negative_prompt: Optional[str],
    seed: int,
    clips_dir: Optional[str],
    ffmpeg_path: Optional[str],
) -> str:
    groups, total_frames = _segment_groups(storyboard, shot_images, frame_rate)
    clips_root = Path(clips_dir or (Path(output_path).parent / "clips"))
    clips_root.mkdir(parents=True, exist_ok=True)
    clips = []
    segment_manifest = []

    for group_idx, group in enumerate(groups):
        items = group["items"]
        start = items[0][3]
        if group_idx + 1 < len(groups):
            end = groups[group_idx + 1]["items"][0][3]
        else:
            end = total_frames
        local_positions = [max(0, item[3] - start) for item in items]
        segment_frames = max(max(local_positions) + 1, end - start)
        segment_frames = snap_frames(segment_frames)
        segment_shots = [deepcopy(item[1]) for item in items]
        segment_images = [item[2] for item in items]
        for shot, local_idx in zip(segment_shots, local_positions):
            shot["resolved_frame_idx"] = local_idx

        segment_storyboard = deepcopy(storyboard)
        segment_storyboard["shots"] = segment_shots
        segment_prompt = _prompt_for_segment(storyboard, segment_shots)
        keyframes, num_frames = _build_keyframes_for_segment(
            segment_storyboard,
            segment_images,
            local_positions,
            segment_frames,
        )
        clip_path = str(clips_root / f"segment_{group_idx:02d}_id_{group['segment_id']:02d}.mp4")
        model.generate(
            prompt=segment_prompt,
            keyframes=keyframes,
            num_frames=num_frames,
            output_path=clip_path,
            frame_rate=frame_rate,
            height=height,
            width=width,
            negative_prompt=negative_prompt,
            seed=seed,
        )
        clips.append(clip_path)
        segment_manifest.append({
            "segment_id": group["segment_id"],
            "clip": clip_path,
            "global_start_frame": start,
            "global_end_frame": end,
            "local_frame_indices": local_positions,
            "shot_ids": [item[1].get("shot_id") for item in items],
        })

    storyboard["_segment_outputs"] = segment_manifest
    storyboard["_concat_command"] = "ffmpeg concat"
    return _concat_clips(clips, output_path, ffmpeg_path=ffmpeg_path)


def gen_cg_video(
    storyboard: dict,
    shot_images: List[str],
    model: LTXModel,
    output_path: str = "output/cg_final.mp4",
    frame_rate: float = DEFAULT_FPS,
    height: int = 768,
    width: int = 1152,
    negative_prompt: Optional[str] = None,
    seed: int = 42,
    clips_dir: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
) -> str:
    """Generate the CG video using one LTX call or segment-level LTX calls."""
    validate_storyboard_timing(storyboard, frame_rate=frame_rate)
    segment_ids = [shot.get("segment_id", 0) for shot in storyboard.get("shots", [])]
    if len(set(segment_ids)) > 1:
        return _generate_segmented(
            storyboard,
            shot_images,
            model,
            output_path,
            frame_rate,
            height,
            width,
            negative_prompt,
            seed,
            clips_dir,
            ffmpeg_path,
        )

    global_prompt = storyboard.get("compiled_video_prompt") or storyboard.get("video_prompt", "")
    keyframes, num_frames = _build_keyframes(storyboard, shot_images, frame_rate)
    storyboard["_segment_outputs"] = []

    return model.generate(
        prompt=global_prompt,
        keyframes=keyframes,
        num_frames=num_frames,
        output_path=output_path,
        frame_rate=frame_rate,
        height=height, width=width,
        negative_prompt=negative_prompt,
        seed=seed,
    )
