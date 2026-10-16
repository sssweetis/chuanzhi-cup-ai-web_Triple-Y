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
      headers: { "Content-Type": "application/json" },
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
      headers: { "Content-Type": "application/json" },
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
