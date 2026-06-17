"""UE Python script builders for scene presentation."""

from __future__ import annotations

import textwrap

from .import_scripts import _build_fbx_import_script


def _build_avatar_present_script(local_path: str, dest_path: str, as_skeletal: bool) -> str:
    return _build_fbx_import_script(local_path, dest_path, as_skeletal, "FBX") + f"\nprefer_skeletal = {bool(as_skeletal)!r}\n" + textwrap.dedent("""\

        def _pick_spawnable_mesh(imported_paths, prefer_skeletal):
            loaded_assets = []
            for asset_path in imported_paths:
                asset = unreal.load_asset(asset_path)
                if asset is not None:
                    loaded_assets.append((asset_path, asset))

            preferred_type = unreal.SkeletalMesh if prefer_skeletal else unreal.StaticMesh
            fallback_type = unreal.StaticMesh if prefer_skeletal else unreal.SkeletalMesh
            preferred_name = "SkeletalMesh" if prefer_skeletal else "StaticMesh"
            fallback_name = "StaticMesh" if prefer_skeletal else "SkeletalMesh"

            for asset_path, asset in loaded_assets:
                if isinstance(asset, preferred_type):
                    return asset_path, asset, preferred_name

            for asset_path, asset in loaded_assets:
                if isinstance(asset, fallback_type):
                    unreal.log_warning(f"[OpenWL] 未找到优先类型 {preferred_name}，改用 {fallback_name}: {asset_path}")
                    return asset_path, asset, fallback_name

            imported = ", ".join(imported_paths)
            raise RuntimeError(f"导入结果里没有可放入场景的 StaticMesh 或 SkeletalMesh: {imported}")

        def _spawn_actor_from_class(actor_class, location, rotation):
            try:
                actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                actor = actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)
                if actor is not None:
                    return actor
            except Exception as exc:
                unreal.log_warning(f"[OpenWL] EditorActorSubsystem spawn 失败，尝试 EditorLevelLibrary: {exc}")

            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location, rotation)
            if actor is None:
                raise RuntimeError(f"无法 Spawn Actor: {actor_class}")
            return actor

        def _set_skeletal_mesh(component, mesh_asset):
            for method_name in ("set_skeletal_mesh_asset", "set_skeletal_mesh"):
                method = getattr(component, method_name, None)
                if method is not None:
                    try:
                        method(mesh_asset)
                        return
                    except Exception:
                        pass

            for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    component.set_editor_property(property_name, mesh_asset)
                    return
                except Exception:
                    pass

            raise RuntimeError("无法给 SkeletalMeshComponent 设置 SkeletalMesh")

        def _spawn_mesh_actor(mesh_asset, mesh_type):
            location = unreal.Vector(0.0, 0.0, 0.0)
            rotation = unreal.Rotator(0.0, 0.0, 0.0)

            if mesh_type == "SkeletalMesh":
                actor = _spawn_actor_from_class(unreal.SkeletalMeshActor, location, rotation)
                component = actor.get_editor_property("skeletal_mesh_component")
                _set_skeletal_mesh(component, mesh_asset)
            else:
                actor = _spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
                component = actor.get_editor_property("static_mesh_component")
                component.set_static_mesh(mesh_asset)

            actor.set_actor_label("OpenWL_Presentation_Actor")
            actor.set_actor_location(location, False, False)
            return actor

        def _actor_bounds(actor):
            try:
                return actor.get_actor_bounds(False)
            except Exception as exc:
                unreal.log_warning(f"[OpenWL] 获取 Actor bounds 失败，使用默认构图: {exc}")
                return unreal.Vector(0.0, 0.0, 90.0), unreal.Vector(100.0, 100.0, 100.0)

        def _spawn_camera(target_actor):
            origin, extent = _actor_bounds(target_actor)
            max_extent = max(abs(extent.x), abs(extent.y), abs(extent.z), 50.0)
            distance = max(max_extent * 3.0, 300.0)
            height = max(max_extent * 0.8, 120.0)
            target = unreal.Vector(origin.x, origin.y, origin.z + max(extent.z * 0.15, 30.0))
            camera_location = unreal.Vector(origin.x - distance, origin.y + distance, origin.z + height)
            camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, target)

            camera_class = getattr(unreal, "CineCameraActor", unreal.CameraActor)
            camera_actor = _spawn_actor_from_class(camera_class, camera_location, camera_rotation)
            camera_actor.set_actor_label("OpenWL_Presentation_Camera")

            if camera_class is getattr(unreal, "CineCameraActor", None):
                try:
                    camera_component = camera_actor.get_cine_camera_component()
                    camera_component.set_editor_property("current_focal_length", 35.0)
                except Exception as exc:
                    unreal.log_warning(f"[OpenWL] 设置 CineCamera 参数失败: {exc}")

            try:
                unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_location, camera_rotation)
            except Exception:
                pass
            return camera_actor

        mesh_asset_path, mesh_asset, mesh_type = _pick_spawnable_mesh(imported_paths, prefer_skeletal)
        actor = _spawn_mesh_actor(mesh_asset, mesh_type)
        camera = _spawn_camera(actor)
        try:
            unreal.EditorLevelLibrary.set_selected_level_actors([actor, camera])
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        result = {
            "imported_paths": imported_paths,
            "mesh_asset_path": mesh_asset_path,
            "mesh_type": mesh_type,
            "actor_label": actor.get_actor_label(),
            "actor_path": actor.get_path_name(),
            "camera_label": camera.get_actor_label(),
            "camera_path": camera.get_path_name(),
        }
        print("OPENWL_PRESENTED:" + repr(result))
    """)


def _build_present_existing_avatar_script(asset_path: str) -> str:
    return textwrap.dedent(f"""\
        import unreal
        asset_path = {asset_path!r}
        mesh_asset = unreal.load_asset(asset_path)
        if mesh_asset is None:
            raise RuntimeError(f"找不到 UE 资产: {{asset_path}}")

        if isinstance(mesh_asset, unreal.SkeletalMesh):
            mesh_type = "SkeletalMesh"
        elif isinstance(mesh_asset, unreal.StaticMesh):
            mesh_type = "StaticMesh"
        else:
            raise RuntimeError(f"选中的资产不是 StaticMesh 或 SkeletalMesh: {{asset_path}}")

        def _all_level_actors():
            try:
                return unreal.EditorLevelLibrary.get_all_level_actors()
            except Exception:
                return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()

        def _destroy_actor(candidate):
            try:
                unreal.EditorLevelLibrary.destroy_actor(candidate)
            except Exception:
                unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(candidate)

        for candidate in list(_all_level_actors()):
            try:
                label = candidate.get_actor_label()
            except Exception:
                label = ""
            if label.startswith("OpenWL_Presentation"):
                _destroy_actor(candidate)

        def _spawn_actor_from_class(actor_class, location, rotation):
            try:
                actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                actor = actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)
                if actor is not None:
                    return actor
            except Exception as exc:
                unreal.log_warning(f"[OpenWL] EditorActorSubsystem spawn 失败，尝试 EditorLevelLibrary: {{exc}}")

            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location, rotation)
            if actor is None:
                raise RuntimeError(f"无法 Spawn Actor: {{actor_class}}")
            return actor

        def _set_skeletal_mesh(component, mesh_asset):
            for method_name in ("set_skeletal_mesh_asset", "set_skeletal_mesh"):
                method = getattr(component, method_name, None)
                if method is not None:
                    try:
                        method(mesh_asset)
                    except Exception:
                        pass
            for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    component.set_editor_property(property_name, mesh_asset)
                except Exception:
                    pass
            # Sync materials from mesh asset to component
            _sync_materials_to_component(component, mesh_asset)

        def _sync_materials_to_component(component, mesh_asset):
            # Try get_editor_property("materials") first
            mesh_materials = None
            try:
                mesh_materials = mesh_asset.get_editor_property("materials")
            except Exception:
                pass
            if not mesh_materials:
                try:
                    mesh_materials = mesh_asset.materials
                except Exception:
                    pass
            if not mesh_materials:
                unreal.log_warning("[OpenWL] SkeletalMesh 没有 materials 属性")
                return
            unreal.log(f"[OpenWL] 找到 {{len(mesh_materials)}} 个材质槽")
            for i, mat_slot in enumerate(mesh_materials):
                mat_interface = None
                # Try various ways to get the material interface
                for attr in ("material_interface", "MaterialInterface", "material", "Material"):
                    try:
                        val = getattr(mat_slot, attr, None)
                        if val is not None:
                            mat_interface = val
                            break
                    except Exception:
                        pass
                if mat_interface is None:
                    try:
                        val = mat_slot.get_editor_property("material_interface")
                        if val is not None:
                            mat_interface = val
                    except Exception:
                        pass
                if mat_interface is None:
                    # mat_slot might already be the material interface itself
                    try:
                        if isinstance(mat_slot, unreal.MaterialInterface):
                            mat_interface = mat_slot
                    except Exception:
                        pass
                if mat_interface is not None:
                    try:
                        component.set_material(i, mat_interface)
                        unreal.log(f"[OpenWL] 设置材质槽 {{i}}: {{mat_interface.get_name()}}")
                    except Exception as exc:
                        unreal.log_warning(f"[OpenWL] set_material({{i}}) 失败: {{exc}}")
                    try:
                        component.set_editor_property("bEnableUpdateOverlapsOnAnimation", False)
                    except Exception:
                        pass
                else:
                    unreal.log_warning(f"[OpenWL] 材质槽 {{i}} 无法提取 MaterialInterface")

        location = unreal.Vector(0.0, 0.0, 0.0)
        rotation = unreal.Rotator(0.0, 0.0, 0.0)
        if mesh_type == "SkeletalMesh":
            actor = _spawn_actor_from_class(unreal.SkeletalMeshActor, location, rotation)
            component = actor.get_editor_property("skeletal_mesh_component")
            _set_skeletal_mesh(component, mesh_asset)
        else:
            actor = _spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
            component = actor.get_editor_property("static_mesh_component")
            component.set_static_mesh(mesh_asset)

        actor.set_actor_label("OpenWL_Presentation_Actor")
        actor.set_actor_location(location, False, False)

        try:
            origin, extent = actor.get_actor_bounds(False)
        except Exception:
            origin, extent = unreal.Vector(0.0, 0.0, 90.0), unreal.Vector(100.0, 100.0, 100.0)
        max_extent = max(abs(extent.x), abs(extent.y), abs(extent.z), 50.0)
        distance = max(max_extent * 3.0, 300.0)
        height = max(max_extent * 0.8, 120.0)
        target = unreal.Vector(origin.x, origin.y, origin.z + max(extent.z * 0.15, 30.0))
        camera_location = unreal.Vector(origin.x - distance, origin.y + distance, origin.z + height)
        camera_rotation = unreal.MathLibrary.find_look_at_rotation(camera_location, target)
        camera_class = getattr(unreal, "CineCameraActor", unreal.CameraActor)
        camera_actor = _spawn_actor_from_class(camera_class, camera_location, camera_rotation)
        camera_actor.set_actor_label("OpenWL_Presentation_Camera")
        try:
            unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_location, camera_rotation)
            unreal.EditorLevelLibrary.set_selected_level_actors([actor, camera_actor])
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        print("OPENWL_PRESENTED_EXISTING:" + repr({{"asset_path": asset_path, "mesh_type": mesh_type, "actor_path": actor.get_path_name()}}))
    """)


def _build_present_playable_avatar_script(
    avatar_asset_path: str,
    idle_animation_path: str = "",
    move_animation_path: str = "",
    playable_blueprint_path: str = "/Script/OpenWLPlayable.OpenWLPlayableCharacter",
    actor_label: str = "OpenWL_Playable_Character",
    mesh_forward_axis: str = "auto",
    mesh_relative_yaw=None,
    align_to_ground: bool = True,
    ground_z: float = 0.0,
    destroy_existing: bool = True,
    walk_speed=None,
    run_speed=None,
) -> str:
    return textwrap.dedent(f"""\
        import unreal

        avatar_asset_path = {avatar_asset_path!r}
        idle_animation_path = {idle_animation_path!r}
        move_animation_path = {move_animation_path!r}
        playable_blueprint_path = {playable_blueprint_path!r}
        actor_label = {actor_label!r}
        mesh_forward_axis = {mesh_forward_axis!r}
        requested_mesh_relative_yaw = {mesh_relative_yaw!r}
        align_to_ground = {bool(align_to_ground)!r}
        ground_z = {float(ground_z)!r}
        destroy_existing = {bool(destroy_existing)!r}
        walk_speed = {walk_speed!r}
        run_speed = {run_speed!r}
        warnings = []

        def _load_asset(path, label, required=True):
            if not path:
                if required:
                    raise RuntimeError("缺少 " + label + " 资产路径")
                return None
            asset = unreal.load_asset(path)
            if asset is None:
                raise RuntimeError("找不到 " + label + ": " + path)
            return asset

        def _all_level_actors():
            try:
                return unreal.EditorLevelLibrary.get_all_level_actors()
            except Exception:
                return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()

        def _destroy_actor(candidate):
            try:
                unreal.EditorLevelLibrary.destroy_actor(candidate)
            except Exception:
                unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(candidate)

        def _spawn_actor_from_class(actor_class, location, rotation):
            try:
                actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                actor = actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)
                if actor is not None:
                    return actor
            except Exception as exc:
                unreal.log_warning(f"[OpenWL] EditorActorSubsystem spawn 失败，尝试 EditorLevelLibrary: {{exc}}")
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location, rotation)
            if actor is None:
                raise RuntimeError(f"无法 Spawn Actor: {{actor_class}}")
            return actor

        def _make_rotator(pitch=0.0, yaw=0.0, roll=0.0):
            try:
                return unreal.Rotator(pitch=float(pitch), yaw=float(yaw), roll=float(roll))
            except Exception:
                rotator = unreal.Rotator()
                for name, value in (("pitch", pitch), ("yaw", yaw), ("roll", roll)):
                    try:
                        rotator.set_editor_property(name, float(value))
                    except Exception:
                        try:
                            setattr(rotator, name, float(value))
                        except Exception:
                            pass
                return rotator

        def _vector_dict(vector):
            if vector is None:
                return None
            return {{"x": float(vector.x), "y": float(vector.y), "z": float(vector.z)}}

        def _rotator_dict(rotator):
            if rotator is None:
                return None
            return {{"pitch": float(rotator.pitch), "yaw": float(rotator.yaw), "roll": float(rotator.roll)}}

        def _load_playable_class(class_or_blueprint_path):
            generated_class = None
            if class_or_blueprint_path.startswith("/Script/"):
                try:
                    generated_class = unreal.load_class(None, class_or_blueprint_path)
                except Exception:
                    generated_class = None
                if generated_class is None:
                    module_and_class = class_or_blueprint_path[len("/Script/"):]
                    class_name = module_and_class.rsplit(".", 1)[-1]
                    generated_class = getattr(unreal, class_name, None)
                if generated_class is None or not isinstance(generated_class, unreal.Class):
                    raise RuntimeError("找不到 C++ 可玩角色类: " + class_or_blueprint_path + "。请确认 OpenWLPlayable 插件已复制到 UE 项目并编译启用。")
                return generated_class

            blueprint = _load_asset(class_or_blueprint_path, "Playable Blueprint")
            class_path = class_or_blueprint_path + "." + class_or_blueprint_path.rsplit("/", 1)[-1] + "_C"
            try:
                generated_class = unreal.load_class(None, class_path)
            except Exception:
                generated_class = None
            if generated_class is None:
                try:
                    generated_class = blueprint.get_editor_property("generated_class")
                except Exception:
                    generated_class = None
            if callable(generated_class) and not isinstance(generated_class, unreal.Class):
                try:
                    generated_class = generated_class()
                except Exception:
                    pass
            if generated_class is None or not isinstance(generated_class, unreal.Class):
                raise RuntimeError(f"Blueprint 没有可用 generated class: {{class_or_blueprint_path}} / {{class_path}}")
            return generated_class

        def _get_skeletal_component(candidate):
            for property_name in ("mesh", "skeletal_mesh_component"):
                try:
                    component = candidate.get_editor_property(property_name)
                    if component is not None:
                        return component
                except Exception:
                    pass
            try:
                return candidate.get_component_by_class(unreal.SkeletalMeshComponent)
            except Exception:
                return None

        def _get_capsule_component(candidate):
            try:
                return candidate.get_component_by_class(unreal.CapsuleComponent)
            except Exception:
                return None

        def _get_character_movement(candidate):
            try:
                return candidate.get_component_by_class(unreal.CharacterMovementComponent)
            except Exception:
                return None

        def _set_skeletal_mesh(component, mesh_asset):
            for method_name in ("set_skeletal_mesh_asset", "set_skeletal_mesh"):
                method = getattr(component, method_name, None)
                if method is not None:
                    try:
                        method(mesh_asset)
                        return
                    except Exception:
                        pass
            for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
                try:
                    component.set_editor_property(property_name, mesh_asset)
                    return
                except Exception:
                    pass
            raise RuntimeError("无法给 SkeletalMeshComponent 设置 SkeletalMesh")

        def _sync_materials_to_component(component, mesh_asset):
            mesh_materials = None
            try:
                mesh_materials = mesh_asset.get_editor_property("materials")
            except Exception:
                pass
            if not mesh_materials:
                try:
                    mesh_materials = mesh_asset.materials
                except Exception:
                    pass
            if not mesh_materials:
                warnings.append("Avatar SkeletalMesh 没有可同步的 materials")
                return
            for i, mat_slot in enumerate(mesh_materials):
                mat_interface = None
                for attr in ("material_interface", "MaterialInterface", "material", "Material"):
                    try:
                        val = getattr(mat_slot, attr, None)
                        if val is not None:
                            mat_interface = val
                            break
                    except Exception:
                        pass
                if mat_interface is None:
                    try:
                        mat_interface = mat_slot.get_editor_property("material_interface")
                    except Exception:
                        pass
                if mat_interface is None:
                    try:
                        if isinstance(mat_slot, unreal.MaterialInterface):
                            mat_interface = mat_slot
                    except Exception:
                        pass
                if mat_interface is not None:
                    try:
                        component.set_material(i, mat_interface)
                    except Exception as exc:
                        warnings.append(f"材质槽 {{i}} 设置失败: {{exc}}")

        def _try_set_property(obj, names, value):
            for name in names:
                try:
                    obj.set_editor_property(name, value)
                    return True
                except Exception:
                    pass
            return False

        def _set_auto_possess_player0(candidate):
            for value in (getattr(unreal.AutoReceiveInput, "PLAYER0", None), getattr(unreal.AutoReceiveInput, "PLAYER_0", None)):
                if value is None:
                    continue
                try:
                    candidate.set_editor_property("auto_possess_player", value)
                    return True
                except Exception:
                    pass
            warnings.append("无法自动设置 Auto Possess Player = Player 0，请在关卡实例上手动设置")
            return False

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
            return str(skeleton.get_path_name()).split(".", 1)[0]

        def _validate_animation_skeleton(animation_asset, avatar_mesh, label):
            if animation_asset is None:
                return
            if not isinstance(animation_asset, unreal.AnimSequence):
                raise RuntimeError(label + " 不是 AnimSequence: " + animation_asset.get_path_name())
            motion_skeleton = _skeleton_path(animation_asset)
            avatar_skeleton = _skeleton_path(avatar_mesh)
            if motion_skeleton and avatar_skeleton and motion_skeleton != avatar_skeleton:
                raise RuntimeError(
                    label + " Skeleton 与 Avatar Skeleton 不匹配。 Motion Skeleton: "
                    + motion_skeleton
                    + " Avatar Skeleton: "
                    + avatar_skeleton
                )

        def _is_actor_from_class(candidate, actor_class):
            try:
                if candidate.get_class() == actor_class:
                    return True
            except Exception:
                pass
            try:
                return candidate.get_class().get_path_name() == actor_class.get_path_name()
            except Exception:
                return False

        def _set_single_node_animation(component, animation_asset, looping=True):
            if animation_asset is None:
                return False
            try:
                component.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            except Exception:
                pass
            try:
                component.set_animation(animation_asset)
                component.set_editor_property("looping", bool(looping))
                component.play(True)
                return True
            except Exception:
                pass
            try:
                component.play_animation(animation_asset, bool(looping))
                return True
            except Exception:
                return False

        def _resolve_mesh_relative_yaw(mesh_asset):
            if requested_mesh_relative_yaw is not None:
                return float(requested_mesh_relative_yaw)
            axis_yaws = {{"+X": 0.0, "+Y": -90.0, "-X": 180.0, "-Y": 90.0}}
            if mesh_forward_axis in axis_yaws:
                return axis_yaws[mesh_forward_axis]
            for key in ("OpenWL_MeshRelativeYaw", "openwl_mesh_relative_yaw"):
                try:
                    value = mesh_asset.get_metadata_tag(key)
                    if value not in (None, ""):
                        return float(value)
                except Exception:
                    pass
            for key in ("OpenWL_ForwardAxis", "openwl_forward_axis"):
                try:
                    value = mesh_asset.get_metadata_tag(key)
                    if value in axis_yaws:
                        return axis_yaws[value]
                except Exception:
                    pass
            return 0.0

        def _get_relative_location(component):
            try:
                return component.get_relative_location()
            except Exception:
                pass
            try:
                return component.get_editor_property("relative_location")
            except Exception:
                return unreal.Vector(0.0, 0.0, 0.0)

        def _set_relative_location(component, location):
            try:
                component.set_relative_location(location, False, None, False)
                return
            except Exception:
                pass
            try:
                component.set_editor_property("relative_location", location)
                return
            except Exception:
                pass
            warnings.append("无法设置 Mesh relative_location")

        def _set_relative_rotation(component, rotation):
            try:
                component.set_relative_rotation(rotation, False, None, False)
                return
            except Exception:
                pass
            try:
                component.set_editor_property("relative_rotation", rotation)
                return
            except Exception:
                pass
            warnings.append("无法设置 Mesh relative_rotation")

        def _component_bounds(component):
            try:
                bounds = component.get_editor_property("bounds")
                origin = bounds.get_editor_property("origin")
                extent = bounds.get_editor_property("box_extent")
                return origin, extent
            except Exception:
                pass
            try:
                bounds = component.bounds
                return bounds.origin, bounds.box_extent
            except Exception:
                pass
            try:
                bounds = component.get_component_bounds()
                if isinstance(bounds, (tuple, list)) and len(bounds) >= 2:
                    return bounds[0], bounds[1]
            except Exception:
                pass
            return None, None

        def _capsule_half_height(capsule):
            if capsule is None:
                return 88.0
            for method_name in ("get_unscaled_capsule_half_height", "get_scaled_capsule_half_height"):
                method = getattr(capsule, method_name, None)
                if method is not None:
                    try:
                        return float(method())
                    except Exception:
                        pass
            try:
                return float(capsule.get_editor_property("capsule_half_height"))
            except Exception:
                return 88.0

        def _align_character_to_ground(candidate, component):
            capsule = _get_capsule_component(candidate)
            half_height = _capsule_half_height(capsule)
            candidate.set_actor_location(unreal.Vector(0.0, 0.0, ground_z + half_height), False, False)
            origin, extent = _component_bounds(component)
            before_min_z = None
            after_min_z = None
            if origin is not None and extent is not None:
                before_min_z = float(origin.z - extent.z)
                relative_location = _get_relative_location(component)
                new_relative_location = unreal.Vector(
                    relative_location.x,
                    relative_location.y,
                    relative_location.z + (ground_z - before_min_z),
                )
                _set_relative_location(component, new_relative_location)
                try:
                    component.update_bounds()
                except Exception:
                    pass
                origin_after, extent_after = _component_bounds(component)
                if origin_after is not None and extent_after is not None:
                    after_min_z = float(origin_after.z - extent_after.z)
            else:
                warnings.append("无法读取 Mesh bounds，跳过自适应落地校准")
            return half_height, before_min_z, after_min_z

        generated_class = _load_playable_class(playable_blueprint_path)
        avatar_mesh = _load_asset(avatar_asset_path, "Avatar SkeletalMesh")
        if not isinstance(avatar_mesh, unreal.SkeletalMesh):
            raise RuntimeError("可玩角色只支持 SkeletalMesh。StaticMesh 请使用旧的调试展示。资产: " + avatar_asset_path)
        idle_animation = _load_asset(idle_animation_path, "Idle Animation", required=False)
        move_animation = _load_asset(move_animation_path, "Move Animation", required=False)
        _validate_animation_skeleton(idle_animation, avatar_mesh, "Idle Animation")
        _validate_animation_skeleton(move_animation, avatar_mesh, "Move Animation")

        if destroy_existing:
            for candidate in list(_all_level_actors()):
                try:
                    label = candidate.get_actor_label()
                except Exception:
                    label = ""
                if label == actor_label or label.startswith("OpenWL_Presentation") or _is_actor_from_class(candidate, generated_class):
                    _destroy_actor(candidate)

        actor = _spawn_actor_from_class(generated_class, unreal.Vector(0.0, 0.0, 0.0), _make_rotator(0.0, 0.0, 0.0))
        actor.set_actor_label(actor_label)
        _set_auto_possess_player0(actor)

        component = _get_skeletal_component(actor)
        if component is None:
            raise RuntimeError("Playable Blueprint 里找不到 SkeletalMeshComponent / Mesh")
        _set_skeletal_mesh(component, avatar_mesh)
        _sync_materials_to_component(component, avatar_mesh)

        mesh_yaw = _resolve_mesh_relative_yaw(avatar_mesh)
        _set_relative_rotation(component, _make_rotator(0.0, mesh_yaw, 0.0))

        capsule_half_height = None
        mesh_bounds_min_z_before = None
        mesh_bounds_min_z_after = None
        if align_to_ground:
            capsule_half_height, mesh_bounds_min_z_before, mesh_bounds_min_z_after = _align_character_to_ground(actor, component)

        if idle_animation is not None:
            if not _try_set_property(actor, ("IdleAnimation", "idle_animation", "Idle Motion", "idle_motion"), idle_animation):
                warnings.append("Blueprint 上没有 IdleAnimation 变量；Idle 动作未自动绑定")
        if move_animation is not None:
            if not _try_set_property(actor, ("MoveAnimation", "move_animation", "Move Motion", "move_motion"), move_animation):
                warnings.append("Blueprint 上没有 MoveAnimation 变量；Move 动作未自动绑定")
            _try_set_property(actor, ("RunAnimation", "run_animation", "Run Motion", "run_motion"), move_animation)
        if idle_animation is not None:
            try:
                animation_mode = component.get_editor_property("animation_mode")
            except Exception:
                animation_mode = None
            if str(animation_mode).endswith("ANIMATION_BLUEPRINT") or "ANIMATION_BLUEPRINT" in str(animation_mode):
                warnings.append("检测到 Mesh 使用 Animation Blueprint；Idle/Move 需要 AnimBP/蓝图变量驱动，后端不会覆盖为单节点动画")
            elif _set_single_node_animation(component, idle_animation, True):
                warnings.append("已把 Idle 动作临时设置为单节点循环。要移动时自动切 Move，请在 AnimBP 或 Character 蓝图里用 Speed 驱动 Idle/Move")
            else:
                warnings.append("Idle 单节点动画设置失败；请检查蓝图 Mesh 动画模式")
        if walk_speed is not None:
            if not _try_set_property(actor, ("WalkSpeed", "walk_speed"), float(walk_speed)):
                warnings.append("Blueprint 上没有 WalkSpeed 变量；尝试只设置 CharacterMovement.MaxWalkSpeed")
        if run_speed is not None:
            if not _try_set_property(actor, ("RunSpeed", "run_speed"), float(run_speed)):
                warnings.append("Blueprint 上没有 RunSpeed 变量；请在 Sprint 蓝图逻辑中手动使用 RunSpeed")

        movement = _get_character_movement(actor)
        if movement is not None:
            if walk_speed is not None:
                try:
                    movement.set_editor_property("max_walk_speed", float(walk_speed))
                except Exception as exc:
                    warnings.append("设置 CharacterMovement.MaxWalkSpeed 失败: " + str(exc))
            try:
                movement.set_editor_property("orient_rotation_to_movement", True)
            except Exception:
                pass
        else:
            warnings.append("找不到 CharacterMovementComponent；请确认 Blueprint 父类是 Character")

        try:
            unreal.EditorLevelLibrary.set_selected_level_actors([actor])
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass

        actor_location = actor.get_actor_location()
        actor_rotation = actor.get_actor_rotation()
        mesh_location = _get_relative_location(component)
        try:
            mesh_rotation = component.get_relative_rotation()
        except Exception:
            try:
                mesh_rotation = component.get_editor_property("relative_rotation")
            except Exception:
                mesh_rotation = None
        result = {{
            "ok": True,
            "actor_label": actor.get_actor_label(),
            "actor_path": actor.get_path_name(),
            "blueprint_path": playable_blueprint_path,
            "avatar_asset_path": avatar_asset_path,
            "idle_animation_path": idle_animation_path,
            "move_animation_path": move_animation_path,
            "mesh_forward_axis": mesh_forward_axis,
            "mesh_relative_yaw": mesh_yaw,
            "mesh_relative_location": _vector_dict(mesh_location),
            "mesh_relative_rotation": _rotator_dict(mesh_rotation),
            "actor_location": _vector_dict(actor_location),
            "actor_rotation": _rotator_dict(actor_rotation),
            "capsule_half_height": capsule_half_height,
            "mesh_bounds_min_z_before": mesh_bounds_min_z_before,
            "mesh_bounds_min_z_after": mesh_bounds_min_z_after,
            "walk_speed": walk_speed,
            "run_speed": run_speed,
            "warnings": warnings,
        }}
    """)


def _build_clear_presentation_script() -> str:
    return textwrap.dedent("""\
        import unreal

        labels = (
            "OpenWL_Presentation_Actor",
            "OpenWL_Presentation_Camera",
            "OpenWL_Presentation_Animated_Sequence",
            "OpenWL_Playable_Character",
        )
        prefixes = ("OpenWL_Presentation", "OpenWL_Playable")

        try:
            actors = unreal.EditorLevelLibrary.get_all_level_actors()
        except Exception:
            actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()

        removed = []
        for actor in list(actors):
            try:
                label = actor.get_actor_label()
            except Exception:
                label = ""
            if label in labels or any(label.startswith(prefix) for prefix in prefixes):
                removed.append({"label": label, "path": actor.get_path_name()})
                try:
                    unreal.EditorLevelLibrary.destroy_actor(actor)
                except Exception:
                    unreal.get_editor_subsystem(unreal.EditorActorSubsystem).destroy_actor(actor)

        try:
            unreal.EditorLevelLibrary.set_selected_level_actors([])
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass

        result = {"removed": removed, "count": len(removed)}
        print("OPENWL_CLEAR_PRESENTATION:" + repr(result))
    """)
