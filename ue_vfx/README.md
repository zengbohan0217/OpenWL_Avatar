# UE VFX Auto-Binding（粒子特效自动绑定）

OpenWL-Avatar pipeline 的 UE5 交付侧模块：将生成的角色 / 动作资产导入 UE5 后，**自动检测动作事件并把 Niagara 粒子特效写入 Animation Notify**，替代手动逐帧挂 Notify 的流程。

```text
角色/动作 FBX ──> UE Python 导入 ──> C++ 插件逐帧分析骨骼轨迹(component space)
                                          │
              vfx_rules.json 规则 ────────┤
                                          ▼
              bind_report.json(校准统计) + Niagara Notify 自动写入动画并保存
```

## 目录

| 路径 | 说明 |
| --- | --- |
| `Plugins/WorldFlexVFXBinder/` | UE5 Editor C++ 插件（事件检测 + Notify 写入 + `WorldFlexVFXBind` commandlet） |
| `scripts/` | UE Python 导入脚本、Niagara 占位资产脚本、`run_vfx_bind.ps1` 批处理入口 |
| `schemas/` | `vfx_rules` / `motion_events` / `vfx_emitters` 的 JSON Schema |
| `samples/luffi_vfx_test/` | Luffi 角色样本：规则文件、检测出的事件、bind_report 示例 |
| `docs/` | 设计方案、UE/Niagara 快速上手、工作进展汇报 |

## 检测规则

速度均为 **component space 骨骼速度（cm/s）**，由参考骨架层级累乘 local transform 得到：

| 规则 | 语义 | 写入的 Notify |
| --- | --- | --- |
| `speed_trail` | 骨骼速度超阈值的持续区间（带滞回，进 100% / 出 80%） | `AnimNotifyState_TimedNiagaraEffect`（带时长） |
| `run_loop` | 骨骼（通常 Hips）水平速度持续超阈值 → 跑动段 | 同上 |
| `speed_peak_impact` | 超阈值帧中后续减速最陡的一帧 → 命中 / 落地 | `AnimNotify_PlayNiagaraEffect`（瞬时） |
| `fixed_frame` | 指定帧直接挂特效 | 同上 |

## 快速开始

```powershell
# 编译插件（UE5.7）
RunUAT.bat BuildPlugin -Plugin=".../WorldFlexVFXBinder.uplugin" -Package="<输出目录>" -TargetPlatforms=Win64
# 将编译产物安装到 UE 工程 Plugins/ 目录

# 1) 校准：只检测，输出 bind_report.json（含 max/mean/p90 速度与建议阈值）
./scripts/run_vfx_bind.ps1 -DetectOnly -Curves

# 2) 按报告回填 vfx_rules.json 阈值后，正式写入 Notify 并保存动画
./scripts/run_vfx_bind.ps1
```

也可直接调用 commandlet（单规则模式同样支持，参数见 `WorldFlexVFXBindCommandlet.cpp` 头部 usage）：

```text
UnrealEditor-Cmd.exe <uproject> -run=WorldFlexVFXBind -Rules=<vfx_rules.json> -Apply=true [-Curves=true] [-Report=<bind_report.json>]
```

## 已在样本上验证

Luffi 角色 + Mma Kick / Standing Melee Run Jump Attack 两段动画，5 个事件全部命中语义正确的帧（踢击拖尾、踢中火花、助跑脚火、挥手闪电、落地爆点），见 `samples/luffi_vfx_test/bind_report.json`。

## 已知限制 / 后续

- `GetBonePosesForFrame` 在 UE5.7 标记 deprecated（仍可用），调用点已收敛到单处，便于迁移 AnimPose。
- 落地检测目前基于"高速后骤停"，未来可加入骨骼高度 / 地面接触特征。
- 角色无 Socket 时直接用骨骼名作为 SocketName（功能等价），可扩展自动创建 `*_VFX` Socket。
