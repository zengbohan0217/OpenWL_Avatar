"""
LTXModel — wrapper for LTX-2.3 video generation.

Primary API:
  - generate_full_video(): takes a list of "groups", where each group contains
    multiple shots that should be smoothly interpolated together (one pipeline
    call per group). Then concatenates all group mp4 files into the final video.

Per-group API:
  - generate_interpolation(): one pipeline call. Accepts a list of keyframes
    (path, frame_idx, strength) — supports 2 or more keyframes.

Legacy API:
  - generate_i2v(): single shot, start frame only.
"""

from pathlib import Path
from typing import Optional, List, Tuple

import torch

from ltx_core.loader import LTXV_LORA_COMFY_RENAMING_MAP, LoraPathStrengthAndSDOps
from ltx_core.model.video_vae import TilingConfig, get_video_chunks_number
from ltx_pipelines.ti2vid_two_stages import TI2VidTwoStagesPipeline
from ltx_pipelines.keyframe_interpolation import KeyframeInterpolationPipeline
from ltx_pipelines.utils.args import ImageConditioningInput
from ltx_pipelines.utils.constants import DEFAULT_NEGATIVE_PROMPT, LTX_2_3_PARAMS
from ltx_pipelines.utils.media_io import encode_video
from ltx_pipelines.utils.types import OffloadMode

_CHECKPOINT   = "ltx-2.3-22b-dev.safetensors"
_DISTILL_LORA = "ltx-2.3-22b-distilled-lora-384-1.1.safetensors"
_UPSAMPLER    = "ltx-2.3-spatial-upscaler-x2-1.1.safetensors"

DEFAULT_NUM_FRAMES = 121
DEFAULT_FPS = 24.0


def _snap_frames(n: int) -> int:
    """Round to nearest 8k+1 as required by LTX."""
    k = max(0, round((n - 1) / 8))
    return 8 * k + 1


def _make_distilled_lora(path: str, strength: float = 0.8):
    return [LoraPathStrengthAndSDOps(path, strength, LTXV_LORA_COMFY_RENAMING_MAP)]


# Type alias: (image_path, frame_idx, strength)
Keyframe = Tuple[str, int, float]


class LTXModel:
    """Wrapper around LTX-2.3 (KeyframeInterpolationPipeline + TI2VidTwoStagesPipeline)."""

    def __init__(self, ltx_root: str, gemma_root: str,
                 device: str = "cuda", offload: str = "none"):
        self.ltx_root   = Path(ltx_root)
        self.gemma_root = gemma_root
        self.offload    = OffloadMode(offload)
        self._i2v_pipe    = None
        self._interp_pipe = None

    def _common_kwargs(self) -> dict:
        root = self.ltx_root
        return dict(
            checkpoint_path        = str(root / _CHECKPOINT),
            distilled_lora         = _make_distilled_lora(str(root / _DISTILL_LORA)),
            spatial_upsampler_path = str(root / _UPSAMPLER),
            gemma_root             = self.gemma_root,
            loras                  = [],
            offload_mode           = self.offload,
        )

    def _load_i2v(self):
        if self._i2v_pipe is None:
            self._i2v_pipe = TI2VidTwoStagesPipeline(**self._common_kwargs())

    def _load_interp(self):
        if self._interp_pipe is None:
            self._interp_pipe = KeyframeInterpolationPipeline(**self._common_kwargs())

    # ------------------------------------------------------------------ #
    #  Primary API: generate full video from grouped storyboard           #
    # ------------------------------------------------------------------ #

    @torch.inference_mode()
    def generate_full_video(
        self,
        groups: list,
        group_images: List[List[str]],
        output_path: str,
        frame_rate: float = DEFAULT_FPS,
        height: int = 768,
        width: int = 1152,
        negative_prompt: Optional[str] = None,
        seed: int = 42,
    ) -> str:
        """
        Generate the final CG video from grouped storyboard.

        Each group contains 1+ shots that should be smoothly interpolated
        together (one pipeline call per group). Final video is the concatenation
        of all per-group mp4 outputs.

        Args:
            groups:       List of group dicts. Each group has {"shots": [...]}.
            group_images: For each group, the list of keyframe image paths
                          (one per shot in that group).
            output_path:  Destination .mp4 path.
            frame_rate:   FPS.
            height/width: Output resolution.
            negative_prompt: Negative prompt.
            seed:         RNG seed.

        Returns:
            output_path
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = out.parent / f"{out.stem}_groups"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        # ---- Generate one mp4 per group ----
        group_mp4s = []
        for gi, (group, images) in enumerate(zip(groups, group_images)):
            shots = group.get("shots", [])
            if len(shots) != len(images):
                raise ValueError(
                    f"Group {gi}: {len(shots)} shots but {len(images)} images."
                )

            # Build keyframes from shots: each shot's image is pinned at its
            # cumulative frame index within the group.
            per_shot_frames = [
                _snap_frames(max(9, round(float(s.get("duration_sec", 2.0)) * frame_rate)))
                for s in shots
            ]

            if len(shots) == 1:
                # Single-shot group → I2V-like generation via interp pipe
                num_frames = per_shot_frames[0]
                keyframes: List[Keyframe] = [(images[0], 0, 1.0)]
            else:
                # Multi-shot group: place each shot image at its boundary frame.
                # Frame layout: shot_0 occupies [0, n0-1], shot_1 occupies [n0-1, n0+n1-2], ...
                cum = 0
                kf_positions = [0]
                for n in per_shot_frames[:-1]:
                    cum += n - 1  # boundary frame shared with next shot
                    kf_positions.append(cum)
                num_frames = _snap_frames(cum + per_shot_frames[-1])
                # Make sure the last keyframe sits exactly at num_frames-1
                kf_positions[-1] = num_frames - 1
                keyframes = [(img, idx, 0.9) for img, idx in zip(images, kf_positions)]

            # Use the first shot's prompt as the group prompt
            group_prompt = shots[0].get("video_prompt", shots[0].get("description", ""))

            group_out = str(tmp_dir / f"group_{gi:02d}.mp4")
            self.generate_interpolation(
                prompt=group_prompt,
                keyframes=keyframes,
                output_path=group_out,
                num_frames=num_frames,
                frame_rate=frame_rate,
                height=height, width=width,
                negative_prompt=negative_prompt,
                seed=seed,
            )
            group_mp4s.append(group_out)

        # ---- Concatenate all group mp4s using imageio ----
        _concat_videos_imageio(group_mp4s, str(out), fps=frame_rate)
        return str(out)

    # ------------------------------------------------------------------ #
    #  Per-group / per-shot generation APIs                               #
    # ------------------------------------------------------------------ #

    @torch.inference_mode()
    def generate_interpolation(
        self,
        prompt: str,
        keyframes: List[Keyframe],
        output_path: str,
        num_frames: int = DEFAULT_NUM_FRAMES,
        frame_rate: float = DEFAULT_FPS,
        height: int = 768, width: int = 1152,
        negative_prompt: Optional[str] = None,
        seed: int = 42,
    ) -> str:
        """
        Keyframe interpolation with N keyframes (N >= 1).

        Args:
            prompt:     Text prompt.
            keyframes:  List of (image_path, frame_idx, strength). Supports any
                        number of keyframes; the pipeline will interpolate between them.
            output_path: Destination .mp4 path.
            num_frames:  Total frames to generate (will be snapped to 8k+1).
            frame_rate, height, width, negative_prompt, seed: standard params.

        Returns:
            output_path
        """
        self._load_interp()
        params = LTX_2_3_PARAMS
        num_frames = _snap_frames(num_frames)
        tiling_config = TilingConfig.default()

        images = [
            ImageConditioningInput(path=p, frame_idx=idx, strength=strength)
            for (p, idx, strength) in keyframes
        ]

        video, audio = self._interp_pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
            seed=seed, height=height, width=width,
            num_frames=num_frames, frame_rate=frame_rate,
            num_inference_steps=params.num_inference_steps,
            video_guider_params=params.video_guider_params,
            audio_guider_params=params.audio_guider_params,
            images=images, tiling_config=tiling_config,
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        encode_video(
            video=video, fps=int(frame_rate), audio=audio,
            output_path=output_path,
            video_chunks_number=get_video_chunks_number(num_frames, tiling_config),
        )
        return output_path

    @torch.inference_mode()
    def generate_i2v(self, prompt: str, start_image: str, output_path: str,
                     num_frames: int = DEFAULT_NUM_FRAMES,
                     frame_rate: float = DEFAULT_FPS,
                     height: int = 768, width: int = 1152,
                     negative_prompt: Optional[str] = None,
                     seed: int = 42) -> str:
        """Image-to-video: start frame only. Writes mp4 to output_path."""
        self._load_i2v()
        params = LTX_2_3_PARAMS
        num_frames = _snap_frames(num_frames)
        tiling_config = TilingConfig.default()
        images = [ImageConditioningInput(path=start_image, frame_idx=0, strength=1.0)]

        video, audio = self._i2v_pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or DEFAULT_NEGATIVE_PROMPT,
            seed=seed, height=height, width=width,
            num_frames=num_frames, frame_rate=frame_rate,
            num_inference_steps=params.num_inference_steps,
            video_guider_params=params.video_guider_params,
            audio_guider_params=params.audio_guider_params,
            images=images, tiling_config=tiling_config,
        )
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        encode_video(
            video=video, fps=int(frame_rate), audio=audio,
            output_path=output_path,
            video_chunks_number=get_video_chunks_number(num_frames, tiling_config),
        )
        return output_path


# ---------------------------------------------------------------------- #
#  Video concat helper (imageio, no ffmpeg shell call)                    #
# ---------------------------------------------------------------------- #

def _concat_videos_imageio(mp4_paths: List[str], output_path: str,
                           fps: float = DEFAULT_FPS) -> str:
    """Read multiple mp4 files frame-by-frame and write one concatenated mp4."""
    import imageio
    import numpy as np

    if not mp4_paths:
        raise ValueError("No mp4 paths to concatenate.")

    writer = imageio.get_writer(
        output_path, fps=fps, codec="libx264",
        quality=8, pixelformat="yuv420p",
    )
    try:
        for mp4 in mp4_paths:
            reader = imageio.get_reader(mp4)
            for frame in reader:
                writer.append_data(np.asarray(frame))
            reader.close()
    finally:
        writer.close()
    return output_path
