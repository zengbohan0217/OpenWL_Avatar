"""
gen_storyboard_image.py — Generate a keyframe image for each storyboard shot
using QwenEditModel.

Each shot's `ref` field controls which image is used as the QwenEdit reference:
  - "original" (default for shot 0): use the original ref_image (e.g. character portrait)
  - "previous":                      use the previous shot's generated image
  - "<shot_id>" (int) or "shot_<id>": use that specific shot's generated image

This enables visual continuity — each shot can be edited from the previous frame.
"""

from pathlib import Path
from typing import Union
from PIL import Image


def _resolve_ref(ref_field, original: Image.Image,
                 generated: list, shot_idx: int) -> Image.Image:
    """Resolve the `ref` field to an actual PIL.Image."""
    # Default: shot 0 → original; subsequent shots → previous
    if ref_field is None:
        return original if shot_idx == 0 else generated[shot_idx - 1]

    if isinstance(ref_field, str):
        if ref_field in ("original", "ref", "src"):
            return original
        if ref_field in ("previous", "prev", "last"):
            if shot_idx == 0:
                return original
            return generated[shot_idx - 1]
        if ref_field.startswith("shot_"):
            idx = int(ref_field.split("_", 1)[1])
            return generated[idx]
        # Numeric string
        if ref_field.lstrip("-").isdigit():
            return generated[int(ref_field)]
        # Treat as a file path
        if Path(ref_field).exists():
            return Image.open(ref_field)
        raise ValueError(f"Unrecognized ref: {ref_field!r}")

    if isinstance(ref_field, int):
        return generated[ref_field]

    raise TypeError(f"ref must be str/int/None, got {type(ref_field).__name__}")


def gen_shot_image(shot: dict, ref_image: Image.Image, model,
                   output_dir: str = "output/storyboard",
                   seed: int = 42) -> str:
    """Generate one keyframe image for a shot. Returns the saved path."""
    shot_id = shot.get("shot_id", 0)
    prompt  = shot.get("image_prompt",
                       shot.get("video_prompt",
                                shot.get("description", "")))
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(output_dir) / f"shot_{shot_id:02d}.png")

    image = model.edit(ref_image, prompt, seed=seed)
    image.save(output_path)
    return output_path


def gen_storyboard_images(shots: list, ref_image: Image.Image, model,
                          output_dir: str = "output/storyboard",
                          seed: int = 42) -> list:
    """
    Generate keyframe images for all shots, with chained reference support.

    Each shot's `ref` field determines what image is used as QwenEdit input:
      - default: shot 0 uses ref_image, shot i (i>0) uses shot i-1's output
      - "original": always use the input ref_image
      - "previous": use previous shot's output
      - "shot_<id>" / int: use a specific earlier shot's output

    Returns:
        List[str]: paths of generated keyframe images, in shot order.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    paths: list = []
    images: list = []  # PIL.Image cache for chained ref resolution

    for i, shot in enumerate(shots):
        src = _resolve_ref(shot.get("ref"), ref_image, images, i)

        shot_id = shot.get("shot_id", i)
        prompt  = shot.get("image_prompt",
                           shot.get("video_prompt",
                                    shot.get("description", "")))
        out_path = str(Path(output_dir) / f"shot_{shot_id:02d}.png")

        img = model.edit(src, prompt, seed=seed)
        img.save(out_path)

        paths.append(out_path)
        images.append(img)

    return paths
