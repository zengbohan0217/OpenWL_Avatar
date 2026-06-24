"""UE asset type mappings and validation helpers."""

from __future__ import annotations

from .config import (
    DEFAULT_AVATAR_DEST,
    DEFAULT_EFFECT_DEST,
    DEFAULT_MATERIAL_DEST,
    DEFAULT_MOTION_DEST,
    DEFAULT_PROP_DEST,
    DEFAULT_SCENE_DEST,
    DEFAULT_TEXTURE_DEST,
    DEFAULT_WEAPON_DEST,
)

ASSET_TYPE_DEFAULT_DESTS = {
    "avatar": DEFAULT_AVATAR_DEST,
    "motion": DEFAULT_MOTION_DEST,
    "scene": DEFAULT_SCENE_DEST,
    "effect": DEFAULT_EFFECT_DEST,
    "material": DEFAULT_MATERIAL_DEST,
    "texture": DEFAULT_TEXTURE_DEST,
    "prop": DEFAULT_PROP_DEST,
    "weapon": DEFAULT_WEAPON_DEST,
}

ASSET_TYPE_CLASSES = {
    "avatar": ("SkeletalMesh", "StaticMesh"),
    "skeleton": ("Skeleton",),
    "motion": ("AnimSequence",),
    "scene": ("World", "Level", "StaticMesh"),
    "effect": ("NiagaraSystem", "NiagaraEmitter", "ParticleSystem"),
    "material": ("Material", "MaterialInstance", "MaterialInstanceConstant"),
    "texture": ("Texture2D", "TextureCube"),
    "prop": ("StaticMesh", "SkeletalMesh"),
    "weapon": ("StaticMesh", "SkeletalMesh"),
}

ASSET_TYPE_ALIASES = {
    "avatars": "avatar",
    "skeletalmesh": "avatar",
    "staticmesh": "avatar",
    "skeletons": "skeleton",
    "motions": "motion",
    "animation": "motion",
    "animations": "motion",
    "animsequence": "motion",
    "scenes": "scene",
    "effects": "effect",
    "niagara": "effect",
    "materials": "material",
    "textures": "texture",
    "props": "prop",
    "weapons": "weapon",
}

GENERIC_IMPORT_SUFFIXES = (
    ".fbx",
    ".glb",
    ".gltf",
    ".usd",
    ".usda",
    ".usdc",
    ".obj",
    ".abc",
    ".png",
    ".jpg",
    ".jpeg",
    ".tga",
    ".exr",
    ".hdr",
    ".bmp",
    ".tif",
    ".tiff",
)
MESH_IMPORT_SUFFIXES = (".fbx", ".glb", ".gltf", ".usd", ".usda", ".usdc", ".obj", ".abc")
TEXTURE_IMPORT_SUFFIXES = (".png", ".jpg", ".jpeg", ".tga", ".exr", ".hdr", ".bmp", ".tif", ".tiff")

ASSET_TYPE_SUFFIXES = {
    "avatar": (".fbx", ".glb", ".gltf"),
    "motion": (".fbx",),
    "scene": (".fbx", ".glb", ".gltf", ".usd", ".usda", ".usdc"),
    "effect": GENERIC_IMPORT_SUFFIXES,
    "material": GENERIC_IMPORT_SUFFIXES,
    "texture": TEXTURE_IMPORT_SUFFIXES,
    "prop": MESH_IMPORT_SUFFIXES,
    "weapon": MESH_IMPORT_SUFFIXES,
}


def _normalize_asset_type(asset_type: str) -> str:
    normalized = (asset_type or "").strip().lower().replace("-", "_").replace(" ", "_")
    normalized = ASSET_TYPE_ALIASES.get(normalized, normalized)
    if normalized not in ASSET_TYPE_CLASSES:
        supported = ", ".join(sorted(ASSET_TYPE_CLASSES))
        raise ValueError(f"不支持的资产类型: {asset_type}（支持: {supported}）")
    return normalized


def default_dest_for_asset_type(asset_type: str) -> str:
    normalized = _normalize_asset_type(asset_type)
    if normalized == "skeleton":
        return DEFAULT_AVATAR_DEST
    return ASSET_TYPE_DEFAULT_DESTS[normalized]
