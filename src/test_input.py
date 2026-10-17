# src/test_input.py
import sys
import json
import logging
from service import analyze_notification, ask_question

# 关掉底层的网络请求日志干扰
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpx2").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

def main():
    print("="*50)
    print("🎉 智能办事助手 - 真实交互终端")
    print("="*50)

    while True:
        print("\n" + "-"*50)
        print("👉 请粘贴你的【真实通知】（支持多行）。")
        print("👉 粘贴完成后，请敲击回车，输入 END 结束粘贴。")
        print("👉 输入 exit 退出程序。")
        print("-"*50)

        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == 'END':
                    break
                if line.strip().lower() == 'exit':
                    sys.exit(0)
                lines.append(line)
            except EOFError:
                break
        
        user_input = "\n".join(lines).strip()
        if not user_input:
            print("⚠️ 内容为空，请重新粘贴。")
            continue

        print("\n🤖 [1/2] AI 正在解析通知结构，请稍候（可能需要10-30秒）...")
        
        result = analyze_notification(user_input)
        if not result["success"]:
            print(f"❌ 解析失败：{result['error']}")
            continue

        matter_data = result["data"]
        print("\n✅ 解析成功！以下是完整的结构化清单 JSON：")
        print("-" * 20)
        print(json.dumps(matter_data, ensure_ascii=False, indent=2))
        print("-" * 20)

        # 2. 进入问答模式
        print("\n" + "="*50)
        print("💬 进入追问模式（例如：这个比赛要求几个人？有视频要求吗？）")
        print("👉 输入问题按回车。输入 exit 重新粘贴新通知。")
        print("="*50)

        while True:
            question = input("\n👤 你问：")
            if question.strip().lower() == 'exit':
                break
            if not question.strip():
                continue

            print("🤖 AI 回答：", end="", flush=True)
            
            ans_result = ask_question(matter_data, user_input, question)
            
            if ans_result["success"]:
                print(ans_result["answer"])
            else:
                print(f"\n❌ 问答失败：{ans_result['error']}")

if __name__ == "__main__":
    main()