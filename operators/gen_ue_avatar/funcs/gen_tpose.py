"""
gen_tpose.py — Generate a game-CG T-pose RGBA image from a reference character image.

Pipeline (mirrors cache_code/gen_avatar_tpose.py):
  1. Use a GenImageModel (Qwen-Image-Edit) to turn the reference image into
     a game-CG T-pose render on a pure white background.
  2. Use a DepthAnythingModel to estimate depth and extract the foreground
     character mask (combined with a near-white background suppression).
  3. Post-process: validate alpha, tight-crop the foreground bbox, pad to a
     square canvas and resize to a fixed target size (1024 by default) so the
     result is directly consumable by downstream 3D pipelines (e.g. TRELLIS).

Input:
    ref_image    : PIL.Image            — reference character image (any background)
    description  : str                  — optional text description of the character
    gen_model    : GenImageModel-like   — must expose `.edit(image, prompt, seed, steps)`
    depth_model  : DepthAnythingModel   — must expose `.predict(image) -> np.ndarray`

Output:
    PIL.Image (RGBA, target_size x target_size) — character in T-pose, transparent bg
"""

from typing import Optional

import numpy as np
from PIL import Image
from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

TPOSE_PROMPT = (
    "Transform this character into a high-quality game CG T-pose reference sheet. "
    "The character should stand upright with arms extended horizontally at shoulder height (T-pose), "
    "facing directly forward, on a pure solid white background (RGB 255,255,255). "
    "Keep the character's original appearance, costume, colors, and style. "
    "Render in a clean game-art / anime-CG style with clear outlines. "
    "No background scenery, no shadows on the floor. "
    "The background must be a flat, uniform, solid white color only — no gradients, no shadows cast on background."
)


# ---------------------------------------------------------------------------
# Step 1: Generate T-pose CG image
# ---------------------------------------------------------------------------

def _generate_tpose_rgb(
    gen_model,
    ref_image: Image.Image,
    description: str,
    seed: int,
    steps: int,
) -> Image.Image:
    """Call the image-edit model to produce the T-pose CG image (white-bg RGB)."""
    prompt = TPOSE_PROMPT
    if description:
        prompt = f"Character description: {description}. " + prompt
    return gen_model.edit(ref_image, prompt=prompt, seed=seed, steps=steps)


# ---------------------------------------------------------------------------
# Step 2: Foreground extraction (DepthAnything + white-bg suppression)
# ---------------------------------------------------------------------------

def _extract_foreground(
    image: Image.Image,
    depth_model,
    white_thresh: int = 235,
    depth_quantile: float = 0.35,
) -> Image.Image:
    """Segment character foreground using depth cues + white-bg suppression."""
    img = np.array(image.convert("RGB"))

    depth = depth_model.predict(image)
    depth_norm = (depth - depth.min()) / (depth.max() - depth.min() + 1e-8)

    # Suppress near-white background pixels.
    white_mask = (
        (img[..., 0] >= white_thresh)
        & (img[..., 1] >= white_thresh)
        & (img[..., 2] >= white_thresh)
    )

    fg = binary_fill_holes(depth_norm >= depth_quantile) & ~white_mask
    fg = binary_dilation(binary_erosion(fg, iterations=2), iterations=3)

    rgba = np.array(image.convert("RGBA"))
    rgba[..., 3] = (fg * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


# ---------------------------------------------------------------------------
# Step 3: Post-process for downstream 3D
# ---------------------------------------------------------------------------

def _postprocess_for_trellis(
    rgba: Image.Image,
    size: int = 1024,
    white_thresh: int = 240,
    padding: float = 0.05,
) -> Image.Image:
    """Validate alpha, tight-crop, pad to square, resize."""
    arr = np.array(rgba).copy()

    fg_pixel_count = (arr[..., 3] > 0).sum()
    total_pixels = arr.shape[0] * arr.shape[1]
    if fg_pixel_count < total_pixels * 0.01:
        print("[warn] Depth-based alpha nearly empty; falling back to white-bg removal.")
        rgb = arr[..., :3]
        white = (
            (rgb[..., 0] >= white_thresh)
            & (rgb[..., 1] >= white_thresh)
            & (rgb[..., 2] >= white_thresh)
        )
        arr[white, 3] = 0
        arr[~white, 3] = 255

    alpha = arr[..., 3]
    rows = np.any(alpha > 0, axis=1)
    cols = np.any(alpha > 0, axis=0)
    if rows.any() and cols.any():
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]

        h_box = y_max - y_min
        w_box = x_max - x_min
        pad_y = int(h_box * padding)
        pad_x = int(w_box * padding)

        img_h, img_w = alpha.shape
        y_min = max(0, y_min - pad_y)
        y_max = min(img_h, y_max + pad_y)
        x_min = max(0, x_min - pad_x)
        x_max = min(img_w, x_max + pad_x)

        arr = arr[y_min:y_max, x_min:x_max]
        print(f"[crop] Foreground bbox: ({x_min},{y_min})-({x_max},{y_max}), "
              f"cropped size: {arr.shape[1]}x{arr.shape[0]}")
    else:
        print("[warn] No foreground pixels found after alpha fix; skipping crop.")

    rgba = Image.fromarray(arr, "RGBA")

    w, h = rgba.size
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (255, 255, 255, 0))
    square.paste(rgba, ((side - w) // 2, (side - h) // 2))
    return square.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def gen_tpose(
    ref_image: Image.Image,
    description: str,
    gen_model,
    depth_model=None,
    seed: int = 42,
    steps: int = 40,
    target_size: int = 1024,
    return_intermediate: bool = False,
):
    """
    Generate a T-pose RGBA image from a reference character image.

    Args:
        ref_image:           Reference PIL image of the character.
        description:         Short text description of the character (can be empty).
        gen_model:           Loaded GenImageModel (e.g. QwenEditModel).
        depth_model:         Loaded DepthAnythingModel. If None, foreground
                             extraction falls back to pure white-bg removal.
        seed:                Random seed for the image-edit model.
        steps:               Diffusion steps for the image-edit model.
        target_size:         Output canvas size (square).
        return_intermediate: If True, also return the white-bg RGB T-pose.

    Returns:
        RGBA PIL image (target_size x target_size, transparent background).
        If `return_intermediate=True`, returns a dict with keys
        {"tpose_rgb", "tpose_rgba"}.
    """
    # Step 1: image edit → white-bg T-pose
    tpose_rgb = _generate_tpose_rgb(gen_model, ref_image, description, seed, steps)

    # Step 2: foreground extraction
    if depth_model is not None:
        fg_rgba = _extract_foreground(tpose_rgb, depth_model)
    else:
        # Direct fallback: postprocess will do white-bg removal.
        fg_rgba = tpose_rgb.convert("RGBA")

    # Step 3: post-process for downstream 3D
    fg_rgba = _postprocess_for_trellis(fg_rgba, size=target_size)

    if return_intermediate:
        return {"tpose_rgb": tpose_rgb, "tpose_rgba": fg_rgba}
    return fg_rgba
