# -*- coding: utf-8 -*-
"""清空演示数据（材料库 / 准备清单存档）。演示前跑一次，材料列表从 0 开始。"""
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
for name in ("files.json", "prepare_lists.json", "comparisons.json"):
    path = os.path.join(DATA, name)
    if os.path.exists(path):
        os.remove(path)
        print("已删除：", path)
    else:
        print("不存在：", path)
print("演示数据已清空")