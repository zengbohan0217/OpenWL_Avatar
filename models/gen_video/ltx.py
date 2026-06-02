"""
LTXModel — thin wrapper around LTX-2.3 KeyframeInterpolationPipeline.

Only one public method: `generate()`. It takes a prompt, a list of
ImageConditioningInput keyframes, and writes one mp4. All higher-level
logic (storyboard parsing, frame index layout, etc.) lives in
operators/gen_game_cg/funcs.
"""

from pathlib import Path
from typing import Optional, List

import torch

from ltx_core.loader import LTXV_LORA_COMFY_RENAMING_MAP, LoraPathStrengthAndSDOps
from ltx_core.model.video_vae import TilingConfig, get_video_chunks_number
from ltx_pipelines.keyframe_interpolation import KeyframeInterpolationPipeline
from ltx_pipelines.utils.args import ImageConditioningInput
from ltx_pipelines.utils.constants import DEFAULT_NEGATIVE_PROMPT, LTX_2_3_PARAMS
from ltx_pipelines.utils.media_io import encode_video
from ltx_pipelines.utils.types import OffloadMode

_CHECKPOINT   = "ltx-2.3-22b-dev.safetensors"
_DISTILL_LORA = "ltx-2.3-22b-distilled-lora-384-1.1.safetensors"
_UPSAMPLER    = "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"

DEFAULT_FPS = 24.0


def snap_frames(n: int) -> int:
    """Round to nearest 8k+1 as required by LTX."""
    k = max(0, round((n - 1) / 8))
    return 8 * k + 1


def _make_distilled_lora(path: str, strength: float = 0.8):
    return [LoraPathStrengthAndSDOps(path, strength, LTXV_LORA_COMFY_RENAMING_MAP)]


class LTXModel:
    """Minimal wrapper around LTX-2.3 KeyframeInterpolationPipeline."""

    def __init__(self, ltx_root: str, gemma_root: str,
                 device: str = "cuda", offload: str = "none"):
        self.ltx_root   = Path(ltx_root)
        self.gemma_root = gemma_root
        self.offload    = OffloadMode(offload)
        self._pipe      = None

    def _load(self):
        if self._pipe is None:
            root = self.ltx_root
            self._pipe = KeyframeInterpolationPipeline(
                checkpoint_path        = str(root / _CHECKPOINT),
                distilled_lora         = _make_distilled_lora(str(root / _DISTILL_LORA)),
                spatial_upsampler_path = str(root / _UPSAMPLER),
                gemma_root             = self.gemma_root,
                loras                  = [],
                offload_mode           = self.offload,
            )

    @torch.inference_mode()
    def generate(
        self,
        prompt: str,
        keyframes: List[ImageConditioningInput],
        num_frames: int,
        output_path: str,
        frame_rate: float = DEFAULT_FPS,
        height: int = 768,
        width: int = 1152,
        negative_prompt: Optional[str] = None,
        seed: int = 42,
    ) -> str:
        """One LTX call → one mp4. `num_frames` will be snapped to 8k+1."""
        self._load()
        params = LTX_2_3_PARAMS
        num_frames = snap_frames(num_frames)
        tiling_config = TilingConfig.default()

        video, audio = self._pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
            seed=seed, height=height, width=width,
            num_frames=num_frames, frame_rate=frame_rate,
            num_inference_steps=params.num_inference_steps,
            video_guider_params=params.video_guider_params,
            audio_guider_params=params.audio_guider_params,
            images=keyframes, tiling_config=tiling_config,
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        encode_video(
            video=video, fps=int(frame_rate), audio=audio,
            output_path=output_path,
            video_chunks_number=get_video_chunks_number(num_frames, tiling_config),
        )
        return output_path
