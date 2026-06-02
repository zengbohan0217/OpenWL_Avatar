"""
GameCGOperator — orchestrates the game CG generation pipeline.

VRAM strategy:
    QwenEdit (image edit) and LTX-2.3 (video) BOTH need tens of GB each.
    Loading them simultaneously OOMs on most GPUs. Pipeline therefore:
      1. Lazy-load QwenEdit → generate keyframe images → UNLOAD (free VRAM)
      2. Lazy-load LTX → one generation call → output mp4

Pipeline:
    1. get_storyboard         : {video_prompt, shots} from JSON / reasoning model
    2. gen_storyboard_images  : QwenEdit per shot → keyframe image paths
    3. gen_cg_video           : ONE LTX KeyframeInterpolationPipeline call

Config keys:
    ltx_root, gemma_root, gen_image_model, device, offload, quantization,
    [reasoning_model]
"""

from models.gen_image.qwen_edit import QwenEditModel
from models.gen_video.ltx import LTXModel
from operators.gen_game_cg.funcs.gen_storyboard import get_storyboard
from operators.gen_game_cg.funcs.gen_storyboard_image import gen_storyboard_images
from operators.gen_game_cg.funcs.gen_cg_video import gen_cg_video


class GameCGOperator:
    """Orchestrates the full game CG generation pipeline (Qwen → unload → LTX)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.device = cfg.get("device", "cuda")
        # Models are lazy-loaded so both never sit in VRAM at the same time.
        self._gen_image_model: QwenEditModel | None = None
        self._video_model: LTXModel | None = None
        self._reasoning_model = None

    # -------------------- lazy model accessors --------------------

    @property
    def gen_image_model(self) -> QwenEditModel:
        if self._gen_image_model is None:
            self._gen_image_model = QwenEditModel(
                self.cfg["gen_image_model"], device=self.device,
            )
        return self._gen_image_model

    @property
    def video_model(self) -> LTXModel:
        if self._video_model is None:
            self._video_model = LTXModel(
                ltx_root     = self.cfg["ltx_root"],
                gemma_root   = self.cfg["gemma_root"],
                device       = self.device,
                offload      = self.cfg.get("offload", "none"),
                quantization = self.cfg.get("quantization"),
            )
        return self._video_model

    @property
    def reasoning_model(self):
        if self._reasoning_model is None and "reasoning_model" in self.cfg:
            from models.reasoning.base import ReasoningModel
            self._reasoning_model = ReasoningModel(
                self.cfg["reasoning_model"], device=self.device,
            )
        return self._reasoning_model

    def _unload_image_model(self):
        if self._gen_image_model is not None:
            self._gen_image_model.unload()
            self._gen_image_model = None

    # -------------------- pipeline steps --------------------

    def get_storyboard(self, script_or_path: str) -> dict:
        return get_storyboard(script_or_path, model=self.reasoning_model)

    def gen_storyboard_images(self, storyboard: dict, ref_image,
                              output_dir: str = "output/storyboard") -> list:
        paths = gen_storyboard_images(
            storyboard.get("shots", []), ref_image,
            self.gen_image_model, output_dir,
        )
        # Free QwenEdit VRAM right after images are saved, BEFORE LTX loads.
        self._unload_image_model()
        return paths

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
