"""
UEAvatarOperator — top-level operator for the UE avatar generation pipeline.

Loads all required models once and exposes high-level pipeline methods.
Internal logic is delegated to funcs/*.py (one file per capability).

UE5 import (RPC) is handled by serving/ue_client.py, not this operator.

Typical usage:
    op = UEAvatarOperator(cfg)
    tpose   = op.gen_tpose(ref_image, description)
    mesh    = op.gen_3d_avatar(tpose)
    motion  = op.gen_motion(mesh, "walk forward")
    # then call serving/ue_client.py to push to UE5
"""

from models.gen_image.qwen_edit import QwenEditModel
from models.gen_3d.trellis import TrellisModel
from models.tools.depth_anything import DepthAnythingModel
from operators.gen_ue_avatar.funcs.gen_tpose import gen_tpose
from operators.gen_ue_avatar.funcs.gen_3d_avatar import gen_3d_avatar
from operators.gen_ue_avatar.funcs.gen_motion import detect_skeleton, gen_motion


class UEAvatarOperator:
    """Orchestrates the UE avatar AI generation pipeline (T-pose → 3D → motion)."""

    def __init__(self, cfg: dict):
        """
        Args:
            cfg: Config dict with model paths, e.g.
                 {
                   "gen_image_model": "/path/to/qwen-edit",
                   "gen_3d_model":    "/path/to/trellis",
                   "device":          "cuda",
                 }
        """
        self.cfg = cfg
        device = cfg.get("device", "cuda")
        self.gen_image_model = QwenEditModel(cfg["gen_image_model"], device=device)
        self.gen_3d_model = TrellisModel(cfg["gen_3d_model"], device=device)
        # Optional: depth model for T-pose foreground extraction.
        depth_path = cfg.get("depth_model")
        self.depth_model = (
            DepthAnythingModel(depth_path, device=device) if depth_path else None
        )

    # ------------------------------------------------------------------
    # Pipeline steps (thin wrappers that call funcs/)
    # ------------------------------------------------------------------

    def gen_tpose(self, ref_image, description: str = "", **kwargs):
        """Step 1: Generate T-pose RGBA image.

        Extra kwargs (seed, steps, target_size, return_intermediate, ...) are
        forwarded to `funcs.gen_tpose.gen_tpose`.
        """
        return gen_tpose(
            ref_image,
            description,
            gen_model=self.gen_image_model,
            depth_model=self.depth_model,
            **kwargs,
        )

    def gen_3d_avatar(self, tpose_image):
        """Step 2: Lift T-pose image to 3D avatar mesh."""
        return gen_3d_avatar(tpose_image, self.gen_3d_model)

    def gen_motion(self, mesh_path: str, motion_desc: str = ""):
        """Step 3: Detect skeleton and generate motion."""
        rigged = detect_skeleton(mesh_path, model=None)    # TODO: set skeleton model
        return gen_motion(rigged, motion_desc, model=None) # TODO: set motion model

    # ------------------------------------------------------------------
    # Convenience: run full pipeline end-to-end (returns assets for serving)
    # ------------------------------------------------------------------

    def run(self, ref_image, description: str = "", motion_desc: str = "") -> dict:
        """
        Run the full AI generation pipeline from a reference image.

        Returns:
            dict with keys: tpose_image, mesh_path, motion_path
            (caller is responsible for pushing results to UE5 via serving/ue_client.py)
        """
        tpose  = self.gen_tpose(ref_image, description)
        mesh   = self.gen_3d_avatar(tpose)
        motion = self.gen_motion(mesh, motion_desc) if motion_desc else None
        return {"tpose_image": tpose, "mesh_path": mesh, "motion_path": motion}
