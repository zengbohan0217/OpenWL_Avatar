from __future__ import annotations

import json
from pathlib import Path

import unreal


SKELETON_PATH = "/Game/WorldFlex/LuffiVFXTest/Character/luffi__2__Skeleton.luffi__2__Skeleton"
REPORT_PATH = Path("D:/document/4D-avatar/samples/luffi_vfx_test/luffi_bones.json")


def main() -> None:
    skeleton = unreal.EditorAssetLibrary.load_asset(SKELETON_PATH)
    names = []

    # UE skeleton exposes reference pose through the skeleton library in C++,
    # but Python exposure differs by version. Try common methods/properties.
    for method in ["get_reference_pose", "get_raw_bone_names", "get_bone_names"]:
        if hasattr(skeleton, method):
            try:
                value = getattr(skeleton, method)()
                names.append({"method": method, "value": [str(x) for x in value]})
            except Exception as exc:
                names.append({"method": method, "error": str(exc)})

    try:
        pose = skeleton.get_reference_pose()
        names.append({"method": "reference_pose.get_bone_names", "value": [str(x) for x in pose.get_bone_names()]})
        names.append({"method": "reference_pose.get_socket_names", "value": [str(x) for x in pose.get_socket_names()]})
    except Exception as exc:
        names.append({"method": "reference_pose", "error": str(exc)})

    report = {
        "skeleton_path": SKELETON_PATH,
        "skeleton_class": skeleton.get_class().get_name() if skeleton else None,
        "candidate_methods": [x for x in dir(skeleton) if "bone" in x.lower() or "socket" in x.lower()][:200] if skeleton else [],
        "results": names,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    unreal.log(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
