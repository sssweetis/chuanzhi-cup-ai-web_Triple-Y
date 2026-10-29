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

import json
import os
import sys
from types import SimpleNamespace

import service
from service import (
    apply_notice_changes,
    check_date,
    compare_notifications,
    run_date_check_tool_loop,
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


def main():
    print("=" * 70)
    print("A 侧 10.29–10.31 验收（无需 API Key）")
    print("=" * 70)
    test_pair1()
    test_pair2()
    test_date_tool()
    test_llm_tool_loop_with_fake_client()

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
