#!/usr/bin/env python3
"""直接测试GitHub API"""

import requests
from datetime import datetime, timedelta

date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

print(f"测试日期: {date_str}")
print("=" * 60)

# 测试1：最简单的查询
print("\n测试1: 搜索AI话题项目（7天内更新，Stars>10）")
url1 = f"https://api.github.com/search/repositories?q=ai+pushed:>{date_str}+stars:>10&sort=stars&order=desc&per_page=5"
print(f"URL: {url1}")
resp1 = requests.get(url1, headers={"Accept": "application/vnd.github.v3+json"}, timeout=10)
data1 = resp1.json()
print(f"状态码: {resp1.status_code}")
print(f"总数: {data1.get('total_count', 0)}")
if data1.get('items'):
    print(f"第一个结果: {data1['items'][0]['full_name']} (⭐{data1['items'][0]['stargazers_count']})")
else:
    print("没有结果")

# 测试2：降低Stars要求
print("\n\n测试2: 搜索AI话题项目（7天内更新，Stars>5）")
url2 = f"https://api.github.com/search/repositories?q=ai+pushed:>{date_str}+stars:>5&sort=stars&order=desc&per_page=5"
print(f"URL: {url2}")
resp2 = requests.get(url2, headers={"Accept": "application/vnd.github.v3+json"}, timeout=10)
data2 = resp2.json()
print(f"状态码: {resp2.status_code}")
print(f"总数: {data2.get('total_count', 0)}")
if data2.get('items'):
    for i, item in enumerate(data2['items'][:3]):
        print(f"  {i+1}. {item['full_name']} (⭐{item['stargazers_count']}, 语言:{item.get('language', 'N/A')})")
else:
    print("没有结果")

# 测试3：不限Stars
print("\n\n测试3: 搜索AI话题项目（7天内更新，不限Stars）")
url3 = f"https://api.github.com/search/repositories?q=ai+machine-learning+pushed:>{date_str}&sort=stars&order=desc&per_page=5"
print(f"URL: {url3}")
resp3 = requests.get(url3, headers={"Accept": "application/vnd.github.v3+json"}, timeout=10)
data3 = resp3.json()
print(f"状态码: {resp3.status_code}")
print(f"总数: {data3.get('total_count', 0)}")
if data3.get('items'):
    for i, item in enumerate(data3['items'][:5]):
        print(f"  {i+1}. {item['full_name']} (⭐{item['stargazers_count']}, 语言:{item.get('language', 'N/A')})")
else:
    print("没有结果")
