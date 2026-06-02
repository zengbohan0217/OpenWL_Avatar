"""
GameCGOperator — orchestrates the game CG generation pipeline.

Pipeline (one continuous take, no concat):
    1. get_storyboard         : {video_prompt, shots} from JSON or reasoning model
    2. gen_storyboard_images  : QwenEdit per shot → keyframe image paths
    3. gen_cg_video           : ONE LTX KeyframeInterpolationPipeline call,
                                all shot images pinned as keyframes, global
                                video_prompt drives the camera narrative.

Config keys:
    ltx_root, gemma_root, gen_image_model, device, offload, [reasoning_model]
"""

from models.gen_image.qwen_edit import QwenEditModel
from models.gen_video.ltx import LTXModel
from operators.gen_game_cg.funcs.gen_storyboard import get_storyboard
from operators.gen_game_cg.funcs.gen_storyboard_image import gen_storyboard_images
from operators.gen_game_cg.funcs.gen_cg_video import gen_cg_video


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

    def get_storyboard(self, script_or_path: str) -> dict:
        return get_storyboard(script_or_path, model=self.reasoning_model)

    def gen_storyboard_images(self, storyboard: dict, ref_image,
                              output_dir: str = "output/storyboard") -> list:
        return gen_storyboard_images(
            storyboard.get("shots", []), ref_image,
            self.gen_image_model, output_dir,
        )

    def gen_cg_video(self, storyboard: dict, shot_images: list,
                     output_path: str = "output/cg_final.mp4",
                     **kwargs) -> str:
        return gen_cg_video(storyboard, shot_images, self.video_model,
                            output_path=output_path, **kwargs)

    def run(self, script_or_path: str, ref_image,
            output_path: str = "output/cg_final.mp4",
            **kwargs) -> str:
        storyboard  = self.get_storyboard(script_or_path)
        shot_images = self.gen_storyboard_images(storyboard, ref_image)
        return self.gen_cg_video(storyboard, shot_images,
                                 output_path=output_path, **kwargs)
