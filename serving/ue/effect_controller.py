"""Effect asset operations."""

from __future__ import annotations

from typing import Any, Optional

from .asset_importer import import_asset
from .asset_registry import list_effect_assets
from .config import DEFAULT_EFFECT_DEST
from .constants import DEFAULT_IMPORT_ROOT


class EffectController:
    def import_effect(self, src_path: str, dst_path: str = DEFAULT_EFFECT_DEST, **options: Any) -> dict:
        return import_asset(src_path, dst_path=dst_path, asset_type="effect", **options)

    def list_effects(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_effect_assets(root_path)

    def spawn_effect(self, effect_asset_path: str, attach_to: Optional[dict] = None) -> dict:
        raise NotImplementedError("Effect socket binding and triggering belongs to the next effect-control milestone")

    def destroy_effect(self, effect_name: str) -> dict:
        raise NotImplementedError("Effect lifecycle control belongs to the next effect-control milestone")
