"""
Game CG generation entrypoint.

Default mode runs real Qwen-Image-Edit and real LTX-2.3 inference.
Use --validate-only or --dry-run only for storyboard checks.
"""

import argparse
import os
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, ".")

from operators.gen_game_cg.operator import GameCGOperator


DEFAULT_MODEL_DIR = Path(os.environ.get("OPENWL_MODEL_DIR", ".models"))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--storyboard", default="assets/storyboard.json")
    parser.add_argument("--ref", default="assets/luffy.jpg")
    parser.add_argument("--output-dir", default="output/game_cg")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--fps", type=float, default=24.0)
    parser.add_argument("--height", type=int, default=512)
    parser.add_argument("--width", type=int, default=768)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--offload", default="none")
    parser.add_argument("--quantization", default=None)
    parser.add_argument("--gen-image-model", default=str(DEFAULT_MODEL_DIR / "Qwen-Image-Edit-2511"))
    parser.add_argument("--ltx-root", default=str(DEFAULT_MODEL_DIR / "LTX-2.3"))
    parser.add_argument("--gemma-root", default=str(DEFAULT_MODEL_DIR / "gemma-3-12b-it-qat-q4_0-unquantized"))
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    cfg = {
        "gen_image_model": args.gen_image_model,
        "ltx_root": args.ltx_root,
        "gemma_root": args.gemma_root,
        "device": args.device,
        "offload": args.offload,
        "quantization": args.quantization,
    }
    op = GameCGOperator(cfg)
    storyboard = op.get_storyboard(args.storyboard)
    op.validate_storyboard(storyboard, frame_rate=args.fps)

    out_dir = Path(args.output_dir)
    output_path = out_dir / "luffy_cg.mp4"
    run_command = " ".join(sys.argv)

    if args.validate_only:
        print(f"Validated storyboard: {args.storyboard}")
        return

    if args.dry_run:
        op.run(
            args.storyboard,
            ref_image=None,
            output_path=str(output_path),
            output_dir=str(out_dir),
            seed=args.seed,
            frame_rate=args.fps,
            height=args.height,
            width=args.width,
            dry_run=True,
            run_command=run_command,
        )
        print(f"Dry-run artifacts: {out_dir}")
        return

    ref_image = Image.open(args.ref).convert("RGB")
    final = op.run(
        args.storyboard,
        ref_image=ref_image,
        output_path=str(output_path),
        output_dir=str(out_dir),
        seed=args.seed,
        frame_rate=args.fps,
        height=args.height,
        width=args.width,
        run_command=run_command,
    )
    print(f"Final CG: {final}")


if __name__ == "__main__":
    main()
