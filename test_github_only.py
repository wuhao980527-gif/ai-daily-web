#!/usr/bin/env python3
"""只测试 GitHub + Papers"""

import os
import sys
from dotenv import load_dotenv

load_dotenv('python_backend/.env')
sys.path.insert(0, 'python_backend')

from agent_tools import fetch_github_trending, fetch_big_tech_papers

print("=" * 60)
print("测试 GitHub 和 Papers")
print("=" * 60)

# GitHub
print("\n1️⃣ GitHub:")
github_results = fetch_github_trending.invoke({})
print(f"返回 {len(github_results)} 条")
if github_results:
    print(f"\n第一条原始数据 (前300字符):\n{github_results[0][:300]}\n")

# Papers
print("\n2️⃣ Papers:")
paper_results = fetch_big_tech_papers.invoke({})
print(f"返回 {len(paper_results)} 篇")
if paper_results:
    print(f"\n第一篇原始数据 (前300字符):\n{paper_results[0][:300]}\n")
