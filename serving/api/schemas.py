"""Request schemas for the local Viewer API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from serving.ue.constants import (
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PLAYABLE_CLASS_PATH,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
)


class PresentAvatarRequest(BaseModel):
    avatar_asset_path: str = Field(..., min_length=1)


class PresentPlayableAvatarRequest(BaseModel):
    avatar_asset_path: str = Field(..., min_length=1)
    idle_animation_path: str = ""
    move_animation_path: str = ""
    playable_blueprint_path: str = DEFAULT_PLAYABLE_CLASS_PATH
    actor_label: str = DEFAULT_PLAYABLE_ACTOR_LABEL
    mesh_forward_axis: Literal["auto", "+X", "+Y", "-X", "-Y"] = "auto"
    mesh_relative_yaw: Optional[float] = None
    align_to_ground: bool = True
    ground_z: float = 0.0
    destroy_existing: bool = True
    walk_speed: Optional[float] = None
    run_speed: Optional[float] = None


class TriggerSkillRequest(BaseModel):
    actor_label: str = DEFAULT_PLAYABLE_ACTOR_LABEL
    skill_name: str = Field(..., min_length=1)


class PlayMotionRequest(BaseModel):
    motion_asset_path: str = Field(..., min_length=1)
    avatar_asset_path: str = ""


class MoveActorRequest(BaseModel):
    actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL
    direction: Optional[Literal["forward", "backward", "left", "right", "up", "down"]] = None
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    step: float = DEFAULT_MOVEMENT_STEP
    forward_offset_yaw: float = 0.0
    face_direction: bool = False


class SetActorAnimationRequest(BaseModel):
    actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL
    motion_asset_path: str = Field(..., min_length=1)
    avatar_asset_path: str = ""
    looping: bool = True


class RotateActorRequest(BaseModel):
    actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL
    yaw_delta: float = DEFAULT_ROTATION_STEP
