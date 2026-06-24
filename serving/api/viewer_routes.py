"""Viewer configuration and status routes."""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from fastapi import APIRouter

from serving.services.scene_service import SceneService
from serving.ue.config import PIXEL_STREAMING_URL, UE_HOST, UE_PORT, UE_REMOTE_URL, VIEWER_HOST, VIEWER_PORT
from serving.ue.constants import (
    DEFAULT_MOVEMENT_STEP,
    DEFAULT_PLAYABLE_ACTOR_LABEL,
    DEFAULT_PLAYABLE_CLASS_PATH,
    DEFAULT_PRESENTATION_ACTOR_LABEL,
    DEFAULT_ROTATION_STEP,
    DEFAULT_RUN_SPEED,
    DEFAULT_WALK_SPEED,
)


def _pixel_status() -> dict:
    if not PIXEL_STREAMING_URL:
        return {
            "configured": False,
            "reachable": False,
            "url": "",
            "message": "未配置 Pixel Streaming。设置 OPENWL_PIXEL_STREAMING_URL 后可在页面内嵌 UE 实时画面。",
        }

    parsed_url = urlparse(PIXEL_STREAMING_URL)
    viewer_hosts = {VIEWER_HOST, "127.0.0.1", "localhost"} if VIEWER_HOST in ("127.0.0.1", "localhost") else {VIEWER_HOST}
    if parsed_url.hostname in viewer_hosts and parsed_url.port == VIEWER_PORT:
        return {
            "configured": True,
            "reachable": False,
            "url": PIXEL_STREAMING_URL,
            "message": "OPENWL_PIXEL_STREAMING_URL 指向了 Viewer 自己。请填写 UE Pixel Streaming 的真实地址，不要使用 7870。",
        }

    try:
        response = requests.get(PIXEL_STREAMING_URL, timeout=2)
        reachable = response.status_code < 500
    except requests.RequestException as exc:
        return {
            "configured": True,
            "reachable": False,
            "url": PIXEL_STREAMING_URL,
            "message": f"Pixel Streaming 不可达: {exc}",
        }

    return {
        "configured": True,
        "reachable": reachable,
        "url": PIXEL_STREAMING_URL,
        "status_code": response.status_code,
        "message": "Pixel Streaming 页面可访问；这只表示 signalling/frontend 可打开，不代表 UE 已经推流" if reachable else "Pixel Streaming 页面返回服务端错误",
    }


def create_viewer_router(scene: SceneService) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health")
    def health() -> dict:
        return {"ok": True, "viewer_host": VIEWER_HOST, "viewer_port": VIEWER_PORT}

    @router.get("/api/ue/status")
    def ue_status() -> dict:
        ok = scene.check_connection()
        return {
            "ok": ok,
            "ue_host": UE_HOST,
            "ue_port": UE_PORT,
            "remote_url": UE_REMOTE_URL,
            "message": "UE Remote Control 已连接" if ok else f"无法连接 UE Remote Control: {UE_REMOTE_URL}",
        }

    @router.get("/api/viewer/config")
    def viewer_config() -> dict:
        return {
            "pixel_streaming_url": PIXEL_STREAMING_URL,
            "pixel_streaming_enabled": bool(PIXEL_STREAMING_URL),
            "default_actor_label": DEFAULT_PRESENTATION_ACTOR_LABEL,
            "playable_actor_label": DEFAULT_PLAYABLE_ACTOR_LABEL,
            "playable_blueprint_path": DEFAULT_PLAYABLE_CLASS_PATH,
            "default_walk_speed": DEFAULT_WALK_SPEED,
            "default_run_speed": DEFAULT_RUN_SPEED,
            "movement_step": DEFAULT_MOVEMENT_STEP,
            "rotation_step": DEFAULT_ROTATION_STEP,
            "viewer_host": VIEWER_HOST,
            "viewer_port": VIEWER_PORT,
        }

    @router.get("/api/viewer/pixel-status")
    def pixel_status() -> dict:
        return _pixel_status()

    return router
