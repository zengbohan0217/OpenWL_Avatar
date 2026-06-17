# Serving — UE5 资产导入、Viewer 与场景控制

`serving` 是 OpenWL 的本地 UE 交付层：把已经生成好的 Avatar / Motion / 特效 / 道具等资产导入 UE5，并通过 Gradio、FastAPI Viewer 和 UE 自动化脚本控制当前关卡展示。它不负责生成 3D/4D Avatar 或动作；生成逻辑应留在 `operators/gen_ue_avatar`。

当前最小链路：

```text
上传资产 → 导入 UE → 刷新 UE 资产列表 → 选择 Avatar/Motion → 展示角色 / 播放动作 / 启动可玩角色
```

## 职责边界

```text
operators/gen_ue_avatar
    │  生成 Avatar / Motion / CG 描述等文件
    ▼
serving
    │  上传资产、导入 UE、查询 UE 资产、创建展示 Actor / 可玩角色
    ▼
UE5 Editor / UE Runtime
    │  渲染角色、动作、镜头、特效，接收 Pixel Streaming 输入
    ▼
Frontend
       资产导入页、Viewer 控制页、Pixel Streaming 画面
```

`serving` 不应该放回 `operators/gen_ue_avatar/funcs`，因为 UE 导入和场景展示属于交付层，不属于资产生成层。

## 代码结构

```text
serving/
    api/                    # FastAPI routes：assets / viewer / scene
    services/               # UI/API 业务层：AssetService / SceneService
    ue/                     # UE 自动化层：client、registry、importer、controllers、scripts
    webui/                  # Gradio 导入页、Viewer 启动入口、viewer 静态文件
    ue_client.py            # legacy / compatibility 顶层模块
```

主要调用链：

```text
资产导入：Gradio / asset_routes.py → AssetService → UEClient → AssetImporter → UE Python
资产查询：Viewer / asset_routes.py → AssetService → UEClient → AssetRegistry → UE Asset Registry
场景控制：viewer.js / scene_routes.py → SceneService → UEClient → Scene/Sequence Controller → UE Python / UE Runtime
```

`serving/ue/ue_client.py` 是 UE 自动化 facade，组合 `RemoteControlClient`、`UEPythonRPCClient`、`AssetImporter`、`AssetRegistry`、`SceneController`、`SequenceController`、`EffectController`、`CameraController`。`scene_service.py` 不应该无限变大，UE 细节应继续下沉到 `serving/ue/`。

## 环境变量与默认端口

```text
UE_HOST / UE_PORT             默认 localhost / 30010，用于 UE Remote Control
UE_RPC_HOST                   默认 http://{UE_HOST}:{UE_PORT}
UE_PYTHON_PLUGIN_PATH         UE PythonScriptPlugin/Content/Python 路径
OPENWL_VIEWER_HOST / PORT     默认 127.0.0.1 / 7870
OPENWL_PIXEL_STREAMING_URL    Pixel Streaming 播放页地址；为空则 Viewer 不嵌入画面
NO_PROXY / no_proxy           建议包含 127.0.0.1,localhost
GRADIO_ANALYTICS_ENABLED      本地启动时默认 False
```

如果本机 Python 需要访问 UE 的 `remote_execution.py`，在 PowerShell 里设置：

```powershell
$env:UE_PYTHON_PLUGIN_PATH = "D:\UE\UE_5.4\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python"
```

推荐端口分工：

```text
30010 = UE Remote Control API
7860  = OpenWL 资产上传 / 导入调试页
7870  = OpenWL UE Viewer / Avatar Controller
8080  = Pixel Streaming 浏览器播放页
8888  = UE streamer WebSocket 端口
```

默认 UE 导入目录：`/Game/Imported/Avatars`、`Motions`、`Scenes`、`Effects`、`Materials`、`Textures`、`Props`、`Weapons`。

## 本地启动

### 1. UE5 侧准备

打开 UE5.4 项目，启用：

- `Remote Control API`
- `Python Editor Script Plugin`
- 如果需要 `.glb` / `.gltf`，启用 `glTF / Interchange` 相关导入支持
- 如果走 Remote Execution fallback，启用 Project Settings → Python → Remote Execution

验证 Remote Control：

```text
http://127.0.0.1:30010/remote/info
```

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

### 3. 启动资产上传 / 导入调试页

```powershell
python test/test_ue_serving.py
# 或
python -m serving.webui.gradio_app
```

浏览器打开 `http://127.0.0.1:7860`。这个页面负责检查 UE 连接、刷新 Avatar / Skeleton / Motion 等资产列表、导入 Avatar、按 Avatar Skeleton 导入 Motion、调试展示 Avatar、调试播放 Motion、导入 Scene / Prop / Weapon / Effect / Material / Texture，以及清理当前展示对象。清理只删除关卡里的 OpenWL 展示 Actor / Camera / Sequence，不删除 Content Browser 资产。

### 4. 启动 UE Streaming Viewer / Avatar Controller

```powershell
python -m serving.webui.viewer_app
```

浏览器打开 `http://127.0.0.1:7870`。Viewer 会加载 `/api/viewer/config`、`/api/viewer/pixel-status`、`/api/ue/status` 和 `/api/assets/groups`。如果 `OPENWL_PIXEL_STREAMING_URL` 可访问，页面会把它嵌入 iframe；否则仍显示控制面板和配置提示。

### 5. 配置 Pixel Streaming

先启动 Pixel Streaming Signalling Server，例如：

```powershell
.\run_local.bat --UseFrontend=true --HttpPort=8080 --StreamerPort=8888
```

UE 作为 streamer 连接 `ws://127.0.0.1:8888`。先确认浏览器直接打开 `http://127.0.0.1:8080/player.html` 能看到 UE 画面，再启动 Viewer：

```powershell
$env:OPENWL_PIXEL_STREAMING_URL = "http://127.0.0.1:8080/player.html"
python -m serving.webui.viewer_app
```

注意：`OPENWL_PIXEL_STREAMING_URL` 不要指向 7870 Viewer 自己；代码会检测这种配置并返回 warning。

## Viewer 当前行为

Viewer 不是资产上传页，主要做 UE 画面嵌入和 Avatar 控制：

- “刷新 UE 资产”读取 Avatar / Motion / Effect / Prop 等分组。
- “启动可玩角色”调用 `/api/scene/present-playable-avatar`，创建 `OpenWLPlayableCharacter`，绑定 Avatar、Idle Motion、Move Motion、朝向、地面对齐和走/跑速度。
- “调试展示 Avatar”调用旧的 `/api/scene/present-avatar`，只生成 Presentation Actor，不吃 WASD。
- “调试播放 Motion”调用 `/api/scene/play-motion`，走 Sequencer / debug 播放路径。
- “清除当前展示”调用 `/api/scene/clear`。

正式键鼠输入不走 FastAPI。WASD / 鼠标 / Space / LeftShift 应先点击 Pixel Streaming 画面，让 UE Runtime 自己接收输入并处理 `CharacterMovement`、Camera 和动画状态。如果 7870 内嵌 iframe 不吃键盘，直接打开 8080 Pixel Streaming 原始页面测试。

`viewer.js` 里仍保留 `/api/scene/move`、`/api/scene/rotate`、`/api/scene/transform` helper；测试也覆盖这些 API。但当前 HTML 没有暴露旧移动按钮，它们属于 Editor Python 调试控制，不是最终游戏式移动方案。

## API 概览

```text
GET  /                         viewer.html
GET  /static/*                 viewer 静态文件
GET  /api/health               Viewer 进程健康检查
GET  /api/ue/status            UE Remote Control 连接状态
GET  /api/viewer/config        Viewer 默认配置、actor label、速度、Pixel URL
GET  /api/viewer/pixel-status  Pixel Streaming URL 可达性检查
GET  /api/assets/groups        按 avatar/skeleton/motion/effect/material/texture/prop/weapon 分组
GET  /api/assets?type=motion   查询某类资产
POST /api/scene/present-avatar           旧 debug Avatar 展示
POST /api/scene/present-playable-avatar  创建 Runtime 可玩角色
POST /api/scene/play-motion              调试播放 Motion
POST /api/scene/clear                    清理 OpenWL 展示对象
POST /api/scene/move                     Editor Python 调试移动
POST /api/scene/rotate                   Editor Python 调试旋转
POST /api/scene/set-animation            给 Actor 设置 AnimSequence
GET  /api/scene/transform                读取 Actor transform
POST /api/scene/trigger-skill            placeholder，当前返回 implemented=false
```

异常会被转换成 HTTP 500：`{"detail": "<ExceptionType>: <message>"}`。资产分组查询是例外：单类失败时该类返回空列表，并在 `_errors` 里记录错误，其它类型继续返回。

## 测试

```powershell
python -m pytest test/test_ue_serving.py test/test_viewer_avatar_control.py
```

测试覆盖：Viewer config / schema 默认值、资产分组 partial error、Motion 导入命名包含 Skeleton、`present-playable-avatar` 字段转发、`present-avatar` 仍走旧 debug path、`trigger-skill` placeholder、可玩角色脚本关键 hook、move / rotate / set-animation / transform API，以及非法 direction 返回 422。

Pixel Streaming 键鼠输入由 UE Runtime 处理，仍需要手动 runtime 验证；pytest 不证明 UE 已经推流或输入可用。

## 当前限制

- `AssetService.import_package()`、`SceneController.spawn_prop()`、`SequenceController.create_sequence()`、`UEClient.destroy_actor()`、`UEClient.stop_animation()` 仍未实现。
- `EffectController.spawn_effect()` / `destroy_effect()`、`CameraController.set_camera()` 仍是后续 milestone。
- `/api/scene/trigger-skill` 当前只返回 `implemented=false`。
- Effect 目前偏导入和列表；Socket 绑定、技能触发、生命周期管理还没接上。
- Motion 和 Avatar 的 Skeleton 必须兼容；当前不做 IK Retarget、Control Rig 或自动重定向。
- StaticMesh Avatar 可以被 debug 展示，但不能直接播放 skeletal motion，也不能作为可玩角色。
- `/api/viewer/pixel-status` 只检查 Pixel Streaming 页面 HTTP 可访问，不保证 UE streamer 已连接、有画面或输入正常。
- Gradio 只适合本地调试，不适合作为最终用户端实时 UE 交互页面。
