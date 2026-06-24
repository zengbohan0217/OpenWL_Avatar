"""Sequence and animation operations."""

from __future__ import annotations

from .asset_importer import import_motion_to_ue_paths
from .config import DEFAULT_MOTION_DEST
from .constants import DEFAULT_PRESENTATION_ACTOR_LABEL
from .python_rpc_client import _call_ue_python_json
from .scripts.sequence_scripts import _build_play_motion_script, _build_resolve_avatar_skeleton_script


def resolve_avatar_skeleton(avatar_asset_path: str) -> str:
    if not avatar_asset_path or not avatar_asset_path.strip():
        return ""
    return _call_ue_python_json(_build_resolve_avatar_skeleton_script(avatar_asset_path))


def play_motion_on_avatar(
    motion_asset_path: str,
    avatar_asset_path: str = "",
    actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
) -> dict:
    if not motion_asset_path or not motion_asset_path.strip():
        raise ValueError("请选择 UE Motion AnimSequence 资产")
    script = _build_play_motion_script(motion_asset_path.strip(), (avatar_asset_path or "").strip(), actor_label)
    return _call_ue_python_json(script, result_var="openwl_play_motion_result")


def import_motion_and_play_in_ue(
    motion_path: str,
    avatar_asset_path: str = "",
    dest_path: str = DEFAULT_MOTION_DEST,
    skeleton_asset_path: str = "",
) -> dict:
    avatar_asset_path = (avatar_asset_path or "").strip()
    skeleton_asset_path = (skeleton_asset_path or "").strip()
    if not skeleton_asset_path and avatar_asset_path:
        skeleton_asset_path = resolve_avatar_skeleton(avatar_asset_path)
    imported_paths = import_motion_to_ue_paths(
        motion_path,
        avatar_name="Avatar",
        dest_path=dest_path,
        skeleton_asset_path=skeleton_asset_path,
    )
    motion_assets = [asset for asset in imported_paths if str(asset).lower().endswith("_anim") or str(asset)]
    if not motion_assets:
        raise RuntimeError("Motion 导入后没有返回可播放资产路径")
    result = play_motion_on_avatar(motion_assets[0], avatar_asset_path=avatar_asset_path)
    result["imported_paths"] = imported_paths
    result["skeleton_asset_path"] = skeleton_asset_path
    return result


class SequenceController:
    def resolve_avatar_skeleton(self, avatar_asset_path: str) -> str:
        return resolve_avatar_skeleton(avatar_asset_path)

    def play_animation(
        self,
        motion_asset_path: str,
        avatar_asset_path: str = "",
        actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL,
    ) -> dict:
        return play_motion_on_avatar(motion_asset_path, avatar_asset_path=avatar_asset_path, actor_label=actor_label)

    def import_motion_and_play(
        self,
        motion_path: str,
        avatar_asset_path: str = "",
        dest_path: str = DEFAULT_MOTION_DEST,
        skeleton_asset_path: str = "",
    ) -> dict:
        return import_motion_and_play_in_ue(
            motion_path,
            avatar_asset_path=avatar_asset_path,
            dest_path=dest_path,
            skeleton_asset_path=skeleton_asset_path,
        )

    def create_sequence(self, sequence_config: dict) -> dict:
        raise NotImplementedError("Custom sequence creation belongs to the next sequence-control milestone")
