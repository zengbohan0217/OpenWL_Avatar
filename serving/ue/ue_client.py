"""Facade for UE automation operations."""

from __future__ import annotations

from typing import Any, Optional

from .constants import (
    DEFAULT_IMPORT_ROOT,
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PLAYABLE_CLASS_PATH,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
)
from .asset_importer import AssetImporter
from .asset_registry import AssetRegistry
from .camera_controller import CameraController
from .effect_controller import EffectController
from .python_rpc_client import UEPythonRPCClient
from .remote_control_client import RemoteControlClient
from .scene_controller import SceneController
from .sequence_controller import SequenceController


class UEClient:
    def __init__(self) -> None:
        self.python = UEPythonRPCClient()
        self.remote_control = RemoteControlClient()
        self.assets = AssetImporter()
        self.registry = AssetRegistry()
        self.scene = SceneController()
        self.sequence = SequenceController()
        self.effects = EffectController()
        self.camera = CameraController()

    def check_connection(self) -> bool:
        return self.remote_control.check_connection()

    def execute_python(self, code: str, timeout: int = 120) -> dict[str, Any]:
        return self.python.execute(code, timeout=timeout)

    def import_asset(self, src_path: str, dst_path: str = "", asset_type: str = "prop", **options: Any) -> dict:
        return self.assets.import_asset(src_path, dst_path=dst_path, asset_type=asset_type, **options)

    def list_assets(self, root_path: str = DEFAULT_IMPORT_ROOT, asset_type: Optional[str] = None) -> list[dict]:
        return self.registry.list_assets(root_path=root_path, asset_type=asset_type)

    def get_asset_registry(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return self.registry.list_assets(root_path=root_path)

    def present_avatar(self, avatar_path: str, dest_path: str = "", as_skeletal: bool = True, existing: bool = False) -> bool:
        if existing:
            return self.scene.present_existing_avatar(avatar_path)
        return self.scene.present_uploaded_avatar(avatar_path, dest_path=dest_path, as_skeletal=as_skeletal)

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
        return self.scene.present_playable_avatar(
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

    def spawn_actor(self, asset_path: str, transform: Optional[dict] = None) -> dict:
        return self.scene.spawn_prop(asset_path, transform=transform)

    def destroy_actor(self, actor_name: str) -> dict:
        raise NotImplementedError("Destroying arbitrary actors belongs to the next scene-control milestone")

    def play_animation(
        self,
        motion_asset_path: str,
        avatar_asset_path: str = "",
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
    ) -> dict:
        return self.sequence.play_animation(
            motion_asset_path,
            avatar_asset_path=avatar_asset_path,
            actor_label=actor_label,
        )

    def stop_animation(self, actor_name: str) -> dict:
        raise NotImplementedError("Stopping arbitrary animations belongs to the next sequence-control milestone")

    def spawn_effect(self, effect_asset_path: str, attach_to: Optional[dict] = None) -> dict:
        return self.effects.spawn_effect(effect_asset_path, attach_to=attach_to)

    def destroy_effect(self, effect_name: str) -> dict:
        return self.effects.destroy_effect(effect_name)

    def set_camera(self, camera_config: dict) -> dict:
        return self.camera.set_camera(camera_config)

    def create_sequence(self, sequence_config: dict) -> dict:
        return self.sequence.create_sequence(sequence_config)

    def get_actor_transform(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL) -> dict:
        return self.scene.get_actor_transform(actor_label)

    def move_actor(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> dict:
        return self.scene.move_actor(actor_label, dx=dx, dy=dy, dz=dz)

    def move_actor_direction(
        self,
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
        direction: str = "forward",
        step: float = DEFAULT_MOVEMENT_STEP,
        forward_offset_yaw: float = 0.0,
        face_direction: bool = False,
    ) -> dict:
        return self.scene.move_actor_direction(
            actor_label,
            direction=direction,
            step=step,
            forward_offset_yaw=forward_offset_yaw,
            face_direction=face_direction,
        )

    def rotate_actor(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, yaw_delta: float = DEFAULT_ROTATION_STEP) -> dict:
        return self.scene.rotate_actor(actor_label, yaw_delta=yaw_delta)

    def set_actor_animation(
        self,
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
        motion_asset_path: str = "",
        avatar_asset_path: str = "",
        looping: bool = True,
    ) -> dict:
        return self.scene.set_actor_animation(
            actor_label=actor_label,
            motion_asset_path=motion_asset_path,
            avatar_asset_path=avatar_asset_path,
            looping=looping,
        )

    def clear_scene(self) -> dict:
        return self.scene.clear_presentation()
