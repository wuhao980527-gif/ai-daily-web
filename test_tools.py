#!/usr/bin/env python3
"""测试各个数据源能否正常工作"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('python_backend/.env')

# 添加路径
sys.path.insert(0, 'python_backend')

from agent_tools import (
    search_new_products,
    fetch_hf_trending_models,
    fetch_github_trending,
    fetch_big_tech_papers
)

print("=" * 60)
print("开始测试各个数据源...")
print("=" * 60)

# 测试 Product Search
print("\n\n1️⃣ 测试 Product Search")
print("-" * 60)
try:
    query = '(OpenAI OR DeepSeek OR "AI产品") (launched OR released OR 发布) after:2026-01-28'
    results = search_new_products.invoke(query)
    print(f"✅ Product Search 成功! 找到 {len(results)} 条结果")
    if results:
        print(f"第一条: {results[0].get('title', 'N/A')[:50]}...")
except Exception as e:
    print(f"❌ Product Search 失败: {e}")

# 测试 HuggingFace
print("\n\n2️⃣ 测试 HuggingFace")
print("-" * 60)
try:
    results = fetch_hf_trending_models.invoke({})
    print(f"✅ HuggingFace 成功! 找到 {len(results)} 个模型")
    if results:
        print(f"第一个: {results[0][:100]}...")
except Exception as e:
    print(f"❌ HuggingFace 失败: {e}")

# 测试 GitHub
print("\n\n3️⃣ 测试 GitHub")
print("-" * 60)
try:
    results = fetch_github_trending.invoke({})
    print(f"✅ GitHub 成功! 找到 {len(results)} 个项目")
    if results:
        print(f"第一个: {results[0][:100]}...")
except Exception as e:
    print(f"❌ GitHub 失败: {e}")

# 测试 Papers
print("\n\n4️⃣ 测试 Papers")
print("-" * 60)
try:
    results = fetch_big_tech_papers.invoke({})
    print(f"✅ Papers 成功! 找到 {len(results)} 篇论文")
    if results:
        print(f"第一篇: {results[0][:100]}...")
except Exception as e:
    print(f"❌ Papers 失败: {e}")

print("\n" + "=" * 60)
print("测试完成!")
print("=" * 60)
