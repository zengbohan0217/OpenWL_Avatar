"""UE Asset Registry queries."""

from __future__ import annotations

import textwrap
from typing import Optional

from .asset_types import ASSET_TYPE_CLASSES, _normalize_asset_type
from .constants import DEFAULT_IMPORT_ROOT
from .python_rpc_client import _call_ue_python_json
from .utils import normalize_dest_path


def _asset_class_name_expr() -> str:
    return textwrap.dedent("""\
        def _asset_class_name(asset_data):
            try:
                return str(asset_data.asset_class_path.asset_name)
            except Exception:
                try:
                    return str(asset_data.asset_class)
                except Exception:
                    return ""
    """)


def list_ue_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    root_path = normalize_dest_path(root_path, DEFAULT_IMPORT_ROOT)
    script = _asset_class_name_expr() + textwrap.dedent(f"""\
        import unreal
        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = asset_registry.get_assets_by_path({root_path!r}, recursive=True)
        result = []
        for asset_data in assets:
            class_name = _asset_class_name(asset_data)
            package_name = str(asset_data.package_name)
            package_path = str(asset_data.package_path)
            asset_name = str(asset_data.asset_name)
            result.append({{
                "name": asset_name,
                "path": package_name,
                "class": class_name,
                "package_path": package_path,
            }})
    """)
    return _call_ue_python_json(script)


def _filter_assets_by_class(assets: list[dict], class_names: tuple[str, ...]) -> list[dict]:
    allowed = set(class_names)
    return [asset for asset in assets if asset.get("class") in allowed]


def _list_skeleton_assets_with_inferred(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    root_path = normalize_dest_path(root_path, DEFAULT_IMPORT_ROOT)
    script = _asset_class_name_expr() + textwrap.dedent(f"""\
        import unreal

        def _package_path_from_object(obj):
            path = str(obj.get_path_name())
            return path.split(".", 1)[0]

        def _asset_name_from_path(path):
            return path.rsplit("/", 1)[-1]

        def _add_skeleton(path, inferred_from=""):
            if not path or path in seen:
                return
            seen.add(path)
            result.append({{
                "name": _asset_name_from_path(path),
                "path": path,
                "class": "Skeleton",
                "package_path": path.rsplit("/", 1)[0],
                "inferred_from": inferred_from,
            }})

        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = asset_registry.get_assets_by_path({root_path!r}, recursive=True)
        result = []
        seen = set()
        skeletal_meshes = []
        for asset_data in assets:
            class_name = _asset_class_name(asset_data)
            package_name = str(asset_data.package_name)
            if class_name == "Skeleton":
                _add_skeleton(package_name)
            elif class_name == "SkeletalMesh":
                skeletal_meshes.append(package_name)

        for mesh_path in skeletal_meshes:
            try:
                mesh = unreal.load_asset(mesh_path)
                skeleton = mesh.get_editor_property("skeleton") if mesh is not None else None
                if skeleton is not None:
                    _add_skeleton(_package_path_from_object(skeleton), mesh_path)
            except Exception as exc:
                unreal.log_warning(f"[OpenWL] 无法从 SkeletalMesh 推断 Skeleton {{mesh_path}}: {{exc}}")
    """)
    return _call_ue_python_json(script)


def _skeleton_info_expr() -> str:
    return textwrap.dedent("""\
        def _package_path_from_object(obj):
            path = str(obj.get_path_name())
            return path.split(".", 1)[0]

        def _asset_name_from_path(path):
            return path.rsplit("/", 1)[-1]

        def _skeleton_path(asset):
            if asset is None:
                return ""
            skeleton = None
            try:
                skeleton = asset.get_editor_property("skeleton")
            except Exception:
                skeleton = getattr(asset, "skeleton", None)
            if skeleton is None:
                return ""
            return _package_path_from_object(skeleton)
    """)


def _list_motion_assets_with_skeleton(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    root_path = normalize_dest_path(root_path, DEFAULT_IMPORT_ROOT)
    script = _asset_class_name_expr() + _skeleton_info_expr() + textwrap.dedent(f"""\
        import unreal
        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        assets = asset_registry.get_assets_by_path({root_path!r}, recursive=True)
        result = []
        for asset_data in assets:
            class_name = _asset_class_name(asset_data)
            if class_name != "AnimSequence":
                continue
            package_name = str(asset_data.package_name)
            package_path = str(asset_data.package_path)
            asset_name = str(asset_data.asset_name)
            animation = unreal.load_asset(package_name)
            skeleton_path = _skeleton_path(animation)
            result.append({{
                "name": asset_name,
                "path": package_name,
                "class": class_name,
                "package_path": package_path,
                "skeleton_path": skeleton_path,
                "skeleton_name": _asset_name_from_path(skeleton_path) if skeleton_path else "",
            }})
    """)
    return _call_ue_python_json(script)


def list_assets_by_type(asset_type: str, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    normalized = _normalize_asset_type(asset_type)
    if normalized == "skeleton":
        return _list_skeleton_assets_with_inferred(root_path)
    if normalized == "motion":
        return _list_motion_assets_with_skeleton(root_path)
    return _filter_assets_by_class(list_ue_assets(root_path), ASSET_TYPE_CLASSES[normalized])


def list_avatar_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("avatar", root_path)


def list_skeleton_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("skeleton", root_path)


def list_motion_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("motion", root_path)


def list_effect_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("effect", root_path)


def list_material_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("material", root_path)


def list_texture_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("texture", root_path)


def list_prop_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("prop", root_path)


def list_weapon_assets(root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
    return list_assets_by_type("weapon", root_path)


class AssetRegistry:
    def list_assets(self, root_path: str = DEFAULT_IMPORT_ROOT, asset_type: Optional[str] = None) -> list[dict]:
        if asset_type:
            return list_assets_by_type(asset_type, root_path=root_path)
        return list_ue_assets(root_path)

    def list_avatar_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_avatar_assets(root_path)

    def list_skeleton_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_skeleton_assets(root_path)

    def list_motion_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_motion_assets(root_path)

    def list_effect_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_effect_assets(root_path)

    def list_material_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_material_assets(root_path)

    def list_texture_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_texture_assets(root_path)

    def list_prop_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_prop_assets(root_path)

    def list_weapon_assets(self, root_path: str = DEFAULT_IMPORT_ROOT) -> list[dict]:
        return list_weapon_assets(root_path)
