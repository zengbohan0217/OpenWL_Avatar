"""
gen_cg_video.py — Generate frames for one storyboard shot using LTX-2.3.

Shot transition modes (controlled by shot["transition"]):
  - "cut"        (default) : hard cut, start frame only → I2V generation
  - "transition"           : smooth transition, start + end frame → keyframe interpolation

Returns:
    List[PIL.Image] — raw frames for this shot.
"""

from pathlib import Path
from typing import List, Optional
from PIL import Image


# Short clips: ~2s @ 12fps = 25 frames (snapped to 8k+1 = 25)
_DEFAULT_NUM_FRAMES = 25


def gen_cg_video(shot: dict, start_image: str, model,
                 output_dir: str = "output/clips",
                 end_image: Optional[str] = None) -> List[Image.Image]:
    """
    Generate frames for one storyboard shot.

    Args:
        shot:        Shot dict with keys: shot_id, video_prompt, duration_sec, transition.
        start_image: Path to the start-frame image (always required).
        model:       Loaded LTXModel instance.
        output_dir:  (unused, kept for API compatibility)
        end_image:   Path to the end-frame image (required when transition == "transition").

    Returns:
        List of PIL.Image frames for this shot.
    """
    prompt     = shot.get("video_prompt", shot.get("description", ""))
    dur_sec    = float(shot.get("duration_sec", 2.0))
    transition = shot.get("transition", "cut")

    num_frames = max(9, round(dur_sec * 12))  # approx, will be snapped inside model

    if transition == "transition" and end_image is not None:
        return model.generate_interpolation(
            prompt=prompt,
            start_image=start_image,
            end_image=end_image,
            num_frames=num_frames,
        )
    else:
        return model.generate_i2v(
            prompt=prompt,
            start_image=start_image,
            num_frames=num_frames,
        )
