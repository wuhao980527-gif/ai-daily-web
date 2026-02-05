#!/usr/bin/env python3
"""完整测试 Product 搜索+验证流程"""

import os
import sys
from dotenv import load_dotenv

load_dotenv('python_backend/.env')
sys.path.insert(0, 'python_backend')

from agent_tools import search_new_products, verify_product_page

print("=" * 60)
print("测试 Product 完整流程（搜索 + 验证）")
print("=" * 60)

# 1. 搜索
query = '(OpenAI OR DeepSeek OR "AI产品") (launched OR released OR 发布) after:2026-01-28'
raw_results = search_new_products.invoke(query)

print(f"\n第一步：搜索到 {len(raw_results)} 条原始结果")
for i, item in enumerate(raw_results[:3]):
    print(f"  {i+1}. {item.get('title', 'N/A')[:60]}...")
    print(f"      URL: {item.get('url', 'N/A')[:60]}...")

# 2. 验证第一条
if raw_results:
    print(f"\n第二步：验证第一条结果...")
    first_url = raw_results[0]['url']
    verification = verify_product_page.invoke(first_url)

    print(f"\n验证结果:")
    print(f"  产品名称: {verification.get('product_name')}")
    print(f"  已发布: {verification.get('is_released')}")
    print(f"  近期: {verification.get('is_recent')}")
    print(f"  发布日期: {verification.get('release_date')}")
    print(f"  描述: {verification.get('description')[:100]}...")

    # 3. 格式化（模拟 agent_graph.py 的逻辑）
    if verification.get('is_released') and verification.get('is_recent'):
        info = (
            f"Product: {verification.get('product_name', 'Unknown')}\n"
            f"Date: {verification.get('release_date', 'N/A')}\n"
            f"Desc: {verification.get('description', 'N/A')}\n"
            f"URL: {first_url}"
        )
        print(f"\n第三步：格式化后的数据:")
        print(info)
    else:
        print(f"\n❌ 该产品未通过验证（is_released={verification.get('is_released')}, is_recent={verification.get('is_recent')}）")
