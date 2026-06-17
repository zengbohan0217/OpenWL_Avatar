"""UE Python script builders for asset imports."""

from __future__ import annotations

import textwrap
from pathlib import Path


def _ue_import_helpers_script() -> str:
    return textwrap.dedent("""\
        import unreal

        def _set_property(obj, property_name, value):
            try:
                obj.set_editor_property(property_name, value)
                return True
            except Exception as exc:
                unreal.log_warning(f"[OpenWL] 跳过属性 {property_name}: {exc}")
                return False

        def _new_import_task(source_path, dest_path, destination_name=""):
            task = unreal.AssetImportTask()
            task.set_editor_property("filename", source_path)
            task.set_editor_property("destination_path", dest_path)
            if destination_name:
                task.set_editor_property("destination_name", destination_name)
            task.set_editor_property("automated", True)
            task.set_editor_property("replace_existing", True)
            task.set_editor_property("save", True)
            return task

        def _run_import_task(task, label):
            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
            paths = task.get_editor_property("imported_object_paths") or []
            if not paths:
                raise RuntimeError(f"{label} 导入没有返回任何资产路径，请查看 UE Output Log")
            imported_paths = [str(path) for path in paths]
            for path in imported_paths:
                unreal.log(f"[OpenWL] Imported {label}: {path}")
            return imported_paths
    """)


def _build_fbx_import_script(local_path: str, dest_path: str, as_skeletal: bool, label: str) -> str:
    return _ue_import_helpers_script() + textwrap.dedent(f"""\
        source_path = {local_path!r}
        dest_path = {dest_path!r}
        task = _new_import_task(source_path, dest_path)
        options = unreal.FbxImportUI()
        _set_property(options, "import_mesh", True)
        _set_property(options, "import_as_skeletal", {bool(as_skeletal)!r})
        _set_property(options, "import_materials", True)
        _set_property(options, "import_textures", True)
        _set_property(options, "import_animations", {bool(as_skeletal)!r})
        task.set_editor_property("options", options)
        imported_paths = _run_import_task(task, {label!r})
        print("OPENWL_IMPORTED:" + repr(imported_paths))
    """)


def _build_generic_import_script(local_path: str, dest_path: str, label: str) -> str:
    return _ue_import_helpers_script() + textwrap.dedent(f"""\
        source_path = {local_path!r}
        dest_path = {dest_path!r}
        task = _new_import_task(source_path, dest_path)
        imported_paths = _run_import_task(task, {label!r})
        print("OPENWL_IMPORTED:" + repr(imported_paths))
    """)


def _safe_asset_name_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value.strip())
    return "_".join(part for part in cleaned.split("_") if part)


def _motion_import_name(local_path: str, skeleton_asset_path: str) -> str:
    motion_name = _safe_asset_name_part(Path(local_path).stem) or "Motion"
    skeleton_package_path = (skeleton_asset_path or "").split(".", 1)[0]
    skeleton_name = _safe_asset_name_part(skeleton_package_path.rsplit("/", 1)[-1])
    if skeleton_name:
        return f"{motion_name}_{skeleton_name}_Anim"
    return f"{motion_name}_Anim"


def _build_motion_import_script(local_path: str, dest_path: str, skeleton_asset_path: str, avatar_name: str) -> str:
    motion_name = _motion_import_name(local_path, skeleton_asset_path)
    return _ue_import_helpers_script() + textwrap.dedent(f"""\
        source_path = {local_path!r}
        dest_path = {dest_path!r}
        skeleton_asset_path = {skeleton_asset_path!r}
        avatar_name = {avatar_name!r}
        if avatar_name:
            unreal.log("[OpenWL] Motion avatar_name hint: " + avatar_name)

        task = _new_import_task(source_path, dest_path, {motion_name!r})
        options = unreal.FbxImportUI()
        for property_name, value in (
            ("automated_import_should_detect_type", False),
            ("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION),
            ("original_import_type", unreal.FBXImportType.FBXIT_ANIMATION),
            ("override_animation_name", {motion_name!r}),
            ("import_mesh", False),
            ("import_as_skeletal", False),
            ("import_materials", False),
            ("import_textures", False),
            ("import_animations", True),
        ):
            _set_property(options, property_name, value)

        if skeleton_asset_path:
            skeleton = unreal.load_asset(skeleton_asset_path)
            if skeleton is None:
                raise RuntimeError(f"找不到 Skeleton 资产: {skeleton_asset_path}")
            _set_property(options, "skeleton", skeleton)

        try:
            _set_property(options.anim_sequence_import_data, "import_custom_attribute", True)
        except Exception:
            pass

        task.set_editor_property("options", options)
        imported_paths = _run_import_task(task, "Motion FBX")
        print("OPENWL_IMPORTED_MOTION:" + repr(imported_paths))
    """)
