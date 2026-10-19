/**
 * 本地保存 / 恢复（10/19 里程碑：刷新后不丢）
 *
 * 只依赖浏览器 localStorage，不引入任何库。B 直接复制到前端 src/utils/storage.js 即可。
 *
 *   import { saveSession, loadSession, clearSession } from "@/utils/storage";
 *
 *   // 每次分析成功 / 每次勾选变化后
 *   saveSession({ text, matter, checkedIds, profile });
 *
 *   // 页面加载时
 *   const s = loadSession();
 *   if (s) { textarea.value = s.text; renderMatter(s.matter); ... }
 */

const SESSION_KEY = "notice.session.v1";
const HISTORY_KEY = "notice.history.v1";
const MAX_HISTORY = 10;

function safeGet(key) {
  try {
    return localStorage.getItem(key);
  } catch (e) {
    return null; // 隐私模式 / 被禁用
  }
}

function safeSet(key, value) {
  try {
    localStorage.setItem(key, value);
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * 保存当前会话（原文 + 解析结果 + 勾选 + 用户自述）
 * @param {{text?: string, matter?: object|null, checkedIds?: string[], profile?: object}} session
 * @returns {boolean} 是否保存成功
 */
export function saveSession({ text = "", matter = null, checkedIds = [], profile = {} } = {}) {
  return safeSet(SESSION_KEY, JSON.stringify({ text, matter, checkedIds, profile, savedAt: new Date().toISOString() }));
}

/**
 * 读取上次会话；没有或数据损坏时返回 null
 * @returns {{text: string, matter: object|null, checkedIds: string[], profile: object, savedAt?: string} | null}
 */
export function loadSession() {
  const raw = safeGet(SESSION_KEY);
  if (!raw) return null;
  try {
    const s = JSON.parse(raw);
    return {
      text: s.text || "",
      matter: s.matter || null,
      checkedIds: Array.isArray(s.checkedIds) ? s.checkedIds : [],
      profile: s.profile || {},
      savedAt: s.savedAt,
    };
  } catch (e) {
    return null;
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch (e) { /* ignore */ }
}

/** 追加一条历史记录（最多保留 10 条，最近的在前） */
export function saveHistory({ text = "", matter = null, checkedIds = [], profile = {} } = {}) {
  let list = listHistory();
  list.unshift({ text, matter, checkedIds, profile, savedAt: new Date().toISOString() });
  list = list.slice(0, MAX_HISTORY);
  return safeSet(HISTORY_KEY, JSON.stringify(list));
}

/** @returns {Array<object>} 历史记录（最近的在前） */
export function listHistory() {
  const raw = safeGet(HISTORY_KEY);
  if (!raw) return [];
  try {
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch (e) {
    return [];
  }
}

export function clearHistory() {
  try {
    localStorage.removeItem(HISTORY_KEY);
  } catch (e) { /* ignore */ }
}