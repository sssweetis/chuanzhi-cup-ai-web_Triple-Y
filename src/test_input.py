# src/test_input.py
from notification_extractor import LLMClient, MatterExtractor
from prompt import SYSTEM_PROMPT
import json

def main():
    # 1. 初始化模型
    llm = LLMClient()
    extractor = MatterExtractor(llm, SYSTEM_PROMPT)
    
    print("="*40)
    print("🎉 智能通知解析工具已启动！")
    print("请粘贴你的真实通知文本，按回车提交。")
    print("（输入 exit 退出程序）")
    print("="*40)

    while True:
        print("\n👉 请粘贴通知内容：")
        user_input = input("> ")
        
        if user_input.strip().lower() == 'exit':
            print("退出程序。")
            break
            
        if not user_input.strip():
            print("内容为空，请重新输入。")
            continue
            
        print("\n🤖 AI 正在思考中，请稍候...")
        matter, err = extractor.process(user_input)
        
        if err:
            print(f"❌ 解析失败：{err}")
        else:
            print("\n✅ 解析成功！以下是提取的 JSON 结果：")
            print(json.dumps(matter.to_dict(), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()