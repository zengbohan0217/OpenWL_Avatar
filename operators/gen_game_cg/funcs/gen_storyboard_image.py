"""
gen_storyboard_image.py — Generate a keyframe image for each storyboard shot
using QwenEditModel. Each image is later passed to LTX as ImageConditioningInput.
"""

from pathlib import Path
from PIL import Image


def gen_shot_image(shot: dict, ref_image: Image.Image, model,
                   output_dir: str = "output/storyboard") -> str:
    """Generate one keyframe image for a shot. Returns the saved path."""
    shot_id = shot.get("shot_id", 0)
    prompt  = shot.get("image_prompt",
                       shot.get("video_prompt",
                                shot.get("description", "")))
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    output_path = str(Path(output_dir) / f"shot_{shot_id:02d}.png")

    image = model.edit(ref_image, prompt)
    image.save(output_path)
    return output_path


def gen_storyboard_images(shots: list, ref_image: Image.Image, model,
                          output_dir: str = "output/storyboard") -> list:
    """Generate keyframe images for all shots. Returns List[str] of paths."""
    return [gen_shot_image(shot, ref_image, model, output_dir) for shot in shots]
