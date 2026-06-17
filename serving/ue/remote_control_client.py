"""UE Remote Control client for lightweight checks and calls."""

from __future__ import annotations

from typing import Optional

import requests

from .config import UE_REMOTE_URL


def _format_remote_control_error(resp: requests.Response) -> str:
    try:
        error_payload = resp.json()
    except ValueError:
        error_payload = {"errorMessage": resp.text.strip()}
    return error_payload.get("errorMessage") or error_payload.get("message") or resp.text.strip()


def _call_ue_python_remote_control(script: str, timeout: int) -> dict:
    payload = {
        "objectPath": "/Script/PythonScriptPlugin.Default__PythonScriptLibrary",
        "functionName": "ExecutePythonCommand",
        "parameters": {
            "PythonCommand": script,
        },
    }
    resp = requests.put(
        f"{UE_REMOTE_URL}/remote/object/call",
        json=payload,
        timeout=timeout,
    )
    if resp.status_code >= 400:
        message = _format_remote_control_error(resp)
        raise RuntimeError(f"UE Remote Control 调用失败 ({resp.status_code}): {message}")

    try:
        return resp.json()
    except ValueError:
        return {"ok": True, "response": resp.text}


def check_ue_connection() -> bool:
    try:
        resp = requests.get(f"{UE_REMOTE_URL}/remote/info", timeout=5)
        return resp.status_code == 200
    except requests.RequestException:
        return False


class RemoteControlClient:
    @property
    def base_url(self) -> str:
        return UE_REMOTE_URL

    def check_connection(self) -> bool:
        return check_ue_connection()

    def call_object(self, object_path: str, function_name: str, parameters: Optional[dict] = None, timeout: int = 10) -> dict:
        payload = {
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters or {},
        }
        response = requests.put(f"{self.base_url}/remote/object/call", json=payload, timeout=timeout)
        if response.status_code >= 400:
            message = _format_remote_control_error(response)
            raise RuntimeError(f"UE Remote Control 调用失败 ({response.status_code}): {message}")
        try:
            return response.json()
        except ValueError:
            return {"ok": True, "response": response.text}
