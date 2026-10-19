# src/test_input.py
import sys
import json
import logging
import re
from service import analyze_notification, update_matter_status, ask_question

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

def print_matter_summary(data, title_prefix=""):
    print(f"\n{title_prefix} 📌 事项：{data.get('title')}")
    deadline = data.get("deadline", {})
    if deadline and deadline.get("due_at"): 
        print(f"⏰ 截止时间：{deadline.get('due_at')}")
    else: 
        print(f"⚠️ 警告：原文未提及明确的截止时间，请手动确认设置！")
        
    print("\n📋 材料清单：")
    for mat in data.get("materials", []):
        print(f"  {'✅ [已准备]' if mat.get('status') == 'prepared' else '❌ [缺少]'} {mat['material_name']}")
        
    print("\n📝 执行步骤 (流程主线)：")
    for step in data.get("step_list", []):
        print(f"  {'✅ [已完成]' if step['status'] == 'completed' else '⬜ [未完成]'} {step['title']}")

    print("\n📌 缺项待办 (具体动作)：")
    for i, todo in enumerate(data.get("todo_list", [])):
        print(f"  {i+1}. {'✅' if todo.get('status') == 'completed' else '⬜'} {todo['action']}")

def main():
    print("="*60)
    print("🎉 智能办事助手 (10.21 状态机终极测试)")
    print("="*60)
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

    print("\n💬 交互命令：update: 材料 | todo: 序号 完成 | todo: 序号 内容 | exit 退出")

    user_materials_list = []
    current_todos = matter_data.get("todo_list", [])

    while True:
        question = input("\n👤 你问：").strip()
        if question.lower() == 'exit': break
        if not question: continue

        # 1. 更新材料
        match_update = re.search(r'(update|更新)[\s:：]+(.*)', question, re.IGNORECASE)
        if match_update:
            new_mats = match_update.group(2).strip()
            for m in [m.strip() for m in new_mats.replace("，", ",").split(",") if m.strip()]:
                if m not in user_materials_list: 
                    user_materials_list.append(m)
            
            print(f"🤖 本地核对中...")
            matter_data = update_matter_status(matter_data, user_materials_list, current_todos)["data"]
            current_todos = matter_data.get("todo_list", [])
            print_matter_summary(matter_data, "【更新后清单】")
            continue

        # 2. 修改/完成待办
        match_todo = re.search(r'todo[\s:：]+(\d+)\s+(.*)', question, re.IGNORECASE)
        if match_todo:
            idx = int(match_todo.group(1)) - 1
            val = match_todo.group(2).strip()
            
            # 去除多余字眼
            if val.startswith("修改为"): val = val[3:].strip()
            if val.startswith("改为"): val = val[2:].strip()
            
            if 0 <= idx < len(current_todos):
                if val in ["完成", "completed", "done"]: 
                    current_todos[idx]["status"] = "completed"
                elif val in ["未完成", "pending"]: 
                    current_todos[idx]["status"] = "pending"
                else: 
                    current_todos[idx]["action"] = val
            
            matter_data = update_matter_status(matter_data, user_materials_list, current_todos)["data"]
            current_todos = matter_data.get("todo_list", [])
            print_matter_summary(matter_data, "【修改后清单】")
            continue

        # 3. 问答
        print("🤖 AI 回答：", end="", flush=True)
        ans = ask_question(matter_data, user_input, question)
        print(ans["answer"] if ans["success"] else f"❌ {ans['error']}")

if __name__ == "__main__":
    main()