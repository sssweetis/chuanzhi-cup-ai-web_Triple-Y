# A2 评测集 v2

> 20 条结构化评测 + 15 条 RAG 检索评测。  
> 生成：`python docs/eval-v2/generate_cases.py`（只写 D 盘项目目录）。  
> 运行真实模型：`backend\.venv\Scripts\python.exe scripts\eval_ai_v2.py`。  
> 结果：`docs/eval-v2/results.json`、`docs/AI评测记录-v2.md`。

## 文件

| 文件 | 内容 |
| --- | --- |
| `cases.json` | 10 文本 + 4 截图 + 3 PDF + 3 补充通知 |
| `rag_questions.json` | 10 个材料内问题 + 5 个材料外问题 |
| `assets/` | 本次评测生成的虚构截图/PDF |
| `generate_cases.py` | 重新生成样本（不覆盖结果） |

## 评测口径

- 文本检查标题、截止时间、材料、步骤数；
- 截图/PDF 检查标题、截止、材料；
- 补充通知检查 `new_deadline` 与 `added_materials`；
- RAG 只评检索命中/拒答，不把生成模型自由回答当事实；
- 失败项保留，不删除失败样本。

## 2026-11-12 结果

- 结构化 + RAG 合计：**35/35**；
- RAG 材料内 Recall@3：10/10；
- 材料外误召回：旧版 2/5 → 混合检索 **0/5**；
- 模型：`deepseek-flash`（API model ID）。
