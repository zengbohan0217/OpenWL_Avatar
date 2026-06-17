"""Tests and compatibility launcher for the local UE Viewer page.

These cover the HTTP routes used by the 7870 Viewer page to present and
manipulate a single Avatar. Pixel Streaming keyboard input is handled by UE
Runtime and still needs manual runtime verification.

Run tests:
    python -m pytest test/test_viewer_avatar_control.py

Launch the local UE Streaming Viewer / Avatar Controller page:
    python test/test_viewer_avatar_control.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("OPENWL_PIXEL_STREAMING_URL", "http://127.0.0.1:8080/player.html")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from serving.api.app import create_app
from serving.ue.constants import (
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
)


class FakeSceneService:
    def __init__(self):
        self.present_playable_avatar_call = None
        self.move_actor_direction_call = None
        self.move_actor_call = None
        self.rotate_actor_call = None
        self.set_actor_animation_call = None
        self.get_actor_transform_call = None

    def check_connection(self):
        return True

    def present_playable_avatar(self, *args, **kwargs):
        self.present_playable_avatar_call = {"args": args, "kwargs": kwargs}
        return {
            "actor_label": kwargs.get("actor_label"),
            "actor_path": "/Temp/OpenWL_Playable_Character",
            "warnings": [],
        }

    def move_actor_direction(self, actor_label, **kwargs):
        self.move_actor_direction_call = {"actor_label": actor_label, **kwargs}
        return {"actor_label": actor_label, **kwargs}

    def move_actor(self, actor_label, dx=0.0, dy=0.0, dz=0.0):
        self.move_actor_call = {"actor_label": actor_label, "dx": dx, "dy": dy, "dz": dz}
        return self.move_actor_call

    def rotate_actor(self, actor_label, yaw_delta=DEFAULT_ROTATION_STEP):
        self.rotate_actor_call = {"actor_label": actor_label, "yaw_delta": yaw_delta}
        return self.rotate_actor_call

    def set_actor_animation(self, **kwargs):
        self.set_actor_animation_call = kwargs
        return kwargs

    def get_actor_transform(self, actor_label):
        self.get_actor_transform_call = actor_label
        return {
            "actor_label": actor_label,
            "location": {"x": 10, "y": 20, "z": 30},
            "rotation": {"pitch": 0, "yaw": 90, "roll": 0},
        }


class FakeAssetService:
    def list_all_groups(self, root_path="/Game/Imported"):
        return {"avatar": [], "motion": [], "effect": [], "prop": []}

    def list_assets(self, asset_type=None, root_path="/Game/Imported"):
        return []


def make_client(scene=None):
    scene = scene or FakeSceneService()
    app = create_app(asset_service=FakeAssetService(), scene_service=scene)
    return TestClient(app), scene


def test_viewer_presents_playable_avatar_for_user_control():
    client, scene = make_client()

    response = client.post(
        "/api/scene/present-playable-avatar",
        json={
            "avatar_asset_path": "/Game/Imported/Avatars/Hero",
            "idle_animation_path": "/Game/Imported/Motions/Idle",
            "move_animation_path": "/Game/Imported/Motions/Run",
            "actor_label": DEFAULT_PLAYABLE_ACTOR_LABEL,
            "walk_speed": 320,
            "run_speed": 620,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["actor_label"] == DEFAULT_PLAYABLE_ACTOR_LABEL
    assert scene.present_playable_avatar_call["args"] == ("/Game/Imported/Avatars/Hero",)
    assert scene.present_playable_avatar_call["kwargs"]["idle_animation_path"] == "/Game/Imported/Motions/Idle"
    assert scene.present_playable_avatar_call["kwargs"]["move_animation_path"] == "/Game/Imported/Motions/Run"


def test_viewer_move_direction_route_targets_default_presentation_actor():
    client, scene = make_client()

    response = client.post(
        "/api/scene/move",
        json={"direction": "forward", "face_direction": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["actor_label"] == DEFAULT_PRESENTATION_ACTOR_LABEL
    assert body["direction"] == "forward"
    assert body["step"] == DEFAULT_MOVEMENT_STEP
    assert body["face_direction"] is True
    assert scene.move_actor_direction_call == {
        "actor_label": DEFAULT_PRESENTATION_ACTOR_LABEL,
        "direction": "forward",
        "step": DEFAULT_MOVEMENT_STEP,
        "forward_offset_yaw": 0.0,
        "face_direction": True,
    }


def test_viewer_move_delta_route_forwards_xyz_offsets():
    client, scene = make_client()

    response = client.post(
        "/api/scene/move",
        json={"actor_label": "CustomActor", "dx": 1.5, "dy": -2.0, "dz": 3.25},
    )

    assert response.status_code == 200
    assert response.json() == {"actor_label": "CustomActor", "dx": 1.5, "dy": -2.0, "dz": 3.25}
    assert scene.move_actor_call == {"actor_label": "CustomActor", "dx": 1.5, "dy": -2.0, "dz": 3.25}


def test_viewer_rotate_route_uses_default_rotation_step():
    client, scene = make_client()

    response = client.post("/api/scene/rotate", json={})

    assert response.status_code == 200
    assert response.json() == {"actor_label": DEFAULT_PRESENTATION_ACTOR_LABEL, "yaw_delta": DEFAULT_ROTATION_STEP}
    assert scene.rotate_actor_call == {"actor_label": DEFAULT_PRESENTATION_ACTOR_LABEL, "yaw_delta": DEFAULT_ROTATION_STEP}


def test_viewer_set_animation_route_forwards_motion_selection():
    client, scene = make_client()

    response = client.post(
        "/api/scene/set-animation",
        json={
            "actor_label": DEFAULT_PLAYABLE_ACTOR_LABEL,
            "motion_asset_path": "/Game/Imported/Motions/Run",
            "avatar_asset_path": "/Game/Imported/Avatars/Hero",
            "looping": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "actor_label": DEFAULT_PLAYABLE_ACTOR_LABEL,
        "motion_asset_path": "/Game/Imported/Motions/Run",
        "avatar_asset_path": "/Game/Imported/Avatars/Hero",
        "looping": True,
    }
    assert scene.set_actor_animation_call == response.json()


def test_viewer_transform_route_reads_selected_actor():
    client, scene = make_client()

    response = client.get(f"/api/scene/transform?actor_label={DEFAULT_PLAYABLE_ACTOR_LABEL}")

    assert response.status_code == 200
    body = response.json()
    assert body["actor_label"] == DEFAULT_PLAYABLE_ACTOR_LABEL
    assert body["location"] == {"x": 10, "y": 20, "z": 30}
    assert scene.get_actor_transform_call == DEFAULT_PLAYABLE_ACTOR_LABEL


def test_viewer_rejects_invalid_move_direction():
    client, _scene = make_client()

    response = client.post("/api/scene/move", json={"direction": "diagonal"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "direction"]


if __name__ == "__main__":
    import uvicorn

    from serving.ue.config import VIEWER_HOST, VIEWER_PORT

    uvicorn.run(create_app(), host=VIEWER_HOST, port=VIEWER_PORT)
