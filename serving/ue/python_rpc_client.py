"""UE Python execution client."""

from __future__ import annotations

import json
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any

import requests

from .config import UE_PYTHON_PLUGIN_PATH
from .remote_control_client import _call_ue_python_remote_control


def _call_ue_python_remote_execution(script: str, timeout: int) -> dict:
    if not UE_PYTHON_PLUGIN_PATH.exists():
        raise RuntimeError(f"找不到 UE remote_execution.py 路径: {UE_PYTHON_PLUGIN_PATH}")

    plugin_path = str(UE_PYTHON_PLUGIN_PATH)
    if plugin_path not in sys.path:
        sys.path.append(plugin_path)

    import remote_execution

    remote = remote_execution.RemoteExecution()
    remote.start()
    try:
        deadline = time.time() + timeout
        while not remote.remote_nodes and time.time() < deadline:
            time.sleep(0.1)

        if not remote.remote_nodes:
            raise RuntimeError(
                "未发现 UE Python Remote Execution 节点。请在 UE Project Settings → Python 中启用 Enable Remote Execution，并重启 UE。"
            )

        node = remote.remote_nodes[0]
        remote.open_command_connection(node["node_id"])
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as script_file:
            script_file.write(script)
            script_path = Path(script_file.name).as_posix()
        try:
            result = remote.run_command(
                script_path,
                unattended=True,
                exec_mode=remote_execution.MODE_EXEC_FILE,
                raise_on_failure=True,
            )
        finally:
            try:
                Path(script_path).unlink(missing_ok=True)
            except Exception:
                pass
        return {"ok": bool(result.get("success", True)), "transport": "python_remote_execution", "result": result}
    finally:
        remote.stop()


def call_ue_python(script: str, timeout: int = 120) -> dict:
    try:
        result = _call_ue_python_remote_control(script, min(timeout, 10))
        result["transport"] = "remote_control"
        return result
    except RuntimeError as exc:
        message = str(exc)
        if "Default__PythonScriptLibrary cannot be accessed remotely" not in message:
            raise
    except requests.RequestException:
        pass

    return _call_ue_python_remote_execution(script, timeout)


def _call_ue_python_json(script: str, result_var: str = "result", timeout: int = 120):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as result_file:
        result_path = Path(result_file.name).as_posix()

    wrapped_script = script + textwrap.dedent(f"""\

        import json as _openwl_json
        with open({result_path!r}, "w", encoding="utf-8") as _openwl_result_file:
            _openwl_json.dump({result_var}, _openwl_result_file, ensure_ascii=False)
    """)
    try:
        call_ue_python(wrapped_script, timeout=timeout)
        with open(result_path, "r", encoding="utf-8") as result_file:
            return json.load(result_file)
    finally:
        try:
            Path(result_path).unlink(missing_ok=True)
        except Exception:
            pass


class UEPythonRPCClient:
    def execute(self, script: str, timeout: int = 120) -> dict[str, Any]:
        return call_ue_python(script, timeout=timeout)

    def execute_json(self, script: str, result_var: str = "result", timeout: int = 120) -> Any:
        return _call_ue_python_json(script, result_var=result_var, timeout=timeout)
