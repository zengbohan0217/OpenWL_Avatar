"""
UE5 Python entrypoint for importing a generated WorldFlex 4D Avatar sample.

Run this inside Unreal's Python environment, for example:
  UnrealEditor-Cmd.exe Project.uproject -ExecutePythonScript=scripts/ue/import_avatar.py -- --sample-dir D:/samples/sample_0001
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

try:
    import unreal
except ImportError:  # Allows syntax checks outside UE.
    unreal = None


DEFAULT_DESTINATION_ROOT = "/Game/WorldFlex/Generated"


def _require_unreal() -> None:
    if unreal is None:
        raise RuntimeError("This script must be run inside Unreal Engine's Python environment.")


def _asset_import_task(filename: Path, destination_path: str, automated: bool = True):
    task = unreal.AssetImportTask()
    task.filename = str(filename)
    task.destination_path = destination_path
    task.automated = automated
    task.save = True
    task.replace_existing = True
    return task


def import_files(files: Iterable[Path], destination_path: str) -> list[str]:
    _require_unreal()
    tasks = [_asset_import_task(path, destination_path) for path in files if path.exists()]
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)

    imported = []
    for task in tasks:
        imported.extend(task.imported_object_paths)
    return imported


def import_avatar(
    sample_dir: Path,
    avatar_fbx: Path | None = None,
    component_fbx_list: Iterable[Path] | None = None,
    animation_fbx_list: Iterable[Path] | None = None,
    destination_root: str = DEFAULT_DESTINATION_ROOT,
) -> dict:
    sample_dir = sample_dir.resolve()
    sample_name = sample_dir.name
    destination_path = f"{destination_root}/{sample_name}"

    avatar_fbx = avatar_fbx or sample_dir / "asset" / "avatar.fbx"
    component_fbx_list = list(component_fbx_list or (sample_dir / "asset" / "components").glob("*.fbx"))
    animation_fbx_list = list(animation_fbx_list or (sample_dir / "motion").glob("*.fbx"))

    imported_avatar = import_files([avatar_fbx], destination_path)
    imported_components = import_files(component_fbx_list, f"{destination_path}/Components")
    imported_animations = import_files(animation_fbx_list, f"{destination_path}/Animations")

    report = {
        "sample_dir": str(sample_dir),
        "destination_path": destination_path,
        "avatar_fbx": str(avatar_fbx),
        "component_fbx": [str(path) for path in component_fbx_list],
        "animation_fbx": [str(path) for path in animation_fbx_list],
        "imported_avatar": imported_avatar,
        "imported_components": imported_components,
        "imported_animations": imported_animations,
        "next_steps": [
            "Create or assign IK Rig and IK Retargeter.",
            "Attach component meshes to sockets.",
            "Create Level Sequence preview.",
            "Validate missing materials and textures."
        ],
    }

    report_path = sample_dir / "ue" / "import_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample-dir", required=True)
    parser.add_argument("--destination-root", default=DEFAULT_DESTINATION_ROOT)
    args = parser.parse_args()

    report = import_avatar(
        sample_dir=Path(args.sample_dir),
        destination_root=args.destination_root,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

