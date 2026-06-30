"""
gen_storyboard.py — Get a storyboard either from a JSON file or a reasoning model.

Storyboard format:
    {
        "video_prompt": "<global cinematic narrative fed to LTX>",
        "character_prompt": "<identity and costume continuity>",
        "style_prompt": "<rendering style>",
        "duration_sec": 4.8,
        "shots": [
            {
                "shot_id": 0,
                "beat_role": "setup",
                "segment_id": 0,
                "transition": "transition",
                "time_sec": 0.0,
                "ref": "original",
                "strength": 1.0,
                "camera": "...",
                "subject": "...",
                "vfx": "..."
            },
            ...
        ]
    }

`video_prompt` is the single global prompt for LTX (camera narrative, pacing,
continuous-take instruction). `image_prompt` per-shot is for QwenEdit only.
All shot images are passed as keyframes to ONE KeyframeInterpolationPipeline call.
"""

import json
from pathlib import Path

from operators.gen_game_cg.funcs.storyboard_ir import (
    compile_storyboard_prompts,
    normalize_storyboard,
)


def load_storyboard(storyboard_path: str) -> dict:
    """Load storyboard from JSON and normalize it into storyboard v2 IR."""
    with open(storyboard_path, "r") as f:
        data = json.load(f)
    return compile_storyboard_prompts(normalize_storyboard(data))


_GEN_PROMPT = """\
You are a game cinematic director. Given a script, return JSON with:
  - video_prompt: a single global cinematic narrative describing camera
    movement (e.g. "start wide, slowly push in"), pacing, lighting, and
    overall style. State explicitly that it is ONE continuous take with NO cuts.
    This is fed to a video generation model.
  - character_prompt: one stable character identity/costume description.
  - style_prompt: one stable rendering style.
  - duration_sec: total duration in seconds.
  - shots: list of 5-6 shots covering setup, anticipation, charge, release,
    impact, aftermath. Each shot has:
      - shot_id: integer starting from 0
      - beat_role: one of setup, anticipation, charge, release, impact, aftermath
      - segment_id: integer, usually 0 unless a separate LTX clip should be generated
      - transition: transition
      - time_sec: strictly increasing keyframe time
      - ref: original or previous
      - strength: keyframe conditioning strength from 0.0 to 1.0
      - camera: camera framing and movement
      - subject: character pose/action at the keyframe
      - vfx: VFX state at the keyframe
Only output valid JSON, no extra text."""


def gen_storyboard(script: str, model) -> dict:
    """Generate storyboard from a script using a reasoning/VLM model."""
    data = model.infer_json(f"{_GEN_PROMPT}\n\nScript:\n{script}")
    return compile_storyboard_prompts(normalize_storyboard(data))


def get_storyboard(script_or_path: str, model=None) -> dict:
    """Unified entry: load from file if path exists, otherwise generate via model."""
    if Path(script_or_path).exists():
        return load_storyboard(script_or_path)
    if model is None:
        raise ValueError("model is required when script_or_path is not a file path.")
    return gen_storyboard(script_or_path, model)
