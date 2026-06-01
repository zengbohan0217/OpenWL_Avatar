"""
compose_cg.py — Compose all shot frames into a final video using imageio.

No ffmpeg dependency. Uses imageio + pillow to write mp4 directly.

Input:
    all_frames  : List[List[PIL.Image]]  — per-shot frame lists
    output_path : str                    — destination .mp4 path
    fps         : float                  — frame rate (default 12)

Output:
    output_path : str
"""

from pathlib import Path
from typing import List

from PIL import Image


def compose_cg(all_frames: List[List[Image.Image]], output_path: str,
               fps: float = 12.0) -> str:
    """
    Concatenate all shot frames and write to a single video file.

    Uses imageio (imageio-ffmpeg as backend) — no raw ffmpeg shell calls.

    Args:
        all_frames:  List of per-shot frame lists (List[List[PIL.Image]]).
        output_path: Destination path for the final video (e.g. "output/cg.mp4").
        fps:         Frame rate (default 12).

    Returns:
        output_path
    """
    try:
        import imageio
    except ImportError:
        raise ImportError(
            "imageio is required: pip install imageio imageio-ffmpeg"
        )

    import numpy as np

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Flatten all shots into a single frame sequence
    flat_frames = []
    for shot_frames in all_frames:
        flat_frames.extend(shot_frames)

    if not flat_frames:
        raise ValueError("No frames to compose.")

    # Ensure consistent size (use first frame as reference)
    ref_w, ref_h = flat_frames[0].size
    writer = imageio.get_writer(output_path, fps=fps, codec="libx264",
                                quality=8, pixelformat="yuv420p")
    try:
        for frame in flat_frames:
            if frame.size != (ref_w, ref_h):
                frame = frame.resize((ref_w, ref_h), Image.LANCZOS)
            writer.append_data(np.asarray(frame.convert("RGB")))
    finally:
        writer.close()

    return output_path
