"""
GameCGOperator — orchestrates the game CG generation pipeline.

Pipeline:
    1. get_storyboard         : load grouped storyboard from JSON (or generate)
    2. gen_storyboard_images  : per-group, per-shot scene images (QwenEditModel)
    3. gen_full_video         : per-group LTX KeyframeInterpolationPipeline call,
                                then concatenate all group mp4s → final .mp4

Storyboard format:
    [
        {"group_id": 0, "shots": [{shot_id, video_prompt, duration_sec, ...}, ...]},
        ...
    ]

Config keys:
    ltx_root, gemma_root, gen_image_model, device, offload, [reasoning_model]
"""

from models.gen_image.qwen_edit import QwenEditModel
from models.gen_video.ltx import LTXModel
from operators.gen_game_cg.funcs.gen_storyboard import get_storyboard
from operators.gen_game_cg.funcs.gen_storyboard_image import gen_storyboard_images


class GameCGOperator:
    """Orchestrates the full game CG generation pipeline."""

    def __init__(self, cfg: dict):
        device = cfg.get("device", "cuda")
        self.gen_image_model = QwenEditModel(cfg["gen_image_model"], device=device)
        self.video_model = LTXModel(
            ltx_root   = cfg["ltx_root"],
            gemma_root = cfg["gemma_root"],
            device     = device,
            offload    = cfg.get("offload", "none"),
        )
        self.reasoning_model = None
        if "reasoning_model" in cfg:
            from models.reasoning.base import ReasoningModel
            self.reasoning_model = ReasoningModel(cfg["reasoning_model"], device=device)

    def get_storyboard(self, script_or_path: str) -> list:
        """Step 1: Load grouped storyboard."""
        return get_storyboard(script_or_path, model=self.reasoning_model)

    def gen_storyboard_images(self, groups: list, ref_image,
                              output_dir: str = "output/storyboard") -> list:
        """Step 2: Generate scene images. Returns List[List[str]] matching group structure."""
        return gen_storyboard_images(groups, ref_image, self.gen_image_model, output_dir)

    def gen_full_video(self, groups: list, group_images: list,
                       output_path: str = "output/cg_final.mp4",
                       **kwargs) -> str:
        """Step 3: Per-group LTX interpolation + concat → final video."""
        return self.video_model.generate_full_video(
            groups=groups,
            group_images=group_images,
            output_path=output_path,
            **kwargs,
        )

    def run(self, script_or_path: str, ref_image,
            output_path: str = "output/cg_final.mp4",
            **kwargs) -> str:
        """Run full pipeline end-to-end."""
        groups       = self.get_storyboard(script_or_path)
        group_images = self.gen_storyboard_images(groups, ref_image)
        return self.gen_full_video(groups, group_images, output_path=output_path, **kwargs)
