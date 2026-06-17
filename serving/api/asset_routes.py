"""Asset listing routes for the local UE Viewer."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from serving.services.asset_service import AssetService
from serving.ue.constants import DEFAULT_IMPORT_ROOT


def create_asset_router(asset_service: AssetService, http_error) -> APIRouter:
    router = APIRouter()

    @router.get("/api/assets/groups")
    def asset_groups(root_path: str = DEFAULT_IMPORT_ROOT) -> dict:
        try:
            return asset_service.list_all_groups(root_path=root_path)
        except Exception as exc:
            raise http_error(exc) from exc

    @router.get("/api/assets")
    def asset_list(asset_type: Optional[str] = Query(default=None, alias="type"), root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        try:
            return asset_service.list_assets(asset_type=asset_type, root_path=root_path)
        except Exception as exc:
            raise http_error(exc) from exc

    return router
