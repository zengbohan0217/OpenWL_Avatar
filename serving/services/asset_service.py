"""UI/API-friendly asset operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from serving.ue.asset_types import default_dest_for_asset_type
from serving.ue.constants import DEFAULT_IMPORT_ROOT
from serving.ue.ue_client import UEClient

SUPPORTED_IMPORT_ASSET_TYPES = ("avatar", "motion", "scene", "effect", "material", "texture", "prop", "weapon")
ASSET_GROUP_TYPES = ("avatar", "skeleton", "motion", "effect", "material", "texture", "prop", "weapon")


class AssetService:
    def __init__(self, client: Optional[UEClient] = None) -> None:
        self.client = client or UEClient()

    def default_destination(self, asset_type: str) -> str:
        return default_dest_for_asset_type(asset_type)

    def import_asset(self, src_path: str, asset_type: str, dst_path: str = "", **options: Any) -> dict:
        asset_type = (asset_type or "").strip().lower()
        if asset_type not in SUPPORTED_IMPORT_ASSET_TYPES:
            supported = ", ".join(SUPPORTED_IMPORT_ASSET_TYPES)
            raise ValueError(f"不支持的资产类型: {asset_type}（支持: {supported}）")
        src_path = Path(src_path).expanduser().resolve().as_posix()
        dst_path = dst_path or self.default_destination(asset_type)
        return self.client.import_asset(src_path, dst_path=dst_path, asset_type=asset_type, **options)

    def list_assets(self, asset_type: Optional[str] = None, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return self.client.list_assets(root_path=root_path, asset_type=asset_type)

    def list_all_groups(self, root_path: str = DEFAULT_IMPORT_ROOT) -> dict:
        groups: dict[str, list[dict] | dict[str, str]] = {}
        errors: dict[str, str] = {}
        for asset_type in ASSET_GROUP_TYPES:
            try:
                groups[asset_type] = self.list_assets(asset_type, root_path)
            except Exception as exc:
                groups[asset_type] = []
                errors[asset_type] = f"{type(exc).__name__}: {exc}"
        if errors:
            groups["_errors"] = errors
        return groups

    def import_package(self, package_path: str, dst_root: str = DEFAULT_IMPORT_ROOT) -> dict:
        raise NotImplementedError("Zip asset package import is reserved for a later milestone")
