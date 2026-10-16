# 不漏办 · 智能办事清单助手

> 面向所有需要处理书面办事通知人群的智能办事助手。
> 粘贴通知、上传截图或 PDF，AI 自动解析，生成结构化办事清单与材料清单。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-P1%20开发中-orange.svg)

---

## 一、项目简介

**不漏办** 是一款面向学生、社团内勤、职场社会人士的智能办事清单助手。

只要存在**书面办事通知**的场景，都可以用它：

- 🎓 **在校学生**：奖助学金、综测申报、竞赛报名、证件补办、选课退改、评优申报、社团立项、入党材料
- 🏢 **社团 / 单位内勤**：活动立项、场地申请、经费报销、跨部门盖章审批
- 💼 **职场社会人士**：入职材料提交、资质证书办理、社保公积金业务、证件换证、项目申报、行政审批

**一句话价值**：把冗长、碎片化的通知，变成可勾选、可溯源、可提醒的待办清单。

---

## 二、痛点

- 通知文字冗长，要求分散在全文各处
- 人工阅读容易遗漏材料、看错截止时间、混淆办理流程
- 通用大模型回答办事要求时容易编造信息，用户无法核验真假
- 一旦缺材料就需要返工，耗费大量时间反复核对原文

---

## 三、核心功能

### 3.1 P1 最小闭环（本次传智杯实现版本）

| 功能 | 说明 | 状态 |
|---|---|---|
| 文本输入解析 | 粘贴通知文字，LLM 解析为结构化 JSON | ✅ 已完成 |
| 结构化提取 | 事项、材料、时间、地点、办理步骤 | ✅ 已完成 |
| 三层复杂度模式 | simple / standard / complex，按通知复杂度自动裁剪字段 | ✅ 已完成 |
| RAG 原文溯源 | 每条信息绑定原文片段，点击可定位 | ✅ 已完成 |
| 材料清单与勾选 | 区分必填 / 可选，用户勾选已准备项 | 🟡 前端联调中 |
| 缺项核对 | 对比清单，高亮缺失项 | 🟡 前端联调中 |
| 冲突提醒 | 截止时间冲突、材料复用 | ✅ 已完成 |
| 一键待办与提醒 | DDL 前 2 小时自动提醒 | ✅ 已完成 |
| 清单导出 | Markdown / CSV | 🟡 规划中 |
| Web 三栏可视化 | 输入区 / 清单区 / 原文预览区联动 | 🟡 前端联调中 |
| OCR / PDF 解析 | 图片 OCR、PDF 文字抽取 | ⏳ 待开发 |
| 链接 / 语音输入 | 网页链接抓正文、语音转文字 | ⏳ 待开发 |

### 3.2 P2 未来规划（本次比赛不开发，答辩作为延展方向）

- 多文件合并解析
- 复杂多层条件分支解析（如"若是应届生，需额外提交 XX"）
- 待办日历同步（Google Calendar / 飞书 / 系统日历）
- 多人协作共享清单
- 移动端 App

---

## 四、系统架构与全流程

### 4.1 整体流程

```
用户输入（文本 / 图片 / PDF / 链接 / 语音）
        │
        ▼
预处理层（Preprocessor）
  · 图片 OCR
  · PDF 文字抽取
  · 链接抓正文
  · 语音转文字
        │
        ▼
AI 解析层（LLM）
  · 判断复杂度，决定 mode
  · 抽取字段：title / deadline / materials / step_list ...
  · 绑定原文锚点 source_ref
  · 禁止编造：找不到就标注【原文未提及】
        │
        ▼
代码约束层（Python）
  · 复杂度公式重算
  · 字段互斥裁剪
  · enabled_sections 覆盖
  · JSON Schema 校验
        │
        ▼
输出与调度
  · Matter 结构化对象（JSON）
  · DDL 提醒任务（ReminderScheduler）
  · 前端按 enabled_sections 渲染
```

### 4.2 三层复杂度模式

系统会根据通知的复杂程度自动推荐模式，用户也可手动升级。

| 模式 | 适用场景 | 输出字段 | 前端渲染区块 |
|---|---|---|---|
| **simple** | 只有一个 DDL 或一个动作 | 标题、截止时间、提醒 | summary, schedule, source |
| **standard** | 有多个动作、材料、地点 | 加材料清单、附件、地点、步骤 | + content, steps, materials |
| **complex** | 有子步骤、依赖、多角色、审核、冲突 | 全部字段 | + warnings, governance |

**核心设计原则**：

1. 一个完整内核，三种输出外壳
2. 自动推荐模式，用户可覆盖
3. 原文没有的字段不输出、不展示、不追问
4. 空模块不显示
5. 用户可随时从 simple 升级到 standard / complex，升级时自动补抽，不重复问

### 4.3 复杂度评分规则

```
score = 0.2*has_deadline
      + 0.1*has_multiple_reminders
      + 0.2*has_multiple_steps
      + 0.2*has_materials
      + 0.1*has_review
      + 0.1*has_dependencies
      + 0.1*has_recurrence
      + 0.1*has_sub_steps

判定规则（优先级从高到低）：
1. 检测到 has_sub_steps / has_review / has_dependencies → 直接 complex
2. score < 0.3  → simple
3. score ≤ 0.6  → standard
4. score > 0.6  → complex
```

---

## 五、技术栈

| 层 | 技术 |
|---|---|
| 语言 | Python 3.10+ |
| LLM 调用 | OpenAI 兼容接口（支持任意自定义供应商：通义千问、DeepSeek、Moonshot、智谱、字节豆包、硅基流动、Ollama、vLLM 等） |
| 结构化校验 | jsonschema |
| 数据建模 | Python dataclass |
| 时间处理 | datetime + zoneinfo（Asia/Shanghai） |
| 提醒调度 | 自研 ReminderScheduler（轻量、无第三方依赖） |
| 前端（规划） | HTML / CSS / JavaScript（或 Vue / React） |
| 后端（规划） | FastAPI + Uvicorn |
| 版本管理 | Git + GitHub |

---

## 六、目录结构

```
chuanzhi-cup-ai-web_Triple-Y/
├── README.md                       ← 本文件
├── LICENSE                         ← 开源协议
├── .gitignore                      ← Git 忽略规则
├── requirements.txt                ← Python 依赖
│
├── src/                            ← 核心代码
│   ├── notification_extractor.py   ← 文字版通知解析脚本
│   └── service.py                  ← 对外接口（供后端调用）
│
├── docs/                           ← 团队文档
│   ├── 环境变量说明.md
│   ├── 前端渲染字段说明.md
│   ├── UI布局建议稿.md
│   └── JSON结构模板.json
│
├── samples/                        ← 示例输出
│   ├── simple_output.json
│   ├── standard_output.json
│   └── complex_output.json
│
└── tests/                          ← 单元测试（规划中）
    └── test_extractor.py
```

---

## 七、快速开始

### 7.1 环境要求

- Python 3.10 或更高
- Windows / macOS / Linux
- 网络（走真实 LLM 时需要）

### 7.2 安装依赖

```bash
pip install -r requirements.txt
```

### 7.3 开发模式（Mock，无需 API Key）

Windows PowerShell：

```powershell
$env:LLM_ENABLE_MOCK="1"
python src/notification_extractor.py
```

macOS / Linux：

```bash
export LLM_ENABLE_MOCK=1
python src/notification_extractor.py
```

### 7.4 真实模式（调用 LLM）

Windows PowerShell：

```powershell
$env:LLM_API_KEY="sk-xxxxxxxx"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-4o"
python src/notification_extractor.py
```

macOS / Linux：

```bash
export LLM_API_KEY="sk-xxxxxxxx"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-4o"
python src/notification_extractor.py
```

### 7.5 输出示例（simple 模式）

```json
{
  "schema_version": "1.0",
  "id": "matter_b9a224b0",
  "mode": "simple",
  "complexity_score": 0.2,
  "title": "提交奖学金报名表",
  "enabled_sections": ["summary", "schedule", "source"],
  "deadline": {
    "scope": "overall",
    "due_at": "2026-10-25T18:00:00+08:00",
    "source_ref": {"quote": "请于10月25日18:00前提交奖学金报名表。"}
  },
  "reminders": [
    {"reminder_id": "rem_1", "offset_minutes": 120, "channels": ["app"], "enabled": true}
  ],
  "sources": [
    {"quote": "请于10月25日18:00前提交奖学金报名表。"}
  ]
}
```

---

## 八、团队分工

| 角色 | 职责 | 交付物 |
|---|---|---|
| **A（AI 开发）** | 定义 JSON 结构、编写 Prompt、解析逻辑、RAG 锚点生成、缺项校验规则、待办生成，封装 AI 解析能力 | notification_extractor.py、service.py、JSON 结构、Prompt、团队文档 |
| **B（网页端）** | 前端页面渲染、输入组件、清单交互、原文高亮锚点、响应式页面、清单导出 UI | Web 页面（输入区 / 清单区 / 原文预览区） |
| **C（接通与运行）** | 后端服务、接收上传文件 / 文本、路由分发、调用 A 模块、临时文件管理、会话管理、项目打包部署 | FastAPI 后端、部署脚本、环境配置 |

---

## 九、提示词核心设计要点

1. **强制约束**：所有提取的规则、材料、时间，必须在原文找到对应片段，找不到就标注【原文无说明，无法确定】，禁止编造任何信息。
2. **区分必填 / 可选材料**，识别简单条件分支（如"若是应届生，需额外提交 XX"），根据用户身份过滤无关材料。
3. **忠于原文**：不自行扩展额外要求。
4. **字段互斥**：simple 模式禁止出现 owner / materials / step_list / warning_list 等字段。
5. **空数组 / 空对象一律省略**，原文没有的不追问。
6. **相对时间归一化**：以系统注入的 NOW 为基准，转换为绝对时间（ISO 8601 +08:00）。

---

## 十、界面交互设计（三栏布局）

```
┌───────────────┬──────────────────────┬──────────────────────┐
│               │                      │                      │
│   输入区       │   结构化清单区        │   原文预览区          │
│               │                      │                      │
│ · 粘贴文本     │ · 材料勾选框          │ · 通知原文            │
│ · 上传图片     │ · 待办卡片            │ · 点击清单条目自动     │
│ · 上传 PDF    │ · 警告提示面板        │   滚动 + 高亮          │
│ · 文件预览     │ · 导出按钮            │ · 直观展示溯源能力     │
│               │                      │                      │
└───────────────┴──────────────────────┴──────────────────────┘
```

- 适配电脑端，移动端可降级
- 点击清单条目 → 右侧原文自动滚动 + 高亮对应文字

---

## 十一、非功能需求

1. **隐私安全**：不上传、不持久存储用户真实个人数据；演示全部使用虚构测试数据；文件仅用于本次会话解析，支持手动清空缓存。
2. **系统边界**：不对接校务、政务、微信等第三方系统；不自动提交表单；仅做信息整理工具。
3. **安全规范**：大模型 API 密钥部署在后端，前端不存放密钥；限制上传文件大小。
4. **容错降级**：OCR 识别失败时，提示用户手动粘贴文本，保证基础功能可用。

---

## 十二、项目局限性（答辩主动说明）

1. **解析效果依赖输入文件清晰度**：模糊截图会降低 OCR 识别效果。
2. **仅基于用户上传的文件内容解析**：不联网检索外部补充文件，无法识别通知之外的隐性规定。
3. **P1 版本对多层嵌套复杂条件识别能力有限**：复杂逻辑将在后续迭代优化。
4. **当前仅支持文字输入**：图片 / PDF / 链接 / 语音输入待后续迭代。

---

## 十三、开发路线图

- [x] **第 1 阶段（10/14 - 10/16）**：文字通知跑通
  - [x] JSON 结构定义
  - [x] Prompt 编写与调优
  - [x] 文字版解析脚本
  - [x] 三层模式 + 字段互斥 + 提醒调度
  - [x] Mock 开发环境
  - [x] 给 B 与 C 的交付文档
- [ ] **第 2 阶段（10/17 - 10/20）**：端到端联调
  - [ ] C 接通 service.py 与网页后端
  - [ ] B 渲染结构化数据
  - [ ] 三区联动（输入 / 清单 / 原文）
  - [ ] 验收：随便选一套测试通知，三人对照原文检查
- [ ] **第 3 阶段（后续迭代）**：多模态输入
  - [ ] OCR（图片 / 截图）
  - [ ] PDF 解析
  - [ ] 网页链接抓取
  - [ ] 语音转文字
- [ ] **第 4 阶段**：P2 功能
  - [ ] 多文件合并解析
  - [ ] 复杂条件分支
  - [ ] 日历同步
  - [ ] 多人协作

---

## 十四、接口数据结构

A 模块输出、C 模块传输、B 模块渲染的统一数据格式。

### 顶层字段

| 字段 | 类型 | 说明 |
|---|---|---|
| schema_version | string | 固定 "1.0" |
| id | string | 事项唯一 ID |
| mode | string | simple / standard / complex |
| mode_source | string | auto / user |
| complexity_score | number | 0~1 |
| detected_features | array | 检测到的特征（如 has_deadline） |
| enabled_sections | array | 前端要渲染的区块 |
| title | string | 事项名称 |
| priority | string | low / medium / high / urgent |
| status | string | 事项状态 |
| deadline | object | 截止时间 |
| reminders | array | 提醒列表 |
| materials | array | 材料清单 |
| step_list | array | 步骤列表（支持递归） |
| warning_list | array | 预警列表（仅 complex） |
| sources | array | 原文出处 |

### enabled_sections 与前端区块对应

| section 值 | 对应区块 | 主要字段 |
|---|---|---|
| summary | 摘要卡 | title / background / target / category / priority |
| schedule | 时间与提醒 | deadline / reminders |
| content | 要点与附件 | key_points / attachments |
| steps | 步骤流程 | step_list |
| materials | 材料清单 | materials |
| warnings | 预警提示 | warning_list |
| governance | 权限与协作 | permissions / audit_log / comments |
| source | 原文出处 | sources |

完整 JSON 结构详见 [`docs/JSON结构模板.json`](docs/JSON结构模板.json)。

---

## 十五、如何贡献

1. Fork 本仓库
2. 新建分支：`git checkout -b feature/your-feature`
3. 提交改动：`git commit -m "feat: 你的改动"`
4. 推送分支：`git push origin feature/your-feature`
5. 提交 Pull Request

### 提交信息规范

- `feat:` 新功能
- `fix:` 修复 bug
- `docs:` 文档改动
- `refactor:` 重构
- `test:` 测试
- `chore:` 杂项

---

## 十六、许可证

本项目采用 [MIT License](LICENSE)。

---

## 十七、致谢

- 第九届传智杯 AI WEB 网页开发挑战赛
- 团队成员：224-19、sssweetis、Yy627757 

---

**不漏办** · 让每一份通知，都能被可靠执行。

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