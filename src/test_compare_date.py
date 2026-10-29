# -*- coding: utf-8 -*-
"""
10.29 / 10.30 / 10.31 A 侧验收脚本（无需 API Key）

覆盖：
- 10.29 补充通知对比：改期、新增材料、删除材料、受影响待办、用户确认
- 10.30 日期核对工具：真实执行 check_date，并把结果写回建议
- 10.31 两组匿名样例 + 标准答案：用固定 Matter 断言示例答案

运行：
    python src/test_compare_date.py
"""

import copy
import json
import os
import sys
from types import SimpleNamespace

import notification_extractor as ne
import service
from service import (
    apply_notice_changes,
    check_date,
    compare_notifications,
    run_date_check_tool_loop,
    search_relevant_chunks,
    split_into_chunks,
    update_from_supplement,
)

HERE = os.path.dirname(os.path.abspath(__file__))
DEMO_DIR = os.path.join(HERE, "..", "docs", "demo-kit")

NOW = "2026-10-31T10:00:00+08:00"
PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print("✅ %s" % name)
    else:
        FAIL.append(name)
        print("❌ %s  %s" % (name, detail))


def read_demo(filename):
    path = os.path.join(DEMO_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def pair1_matters():
    """样例 1：补充通知明确“以此为准”，改期 + 新增材料。"""
    original = {
        "id": "matter_demo_scholarship",
        "title": "2026年度校级奖学金申报",
        "mode": "standard",
        "deadline": {
            "due_at": "2026-11-10T18:00:00+08:00",
            "source_ref": {"quote": "请于11月10日18:00前提交《奖学金申请表》……"},
        },
        "materials": [
            {"material_id": "mat_1", "material_name": "奖学金申请表", "material_type": "required"},
            {"material_id": "mat_2", "material_name": "成绩单", "material_type": "required"},
            {"material_id": "mat_3", "material_name": "身份证复印件", "material_type": "required"},
        ],
        "step_list": [
            {"step_id": "step_1", "title": "准备申请材料"},
            {"step_id": "step_2", "title": "交至行政楼302办公室"},
        ],
        "todo_list": [
            {"todo_id": "todo_1", "action": "准备奖学金申请表", "status": "pending", "material_id": "mat_1"},
            {"todo_id": "todo_2", "action": "准备成绩单", "status": "pending", "material_id": "mat_2"},
            {"todo_id": "todo_3", "action": "准备身份证复印件", "status": "pending", "material_id": "mat_3"},
            {"todo_id": "todo_4", "action": "提交材料至行政楼302", "status": "pending", "step_id": "step_2"},
        ],
    }
    supplement = {
        "id": "matter_demo_scholarship_supp",
        "title": "2026年度校级奖学金申报（补充）",
        "mode": "standard",
        "deadline": {
            "due_at": "2026-11-08T18:00:00+08:00",
            "source_ref": {"quote": "申报截止时间调整为11月8日18:00"},
        },
        "materials": [
            {"material_id": "mat_1", "material_name": "奖学金申请表", "material_type": "required"},
            {"material_id": "mat_2", "material_name": "成绩单", "material_type": "required"},
            {"material_id": "mat_3", "material_name": "身份证复印件", "material_type": "required"},
            {"material_id": "mat_4", "material_name": "学院推荐表", "material_type": "required"},
        ],
        "step_list": [
            {"step_id": "step_1", "title": "准备申请材料"},
            {"step_id": "step_2", "title": "交至行政楼302办公室"},
        ],
        "todo_list": [],
    }
    return original, supplement


def pair2_matters():
    """样例 2：补充通知没写“以此为准”，改期 + 改材料 → 必须让用户确认。"""
    original = {
        "id": "matter_demo_practice",
        "title": "2026年暑期社会实践立项",
        "mode": "standard",
        "deadline": {
            "due_at": "2026-11-15T17:00:00+08:00",
            "source_ref": {"quote": "各团队须于11月15日17:00前提交……"},
        },
        "materials": [
            {"material_id": "mat_1", "material_name": "实践立项申报表", "material_type": "required"},
            {"material_id": "mat_2", "material_name": "指导老师推荐意见", "material_type": "required"},
        ],
        "step_list": [
            {"step_id": "step_1", "title": "提交电子版"},
            {"step_id": "step_2", "title": "提交纸质版"},
            {"step_id": "step_3", "title": "参加立项答辩"},
        ],
        "todo_list": [
            {"todo_id": "todo_1", "action": "准备实践立项申报表", "status": "pending", "material_id": "mat_1"},
            {"todo_id": "todo_2", "action": "准备指导老师推荐意见", "status": "pending", "material_id": "mat_2"},
            {"todo_id": "todo_3", "action": "提交纸质材料至行政楼305", "status": "pending", "step_id": "step_2"},
        ],
    }
    supplement = {
        "id": "matter_demo_practice_supp",
        "title": "2026年暑期社会实践立项（补充）",
        "mode": "standard",
        "deadline": {
            "due_at": "2026-11-08T17:00:00+08:00",
            "source_ref": {"quote": "立项申报截止时间调整为11月8日17:00"},
        },
        "materials": [
            {"material_id": "mat_1", "material_name": "实践立项申报表", "material_type": "required"},
            {"material_id": "mat_3", "material_name": "团队安全承诺书", "material_type": "required"},
        ],
        "step_list": [
            {"step_id": "step_1", "title": "提交电子版"},
            {"step_id": "step_2", "title": "提交纸质版"},
            {"step_id": "step_3", "title": "参加立项答辩"},
        ],
        "todo_list": [],
    }
    return original, supplement


def test_pair1():
    print("\n" + "=" * 70)
    print("【10.29 样例 1】明确以此为准 → 直接改期 + 新增材料")
    print("=" * 70)
    original_text = read_demo("06-补充通知1-原通知.txt")
    supplement_text = read_demo("07-补充通知1-补充通知.txt")
    original, supplement = pair1_matters()

    compared = compare_notifications(
        original_text, supplement_text,
        original_matter=original, supplement_matter=supplement, use_llm=False,
    )
    check("对比返回成功", compared.get("success"), str(compared.get("error")))
    diff = compared["data"]["diff"]

    texts = [c.get("text", "") for c in diff["changes"]]
    check("识别出改期", any("截止时间由" in t and "11-08" in t for t in texts), str(texts))
    check("识别出新增材料", any("新增材料：学院推荐表" in t for t in texts), str(texts))
    check("明确以此为准 → 不需要确认", diff["requires_confirmation"] is False,
          str(diff.get("confirmation_needed")))
    check("受影响待办包含新增和改期",
          any("新增待办" in t for t in diff["affected_todos"])
          and any("更新截止" in t for t in diff["affected_todos"]),
          str(diff["affected_todos"]))
    check("预览待办数 = 原 4 条 + 新增 1 条", len(diff["preview_todo_list"]) == 5,
          str(len(diff["preview_todo_list"])))

    preview = update_from_supplement(
        original_text, supplement_text,
        original_matter=original, supplement_matter=supplement,
        confirmed=False, use_llm=False,
    )
    check("保存前先返回预览，不直接覆盖", preview["data"].get("applied") is False)
    check("无歧义也要用户点确认", preview["data"].get("requires_user_confirmation") is True)
    check("无歧义时不额外弹出选择", preview["data"].get("requires_confirmation") is False)

    applied = update_from_supplement(
        original_text, supplement_text,
        original_matter=original, supplement_matter=supplement,
        confirmed=True, use_llm=False,
    )
    check("用户确认后应用", applied["data"].get("applied") is True, str(applied["data"].get("applied")))
    matter = applied["data"]["matter"]
    check("新截止时间已写入", matter["deadline"]["due_at"].startswith("2026-11-08"),
          matter["deadline"].get("due_at"))
    check("新材料已写入", any(m.get("material_name") == "学院推荐表" for m in matter["materials"]))
    check("旧清单已留档", matter.get("change_log", {}).get("before", {}).get("deadline", {}).get("due_at", "").startswith("2026-11-10"))


def test_pair2():
    print("\n" + "=" * 70)
    print("【10.29 样例 2】没写以此为准 → 改期 + 换材料必须确认")
    print("=" * 70)
    original_text = read_demo("08-补充通知2-原通知.txt")
    supplement_text = read_demo("09-补充通知2-补充通知.txt")
    original, supplement = pair2_matters()

    compared = compare_notifications(
        original_text, supplement_text,
        original_matter=original, supplement_matter=supplement, use_llm=False,
    )
    check("对比返回成功", compared.get("success"), str(compared.get("error")))
    diff = compared["data"]["diff"]

    check("需要用户确认", diff["requires_confirmation"] is True)
    joined = " ".join(diff["confirmation_needed"])
    check("提示确认截止时间", "截止时间" in joined, joined)
    check("提示确认是否取消推荐意见", "推荐意见" in joined, joined)
    check("受影响待办包含需确认删除", any("需确认是否删除待办" in t for t in diff["affected_todos"]),
          str(diff["affected_todos"]))
    check("新增安全承诺书待办", any("团队安全承诺书" in t for t in diff["affected_todos"]),
          str(diff["affected_todos"]))

    not_confirmed = apply_notice_changes(original, diff, confirmed=False)
    check("未确认时不覆盖清单", not_confirmed["data"].get("applied") is False)
    check("未确认时返回待确认项", len(not_confirmed["data"].get("confirmation_needed") or []) >= 2,
          str(not_confirmed["data"].get("confirmation_needed")))

    confirmed = apply_notice_changes(original, diff, confirmed=True)
    check("确认后才应用", confirmed["data"].get("applied") is True)
    matter = confirmed["data"]["matter"]
    material_names = [m.get("material_name") for m in matter["materials"]]
    todo_actions = [t.get("action") for t in matter["todo_list"]]
    check("推荐意见已移除", "指导老师推荐意见" not in material_names, str(material_names))
    check("安全承诺书已加入", "团队安全承诺书" in material_names, str(material_names))
    check("推荐意见待办已删除", not any("推荐意见" in (a or "") for a in todo_actions), str(todo_actions))
    check("确认后仍保留修改前内容", "before" in matter.get("change_log", {}))


def test_date_tool():
    print("\n" + "=" * 70)
    print("【10.30】日期核对工具（真实执行 check_date）")
    print("=" * 70)
    result = check_date("2026-11-08T18:00:00+08:00", now=NOW)
    check("工具返回成功", result.get("success") is True, str(result.get("error")))
    check("剩余天数 = 8", result.get("days_left") == 8, str(result.get("days_left")))
    check("识别周日", result.get("weekday") == "周日", str(result.get("weekday")))
    check("识别周末", result.get("is_weekend") is True)
    check("建议周五前完成", "11月06日" in result.get("suggestion", ""), result.get("suggestion"))
    check("建议完成时间 = 11月06日 18:00", result.get("suggested_finish_at") == "2026-11-06 18:00",
          str(result.get("suggested_finish_at")))

    original, _ = pair1_matters()
    original["deadline"]["due_at"] = "2026-11-08T18:00:00+08:00"
    traced = run_date_check_tool_loop(original, now=NOW, use_llm=False)
    check("工具调用返回成功", traced.get("success") is True, str(traced.get("error")))
    check("真实执行了 1 次工具调用", len(traced.get("tool_calls") or []) == 1,
          str(traced.get("tool_calls")))
    call = (traced.get("tool_calls") or [{}])[0]
    check("工具名是 check_date", call.get("tool") == "check_date", str(call.get("tool")))
    check("调用参数包含截止时间", "due_at" in (call.get("arguments") or {}), str(call.get("arguments")))
    check("工具结果已写回 date_check", traced["data"].get("date_check", {}).get("days_left") == 8)
    check("工具结果已生成建议", len(traced["data"].get("suggestions") or []) >= 1,
          str(traced["data"].get("suggestions")))

    expired = check_date("2026-10-30T18:00:00+08:00", now=NOW)
    check("过期时间能识别", expired.get("is_expired") is True)
    check("过期风险为 high", expired.get("risk_level") == "high", str(expired.get("risk_level")))


def test_llm_tool_loop_with_fake_client():
    """用假客户端验证 Function Calling 协议：模型调用工具 → 工具结果回传 → 模型总结。"""
    print("\n" + "=" * 70)
    print("【10.30】Function Calling 协议（假客户端，不依赖真实 Key）")
    print("=" * 70)

    class FakeCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                call = SimpleNamespace(
                    id="call_1",
                    function=SimpleNamespace(
                        name="check_date",
                        arguments=json.dumps({"due_at": "2026-11-08T18:00:00+08:00"}),
                    ),
                )
                message = SimpleNamespace(content=None, tool_calls=[call])
            else:
                message = SimpleNamespace(
                    content=json.dumps({
                        "suggestions": ["模型建议：周五前提交"],
                        "risk_level": "low",
                    }),
                    tool_calls=None,
                )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    original, _ = pair1_matters()
    original["deadline"]["due_at"] = "2026-11-08T18:00:00+08:00"
    llm = SimpleNamespace(api_key="fake", base_url="http://fake", model="fake", timeout=1)
    fake = FakeClient()
    result = service._llm_date_tool_loop(original, llm, now=NOW, client=fake)

    check("模型发起了工具调用", result.get("mode") == "llm", str(result.get("mode")))
    check("工具轨迹已记录", len(result.get("tool_calls") or []) == 1)
    check("工具结果已回传给模型", fake.chat.completions.calls == 2,
          str(fake.chat.completions.calls))
    check("模型建议已合并", any("模型建议" in s for s in result["data"].get("suggestions") or []),
          str(result["data"].get("suggestions")))


def test_edge_cases():
    """补充通知、日期工具、模式裁剪、检索与 Prompt 契约的边界用例。"""
    print("\n" + "=" * 70)
    print("【边界用例】防止误删材料 / 冲突判断 / 模式裁剪 / 检索")
    print("=" * 70)
    original, _ = pair1_matters()

    # E01：补充通知只改截止时间，没有重复列材料/步骤 → 不能误删
    supplement = {
        "deadline": {"due_at": "2026-11-08T18:00:00+08:00"},
        "materials": [],
        "step_list": [],
        "todo_list": [],
    }
    compared = compare_notifications(
        "原通知：11月10日18:00前提交报名表。",
        "补充通知：截止时间调整为11月8日18:00。",
        original_matter=original,
        supplement_matter=supplement,
        use_llm=False,
    )
    diff = compared["data"]["diff"]
    check("E01 补充通知没重列材料时不误删", diff["removed_materials"] == [],
          str(diff["removed_materials"]))
    check("E01 待办预览仍保留原 4 条", len(diff["preview_todo_list"]) == 4,
          str(len(diff["preview_todo_list"])))
    applied = apply_notice_changes(original, diff, confirmed=True)
    check("E01 应用后材料仍为 3 项", len(applied["data"]["matter"]["materials"]) == 3,
          str(len(applied["data"]["matter"]["materials"])))

    # E02：补充通知没提截止时间 → 保留原截止时间
    supplement = {
        "materials": original["materials"],
        "step_list": original["step_list"],
        "todo_list": [],
    }
    compared = compare_notifications(
        "原通知：11月10日18:00前提交。",
        "补充通知：请补充填写学院推荐表。",
        original_matter=original,
        supplement_matter=supplement,
        use_llm=False,
    )
    diff = compared["data"]["diff"]
    applied = apply_notice_changes(original, diff, confirmed=True)
    check("E02 没提截止时间时保留原截止",
          applied["data"]["matter"]["deadline"]["due_at"].startswith("2026-11-10"),
          applied["data"]["matter"]["deadline"].get("due_at"))

    # E03：明确写“不再要求” → 直接删材料，不额外弹确认
    supplement = {
        "deadline": original["deadline"],
        "materials": [m for m in original["materials"] if m["material_name"] != "成绩单"],
        "step_list": original["step_list"],
        "todo_list": [],
    }
    compared = compare_notifications(
        "原通知：提交报名表、成绩单。",
        "补充通知：不再要求提交成绩单。",
        original_matter=original,
        supplement_matter=supplement,
        use_llm=False,
    )
    diff = compared["data"]["diff"]
    check("E03 明确取消材料 → 不额外确认", diff["requires_confirmation"] is False,
          str(diff["confirmation_needed"]))
    check("E03 预览里已去掉成绩单待办",
          all("成绩单" not in (t.get("action") or "") for t in diff["preview_todo_list"]))
    applied = apply_notice_changes(original, diff, confirmed=True)
    check("E03 应用后成绩单材料被删除",
          all(m["material_name"] != "成绩单" for m in applied["data"]["matter"]["materials"]),
          str([m["material_name"] for m in applied["data"]["matter"]["materials"]]))

    # E04：材料名带书名号/附件号 → 归一化后不误判为新增/删除
    supplement = copy.deepcopy(original)
    supplement["materials"] = [
        {"material_id": "mat_1", "material_name": "《奖学金申请表》（附件1）", "material_type": "required"},
        {"material_id": "mat_2", "material_name": "成绩单", "material_type": "required"},
        {"material_id": "mat_3", "material_name": "身份证复印件", "material_type": "required"},
    ]
    compared = compare_notifications(
        "原通知", "补充通知",
        original_matter=original, supplement_matter=supplement, use_llm=False,
    )
    diff = compared["data"]["diff"]
    check("E04 名称格式差异不误判新增", diff["added_materials"] == [],
          str([m["material_name"] for m in diff["added_materials"]]))
    check("E04 名称格式差异不误判删除", diff["removed_materials"] == [],
          str([m["material_name"] for m in diff["removed_materials"]]))

    # E05：同名材料重复出现也不崩溃
    duplicate = {
        "deadline": {"due_at": "2026-11-08T18:00:00+08:00"},
        "materials": [
            {"material_id": "mat_a", "material_name": "报名表"},
            {"material_id": "mat_b", "material_name": "报名表"},
        ],
        "step_list": [],
        "todo_list": [],
    }
    compared = compare_notifications(
        "原通知", "补充通知",
        original_matter=duplicate, supplement_matter=duplicate, use_llm=False,
    )
    check("E05 同名材料重复也不崩溃", compared.get("success") is True,
          str(compared.get("error")))

    # E14：补充通知只新增一项材料，不能把没重复列的原材料误报为删除
    supplement = {
        "title": "补充通知",
        "deadline": {"due_at": "2026-11-08T18:00:00+08:00"},
        "materials": [{"material_id": "mat_new", "material_name": "学院推荐表"}],
        "step_list": [],
        "todo_list": [],
    }
    compared = compare_notifications(
        "原通知：提交报名表、成绩单、身份证复印件。",
        "补充通知：新增学院推荐表。",
        original_matter=original,
        supplement_matter=supplement,
        use_llm=False,
    )
    diff = compared["data"]["diff"]
    check("E14 补充通知只新增材料时不误报删除", diff["removed_materials"] == [],
          str([m["material_name"] for m in diff["removed_materials"]]))
    check("E14 补充通知只新增材料时不要求删除确认",
          not any("取消材料" in c for c in diff["confirmation_needed"]),
          str(diff["confirmation_needed"]))
    check("E14 新增材料仍被识别",
          any(m["material_name"] == "学院推荐表" for m in diff["added_materials"]))

    # E15：模型误报 has_review/has_dependencies 时，用原文关键词降级
    text = "请各队于11月2日17:00前提交视频、说明文档和报名表，需指导老师签字。"
    features = ne.sanitize_features(
        ["has_deadline", "has_multiple_steps", "has_materials", "has_review", "has_dependencies"],
        text,
    )
    check("E15 普通签字不被误判为审核", "has_review" not in features, str(features))
    check("E15 并列步骤不被误判为依赖", "has_dependencies" not in features, str(features))
    score = ne.recompute_complexity(features)
    check("E15 误报特征清理后应为 standard", ne.decide_mode(features, score) == "standard",
          str(ne.decide_mode(features, score)))
    kept = ne.sanitize_features(
        ["has_deadline", "has_materials", "has_review", "has_dependencies"],
        "学院审核通过后，于11月20日参加答辩。",
    )
    check("E15 原文有审核/通过后时保留复杂特征",
          "has_review" in kept and "has_dependencies" in kept, str(kept))

    # E16：截图模型返回中文日期时归一化为 ISO
    normalized = service._normalize_deadline_value("11月2日 17:00")
    check("E16 中文日期归一化为 ISO",
          str(normalized.get("due_at", "")).startswith("2026-11-02T17:00"),
          str(normalized))

    # E06–E08：日期工具边界
    invalid = check_date("not-a-date")
    check("E06 非法日期返回失败", invalid.get("success") is False)
    expired = check_date("2026-10-30T18:00:00+08:00", now=NOW)
    check("E07 过期风险为 high", expired.get("risk_level") == "high",
          str(expired.get("risk_level")))
    check("E07 过期建议提示补交", "补交" in expired.get("suggestion", ""),
          expired.get("suggestion"))
    no_due = copy.deepcopy(original)
    no_due.pop("deadline", None)
    skipped = run_date_check_tool_loop(no_due, now=NOW, use_llm=False)
    check("E08 无截止时间不调用工具", skipped.get("mode") == "skipped",
          str(skipped.get("mode")))
    check("E08 无截止时间给出补充提示",
          any("截止时间" in s for s in skipped["data"].get("suggestions") or []))

    # E09：simple 模式必须裁掉材料/步骤/待办
    simple = {
        "schema_version": "1.0", "id": "m1", "mode": "simple", "title": "交表",
        "status": "not_started",
        "materials": [{"material_id": "mat_1", "material_name": "报名表"}],
        "step_list": [{"step_id": "step_1", "title": "交表", "dependencies": ["step_2"]}],
        "todo_list": [{"todo_id": "todo_1", "action": "准备报名表"}],
    }
    clipped = ne.enforce_mode(copy.deepcopy(simple))
    clipped = ne.enforce_enabled_sections(clipped)
    check("E09 simple 裁掉 materials", "materials" not in clipped)
    check("E09 simple 裁掉 step_list", "step_list" not in clipped)
    check("E09 simple 裁掉 todo_list", "todo_list" not in clipped)
    check("E09 simple 区块正确",
          clipped.get("enabled_sections") == ["summary", "schedule", "source"],
          str(clipped.get("enabled_sections")))

    # E10：standard 保留材料/步骤，但裁掉依赖与治理字段
    standard = {
        "schema_version": "1.0", "id": "m2", "mode": "standard", "title": "报名",
        "status": "not_started",
        "materials": [{"material_id": "mat_1", "material_name": "报名表"}],
        "step_list": [{"step_id": "step_1", "title": "交表", "dependencies": ["step_2"]}],
        "audit_log": [{"action": "x"}],
        "warning_list": [
            {"warning_type": "deadline_risk", "message": "时间紧"},
            {"warning_type": "permission", "message": "无权限"},
        ],
    }
    clipped = ne.enforce_mode(copy.deepcopy(standard))
    clipped = ne.enforce_enabled_sections(clipped)
    check("E10 standard 保留 materials", "materials" in clipped)
    check("E10 standard 裁掉 dependencies",
          all("dependencies" not in s for s in clipped.get("step_list") or []))
    check("E10 standard 裁掉 audit_log", "audit_log" not in clipped)
    check("E10 standard 只保留两类预警",
          [w["warning_type"] for w in clipped.get("warning_list") or []] == ["deadline_risk"],
          str(clipped.get("warning_list")))

    # E11：复杂度公式与模式判定
    check("E11 公式重算 0.2", ne.recompute_complexity(["has_deadline"]) == 0.2)
    check("E11 0.2 → simple", ne.decide_mode(["has_deadline"], 0.2) == "simple")
    check("E11 0.4 → standard",
          ne.decide_mode(["has_deadline", "has_materials"], 0.4) == "standard")
    check("E11 has_review → complex", ne.decide_mode(["has_review"], 0.1) == "complex")

    # E12：分段编号与检索
    chunks = split_into_chunks("请提交报名表。演示视频不超过3分钟。", "视频要求.md", "doc_video")
    check("E12 分段生成唯一编号", len({c["chunk_id"] for c in chunks}) == len(chunks),
          str([c["chunk_id"] for c in chunks]))
    hits = search_relevant_chunks(
        "视频有什么要求",
        [
            {"text": "演示视频不超过3分钟，MP4 格式。", "doc_name": "视频要求.md", "doc_id": "doc_1"},
            {"text": "报名表交至行政楼302。", "doc_name": "报名要求.md", "doc_id": "doc_2"},
        ],
        top_k=2,
    )
    check("E12 检索命中视频材料", bool(hits) and "视频" in hits[0]["content"],
          str(hits[:1]))

    # E13：Prompt 契约静态检查（防止后续改 Prompt 时丢关键约束）
    with open(os.path.join(HERE, "prompt.py"), encoding="utf-8") as f:
        prompt_text = f.read()
    for token in ("source_ref", "未找到依据", "check_date", "以此为准", "confirmation_needed"):
        check("E13 Prompt 保留约束：%s" % token, token in prompt_text)


def main():
    print("=" * 70)
    print("A 侧 10.29–10.31 验收（无需 API Key）")
    print("=" * 70)
    test_pair1()
    test_pair2()
    test_date_tool()
    test_llm_tool_loop_with_fake_client()
    test_edge_cases()

    print("\n" + "=" * 70)
    print("结果：%d 通过，%d 失败" % (len(PASS), len(FAIL)))
    if FAIL:
        print("失败项：")
        for name in FAIL:
            print(" - %s" % name)
        sys.exit(1)
    print("全部通过 ✅")
    print("说明：真实 LLM Function Calling 需要配置 Key 后再跑一次；")
    print("      当前用同一套 check_date 工具验证了真实调用与结果回写。")


if __name__ == "__main__":
    main()
