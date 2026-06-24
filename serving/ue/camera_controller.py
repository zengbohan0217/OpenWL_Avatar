"""Camera control adapter."""

from __future__ import annotations


class CameraController:
    def set_camera(self, camera_config: dict) -> dict:
        raise NotImplementedError("Camera presets and switching belong to the next camera-control milestone")
