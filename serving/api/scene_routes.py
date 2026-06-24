"""Scene presentation and control routes for the local UE Viewer."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from serving.api.schemas import (
    MoveActorRequest,
    PlayMotionRequest,
    PresentAvatarRequest,
    PresentPlayableAvatarRequest,
    RotateActorRequest,
    SetActorAnimationRequest,
    TriggerSkillRequest,
)
from serving.services.scene_service import SceneService
from serving.ue.constants import DEFAULT_PRESENTATION_ACTOR_LABEL

logger = logging.getLogger("openwl.viewer")


def create_scene_router(scene: SceneService, http_error) -> APIRouter:
    router = APIRouter()

    @router.post("/api/scene/present-avatar")
    def present_avatar(request: PresentAvatarRequest) -> dict:
        try:
            scene.present_existing_avatar(request.avatar_asset_path)
            return {"ok": True, "avatar_asset_path": request.avatar_asset_path}
        except Exception as exc:
            raise http_error(exc) from exc

    @router.post("/api/scene/present-playable-avatar")
    def present_playable_avatar(request: PresentPlayableAvatarRequest) -> dict:
        try:
            result = scene.present_playable_avatar(
                request.avatar_asset_path,
                idle_animation_path=request.idle_animation_path,
                move_animation_path=request.move_animation_path,
                playable_blueprint_path=request.playable_blueprint_path,
                actor_label=request.actor_label,
                mesh_forward_axis=request.mesh_forward_axis,
                mesh_relative_yaw=request.mesh_relative_yaw,
                align_to_ground=request.align_to_ground,
                ground_z=request.ground_z,
                destroy_existing=request.destroy_existing,
                walk_speed=request.walk_speed,
                run_speed=request.run_speed,
            )
            result["ok"] = True
            return result
        except Exception as exc:
            raise http_error(exc) from exc

    @router.post("/api/scene/trigger-skill")
    def trigger_skill(request: TriggerSkillRequest) -> dict:
        return {
            "ok": False,
            "implemented": False,
            "actor_label": request.actor_label,
            "skill_name": request.skill_name,
            "message": "Skill runtime hook is reserved for a later milestone.",
        }

    @router.post("/api/scene/play-motion")
    def play_motion(request: PlayMotionRequest) -> dict:
        try:
            result = scene.play_motion(request.motion_asset_path, avatar_asset_path=request.avatar_asset_path)
            result["ok"] = True
            return result
        except Exception as exc:
            raise http_error(exc) from exc

    @router.post("/api/scene/clear")
    def clear_scene() -> dict:
        try:
            result = scene.clear_presentation()
            result["ok"] = True
            return result
        except Exception as exc:
            raise http_error(exc) from exc

    @router.post("/api/scene/move")
    def move_actor(request: MoveActorRequest) -> dict:
        try:
            if request.direction:
                logger.info("Move request: direction=%s, offset=%s, step=%s", request.direction, request.forward_offset_yaw, request.step)
                return scene.move_actor_direction(
                    request.actor_label,
                    direction=request.direction,
                    step=request.step,
                    forward_offset_yaw=request.forward_offset_yaw,
                    face_direction=request.face_direction,
                )
            return scene.move_actor(request.actor_label, dx=request.dx, dy=request.dy, dz=request.dz)
        except Exception as exc:
            raise http_error(exc) from exc

    @router.post("/api/scene/rotate")
    def rotate_actor(request: RotateActorRequest) -> dict:
        try:
            return scene.rotate_actor(request.actor_label, yaw_delta=request.yaw_delta)
        except Exception as exc:
            raise http_error(exc) from exc

    @router.post("/api/scene/set-animation")
    def set_actor_animation(request: SetActorAnimationRequest) -> dict:
        try:
            return scene.set_actor_animation(
                actor_label=request.actor_label,
                motion_asset_path=request.motion_asset_path,
                avatar_asset_path=request.avatar_asset_path,
                looping=request.looping,
            )
        except Exception as exc:
            raise http_error(exc) from exc

    @router.get("/api/scene/transform")
    def actor_transform(actor_label: str = DEFAULT_PRESENTATION_ACTOR_LABEL) -> dict:
        try:
            return scene.get_actor_transform(actor_label)
        except Exception as exc:
            raise http_error(exc) from exc

    return router
