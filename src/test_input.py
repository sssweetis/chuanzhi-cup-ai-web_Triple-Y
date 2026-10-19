# src/test_input.py
import sys
import json
import logging
import re
from service import analyze_notification, ask_question

# 关掉烦人的网络日志
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

def print_matter_summary(data, title_prefix=""):
    print(f"\n{title_prefix} 📌 事项：{data.get('title')}")
    
    # 1. 检查 DDL (截止时间)
    deadline = data.get("deadline", {})
    due_at = deadline.get("due_at") if deadline else None
    if due_at:
        print(f"⏰ 截止时间：{due_at}")
        print(f"🔔 提醒：已为您设置提前 2 小时提醒")
    else:
        print(f"⚠️ 警告：原文未提及明确的截止时间，请手动确认设置！")
        
    # 2. 打印材料状态
    print("\n📋 材料清单：")
    materials = data.get("materials", [])
    if not materials:
        print("  (无材料要求)")
    for mat in materials:
        status_icon = "✅ [已准备]" if mat.get("status") == "prepared" else "❌ [缺少]"
        print(f"  {status_icon} {mat['material_name']}  —— 原文引用：“{mat.get('source_ref', {}).get('quote', '')}”")
        
    # 3. 打印步骤
    print("\n📝 执行步骤：")
    steps = data.get("step_list", [])
    if not steps:
        print("  (无详细步骤)")
    for step in steps:
        status_icon = "✅ [已完成]" if step['status'] == 'completed' else "⬜ [未完成]"
        print(f"  {status_icon} {step['title']}")
        print(f"      ↳ 依据原文：“{step.get('source_ref', {}).get('quote', '')}”")

def main():
    print("="*60)
    print("🎉 智能办事助手 - 真实交互与缺项迭代测试")
    print("="*60)

    print("\n👉 请粘贴你的【真实通知】")
    print("👉 【操作提示】：在终端里直接右键粘贴。或者按 Shift+Insert。")
    print("👉 粘贴完成后，敲击回车，手动输入 END 并回车结束粘贴。")
    
    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == 'END': break
            lines.append(line)
        except EOFError:
            break
    
    user_input = "\n".join(lines).strip()
    if not user_input: 
        print("⚠️ 通知内容为空，程序退出。")
        return

    print("\n🤖 正在解析初始清单，请稍候...")
    
    user_materials_list = []

    result = analyze_notification(user_input, user_materials=user_materials_list)
    if not result["success"]:
        print(f"❌ 解析失败：{result['error']}")
        return

    updated_data = result["data"]
    print_matter_summary(updated_data, "【初始结构化清单】")

    print("\n" + "="*60)
    print("💬 进入交互模式")
    print("👉 提问：直接输入问题")
    print("👉 更新材料：输入 update: 材料名1, 材料名2")
    print("👉 输入 exit 退出。")
    print("="*60)

    while True:
        question = input("\n👤 你问：")
        if question.strip().lower() == 'exit': break
        if not question.strip(): continue

        # ====== 拦截更新材料指令 ======
        match = re.match(r'^(update|更新)[\s:：]+(.*)', question.strip(), re.IGNORECASE)
        
        if match:
            new_mats = match.group(2).strip()
            new_mats_list = [m.strip() for m in new_mats.replace("，", ",").split(",") if m.strip()]
            
            # 追加去重逻辑
            for m in new_mats_list:
                if m not in user_materials_list:
                    user_materials_list.append(m)
            
            print(f"🤖 收到！系统正在根据您目前拥有的全部材料 {user_materials_list} 重新核对...")
            
            result_iter = analyze_notification(user_input, user_materials=user_materials_list)
            updated_data = result_iter["data"]
            
            print_matter_summary(updated_data, "【更新后的结构化清单】")
            
            missing = updated_data.get("missing_items", [])
            if missing:
                print("\n🚨 系统核对结果：您仍然缺少以下必填材料！")
                for m in missing:
                    print(f"  - {m['material_name']}（{m['reason']}）")
            else:
                print("\n✅ 太棒了，您的材料已全部备齐！")
            continue

        # ====== 正常问答 ======
        print("🤖 AI 回答：", end="", flush=True)
        prompt_addon = "\n(注意：你无法直接修改系统清单的状态，只能根据当前清单回答问题。)" 
        ans_result = ask_question(updated_data, user_input, question + prompt_addon)
        
        if ans_result["success"]:
            print(ans_result["answer"])
        else:
            print(f"\n❌ 问答失败：{ans_result['error']}")

if __name__ == "__main__":
    main()