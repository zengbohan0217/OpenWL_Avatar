"""FastAPI app assembly for the local UE Viewer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from serving.api.asset_routes import create_asset_router
from serving.api.scene_routes import create_scene_router
from serving.api.viewer_routes import create_viewer_router
from serving.services.asset_service import AssetService
from serving.services.scene_service import SceneService

logger = logging.getLogger("openwl.viewer")

STATIC_DIR = Path(__file__).resolve().parents[1] / "webui" / "static"
VIEWER_HTML = STATIC_DIR / "viewer.html"


def _http_error(exc: Exception) -> HTTPException:
    logger.error("API error: %s: %s", type(exc).__name__, exc, exc_info=True)
    return HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


def create_app(asset_service: Optional[AssetService] = None, scene_service: Optional[SceneService] = None) -> FastAPI:
    assets = asset_service or AssetService()
    scene = scene_service or SceneService()
    app = FastAPI(title="OpenWL Local UE Viewer", version="0.1.0")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(VIEWER_HTML)

    app.include_router(create_viewer_router(scene))
    app.include_router(create_asset_router(assets, _http_error))
    app.include_router(create_scene_router(scene, _http_error))

    return app
