#!/usr/bin/env python3
"""测试 writer_node 的数据解析逻辑"""

import re

# 模拟 Product 数据（从 agent_graph.py 的格式）
product_sample = """Product: Grok Imagine Video
Date: 2026-01-21
Desc: Text-to-video generation feature in Grok AI
URL: https://example.com/grok-imagine"""

# 模拟 GitHub 数据（从 agent_tools.py 的格式）
github_sample = """=== Repo: f/prompts.chat ===
URL: https://github.com/f/prompts.chat
Date: 2022-12-05
Language: MDX
Stars: 144553
README snippet ---
This is a prompts repository for AI...
======================"""

print("测试 Product 解析:")
print("=" * 60)
lines = product_sample.strip().split('\n')
data = {}
for line in lines:
    if ":" in line:
        key, val = line.split(":", 1)
        data[key.strip()] = val.strip()

print(f"解析结果: {data}")
print(f"是否满足条件: data.get('Product')={data.get('Product')}, data.get('URL')={data.get('URL')}")

print("\n\n测试 GitHub 解析:")
print("=" * 60)
repo_match = re.search(r'Repo:\s*(.+?)(?:\n|$)', github_sample)
url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', github_sample)
date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', github_sample)
stars_match = re.search(r'Stars:\s*(\d+)', github_sample)
readme_match = re.search(r'README snippet ---\n(.+?)(?:\n=|$)', github_sample, re.DOTALL)

print(f"Repo: {repo_match.group(1) if repo_match else None}")
print(f"URL: {url_match.group(1) if url_match else None}")
print(f"Date: {date_match.group(1) if date_match else None}")
print(f"Stars: {stars_match.group(1) if stars_match else None}")
print(f"README: {readme_match.group(1)[:50] if readme_match else None}...")
print(f"是否满足条件: repo_match={bool(repo_match)}, url_match={bool(url_match)}")
