"""
gen_storyboard.py — Get a storyboard either from a JSON file or a reasoning model.

Storyboard format:
    {
        "video_prompt": "<global cinematic narrative fed to LTX>",
        "shots": [
            {"shot_id": 0, "description": "...", "image_prompt": "...", "duration_sec": 3},
            ...
        ]
    }

`video_prompt` is the single global prompt for LTX (camera narrative, pacing,
continuous-take instruction). `image_prompt` per-shot is for QwenEdit only.
All shot images are passed as keyframes to ONE KeyframeInterpolationPipeline call.
"""

import json
from pathlib import Path


def load_storyboard(storyboard_path: str) -> dict:
    """Load storyboard from JSON. Normalizes legacy formats into {video_prompt, shots}."""
    with open(storyboard_path, "r") as f:
        data = json.load(f)

    # Back-compat: list of groups -> flatten; list of shots -> wrap.
    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "shots" in data[0]:
            shots = [s for g in data for s in g.get("shots", [])]
            video_prompt = data[0].get("video_prompt", "")
        else:
            shots = data
            video_prompt = ""
        data = {"video_prompt": video_prompt, "shots": shots}

    data.setdefault("video_prompt", "")
    data.setdefault("shots", [])
    return data


_GEN_PROMPT = """\
You are a game cinematic director. Given a script, return JSON with:
  - video_prompt: a single global cinematic narrative describing camera
    movement (e.g. "start wide, slowly push in"), pacing, lighting, and
    overall style. State explicitly that it is ONE continuous take with NO cuts.
    This is fed to a video generation model.
  - shots: list of 2-4 shots. Each shot has:
      - shot_id: integer starting from 0
      - description: one-sentence description
      - image_prompt: prompt for an image edit model that creates the keyframe
      - duration_sec: 2-5
Only output valid JSON, no extra text."""


def gen_storyboard(script: str, model) -> dict:
    """Generate storyboard from a script using a reasoning/VLM model."""
    data = model.infer_json(f"{_GEN_PROMPT}\n\nScript:\n{script}")
    if isinstance(data, list):
        data = {"video_prompt": "", "shots": data}
    data.setdefault("video_prompt", "")
    data.setdefault("shots", [])
    return data


def get_storyboard(script_or_path: str, model=None) -> dict:
    """Unified entry: load from file if path exists, otherwise generate via model."""
    if Path(script_or_path).exists():
        return load_storyboard(script_or_path)
    if model is None:
        raise ValueError("model is required when script_or_path is not a file path.")
    return gen_storyboard(script_or_path, model)
