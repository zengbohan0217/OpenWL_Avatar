"""Scene presentation operations."""

from __future__ import annotations

from typing import Optional

from .config import DEFAULT_AVATAR_DEST
from .constants import (
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PLAYABLE_CLASS_PATH,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
)
from .scripts.scene_control_scripts import (
    _build_get_actor_transform_script,
    _build_move_actor_direction_script,
    _build_move_actor_script,
    _build_rotate_actor_script,
    _build_set_actor_animation_script,
)
from .scripts.presentation_scripts import (
    _build_avatar_present_script,
    _build_clear_presentation_script,
    _build_present_existing_avatar_script,
    _build_present_playable_avatar_script,
)
from .python_rpc_client import _call_ue_python_json, call_ue_python
from .utils import normalize_dest_path, validate_local_file


def present_avatar_in_ue(
    avatar_path: str,
    dest_path: str = DEFAULT_AVATAR_DEST,
    as_skeletal: bool = True,
) -> bool:
    local_path = validate_local_file(avatar_path, (".fbx",))
    dest_path = normalize_dest_path(dest_path, DEFAULT_AVATAR_DEST)
    call_ue_python(_build_avatar_present_script(local_path, dest_path, as_skeletal))
    return True


def present_fbx_in_ue(
    avatar_path: str,
    dest_path: str = DEFAULT_AVATAR_DEST,
    as_skeletal: bool = True,
) -> bool:
    return present_avatar_in_ue(avatar_path, dest_path, as_skeletal=as_skeletal)


def present_existing_avatar_in_ue(asset_path: str) -> bool:
    if not asset_path or not asset_path.strip():
        raise ValueError("请选择 UE Avatar 资产")
    call_ue_python(_build_present_existing_avatar_script(asset_path.strip()))
    return True


def present_playable_avatar_in_ue(
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
    if not avatar_asset_path or not avatar_asset_path.strip():
        raise ValueError("请选择 UE Avatar SkeletalMesh 资产")
    return _call_ue_python_json(
        _build_present_playable_avatar_script(
            avatar_asset_path.strip(),
            idle_animation_path=(idle_animation_path or "").strip(),
            move_animation_path=(move_animation_path or "").strip(),
            playable_blueprint_path=(playable_blueprint_path or DEFAULT_PLAYABLE_CLASS_PATH).strip(),
            actor_label=(actor_label or DEFAULT_PLAYABLE_ACTOR_LABEL).strip(),
            mesh_forward_axis=mesh_forward_axis or "auto",
            mesh_relative_yaw=mesh_relative_yaw,
            align_to_ground=align_to_ground,
            ground_z=ground_z,
            destroy_existing=destroy_existing,
            walk_speed=walk_speed,
            run_speed=run_speed,
        )
    )


def clear_presentation_in_ue() -> dict:
    return _call_ue_python_json(_build_clear_presentation_script())


def get_actor_transform(actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL) -> dict:
    return _call_ue_python_json(_build_get_actor_transform_script(actor_label))


def move_actor(actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> dict:
    return _call_ue_python_json(_build_move_actor_script(actor_label, dx, dy, dz))


def move_actor_direction(
    actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
    direction: str = "forward",
    step: float = DEFAULT_MOVEMENT_STEP,
    forward_offset_yaw: float = 0.0,
    face_direction: bool = False,
) -> dict:
    return _call_ue_python_json(
        _build_move_actor_direction_script(
            actor_label,
            direction,
            step,
            forward_offset_yaw=forward_offset_yaw,
            face_direction=face_direction,
        )
    )


def rotate_actor(actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, yaw_delta: float = DEFAULT_ROTATION_STEP) -> dict:
    return _call_ue_python_json(_build_rotate_actor_script(actor_label, yaw_delta))


def set_actor_animation(
    actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
    motion_asset_path: str = "",
    avatar_asset_path: str = "",
    looping: bool = True,
) -> dict:
    if not motion_asset_path or not motion_asset_path.strip():
        raise ValueError("请选择 UE Motion AnimSequence 资产")
    return _call_ue_python_json(
        _build_set_actor_animation_script(
            actor_label,
            motion_asset_path.strip(),
            avatar_asset_path=(avatar_asset_path or "").strip(),
            looping=looping,
        )
    )


class SceneController:
    def present_uploaded_avatar(
        self,
        avatar_path: str,
        dest_path: str = DEFAULT_AVATAR_DEST,
        as_skeletal: bool = True,
    ) -> bool:
        return present_avatar_in_ue(avatar_path, dest_path=dest_path, as_skeletal=as_skeletal)

    def present_existing_avatar(self, asset_path: str) -> bool:
        return present_existing_avatar_in_ue(asset_path)

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
        return present_playable_avatar_in_ue(
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

    def clear_presentation(self) -> dict:
        return clear_presentation_in_ue()

    def spawn_prop(self, asset_path: str, transform: Optional[dict] = None) -> dict:
        raise NotImplementedError("Prop spawn belongs to the next scene-control milestone")

    def get_actor_transform(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL) -> dict:
        return get_actor_transform(actor_label)

    def move_actor(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> dict:
        return move_actor(actor_label, dx=dx, dy=dy, dz=dz)

    def move_actor_direction(
        self,
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
        direction: str = "forward",
        step: float = DEFAULT_MOVEMENT_STEP,
        forward_offset_yaw: float = 0.0,
        face_direction: bool = False,
    ) -> dict:
        return move_actor_direction(
            actor_label,
            direction=direction,
            step=step,
            forward_offset_yaw=forward_offset_yaw,
            face_direction=face_direction,
        )

    def rotate_actor(self, actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL, yaw_delta: float = DEFAULT_ROTATION_STEP) -> dict:
        return rotate_actor(actor_label, yaw_delta=yaw_delta)

    def set_actor_animation(
        self,
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
        motion_asset_path: str = "",
        avatar_asset_path: str = "",
        looping: bool = True,
    ) -> dict:
        return set_actor_animation(
            actor_label=actor_label,
            motion_asset_path=motion_asset_path,
            avatar_asset_path=avatar_asset_path,
            looping=looping,
        )
