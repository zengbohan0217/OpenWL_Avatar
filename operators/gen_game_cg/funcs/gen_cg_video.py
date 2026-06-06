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

from typing import Optional, List

from ltx_pipelines.utils.args import ImageConditioningInput

from models.gen_video.ltx import LTXModel, snap_frames, DEFAULT_FPS


def _resolve_positions(shots: list, frame_rate: float) -> List[int]:
    """
    Resolve each shot's frame_idx using the priority:
        frame_idx > time_sec*frame_rate > cumulative duration_sec.
    """
    positions: List[int] = []
    cum_seconds = 0.0
    for i, shot in enumerate(shots):
        if "frame_idx" in shot:
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
) -> str:
    """Generate the entire CG video in ONE LTX call."""
    global_prompt = storyboard.get("video_prompt", "")
    keyframes, num_frames = _build_keyframes(storyboard, shot_images, frame_rate)

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
