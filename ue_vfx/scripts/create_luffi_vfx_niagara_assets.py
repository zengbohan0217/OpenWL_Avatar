from __future__ import annotations

import json
from pathlib import Path

import unreal


DEST_DIR = "/Game/WorldFlex/LuffiVFXTest/Niagara"
REPORT_PATH = Path("D:/document/4D-avatar/samples/luffi_vfx_test/niagara_assets_report.json")


ASSETS = [
    {
        "name": "NS_KickFootAfterimage",
        "source_candidates": [
            "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight",
            "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurstLightweight.DirectionalBurstLightweight",
            "/Niagara/DefaultAssets/Templates/Systems/Fountain.Fountain",
        ],
        "purpose": "脚部或手部拖尾。第一版用喷泉/轻量粒子模板代替真正 Ribbon，先保证能跟随骨骼播放。",
    },
    {
        "name": "NS_ImpactBurstSmall",
        "source_candidates": [
            "/Niagara/DefaultAssets/Templates/Systems/RadialBurst.RadialBurst",
            "/Niagara/DefaultAssets/Templates/Systems/SimpleExplosion.SimpleExplosion",
            "/Niagara/DefaultAssets/Templates/Systems/DirectionalBurst.DirectionalBurst",
        ],
        "purpose": "踢中、落地、攻击命中的小型爆点。",
    },
    {
        "name": "NS_RunDustSmall",
        "source_candidates": [
            "/Niagara/DefaultAssets/Templates/Systems/FountainLightweight.FountainLightweight",
            "/Niagara/DefaultAssets/Templates/Systems/Fountain.Fountain",
        ],
        "purpose": "跑动阶段脚底或 pelvis/root 附近的小尘土。",
    },
]


def load_first(candidates: list[str]):
    for path in candidates:
        asset = unreal.EditorAssetLibrary.load_asset(path)
        if asset:
            return path, asset
    return None, None


def main() -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(DEST_DIR):
        unreal.EditorAssetLibrary.make_directory(DEST_DIR)

    report = {
        "destination": DEST_DIR,
        "created": [],
        "failed": [],
        "notes": [
            "These are duplicated from built-in Niagara templates.",
            "Fine visual parameters should be adjusted in the Niagara editor UI.",
            "Use Anim Notify > Play Niagara Particle Effect to attach them to animation frames."
        ],
    }

    for spec in ASSETS:
        dest_asset_path = f"{DEST_DIR}/{spec['name']}"
        source_path, source_asset = load_first(spec["source_candidates"])
        if not source_asset:
            report["failed"].append({
                "name": spec["name"],
                "reason": "No source template found",
                "candidates": spec["source_candidates"],
            })
            continue

        if unreal.EditorAssetLibrary.does_asset_exist(dest_asset_path):
            unreal.EditorAssetLibrary.delete_asset(dest_asset_path)

        new_asset = unreal.EditorAssetLibrary.duplicate_asset(source_path, dest_asset_path)
        if new_asset:
            unreal.EditorAssetLibrary.save_asset(dest_asset_path, only_if_is_dirty=False)
            report["created"].append({
                "name": spec["name"],
                "path": f"{dest_asset_path}.{spec['name']}",
                "source": source_path,
                "purpose": spec["purpose"],
            })
        else:
            report["failed"].append({
                "name": spec["name"],
                "reason": "duplicate_asset returned None",
                "source": source_path,
            })

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    unreal.log(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
