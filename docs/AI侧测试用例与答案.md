# A 侧测试用例与标准答案（10–15 个）

> 整理：A（李丹阳）｜日期：2026-10-29
> 环境：Windows / Python 3.10 / `mode=mock`（团队 DeepSeek Key 未配置）
> 说明：标“✅ 自动化”的用例不依赖 Key；标“⏳ 待 Key”的用例结构/规则已验证，真实模型输出待团队 Key 到位后补记录。

## 1. 用例总表

| 编号 | 类别 | 输入 | 标准答案 / 期望 | 验证方式 |
| --- | --- | --- | --- | --- |
| A01 | 文字·简单通知 | `docs/demo-kit/03-材料视频通知.txt` | `mode=simple`；只保留标题、截止时间、提醒、出处；不出现 materials / step_list / todo_list | C 侧 `smoke_test_acceptance.py` 3/3（Mock）；⏳ 真实模型待 Key |
| A02 | 文字·标准通知 | `docs/demo-kit/01-标准通知-奖学金.txt` | `mode=standard`；提取截止时间、3 项材料、办理步骤、待办；每条带 `source_ref` | C 侧 `smoke_test_acceptance.py` 3/3（Mock）；⏳ 真实模型待 Key |
| A03 | 文字·复杂通知 | `docs/demo-kit/02-完整流程-社会实践.txt` | `mode=complex`；包含审核/依赖/子步骤/预警；`enabled_sections` 含 warnings / governance | C 侧 `smoke_test_acceptance.py` 3/3（Mock）；⏳ 真实模型待 Key |
| A04 | 截图·清晰 | `docs/demo-kit/04-通知截图.png` | 识别出标题、截止日期、材料、人数/金额等；不产生无依据的 `confirmation_needed` | C 侧 `smoke_test_image.py` 6/6（本地 OCR）；⏳ 视觉模型待 Key |
| A05 | 截图·模糊/歧义 | 模糊/遮挡截图 | 看不清的字段写入 `confirmation_needed`，不猜测；其余字段正常输出 | `IMAGE_CHECK_RULES` 规则静态检查；⏳ 真实视觉模型待 Key |
| A06 | PDF·文字型 | `docs/demo-kit/05-文字型通知.pdf` | 成功提取文字并生成 Matter；返回页数、字符数 | C 侧 `smoke_test_pdf.py` 6/6（pypdf）；⏳ 真实模型待 Key |
| A07 | PDF·扫描版 | 无文字层 PDF | `success=false` 或明确提示“扫描件请改用清晰截图”，不返回空结果 | C 侧 `smoke_test_pdf.py` 6/6 |
| A08 | RAG·材料内问题 | 上传 `01`/`03`，问“视频有什么要求？” | 回答引用材料原文，附文件名 + 片段编号（+ 页码）；不编造 | C 侧 `smoke_test_files.py` 10/10（检索兜底）；⏳ 真实模型待 Key |
| A09 | RAG·材料外问题 | 问“食堂几点开门？” | 明确“在已上传的材料中没有找到……无法回答”，不给通用常识答案 | C 侧 `smoke_test_files.py` 10/10 |
| A10 | 补充通知·明确以此为准 | `06` + `07` | 截止 11/10→11/08；新增“学院推荐表”；无需额外确认“哪份有效”；保存前仍需用户点确认 | ✅ A 侧 `test_compare_date.py` 样例 1 |
| A11 | 补充通知·没写以此为准 | `08` + `09` | 生成 2 条确认：截止时间以哪份为准、是否取消“指导老师推荐意见”；未确认时 `applied=false`，不覆盖旧清单 | ✅ A 侧 `test_compare_date.py` 样例 2 |
| A12 | 变更确认·版本历史 | 保存 v1 → 修改 → 保存 v2 | `version=2`；`previous_todo_list` 保留 v1；`history` 保留最近 5 版；导出 CSV/Markdown 含最新版本 | C 侧 `smoke_test_hardening.py` 16/16 |
| A13 | 日期工具·周末 | 截止 `2026-11-08 18:00`，当前 `2026-10-31 10:00` | 剩余 8 天；周日；`is_weekend=true`；建议 `2026-11-06 18:00`（周五）前提交；`tool_trace` 包含 `check_date` 调用 | ✅ A 侧 `test_compare_date.py` 日期用例 |
| A14 | 日期工具·过期/无截止 | 截止 `2026-10-30 18:00`；或无 `deadline` | 过期：`is_expired=true`、`risk_level=high`、建议联系对方确认补交；无截止：不调用工具（`mode=skipped`），提示手动补充 | ✅ A 侧 `test_compare_date.py` 边界用例 |
| A15 | 无 Key / 接口失败降级 | 不配置 `LLM_API_KEY`，上传文字/截图 | 文本走离线 Mock，截图走本地 OCR；`/health` 返回 `mode=mock`；页面不白屏，错误有可读提示 | C 侧 `smoke_test.py` / `preflight.py`；✅ 本地 Mock |

## 2. 关键标准答案

### A10：明确“以此为准”的补充通知

```text
变化：
- 截止时间由 2026-11-10 18:00 变为 2026-11-08 18:00
- 新增材料：学院推荐表

受影响待办：
- 更新截止：准备奖学金申请表 → 2026-11-08 18:00
- 更新截止：准备成绩单 → 2026-11-08 18:00
- 更新截止：准备身份证复印件 → 2026-11-08 18:00
- 更新截止：提交材料至行政楼302 → 2026-11-08 18:00
- 新增待办：准备学院推荐表

确认项：无“哪份有效”的歧义；保存前仍需用户确认更新。
```

### A11：没写“以此为准”的补充通知

```text
必须确认：
1. 补充通知未明确说明是否替代原截止时间（原 2026-11-15 17:00，新 2026-11-08 17:00），请确认以哪个为准。
2. 补充通知未明确说明是否取消材料《指导老师推荐意见》，请确认是否还需要提交。

未确认：applied=false，只返回预览与待确认项，不覆盖旧清单。
确认后：移除推荐意见及待办，加入团队安全承诺书及待办；change_log.before 保留旧内容。
```

### A13：日期核对标准答案

```text
due_at: 2026-11-08 18:00
now: 2026-10-31 10:00
days_left: 8
weekday: 周日
is_weekend: true
risk_level: low
suggested_finish_at: 2026-11-06 18:00
suggestion: 截止日 11月08日 是周日，建议在 11月06日（周五）18:00 前提交，避免周末无人审核。
```

### A14：过期与无截止

```text
过期（2026-10-30 18:00，now=2026-10-31 10:00）：
is_expired=true；risk_level=high；建议先联系对方确认能否补交。

无 deadline：
run_date_check_tool_loop 返回 mode=skipped，tool_calls=[]；
suggestions 中包含“通知里没有明确截止时间，请手动补充后再核对”。
```

## 3. 复现命令

```powershell
# A 侧：补充通知 + 日期工具 + 模式裁剪 + 检索 + Prompt 契约（78 项，不需要 Key）
python src/test_compare_date.py

# C 侧：后端接口（需要先启动后端）
cd backend
python smoke_test_hardening.py
python preflight.py
```

## 4. 仍需外部条件、本次不做的用例

| 用例 | 缺少条件 |
| --- | --- |
| 真实 DeepSeek 文本抽取准确率 | 团队 DeepSeek Key |
| 真实视觉模型识别率 | 团队 Key 是否支持图片输入 |
| 真实 Function Calling 的 token/耗时/费用 | 团队 DeepSeek Key |
| 手机 / 另一台电脑布局 | B 或实际设备 |
| 线上三案例复现 | C 部署公网地址 |
| 演示视频成片 | 全队录屏与剪辑 |
