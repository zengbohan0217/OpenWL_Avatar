"""
Local debug WebUI for importing and presenting UE assets.

Run:
    python -m serving.webui.gradio_app
"""
import os
import sys
from pathlib import Path
from typing import Optional

os.environ["NO_PROXY"] = "127.0.0.1,localhost"
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import gradio as gr


def _patch_gradio_schema_for_local_env() -> None:
    try:
        from gradio_client import utils as client_utils
    except Exception:
        return

    original = client_utils._json_schema_to_python_type

    def patched(schema, defs=None):
        if isinstance(schema, bool):
            return "Any"
        return original(schema, defs)

    client_utils._json_schema_to_python_type = patched


_patch_gradio_schema_for_local_env()

from serving.services.asset_service import AssetService
from serving.services.scene_service import SceneService
from serving.ue.config import (
    DEFAULT_AVATAR_DEST,
    DEFAULT_MOTION_DEST,
    DEFAULT_PROP_DEST,
    UE_HOST,
    UE_PORT,
)

ASSET_SERVICE = AssetService()
SCENE_SERVICE = SceneService()

GENERIC_ASSET_TYPES = ["scene", "effect", "material", "texture", "prop", "weapon"]
GENERIC_FILE_TYPES = [
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
]


def _uploaded_path(file_obj) -> str:
    return file_obj.name if hasattr(file_obj, "name") else str(file_obj)


def _ensure_ue_connected() -> Optional[str]:
    if SCENE_SERVICE.check_connection():
        return None
    return (
        f"无法连接 UE Remote Control ({UE_HOST}:{UE_PORT})。\n"
        "请确认 UE 编辑器已启动，并已启用 Remote Control API 与 Python Editor Script Plugin。"
    )


def _asset_choices(assets) -> list[str]:
    return [asset.get("path", "") for asset in assets if asset.get("path")]


def _motion_choices(assets) -> list[tuple[str, str]]:
    choices = []
    for asset in assets:
        path = asset.get("path", "")
        if not path:
            continue
        skeleton_name = asset.get("skeleton_name") or "无 Skeleton"
        label = f"{asset.get('name') or path} — Skeleton: {skeleton_name}"
        choices.append((label, path))
    return choices


def _selected_path(value) -> str:
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return (value or "").strip()


def _ue_package_path(asset_path: str) -> str:
    return _selected_path(asset_path).split(".", 1)[0]


def on_check_connection():
    if SCENE_SERVICE.check_connection():
        return f"UE Remote Control 连接正常 ({UE_HOST}:{UE_PORT})"
    return (
        "无法连接 UE Remote Control。请检查：\n"
        "1. UE 编辑器是否启动\n"
        "2. Remote Control API 插件是否启用\n"
        f"3. 当前连接地址是否正确: {UE_HOST}:{UE_PORT}"
    )


def on_clear_presentation():
    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    try:
        result = SCENE_SERVICE.clear_presentation()
    except Exception as exc:
        return f"清除当前界面展示失败: {type(exc).__name__}: {exc}"

    removed = result.get("removed", [])
    if not removed:
        return "当前 UE 关卡里没有 OpenWL 展示对象需要清除；Content Browser 里的已导入资产不会被删除。"

    lines = [
        f"已清除当前 UE 关卡展示对象: {result.get('count', len(removed))}",
        "只删除当前界面展示 Actor / Camera / Sequence；Content Browser 里的 Avatar/Motion/Effect/Prop 资产不会被删除。",
    ]
    lines.extend(f"- {item.get('label', '')}: {item.get('path', '')}" for item in removed)
    return "\n".join(lines)


def _empty_asset_updates(count: int):
    return tuple(gr.update(choices=[], value=None) for _ in range(count))


def on_refresh_assets():
    connection_error = _ensure_ue_connected()
    if connection_error:
        return (*_empty_asset_updates(2), connection_error)

    try:
        groups = ASSET_SERVICE.list_all_groups()
        avatar_choices = _asset_choices(groups.get("avatar", []))
        motion_choices = _motion_choices(groups.get("motion", []))
    except Exception as exc:
        return (*_empty_asset_updates(2), f"刷新 UE 资产列表失败: {type(exc).__name__}: {exc}")

    status_lines = [
        "UE 资产列表已刷新" if not groups.get("_errors") else "UE 资产列表已部分刷新（部分类型查询失败）",
        f"Avatar: {len(avatar_choices)}",
        f"Motion: {len(motion_choices)}",
    ]
    if groups.get("_errors"):
        status_lines.append("失败类型:")
        status_lines.extend(f"- {asset_type}: {message}" for asset_type, message in groups["_errors"].items())
    status = "\n".join(status_lines)
    return (
        gr.update(choices=avatar_choices, value=avatar_choices[0] if avatar_choices else None),
        gr.update(choices=[("请选择 Motion", ""), *motion_choices], value=""),
        status,
    )


def on_import_avatar(file_obj, dest_path, as_skeletal):
    if file_obj is None:
        return "请先选择 avatar 文件"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    local_path = _uploaded_path(file_obj)
    try:
        ASSET_SERVICE.import_asset(local_path, "avatar", dst_path=dest_path, as_skeletal=as_skeletal)
    except Exception as exc:
        return f"Avatar 导入失败: {type(exc).__name__}: {exc}"

    suffix = Path(local_path).suffix.lower()
    skeletal_text = bool(as_skeletal) if suffix == ".fbx" else "GLB/GLTF 不适用"
    return "\n".join(
        [
            "Avatar 导入请求已发送至 UE",
            f"源文件: {local_path}",
            f"UE 目标路径: {dest_path}",
            f"文件类型: {suffix}",
            f"作为 Skeletal Mesh: {skeletal_text}",
            "导入完成后请点击“刷新 UE 资产列表”。",
        ]
    )


def on_present_uploaded_avatar(file_obj, dest_path, as_skeletal):
    if file_obj is None:
        return "请先选择 avatar .fbx 文件"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    local_path = _uploaded_path(file_obj)
    if Path(local_path).suffix.lower() != ".fbx":
        return "展示上传 Avatar 当前只支持 .fbx 文件；GLB/GLTF 请先导入，再刷新资产列表并选择 UE Avatar 调试展示。"

    try:
        SCENE_SERVICE.present_uploaded_avatar(local_path, dest_path=dest_path, as_skeletal=as_skeletal)
    except Exception as exc:
        return f"Avatar 调试展示失败: {type(exc).__name__}: {exc}"

    return "\n".join(
        [
            "Avatar 已导入并调试展示到 UE 当前关卡",
            f"源文件: {local_path}",
            f"UE 目标路径: {dest_path}",
            f"作为 Skeletal Mesh: {bool(as_skeletal)}",
            "这只影响当前关卡展示，不会删除或覆盖 Content Browser 里的其他资产。",
        ]
    )


def on_present_existing_avatar(selected_avatar_path):
    selected_avatar_path = _selected_path(selected_avatar_path)
    if not selected_avatar_path:
        return "请先刷新并选择一个 UE Avatar 资产"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    try:
        SCENE_SERVICE.present_existing_avatar(selected_avatar_path)
    except Exception as exc:
        return f"选中 Avatar 调试展示失败: {type(exc).__name__}: {exc}"

    return "\n".join(
        [
            "选中 UE Avatar 已调试展示到当前关卡",
            f"UE Avatar: {selected_avatar_path}",
        ]
    )


def on_avatar_selection_change(selected_avatar_path):
    selected_avatar_path = _selected_path(selected_avatar_path)
    if not selected_avatar_path:
        return "请先选择 Avatar，系统会自动读取它绑定的 Skeleton。"
    try:
        skeleton_asset_path = _ue_package_path(SCENE_SERVICE.resolve_avatar_skeleton(selected_avatar_path))
    except Exception as exc:
        return f"自动读取 Skeleton 失败: {type(exc).__name__}: {exc}"
    return skeleton_asset_path or "未从该 Avatar 读取到 Skeleton，请确认它是 SkeletalMesh。"


def _skeleton_for_motion(selected_avatar_path, manual_skeleton_path):
    manual_skeleton_path = _ue_package_path(manual_skeleton_path)
    if manual_skeleton_path:
        return manual_skeleton_path

    selected_avatar_path = _selected_path(selected_avatar_path)
    if selected_avatar_path:
        return _ue_package_path(SCENE_SERVICE.resolve_avatar_skeleton(selected_avatar_path))

    return ""


def on_import_motion(file_obj, dest_path, selected_avatar_path, manual_skeleton_path):
    if file_obj is None:
        return "请先选择 motion .fbx 文件"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    local_path = _uploaded_path(file_obj)
    try:
        skeleton_asset_path = _skeleton_for_motion(selected_avatar_path, manual_skeleton_path)
        if not skeleton_asset_path:
            return "请先选择一个 SkeletalMesh Avatar，或在高级选项里手动填写 Skeleton package path；Skeleton 决定 Motion 绑定到哪个骨骼。"
        ASSET_SERVICE.import_asset(
            local_path,
            "motion",
            dst_path=dest_path,
            avatar_name="Avatar",
            skeleton_asset_path=skeleton_asset_path,
        )
    except Exception as exc:
        return f"Motion 导入失败: {type(exc).__name__}: {exc}"

    skeleton_text = skeleton_asset_path
    return "\n".join(
        [
            "Motion 导入请求已发送至 UE",
            f"源文件: {local_path}",
            f"UE 目标路径: {dest_path}",
            f"Skeleton: {skeleton_text}",
            "导入完成后请点击“刷新 UE 资产列表”。",
        ]
    )


def on_import_and_play_motion(file_obj, dest_path, selected_avatar_path, manual_skeleton_path):
    selected_avatar_path = _selected_path(selected_avatar_path)
    if file_obj is None:
        return "请先选择 motion .fbx 文件"
    if not selected_avatar_path:
        return "请先选择一个 SkeletalMesh Avatar，用于绑定并播放 Motion"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    local_path = _uploaded_path(file_obj)
    try:
        skeleton_asset_path = _skeleton_for_motion(selected_avatar_path, manual_skeleton_path)
        result = SCENE_SERVICE.import_motion_and_play(
            local_path,
            avatar_asset_path=selected_avatar_path,
            dest_path=dest_path,
            skeleton_asset_path=skeleton_asset_path,
        )
    except Exception as exc:
        return f"Motion 导入并调试播放失败: {type(exc).__name__}: {exc}"

    return "\n".join(
        [
            "Motion 已导入，并已创建 Sequencer 调试展示",
            f"Motion 文件: {local_path}",
            f"导入资产: {', '.join(result.get('imported_paths', []))}",
            f"Avatar: {selected_avatar_path}",
            f"Skeleton: {result.get('skeleton_asset_path') or skeleton_asset_path or '由 Avatar 自动推断或未填写'}",
            f"Sequence: {result.get('sequence_path', '')}",
            f"Sequence Actor: {result.get('sequence_actor_path', '')}",
            f"Animation Section: {result.get('assigned_animation_path', '')}",
            f"Actor: {result.get('actor_path', '')}",
            f"Component: {result.get('component_path', '')}",
            f"Camera: {result.get('camera_path', '')}",
            f"Duration Frames: {result.get('duration_frames', '')}",
        ]
    )


def on_play_existing_motion(selected_motion_path, selected_avatar_path):
    selected_motion_path = _selected_path(selected_motion_path)
    selected_avatar_path = _selected_path(selected_avatar_path)
    if not selected_motion_path:
        return "请先刷新并选择一个 UE Motion AnimSequence"
    if not selected_avatar_path:
        return "请先选择一个 SkeletalMesh Avatar"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    try:
        result = SCENE_SERVICE.play_motion(selected_motion_path, avatar_asset_path=selected_avatar_path)
    except Exception as exc:
        return f"播放选中 Motion 失败: {type(exc).__name__}: {exc}"

    return "\n".join(
        [
            "选中 UE Motion 已创建 Sequencer 调试展示",
            f"Motion: {selected_motion_path}",
            f"Avatar: {selected_avatar_path}",
            f"Sequence: {result.get('sequence_path', '')}",
            f"Sequence Actor: {result.get('sequence_actor_path', '')}",
            f"Animation Section: {result.get('assigned_animation_path', '')}",
            f"Actor: {result.get('actor_path', '')}",
            f"Component: {result.get('component_path', '')}",
            f"Camera: {result.get('camera_path', '')}",
            f"Duration Frames: {result.get('duration_frames', '')}",
        ]
    )


def on_generic_asset_type_change(asset_type):
    asset_type = _selected_path(asset_type) or "prop"
    try:
        return ASSET_SERVICE.default_destination(asset_type)
    except Exception:
        return DEFAULT_PROP_DEST


def on_import_generic_asset(file_obj, asset_type, dest_path, as_skeletal):
    if file_obj is None:
        return "请先选择要导入的资产文件"

    connection_error = _ensure_ue_connected()
    if connection_error:
        return connection_error

    asset_type = _selected_path(asset_type) or "prop"
    local_path = _uploaded_path(file_obj)
    try:
        result = ASSET_SERVICE.import_asset(
            local_path,
            asset_type,
            dst_path=dest_path,
            as_skeletal=as_skeletal,
        )
    except Exception as exc:
        return f"通用资产导入失败: {type(exc).__name__}: {exc}"

    imported_paths = result.get("imported_paths", [])
    return "\n".join(
        [
            "通用资产导入请求已发送至 UE",
            f"资产类型: {result.get('asset_type', asset_type)}",
            f"源文件: {result.get('src_path', local_path)}",
            f"UE 目标路径: {result.get('dest_path', dest_path)}",
            f"导入资产: {', '.join(imported_paths) if imported_paths else 'UE 未返回路径'}",
            "导入完成后请点击“刷新 UE 资产列表”。",
            "说明：Effect 当前只做导入/列表，不做 Socket 绑定或技能触发。",
        ]
    )


def build_app():
    with gr.Blocks(title="OpenWL UE Asset Import") as app:
        gr.Markdown("# OpenWL UE 资产上传 / 导入调试页")
        gr.Markdown("这个页面主要负责本地上传、导入和刷新 UE 资产列表；也保留快速展示 / 播放按钮方便调试。正式 UE 实时画面和角色控制请使用独立 Viewer 页。")

        with gr.Row():
            check_btn = gr.Button("检查 UE 连接")
            refresh_btn = gr.Button("刷新 UE 资产列表", variant="primary")
            clear_btn = gr.Button("清除当前展示（不删除资产）", variant="secondary")
        with gr.Row():
            check_output = gr.Textbox(label="连接 / 刷新状态", lines=9, interactive=False)

        gr.Markdown("## 1. 选择 / 导入 Avatar")
        gr.Markdown("主流程只需要选择 Avatar。Skeleton、材质、贴图通常由 Avatar 自身携带，页面会自动读取 Avatar 绑定的 Skeleton。")
        with gr.Row():
            avatar_asset_dropdown = gr.Dropdown(label="已有 Avatar", choices=[], interactive=True)
            avatar_skeleton_display = gr.Textbox(label="自动读取的 Avatar Skeleton", interactive=False)
        with gr.Row():
            avatar_file_input = gr.File(
                label="上传 Avatar 文件 (.fbx / .glb / .gltf)",
                file_types=[".fbx", ".glb", ".gltf"],
            )
            avatar_dest_input = gr.Textbox(
                label="Avatar UE 目标路径",
                value=DEFAULT_AVATAR_DEST,
            )
            skeletal_input = gr.Checkbox(
                label="FBX 作为 Skeletal Mesh 导入",
                value=True,
            )
        with gr.Row():
            import_avatar_btn = gr.Button("导入 Avatar", variant="primary")
            present_uploaded_avatar_btn = gr.Button("导入并调试展示上传 Avatar", variant="secondary")
            present_existing_avatar_btn = gr.Button("调试展示选中 Avatar", variant="secondary")

        gr.Markdown("---")
        gr.Markdown("## 2. 给当前 Avatar 导入 / 播放 Motion")
        gr.Markdown("先选择目标 Avatar，系统会自动使用它绑定的 Skeleton 导入 Motion。Motion 保存目录只决定 AnimSequence 放在哪里；Skeleton 才决定 Motion 绑定到哪个骨骼。")
        with gr.Row():
            motion_asset_dropdown = gr.Dropdown(label="已有 Motion（显示其 Skeleton）", choices=[], interactive=True)
            motion_file_input = gr.File(
                label="上传 Motion 文件 (.fbx)",
                file_types=[".fbx"],
            )
            motion_dest_input = gr.Textbox(
                label="Motion 保存目录（不影响绑定 Skeleton）",
                value=DEFAULT_MOTION_DEST,
            )
        with gr.Accordion("高级：手动覆盖 Skeleton（决定 Motion 绑定骨骼，默认不用填）", open=False):
            manual_skeleton_asset_input = gr.Textbox(
                label="Skeleton package path 覆盖",
                placeholder="例如 /Game/Imported/Avatars/Hero_Skeleton；留空则从 Avatar 自动推断。不要填写 .Skeleton 后缀也可以。",
            )
        with gr.Row():
            import_motion_btn = gr.Button("导入 Motion 到当前 Avatar Skeleton", variant="primary")
            import_play_motion_btn = gr.Button("导入并调试播放 Motion", variant="secondary")
            play_existing_motion_btn = gr.Button("调试播放选中 Motion", variant="secondary")

        with gr.Accordion("高级资产导入（Scene / Prop / Weapon / Effect / Material / Texture）", open=False):
            gr.Markdown("材质和贴图通常会随 Avatar 自动导入；这里主要用于补充导入场景、道具、武器、特效或修复资源。Effect 本轮只做导入和列表，不做技能触发。")
            with gr.Row():
                generic_asset_file_input = gr.File(
                    label="选择高级资产文件",
                    file_types=GENERIC_FILE_TYPES,
                )
                generic_asset_type_input = gr.Dropdown(
                    label="资产类型",
                    choices=GENERIC_ASSET_TYPES,
                    value="prop",
                    interactive=True,
                )
                generic_dest_input = gr.Textbox(
                    label="UE 目标路径",
                    value=DEFAULT_PROP_DEST,
                )
            generic_skeletal_input = gr.Checkbox(
                label="Prop/Weapon FBX 作为 Skeletal Mesh 导入",
                value=False,
            )
            import_generic_asset_btn = gr.Button("导入高级资产", variant="secondary")

        output = gr.Textbox(label="导入 / 展示日志", lines=16, interactive=False)

        check_btn.click(on_check_connection, outputs=check_output)
        clear_btn.click(on_clear_presentation, outputs=check_output)
        refresh_btn.click(
            on_refresh_assets,
            outputs=[
                avatar_asset_dropdown,
                motion_asset_dropdown,
                check_output,
            ],
        )
        avatar_asset_dropdown.change(
            on_avatar_selection_change,
            inputs=[avatar_asset_dropdown],
            outputs=avatar_skeleton_display,
        )
        import_avatar_btn.click(
            on_import_avatar,
            inputs=[avatar_file_input, avatar_dest_input, skeletal_input],
            outputs=output,
        )
        present_uploaded_avatar_btn.click(
            on_present_uploaded_avatar,
            inputs=[avatar_file_input, avatar_dest_input, skeletal_input],
            outputs=output,
        )
        present_existing_avatar_btn.click(
            on_present_existing_avatar,
            inputs=[avatar_asset_dropdown],
            outputs=output,
        )
        import_motion_btn.click(
            on_import_motion,
            inputs=[
                motion_file_input,
                motion_dest_input,
                avatar_asset_dropdown,
                manual_skeleton_asset_input,
            ],
            outputs=output,
        )
        import_play_motion_btn.click(
            on_import_and_play_motion,
            inputs=[
                motion_file_input,
                motion_dest_input,
                avatar_asset_dropdown,
                manual_skeleton_asset_input,
            ],
            outputs=output,
        )
        play_existing_motion_btn.click(
            on_play_existing_motion,
            inputs=[motion_asset_dropdown, avatar_asset_dropdown],
            outputs=output,
        )
        generic_asset_type_input.change(
            on_generic_asset_type_change,
            inputs=[generic_asset_type_input],
            outputs=generic_dest_input,
        )
        import_generic_asset_btn.click(
            on_import_generic_asset,
            inputs=[generic_asset_file_input, generic_asset_type_input, generic_dest_input, generic_skeletal_input],
            outputs=output,
        )

    return app


if __name__ == "__main__":
    build_app().launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=False,
        show_api=False,
        prevent_thread_lock=False,
    )
