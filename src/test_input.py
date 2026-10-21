# src/test_input.py
import sys
import json
import logging
import re
from service import analyze_notification, update_matter_status_with_ai, ask_question

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

def print_matter_summary(data, title_prefix=""):
    print(f"\n{title_prefix} 📌 事项：{data.get('title')}")
    deadline = data.get("deadline", {})
    if deadline and deadline.get("due_at"):
        print(f"⏰ 截止时间：{deadline.get('due_at')}")
    else:
        print("⚠️ 警告：原文未提及明确的截止时间，请手动确认设置！")

    print("\n📋 材料清单：")
    for mat in data.get("materials", []):
        mark = "✅ [已准备]" if mat.get("status") == "prepared" else "❌ [缺少]"
        print(f"  {mark} {mat.get('material_name')} ({mat.get('material_id')})")

    print("\n📝 执行步骤：")
    for step in data.get("step_list", []):
        mark = "✅ [已完成]" if step.get("status") == "completed" else "⬜ [未完成]"
        print(f"  {mark} {step.get('title')}")

    print("\n📌 缺项待办：")
    for i, todo in enumerate(data.get("todo_list", [])):
        mark = "✅" if todo.get("status") == "completed" else "⬜"
        print(f"  {i+1}. {mark} {todo.get('action')} [{todo.get('todo_id')}]")

    if data.get("missing_items"):
        print("\n🔴 缺项：")
        for item in data["missing_items"]:
            print(f"  - {item['material_name']}：{item['reason']}")

def main():
    print("=" * 60)
    print("🎉 智能办事助手 (大模型常识推理版)")
    print("=" * 60)
    print("\n👉 请粘贴你的【真实通知】，输入 END 结束。")

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END': break
            lines.append(line)
        except EOFError: break

    user_input = "\n".join(lines).strip()
    if not user_input: return

    print("\n🤖 正在解析初始清单(调大模型)...")
    result = analyze_notification(user_input)
    if not result["success"]:
        return print(f"❌ 解析失败：{result['error']}")

    matter_data = result["data"]
    print_matter_summary(matter_data, "【初始清单】")

    print("\n💬 交互命令：update: 材料 | todo: 序号 完成 | step: 序号 完成 | exit 退出")

    while True:
        question = input("\n👤 你问：").strip()
        if question.lower() == 'exit': break
        if not question: continue

        # 判断是否是需要更新状态的指令
        is_update_cmd = re.search(r'(update|更新|todo|step)[\s:：]', question, re.IGNORECASE)
        
        if is_update_cmd:
            print("🤖 大模型正在根据您的操作推演状态（请稍候）...")
            resp = update_matter_status_with_ai(matter_data, user_input, question)
            matter_data = resp["data"]
            print_matter_summary(matter_data, "【更新后清单】")
            continue

        # 正常问答
        print("🤖 AI 回答：", end="", flush=True)
        ans = ask_question(matter_data, user_input, question)
        print(ans["answer"] if ans["success"] else f"❌ {ans['error']}")

if __name__ == "__main__":
    main()