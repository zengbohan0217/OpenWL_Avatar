"""
gen_storyboard.py — Get a storyboard either from a JSON file or a reasoning model.

Storyboard format (group-based):
    [
        {
            "group_id": 0,
            "shots": [
                {"shot_id": 0, "description": "...", "video_prompt": "...", "duration_sec": 3},
                ...
            ]
        },
        ...
    ]

Each "group" is one LTX KeyframeInterpolationPipeline call: all its shot images
are passed as keyframes simultaneously and the model interpolates between them.
Groups are concatenated at the end.
"""

import json
from pathlib import Path


def load_storyboard(storyboard_path: str) -> list:
    """Load grouped storyboard from a JSON file. Auto-wraps a flat shot list."""
    with open(storyboard_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        data = [data]
    # Back-compat: if it's a flat list of shots, wrap each as its own group
    if data and "shots" not in data[0]:
        data = [{"group_id": i, "shots": [s]} for i, s in enumerate(data)]
    return data


_GEN_PROMPT = """\
You are a game cinematic director. Given a script, break it into 2-3 groups of shots.
Each group is a sequence of 1-3 closely related shots that should be smoothly interpolated together.
Return a JSON array. Each element has:
  - group_id: integer starting from 0
  - shots: list of shot dicts, each with:
      - shot_id: integer starting from 0 (global across all groups)
      - description: one-sentence shot description
      - video_prompt: detailed prompt for image-to-video (cinematic, game-style)
      - duration_sec: estimated duration in seconds (2-5)
Only output valid JSON, no extra text."""


def gen_storyboard(script: str, model) -> list:
    """Generate grouped storyboard from a script using a reasoning/VLM model."""
    data = model.infer_json(f"{_GEN_PROMPT}\n\nScript:\n{script}")
    if not isinstance(data, list):
        data = [data]
    if data and "shots" not in data[0]:
        data = [{"group_id": i, "shots": [s]} for i, s in enumerate(data)]
    return data


def get_storyboard(script_or_path: str, model=None) -> list:
    """Unified entry: load from file if path exists, otherwise generate via model."""
    if Path(script_or_path).exists():
        return load_storyboard(script_or_path)
    if model is None:
        raise ValueError("model is required when script_or_path is not a file path.")
    return gen_storyboard(script_or_path, model)


def flatten_shots(groups: list) -> list:
    """Flatten grouped storyboard into a single list of shots."""
    return [shot for group in groups for shot in group.get("shots", [])]
