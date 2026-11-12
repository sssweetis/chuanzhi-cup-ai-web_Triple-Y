# A 侧任务完成情况（2026-11-12）

| 任务 | 状态 | 产物/证据 |
| --- | --- | --- |
| A1 统一 AI 失败语义 | ✅ 完成 | `src/ai_error.py`；`service.py` 文本/图片/对比/RAG 统一错误对象；`test_ai_hardening.py` 覆盖 |
| A2 20 条评测集 | ✅ 完成 | `docs/eval-v2/`；`scripts/eval_ai_v2.py`；`docs/AI评测记录-v2.md`；真实模型 **35/35** |
| A3 安全/注入测试 | ✅ 完成 | `docs/安全测试.md`；`test_ai_hardening.py` **28/28**；不泄露 Key/脚本 |
| A4 RAG 混合检索 | ✅ 完成 | `NotificationRetriever.search`：同义扩展 + IDF/BM25 + 短语 + 去重 + 领域锚点；材料外误召回 2/5 → **0/5** |
| A5 工作流 trace + 第二工具 | ✅ 完成 | `workflow_trace`（5 阶段 + date_tool）；`search_materials` 工具；`tool_trace` |
| A6 用户测试 | 🟡 工具完成，待真人执行 | `docs/用户测试/` 任务卡/记录表/汇总脚本；**未填入虚构用户数据** |
| A7 技术文档 AI 章 | ✅ 完成 | `docs/技术文档.md/.html/.pdf` v1.5，27 页；评测、错误语义、混合检索、MCP |
| A8 6:30 技术口播 | ✅ 完成 | `docs/A侧演示口播-6分30秒.md` |
| A9 MCP 适配（P2） | ✅ 完成 | `src/mcp_server.py`；`test_mcp_server.py` 4/4；只读工具，不改变主链路 |

## 复现命令

```powershell
# A 侧确定性回归
cd src
..\backend\.venv\Scripts\python.exe test_compare_date.py
..\backend\.venv\Scripts\python.exe test_ai_hardening.py
..\backend\.venv\Scripts\python.exe test_mcp_server.py

# 真实模型评测（会消耗 API 额度）
cd ..
backend\.venv\Scripts\python.exe scripts\eval_ai_v2.py
```

## 说明

- A6 的真人测试必须由团队找 8–10 名同学执行；AI 不能替代真实用户，因此没有伪造数据。
- A2 截图/PDF 均为虚构通知；未使用真实个人信息。
- 所有新增文件均在 D 盘项目目录，不写 C 盘。
