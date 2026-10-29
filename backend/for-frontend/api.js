/**
 * 通知抽取服务 · 前端调用入口（B 直接复制到前端项目 src/api/notice.js）
 *
 * 约定：
 *   1. 后端地址从环境变量 VITE_API_BASE_URL 读（见同目录 env.example），不写死在代码里
 *   2. 后端所有响应都是 HTTP 200 + { success, data, error }，这里已经统一转成 { ok, data|error }
 *   3. 后端已开 CORS，本地开发可以直接跨域调用，不需要配 Vite 代理
 *
 * data 结构按 mode 不同：
 *   simple   → title / deadline.due_at / reminders / sources
 *   standard → 上面 + default_location / key_points / attachments / materials / step_list
 *   complex  → 上面 + warning_list / recurrence / step_list 里的 dependencies / review / sub_step_list
 */

const BASE_URL = (
  (import.meta.env && import.meta.env.VITE_API_BASE_URL) || "http://127.0.0.1:8000"
).replace(/\/+$/, "");

const SESSION_KEY = "tripley_session_id";

/** 同一浏览器保持稳定会话；用于文件库、准备清单、通知对比的数据隔离。 */
export function getSessionId() {
  try {
    let value = localStorage.getItem(SESSION_KEY);
    if (!value) {
      value = (globalThis.crypto && crypto.randomUUID)
        ? crypto.randomUUID()
        : `session_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
      localStorage.setItem(SESSION_KEY, value);
    }
    return value;
  } catch {
    return "default";
  }
}

function withSession(headers = {}) {
  return { ...headers, "X-Session-Id": getSessionId() };
}

async function requestJSON(path, { method = "POST", body, timeoutMs = 90000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: withSession({ "Content-Type": "application/json" }),
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const payload = await res.json();
    return payload.success
      ? { ok: true, data: payload.data }
      : { ok: false, error: payload.error || "请求失败" };
  } catch (e) {
    return { ok: false, error: e.name === "AbortError" ? "请求超时，请稍后重试" : `连不上后端服务（${BASE_URL}）` };
  } finally {
    clearTimeout(timer);
  }
}

/** 服务端状态：{ status: "ok", mode: "mock" | "real" } */
export async function health() {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    return await res.json();
  } catch (e) {
    return { status: "down", mode: null, error: String(e) };
  }
}

/**
 * 解析通知原文
 * @param {string} text 通知原文（前端建议先限制在 3000 字内，超长后端会直接返回错误）
 * @param {{ timeoutMs?: number }} [options]
 * @returns {Promise<{ok: true, data: object} | {ok: false, error: string}>}
 */
export async function analyzeNotice(text, { timeoutMs = 90000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}/api/analyze`, {
      method: "POST",
      headers: withSession({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text }),
      signal: controller.signal,
    });
    const payload = await res.json();
    if (!payload.success) {
      return { ok: false, error: payload.error || "解析失败" };
    }
    return { ok: true, data: payload.data };
  } catch (e) {
    if (e.name === "AbortError") {
      return { ok: false, error: `解析超时（> ${timeoutMs / 1000}s），请稍后重试` };
    }
    return {
      ok: false,
      error: `连不上后端服务（${BASE_URL}），请确认已启动：python -m uvicorn main:app --reload --port 8000`,
    };
  } finally {
    clearTimeout(timer);
  }
}

export const API_BASE_URL = BASE_URL;

/**
 * 用户情况核对（10/18 里程碑）：把用户勾选/自述的情况和 Matter 放在一起，返回「还缺什么」
 * @param {{matter?: object, text?: string, checkedMaterialIds?: string[], profile?: object, profileChecks?: object[]}} params
 * @returns {Promise<{ok: true, data: object} | {ok: false, error: string}>}
 *          data.missing_required / data.need_confirm / data.profile_issues / data.ready / data.ready_ratio / data.summary
 */
export async function checkRequirements({ matter, text, checkedMaterialIds = [], profile = {}, profileChecks, timeoutMs = 30000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const payload = { checked_material_ids: checkedMaterialIds, profile };
    if (matter) payload.matter = matter;
    else if (text) payload.text = text;
    if (profileChecks) payload.profile_checks = profileChecks;

    const res = await fetch(`${BASE_URL}/api/check`, {
      method: "POST",
      headers: withSession({ "Content-Type": "application/json" }),
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const body = await res.json();
    if (!body.success) return { ok: false, error: body.error || "核对失败" };
    return { ok: true, data: body.data };
  } catch (e) {
    if (e.name === "AbortError") return { ok: false, error: `核对超时（> ${timeoutMs / 1000}s）` };
    return { ok: false, error: `连不上后端服务（${BASE_URL}）` };
  } finally {
    clearTimeout(timer);
  }
}


/** 双通知对比：每侧 { filename, text }，也支持传已解析的 matter。 */
export async function compareNotifications({ left, right, timeoutMs = 90000 } = {}) {
  return requestJSON("/api/compare", { body: { left, right }, timeoutMs });
}

/** 日期核对：返回 weekday / days_left / is_weekend / is_holiday / is_workday。 */
export async function checkDate(date) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const res = await fetch(`${BASE_URL}/api/tools/check-date?date=${encodeURIComponent(date)}`, {
      headers: withSession(), signal: controller.signal,
    });
    const payload = await res.json();
    return payload.success ? { ok: true, data: payload.data } : { ok: false, error: payload.error };
  } catch (e) {
    return { ok: false, error: e.name === "AbortError" ? "日期核对超时" : "连不上后端服务" };
  } finally {
    clearTimeout(timer);
  }
}

/** 保存准备清单；只有用户点击“保存/确认”时才调用。 */
export async function savePrepareList(payload) {
  return requestJSON("/api/prepare-list/save", { body: payload });
}

/** 读取准备清单当前版本。 */
export async function loadPrepareList(matterId) {
  return requestJSON(`/api/prepare-list/${encodeURIComponent(matterId)}`, { method: "GET" });
}

/** 读取最近 5 个修改前版本。 */
export async function loadPrepareListHistory(matterId) {
  return requestJSON(`/api/prepare-list/${encodeURIComponent(matterId)}/history`, { method: "GET" });
}

/** 导出地址；直接放到 <a href> 下载（浏览器会带上当前 Cookie，但会话头需用 fetch 方案）。 */
export function prepareListExportUrl(matterId, format = "csv") {
  const session = encodeURIComponent(getSessionId());
  return `${BASE_URL}/api/prepare-list/${encodeURIComponent(matterId)}/export?format=${encodeURIComponent(format)}&session_id=${session}`;
}

/** 上传材料（TXT/MD/文字型 PDF），multipart 字段名固定为 file。 */
export async function uploadMaterial(file, timeoutMs = 90000) {
  const fd = new FormData();
  fd.append("file", file);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${BASE_URL}/api/files`, {
      method: "POST", headers: withSession(), body: fd, signal: controller.signal,
    });
    const payload = await res.json();
    return payload.success ? { ok: true, data: payload.data } : { ok: false, error: payload.error };
  } catch (e) {
    return { ok: false, error: e.name === "AbortError" ? "上传超时" : "连不上后端服务" };
  } finally {
    clearTimeout(timer);
  }
}

/** 删除当前会话的数据。 */
export function deletePrepareList(matterId) {
  return requestJSON(`/api/prepare-list/${encodeURIComponent(matterId)}`, { method: "DELETE" });
}

export function deleteFile(fileId) {
  return requestJSON(`/api/files/${encodeURIComponent(fileId)}`, { method: "DELETE" });
}

export function deleteComparison(comparisonId) {
  return requestJSON(`/api/compare/${encodeURIComponent(comparisonId)}`, { method: "DELETE" });
}
