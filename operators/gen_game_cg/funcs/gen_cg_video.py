"""
gen_cg_video.py — Build LTX keyframes from storyboard and run ONE generation.

Layout: each shot's image is pinned at its cumulative frame index. The first
shot at frame 0, the last shot at frame (total-1). LTX interpolates everything
in between as one continuous take (no cuts, no concat).
"""

from typing import Optional, List

from ltx_pipelines.utils.args import ImageConditioningInput

from models.gen_video.ltx import LTXModel, snap_frames, DEFAULT_FPS


def _build_keyframes(shots: list, shot_images: List[str],
                     frame_rate: float) -> tuple:
    """
    Build (keyframes, total_num_frames) from storyboard shots.

    Per-shot overrides supported in storyboard JSON:
      - frame_idx: absolute frame position for this keyframe (overrides default)
      - strength:  ImageConditioningInput strength (overrides default)

    Default layout: each shot's image is pinned at its cumulative frame index
    based on `duration_sec`; boundary frames are shared between consecutive shots.
    Default strength: 1.0 for first/last anchor, 0.9 for intermediate keyframes.
    """
    if len(shots) != len(shot_images):
        raise ValueError(f"{len(shots)} shots but {len(shot_images)} images.")

    per_shot_frames = [
        snap_frames(max(9, round(float(s.get("duration_sec", 3.0)) * frame_rate)))
        for s in shots
    ]

    if len(shots) == 1:
        total = per_shot_frames[0]
        default_positions = [0]
    else:
        cum = 0
        default_positions = [0]
        for n in per_shot_frames[:-1]:
            cum += n - 1
            default_positions.append(cum)
        total = snap_frames(cum + per_shot_frames[-1])
        default_positions[-1] = total - 1

    # Allow shots to override frame_idx; recompute total to cover any larger override
    final_positions = []
    for shot, default_idx in zip(shots, default_positions):
        idx = int(shot.get("frame_idx", default_idx))
        final_positions.append(idx)
    total = max(total, max(final_positions) + 1)
    total = snap_frames(total)

    # Build keyframes with per-shot strength override
    keyframes = []
    for i, (shot, img, idx) in enumerate(zip(shots, shot_images, final_positions)):
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
    """
    Generate the entire CG video in ONE LTX call.

    Args:
        storyboard:  {"video_prompt": str, "shots": [...]}.
        shot_images: List of keyframe image paths, one per shot.
        model:       Loaded LTXModel.
    """
    shots         = storyboard.get("shots", [])
    global_prompt = storyboard.get("video_prompt", "")

    keyframes, num_frames = _build_keyframes(shots, shot_images, frame_rate)

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
