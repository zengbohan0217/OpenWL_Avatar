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

from operators.gen_game_cg.funcs.gen_storyboard import get_storyboard
from operators.gen_game_cg.funcs.gen_storyboard_image import gen_storyboard_images
from operators.gen_game_cg.funcs.storyboard_ir import (
    build_contact_sheet,
    build_run_manifest,
    compile_storyboard_prompts,
    normalize_storyboard,
    validate_storyboard_timing,
    write_resolved_storyboard,
    write_run_manifest,
)

import shutil
import time
from pathlib import Path
from typing import Any


class GameCGOperator:
    """Orchestrates the full game CG generation pipeline (Qwen → unload → LTX)."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.device = cfg.get("device", "cuda")
        # Models are lazy-loaded so both never sit in VRAM at the same time.
        self._gen_image_model: Any | None = None
        self._video_model: Any | None = None
        self._reasoning_model = None

    # -------------------- lazy model accessors --------------------

    @property
    def gen_image_model(self) -> Any:
        if self._gen_image_model is None:
            from models.gen_image.qwen_edit import QwenEditModel
            self._gen_image_model = QwenEditModel(
                self.cfg["gen_image_model"], device=self.device,
            )
        return self._gen_image_model

    @property
    def video_model(self) -> Any:
        if self._video_model is None:
            from models.gen_video.ltx import LTXModel
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

    def normalize_storyboard(self, storyboard: dict, frame_rate: float = 24.0) -> dict:
        return compile_storyboard_prompts(normalize_storyboard(storyboard, frame_rate=frame_rate))

    def validate_storyboard(self, storyboard: dict, frame_rate: float = 24.0) -> list[str]:
        return validate_storyboard_timing(storyboard, frame_rate=frame_rate)

    def gen_storyboard_images(self, storyboard: dict, ref_image,
                              output_dir: str = "output/storyboard",
                              seed: int = 42) -> list:
        paths = gen_storyboard_images(
            storyboard.get("shots", []), ref_image,
            self.gen_image_model, output_dir, seed=seed,
        )
        # Free QwenEdit VRAM right after images are saved, BEFORE LTX loads.
        self._unload_image_model()
        return paths

    def gen_cg_video(self, storyboard: dict, shot_images: list,
                     output_path: str = "output/cg_final.mp4",
                     **kwargs) -> str:
        from operators.gen_game_cg.funcs.gen_cg_video import gen_cg_video
        return gen_cg_video(storyboard, shot_images, self.video_model,
                            output_path=output_path, **kwargs)

    def run(self, script_or_path: str, ref_image,
            output_path: str = "output/cg_final.mp4",
            output_dir: str | None = None,
            seed: int = 42,
            frame_rate: float = 24.0,
            height: int = 512,
            width: int = 768,
            dry_run: bool = False,
            run_command: str | None = None,
            **kwargs) -> str:
        started_at = time.time()
        output_path_obj = Path(output_path)
        base_dir = Path(output_dir) if output_dir else output_path_obj.parent
        base_dir.mkdir(parents=True, exist_ok=True)

        storyboard = self.get_storyboard(script_or_path)
        validate_storyboard_timing(storyboard, frame_rate=frame_rate)

        resolved_path = write_resolved_storyboard(storyboard, base_dir / "storyboard_resolved.json")
        write_resolved_storyboard(storyboard, base_dir / "storyboard" / "storyboard_resolved.json")
        if dry_run:
            manifest = build_run_manifest(
                storyboard_input=script_or_path,
                storyboard=storyboard,
                output_files={
                    "storyboard_resolved": resolved_path,
                    "storyboard_resolved_in_storyboard_dir": str(base_dir / "storyboard" / "storyboard_resolved.json"),
                    "dry_run": True,
                },
                cfg=self.cfg,
                params={
                    "seed": seed,
                    "frame_rate": frame_rate,
                    "height": height,
                    "width": width,
                },
                started_at=started_at,
                repo_root=Path.cwd(),
                run_command=run_command,
            )
            write_run_manifest(manifest, base_dir / "run_manifest.json")
            return str(output_path_obj)

        shot_images = self.gen_storyboard_images(
            storyboard,
            ref_image,
            output_dir=str(base_dir / "storyboard"),
            seed=seed,
        )
        contact_sheet = build_contact_sheet(storyboard, shot_images, base_dir / "contact_sheet.png")
        storyboard_contact_sheet = base_dir / "storyboard" / "contact_sheet.png"
        storyboard_contact_sheet.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(contact_sheet, storyboard_contact_sheet)
        final_video = self.gen_cg_video(
            storyboard,
            shot_images,
            output_path=str(output_path_obj),
            seed=seed,
            frame_rate=frame_rate,
            height=height,
            width=width,
            clips_dir=str(base_dir / "clips"),
            **kwargs,
        )
        output_files = {
            "storyboard_resolved": resolved_path,
            "contact_sheet": contact_sheet,
            "storyboard_contact_sheet": str(storyboard_contact_sheet),
            "shot_images": shot_images,
            "final_video": final_video,
            "segments": storyboard.get("_segment_outputs", []),
        }
        manifest = build_run_manifest(
            storyboard_input=script_or_path,
            storyboard=storyboard,
            output_files=output_files,
            cfg=self.cfg,
            params={
                "seed": seed,
                "frame_rate": frame_rate,
                "height": height,
                "width": width,
            },
            started_at=started_at,
            repo_root=Path.cwd(),
            run_command=run_command,
        )
        write_run_manifest(manifest, base_dir / "run_manifest.json")
        return final_video
