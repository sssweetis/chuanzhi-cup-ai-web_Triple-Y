# 给 B 的前端接入包（C 提供 · 10/16）

| 文件 | 用途 |
| --- | --- |
| `api.js` | 直接复制到前端 `src/api/notice.js`，暴露 `analyzeNotice(text)` 和 `health()` |
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