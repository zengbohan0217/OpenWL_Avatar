from __future__ import annotations

import json
from pathlib import Path

import unreal


DEST_DIR = "/Game/WorldFlex/LuffiVFXTest/Niagara"
REPORT_PATH = Path("D:/document/4D-avatar/samples/luffi_vfx_test/fire_lightning_niagara_report.json")


ASSETS = [
    {
        "name": "NS_HandFireSmall",
        "source": "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight",
        "purpose": "手部小火焰。建议挂到 RightHand，可用于蓄力、拳头火焰、短促火焰附着。",
        "suggested_socket": "RightHand",
    },
    {
        "name": "NS_FootFireTrail",
        "source": "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight",
        "purpose": "脚部火焰拖尾。建议挂到 RightFoot，可用于踢击火焰尾迹。",
        "suggested_socket": "RightFoot",
    },
    {
        "name": "NS_LightningArcSmall",
        "source": "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurstLightweight.DirectionalBurstLightweight",
        "purpose": "小型闪电/电弧占位。建议挂到 RightHand 或命中点，用于电击、命中电爆。",
        "suggested_socket": "RightHand",
    },
]


def main() -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(DEST_DIR):
        unreal.EditorAssetLibrary.make_directory(DEST_DIR)

    report = {
        "destination": DEST_DIR,
        "created": [],
        "failed": [],
        "manual_tuning_notes": {
            "NS_HandFireSmall": [
                "颜色调成橙红/黄色。",
                "粒子向上速度稍大，生命周期 0.2-0.5 秒。",
                "如果太像喷泉，降低 Spawn Rate 和 Velocity，缩小 Sprite Size。"
            ],
            "NS_FootFireTrail": [
                "颜色调成橙红，生命周期短一点。",
                "挂 RightFoot，踢腿时用 Notify 触发。",
                "如果火焰拖得太长，降低 Lifetime。"
            ],
            "NS_LightningArcSmall": [
                "颜色调成蓝白，高亮，生命周期 0.08-0.2 秒。",
                "适合用在命中瞬间，Spawn 时间不要太长。",
                "后续可升级成 Ribbon/Beam 版本。"
            ],
        },
    }

    for spec in ASSETS:
        dest = f"{DEST_DIR}/{spec['name']}"
        source_asset = unreal.EditorAssetLibrary.load_asset(spec["source"])
        if not source_asset:
            report["failed"].append({
                "name": spec["name"],
                "reason": "source template not found",
                "source": spec["source"],
            })
            continue

        if unreal.EditorAssetLibrary.does_asset_exist(dest):
            unreal.EditorAssetLibrary.delete_asset(dest)

        new_asset = unreal.EditorAssetLibrary.duplicate_asset(spec["source"], dest)
        if not new_asset:
            report["failed"].append({
                "name": spec["name"],
                "reason": "duplicate failed",
                "source": spec["source"],
            })
            continue

        unreal.EditorAssetLibrary.save_asset(dest, only_if_is_dirty=False)
        report["created"].append({
            "name": spec["name"],
            "path": f"{dest}.{spec['name']}",
            "source": spec["source"],
            "purpose": spec["purpose"],
            "suggested_socket": spec["suggested_socket"],
        })

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    unreal.log(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
