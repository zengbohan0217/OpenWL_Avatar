const state = {
  config: null,
  lastControlAt: 0,
  activeMoveKeys: new Set(),
  currentLocomotion: "idle",
  idleTimer: null,
  avatarPresented: false,
};

const $ = (id) => document.getElementById(id);

function setPill(element, ok, text) {
  element.textContent = text;
  element.classList.remove("ok", "bad", "muted");
  element.classList.add(ok ? "ok" : "bad");
}

function log(message, payload) {
  const now = new Date().toLocaleTimeString();
  const suffix = payload === undefined ? "" : `\n${JSON.stringify(payload, null, 2)}`;
  $("logOutput").textContent = `[${now}] ${message}${suffix}\n\n${$("logOutput").textContent}`;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail || response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return body;
}

function assetLabel(asset) {
  const name = asset.name || asset.path;
  if (asset.class === "AnimSequence" && asset.skeleton_name) {
    return `${name} — Skeleton: ${asset.skeleton_name}`;
  }
  return `${name} (${asset.class || "Asset"})`;
}

function fillSelect(select, assets) {
  const previousValue = select.value;
  select.innerHTML = "";
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "请选择";
  select.appendChild(empty);
  for (const asset of assets || []) {
    const option = document.createElement("option");
    option.value = asset.path || "";
    option.textContent = assetLabel(asset);
    select.appendChild(option);
  }
  if (previousValue && [...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  }
}

async function loadConfig() {
  state.config = await api("/api/viewer/config");
  if ($("walkSpeedInput") && state.config.default_walk_speed) {
    $("walkSpeedInput").value = state.config.default_walk_speed;
  }
  if ($("runSpeedInput") && state.config.default_run_speed) {
    $("runSpeedInput").value = state.config.default_run_speed;
  }

  const pixel = await api("/api/viewer/pixel-status");
  const frame = $("pixelFrame");
  const fallback = $("pixelFallback");
  const directLink = $("pixelDirectLink");
  $("pixelMessage").textContent = pixel.message || "";
  if (directLink && state.config.pixel_streaming_url) {
    directLink.href = state.config.pixel_streaming_url;
    directLink.hidden = false;
  }

  if (pixel.configured && pixel.reachable) {
    frame.src = state.config.pixel_streaming_url;
    frame.hidden = false;
    fallback.hidden = true;
    frame.addEventListener("load", () => frame.focus(), { once: true });
    setPill($("pixelStatus"), true, "Pixel page: reachable");
  } else {
    frame.removeAttribute("src");
    frame.hidden = true;
    fallback.hidden = false;
    setPill($("pixelStatus"), false, pixel.configured ? "Pixel Streaming: unreachable" : "Pixel Streaming: not configured");
  }
}

async function refreshStatus() {
  const status = await api("/api/ue/status");
  setPill($("ueStatus"), status.ok, status.ok ? "UE: connected" : "UE: disconnected");
  return status;
}

async function refreshAssets() {
  const groups = await api("/api/assets/groups");
  fillSelect($("avatarSelect"), groups.avatar || []);
  fillSelect($("motionSelect"), groups.motion || []);
  fillSelect($("idleMotionSelect"), groups.motion || []);
  fillSelect($("moveMotionSelect"), groups.motion || []);
  const summary = {
    avatar: (groups.avatar || []).length,
    motion: (groups.motion || []).length,
    effect: (groups.effect || []).length,
    prop: (groups.prop || []).length,
  };
  if (groups._errors) {
    summary.partial_errors = groups._errors;
    log("UE 资产已部分刷新，部分类型查询失败", summary);
    return;
  }
  log("UE 资产已刷新", summary);
}

function actorLabel() {
  return $("actorLabelInput").value.trim() || "OpenWL_Presentation_Actor";
}

function forwardOffsetYaw() {
  return Number($("forwardOffsetInput").value) || 0;
}

function faceDirection() {
  return Boolean($("faceDirectionInput")?.checked);
}

function debugKeyboardEnabled() {
  return Boolean($("debugKeyboardInput")?.checked);
}

async function setActorAnimation(motionAssetPath, mode, looping = true) {
  if (!motionAssetPath) {
    return null;
  }
  if (!state.avatarPresented) {
    log("已记录动作选择，展示 Avatar 后再应用", { mode, motion_asset_path: motionAssetPath });
    return null;
  }
  state.currentLocomotion = mode;
  const result = await api("/api/scene/set-animation", {
    method: "POST",
    body: JSON.stringify({
      actor_label: actorLabel(),
      motion_asset_path: motionAssetPath,
      avatar_asset_path: $("avatarSelect").value || "",
      looping,
    }),
  });
  log(`${mode === "move" ? "移动" : "待机"}动作已设置`, result);
  return result;
}

async function ensureLocomotion(mode) {
  if (mode !== "move" && state.currentLocomotion === mode) {
    return;
  }
  const selectId = mode === "move" ? "moveMotionSelect" : "idleMotionSelect";
  const motion = $(selectId).value;
  if (!motion) {
    log(mode === "move" ? "未选择 Move Motion，只执行位置移动" : "未选择 Idle Motion，停下后不切待机动作");
    return;
  }
  if (mode === "idle") {
    state.currentLocomotion = mode;
    const result = await api("/api/scene/play-motion", {
      method: "POST",
      body: JSON.stringify({
        motion_asset_path: motion,
        avatar_asset_path: $("avatarSelect").value || "",
      }),
    });
    log("待机动作已设置（Sequencer）", result);
    return;
  }
  await setActorAnimation(motion, mode, true);
}

function optionalNumber(id) {
  const value = $(id).value.trim();
  if (!value) {
    return null;
  }
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

async function presentPlayableAvatar() {
  const avatar = $("avatarSelect").value;
  if (!avatar) {
    log("请先选择 Avatar");
    return;
  }
  const result = await api("/api/scene/present-playable-avatar", {
    method: "POST",
    body: JSON.stringify({
      avatar_asset_path: avatar,
      idle_animation_path: $("idleMotionSelect").value || "",
      move_animation_path: $("moveMotionSelect").value || "",
      playable_blueprint_path: state.config?.playable_blueprint_path || "/Script/OpenWLPlayable.OpenWLPlayableCharacter",
      actor_label: state.config?.playable_actor_label || "OpenWL_Playable_Character",
      mesh_forward_axis: $("meshForwardSelect").value || "auto",
      mesh_relative_yaw: optionalNumber("meshYawInput"),
      align_to_ground: true,
      ground_z: 0,
      destroy_existing: true,
      walk_speed: optionalNumber("walkSpeedInput"),
      run_speed: optionalNumber("runSpeedInput"),
    }),
  });
  log("可玩角色已启动。请重启/进入 UE Play 或 Standalone 后点击 Pixel Streaming 画面测试 WASD/Space/Shift", result);
  state.avatarPresented = true;
}

async function presentAvatar() {
  const avatar = $("avatarSelect").value;
  if (!avatar) {
    log("请先选择 Avatar");
    return;
  }
  const result = await api("/api/scene/present-avatar", {
    method: "POST",
    body: JSON.stringify({ avatar_asset_path: avatar }),
  });
  log("Avatar 已调试展示（旧 Presentation Actor，不吃 WASD）", result);
  state.avatarPresented = true;
}

async function playMotion() {
  const motion = $("motionSelect").value;
  if (!motion) {
    log("请先选择 Motion");
    return;
  }
  const result = await api("/api/scene/play-motion", {
    method: "POST",
    body: JSON.stringify({ motion_asset_path: motion, avatar_asset_path: $("avatarSelect").value || "" }),
  });
  log("Motion 已播放", result);
}

async function clearScene() {
  const result = await api("/api/scene/clear", { method: "POST", body: "{}" });
  state.avatarPresented = false;
  state.currentLocomotion = "";
  state.activeMoveKeys.clear();
  if (state.idleTimer) {
    clearTimeout(state.idleTimer);
    state.idleTimer = null;
  }
  log("当前展示已清除", result);
}

async function move(direction) {
  const now = Date.now();
  if (now - state.lastControlAt < 120) {
    return;
  }
  state.lastControlAt = now;
  if (!["up", "down"].includes(direction)) {
    await ensureLocomotion("move").catch((err) => log("设置移动动作失败", err.message));
  }
  const offset = forwardOffsetYaw();
  const result = await api("/api/scene/move", {
    method: "POST",
    body: JSON.stringify({
      actor_label: actorLabel(),
      direction,
      step: state.config?.movement_step || 30,
      forward_offset_yaw: offset,
      face_direction: faceDirection(),
    }),
  });
  log(`移动: ${direction} (offset=${offset})`, result);
  if (!["up", "down"].includes(direction)) {
    if (state.idleTimer) {
      clearTimeout(state.idleTimer);
      state.idleTimer = null;
    }
    state.idleTimer = setTimeout(() => {
      state.activeMoveKeys.clear();
      ensureLocomotion("idle").catch((err) => log("设置待机动作失败", err.message));
      state.idleTimer = null;
    }, 700);
  }
}

async function rotate(yawDelta) {
  const now = Date.now();
  if (now - state.lastControlAt < 120) {
    return;
  }
  state.lastControlAt = now;
  const result = await api("/api/scene/rotate", {
    method: "POST",
    body: JSON.stringify({ actor_label: actorLabel(), yaw_delta: Number(yawDelta) }),
  });
  log(`旋转: ${yawDelta}`, result);
}

async function transform() {
  const result = await api(`/api/scene/transform?actor_label=${encodeURIComponent(actorLabel())}`);
  log("当前 Transform", result);
}

function bindEvents() {
  $("refreshAssetsBtn").addEventListener("click", () => refreshAssets().catch((err) => log("刷新资产失败", err.message)));
  $("presentPlayableAvatarBtn").addEventListener("click", () => presentPlayableAvatar().catch((err) => log("启动可玩角色失败", err.message)));
  $("presentAvatarBtn").addEventListener("click", () => presentAvatar().catch((err) => log("展示 Avatar 失败", err.message)));
  $("playMotionBtn").addEventListener("click", () => playMotion().catch((err) => log("播放 Motion 失败", err.message)));
  $("clearSceneBtn").addEventListener("click", () => clearScene().catch((err) => log("清除场景失败", err.message)));
}

async function init() {
  bindEvents();
  try {
    await loadConfig();
    await refreshStatus();
    await refreshAssets();
    log("Viewer 已启动");
  } catch (err) {
    log("Viewer 初始化失败", err.message);
  }
}

init();
