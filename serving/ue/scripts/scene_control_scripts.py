"""UE Python script builders for interactive scene controls."""

from __future__ import annotations

import textwrap


def _scene_control_helpers_script(actor_label: str) -> str:
    return textwrap.dedent(f"""\
        import unreal

        actor_label = {actor_label!r}

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

        def _make_rotator(pitch=0.0, yaw=0.0, roll=0.0):
            # Use keyword args first. Positional args are easy to misread across UE Python versions.
            try:
                return unreal.Rotator(pitch=float(pitch), yaw=float(yaw), roll=float(roll))
            except Exception:
                pass
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

        def _transform_result(actor):
            location = actor.get_actor_location()
            rotation = actor.get_actor_rotation()
            return {{
                "ok": True,
                "actor_label": actor.get_actor_label(),
                "actor_path": actor.get_path_name(),
                "location": {{"x": float(location.x), "y": float(location.y), "z": float(location.z)}},
                "rotation": {{"pitch": float(rotation.pitch), "yaw": float(rotation.yaw), "roll": float(rotation.roll)}},
            }}

        actor = _find_actor_by_label(actor_label)
        if actor is None:
            raise RuntimeError("找不到展示 Actor: " + actor_label + "。请先展示一个 Avatar。")
    """)


def _build_get_actor_transform_script(actor_label: str) -> str:
    return _scene_control_helpers_script(actor_label) + textwrap.dedent("""\

        result = _transform_result(actor)
    """)


def _build_move_actor_script(actor_label: str, dx: float, dy: float, dz: float) -> str:
    return _scene_control_helpers_script(actor_label) + textwrap.dedent(f"""\

        location = actor.get_actor_location()
        new_location = unreal.Vector(
            location.x + {float(dx)!r},
            location.y + {float(dy)!r},
            location.z + {float(dz)!r},
        )
        actor.set_actor_location(new_location, False, False)
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        result = _transform_result(actor)
    """)


def _build_move_actor_direction_script(
    actor_label: str,
    direction: str,
    step: float,
    forward_offset_yaw: float = 0.0,
    face_direction: bool = False,
) -> str:
    return _scene_control_helpers_script(actor_label) + textwrap.dedent(f"""\

        direction = {direction!r}
        step = {float(step)!r}
        forward_offset_yaw = {float(forward_offset_yaw)!r}
        face_direction = {bool(face_direction)!r}
        rotation = actor.get_actor_rotation()
        turn_yaws = {{
            "forward": 0.0,
            "backward": 180.0,
            "left": -90.0,
            "right": 90.0,
            "up": 0.0,
            "down": 0.0,
        }}
        if direction not in turn_yaws:
            raise RuntimeError("不支持的移动方向: " + direction)

        if direction in ("up", "down"):
            vector = unreal.Vector(0.0, 0.0, 1.0 if direction == "up" else -1.0)
            effective_yaw = rotation.yaw + forward_offset_yaw
        elif face_direction:
            # Turn only around vertical yaw. Never carry animation/editor pitch/roll into locomotion.
            target_actor_yaw = rotation.yaw + turn_yaws[direction]
            target_rotation = _make_rotator(0.0, target_actor_yaw, 0.0)
            actor.set_actor_rotation(target_rotation, False)
            effective_yaw = target_actor_yaw + forward_offset_yaw
            vector = unreal.MathLibrary.get_forward_vector(_make_rotator(0.0, effective_yaw, 0.0))
        else:
            effective_yaw = rotation.yaw + forward_offset_yaw
            from_rotation = _make_rotator(0.0, effective_yaw, 0.0)
            forward = unreal.MathLibrary.get_forward_vector(from_rotation)
            right = unreal.MathLibrary.get_right_vector(from_rotation)
            direction_vectors = {{
                "forward": forward,
                "backward": unreal.Vector(-forward.x, -forward.y, 0.0),
                "right": unreal.Vector(right.x, right.y, 0.0),
                "left": unreal.Vector(-right.x, -right.y, 0.0),
            }}
            vector = direction_vectors[direction]
        if direction not in ("up", "down"):
            vector = unreal.Vector(vector.x, vector.y, 0.0)

        location = actor.get_actor_location()
        new_location = unreal.Vector(
            location.x + vector.x * step,
            location.y + vector.y * step,
            location.z + vector.z * step,
        )
        actor.set_actor_location(new_location, False, False)

        # Follow camera by translating it with the actor delta, preserving the user's viewing angle.
        camera = _find_actor_by_label("OpenWL_Presentation_Camera")
        if camera is not None:
            try:
                camera_location = camera.get_actor_location()
                camera_rotation = camera.get_actor_rotation()
                delta = unreal.Vector(new_location.x - location.x, new_location.y - location.y, new_location.z - location.z)
                new_camera_location = unreal.Vector(
                    camera_location.x + delta.x,
                    camera_location.y + delta.y,
                    camera_location.z + delta.z,
                )
                camera.set_actor_location(new_camera_location, False, False)
                try:
                    unreal.EditorLevelLibrary.set_level_viewport_camera_info(new_camera_location, camera_rotation)
                except Exception:
                    pass
            except Exception as exc:
                unreal.log_warning("[OpenWL] 更新跟随摄像机失败: " + str(exc))

        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        result = _transform_result(actor)
        result["forward_offset_yaw"] = forward_offset_yaw
        result["effective_yaw"] = effective_yaw
        result["face_direction"] = face_direction
        result["camera_follow"] = camera is not None
    """)


def _build_rotate_actor_script(actor_label: str, yaw_delta: float) -> str:
    return _scene_control_helpers_script(actor_label) + textwrap.dedent(f"""\

        rotation = actor.get_actor_rotation()
        new_rotation = _make_rotator(0.0, rotation.yaw + {float(yaw_delta)!r}, 0.0)
        actor.set_actor_rotation(new_rotation, False)
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        result = _transform_result(actor)
    """)


def _build_set_actor_animation_script(
    actor_label: str,
    motion_asset_path: str,
    avatar_asset_path: str = "",
    looping: bool = True,
) -> str:
    return _scene_control_helpers_script(actor_label) + textwrap.dedent(f"""\

        motion_asset_path = {motion_asset_path!r}
        avatar_asset_path = {avatar_asset_path!r}
        looping = {bool(looping)!r}
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

        avatar_asset = unreal.load_asset(avatar_asset_path) if avatar_asset_path else None
        component = _get_skeletal_component(actor)
        if component is None:
            raise RuntimeError("当前展示 Actor 不是 SkeletalMeshActor，不能播放骨骼动画")
        if avatar_asset is not None:
            motion_skeleton = _skeleton_path(animation_asset)
            avatar_skeleton = _skeleton_path(avatar_asset)
            if motion_skeleton and avatar_skeleton and motion_skeleton != avatar_skeleton:
                raise RuntimeError(
                    "Motion Skeleton 与 Avatar Skeleton 不匹配。 Motion Skeleton: "
                    + motion_skeleton
                    + " Avatar Skeleton: "
                    + avatar_skeleton
                )

        try:
            actor_rotation = actor.get_actor_rotation()
            actor.set_actor_rotation(_make_rotator(0.0, actor_rotation.yaw, 0.0), False)
        except Exception:
            pass
        try:
            component.set_editor_property("animation_mode", unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        except Exception:
            pass
        for property_name, value in (
            ("update_animation_in_editor", True),
            ("enable_update_rate_optimizations", False),
            ("pause_anims", False),
            ("playing", True),
            ("looping", looping),
            ("animation", animation_asset),
            ("animation_asset", animation_asset),
        ):
            try:
                component.set_editor_property(property_name, value)
            except Exception:
                pass
        played = False
        try:
            component.override_animation_data(animation_asset, looping, True, 0.0, 1.0)
            played = True
        except Exception:
            pass
        try:
            component.play_animation(animation_asset, looping)
            played = True
        except Exception:
            pass
        try:
            component.set_animation(animation_asset)
            component.play(looping)
            played = True
        except Exception:
            pass
        try:
            component.tick_animation(0.033, False)
            component.refresh_bone_transforms()
            component.refresh_slave_components()
        except Exception:
            pass
        if not played:
            raise RuntimeError("播放 Actor 动画失败：SkeletalMeshComponent 不接受单节点动画播放")
        try:
            unreal.EditorLevelLibrary.editor_invalidate_viewports()
        except Exception:
            pass
        result = _transform_result(actor)
        result["motion_asset_path"] = motion_asset_path
        result["avatar_asset_path"] = avatar_asset_path
        result["looping"] = looping
        result["motion_skeleton"] = _skeleton_path(animation_asset)
        result["avatar_skeleton"] = _skeleton_path(avatar_asset) if avatar_asset is not None else ""
    """)
