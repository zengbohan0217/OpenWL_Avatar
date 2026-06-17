"""
Serving tests and compatibility launcher for the local UE asset/debug WebUI.

Run tests:
    python -m pytest test/test_ue_serving.py

Launch the local Gradio asset import/debug page:
    python test/test_ue_serving.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from serving.api.app import create_app
from serving.api.schemas import MoveActorRequest, PresentPlayableAvatarRequest, RotateActorRequest
from serving.services.asset_service import AssetService
from serving.ue.constants import (
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PLAYABLE_CLASS_PATH,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
    DEFAULT_RUN_SPEED,
    DEFAULT_WALK_SPEED,
)
from serving.ue.scripts.import_scripts import _motion_import_name
from serving.ue.scripts.presentation_scripts import _build_present_playable_avatar_script
from serving.webui.gradio_app import build_app


class FakeSceneService:
    def __init__(self):
        self.present_playable_avatar_call = None
        self.present_existing_avatar_call = None

    def check_connection(self):
        return True

    def present_existing_avatar(self, avatar_asset_path):
        self.present_existing_avatar_call = avatar_asset_path

    def present_playable_avatar(self, *args, **kwargs):
        self.present_playable_avatar_call = {"args": args, "kwargs": kwargs}
        return {"actor_label": kwargs.get("actor_label"), "warnings": []}


class FakeAssetService:
    def list_all_groups(self, root_path="/Game/Imported"):
        return {"avatar": [], "motion": [], "effect": [], "prop": []}

    def list_assets(self, asset_type=None, root_path="/Game/Imported"):
        return []


def test_viewer_config_uses_shared_defaults():
    app = create_app(asset_service=FakeAssetService(), scene_service=FakeSceneService())
    client = TestClient(app)

    response = client.get("/api/viewer/config")

    assert response.status_code == 200
    body = response.json()
    assert body["default_actor_label"] == DEFAULT_PRESENTATION_ACTOR_LABEL
    assert body["playable_actor_label"] == DEFAULT_PLAYABLE_ACTOR_LABEL
    assert body["playable_blueprint_path"] == DEFAULT_PLAYABLE_CLASS_PATH
    assert body["default_walk_speed"] == DEFAULT_WALK_SPEED
    assert body["default_run_speed"] == DEFAULT_RUN_SPEED
    assert body["movement_step"] == DEFAULT_MOVEMENT_STEP
    assert body["rotation_step"] == DEFAULT_ROTATION_STEP


def test_request_schema_defaults_use_shared_constants():
    playable = PresentPlayableAvatarRequest(avatar_asset_path="/Game/Imported/Avatars/Hero")
    move = MoveActorRequest()
    rotate = RotateActorRequest()

    assert playable.playable_blueprint_path == DEFAULT_PLAYABLE_CLASS_PATH
    assert playable.actor_label == DEFAULT_PLAYABLE_ACTOR_LABEL
    assert move.actor_label == DEFAULT_PRESENTATION_ACTOR_LABEL
    assert move.step == DEFAULT_MOVEMENT_STEP
    assert rotate.actor_label == DEFAULT_PRESENTATION_ACTOR_LABEL
    assert rotate.yaw_delta == DEFAULT_ROTATION_STEP


def test_asset_groups_returns_partial_results_when_one_type_fails():
    class PartialFailureClient:
        def list_assets(self, root_path="/Game/Imported", asset_type=None):
            if asset_type == "skeleton":
                raise RuntimeError("remote socket failed")
            return [{"type": asset_type, "root_path": root_path}]

    service = AssetService(client=PartialFailureClient())

    groups = service.list_all_groups(root_path="/Game/Imported")

    assert groups["avatar"] == [{"type": "avatar", "root_path": "/Game/Imported"}]
    assert groups["skeleton"] == []
    assert groups["motion"] == [{"type": "motion", "root_path": "/Game/Imported"}]
    assert groups["_errors"] == {"skeleton": "RuntimeError: remote socket failed"}


def test_motion_import_name_includes_target_skeleton():
    assert _motion_import_name("C:/tmp/Jogging.fbx", "/Game/Imported/Avatars/The_Boss_Skeleton") == "Jogging_The_Boss_Skeleton_Anim"
    assert _motion_import_name("C:/tmp/Jogging.fbx", "/Game/Imported/Avatars/The_Boss_Skeleton.The_Boss_Skeleton") == "Jogging_The_Boss_Skeleton_Anim"


def test_present_playable_avatar_route_passes_request_fields():
    scene = FakeSceneService()
    app = create_app(asset_service=FakeAssetService(), scene_service=scene)
    client = TestClient(app)

    response = client.post(
        "/api/scene/present-playable-avatar",
        json={
            "avatar_asset_path": "/Game/Imported/Avatars/Hero",
            "idle_animation_path": "/Game/Imported/Motions/Idle",
            "move_animation_path": "/Game/Imported/Motions/Run",
            "mesh_forward_axis": "+Y",
            "mesh_relative_yaw": -90,
            "walk_speed": 320,
            "run_speed": 620,
        },
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert scene.present_playable_avatar_call["args"] == ("/Game/Imported/Avatars/Hero",)
    kwargs = scene.present_playable_avatar_call["kwargs"]
    assert kwargs["idle_animation_path"] == "/Game/Imported/Motions/Idle"
    assert kwargs["move_animation_path"] == "/Game/Imported/Motions/Run"
    assert kwargs["mesh_forward_axis"] == "+Y"
    assert kwargs["mesh_relative_yaw"] == -90
    assert kwargs["walk_speed"] == 320
    assert kwargs["run_speed"] == 620


def test_present_avatar_route_still_uses_debug_presentation_path():
    scene = FakeSceneService()
    app = create_app(asset_service=FakeAssetService(), scene_service=scene)
    client = TestClient(app)

    response = client.post("/api/scene/present-avatar", json={"avatar_asset_path": "/Game/Imported/Avatars/Hero"})

    assert response.status_code == 200
    assert scene.present_existing_avatar_call == "/Game/Imported/Avatars/Hero"
    assert scene.present_playable_avatar_call is None


def test_trigger_skill_route_is_explicit_placeholder():
    app = create_app(asset_service=FakeAssetService(), scene_service=FakeSceneService())
    client = TestClient(app)

    response = client.post("/api/scene/trigger-skill", json={"skill_name": "Skill1"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["implemented"] is False
    assert body["skill_name"] == "Skill1"


def test_playable_script_contains_runtime_character_setup_hooks():
    script = _build_present_playable_avatar_script(
        "/Game/Imported/Avatars/Hero",
        idle_animation_path="/Game/Imported/Motions/Idle",
        move_animation_path="/Game/Imported/Motions/Run",
        mesh_forward_axis="+Y",
        mesh_relative_yaw=-90,
        walk_speed=320,
        run_speed=620,
    )

    assert DEFAULT_PLAYABLE_CLASS_PATH in script
    assert "OpenWL_Playable_Character" in script
    assert "/Game/Imported/Avatars/Hero" in script
    assert "auto_possess_player" in script
    assert "IdleAnimation" in script
    assert "MoveAnimation" in script
    assert "WalkSpeed" in script
    assert "RunSpeed" in script
    assert "mesh_relative_yaw" in script
    assert "mesh_bounds_min_z_before" in script
    assert "可玩角色只支持 SkeletalMesh" in script


if __name__ == "__main__":
    build_app().launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=False,
        prevent_thread_lock=False,
    )
