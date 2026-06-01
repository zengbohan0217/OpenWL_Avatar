"""
gen_storyboard_image.py — Generate a scene image for each storyboard shot.

The generated image serves as a keyframe (ImageConditioningInput) for LTX
KeyframeInterpolationPipeline. Uses QwenEditModel: takes a reference character
image + shot prompt → scene image.
"""

from pathlib import Path
from PIL import Image


def gen_shot_image(shot: dict, ref_image: Image.Image, model,
                   output_dir: str = "output/storyboard") -> str:
    """Generate a scene image for one shot. Returns the saved path."""
    shot_id = shot.get("shot_id", 0)
    prompt  = shot.get("video_prompt", shot.get("description", ""))
    output_path = str(Path(output_dir) / f"shot_{shot_id:02d}.png")

    image = model.edit(ref_image, prompt)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def gen_storyboard_images(groups: list, ref_image: Image.Image, model,
                          output_dir: str = "output/storyboard") -> list:
    """
    Generate scene images for all shots, preserving the group structure.

    Args:
        groups: List of group dicts, each with "shots" list.

    Returns:
        List[List[str]]: For each group, the list of image paths (one per shot).
    """
    return [
        [gen_shot_image(shot, ref_image, model, output_dir)
         for shot in group.get("shots", [])]
        for group in groups
    ]
