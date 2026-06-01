"""
Test: Game CG generation pipeline (group-based).

Pipeline:
    1. Load grouped storyboard from JSON
    2. Generate per-shot scene images (List[List[str]] matching group structure)
    3. Per group: one KeyframeInterpolationPipeline call (all shot images as keyframes)
       → per-group mp4
    4. Concatenate all per-group mp4s → final .mp4
"""

import sys
sys.path.insert(0, ".")

from PIL import Image
from operators.gen_game_cg.operator import GameCGOperator

CFG = {
    "gen_image_model": "Qwen/Qwen-Image-Edit-2511",
    "ltx_root":        "Lightricks/LTX-2.3",
    "gemma_root":      "Lightricks/gemma-3-12b-it-qat-q4_0-unquantized",
    "device":          "cuda",
    "offload":         "none",
    # "reasoning_model": "Qwen/Qwen3.5-VL-7B-Instruct",
}

if __name__ == "__main__":
    ref_image = Image.open("assets/luffy.jpg")
    storyboard_input = "assets/storyboard.json"

    op = GameCGOperator(CFG)

    # Step-by-step
    groups       = op.get_storyboard(storyboard_input)
    group_images = op.gen_storyboard_images(groups, ref_image)

    print(f"Storyboard: {len(groups)} groups")
    for g, imgs in zip(groups, group_images):
        shots = g.get("shots", [])
        print(f"  Group {g.get('group_id')}: {len(shots)} shots")
        for s, p in zip(shots, imgs):
            print(f"    Shot {s['shot_id']}: {s['duration_sec']}s  {p}")

    # Per-group LTX call + concat → final video
    final = op.gen_full_video(groups, group_images, output_path="output/luffy_cg.mp4")
    print(f"\n✅ Final CG: {final}")

    # Or end-to-end:
    # final = op.run(storyboard_input, ref_image, output_path="output/luffy_cg.mp4")
