# A 侧答辩速查（AI 技术）

> 用途：答辩/评审提问时快速定位；不替代技术文档。
> 原则：只讲代码里真实存在的机制。团队 DeepSeek Key 已配置，默认按**真实 DeepSeek Flash**演示；只有临时无 Key 时才切 Mock + 本地 OCR，并明确说明。

## 1. 一句话讲清项目

把一段中文办事通知，变成一份**可勾选、可溯源、可提醒**的清单：每条要求能回到原文，缺什么能直接指出来，补充通知改了什么也能对比并让用户确认。

## 2. 五个技术亮点

| 亮点 | 为什么 | 怎么做 | 代码位置 |
| --- | --- | --- | --- |
| 三档结构化 | 简单通知不需要一堆空模块 | 模型先判断，代码用公式重算复杂度并取更高档，再按模式裁剪字段 | `src/notification_extractor.py` |
| 防幻觉溯源 | 通用模型容易编造要求 | 每条要求带 `source_ref.quote`；无依据标 `is_suggestion=true`；材料外拒答 | `src/prompt.py`、`src/service.py` |
| RAG 追问 | 用户要问“材料里怎么写的” | 先切片段、编号、检索 Top-K，再让模型基于片段回答并附出处 | `NotificationRetriever`、`ask_question_with_rag` |
| 补充通知对比 | 同一事项经常改版 | 分别解析两份通知，对比截止/材料/步骤；受影响待办预览；用户确认后才覆盖，`change_log` 留旧内容 | `compare_notifications`、`apply_notice_changes` |
| 日期工具调用 | 模型心算日期容易错 | 定义 `check_date` 工具；模型先调用，代码执行；无 Key 时也真实执行工具并生成建议 | `DATE_TOOL_SCHEMA`、`run_date_check_tool_loop` |

## 3. 常见提问与回答

### Q1：为什么用通用大模型，不自己微调？

通知场景的难点是“稳定输出结构 + 不编造 + 能和代码规则配合”，不是模型不认识“奖学金”。微调需要标注、训练和持续维护，比赛周期内收益不稳定；当前方案用 Prompt + JSON Schema + 代码约束 + 降级，换供应商只改环境变量。

### Q2：怎么保证模型不瞎编？

三层：
1. Prompt 要求只抽原文，原文没有就省略，禁止输出 `null` 占位；
2. 每条要求带 `source_ref.quote`，无依据的标 `is_suggestion=true`，前端黄色“系统建议”；
3. RAG 追问先检索，检索不到直接“未找到依据”，不调用模型补答。

### Q3：RAG 具体怎么做的？为什么不用向量检索？

当前是轻量词法检索：中文二元组、连续字串匹配、词频覆盖度加权，片段带 `文件-片段ID-页码`。优点是零额外服务、可解释、演示稳定；缺点是同义改写召回弱。向量检索 + rerank 已列 P2，不是本次没做就假装做了。

### Q4：三档模式怎么保证稳定？

模型输出 `detected_features` 和 `mode`，但服务端用固定公式重算 `complexity_score`，按 `has_sub_steps/has_review/has_dependencies → complex`、`<0.3 simple`、`0.3–0.6 standard`、`>0.6 complex` 判定，并取“模型档位”和“公式档位”中更高的一档；最后 `enforce_mode` 裁掉互斥字段。模型不能把复杂通知降成 simple。

### Q5：Function Calling 真的调用了吗？

`DATE_TOOL_SCHEMA` 是标准 OpenAI tools 格式；`_llm_date_tool_loop` 会接收模型返回的 `tool_calls`，执行本地 `check_date`，把结果以 `role=tool` 回传，再让模型总结。真实 DeepSeek Key 已完成调用验证：`tool_trace` 中有 1 次 `check_date`，约 3.17s。没有 Key 时仍走同一套工具执行轨迹（`tool_trace`），只是不做模型总结。

### Q6：补充通知怎么防止误覆盖？

先对比、只出预览；改期/删材料如果没有“以此为准/不再要求”等明确表述，就写入 `confirmation_needed`；`apply_notice_changes` 在 `confirmed=false` 时固定 `applied=false`，确认后才更新，并把旧 `deadline/materials/step_list/todo_list` 存进 `change_log.before`。

### Q7：截图识别不准怎么办？

有视觉模型时走视觉抽取；模型不可用走本地 RapidOCR；对“字迹模糊、表格错位、数字被切断”等视觉歧义写 `confirmation_needed`，让用户确认。注意：原文本来就没写的信息不算“看不清”，不塞进确认项。

### Q8：如果现场临时没有 Key，怎么演示？

团队 DeepSeek Key 已配置，默认按真实模型演示：文本、截图、PDF、RAG 和日期工具均已验证，详见 `docs/真实模型验收记录.md`。如果现场临时没有 Key，再切 Mock + 本地 OCR：文本结构真实、内容虚构；截图走本地 OCR；页面标注“演示数据”，并明确说明是降级模式。

### Q9：和普通 AI 总结有什么区别？

普通总结给一段文字；本项目给可勾选的材料、可排序的步骤、可提醒的 DDL、可点击的原文依据，还能做缺项核对、材料库追问、补充通知对比和用户确认。输出是“能执行的清单”，不是“读后感”。

### Q10：最大的局限是什么？

真实 DeepSeek Flash 已完成首轮验收（`preflight.py` 13/13、加固 19/19、验收 3/3、A 侧 95/95），但样本量仍需扩大；扫描版 PDF 依赖截图；RAG 是词法检索；补充通知语义对比仍可能漏判；日期只覆盖周末/常见固定节假日，调休要人工确认；会话隔离不是登录鉴权；在线演示为可选加分项，当前以本地演示和视频为准。详见 README「项目局限性」。

## 4. 演示口径（必须记住）

- 团队 DeepSeek Key 已配置，`/health` 为 `real`，默认按**真实 DeepSeek Flash**演示；
- 演示前先跑 `preflight.py`，并打开一次 `/health` 预热；真实文本解析约 20–42s，截图/PDF 更久；
- 演示数据为虚构数据，页面可标注“演示数据”，但**不要标成 Mock**；
- 如果现场临时无 Key，再切 Mock + 本地 OCR，并明确说明“当前是降级模式”；
- 不展示 Key、`.env`、控制台账单或任何密钥。
