# OpenWL-Avatar

## 目录结构

```
codes/
├── assets/              # 示例图片和 data.jsonl
├── models/              # 模型 wrapper（每个模型一个文件）
│   ├── gen_image/       # 图像生成（Qwen-Image-Edit 等）
│   ├── gen_3d/          # 3D 生成（Trellis 等）
│   ├── gen_video/       # 视频生成（HunyuanVideo 等）
│   ├── reasoning/       # 视觉语言模型（Qwen-VL 等）
│   └── tools/           # 工具类模型（DepthAnything、分割、去背景等，统一 BaseToolModel）
├── operators/           # 流水线 operator（加载 models，调用 funcs）
│   ├── gen_ue_avatar/   # UE avatar 生成流水线（纯 AI 推理）
│   │   ├── operator.py  # UEAvatarOperator
│   │   └── funcs/       # 解耦功能函数
│   ├── gen_game_cg/     # 游戏 CG 生成流水线
│   │   ├── operator.py  # GameCGOperator
│   │   └── funcs/
│   └── process_input/   # 输入预处理流水线
│       ├── operator.py  # InputProcessor
│       └── funcs/
├── serving/             # HTTP serving + UE5 RPC 交付层
│   ├── server.py        # HTTP API 入口（接收前端请求）
│   └── ue_client.py     # UE5 RPC 调用（推送结果到 UE5）
└── test/                # 测试入口（调用尽可能简单）
```

## 调用逻辑

```
输入请求 (image + text)
     ↓
serving/server.py        ← 接收前端请求
     ↓
InputProcessor           ← operators/process_input/operator.py
     ↓
UEAvatarOperator         ← operators/gen_ue_avatar/operator.py（纯 AI 生成）
  ├── gen_tpose()        ← funcs/gen_tpose.py     (GenImageModel)
  ├── gen_3d_avatar()    ← funcs/gen_3d_avatar.py (Gen3DModel)
  └── gen_motion()       ← funcs/gen_motion.py
     ↓
serving/ue_client.py     ← Python 调 UE5 RPC，推送结果到前端展示

GameCGOperator           ← operators/gen_game_cg/operator.py
  ├── gen_storyboard()   ← funcs/gen_storyboard.py (ReasoningModel)
  ├── gen_cg_video()     ← funcs/gen_cg_video.py   (GenVideoModel)
  └── compose_cg()       ← funcs/compose_cg.py
```

## 快速开始

```python
# 1. 加载 operator（内部自动加载所需模型）
from operators.gen_ue_avatar.operator import UEAvatarOperator
from serving.ue_client import import_avatar_to_ue, import_motion_to_ue

op = UEAvatarOperator({
    "gen_image_model": "/path/to/Qwen-Image-Edit",
    "gen_3d_model":    "/path/to/TRELLIS",
    "device":          "cuda",
})

# 2. 运行 AI 生成流水线
from PIL import Image
ref = Image.open("assets/luffy.jpg")

result = op.run(ref, description="straw hat pirate", motion_desc="walk forward")

# 3. 推送到 UE5（由 serving 层负责）
import_avatar_to_ue(result["mesh_path"])
import_motion_to_ue(result["motion_path"], avatar_name="Avatar")
```

## 扩展新功能

1. 在对应 `funcs/` 目录下新建 `.py` 文件，实现函数
2. 在 `operator.py` 中添加调用方法
3. 在 `models/` 对应子目录添加 model wrapper
4. 在 `test/` 添加测试文件
