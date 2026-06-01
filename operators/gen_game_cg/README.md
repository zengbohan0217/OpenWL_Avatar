# Game CG Generation Pipeline

## 功能概述

生成游戏级别的 CG 动画，支持：
- 📝 从 JSON 文件加载分镜脚本
- 🎨 为每个镜头生成场景图片（使用 Qwen-Image-Edit）
- 🎬 生成视频片段（使用 LTX-2.3）
- 🔄 支持两种镜头过渡方式：
  - **cut**: 硬切（独立生成每个镜头）
  - **transition**: 平滑过渡（使用关键帧插值）
- 🎞️ 自动拼接成完整视频

## 镜头过渡说明

### Cut（硬切）
```json
{
    "shot_id": 0,
    "transition": "cut"
}
```
- 使用 `TI2VidTwoStagesPipeline`（I2V 模式）
- 只需要起始帧，自由生成视频内容
- 适合场景切换、视角大幅变化

### Transition（平滑过渡）
```json
{
    "shot_id": 1,
    "transition": "transition"
}
```
- 使用 `KeyframeInterpolationPipeline`（关键帧插值）
- 需要起始帧和结束帧（自动使用下一个镜头的起始帧）
- 适合连续动作、镜头推进、视角平移

## Storyboard 示例

当前 `assets/storyboard.json` 包含 8 个镜头：

```
Shot 0 (cut)        → 路飞站在船头，暴风雨中
Shot 1 (transition) → 抓住栏杆，风吹动衣服
Shot 2 (transition) → 特写眼神，雨滴反射闪电
Shot 3 (transition) → 拳头充能，红色能量
Shot 4 (cut)        → 从船头跃起
Shot 5 (transition) → POV 冲向敌船桅杆
Shot 6 (cut)        → 拳头击碎桅杆
Shot 7 (cut)        → 碎片坠落，桅杆倒塌
```

**过渡逻辑**：
- Shot 1 的 end_frame = Shot 2 的 start_frame
- Shot 2 的 end_frame = Shot 3 的 start_frame
- Shot 3 的 end_frame = Shot 4 的 start_frame
- Shot 5 的 end_frame = Shot 6 的 start_frame

## 使用方法

### 方式 1：分步执行（手动控制）
```python
op = GameCGOperator(CFG)

board       = op.get_storyboard("assets/storyboard.json")
shot_images = op.gen_storyboard_images(board, ref_image)

clips = []
for i, (shot, img) in enumerate(zip(board, shot_images)):
    end_img = None
    if shot.get("transition") == "transition" and i + 1 < len(shot_images):
        end_img = shot_images[i + 1]
    
    clip = op.gen_cg_video(shot, img, end_image=end_img)
    clips.append(clip)

final = op.compose_cg(clips, output_path="output/luffy_cg.mp4")
```

### 方式 2：一键执行（推荐）
```python
op = GameCGOperator(CFG)
final = op.run("assets/storyboard.json", ref_image, output_path="output/luffy_cg.mp4")
```

## compose_cg 功能

支持两种输入格式：

### 1. 视频片段列表
```python
clips = ["output/clips/shot_00.mp4", "output/clips/shot_01.mp4"]
compose_cg(clips, "output/final.mp4")
```

### 2. 帧序列列表
```python
frame_sequences = [
    ["frame_00.png", "frame_01.png", "frame_02.png"],  # Clip 1
    ["frame_03.png", "frame_04.png", "frame_05.png"],  # Clip 2
]
compose_cg(frame_sequences, "output/final.mp4", fps=12.0)
```

## 配置说明

```python
CFG = {
    "gen_image_model": "Qwen/Qwen-Image-Edit-2509",      # 图片编辑模型
    "ltx_root":        "Lightricks/LTX-2.3",             # LTX-2.3 模型路径
    "gemma_root":      "Lightricks/gemma-3-12b-it-...",  # Gemma 文本编码器
    "device":          "cuda",                            # 设备
    "offload":         "none",                            # 卸载模式: none/cpu/disk
}
```

## 依赖项

- torch
- diffusers
- PIL
- ffmpeg（系统命令）
- ltx_core, ltx_pipelines（LTX-2.3）

## 输出结构

```
output/
├── storyboard/          # 每个镜头的起始帧图片
│   ├── shot_00.png
│   ├── shot_01.png
│   └── ...
├── clips/               # 每个镜头的视频片段
│   ├── shot_00.mp4
│   ├── shot_01.mp4
│   └── ...
└── luffy_cg.mp4        # 最终合成视频
```
