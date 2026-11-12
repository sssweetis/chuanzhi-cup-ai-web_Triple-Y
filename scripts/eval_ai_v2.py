# -*- coding: utf-8 -*-
"""A2：20 条评测 + 15 条 RAG 检索评测。

默认调用真实 DeepSeek Flash（读取 backend/.env），输出：
  docs/eval-v2/results.json
  docs/AI评测记录-v2.md

只写入 D 盘项目目录；不打印/保存 Key。
运行：backend\\.venv\\Scripts\\python.exe scripts\\eval_ai_v2.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / "backend" / ".env")
os.environ.setdefault("LLM_TIMEOUT", "120")

import service  # noqa: E402

EVAL = ROOT / "docs" / "eval-v2"
CASES = json.loads((EVAL / "cases.json").read_text(encoding="utf-8"))
RAG = json.loads((EVAL / "rag_questions.json").read_text(encoding="utf-8"))

# 图片/PDF 用可读期望；文本 case 的期望在 cases.json 中。
ASSET_EXPECT = {
    "I01": {"title": ["奖学金"], "deadline": "2026-11-21", "materials": ["报名表", "成绩单"]},
    "I02": {"title": ["社团"], "deadline": "2026-12-03", "materials": ["活动方案", "安全承诺书"]},
    "I03": {"title": ["证件", "身份证"], "deadline": "2026-11-26", "materials": ["身份证"]},
    "I04": {"title": ["竞赛"], "deadline": "2026-12-06", "materials": ["报名表", "项目说明书", "视频"]},
    "P01": {"title": ["奖学金"], "deadline": "2026-11-20", "materials": ["报名表", "成绩单", "身份证"]},
    "P02": {"title": ["社会实践", "立项"], "deadline": "2026-11-24", "materials": ["申报书", "安全承诺书"]},
    "P03": {"title": ["竞赛", "报名"], "deadline": "2026-12-02", "materials": ["报名表", "项目说明书"]},
}

results = []


def _names(matter):
    return [str(m.get("material_name") or "") for m in (matter.get("materials") or []) if isinstance(m, dict)]


def _title_ok(title, expected):
    title = str(title or "")
    return any(x in title for x in expected) if expected else True


def _deadline_ok(matter, expected):
    if not expected:
        return True
    due = ((matter.get("deadline") or {}).get("due_at") or "")
    return str(due).startswith(expected)


def _materials_ok(matter, expected):
    if not expected:
        return True
    names = " ".join(_names(matter))
    return all(any(x in names for x in [e]) for e in expected)


def _record(kind, cid, label, ok, detail, elapsed, error=None):
    row = {
        "kind": kind,
        "id": cid,
        "label": label,
        "ok": bool(ok),
        "detail": detail,
        "elapsed_ms": round(elapsed * 1000),
        "error": error,
    }
    results.append(row)
    print(("%s %s %s" % ("✅" if ok else "❌", cid, label)) + ("  → %s" % detail if detail else ""))


def run_matter_case(kind, cid, label, fn, expect):
    t0 = time.perf_counter()
    try:
        res = fn()
        elapsed = time.perf_counter() - t0
        if not res.get("success"):
            err = res.get("error")
            msg = err.get("message") if isinstance(err, dict) else str(err)
            _record(kind, cid, label, False, "解析失败", elapsed, msg)
            return
        data = res.get("data") or {}
        checks = []
        if "title" in expect:
            checks.append(("标题", _title_ok(data.get("title"), expect["title"])))
        if "deadline" in expect:
            checks.append(("截止", _deadline_ok(data, expect.get("deadline"))))
        if "materials" in expect:
            checks.append(("材料", _materials_ok(data, expect.get("materials"))))
        if "min_steps" in expect:
            checks.append(("步骤", len(data.get("step_list") or []) >= expect["min_steps"]))
        ok = all(v for _k, v in checks) if checks else bool(data)
        detail = "; ".join("%s=%s" % (k, "✓" if v else "✗") for k, v in checks)
        _record(kind, cid, label, ok, detail, elapsed)
    except Exception as e:
        _record(kind, cid, label, False, "异常", time.perf_counter() - t0, type(e).__name__ + ": " + str(e)[:120])


def run_compare(case):
    t0 = time.perf_counter()
    try:
        res = service.compare_notifications(case["left"], case["right"], use_llm=True)
        elapsed = time.perf_counter() - t0
        if not res.get("success"):
            err = res.get("error")
            msg = err.get("message") if isinstance(err, dict) else str(err)
            _record("compare", case["id"], "补充通知对比", False, "对比失败", elapsed, msg)
            return
        diff = (res.get("data") or {}).get("diff") or {}
        exp = case.get("expect") or {}
        new_deadline = diff.get("new_deadline") or {}
        old_deadline = diff.get("old_deadline") or {}
        deadline_ok = any(str(d.get("due_at") or "").startswith(exp.get("deadline", ""))
                          for d in (new_deadline, old_deadline) if isinstance(d, dict))
        added_names = " ".join(str(m.get("material_name") or "") for m in (diff.get("added_materials") or []))
        material_ok = (not exp.get("new_material")) or (exp.get("new_material") in added_names)
        ok = bool(deadline_ok and material_ok)
        _record("compare", case["id"], "补充通知对比", ok,
                "deadline=%s ; new_material=%s" % (deadline_ok, material_ok), elapsed)
    except Exception as e:
        _record("compare", case["id"], "补充通知对比", False, "异常",
                time.perf_counter() - t0, type(e).__name__ + ": " + str(e)[:120])


def run_rag():
    print("\n[RAG] 检索命中 / 材料外拒答（本地检索，不调用生成模型）")
    for q in RAG["questions"]:
        t0 = time.perf_counter()
        hits = service.search_relevant_chunks(q["query"], RAG["docs"], top_k=3, score_threshold=0.10)
        elapsed = time.perf_counter() - t0
        if q.get("out_of_scope"):
            ok = len(hits) == 0
            detail = "hits=%d" % len(hits)
        else:
            joined = " ".join(h.get("content", "") for h in hits)
            ok = bool(q.get("expect")) and q["expect"] in joined
            detail = "top=%s" % [h.get("doc_name") for h in hits]
        _record("rag", q["id"], q["query"], ok, detail, elapsed)


def write_report():
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    by_kind = {}
    for r in results:
        k = r["kind"]
        by_kind.setdefault(k, {"total": 0, "pass": 0})
        by_kind[k]["total"] += 1
        by_kind[k]["pass"] += 1 if r["ok"] else 0
    summary = {"total": total, "pass": passed, "rate": round(passed / total, 4) if total else 0,
               "by_kind": by_kind}
    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": os.getenv("LLM_MODEL"),
        "base_url": os.getenv("LLM_BASE_URL"),
        "summary": summary,
        "results": results,
    }
    (EVAL / "results.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# A 侧 AI 评测记录 v2",
        "",
        "> 生成时间：%s ｜ 模型：`%s` ｜ Base URL：`%s`" % (out["generated_at"], out["model"], out["base_url"]),
        "> 说明：真实模型调用；图片/PDF/补充通知会消耗 API 额度。敏感输入只用虚构数据。",
        "",
        "## 1. 总览",
        "",
        "| 类别 | 通过/总数 | 通过率 |",
        "| --- | ---: | ---: |",
    ]
    labels = {"text": "文本", "image": "截图", "pdf": "PDF", "compare": "补充通知", "rag": "RAG 检索"}
    for k, v in by_kind.items():
        lines.append("| %s | %d/%d | %.0f%% |" % (labels.get(k, k), v["pass"], v["total"],
                                                   100 * v["pass"] / max(1, v["total"])))
    lines += [
        "| **合计** | **%d/%d** | **%.0f%%** |" % (passed, total, 100 * passed / max(1, total)),
        "",
        "## 2. 明细",
        "",
        "| 类别 | ID | 检查项 | 结果 | 耗时 | 说明 |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for r in results:
        lines.append("| %s | %s | %s | %s | %dms | %s |" % (
            labels.get(r["kind"], r["kind"]), r["id"], r["label"],
            "✅" if r["ok"] else "❌", r["elapsed_ms"], (r.get("detail") or r.get("error") or "").replace("|", "/")))
    lines += [
        "",
        "## 3. 说明与边界",
        "",
        "- 文本 10 条、截图 4 条、PDF 3 条、补充通知 3 条，共 20 条；RAG 15 条（含 5 条材料外）。",
        "- 截图/PDF 为本次评测生成的虚构通知，不包含真实个人信息。",
        "- RAG 只评检索命中/拒答，不把生成模型的自由回答当作事实依据。",
        "- 失败项保留原因，不删除失败样本；优化后再重跑。",
    ]
    (ROOT / "docs" / "AI评测记录-v2.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nsummary: %d/%d (%.1f%%)" % (passed, total, 100 * passed / max(1, total)))
    print("written:", EVAL / "results.json")
    print("written:", ROOT / "docs" / "AI评测记录-v2.md")


def main():
    print("=" * 70)
    print("A2 真实模型评测 v2  model=%s base_url=%s" % (os.getenv("LLM_MODEL"), os.getenv("LLM_BASE_URL")))
    print("=" * 70)
    for c in CASES["text_cases"]:
        run_matter_case("text", c["id"], c["text"][:26], lambda c=c: service.analyze_notification(c["text"]), c["expect"])
    for c in CASES["image_cases"]:
        raw = (EVAL / c["path"]).read_bytes()
        data_uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        run_matter_case("image", c["id"], c["path"],
                        lambda data_uri=data_uri: service.analyze_notification_from_image(data_uri),
                        ASSET_EXPECT.get(c["id"], c["expect"]))
    for c in CASES["pdf_cases"]:
        path = str(EVAL / c["path"])
        run_matter_case("pdf", c["id"], c["path"],
                        lambda path=path: service.analyze_notification_from_pdf(path),
                        ASSET_EXPECT.get(c["id"], c["expect"]))
    for c in CASES["compare_cases"]:
        run_compare(c)
    run_rag()
    write_report()


if __name__ == "__main__":
    main()
