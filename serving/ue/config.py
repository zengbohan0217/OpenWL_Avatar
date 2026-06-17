"""UE connection and destination configuration."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

UE_HOST = os.environ.get("UE_HOST", "localhost")
UE_PORT = int(os.environ.get("UE_PORT", "30010"))
UE_RPC_HOST = os.environ.get("UE_RPC_HOST", f"http://{UE_HOST}:{UE_PORT}").rstrip("/")
UE_REMOTE_URL = UE_RPC_HOST
def _default_ue_python_plugin_path() -> Path:
    candidates = [
        Path("D:/UE/UE_5.4/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"),
        Path("D:/UE5/UE_5.4/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"),
        Path("C:/Program Files/Epic Games/UE_5.4/Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python"),
    ]
    for candidate in candidates:
        if (candidate / "remote_execution.py").exists():
            return candidate
    return candidates[0]


UE_PYTHON_PLUGIN_PATH = Path(os.environ.get("UE_PYTHON_PLUGIN_PATH", _default_ue_python_plugin_path()))

DEFAULT_AVATAR_DEST = "/Game/Imported/Avatars"
DEFAULT_MOTION_DEST = "/Game/Imported/Motions"
DEFAULT_SCENE_DEST = "/Game/Imported/Scenes"
DEFAULT_SEQUENCE_DEST = "/Game/Imported/Sequences"
DEFAULT_EFFECT_DEST = "/Game/Imported/Effects"
DEFAULT_MATERIAL_DEST = "/Game/Imported/Materials"
DEFAULT_TEXTURE_DEST = "/Game/Imported/Textures"
DEFAULT_PROP_DEST = "/Game/Imported/Props"
DEFAULT_WEAPON_DEST = "/Game/Imported/Weapons"

VIEWER_HOST = os.environ.get("OPENWL_VIEWER_HOST", "127.0.0.1")
VIEWER_PORT = int(os.environ.get("OPENWL_VIEWER_PORT", "7870"))
PIXEL_STREAMING_URL = os.environ.get("OPENWL_PIXEL_STREAMING_URL", "").strip()
