"""
Import the current Luffi VFX test sample into an Unreal Engine project.

Run from UE:
  D:/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe ^
    "D:/document/Unreal Projects/特效探索/特效探索.uproject" ^
    -ExecutePythonScript="D:/document/4D-avatar/scripts/ue/import_luffi_vfx_sample.py"

Imported assets are placed under:
  /Game/WorldFlex/LuffiVFXTest
"""

from __future__ import annotations

import json
from pathlib import Path

try:
    import unreal
except ImportError:
    unreal = None


# 修改这里指向你本地存放 FBX 的目录
ASSETS_DIR = Path("D:/assets/luffi_sample")

CHARACTER_FBX = ASSETS_DIR / "luffi (2).fbx"
MOTION_FBX = [
    ASSETS_DIR / "Mma Kick.fbx",
    ASSETS_DIR / "Standing Melee Run Jump Attack (1)(1).fbx",
]

DEST_ROOT = "/Game/WorldFlex/LuffiVFXTest"
REPORT_PATH = Path("D:/document/4D-avatar/samples/luffi_vfx_test/ue_import_report.json")


def require_unreal() -> None:
    if unreal is None:
        raise RuntimeError("Run this script with Unreal Engine Python, not system Python.")


def ensure_dir(asset_path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(asset_path):
        unreal.EditorAssetLibrary.make_directory(asset_path)


def make_import_task(filename: Path, destination_path: str, options) -> object:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(filename))
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("options", options)
    return task


def make_skeletal_mesh_options() -> object:
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_textures", True)
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    return options


def make_animation_options(skeleton) -> object:
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", False)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("import_animations", True)
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    options.skeleton = skeleton
    return options


def import_tasks(tasks: list[object]) -> list[str]:
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    imported = []
    for task in tasks:
        imported.extend(task.get_editor_property("imported_object_paths"))
    return imported


def load_first_skeletal_mesh(imported_paths: list[str]):
    for asset_path in imported_paths:
        asset = unreal.EditorAssetLibrary.load_asset(asset_path)
        if isinstance(asset, unreal.SkeletalMesh):
            return asset
    raise RuntimeError(f"No SkeletalMesh found in imported paths: {imported_paths}")


def main() -> None:
    require_unreal()

    missing = [str(path) for path in [CHARACTER_FBX, *MOTION_FBX] if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing FBX files: " + ", ".join(missing))

    ensure_dir(DEST_ROOT)
    ensure_dir(f"{DEST_ROOT}/Character")
    ensure_dir(f"{DEST_ROOT}/Animations")

    character_task = make_import_task(
        CHARACTER_FBX,
        f"{DEST_ROOT}/Character",
        make_skeletal_mesh_options(),
    )
    character_imported = import_tasks([character_task])
    skeletal_mesh = load_first_skeletal_mesh(character_imported)
    skeleton = skeletal_mesh.get_editor_property("skeleton")

    animation_tasks = [
        make_import_task(path, f"{DEST_ROOT}/Animations", make_animation_options(skeleton))
        for path in MOTION_FBX
    ]
    animation_imported = import_tasks(animation_tasks)

    report = {
        "destination_root": DEST_ROOT,
        "character_fbx": str(CHARACTER_FBX),
        "motion_fbx": [str(path) for path in MOTION_FBX],
        "character_imported": character_imported,
        "animation_imported": animation_imported,
        "skeleton": skeleton.get_path_name() if skeleton else None,
        "next_manual_steps": [
            "Open each animation sequence.",
            "Scrub to contact frames and correct the JSON frame numbers.",
            "Add Anim Notifies for Niagara spawn events.",
            "Create Niagara systems for kick trail, impact burst, and run dust."
        ],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    unreal.log("WorldFlex Luffi VFX sample import finished.")
    unreal.log(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

