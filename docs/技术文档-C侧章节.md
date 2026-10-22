# 技术文档 · C 侧章节（草稿）

> 配合 `docs/技术文档大纲.md` 使用。本文件覆盖大纲的 **3、4.3–4.5、5、6** 章，A 负责的 AI 选型与 Prompt 设计请合并到第 4 章。

## 3. 系统架构设计

系统采用前后端分离的三层结构：

```
浏览器（前端 5173 / 静态托管）
        │  HTTP + JSON / multipart
        ▼
FastAPI 后端（8000）
  ├─ 入口层：CORS、参数校验、统一响应、异常兜底
  ├─ 能力层：文本抽取 / 图片解析 / PDF 提取 / 准备清单 / 查看依据 / 文件检索 / 追问
  ├─ 抽取层：A 的 service.py（Prompt + LLM + Matter 结构 + Schema 校验）
  └─ 存储层：backend/data（准备清单、文件片段索引，JSON 原子写）
        │
        ▼
大模型（OpenAI 兼容接口，可配置）
  文本模型：LLM_MODEL        视觉模型：TEAM_LLM_MODEL
  无 Key 时：离线 Mock + 本地 OCR（RapidOCR）
```

核心设计原则：**模型只负责"读懂"，结构、判定与降级由代码兜底**，保证演示可复现、失败有反馈。

### 接口清单

| 接口 | 作用 |
| --- | --- |
| `POST /api/analyze` | 文字 → Matter |
| `POST /api/check` | 用户勾选 + 自述 → 缺项核对 |
| `POST /api/prepare-list` / `save` / `GET` | 准备清单生成 / 保存 / 读取 |
| `POST /api/evidence`、`/index` | 要求 → 原文依据（无依据标为系统建议） |
| `POST /api/analyze-image` | 截图 → Matter（视觉模型 / 本地 OCR） |
| `POST /api/analyze-pdf` | 文字型 PDF → Matter |
| `POST /api/files`、`GET /api/files`、`POST /api/files/search` | 材料上传、片段编号、检索 |
| `POST /api/ask` | 先检索再回答，附出处，材料外拒答 |
| `GET /health` | 服务状态与当前模式（mock/real） |

所有接口统一返回 `{success, data, error}`，且始终 HTTP 200，前端只需判断 `success`。

## 4.3 输出稳定性（C 侧实现）

1. **复杂度重算**：不采信模型给的分数，用固定公式
   `0.2·deadline + 0.1·多提醒 + 0.2·多步骤 + 0.2·材料 + 0.1·审核 + 0.1·依赖 + 0.1·周期 + 0.1·子步骤`，
   再按 `has_sub_steps/has_review/has_dependencies → complex`、`<0.3 simple`、`0.3–0.6 standard`、`>0.6 complex` 判定。
2. **字段裁剪**：`enforce_mode` 按模式删除互斥字段（simple 不出现 materials/step_list/todo_list 等），保证前端渲染契约稳定。
3. **Schema 校验**：`jsonschema` 校验 Matter 结构，失败直接返回可读错误，不把脏数据交给前端。
4. **三层降级**：真实模型 → 本地 OCR（图片）→ 离线 Mock（无 Key），任一层可用即可演示。

## 4.4 多模态与 OCR（C 侧实现）

- **截图**：`POST /api/analyze-image`，multipart 字段 `image`，JPG/PNG/WEBP，≤5MB。
  有团队 Key 时调用 `analyze_notification_from_image`（多模态 + 截图专用规则：表格/人数/日期/材料/金额，模糊写入 `confirmation_needed`）；
  无 Key 或视觉调用失败时，自动用 **RapidOCR（onnxruntime）** 本地识别，再走统一抽取管道。
- **PDF**：`POST /api/analyze-pdf`，字段 `file`，≤10MB、≤30页，仅文字型；用 pypdf 提取文字。
  扫描版提取不到文字时返回"请改用清晰截图或直接粘贴文字"，避免空结果。
- 统一限制端点：`/api/analyze-image/limits`、`/api/analyze-pdf/limits`，前端提示与后端完全一致。

## 4.5 RAG 与可解释性（C 侧实现）

- **片段编号**：上传材料按 400 字 / 80 字重叠切分，生成 `file_xxx_c1`、`_c2`…，记录 `char_start/char_end`。
- **检索**：`POST /api/files/search` 对片段做中文二元组重叠打分（命中片段 + 精确子串加权），返回文件名、片段号、原文、分数。
- **追问**：`POST /api/ask` 先检索；有 Key 时把检索片段作为上下文交给 `ask_question`，无 Key 时直接返回最相关原文与出处。
- **不敢答**：检索为空时返回"在已上传的材料中没有找到…无法回答"，不调用模型编造。
- **依据**：`POST /api/evidence` 对材料/步骤/待办/附件/截止/预警/要点返回 `source_ref.quote`；无引用的条目标 `is_suggestion=true`，前端以黄色"系统建议"展示。

## 5. 核心功能实现（后端）

- **统一入口**：`main.py` 负责 CORS、参数校验（空文本 / 超长 10000 字）、multipart 大小与格式校验、统一异常兜底。
- **统一管道**：`analysis_pipeline.analyze_with_fallback` 负责"真实模型 / 离线 Mock"切换，文本、PDF、图片三条入口共用。
- **存储**：准备清单（`data/prepare_lists.json`）与文件索引（`data/files.json`）采用线程锁 + 临时文件原子写，容器通过 volume 持久化。
- **状态联动**：勾选材料 → 关联待办自动 `completed`；依赖全部完成 → `blocked` 解除为 `pending`；状态枚举兼容 `pending/completed/blocked/need_confirm`。

## 6. 测试与部署

### 自动化测试（8 套，全部通过）

| 脚本 | 项数 | 覆盖 |
| --- | --- | --- |
| `smoke_test.py` | 10 | 健康检查、正常/空/超长文本、非法 JSON、CORS、Mock 性能 |
| `smoke_test_check.py` | 10 | 缺项差集、全勾选、自述冲突、参数兜底 |
| `smoke_test_prepare.py` | 11 | 生成、保存、读取、修改内容持久化 |
| `smoke_test_evidence.py` | 8 | 索引、单条依据、无依据 → 建议、参数校验 |
| `smoke_test_image.py` | 6 | limits、合法图、格式/大小/空文件 |
| `smoke_test_pdf.py` | 6 | 文字型 PDF、扫描件、页数/大小限制 |
| `smoke_test_files.py` | 10 | 上传、片段编号、检索、追问、材料外拒答 |
| `smoke_test_acceptance.py` | 3 样本 | 三档模式端到端验收 |

### 部署

- Docker：`backend/Dockerfile`（含 pypdf、RapidOCR）+ `docker-compose.yml`，`backend/data` volume 持久化，内置 HEALTHCHECK。
- Nginx 反代 + HTTPS，`proxy_read_timeout 180s`、`client_max_body_size 12m`。
- 详见 `docs/部署说明.md`。