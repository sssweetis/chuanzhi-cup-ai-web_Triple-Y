# 不漏办 · 智能办事清单助手

> 面向所有需要处理书面办事通知人群的智能办事助手。
> 粘贴通知、上传截图或 PDF，AI 自动解析，生成结构化办事清单与材料清单。

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-P1%20Complete-green.svg)
![Demo](https://img.shields.io/badge/Demo-Mock%20%2B%20Local%20OCR-orange.svg)

> **当前提交版本说明**：团队正式 Key 计划使用 DeepSeek，尚未配置；仓库默认 `LLM_ENABLE_MOCK=1`，文本解析走离线 Mock、截图走本地 OCR。真实模型接入代码已就绪，Key 到位后按 [`docs/真实模型验收记录.md`](docs/真实模型验收记录.md) 补 token / 耗时 / 费用记录。演示数据全部为虚构数据。

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
| 结构化提取 | 事项、材料、时间、地点、办理步骤、待办 | ✅ 已完成 |
| 三层复杂度模式 | simple / standard / complex，按复杂度自动裁剪字段 | ✅ 已完成 |
| RAG 原文溯源 | 每条要求绑定 `source_ref`，无依据标为“系统建议” | ✅ 已完成 |
| 截图解析 | 视觉模型识别；无 Key 自动降级本地 RapidOCR | ✅ 已完成 |
| PDF 解析 | 文字型 PDF 提取文字后接入统一抽取；扫描件明确提示 | ✅ 已完成 |
| 材料清单与勾选 | 区分必填 / 可选，勾选已准备项 | ✅ 已完成 |
| 缺项核对 | 输出已准备 / 缺少 / 需要确认三类结果 | ✅ 已完成 |
| 材料库与追问 | 上传多份材料、片段编号、检索、回答附出处、材料外拒答 | ✅ 已完成 |
| 准备清单保存 / 恢复 | 保存后刷新或重启仍可恢复，带版本历史 | ✅ 已完成 |
| 清单导出 | 服务端导出 CSV（UTF-8 BOM）与 Markdown | ✅ 已完成 |
| 补充通知对比 | 保留两份通知来源，识别改期、增删材料、受影响待办 | ✅ 已完成 |
| 变更确认 | 未确认不覆盖旧清单，确认后保留 `change_log` 旧内容 | ✅ 已完成 |
| 日期核对 | 星期、距今、周末、常见节假日；调休需人工确认 | ✅ 已完成 |
| 会话隔离与删除 | `X-Session-Id` 隔离文件 / 清单 / 对比记录，支持删除 | ✅ 已完成 |
| 限流与密钥安全 | 真实模式按 IP + 路径限流，Key 只从后端环境变量读取 | ✅ 已完成 |
| 待办提醒 | 已生成 DDL 提醒任务；浏览器系统通知未接入 | 🟡 部分完成 |
| 语音输入 | 浏览器原生 SpeechRecognition，实验性 | 🟡 实验性 |
| 网页链接抓正文 | 未实现，列入 P2 | ⏳ 未实现 |
| 登录 / 多用户权限 | 只有会话隔离，没有账号体系 | ❌ 未实现 |

### 3.2 P2 未来规划（本次比赛不开发，答辩作为延展方向）

- 多文件合并解析
- 复杂多层条件分支解析（如“若是应届生，需额外提交 XX”）
- 向量检索 / 重排，提升同义改写与长材料的召回
- 待办日历同步（Google Calendar / 飞书 / 系统日历）
- 多人协作共享清单
- 网页链接抓正文、移动端 App

---

## 四、系统架构与全流程

### 4.1 整体流程

```
用户输入（文字 / 截图 / 文字型 PDF）
        │
        ▼
预处理层
  · 截图 → 视觉模型；无 Key 走本地 RapidOCR
  · PDF → pypdf / pymupdf 提取文字
        │
        ▼
AI 解析层（LLM）
  · 判断复杂度，决定 mode
  · 抽取 title / deadline / materials / step_list / todo_list
  · 绑定原文锚点 source_ref；无依据标 is_suggestion
  · 禁止编造：找不到就省略，不猜
        │
        ▼
代码约束层（Python）
  · 复杂度公式重算，取更高档
  · 字段互斥裁剪 + enabled_sections 覆盖
  · JSON Schema 校验 + 空字段修补 + 降级兜底
        │
        ▼
业务能力层
  · 缺项核对 / 查看依据 / 材料库检索与追问
  · 补充通知对比 / 变更确认 / 版本历史 / 导出
  · 日期核对工具 / DDL 提醒任务 / 会话隔离
        │
        ▼
输出
  · Matter 结构化对象（JSON）
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
| 时间处理 | datetime（Asia/Shanghai） |
| 提醒调度 | 自研 ReminderScheduler（轻量、无第三方依赖） |
| 前端 | HTML / CSS / JavaScript + Vite（原生组件化，无重型框架） |
| 后端 | FastAPI + Uvicorn |
| 图片 OCR | 视觉模型；无 Key 时 RapidOCR + onnxruntime |
| PDF | pypdf / pymupdf |
| 存储 | 本地 JSON 原子写（线程锁 + `os.replace`），Docker volume 持久化 |
| 导出 | CSV（UTF-8 BOM）/ Markdown |
| 部署 | Docker + docker-compose；Render Blueprint（可选在线演示） |
| 测试 | 9 套 smoke test + `preflight.py` 一键自检 + `check_sync.py` |
| 版本管理 | Git + GitHub |

---

## 六、目录结构

```
chuanzhi-cup-ai-web_Triple-Y/
├── README.md                       ← 本文件
├── LICENSE                         ← 开源协议
├── .gitignore                      ← Git 忽略规则
├── requirements.txt                ← Python 依赖（根目录）
├── docker-compose.yml              ← Docker 一键启动
├── render.yaml                     ← Render 在线演示 Blueprint
│
├── backend/                        ← FastAPI 后端
│   ├── main.py                     ← 路由、CORS、参数校验、统一响应
│   ├── service.py                  ← AI 入口（与 src/service.py 同源）
│   ├── prompt.py                   ← Prompt 模板（与 src/prompt.py 同源）
│   ├── notification_extractor.py   ← Matter 结构 / Schema / 复杂度
│   ├── analysis_pipeline.py        ← 真实模型 / Mock 切换
│   ├── prepare_list.py             ← 准备清单、版本历史、导出
│   ├── compare_store.py            ← 双通知对比记录
│   ├── date_tool.py                ← 日期核对（周末/节假日）
│   ├── export_tools.py             ← CSV / Markdown 导出
│   ├── rate_limit.py               ← IP + 路径限流
│   ├── smoke_test_*.py             ← 9 套接口自测
│   ├── preflight.py                ← 演示前一键自检
│   └── data/                       ← 运行时数据（gitignore）
│
├── src/                            ← A 的 AI 工作目录
│   ├── notification_extractor.py   ← 结构定义 / 复杂度 / Schema
│   ├── service.py                  ← 抽取 / 多模态 / RAG / 对比 / 日期工具
│   ├── prompt.py                   ← 6 类 Prompt 模板
│   └── test_compare_date.py        ← 10/29–10/31 A 侧验收脚本
│
├── frontend/                       ← 前端（Vite + 原生 JS）
│   ├── src/components/             ← 输入、清单、结果卡片、日历等
│   ├── src/api.js                  ← 后端接口封装
│   └── src/styles.css              ← 响应式样式
│
├── docs/                           ← 技术文档与演示材料
│   ├── 技术文档.md / .html / .pdf
│   ├── 接口契约.md
│   ├── 环境配置与运行说明.md
│   ├── 部署说明.md
│   ├── 第三阶段测试用例.md
│   ├── AI侧测试用例与答案.md       ← A 侧 15 个 AI 用例与标准答案
│   ├── AI侧答辩速查.md             ← 10 个常见答辩问题
│   ├── 真实模型验收记录.md         ← 团队 DeepSeek Key 到位后补记录
│   └── demo-kit/                   ← 匿名演示通知、截图、PDF、标准答案
│
├── scripts/                        ← 构建与提交前检查
│   ├── build_tech_pdf.ps1          ← Markdown → HTML → PDF
│   └── pre_submit_check.py
│
└── samples/                        ← 示例输出 JSON
```

---

## 七、快速开始

### 7.1 环境要求

- Python 3.10 或更高
- Node.js 18 或更高（前端）
- Windows / macOS / Linux
- 网络（走真实 LLM 时需要；Mock 模式不需要）

### 7.2 启动后端

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

macOS / Linux：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- 健康检查：<http://127.0.0.1:8000/health>
- 接口文档：<http://127.0.0.1:8000/docs>

### 7.3 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开终端提示的地址（默认 <http://localhost:5173>）。

### 7.4 Mock 模式（默认，无需 API Key）

`backend/.env` 默认 `LLM_ENABLE_MOCK=1`：

- 文本解析走离线 Mock（结构真实、内容虚构）；
- 截图走本地 RapidOCR；
- `/health` 返回 `mode=mock`；
- 适合前端联调、录演示视频时明确标注“演示数据”。

### 7.5 真实模型模式

在 `backend/.env` 填写：

```env
LLM_ENABLE_MOCK=0
LLM_API_KEY=<your-deepseek-key>
# 团队正式 Key 计划使用 DeepSeek
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

# 截图视觉模型（可选；若 DeepSeek Key 不含图片输入，留空走本地 OCR）
TEAM_LLM_API_KEY=<your-vision-key>
TEAM_LLM_BASE_URL=<vision-base-url>
TEAM_LLM_MODEL=<vision-model>
```

重启后端，`/health` 返回 `mode=real`。Key 只放后端，禁止提交到仓库或写进前端。

### 7.6 演示数据与自测

- 演示通知、截图、PDF、补充通知对与标准答案：`docs/demo-kit/`
- 单套自测（后端已启动）：
  ```powershell
  cd backend
  python smoke_test_hardening.py
  python preflight.py
  ```
- A 侧 10/29–10/31 验收（无需 Key）：`python src/test_compare_date.py`

### 7.7 输出示例（simple 模式）

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

## 八、团队成员与分工

| 角色 | 姓名 | GitHub 账号 | 负责模块 |
| :--- | :--- | :--- | :--- |
| **A（AI 开发）** | 李丹阳 | 224-19 | 核心 AI 引擎、Prompt 调优、RAG 检索、多模态解析、状态推演与兜底机制 |
| **B（前端开发）** | 敬柯盈 | Yy627757 | 网页 UI 设计、交互逻辑、上传组件、RAG 出处卡片与弹窗提示 |
| **C（后端与运维）** | 方可圆 | sssweetis | 后端 API 路由、文件接收与存储、环境部署、数据库与会话管理 |
---

## 九、提示词核心设计要点

1. **强制约束**：所有提取的规则、材料、时间，必须在原文找到对应片段，找不到就标注【原文无说明，无法确定】，禁止编造任何信息。
2. **区分必填 / 可选材料**，识别简单条件分支（如"若是应届生，需额外提交 XX"），根据用户身份过滤无关材料。
3. **忠于原文**：不自行扩展额外要求。
4. **字段互斥**：simple 模式禁止出现 owner / materials / step_list / warning_list 等字段。
5. **空数组 / 空对象一律省略**，原文没有的不追问。
6. **相对时间归一化**：以系统注入的 NOW 为基准，转换为绝对时间（ISO 8601 +08:00）。
7. **补充通知先对比再更新**：只有明确写“以此为准 / 原通知作废”才直接覆盖；否则改期、删材料必须让用户确认。
8. **日期不靠模型心算**：需要核对截止时间时，模型先调用 `check_date` 工具，再根据工具返回结果生成建议。

---

## 十、界面交互设计

桌面端采用“左侧情况/日历 + 右侧输入/清单”的双栏布局，分析结果卡片内展示材料、步骤、待办与出处：

```
┌───────────────────────┬─────────────────────────────────────────┐
│ 左侧：个人情况 / 日历   │ 右侧：通知输入 / 结构化清单              │
│                       │                                         │
│ · 已准备材料勾选        │ · 粘贴文字 / 上传截图 / 上传 PDF         │
│ · 团队情况（人数/视频）  │ · AI 智能解析 → 结果卡片                 │
│ · 截止日期提醒          │ · 材料清单 / 步骤 / 待办 / 预警          │
│ · 任务日历              │ · 查看依据 / 加入任务清单 / 下载清单      │
└───────────────────────┴─────────────────────────────────────────┘
```

- 桌面端优先，移动端使用单栏响应式布局（基础适配已完成，真机验收仍在进行）
- 点击“出处” → 弹窗展示原文片段；无原文依据的条目标黄色“系统建议”
- 补充通知场景：对比区展示原要求 / 新要求 / 变化 / 受影响待办，确认后才更新清单
- 上传失败、请求失败、解析失败都有明确提示与重试入口

---

## 十一、非功能需求

1. **隐私安全**：演示全部使用虚构数据；文件、清单、对比记录按 `X-Session-Id` 隔离，支持用户主动删除；不接入校务、政务、微信等第三方系统。
2. **系统边界**：只做信息整理，不自动提交表单、不代替用户办理业务。
3. **安全规范**：大模型 Key 只从后端环境变量读取，前端不存放；上传文件有大小/格式/页数限制；真实模式默认限流。
4. **容错降级**：视觉模型不可用 → 本地 OCR；文本模型不可用 → Mock/离线抽取；扫描版 PDF → 提示改用截图，保证基础流程可用。
5. **可解释性**：关键结论带 `source_ref`；查不到依据时明确拒答或标“系统建议”，不编造。
6. **会话边界**：`X-Session-Id` 只是浏览器会话隔离，不是登录鉴权；清除浏览器缓存或换设备会生成新会话。

---

## 十二、项目局限性（答辩主动说明）

> **功能冻结说明**：自 11/07 起不再新增功能，只修复阻断主流程的问题；以下为已知局限，答辩时主动说明。

1. **真实模型效果尚未在本仓库验收**：团队正式 Key（计划 DeepSeek）尚未配置，所有自动化测试和演示数据都是 Mock + 本地 OCR；开发阶段 A 曾用个人 OpenAI Key 做本机联调，但不作为团队验收数据。真实 DeepSeek 文本模型、视觉模型、Function Calling 的准确率、耗时、token、费用还没有实测记录，不能把个人联调或 Mock 结果当成团队真实模型效果。
2. **扫描版 PDF 和复杂版式能力有限**：只支持可复制文字的 PDF；扫描件需要改用截图通道；复杂表格、手写体、印章遮挡的识别精度取决于视觉模型或本地 OCR。
3. **RAG 是词法检索，不是向量检索**：当前用中文二元组重叠、连续字串匹配和词频加权，能覆盖大部分“原文里明确写了”的问题，但对同义改写、跨段落归纳、长材料召回不如 embedding + rerank；检索不到时会拒答，可能漏掉本可回答的问题。
4. **补充通知对比仍可能漏判**：采用“规则差异 + 可选 LLM 语义补充”，对同义改写、跨段落改期、连续多份补充通知的链路还不够稳；改期和删材料默认要求用户确认，避免误覆盖，但也增加了操作步骤。
5. **日期核对不是校历**：只识别周末和常见固定节假日（元旦/劳动节/国庆），不包含农历节日、地方假期和调休；遇到节假日一律提示人工确认，不能替代学校/单位正式通知。
6. **会话隔离不是登录鉴权**：`X-Session-Id` 只用于同一浏览器的数据隔离，换浏览器/清缓存会生成新会话；没有账号体系、权限管理和多人协作，不能据此认为数据“安全隔离”。
7. **复杂业务能力未覆盖**：多层嵌套条件（“若是应届生且已入党……”）、多文件合并解析、日历/飞书同步、网页链接抓正文、移动端 App 均未实现；语音输入依赖浏览器原生 API，属于实验性能力。
8. **提醒没有接入系统通知**：`ReminderScheduler` 能生成 DDL 提醒任务，但浏览器/系统推送尚未接入，当前主要靠清单倒计时和用户主动查看。
9. **在线演示尚未部署**：仓库已提供 Docker / Render 配置，但还没有公网地址；Render 免费实例存在冷启动和重新部署清空本地数据的问题，正式演示前需要预热并准备本地备份。
10. **演示数据是虚构的**：`docs/demo-kit/` 中的通知、姓名、邮箱、金额均为虚构，只用于功能演示；结构真实，但内容不代表任何真实学校或单位。

---

## 十三、开发路线图

- [x] **第 1 阶段（10/14 - 10/20）**：文字通知跑通
  - [x] JSON 结构定义
  - [x] Prompt 编写与调优
  - [x] 文字版解析脚本
  - [x] 三层模式 + 字段互斥 + 提醒调度
  - [x] Mock 开发环境
  - [x] 给 B 与 C 的交付文档

- [x] **第 2 阶段（10/21 - 10/27）**：端到端联调 + 多模态 + RAG
  - [x] C 接通 service.py 与网页后端
  - [x] B 渲染结构化数据
  - [x] 待办生成、修改、保存与恢复
  - [x] 查看依据 / 无依据标系统建议
  - [x] 截图解析（视觉模型 + 本地 OCR 兜底）
  - [x] 文字型 PDF 解析
  - [x] 材料片段编号、检索、追问、材料外拒答

- [x] **第 3 阶段（10/28 - 10/31）**：补充通知与工具调用
  - [x] 双通知对比：保留两份来源，识别改期 / 增删材料 / 冲突
  - [x] 变更联动待办 + 用户确认 + 版本历史
  - [x] 日期核对工具（星期 / 距今 / 周末 / 常见节假日）
  - [x] 清单 CSV / Markdown 导出
  - [x] 会话隔离、删除接口、限流与密钥安全
  - [x] 第三阶段测试用例与加固自测

- [ ] **第 4 阶段（11/01 - 11/10）**：稳定与提交材料
  - [x] 技术文档 4.1 模型选型 / 4.2 Prompt 设计
  - [x] README 功能状态、路线图、局限性更新
  - [x] 重新导出技术文档 PDF（16 页，含 4.1/4.2）
  - [x] AI 侧 15 个测试用例与标准答案
  - [x] 6 分 30 秒视频讲稿与三个演示案例
  - [ ] 真实 Key 验收 + token / 耗时 / 费用记录
  - [ ] 演示视频录制与剪辑
  - [ ] 在线演示部署（可选加分）
  - [x] 最终测试表、复现步骤与已知问题清单
  - [x] AI 侧答辩速查（10 个常见问题）

- [ ] **P2 未来规划**：本次不开发，答辩作为延展
  - [ ] 多文件合并解析
  - [ ] 复杂条件分支
  - [ ] 向量检索 / 重排
  - [ ] 日历 / 飞书同步
  - [ ] 多人协作与账号权限
  - [ ] 网页链接抓正文、移动端 App

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

### 扩展字段（10/28–10/31 新增）

| 字段 | 类型 | 说明 |
|---|---|---|
| `confirmation_needed` | array | 截图看不清、补充通知有歧义时，要求用户确认的项 |
| `suggestions` | array | 日期核对工具生成的准备建议 |
| `date_check` | object | `check_date` 返回的剩余天数、星期、是否周末、风险等级 |
| `tool_trace` | array | 真实工具调用轨迹（工具名、参数、返回结果） |
| `change_log` | object | 补充通知更新前的 `deadline / materials / step_list / todo_list` 快照 |
| `diff` | object | 双通知对比结果：`changes / affected_todos / preview_todo_list` |
| `version` / `history` | number / array | 准备清单版本号与最近 5 版历史 |

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
