"""UI/API-friendly scene presentation operations."""

from __future__ import annotations

from typing import Optional

from serving.ue.config import DEFAULT_AVATAR_DEST, DEFAULT_MOTION_DEST
from serving.ue.constants import (
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PLAYABLE_CLASS_PATH,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
)
from serving.ue.ue_client import UEClient


class SceneService:
    def __init__(self, client: Optional[UEClient] = None) -> None:
        self.client = client or UEClient()

    def present_uploaded_avatar(
        self,
        avatar_path: str,
        dest_path: str = DEFAULT_AVATAR_DEST,
        as_skeletal: bool = True,
    ) -> bool:
        return self.client.present_avatar(
            avatar_path,
            dest_path=dest_path,
            as_skeletal=as_skeletal,
            existing=False,
        )

    def present_existing_avatar(self, avatar_asset_path: str) -> bool:
        return self.client.present_avatar(avatar_asset_path, existing=True)

    def present_playable_avatar(
        self,
        avatar_asset_path: str,
        idle_animation_path: str = "",
        move_animation_path: str = "",
        playable_blueprint_path: str = DEFAULT_PLAYABLE_CLASS_PATH,
        actor_label: str = DEFAULT_PLAYABLE_ACTOR_LABEL,
        mesh_forward_axis: str = "auto",
        mesh_relative_yaw=None,
        align_to_ground: bool = True,
        ground_z: float = 0.0,
        destroy_existing: bool = True,
        walk_speed=None,
        run_speed=None,
    ) -> dict:
        return self.client.present_playable_avatar(
            avatar_asset_path,
            idle_animation_path=idle_animation_path,
            move_animation_path=move_animation_path,
            playable_blueprint_path=playable_blueprint_path,
            actor_label=actor_label,
            mesh_forward_axis=mesh_forward_axis,
            mesh_relative_yaw=mesh_relative_yaw,
            align_to_ground=align_to_ground,
            ground_z=ground_z,
            destroy_existing=destroy_existing,
            walk_speed=walk_speed,
            run_speed=run_speed,
        )

    def play_motion(self, motion_asset_path: str, avatar_asset_path: str = "") -> dict:
        return self.client.play_animation(motion_asset_path, avatar_asset_path=avatar_asset_path)

    def resolve_avatar_skeleton(self, avatar_asset_path: str) -> str:
        skeleton_path = self.client.sequence.resolve_avatar_skeleton(avatar_asset_path)
        return (skeleton_path or "").split(".", 1)[0]

    def import_motion_and_play(
        self,
        motion_path: str,
        avatar_asset_path: str = "",
        dest_path: str = DEFAULT_MOTION_DEST,
        skeleton_asset_path: str = "",
    ) -> dict:
        return self.client.sequence.import_motion_and_play(
            motion_path,
            avatar_asset_path=avatar_asset_path,
            dest_path=dest_path,
            skeleton_asset_path=skeleton_asset_path,
        )

    def clear_presentation(self) -> dict:
        return self.client.clear_scene()

    def check_connection(self) -> bool:
        return self.client.check_connection()

    def get_actor_transform(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL) -> dict:
        return self.client.get_actor_transform(actor_label)

    def move_actor(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> dict:
        return self.client.move_actor(actor_label, dx=dx, dy=dy, dz=dz)

    def move_actor_direction(
        self,
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
        direction: str = "forward",
        step: float = DEFAULT_MOVEMENT_STEP,
        forward_offset_yaw: float = 0.0,
        face_direction: bool = False,
    ) -> dict:
        return self.client.move_actor_direction(
            actor_label,
            direction=direction,
            step=step,
            forward_offset_yaw=forward_offset_yaw,
            face_direction=face_direction,
        )

    def rotate_actor(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, yaw_delta: float = DEFAULT_ROTATION_STEP) -> dict:
        return self.client.rotate_actor(actor_label, yaw_delta=yaw_delta)

    def set_actor_animation(
        self,
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
        motion_asset_path: str = "",
        avatar_asset_path: str = "",
        looping: bool = True,
    ) -> dict:
        return self.client.set_actor_animation(
            actor_label=actor_label,
            motion_asset_path=motion_asset_path,
            avatar_asset_path=avatar_asset_path,
            looping=looping,
        )

    def spawn_prop(self, asset_path: str, transform: Optional[dict] = None) -> dict:
        return self.client.spawn_actor(asset_path, transform=transform)

    def trigger_effect(self, effect_asset_path: str, attach_to: Optional[dict] = None) -> dict:
        return self.client.spawn_effect(effect_asset_path, attach_to=attach_to)
