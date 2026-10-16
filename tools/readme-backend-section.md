

---

## 十八、后端服务与联调（C 负责）

后端实现集中在 `backend/` 目录，与 `src/notification_extractor.py`（A 的抽取逻辑）共用同一套 Matter 数据结构，可独立启动、独立自测：

| 文件 | 作用 |
| --- | --- |
| `backend/main.py` | FastAPI 入口：CORS 全放开、参数校验（空文本 / 超长 3000 字）、统一响应结构、`GET /health` |
| `backend/service.py` | 对外抽取接口 `analyze_notification(text)` |
| `backend/notification_extractor.py` | 与 `src/notification_extractor.py` 同源：LLM 调用 + Matter 结构 + JSON Schema 校验 |
| `backend/check_env.py` | 环境自检（Python / 依赖 / .env / 端口 / 抽取链路） |
| `backend/test_llm.py` | 大模型密钥连通性验证（`--mock` 可离线自检，不消耗额度） |
| `backend/smoke_test.py` | 接口回归自测 10 项（空文本、超长、CORS、Mock 性能等） |
| `backend/for-frontend/` | 给前端的接入包：`api.js`（`analyzeNotice` 封装）+ 环境变量示例 |
| `backend/configure_env.ps1` | 交互式配置密钥，写入本地 `.env`（不入库） |

**启动（Windows）**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # 默认 Mock 模式，无需 API Key
python check_env.py             # 应输出「环境就绪」
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**接口约定**

- `POST /api/analyze`：请求 `{"text": "通知原文"}`，响应恒定 HTTP 200 + `{success, data, error}`
- `GET /health`：返回 `{"status": "ok", "mode": "mock" 或 "real"}`
- 参数校验：空文本 → `通知内容不能为空`；超长 → `通知过长，当前N字符，上限3000`
- 完整字段结构与调用示例见 `docs/接口契约.md`

**密钥安全**：本地 `.env` 已在 `.gitignore` 中，仓库只保留 `backend/.env.example`（比赛要求：API 密钥不得出现在公开仓库）。

**待办**：`backend/notification_extractor.py` 与 `src/notification_extractor.py` 目前是同源双份，后续合并为单一来源，避免两处维护。

> 提交物对照清单与评分维度见 `docs/比赛要求与评分标准.md`，环境变量与部署说明见 `docs/环境配置与运行说明.md`。