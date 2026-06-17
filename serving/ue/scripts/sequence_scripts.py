"""UE Python script builders for motion and sequence playback."""

from __future__ import annotations

import textwrap

from serving.ue.config import DEFAULT_SEQUENCE_DEST


def _build_resolve_avatar_skeleton_script(avatar_asset_path: str) -> str:
    return textwrap.dedent(f"""\
        import unreal
        avatar_asset_path = {avatar_asset_path.strip()!r}
        asset = unreal.load_asset(avatar_asset_path)
        if asset is None:
            raise RuntimeError(f"找不到 Avatar 资产: {{avatar_asset_path}}")
        if not isinstance(asset, unreal.SkeletalMesh):
            result = ""
        else:
            skeleton = None
            try:
                skeleton = asset.get_editor_property("skeleton")
            except Exception:
                skeleton = getattr(asset, "skeleton", None)
            result = skeleton.get_path_name() if skeleton is not None else ""
    """)


def _build_play_motion_script(motion_asset_path: str, avatar_asset_path: str, actor_label: str) -> str:
    return textwrap.dedent(f"""\
        import unreal
        motion_asset_path = {motion_asset_path!r}
        avatar_asset_path = {avatar_asset_path!r}
        actor_label = {actor_label!r}
        sequence_dest_path = {DEFAULT_SEQUENCE_DEST!r}
        animation_asset = unreal.load_asset(motion_asset_path)
        if animation_asset is None:
            raise RuntimeError("找不到 Motion 资产: " + motion_asset_path)
        if not isinstance(animation_asset, unreal.AnimSequence):
            raise RuntimeError("选中的 Motion 不是 AnimSequence: " + motion_asset_path)

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

        avatar_asset = None
        if avatar_asset_path:
            avatar_asset = unreal.load_asset(avatar_asset_path)
            if avatar_asset is None:
                raise RuntimeError("找不到 Avatar 资产: " + avatar_asset_path)
            if not isinstance(avatar_asset, unreal.SkeletalMesh):
                raise RuntimeError("播放 Motion 需要 SkeletalMesh Avatar，StaticMesh 不能播放骨骼动画")
            animation_skeleton_path = _skeleton_path(animation_asset)
            avatar_skeleton_path = _skeleton_path(avatar_asset)
            if not animation_skeleton_path:
                raise RuntimeError("选中的 Motion 没有绑定 Skeleton，请用 Avatar 对应 Skeleton 重新导入 Motion")
            if not avatar_skeleton_path:
                raise RuntimeError("选中的 Avatar 没有 Skeleton，不能播放骨骼动画")
            if animation_skeleton_path != avatar_skeleton_path:
                raise RuntimeError(
                    "Motion Skeleton 与 Avatar Skeleton 不匹配。"
                    + " Motion Skeleton: " + animation_skeleton_path
                    + " Avatar Skeleton: " + avatar_skeleton_path
                    + "。请用这个 Avatar 的 Skeleton 重新导入 Motion，或选择同一 Skeleton 的 Motion。"
                )

        def _spawn_actor_from_class(actor_class, location, rotation):
            try:
                actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
                actor = actor_subsystem.spawn_actor_from_class(actor_class, location, rotation)
                if actor is not None:
                    return actor
            except Exception as exc:
                unreal.log_warning("[OpenWL] EditorActorSubsystem spawn 失败，尝试 EditorLevelLibrary: " + str(exc))
            actor = unreal.EditorLevelLibrary.spawn_actor_from_class(actor_class, location, rotation)
            if actor is None:
                raise RuntimeError("无法 Spawn Actor: " + str(actor_class))
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
            _sync_materials_to_component(component, mesh_asset)

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
                        val = mat_slot.get_editor_property("material_interface")
                        if val is not None:
                            mat_interface = val
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
                    except Exception:
                        pass

        def _get_skeletal_component(candidate):
            try:
                component = candidate.get_editor_property("skeletal_mesh_component")
                if component is not None:
                    return component
            except Exception:
                pass
            try:
                return candidate.get_component_by_class(unreal.SkeletalMeshComponent)
            except Exception:
                return None

        def _all_level_actors():
            try:
                return unreal.EditorLevelLibrary.get_all_level_actors()
            except Exception:
                return unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()

        def _find_actor_by_label(label):
            for candidate in _all_level_actors():
                try:
                    if candidate.get_actor_label() == label:
                        return candidate
                except Exception:
                    pass
            return None

        def _actor_bounds(target_actor):
            try:
                return target_actor.get_actor_bounds(False)
            except Exception as exc:
                unreal.log_warning("[OpenWL] 获取 Actor bounds 失败，使用默认构图: " + str(exc))
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
                    unreal.log_warning("[OpenWL] 设置 CineCamera 参数失败: " + str(exc))
            try:
                unreal.EditorLevelLibrary.set_level_viewport_camera_info(camera_location, camera_rotation)
            except Exception:
                pass
            return camera_actor

        def _sanitize_asset_name(value):
            cleaned = []
            for char in str(value):
                if char.isalnum() or char == "_":
                    cleaned.append(char)
                else:
                    cleaned.append("_")
            return "".join(cleaned).strip("_") or "OpenWL_Motion_Preview"

        def _unique_sequence_name():
            unreal.EditorAssetLibrary.make_directory(sequence_dest_path)
            base_name = _sanitize_asset_name("OpenWL_Motion_" + motion_asset_path.split("/")[-1].split(".")[-1])
            candidate = base_name
            index = 1
            while unreal.EditorAssetLibrary.does_asset_exist(sequence_dest_path + "/" + candidate):
                candidate = base_name + "_" + str(index).zfill(2)
                index += 1
            return candidate

        def _set_section_range(section, start_frame, end_frame):
            try:
                section.set_range(start_frame, end_frame)
                return
            except Exception:
                pass
            try:
                section.set_start_frame_seconds(float(start_frame) / 30.0)
                section.set_end_frame_seconds(float(end_frame) / 30.0)
            except Exception as exc:
                unreal.log_warning("[OpenWL] 设置 Sequencer section 范围失败: " + str(exc))

        def _try_set_editor_property(obj, property_names, value):
            for property_name in property_names:
                try:
                    obj.set_editor_property(property_name, value)
                    return True
                except Exception:
                    pass
            return False

        def _animation_duration_frames(animation):
            duration_seconds = 5.0
            for property_name in ("sequence_length", "duration"):
                try:
                    duration_seconds = float(animation.get_editor_property(property_name))
                    break
                except Exception:
                    pass
            else:
                try:
                    duration_seconds = float(animation.get_play_length())
                except Exception:
                    pass
            return max(int(round(duration_seconds * 30.0)), 1)

        def _set_actor_animation(component, animation):
            try:
                component.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            except Exception as exc:
                unreal.log_warning("[OpenWL] 设置 animation_mode 失败: " + str(exc))
            if not _try_set_editor_property(component, ("animation", "animation_asset"), animation):
                try:
                    component.set_animation(animation)
                except Exception as exc:
                    unreal.log_warning("[OpenWL] 设置 SkeletalMeshComponent 动画失败: " + str(exc))
            try:
                component.set_editor_property("playing", True)
            except Exception:
                pass
            try:
                component.set_editor_property("looping", True)
            except Exception:
                pass
            try:
                component.play_animation(animation, True)
            except Exception:
                try:
                    component.play(True)
                except Exception:
                    pass

        def _set_camera_cut_binding(sequence, section, camera_binding):
            try:
                binding_id = sequence.make_binding_id(camera_binding, unreal.MovieSceneObjectBindingSpace.LOCAL)
                section.set_camera_binding_id(binding_id)
                return
            except Exception:
                pass
            try:
                section.set_camera_binding_id(camera_binding.get_binding_id())
                return
            except Exception:
                pass
            binding_id = unreal.MovieSceneObjectBindingID()
            binding_id.set_editor_property("guid", camera_binding.get_id())
            section.set_editor_property("camera_binding_id", binding_id)

        def _read_param_animation(params):
            for property_name in ("animation", "Animation"):
                try:
                    return params.get_editor_property(property_name)
                except Exception:
                    pass
            return None

        def _assign_animation_to_section(animation_section, animation):
            params = None
            try:
                params = animation_section.get_editor_property("params")
            except Exception:
                pass
            if params is None:
                params = unreal.MovieSceneSkeletalAnimationParams()

            if not _try_set_editor_property(params, ("animation", "Animation"), animation):
                raise RuntimeError("无法设置 MovieSceneSkeletalAnimationParams.animation")
            _try_set_editor_property(params, ("start_frame_offset", "StartFrameOffset"), 0)
            _try_set_editor_property(params, ("end_frame_offset", "EndFrameOffset"), 0)
            _try_set_editor_property(params, ("play_rate", "PlayRate"), 1.0)
            _try_set_editor_property(params, ("reverse", "Reverse"), False)

            if not _try_set_editor_property(animation_section, ("params", "Params"), params):
                raise RuntimeError("无法设置 Skeletal Animation Section params")
            _try_set_editor_property(animation_section, ("is_active", "IsActive"), True)
            _try_set_editor_property(animation_section, ("is_locked", "IsLocked"), False)

            assigned = None
            try:
                assigned = _read_param_animation(animation_section.get_editor_property("params"))
            except Exception:
                assigned = _read_param_animation(params)
            if assigned is None:
                raise RuntimeError("Skeletal Animation Section 已创建，但没有写入 AnimSequence")
            return assigned.get_path_name()

        def _binding_id(sequence, binding):
            try:
                return sequence.make_binding_id(binding, unreal.MovieSceneObjectBindingSpace.LOCAL)
            except Exception:
                binding_id = unreal.MovieSceneObjectBindingID()
                binding_id.set_editor_property("guid", binding.get_id())
                return binding_id

        def _create_sequence(camera_actor, skeletal_actor, skeletal_component, animation):
            duration_frames = _animation_duration_frames(animation)
            asset_name = _unique_sequence_name()
            sequence = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                asset_name,
                sequence_dest_path,
                unreal.LevelSequence,
                unreal.LevelSequenceFactoryNew(),
            )
            if sequence is None:
                raise RuntimeError("无法创建 Level Sequence: " + sequence_dest_path + "/" + asset_name)
            try:
                sequence.set_display_rate(unreal.FrameRate(30, 1))
            except Exception:
                pass
            try:
                sequence.set_playback_start(0)
                sequence.set_playback_end(duration_frames)
            except Exception:
                pass

            actor_binding = sequence.add_possessable(skeletal_actor)
            component_binding = sequence.add_possessable(skeletal_component)
            try:
                component_binding.set_parent(actor_binding)
            except Exception as exc:
                unreal.log_warning("[OpenWL] 设置 SkeletalMeshComponent binding parent 失败: " + str(exc))
            try:
                component_binding.set_display_name("SkeletalMeshComponent")
            except Exception:
                pass

            animation_track = component_binding.add_track(unreal.MovieSceneSkeletalAnimationTrack)
            try:
                animation_track.set_display_name("OpenWL Motion")
            except Exception:
                pass
            animation_section = animation_track.add_section()
            _set_section_range(animation_section, 0, duration_frames)
            assigned_animation_path = _assign_animation_to_section(animation_section, animation)

            camera_binding = sequence.add_possessable(camera_actor)
            camera_cut_track = sequence.add_master_track(unreal.MovieSceneCameraCutTrack)
            camera_cut_section = camera_cut_track.add_section()
            _set_section_range(camera_cut_section, 0, duration_frames)
            _set_camera_cut_binding(sequence, camera_cut_section, camera_binding)

            sequence_path = sequence.get_path_name()
            unreal.EditorAssetLibrary.save_asset(sequence_path)
            return sequence, sequence_path, actor_binding, component_binding, camera_binding, duration_frames, assigned_animation_path

        def _spawn_sequence_actor(sequence, actor_binding, skeletal_actor, component_binding, camera_binding, camera_actor):
            sequence_actor = _spawn_actor_from_class(unreal.LevelSequenceActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
            sequence_actor.set_actor_label("OpenWL_Presentation_Animated_Sequence")
            try:
                sequence_actor.set_sequence(sequence)
            except Exception:
                sequence_actor.set_editor_property("level_sequence_asset", sequence)
            skeletal_component = _get_skeletal_component(skeletal_actor)
            binding_targets = [(actor_binding, skeletal_actor), (camera_binding, camera_actor)]
            if skeletal_component is not None:
                binding_targets.append((component_binding, skeletal_component))
            for binding, bound_actor in binding_targets:
                try:
                    sequence_actor.set_binding(_binding_id(sequence, binding), [bound_actor], False)
                except Exception:
                    try:
                        sequence_actor.set_binding(binding.get_binding_id(), [bound_actor], False)
                    except Exception as exc:
                        unreal.log_warning("[OpenWL] 设置 LevelSequenceActor binding override 失败: " + str(exc))
            try:
                unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
                unreal.LevelSequenceEditorBlueprintLibrary.refresh_current_level_sequence()
            except Exception as exc:
                unreal.log_warning("[OpenWL] 打开 Sequencer 失败: " + str(exc))
            try:
                sequence_player = sequence_actor.get_sequence_player()
                sequence_player.set_frame_range(0, max(_animation_duration_frames(animation_asset), 1))
                sequence_player.set_playback_position_seconds(0.0)
                try:
                    sequence_player.set_looping(True)
                except Exception:
                    pass
                try:
                    sequence_player.play_looping(-1)
                except Exception:
                    try:
                        sequence_player.play_looping()
                    except Exception:
                        sequence_player.play()
            except Exception:
                try:
                    sequence_actor.sequence_player.play()
                except Exception:
                    pass
            return sequence_actor

        actor = _find_actor_by_label(actor_label)
        component = _get_skeletal_component(actor) if actor is not None else None
        if component is None:
            if avatar_asset is None:
                raise RuntimeError("当前场景没有可播放的 SkeletalMeshActor，请先展示一个 SkeletalMesh Avatar 或选择 Avatar 资产")
            actor = _spawn_actor_from_class(unreal.SkeletalMeshActor, unreal.Vector(0.0, 0.0, 0.0), unreal.Rotator(0.0, 0.0, 0.0))
            actor.set_actor_label(actor_label)
            component = _get_skeletal_component(actor)
        if component is None:
            raise RuntimeError("当前展示 Actor 不是 SkeletalMeshActor，不能播放骨骼动画")
        if avatar_asset is not None:
            _set_skeletal_mesh(component, avatar_asset)
        try:
            component.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        except Exception:
            pass

        camera = _spawn_camera(actor)
        sequence, sequence_path, actor_binding, component_binding, camera_binding, duration_frames, assigned_animation_path = _create_sequence(camera, actor, component, animation_asset)
        sequence_actor = _spawn_sequence_actor(sequence, actor_binding, actor, component_binding, camera_binding, camera)
        try:
            unreal.EditorLevelLibrary.set_selected_level_actors([actor, camera, sequence_actor])
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass

        motion_skeleton = _skeleton_path(animation_asset)
        avatar_skeleton = _skeleton_path(avatar_asset) if avatar_asset is not None else ""
        result = dict(
            motion_asset_path=motion_asset_path,
            avatar_asset_path=avatar_asset_path,
            motion_skeleton=motion_skeleton,
            avatar_skeleton=avatar_skeleton,
            skeletons_match=(motion_skeleton == avatar_skeleton) if (motion_skeleton and avatar_skeleton) else None,
            actor_label=actor.get_actor_label(),
            actor_path=actor.get_path_name(),
            component_path=component.get_path_name(),
            component_binding_id=str(component_binding.get_id()),
            camera_label=camera.get_actor_label(),
            camera_path=camera.get_path_name(),
            sequence_actor_label=sequence_actor.get_actor_label(),
            sequence_actor_path=sequence_actor.get_path_name(),
            sequence_path=sequence_path,
            assigned_animation_path=assigned_animation_path,
            duration_frames=duration_frames,
        )
        openwl_play_motion_result = result
        unreal.log("[OpenWL] Motion Sequencer presentation ready: " + repr(result))
        print("OPENWL_PLAY_MOTION_SEQUENCE:" + repr(result))
    """)
