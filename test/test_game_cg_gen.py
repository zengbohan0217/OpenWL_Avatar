"""
Test: Game CG generation pipeline (one continuous take, single LTX call).
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

    storyboard  = op.get_storyboard(storyboard_input)
    shot_images = op.gen_storyboard_images(storyboard, ref_image)

    shots = storyboard.get("shots", [])
    print(f"Storyboard: {len(shots)} shots")
    print(f"  Global video_prompt: {storyboard.get('video_prompt', '')[:80]}...")
    for s, p in zip(shots, shot_images):
        t = s.get("time_sec", s.get("frame_idx", "?"))
        print(f"  Shot {s['shot_id']}: t={t}  {p}")

    final = op.gen_cg_video(storyboard, shot_images, output_path="output/luffy_cg.mp4")
    print(f"\n✅ Final CG: {final}")

    # Or end-to-end:
    # final = op.run(storyboard_input, ref_image, output_path="output/luffy_cg.mp4")
