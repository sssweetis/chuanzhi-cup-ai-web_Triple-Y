# 给 B 的前端接入包（C 提供 · 10/16）

| 文件 | 用途 |
| --- | --- |
| `api.js` | 直接复制到前端 `src/api/notice.js`，暴露 `analyzeNotice(text)`、`checkRequirements({...})` 和 `health()` |
| `env.example` | 里面那一行复制到前端项目根目录的 `.env.local`，指定后端地址 |

## 三步接入

1. 前端项目根目录建 `.env.local`，写 `VITE_API_BASE_URL=http://127.0.0.1:8000`
2. 复制 `api.js` → `src/api/notice.js`
3. 页面里调用：

```js
import { analyzeNotice } from "@/api/notice";

const { ok, data, error } = await analyzeNotice(noticeText);
if (!ok) return showToast(error);      // "通知内容不能为空" / "通知过长，当前3200字符，上限3000"
// data.mode 决定渲染哪些区块：
//   simple   → 标题 + 截止时间 + 提醒
//   standard → 再加 材料清单 / 步骤
//   complex  → 再加 风险预警 / 依赖关系 / 子步骤
```

## 注意

- **不需要配 Vite 代理**：后端已开 CORS（允许所有来源，包含 `http://localhost:5173`）。
- 想用局域网给同学演示：后端启动加 `--host 0.0.0.0`，然后把 `VITE_API_BASE_URL` 改成 `http://<你的电脑IP>:8000`。
- 当前后端是 **Mock 模式**（无 API Key 时返回虚构 Matter 数据），字段结构是真的，内容不用当真，用于先把前端页面跑通。
- 后端约定的错误码：空文本 / 超长 / 请求体错误都会返回 `success: false` 且 `error` 是中文可读提示，可以直接提示给用户。
## 用户情况核对（10/18）

```js
import { analyzeNotice, checkRequirements } from "@/api/notice";

const first = await analyzeNotice(noticeText);            // 解析一次，拿到 data（含 materials）
const r = await checkRequirements({
  matter: first.data,                                     // 直接传上次结果 → 不重新跑模型
  checkedMaterialIds: ["mat_1"],                          // 用户勾选「已准备」
  profile: { has_video: false },                          // 用户自述情况
});
// r.data.summary            → "还缺 1 项必交材料：成绩单"
// r.data.missing_required   → 高亮缺项
// r.data.profile_issues     → "原文要求提交视频，你说还没准备"
// r.data.ready_ratio        → 进度条
```

## 联调演示页（不用构建，浏览器直接打开）

`backend/for-frontend/demo.html` 是 C 侧的**完整链路演示**：先启动后端，再用浏览器打开它即可。

- 粘贴通知 → 分析 → 展示标题 / 截止时间 / 材料清单 / 步骤 / 风险预警
- 勾选「已准备好的材料」+ 勾选「我还没有准备视频」→ 点核对 → 显示还缺什么、哪些需要确认
- 输入、结果、勾选状态**自动存 localStorage，刷新不丢**（10/19 交付物）

> 这个页面是给验收/前端参考用的实现（原生 JS、单文件）。B 的正式页面按自己的工程结构做即可。

## 本地保存 / 恢复（10/19 里程碑）

`storage.js`：`saveSession` / `loadSession` / `clearSession` / `saveHistory` / `listHistory`

```js
import { saveSession, loadSession } from "@/utils/storage";

// 分析成功、勾选变化后
saveSession({ text, matter, checkedIds, profile });

// 页面加载时
const s = loadSession();
if (s) { textarea.value = s.text; renderMatter(s.matter); }
```
