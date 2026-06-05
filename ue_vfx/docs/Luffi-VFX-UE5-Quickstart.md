# Luffi 粒子特效 UE5 操作手册

这份文档只针对你负责的“粒子特效 / Niagara”部分。角色资产和动作已经导入好了，你现在主要做三件事：

1. 打开动画，找到特效应该出现的帧。
2. 创建 Niagara 粒子系统。
3. 在动画里用 Notify 触发 Niagara。

## 1. 样本在哪里

项目里的测试样本配置在：

```text
D:/document/4D-avatar/samples/luffi_vfx_test/
```

注意：这里没有复制大 FBX 文件，只记录了原始文件路径。

原始 FBX 文件位置：

```text
D:/assets/luffi_sample/luffi (2).fbx
D:/assets/luffi_sample/Mma Kick.fbx
D:/assets/luffi_sample/Standing Melee Run Jump Attack (1)(1).fbx
```

## 2. UE 工程在哪里

打开这个 UE 工程：

```text
D:/document/Unreal Projects/特效探索/特效探索.uproject
```

我已经把资源导入到 UE 工程里了。打开 UE 后，在 Content Browser 里找：

```text
/Game/WorldFlex/LuffiVFXTest
```

里面应该能看到：

```text
Character/luffi__2_
Character/luffi__2__Skeleton
Animations/Mma_Kick
Animations/Standing_Melee_Run_Jump_Attack__1__1_
```

## 3. 先做哪几个 Niagara

建议你先做 3 个最基础的效果：

```text
NS_KickFootAfterimage      脚部拖尾
NS_ImpactBurstSmall        命中爆点
NS_RunDustSmall            跑动尘土
```

这 3 个 Niagara 我已经帮你创建好了，位置是：

```text
/Game/WorldFlex/LuffiVFXTest/Niagara/NS_KickFootAfterimage
/Game/WorldFlex/LuffiVFXTest/Niagara/NS_ImpactBurstSmall
/Game/WorldFlex/LuffiVFXTest/Niagara/NS_RunDustSmall
```

它们是从 UE 自带 Niagara 模板复制出来的第一版可播放资产。后面如果要更好看，再进 Niagara 编辑器微调颜色、大小、速度和生命周期。

动作对应关系：

| 动作 | 时机 | Niagara |
| --- | --- | --- |
| `Mma_Kick` | 踢腿快速摆动时 | `NS_KickFootAfterimage` |
| `Mma_Kick` | 踢中/接触瞬间 | `NS_ImpactBurstSmall` |
| `Standing_Melee_Run_Jump_Attack` | 跑动起步阶段 | `NS_RunDustSmall` |
| `Standing_Melee_Run_Jump_Attack` | 跳劈/挥击阶段 | `NS_KickFootAfterimage` 或手部拖尾版本 |
| `Standing_Melee_Run_Jump_Attack` | 落地/命中瞬间 | `NS_ImpactBurstSmall` |

## 4. 创建 Niagara 文件夹

在 UE 的 Content Browser 里打开：

```text
/Game/WorldFlex/LuffiVFXTest
```

右键新建文件夹：

```text
Niagara
```

之后所有 Niagara 都放这里：

```text
/Game/WorldFlex/LuffiVFXTest/Niagara
```

这一步我已经帮你做完了。如果 UE 里没有刷新出来，在 Content Browser 里右键空白处点一下 `Refresh`。

## 5. 做脚部拖尾：NS_KickFootAfterimage

目标：脚踢出去的时候，有一小段淡蓝白色拖尾。先做一个简单版本，不用 Ribbon，直接用小粒子跟随脚部，效果会更容易成功。

操作：

1. 在 `Niagara` 文件夹里右键。
2. 选择：

```text
FX > Niagara System
```

3. 选择：

```text
New system from selected emitters
```

4. 选择模板：

```text
Fountain
```

5. 命名为：

```text
NS_KickFootAfterimage
```

打开 `NS_KickFootAfterimage` 后，点左边的 emitter，然后改这些参数：

```text
Emitter State
  Life Cycle Mode: Self
  Inactive Response: Complete

Spawn Rate
  Spawn Rate: 80

Initialize Particle
  Lifetime: 0.12 - 0.20
  Sprite Size: 8 - 18
  Color: 淡蓝 / 白色

Add Velocity
  Velocity Mode: Cone
  Velocity Strength: 20 - 60

Gravity Force
  可以关掉，或者设得很小

Scale Sprite Size
  让粒子随生命周期逐渐缩小到 0
```

保存。

## 6. 做命中爆点：NS_ImpactBurstSmall

目标：踢中或者落地的一瞬间，出现一个小范围金色/橙色爆点。

操作：

1. 在 `Niagara` 文件夹里再新建一个 Niagara System。
2. 还是用 `Fountain` 模板。
3. 命名为：

```text
NS_ImpactBurstSmall
```

打开后改参数：

```text
Emitter State
  Life Cycle Mode: Self
  Inactive Response: Complete

Spawn Burst Instantaneous
  Spawn Count: 30 - 60

Spawn Rate
  Spawn Rate: 0

Initialize Particle
  Lifetime: 0.18 - 0.35
  Sprite Size: 6 - 22
  Color: 橙色 / 金色

Add Velocity
  Velocity Mode: Sphere
  Velocity Strength: 120 - 260

Drag
  Drag: 2 - 5

Gravity Force
  Gravity: 小一点，比如 -100 到 -300

Scale Sprite Size
  开始稍大，然后快速缩小
```

保存。

## 7. 做跑动尘土：NS_RunDustSmall

目标：角色跑动的时候，脚底附近有一点灰棕色尘土，不要太夸张。

操作：

1. 在 `Niagara` 文件夹里新建 Niagara System。
2. 用 `Fountain` 模板。
3. 命名为：

```text
NS_RunDustSmall
```

打开后改参数：

```text
Spawn Rate
  Spawn Rate: 20 - 40

Initialize Particle
  Lifetime: 0.4 - 0.7
  Sprite Size: 18 - 45
  Color: 灰色 / 棕灰色

Add Velocity
  X/Y 随机扩散: 30 - 80
  Z 向上: 10 - 40

Gravity Force
  Gravity: 小一点

Drag
  Drag: 4 - 8

Scale Color
  Alpha 逐渐变成 0，让尘土淡出
```

保存。

## 8. 找骨骼名 / Socket 名

Niagara 要跟着脚或手动，就必须知道骨骼名字。

我已经帮你读取了 Luffi 的骨骼。当前可以直接用：

```text
右脚: RightFoot
右手: RightHand
身体/跑动尘土: Hips
```

这个模型暂时没有 Socket，所以 Notify 里的 `Socket Name` 先直接填骨骼名即可。

操作：

1. 打开角色 Skeletal Mesh：

```text
/Game/WorldFlex/LuffiVFXTest/Character/luffi__2_
```

2. 找到左边的 `Skeleton Tree`。
3. 搜索这些关键词：

```text
foot
toe
hand
wrist
root
pelvis
```

4. 找到右脚、右手、root/pelvis 的真实名字，复制下来。

后面在动画 Notify 里，`Socket Name` 就填这个真实骨骼名。

## 9. 在 Mma_Kick 里挂脚部拖尾

操作：

1. 打开动画：

```text
/Game/WorldFlex/LuffiVFXTest/Animations/Mma_Kick
```

2. 播放或拖动时间轴，找到腿开始快速踢出去的帧。
3. 在下面的 Notify 轨道上右键。
4. 选择：

```text
Add Notify > Play Niagara Particle Effect
```

5. 在右侧 Details 面板里设置：

```text
Template: NS_KickFootAfterimage
Attached: 勾选
Socket Name: 右脚骨骼名
Location Offset: 如果粒子在脚里面，就稍微调一下位置
```

6. 播放动画预览，看粒子是不是跟着脚走。

## 10. 在 Mma_Kick 里挂命中爆点

操作：

1. 继续打开 `Mma_Kick`。
2. 找到脚踢到目标或动作最有力的那一帧。
3. 在 Notify 轨道右键：

```text
Add Notify > Play Niagara Particle Effect
```

4. Details 里设置：

```text
Template: NS_ImpactBurstSmall
Attached: 勾选
Socket Name: 右脚骨骼名
```

5. 播放预览。

如果爆点太大，回到 `NS_ImpactBurstSmall` 里调小：

```text
Spawn Count
Sprite Size
Velocity Strength
```

## 11. 在跑跳攻击里挂尘土和爆点

打开动画：

```text
/Game/WorldFlex/LuffiVFXTest/Animations/Standing_Melee_Run_Jump_Attack__1__1_
```

建议加三个 Notify：

1. 跑动阶段：

```text
Template: NS_RunDustSmall
Attached: 勾选
Socket Name: root 或 pelvis
```

2. 跳起/挥击阶段：

```text
Template: NS_KickFootAfterimage
Attached: 勾选
Socket Name: 右手骨骼名，或者武器骨骼名
```

3. 落地/命中瞬间：

```text
Template: NS_ImpactBurstSmall
Attached: 勾选
Socket Name: root、pelvis、右手或右脚，看动作接触点
```

## 12. 怎么判断效果合格

第一版不用追求华丽，先满足这些：

- 粒子能跟着脚、手或者身体走，不要漂在空中。
- 命中爆点出现在接触瞬间，误差最好小于 2-3 帧。
- 特效不要盖住角色动作。
- 视觉风格偏动作游戏，不要做成满屏无双特效。
- 两个动作都能播放并看到对应粒子。

## 13. 能不能自动绑定动作

可以，而且后面应该做成自动的。手动判断开始帧/结束帧只适合第一版验证。

自动绑定可以分两层：

### 第一层：自动检测特效事件

程序逐帧读取动画里的骨骼位置，比如：

```text
RightFoot
RightHand
Hips
```

然后根据规则自动判断：

```text
脚/手速度突然变快 -> 拖尾开始
脚/手速度降低并接近地面/目标 -> 命中爆点
Hips 或脚部持续移动 -> 跑动尘土
动作结束、速度下降 -> 拖尾结束
```

这样可以自动生成类似：

```json
[
  {
    "frame": 14,
    "type": "trail_start",
    "bone": "RightFoot",
    "niagara": "NS_FootFireTrail"
  },
  {
    "frame": 23,
    "type": "impact",
    "bone": "RightFoot",
    "niagara": "NS_ImpactBurstSmall"
  }
]
```

### 第二层：自动写入 UE Animation Notify

UE C++ 里有接口可以自动写入 Notify：

```text
UAnimationBlueprintLibrary::AddAnimationNotifyEvent
UAnimationBlueprintLibrary::AddAnimationNotifyTrack
```

但当前 UE 5.7 的 Python 没直接暴露这个接口，所以纯 Python 不能稳定地把 Notify 写进动画资产。

后续要做全自动，需要二选一：

```text
方案 A：写一个 UE Editor C++ 小插件
方案 B：写一个 Animation Modifier / Editor Utility
```

这两个方案都能做到：

```text
读取动画 -> 自动检测帧 -> 自动添加 Niagara Notify -> 自动保存动画资产
```

### 当前建议

现在先用手动 Notify 跑通视觉效果。等确认要用哪些 Niagara 后，再做自动绑定工具。

第一版自动绑定工具建议输入：

```text
动画资产路径
骨骼名，比如 RightFoot / RightHand / Hips
Niagara 名，比如 NS_FootFireTrail / NS_LightningArcSmall
检测规则，比如 speed_peak / contact / run_loop
```

输出：

```text
自动写入 Animation Notify
或者先输出 events.json 给人检查
```

## 14. 如果效果不对，优先检查什么

粒子完全看不到：

```text
检查 Niagara 是否保存
检查 Notify 的 Template 是否选对
检查 Spawn Rate 或 Spawn Burst 是否为 0
检查粒子颜色/透明度是不是太低
```

粒子出现了但不跟着脚：

```text
检查 Attached 是否勾选
检查 Socket Name 是否写对
检查是不是填了左脚而不是右脚
```

爆点太夸张：

```text
降低 Spawn Count
降低 Sprite Size
降低 Velocity Strength
降低 Lifetime
```

拖尾太散：

```text
降低 Velocity Strength
降低 Lifetime
降低 Spawn Rate
```

尘土飞太高：

```text
降低 Z 方向速度
增大 Drag
减小 Lifetime
```
