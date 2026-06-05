# UE5 C++ VFX 自动绑定方案

日期：2026-06-04

## 目标

把目前手动完成的流程：

```text
打开动画 -> 判断帧 -> Add Notify -> 选择 Niagara -> 填 Socket Name
```

升级成 C++ Editor 工具自动完成：

```text
选择动画和 VFX 规则 -> 自动分析动作 -> 自动写入 Niagara Animation Notify -> 保存动画
```

整体分为两个流程：

1. 动作事件自动检测。
2. Niagara Notify 自动写入。

## 当前实现状态

已完成第一版 UE Editor C++ 插件：

```text
D:/document/4D-avatar/Plugins/WorldFlexVFXBinder
```

并已安装到 UE 工程：

```text
D:/document/Unreal Projects/特效探索/Plugins/WorldFlexVFXBinder
```

插件已通过 UE5.7 `BuildPlugin` 编译：

```text
D:/document/4D-avatar/Build/WorldFlexVFXBinder
```

编译结果：

```text
BUILD SUCCESSFUL
```

当前唯一 warning：

```text
UAnimationBlueprintLibrary::GetBonePosesForFrame deprecated
```

该接口在 UE5.7 仍可用，后续升级 UE 时建议迁移到 AnimPose / AnimationDataModel。

## 流程一：动作事件自动检测

### 输入

```text
Animation Sequence
Preview Skeletal Mesh，可选
Bone List，例如 RightFoot / RightHand / Hips
VFX Rule，例如 fire_trail / lightning_hand / impact / run_dust
```

当前 Luffi 可用骨骼：

```text
RightFoot
RightHand
Hips
```

### C++ 关键 API

UE5.7 中可以使用：

```cpp
UAnimationBlueprintLibrary::GetBonePoseForFrame(
    AnimationSequenceBase,
    BoneName,
    Frame,
    bExtractRootMotion,
    OutPose
);
```

或者批量读取：

```cpp
UAnimationBlueprintLibrary::GetBonePosesForFrame(
    AnimationSequenceBase,
    BoneNames,
    Frame,
    bExtractRootMotion,
    OutPoses,
    PreviewMesh
);
```

### 检测逻辑

逐帧读取骨骼位置：

```text
P[t] = BoneWorldOrLocalPosition(frame=t)
V[t] = |P[t] - P[t-1]| / DeltaTime
A[t] = |V[t] - V[t-1]| / DeltaTime
```

基础规则：

| VFX 事件 | 检测规则 |
| --- | --- |
| 脚部火焰拖尾开始 | `RightFoot` 速度超过阈值，并持续 N 帧 |
| 脚部火焰拖尾结束 | `RightFoot` 速度回落到阈值以下 |
| 手部闪电开始 | `RightHand` 速度超过阈值，或处于攻击挥手区间 |
| 命中爆点 | 速度峰值之后出现明显减速，或脚/手接近地面 |
| 跑动尘土 | `Hips` 有持续水平位移，且脚部周期性接近地面 |

### 输出事件结构

建议先输出一个中间事件表，方便检查：

```json
[
  {
    "time": 0.46,
    "frame": 14,
    "type": "trail_start",
    "bone": "RightFoot",
    "niagara": "/Game/NiagaraExamples/FX_Footstep/NS_Footstep_Fire"
  },
  {
    "time": 0.76,
    "frame": 23,
    "type": "impact",
    "bone": "RightFoot",
    "niagara": "/Game/NiagaraExamples/FX_Sparks/NS_Spark_Burst"
  }
]
```

第一版建议：先输出 JSON，不直接写动画。人工确认检测合理后，再打开自动写入。

## 流程二：Niagara Notify 自动写入

### C++ 关键 API

UE5.7 `AnimationBlueprintLibrary` 中提供：

```cpp
UAnimationBlueprintLibrary::AddAnimationNotifyTrack(
    AnimationSequenceBase,
    NotifyTrackName,
    TrackColor
);
```

```cpp
UAnimationBlueprintLibrary::AddAnimationNotifyEvent(
    AnimationSequenceBase,
    NotifyTrackName,
    StartTime,
    NotifyClass
);
```

Niagara Notify 类：

```cpp
UAnimNotify_PlayNiagaraEffect
```

关键字段：

```cpp
Template     // UNiagaraSystem*
Attached     // bool
SocketName   // FName
LocationOffset
RotationOffset
Scale
```

### 写入逻辑

对每个自动检测出的事件：

1. 确保动画里有 VFX Notify Track。
2. 调用 `AddAnimationNotifyEvent` 创建 `UAnimNotify_PlayNiagaraEffect`。
3. 设置 Niagara System。
4. 设置挂载骨骼名。
5. 标记动画 dirty 并保存。

### 核心伪代码

```cpp
void UWorldFlexVFXBinder::AddNiagaraNotify(
    UAnimSequenceBase* Anim,
    float Time,
    const FName TrackName,
    UNiagaraSystem* NiagaraSystem,
    const FName SocketName)
{
    if (!Anim || !NiagaraSystem)
    {
        return;
    }

    if (!UAnimationBlueprintLibrary::IsValidAnimNotifyTrackName(Anim, TrackName))
    {
        UAnimationBlueprintLibrary::AddAnimationNotifyTrack(
            Anim,
            TrackName,
            FLinearColor::Yellow
        );
    }

    UAnimNotify* Notify = UAnimationBlueprintLibrary::AddAnimationNotifyEvent(
        Anim,
        TrackName,
        Time,
        UAnimNotify_PlayNiagaraEffect::StaticClass()
    );

    UAnimNotify_PlayNiagaraEffect* NiagaraNotify =
        Cast<UAnimNotify_PlayNiagaraEffect>(Notify);

    if (!NiagaraNotify)
    {
        return;
    }

    NiagaraNotify->Template = NiagaraSystem;
    NiagaraNotify->Attached = true;
    NiagaraNotify->SocketName = SocketName;
    NiagaraNotify->LocationOffset = FVector::ZeroVector;
    NiagaraNotify->RotationOffset = FRotator::ZeroRotator;
    NiagaraNotify->Scale = FVector(1.0f);

    Anim->Modify();
    Anim->MarkPackageDirty();
}
```

保存资产：

```cpp
UPackage* Package = Anim->GetOutermost();
FEditorFileUtils::PromptForCheckoutAndSave({Package}, false, false);
```

或者在命令行/批处理模式下使用 `UEditorAssetLibrary::SaveLoadedAsset`。

## 推荐插件结构

建议做一个 Editor-only 插件：

```text
Plugins/
  WorldFlexVFXBinder/
    WorldFlexVFXBinder.uplugin
    Source/
      WorldFlexVFXBinder/
        WorldFlexVFXBinder.Build.cs
        Public/
          WorldFlexVFXBinderSubsystem.h
          WorldFlexVFXEvent.h
        Private/
          WorldFlexVFXBinderSubsystem.cpp
```

`WorldFlexVFXEvent.h`:

```cpp
USTRUCT(BlueprintType)
struct FWorldFlexVFXEvent
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    float Time = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Frame = 0;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FName EventType;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FName BoneName;

    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    TObjectPtr<UNiagaraSystem> NiagaraSystem = nullptr;
};
```

Editor Subsystem 暴露两个按钮/函数：

```cpp
UFUNCTION(CallInEditor)
void DetectVFXEvents(UAnimSequence* Animation);

UFUNCTION(CallInEditor)
void ApplyVFXEventsToAnimation(UAnimSequence* Animation);
```

## Build.cs 依赖

需要依赖 Editor、Animation、Niagara 相关模块：

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core",
    "CoreUObject",
    "Engine",
    "Niagara",
    "NiagaraAnimNotifies"
});

PrivateDependencyModuleNames.AddRange(new string[]
{
    "UnrealEd",
    "AnimationBlueprintLibrary",
    "EditorScriptingUtilities",
    "AssetTools",
    "Slate",
    "SlateCore"
});
```

## 第一版规则建议

### Mma Kick

| 事件 | 骨骼 | Niagara | 规则 |
| --- | --- | --- | --- |
| 脚火/拖尾 | `RightFoot` | `/Game/NiagaraExamples/FX_Footstep/NS_Footstep_Fire` | 右脚速度超过阈值 |
| 命中火花 | `RightFoot` | `/Game/NiagaraExamples/FX_Sparks/NS_Spark_Burst` | 右脚速度峰值后 2-4 帧 |

### Standing Melee Run Jump Attack

| 事件 | 骨骼 | Niagara | 规则 |
| --- | --- | --- | --- |
| 跑动脚火 | `RightFoot` | `/Game/NiagaraExamples/FX_Footstep/NS_Footstep_Fire` | Hips 水平位移持续，右脚接近地面 |
| 手部闪电 | `RightHand` | `/Game/NiagaraExamples/FX_Player/NS_Player_Electricity_Looping` | 右手速度超过阈值 |
| 落地爆点 | `Hips` | `/Game/NiagaraExamples/FX_Explosions/NS_Explosion_Small` | Hips 高度下降后速度骤降 |

## 自动化批处理流程

最终命令行目标：

```text
UnrealEditor-Cmd.exe 特效探索.uproject -run=WorldFlexVFXBind \
  -Anim=/Game/WorldFlex/LuffiVFXTest/Animations/Mma_Kick \
  -Rules=D:/document/4D-avatar/samples/luffi_vfx_test/vfx_rules.json \
  -Apply=true
```

当前插件已提供 commandlet：

```text
WorldFlexVFXBind
```

只检测并导出 JSON，不写动画：

```powershell
D:/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe "D:/document/Unreal Projects/特效探索/特效探索.uproject" -run=WorldFlexVFXBind -Anim=/Game/WorldFlex/LuffiVFXTest/Animations/Mma_Kick.Mma_Kick -Mesh=/Game/WorldFlex/LuffiVFXTest/Character/luffi__2_.luffi__2_ -Niagara=/Game/NiagaraExamples/FX_Footstep/NS_Footstep_Fire.NS_Footstep_Fire -Bone=RightFoot -Rule=fixed_frame -Frame=14 -Apply=false -Json="D:/document/4D-avatar/samples/luffi_vfx_test/auto_detect_fixed_frame_test.json"
```

检测并写入 Animation Notify：

```powershell
D:/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe "D:/document/Unreal Projects/特效探索/特效探索.uproject" -run=WorldFlexVFXBind -Anim=/Game/WorldFlex/LuffiVFXTest/Animations/Mma_Kick.Mma_Kick -Mesh=/Game/WorldFlex/LuffiVFXTest/Character/luffi__2_.luffi__2_ -Niagara=/Game/NiagaraExamples/FX_Footstep/NS_Footstep_Fire.NS_Footstep_Fire -Bone=RightFoot -Rule=fixed_frame -Frame=14 -Apply=true -RemoveExisting=false
```

已验证：

- `fixed_frame` 规则可以成功导出事件 JSON。
- 插件可以在当前工程中加载并执行 commandlet。
- 由于工程路径包含中文，项目内源码临时编译会出现路径编码问题；当前采用已编译插件二进制安装方式规避。

待校准：

- `speed_trail` / `speed_peak_impact` 规则已经实现，但当前 Luffi 动画的骨骼 pose 读取结果需要继续校准阈值和空间定义。
- 第一版建议先使用 `fixed_frame` 规则完成自动写入验证，再逐步切换到速度检测。

执行结果：

```text
1. 自动读取动画骨骼轨迹
2. 自动生成 events.json
3. 自动写入 Niagara Notify
4. 自动保存 Animation Sequence
5. 输出绑定报告 bind_report.json
```

## 风险与注意点

- `GetBonePoseForFrame` 在 UE5.7 已标记 deprecated，但仍可用；更长期可切到 AnimPose 或 AnimationDataModel。
- 骨骼 pose 默认可能是 local transform，若需要世界空间或组件空间，需要结合骨骼层级累乘 transform。
- 当前 Luffi 没有 Socket，第一版直接使用骨骼名，后续可自动创建 `RightFoot_VFX`、`RightHand_VFX` Socket。
- 自动检测第一版不追求 100% 精确，应允许人工 review JSON 后再 apply。
- 对 looping Niagara，例如 `NS_Player_Electricity_Looping`，更适合使用 Notify State 控制持续时间；瞬时火花则使用普通 Notify。

## 推荐落地顺序

1. 实现 `DetectVFXEvents`，只输出 JSON。
2. 人工检查 JSON 与动画帧是否合理。
3. 实现 `ApplyVFXEventsToAnimation` 写普通 Niagara Notify。
4. 增加 Notify State 支持，用于持续闪电/持续火焰。
5. 做命令行批处理，支持批量动画自动绑定。

---

## 2026-06-05 更新：自动化流程补全

本次更新完成了剩余的自动化缺口，插件源码位于 `Plugins/WorldFlexVFXBinder`，**需要重新执行 BuildPlugin 编译并重新安装到 UE 工程**。

### 1. 修复 speed 规则检测失效的根因（component space 采样）

`GetBonePosesForFrame` 返回的是 local space（相对父骨骼）transform。对 `RightFoot` 这类深层骨骼，local translation 基本等于固定骨长，逐帧差分得到的"速度"没有物理意义——这就是 `speed_trail` / `speed_peak_impact` 始终检测不到事件（输出空 JSON）的原因。

新实现（`FWorldFlexBoneSampler`，见 `WorldFlexVFXBinderLibrary.cpp`）：

- 从参考骨架（PreviewMesh 优先，否则 Skeleton）构建 root → bone 的骨骼链。
- 逐帧读取整条链的 local pose，按 `ChildComponent = ChildLocal * ParentComponent` 累乘得到 component space 位置。
- 速度为真实物理量（cm/s），阈值从此可校准。
- 旧的 `LinearSpeed + AngularSpeed * 50` motion score 补丁已删除。
- trail 检测加入滞回（进入阈值 100%，退出阈值 80%），避免速度在阈值附近抖动产生碎片 trail。
- `run_loop` 规则默认只统计水平（XY）速度，适合 Hips 跑动检测。
- deprecated API 调用收敛到 `FWorldFlexBoneSampler` 内唯一调用点，未来迁移 AnimPose 只改一处。

### 2. Rules JSON 批处理

commandlet 新增批量模式：

```powershell
UnrealEditor-Cmd.exe "<uproject>" -run=WorldFlexVFXBind -Rules=D:/document/4D-avatar/samples/luffi_vfx_test/vfx_rules.json -Apply=false -Curves=true
```

- `-Rules=`：规则 JSON，一次处理多个动画 × 多条规则（schema 见 `schemas/vfx_rules.schema.json`，样本见 `samples/luffi_vfx_test/vfx_rules.json`）。
- `-Apply=false`：只检测出报告，不写动画（校准阶段用）。
- `-Curves=true`：报告中附带逐帧速度曲线。
- `-Report=`：报告输出路径，默认规则文件同目录 `bind_report.json`。
- 旧的单规则参数（`-Anim/-Niagara/-Bone/-Rule/...`）完全向后兼容，新增 `-HorizontalOnly=`、`-Report=`。

### 3. bind_report.json 与阈值校准

报告中每条规则输出 `max_speed` / `mean_speed` / `p90_speed` / `peak_frame` / `suggested_threshold`（cm/s）。校准流程：

1. `scripts/ue/run_vfx_bind.ps1 -DetectOnly -Curves` 跑一次检测。
2. 打开 `bind_report.json`，对比每条规则的 `max_speed` 与当前 `speed_threshold`；事件数为 0 时参考 `suggested_threshold`（mean 与 max 的中点）回填 `vfx_rules.json`。
3. 重复 1-2 直到 events 合理，再 `scripts/ue/run_vfx_bind.ps1` 正式写入。

### 4. 新增/修改文件

| 文件 | 说明 |
| --- | --- |
| `Plugins/.../WorldFlexVFXBinderTypes.h` | 规则新增 `bHorizontalOnly`；新增 `FWorldFlexVFXRuleStats` 统计结构 |
| `Plugins/.../WorldFlexVFXBinderLibrary.h/.cpp` | component space 采样器；`DetectVFXEventsWithStats`；滞回 trail 检测；仅在实际写入后保存资产 |
| `Plugins/.../WorldFlexVFXBindCommandlet.cpp` | `-Rules` 批量模式；`bind_report.json`；向后兼容单规则模式 |
| `samples/luffi_vfx_test/vfx_rules.json` | 两个动画的首版规则（阈值为待校准初值） |
| `schemas/vfx_rules.schema.json` | 规则文件 schema |
| `scripts/ue/run_vfx_bind.ps1` | 批处理入口脚本（-DetectOnly / -Curves 开关） |

### 5. 重新编译

```powershell
D:/UE_5.7/Engine/Build/BatchFiles/RunUAT.bat BuildPlugin -Plugin="D:/document/4D-avatar/Plugins/WorldFlexVFXBinder/WorldFlexVFXBinder.uplugin" -Package="D:/document/4D-avatar/Build/WorldFlexVFXBinder" -TargetPlatforms=Win64
```

编译后将 `Build/WorldFlexVFXBinder` 覆盖安装到 `D:/document/Unreal Projects/特效探索/Plugins/WorldFlexVFXBinder`（与之前规避中文路径编码问题的方式一致）。

### 6. 仍待办（优先级从高到低）

1. 在真实动画上跑校准流程，确定 Mma_Kick / Run Jump Attack 的最终阈值。
2. 落地爆点规则升级：当前用 Hips 速度峰值近似，更准确的是"Hips 高度下降后骤减速"（可在 sampler 上加高度/加速度特征）。
3. 自动创建 `RightFoot_VFX` 等 Socket（当前直接用骨骼名，功能上等价）。
4. 迁移 deprecated `GetBonePosesForFrame` → AnimPose / AnimationDataModel（UE 升级时再做）。
