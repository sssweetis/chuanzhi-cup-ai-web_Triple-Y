# 通知抽取服务（后端 · C 负责）

校园通知原文 → 结构化 **Matter JSON**（截止时间 / 材料清单 / 步骤 / 风险预警）。
FastAPI 提供 HTTP 接口，前端 B 跨域直接调用；抽取逻辑来自 A 的 `service.py` + `notification_extractor.py`（**未改动字段命名、模式判定、复杂度评分**）。

---

## 1. 目录结构

```
backend/
├── main.py                   # C：FastAPI 入口（CORS / 参数校验 / 统一响应 / /health）
├── service.py                # A：对外抽取接口 analyze_notification()
├── notification_extractor.py # A：LLM 调用 + Matter 结构与 Schema 校验（v2，见第 10 节变更记录）
├── check_env.py              # C：服务端环境自检（Python/依赖/.env/模式/端口/链路）
├── test_llm.py               # C：大模型密钥连通性验证（真实调用 / --mock 离线）
├── smoke_test.py             # C：接口自测 10 项（只看标准库）
├── smoke_test_check.py       # C：/api/check 用户情况核对自测（10 项）
├── requirement_checker.py   # C：缺项核对规则（10/18 里程碑，纯确定性逻辑）
├── check_sync.py            # C：核对 backend/ 与 src/ 的抽取模块是否同步
├── configure_env.ps1 / .sh   # C：交互式配置 .env（隐藏输入密钥）
├── for-frontend/             # C：给 B 的接入包（api.js + env.example）
├── requirements.txt          # 运行时依赖
├── .env.example              # 环境变量模板（复制成 .env）
├── .env                      # 本地配置（含密钥时不要提交，已 gitignore）
├── run.sh / run.ps1          # 一键启动
└── .venv/                    # 本地虚拟环境（不入库）
```

---

## 2. 准备服务端调用环境

```powershell
cd "C:\Users\34683\Desktop\Triple Y\backend"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

本目录里 `.venv` 和 `.env` 已经就绪、依赖已装好，可直接跳到第 3 步。

**环境自检（推荐先跑一遍，可直接截图当交付证据）**：

```powershell
python check_env.py
```

输出示例：

```
✅ Python 3.14.7     ...\.venv\Scripts\python.exe
✅ 依赖 fastapi / uvicorn / pydantic / dotenv / openai / jsonschema
✅ .env 配置文件
✅ LLM_API_KEY 未配置  → 当前模式 = mock（返回虚构数据，用于前端联调）
✅ 文本长度上限 3000 字符
✅ 端口 8000 空闲
✅ 抽取链路可用（service.analyze_notification） mode=simple 耗时=12 ms
环境就绪 ✅
```

---

## 3. 启动服务

```powershell
# 方式一：官方命令（演示用这个）
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 方式二：一键脚本
powershell -ExecutionPolicy Bypass -File .\run.ps1    # Windows
bash run.sh                                          # macOS / Linux / Git Bash

# 方式三：直接跑入口
python main.py
```

验证：浏览器打开 <http://127.0.0.1:8000/health> → `{"status":"ok","mode":"mock"}`；接口文档 <http://127.0.0.1:8000/docs>。

---

## 4. 接口契约（不得修改）

| 接口 | 说明 |
| --- | --- |
| `GET /health` | `{"status":"ok","mode":"mock"或"real"}` |
| `POST /api/analyze` | `{"text":"通知原文"}` → `{"success":bool,"data":Matter JSON 或 null,"error":str 或 null}` |
| `POST /api/check` | 用户情况核对：传 `matter`（或 `text`）+ `checked_material_ids` + `profile` → 返回还缺哪些材料、哪些需要确认（纯规则，不调用模型） |
| `GET /` | 服务信息（演示用） |
| `GET /docs` | 自动生成的接口文档 |

成功响应（simple 模式）：

```json
{
  "success": true,
  "error": null,
  "data": {
    "schema_version": "1.0",
    "id": "matter_12b1dcb2",
    "mode": "simple",
    "mode_source": "auto",
    "complexity_score": 0.2,
    "title": "提交奖学金报名表",
    "priority": "medium",
    "status": "not_started",
    "status_source": "auto",
    "timezone": "Asia/Shanghai",
    "created_at": "2026-10-16T17:34:15+08:00",
    "updated_at": "2026-10-16T17:34:15+08:00",
    "detected_features": ["has_deadline"],
    "enabled_sections": ["summary", "schedule", "source"],
    "deadline": {
      "scope": "overall",
      "label": "截止时间",
      "all_day": false,
      "due_at": "2026-10-25T18:00:00+08:00",
      "source_ref": { "quote": "请于10月25日18:00前提交" }
    },
    "reminders": [
      { "reminder_id": "rem_1", "offset_minutes": 120, "channels": ["app"], "enabled": true }
    ],
    "sources": [{ "quote": "请于10月25日18:00前提交", "page": null }]
  }
}
```

> simple 模式**不会**出现 `materials` / `step_list` / `attachments` / `warning_list`（由 A 的 `enforce_mode()` 裁剪，已回归验证）。

---

## 5. 前端 B 的连接入口

接入包在 `for-frontend/`：

| 文件 | 用途 |
| --- | --- |
| `for-frontend/api.js` | 复制到前端 `src/api/notice.js`，暴露 `analyzeNotice(text)` / `health()` |
| `for-frontend/env.example` | 那一行复制到前端 `.env.local`，指定后端地址 |
| `for-frontend/README.md` | 三步接入手册 + 各模式渲染建议 |

```js
import { analyzeNotice } from "@/api/notice";

const { ok, data, error } = await analyzeNotice(noticeText);
if (!ok) return showToast(error);
// data.mode = simple / standard / complex，按 mode 决定渲染哪些区块
```

要点：
- **不需要配 Vite 代理**，后端已开 CORS（`allow_origins=["*"]`，含 `http://localhost:5173`）。
- 所有响应**始终是 HTTP 200 + 统一结构**（含参数错误、内部异常），B 只判断 `success`，不用处理 FastAPI 默认的 422 `detail`。
- 局域网演示：后端加 `--host 0.0.0.0`，前端 `VITE_API_BASE_URL` 改成 `http://<本机IP>:8000`。

---

## 6. 参数校验规则（入口层，未改 A 的抽取逻辑）

| 情况 | 返回 |
| --- | --- |
| 空字符串 / 只有空白 / 没传 `text` | `{"success":false,"data":null,"error":"通知内容不能为空"}` |
| 长度 > 上限（默认 3000 字符） | `{"success":false,"data":null,"error":"通知过长，当前N字符，上限3000"}` |
| 请求体不是合法 JSON | `{"success":false,"data":null,"error":"请求体格式错误，应为 {\"text\": \"通知原文\"}"}` |
| 正常文本 | 交给 `service.analyze_notification()`，返回 Matter JSON |

改上限（不用改代码）：`.env` 里 `MAX_TEXT_LENGTH=5000`（`0` = 不限制）。

---

## 7. 配置密钥（真实大模型）

### 方式一：交互式脚本（推荐）

```powershell
powershell -ExecutionPolicy Bypass -File .\configure_env.ps1
```

会依次问你 API Key（**隐藏输入，不回显**）、Base URL、模型名、端口，然后写进 `.env`；配了 Key 默认把 `LLM_ENABLE_MOCK` 置 0。也可以一次性传参：

```powershell
powershell -ExecutionPolicy Bypass -File .\configure_env.ps1 -ApiKey "<你的APIKey>" -BaseUrl "https://你的平台接口地址/v1" -Model "<模型名>" -Port 8000
```

### 方式二：手改 `.env`

```env
LLM_ENABLE_MOCK=0
LLM_API_KEY=<在此填入你的APIKey>
LLM_BASE_URL=https://api.openai.com/v1   # 用国内平台就换成对应地址
LLM_MODEL=gpt-4o                         # 与平台匹配的模型名
PORT=8000
```

### 方式三：系统环境变量（比赛演示机器不想留 .env 文件时）

```powershell
$env:LLM_API_KEY="<在此填入你的APIKey>"; $env:LLM_MODEL="gpt-4o"; python -m uvicorn main:app --port 8000
```

### 验证密钥是否真的能用

```powershell
python test_llm.py          # 真实调用一次，打印耗时 + 是否被降级到 mock
python test_llm.py --mock   # 离线自检，不联网、不消耗额度
```

成功输出 `✅ 真实大模型调用成功！`；失败会给出 401 / 404 / 超时 的排查方向。
**改完 `.env` 必须重启服务**，然后看 `/health` 的 `mode`。

> ⚠️ 官方 `/api/analyze` 只有真 Key 才走真实模型：`.env` 里 `LLM_ENABLE_MOCK=1` 且**无 Key** → mock；有 Key → 真实调用（失败时按 `LLM_ENABLE_MOCK` 决定是否降级）。

---

## 8. 验收自查结果（2026-10-16 实测）

```powershell
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000   # 一个窗口
python smoke_test.py                                            # 另一个窗口
```

| 检查项 | 预期 | 实测 |
| --- | --- | --- |
| 空文本 / 空白文本 / 缺 text | success=false，error 非空 | ✅ `通知内容不能为空` |
| 超长文本（3600 字） | success=false，含字符数 | ✅ `通知过长，当前3600字符，上限3000` |
| 边界 3000 字 | 正常返回 | ✅ success=true |
| Mock 模式（无 Key + `LLM_ENABLE_MOCK=1`） | 返回虚构 Matter | ✅ mode=simple，字段完整 |
| 结构正确 | simple 无 materials/step_list/attachments | ✅ 无禁字段 |
| `/health` | `{"status":"ok","mode":"mock"}` | ✅ 配 Key 时 `mode=real` |
| 响应时间（Mock） | 毫秒级 | ✅ 平均 **13~25 ms/次**（20 次） |
| CORS 预检 | 放行 `http://localhost:5173` | ✅ `Access-Control-Allow-Origin: *` |
| 非法 JSON 兜底 | 统一契约，不给 500 | ✅ `请求体格式错误…` |
| A v2 回归（0.6 分档） | 标准通知判 standard，不误判 complex | ✅ score=0.6 → **standard**（修复前会误判 complex） |

A v2 三个样本回归：

```
A-样本1 simple   -> mode=simple    score=0.2
A-样本2 standard -> mode=standard  score=0.6
A-样本3 complex  -> mode=complex   score=0.9
```

---

## 9. 常见问题

1. **改了 `.env` 不生效？** 重启服务。`LLM_ENABLE_MOCK` 是 `notification_extractor` 导入时读取的，所以 `main.py` 里 `load_dotenv()` 必须写在 `import service` 之前（已处理）。
2. **`configure_env.ps1` 报一堆语法错误？** 用 PowerShell 5.1 打开 `.ps1` 时，文件必须带 **UTF-8 BOM**（本目录的脚本已带）。以后自己新建带中文的 `.ps1` 也要注意，否则会按 GBK 解析成乱码。
3. **A 发来的 `.py` 覆盖不了，提示“访问被拒绝”？** 微信接收的文件常带**只读属性**，先执行：
   ```powershell
   (Get-Item .\notification_extractor.py).IsReadOnly = $false
   ```
4. **什么时候 mock、什么时候 real？** 看 `/health` 的 `mode`：有 `LLM_API_KEY` → real；无 Key 且 `LLM_ENABLE_MOCK=1` → mock；无 Key 且没开 Mock → real（会直接报错，用于暴露配置问题）。
5. **Mock 数据是真的吗？** 不是。Mock 由 A 的 `_mock_extract()` 按关键词返回虚构 Matter，仅用于前后端联调；结构是真的、内容是假的。
6. **密钥安全**：`.env` 已在 `.gitignore`；比赛要求密钥只能走环境变量，提交前确认仓库里没有 Key。
7. **上线清理**：A 的 `notification_extractor.py` 里 mock 代码都带 `[MOCK]` 标记，文件顶部有清理清单。

---

## 10. 变更记录

| 日期 | 文件 | 变更 |
| --- | --- | --- |
| 10/16 | `main.py`（C） | 新建：CORS、3000 字上限、空文本校验、统一响应、`/health`、异常兜底 |
| 10/16 | `service.py` / `notification_extractor.py`（A） | 接入，未改动核心逻辑（SHA256 与 A 原文件一致） |
| 10/16 | `notification_extractor.py` → **v2**（A） | 修 1 处精度 bug：`MatterExtractor.process()` 里改成 `score = round(recompute_complexity(features), 3)` 再传给 `decide_mode()`。原写法下 `0.2+0.2+0.2 = 0.6000000000000001 > 0.6` 会把标准通知误判成 complex。同时补了 2 行注释。文件 52337 → 52488 字节，其余无改动 |

> 更新 A 的文件时的标准流程：`(Get-Item .\notification_extractor.py).IsReadOnly = $false` → 覆盖 → `python smoke_test.py` 回归 → 记录到上表。

---

## 11. 待 A / B 确认的一个差异（重要）

- A 的联调清单写：**输入超长文本（>5000 字）不报错，可正常返回**。
- C 的本次需求写：**上限 3000 字符，超长返回 `success=false`**。

当前按 **3000 字符上限** 落地，留了开关：`.env` 里 `MAX_TEXT_LENGTH=10000`（或 `0` 不限制）即可切换成 A 清单的行为。
请 A/B 确认最终策略，确认后我把默认值改一致。

---

## 12.（10/18 里程碑）用户情况核对接口 `POST /api/check`

用途：把**用户填写的实际情况**（勾选了哪些材料、自述情况）和 A 抽出的 Matter 放在一起，返回「还缺什么、什么需要确认」。
**纯规则比对，不调用大模型**，字段命名与 `/api/analyze` 完全一致。

### 请求（三种用法）

```json
{
  "matter": { "...": "上一次 /api/analyze 返回的 data（推荐，不跑模型、最快）" },
  "text": "通知原文（没传 matter 时用它先抽一次）",
  "checked_material_ids": ["mat_1", "mat_2"],
  "profile": { "has_video": false, "people_count": 3 },
  "profile_checks": [ { "key": "has_video", "label": "视频材料", "keywords": ["视频"], "message": "原文要求提交视频，你说还没准备" } ]
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `matter` | 二选一 | 直接传上次的解析结果 → 不跑模型；与 `text` 同时传时以 `matter` 为准 |
| `text` | 二选一 | 通知原文，服务端先跑 `/api/analyze` 再核对（同样受 3000 字上限约束） |
| `checked_material_ids` | 否 | 用户勾选「已准备好」的材料 ID（也接受材料名，容错） |
| `profile` | 否 | 用户自述情况，如 `{"has_video": false}` |
| `profile_checks` | 否 | 自定义自述核对规则；不传则用 `requirement_checker.DEFAULT_PROFILE_CHECKS` |

### 响应

```json
{
  "success": true,
  "error": null,
  "data": {
    "matter": { "...": "原样回显 A 的 Matter JSON" },
    "mode": "standard",
    "required_total": 2,
    "checked": [{ "material_id": "mat_1", "material_name": "报名表", "material_type": "required", "required_by_source": true }],
    "missing_required": [{ "material_id": "mat_2", "material_name": "成绩单", "material_type": "required", "required_by_source": false }],
    "missing_optional": [],
    "unchecked_unspecified": [],
    "need_confirm": [{ "item": "截止时间", "reason": "原文未识别到明确截止时间，建议向发布方确认" }],
    "profile_issues": [],
    "ready": false,
    "ready_ratio": 0.5,
    "summary": "还缺 1 项必交材料：成绩单"
  }
}
```

字段含义：

| 字段 | 说明 |
| --- | --- |
| `missing_required` | **必交**材料里用户还没勾选的（`material_type=required` 或 `required_by_source=true`） |
| `missing_optional` | 可选材料里还没勾选的 |
| `unchecked_unspecified` | 原文没明确是否必交的材料 |
| `need_confirm` | 原文没写清、需要用户去问发布方的（如没有截止时间） |
| `profile_issues` | 用户自述情况与原文要求的冲突（如原文要视频、用户说没有） |
| `ready` / `ready_ratio` | 必交清单是否齐全 + 完成比例，可直接做进度条 |
| `summary` | 一句话结论文案，可直接展示 |

### 自测

```powershell
python smoke_test_check.py            # 10 项
python smoke_test_check.py http://127.0.0.1:8123
```

> 说明：`profile` 的判定规则表是 C 侧的兜底实现（`requirement_checker.DEFAULT_PROFILE_CHECKS`）。
> A 定稿核对规则后，替换规则表或由前端传 `profile_checks` 即可，不需要改接口结构。

