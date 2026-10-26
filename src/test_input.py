# src/test_input.py
# -*- coding: utf-8 -*-
import sys
import os
import json
import logging
import re
from service import (
    analyze_notification,
    analyze_notification_from_pdf,
    update_matter_status_with_ai,
    ask_question_with_rag,
    search_relevant_chunks,
    ask_question
)

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
        suggest = " [💡AI建议]" if mat.get("is_suggestion") else ""
        quote = f"  (依据: {mat.get('source_ref', {}).get('quote', '')})" if mat.get("source_ref") else ""
        print(f"  {mark} {mat.get('material_name')}{suggest}{quote}")

    print("\n📝 执行步骤：")
    for step in data.get("step_list", []):
        mark = "✅ [已完成]" if step.get("status") == "completed" else "⬜ [未完成]"
        suggest = " [💡AI建议]" if step.get("is_suggestion") else ""
        quote = f"  (依据: {step.get('source_ref', {}).get('quote', '')})" if step.get("source_ref") else ""
        print(f"  {mark} {step.get('title')}{suggest}{quote}")

    print("\n📌 缺项待办：")
    for i, todo in enumerate(data.get("todo_list", [])):
        mark = "✅" if todo.get("status") == "completed" else "⬜"
        quote = f"  (依据: {todo.get('source_ref', {}).get('quote', '')})" if todo.get("source_ref") else ""
        print(f"  {i+1}. {mark} {todo.get('action')}{quote}")

    if data.get("missing_items"):
        print("\n🔴 缺项：")
        for item in data["missing_items"]:
            print(f"  - {item['material_name']}：{item['reason']}")


def main():
    print("=" * 65)
    print("🎉 智能办事助手 (支持文字/PDF解析 · 片段检索 · 先查材料再回答)")
    print("=" * 65)
    print("\n👉 输入方式（任选其一）：")
    print("   1. 直接输入文字型 PDF 路径（例如：测试通知.pdf）")
    print("   2. 直接粘贴通知全文，末尾另起一行输入 END 结束。")
    print("-" * 65)

    first_line = input().strip()
    user_input = ""
    is_pdf_input = False
    pdf_path = ""

    # 检测是否为 PDF 输入
    clean_path = first_line.strip('"').strip("'")
    if clean_path.lower().endswith(".pdf") and os.path.exists(clean_path):
        is_pdf_input = True
        pdf_path = clean_path
    else:
        lines = [first_line]
        while True:
            try:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        user_input = "\n".join(lines).strip()

    if not is_pdf_input and not user_input:
        print("未输入任何内容，程序退出。")
        return

    # 解析通知（PDF 或 文本）
    if is_pdf_input:
        print(f"\n📄 检测到 PDF 输入，正在提取文字并接入分析流程 [{pdf_path}]...")
        result = analyze_notification_from_pdf(pdf_path)
        if not result["success"]:
            print(f"❌ 解析失败：{result['error']}")
            if "额度不足" in str(result["error"]) or "insufficient_user_quota" in str(result["error"]):
                print("💡 提示：检测到您的 One API 后台额度已用尽，请前往后台充值。")
            return
        matter_data = result["data"]
        user_input = result.get("extracted_text", "")
        print_matter_summary(matter_data, f"【PDF 解析清单 - 共 {result.get('total_pages', 1)} 页】")
    else:
        print("\n🤖 正在解析文字通知...")
        result = analyze_notification(user_input)
        if not result["success"]:
            print(f"❌ 解析失败：{result['error']}")
            if "额度不足" in str(result["error"]) or "insufficient_user_quota" in str(result["error"]):
                print("💡 提示：检测到您的 One API 后台额度已用尽，请前往后台充值。")
            return
        matter_data = result["data"]
        print_matter_summary(matter_data, "【初始清单】")

    print("\n" + "=" * 65)
    print("💬 交互命令说明：")
    print("   - 普通追问：直接输入问题（例如：“视频有什么要求？”、“每队报销多少？”）")
    print("   - 片段检索：search: 关键词（查看材料切片与编号匹配结果）")
    print("   - 状态更新：update: 材料名 | todo: 序号 完成 | step: 序号 完成")
    print("   - 退出程序：exit")
    print("=" * 65)

    while True:
        try:
            question = input("\n👤 你问：").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if question.lower() == "exit":
            print("👋 再见！")
            break
        if not question:
            continue

        # 1. 快捷检索指令 (10.26 任务展示)
        if question.lower().startswith("search:") or question.startswith("检索:") or question.startswith("搜索:"):
            q_term = question.split(":", 1)[1].strip()
            print(f"🔍 正在材料片段中检索：“{q_term}”...")
            hits = search_relevant_chunks(q_term, user_input, top_k=3)
            if not hits:
                print("   未检索到相关片段。")
            else:
                print(f"   命中 {len(hits)} 个相关片段：")
                for h in hits:
                    page_str = f" (第 {h['page']} 页)" if h.get("page") else ""
                    print(f"   * [相关度 {h['score']}] 片段编号: {h['chunk_id']} | 来源: {h['doc_name']}{page_str}")
                    print(f"     原文: {h['content'][:100]}...")
            continue

        # 2. 状态推演指令
        is_update_cmd = re.search(r"^(update|更新|todo|step)[\s:：]", question, re.IGNORECASE)
        if is_update_cmd:
            print("🤖 大模型正在根据您的操作推演状态（请稍候）...")
            resp = update_matter_status_with_ai(matter_data, user_input, question)
            if resp.get("success"):
                matter_data = resp["data"]
                print_matter_summary(matter_data, "【更新后清单】")
            else:
                print(f"❌ 状态更新失败: {resp.get('error')}")
            continue

        # 3. 追问与 RAG 问答 (10.27 任务：先查材料再回答，附出处，无依据不乱答)
        print("🤖 AI 正在检索材料并回答...", flush=True)
        ans = ask_question_with_rag(question, user_input, matter_json=matter_data)
        if ans["success"]:
            print(f"\n【回答结果】\n{ans['answer']}")
            if ans.get("evidence_chunks"):
                print("\n📌 [检索依据来源]")
                for c in ans["evidence_chunks"]:
                    p_info = f" (第 {c['page']} 页)" if c.get("page") else ""
                    print(f"   - {c['doc_name']}{p_info} | 片段: {c['chunk_id']} (匹配度: {c['score']})")
        else:
            print(f"❌ {ans['error']}")
            if "额度不足" in str(ans.get("error", "")):
                print("💡 提示：API 额度已用尽，请前往 One API 后台充值。")


if __name__ == "__main__":
    main()
