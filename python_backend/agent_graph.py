import operator
from typing import Annotated, List, TypedDict
from datetime import datetime, timedelta

# LangGraph 核心组件
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import SystemMessage, HumanMessage


# 引入 V3.0 工具集
from agent_tools import (
    groq_llm,
    search_new_products,
    batch_extract_products,
    verify_product_page,
    react_reason,
    fetch_hf_trending_models,
    fetch_github_trending,
    fetch_big_tech_papers
)

import os  # 确保这行一定要有（如果没有就补上，如果本来就有就不用重复写）
# ========================================================
# 🌍 强制代理设置 (针对 VPN 端口 7897)
# 作用：确保无论是手动运行还是 Crontab 定时任务，都能连上外网
# ⚠️ 注意：如果你换了 VPN 软件，记得回来把 7897 改成新端口
# ========================================================
LOCAL_VPN = os.getenv("LOCAL_VPN", "")
if LOCAL_VPN:
    os.environ["http_proxy"] = LOCAL_VPN
    os.environ["https_proxy"] = LOCAL_VPN
    print(f"🔧 [Config] 使用本地代理: {LOCAL_VPN}")
else:
    print("🌐 [Config] 直连模式 (GitHub Actions)")
# ========================================================


# ================= 1. 定义记忆 (State) =================
class AgentState(TypedDict):
    final_report: str

    # --- 板块 1: 新品 (ReAct) ---
    product_queries: List[str]        # 支持多query
    product_retries: int
    product_raw_items: List[dict]
    product_verified_items: Annotated[List[str], operator.add]
    product_react_should_stop: bool
    product_search_history: str       # 搜索历史摘要，传给reflect用

    # --- 板块 2/3/4: 列表数据 ---
    hf_models: List[str]
    github_repos: List[str]
    tech_papers: List[str]

# ================= 2. 定义节点 (Nodes) =================

def init_node(state: AgentState):
    """初始化：生成多角度定向 cold-start query"""
    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    initial_queries = [
        # 角度1: 中文AI权威媒体
        f'AI ("发布" OR "上线" OR "推出" OR "开源") (site:36kr.com OR site:jiqizhixin.com OR site:infoq.cn) after:{target_date}',
        # 角度2: 英文科技媒体
        f'AI ("launched" OR "released" OR "announced" OR "open-sourced") (site:techcrunch.com OR site:theverge.com OR site:venturebeat.com) after:{target_date}',
        # 角度3: 头部AI厂商定向（国际）
        f'("OpenAI" OR "Anthropic" OR "Google" OR "Meta AI") ("launch" OR "release" OR "new model") after:{target_date}',
        # 角度4: 头部AI厂商定向（国内）
        f'("DeepSeek" OR "Kimi" OR "Qwen" OR "智谱" OR "豆包") ("发布" OR "上线" OR "开源") after:{target_date}',
        # 角度5: AI应用/工具（放开限制，依赖三级过滤）
        f'AI ("新功能" OR "视频生成" OR "图像生成" OR "new feature" OR "AI助手") after:{target_date}',
        # 角度6: AI硬件/机器人（放开限制，依赖三级过滤）
        f'(AI 硬件 OR AI芯片 OR 机器人 OR "AI glasses" OR "AI chip" OR "humanoid robot") after:{target_date}',
        # 角度7: 商业事件（放开限制，依赖三级过滤）
        f'AI ("融资" OR "收购" OR "合作" OR "funding" OR "acquisition" OR "partnership") after:{target_date}',
    ]

    print(f"⚙️ [Init] 首轮多角度搜索: {len(initial_queries)} 个定向query, 7天内")
    return {
        "product_queries": initial_queries,
        "product_retries": 0,
        "product_verified_items": [],
        "product_react_should_stop": False,
        "product_search_history": ""
    }
# --- 板块 1: 新品 ReAct 循环逻辑 ---

def product_search_node(state: AgentState):
    """【Act】执行多query搜索 + date过滤 + snippet级预过滤"""
    from dateutil import parser as date_parser

    queries = state.get('product_queries', [])
    retries = state.get('product_retries', 0)

    # 1. 执行所有query，收集结果
    all_results = []
    for i, q in enumerate(queries):
        print(f"\n🔍 [Act] 第{retries+1}轮-Query{i+1}/{len(queries)}: {q[:60]}...")
        try:
            results = search_new_products.invoke(q)
            all_results.extend(results)
        except Exception as e:
            print(f"   ⚠️ 搜索失败: {e}")

    # 2. 跨轮次URL去重
    existing_urls = set()
    for item_str in state.get('product_verified_items', []):
        for line in item_str.split('\n'):
            if line.startswith('URL:'):
                existing_urls.add(line.split(':', 1)[1].strip())

    unique = []
    for item in all_results:
        url = item.get('url', '')
        if url and url not in existing_urls:
            existing_urls.add(url)
            unique.append(item)

    # 3. date过滤：published_date不在7天内的直接扔（免费，无LLM调用）
    cutoff = datetime.now() - timedelta(days=7)
    date_filtered = []
    for r in unique:
        pub_date = r.get('published_date', '')
        if pub_date:
            try:
                dt = date_parser.parse(pub_date)
                if dt.replace(tzinfo=None) < cutoff:
                    print(f"   📅 跳过过旧: {r.get('title','')[:40]} ({pub_date})")
                    continue
            except Exception:
                pass  # 解析失败的保留，让后续步骤处理
        date_filtered.append(r)

    # 4. LLM批量提取产品名（便宜：全部snippet一次调用）
    candidates = batch_extract_products.invoke({"search_results": date_filtered})

    # 5. 生成搜索摘要（给reflect用）
    search_summary = f"第{retries+1}轮: {len(queries)}个query, {len(all_results)}条结果, 去重后{len(unique)}条, date过滤后{len(date_filtered)}条, 提取到{len(candidates)}个产品候选"

    print(f"   ✅ {search_summary}")
    return {
        "product_raw_items": candidates,
        "product_search_history": state.get('product_search_history', '') + '\n' + search_summary
    }

def product_verify_node(state: AgentState):
    """核查搜索结果"""
    from datetime import datetime, timedelta
    from dateutil import parser as date_parser
    import re

    raw = state.get('product_raw_items', [])
    verified = []

    # verify前URL去重，避免同一URL浪费多次verify调用
    seen_urls = set()
    seen_product_names = set()  # 新增：基于提取后的产品名去重
    deduped = []
    for item in raw:
        url = item.get('url', '')
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append(item)
    if len(deduped) < len(raw):
        print(f"\n🔍 [Graph] 正在核实 {len(deduped)} 条新品线索（去重前 {len(raw)} 条）...")
    else:
        print(f"\n🔍 [Graph] 正在核实 {len(deduped)} 条新品线索...")

    seven_days_ago = datetime.now() - timedelta(days=7)

    for item in deduped:
        try:
            # 调用 agent_tools 里的核查工具
            res = verify_product_page.invoke(item['url'])

            # 只有真正发布且是近期的新品才保留
            if res.get('is_released') and res.get('is_recent'):
                # 硬性验证日期：代码层面二次检查
                release_date_str = res.get('release_date', '')
                is_truly_recent = False

                try:
                    # 尝试解析日期字符串
                    # 提取年月日数字
                    date_match = re.search(r'202[4-6][-/年]\s*(\d{1,2})[-/月]\s*(\d{1,2})', release_date_str)
                    if date_match:
                        parsed_date = date_parser.parse(release_date_str, fuzzy=True)
                        if parsed_date >= seven_days_ago:
                            is_truly_recent = True
                            print(f"      ✅ 日期验证通过: {res.get('product_name', 'Unknown')} ({parsed_date.strftime('%Y-%m-%d')})")
                        else:
                            print(f"      ❌ 日期过旧: {res.get('product_name', 'Unknown')} ({parsed_date.strftime('%Y-%m-%d')}) - 跳过")
                            continue
                    else:
                        # 无法解析日期，检查是否包含"今天"、"yesterday"、"本周"等关键词
                        recent_keywords = ['今天', '昨天', 'today', 'yesterday', '本周', 'this week', '刚刚', 'just now']
                        if any(kw in release_date_str.lower() for kw in recent_keywords):
                            is_truly_recent = True
                            print(f"      ✅ 相对日期验证通过: {res.get('product_name', 'Unknown')} ({release_date_str})")
                        else:
                            print(f"      ⚠️ 无法验证日期: {res.get('product_name', 'Unknown')} ({release_date_str}) - 跳过")
                            continue
                except Exception as e:
                    print(f"      ⚠️ 日期解析失败: {release_date_str} - {e}")
                    continue

                if is_truly_recent:
                    # 🔥 关键：基于提取后的产品名去重
                    product_name = res.get('product_name', 'Unknown')
                    product_name_normalized = product_name.strip().lower()

                    if product_name_normalized in seen_product_names:
                        print(f"      ⚠️ 产品名重复: {product_name} - 跳过（不同媒体报道同一产品）")
                        continue

                    seen_product_names.add(product_name_normalized)

                    url_lower = item['url'].lower()

                    # 检查1：URL中不应包含负面市场词汇
                    negative_keywords = ['wipe', 'crash', 'plunge', 'drop', 'fall', 'decline', 'loss', 'billion', 'stock']
                    if any(kw in url_lower for kw in negative_keywords):
                        print(f"      ⚠️ URL包含市场负面词汇: {product_name} - 可能是二手新闻，跳过")
                        continue

                    # 检查2：拒绝新闻快讯类型（内容太简短）
                    low_quality_patterns = ['newsflash', 'kuaixun', '快讯', '/news/', '/brief/']
                    if any(pattern in url_lower for pattern in low_quality_patterns):
                        print(f"      ⚠️ 低质量快讯类型: {product_name} - 内容过于简短，跳过")
                        continue

                    # 格式化数据，方便主编直接使用
                    info = (
                        f"Product: {product_name}\n"
                        f"Date: {res.get('release_date', 'N/A')}\n"
                        f"Desc: {res.get('description', 'N/A')}\n"
                        f"URL: {item['url']}"
                    )
                    verified.append(info)
        except Exception as e:
            print(f"      ⚠️ 核查失败 ({item.get('url', 'N/A')}): {e}")
            continue

    return {"product_verified_items": verified}

def product_reflect_node(state: AgentState):
    """🧠【Reason】LLM 评估当前结果，决定是否继续 + 生成下一轮 query"""
    new_retries = state['product_retries'] + 1
    items = state.get('product_verified_items', [])
    history = state.get('product_search_history', '')

    print(f"\n🧠 [Reason] 第 {new_retries} 轮推理，当前 {len(items)} 条...")

    # 硬性上限：第3轮必须停止
    if new_retries >= 3:
        print(f"   🛑 已达最大轮次(3)，强制停止")
        return {
            "product_retries": new_retries,
            "product_react_should_stop": True
        }

    try:
        # 传入搜索历史，让LLM知道哪些角度已经试过了
        decision = react_reason.invoke({
            "current_items": items,
            "retry_count": new_retries,
            "search_history": history
        })

        print(f"   💭 推理: {decision['reasoning'][:100]}...")
        print(f"   📋 缺失: {decision['gap_category']}")

        if decision['should_continue']:
            print(f"   🔍 下一轮: {decision['next_query'][:80]}...")
        else:
            print(f"   ✅ LLM 判断: 结果已足够")

        return {
            "product_queries": [decision['next_query']],  # LLM的query包成列表
            "product_retries": new_retries,
            "product_react_should_stop": not decision['should_continue']
        }
    except Exception as e:
        print(f"   ⚠️ Groq 推理失败: {e}，降级停止")
        return {
            "product_retries": new_retries,
            "product_react_should_stop": True
        }

def should_continue_product(state: AgentState):
    """路由：基于 LLM 推理决策"""
    should_stop = state.get('product_react_should_stop', False)
    items = state.get('product_verified_items', [])
    retries = state.get('product_retries', 0)

    print(f"\n📊 [Route] items={len(items)} | round={retries}/3 | LLM_stop={should_stop}")

    if should_stop:
        return "join"
    return "continue"

# --- 板块 2/3/4: API 直连逻辑 ---

def hf_node(state: AgentState):
    try:
        return {"hf_models": fetch_hf_trending_models.invoke({})}
    except Exception as e:
        print(f"⚠️ [HF] 获取失败: {e}")
        return {"hf_models": []}

def github_node(state: AgentState):
    try:
        return {"github_repos": fetch_github_trending.invoke({})}
    except Exception as e:
        print(f"⚠️ [GitHub] 获取失败: {e}")
        return {"github_repos": []}

def paper_node(state: AgentState):
    try:
        return {"tech_papers": fetch_big_tech_papers.invoke({})}
    except Exception as e:
        print(f"⚠️ [Papers] 获取失败: {e}")
        return {"tech_papers": []}

# --- 核心：主编汇总 ---

def writer_node(state: AgentState):
    """汇总四个板块的数据，生成结构化 JSON 数据"""
    print("\n✍️ [Writer] 数据就位，生成结构化新闻...")

    import json
    import hashlib
    import re

    # 数据判空处理
    p_items = state.get('product_verified_items', [])
    h_items = state.get('hf_models', [])
    g_items = state.get('github_repos', [])
    paper_items = state.get('tech_papers', [])

    # 调试输出
    print(f"\n🔍 [DEBUG] 原始数据统计:")
    print(f"  - Product: {len(p_items)} 条")
    print(f"  - HuggingFace: {len(h_items)} 条")
    print(f"  - GitHub: {len(g_items)} 条")
    print(f"  - Papers: {len(paper_items)} 条")

    if p_items:
        print(f"\n📦 Product 第一条原始数据:\n{p_items[0]}\n")
    if g_items:
        print(f"\n🐙 GitHub 第一条原始数据:\n{g_items[0][:200]}...\n")
    if paper_items:
        print(f"\n📜 Papers 第一条原始数据:\n{paper_items[0][:200]}...\n")

    # 收集所有原始数据
    raw_items = []
    seen_urls = set()  # 用于URL去重
    seen_titles = set()  # 用于标题去重（避免不同来源的相同产品）

    # ==================== 解析新品（带去重）====================
    for item_str in p_items:
        try:
            lines = item_str.strip().split('\n')
            data = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    data[key.strip()] = val.strip()

            url = data.get("URL")
            title = data.get("Product", "")
            if title and url:
                # URL去重检查
                if url in seen_urls:
                    print(f"   ⚠️ 跳过重复URL: {title}")
                    continue

                # 标题去重检查（标准化后比较）
                title_normalized = title.strip().lower()
                if title_normalized in seen_titles:
                    print(f"   ⚠️ 跳过重复标题: {title}")
                    continue

                seen_urls.add(url)
                seen_titles.add(title_normalized)

                raw_items.append({
                    "type": "Product",
                    "title": title,
                    "url": url,
                    "description": data.get("Desc", ""),
                    "date": data.get("Date", "")
                })
        except Exception as e:
            print(f"⚠️ 解析新品出错: {e}")

    # ==================== 解析 HF 模型 ====================
    for item_str in h_items:
        try:
            # 提取各个字段
            model_match = re.search(r'Model:\s*(.+?)(?:\n|$)', item_str)
            url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', item_str)
            date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', item_str)
            likes_match = re.search(r'Likes:\s*(\d+)', item_str)
            readme_match = re.search(r'README Summary ---\n(.+?)(?:\n=|$)', item_str, re.DOTALL)

            if model_match and url_match:
                url = url_match.group(1).strip()
                title = model_match.group(1).strip().replace("===", "").strip()
                title_normalized = title.lower()

                # 去重检查
                if url in seen_urls or title_normalized in seen_titles:
                    print(f"   ⚠️ 跳过重复HF模型: {title}")
                    continue

                seen_urls.add(url)
                seen_titles.add(title_normalized)

                raw_items.append({
                    "type": "HuggingFace",
                    "title": title,
                    "url": url,
                    "description": readme_match.group(1).strip()[:500] if readme_match else "",
                    "date": date_match.group(1).strip() if date_match else "",
                    "likes": int(likes_match.group(1)) if likes_match else 0
                })
        except Exception as e:
            print(f"⚠️ 解析 HF 模型出错: {e}")

    # ==================== 解析 GitHub 项目 ====================
    for item_str in g_items:
        try:
            repo_match = re.search(r'Repo:\s*(.+?)(?:\n|$)', item_str)
            url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', item_str)
            date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', item_str)
            lang_match = re.search(r'Language:\s*(.+?)(?:\n|$)', item_str)
            stars_match = re.search(r'Stars:\s*(\d+)', item_str)
            readme_match = re.search(r'README snippet ---\n(.+?)(?:\n=|$)', item_str, re.DOTALL)

            if repo_match and url_match:
                url = url_match.group(1).strip()
                title = repo_match.group(1).strip().replace("===", "").strip()
                title_normalized = title.lower()

                # 去重检查
                if url in seen_urls or title_normalized in seen_titles:
                    print(f"   ⚠️ 跳过重复GitHub项目: {title}")
                    continue

                seen_urls.add(url)
                seen_titles.add(title_normalized)

                raw_items.append({
                    "type": "GitHub",
                    "title": title,
                    "url": url,
                    "description": readme_match.group(1).strip()[:500] if readme_match else "",
                    "language": lang_match.group(1).strip() if lang_match else "Unknown",
                    "date": date_match.group(1).strip() if date_match else "",
                    "stars": int(stars_match.group(1)) if stars_match else 0
                })
        except Exception as e:
            print(f"⚠️ 解析 GitHub 项目出错: {e}")

    # ==================== 解析论文 ====================
    for item_str in paper_items:
        try:
            title_match = re.search(r'Paper:\s*(.+?)(?:\n|$)', item_str)
            url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', item_str)
            date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', item_str)
            org_match = re.search(r'Organization:\s*(.+?)(?:\n|$)', item_str)
            abstract_match = re.search(r'Abstract:\s*(.+?)(?:\n=|$)', item_str, re.DOTALL)

            if title_match and url_match:
                url = url_match.group(1).strip()
                org_name = org_match.group(1).strip() if org_match else ""
                paper_title = title_match.group(1).strip().replace("===", "").strip()

                # 在标题中添加机构标注（如果标题中还没有）
                if org_name and org_name not in paper_title:
                    paper_title = f"[{org_name}] {paper_title}"

                title_normalized = paper_title.lower()

                # 去重检查
                if url in seen_urls or title_normalized in seen_titles:
                    print(f"   ⚠️ 跳过重复论文: {paper_title}")
                    continue

                seen_urls.add(url)
                seen_titles.add(title_normalized)

                raw_items.append({
                    "type": "Papers",
                    "title": paper_title,
                    "url": url,
                    "description": abstract_match.group(1).strip()[:300] if abstract_match else "",
                    "organization": org_name,
                    "date": date_match.group(1).strip() if date_match else ""
                })
        except Exception as e:
            print(f"⚠️ 解析论文出错: {e}")

    # ==================== 用一次 LLM 调用处理所有数据 ====================
    if raw_items:
        # 构建 prompt
        items_text = ""
        for i, item in enumerate(raw_items):
            # 如果是论文，添加机构信息
            org_info = f" | 机构:{item.get('organization', 'N/A')}" if item['type'] == 'Papers' and item.get('organization') else ""
            items_text += f"\n[{i}] 类型:{item['type']}{org_info} | 标题:{item['title']} | 描述:{item['description'][:100]}...\n"

        prompt = f"""你是资深的 AI 行业分析师。请为以下 {len(raw_items)} 条新闻撰写专业的中文解读。

{items_text}

⚠️ 重要要求：
1. 每条新闻写一段详细的中文解读（100-150字），必须包含：
   - 核心功能/技术特点（是什么）
   - 技术亮点/创新点（有什么特别之处）
   - 应用场景（能用在哪里）
   - 行业意义/影响（为什么重要）
   - **如果是Papers类型，必须在解读开头明确提及机构名称**（如："Meta发布的..."、"Google提出..."）

2. 写作风格：客观专业，避免营销词汇，用事实说话

3. 提取3个精准的中文标签（格式：#标签，如 #生成式AI #多模态 #开源）

4. 输出格式必须严格为 JSON 数组：
[
  {{"index": 0, "summary": "详细解读文本（100-150字）", "tags": ["#标签1", "#标签2", "#标签3"]}},
  {{"index": 1, "summary": "详细解读文本（100-150字）", "tags": ["#标签1", "#标签2", "#标签3"]}}
]

只输出 JSON，不要其他文字！"""

        try:
            response = groq_llm.invoke(prompt).content
            # 提取 JSON 部分
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                summaries = json.loads(json_match.group())

                # 将摘要和标签填充回原数据
                for summary_data in summaries:
                    idx = summary_data.get("index")
                    if idx is not None and idx < len(raw_items):
                        raw_items[idx]["summary"] = summary_data.get("summary", raw_items[idx]["description"][:100])
                        raw_items[idx]["tags"] = summary_data.get("tags", ["#AI"])
            else:
                print("⚠️ LLM 未返回有效 JSON，使用原始描述")
                for item in raw_items:
                    item["summary"] = item["description"][:100]
                    item["tags"] = ["#AI", f"#{item['type']}"]

        except Exception as e:
            print(f"⚠️ LLM 处理失败: {e}，使用原始描述")
            for item in raw_items:
                item["summary"] = item["description"][:100] if item["description"] else "暂无描述"
                item["tags"] = ["#AI", f"#{item['type']}"]

    # ==================== 组装最终数据 ====================
    all_news = []
    for item in raw_items:
        item_id = hashlib.md5(item["url"].encode()).hexdigest()[:6]

        news_item = {
            "id": item_id,
            "title": item["title"],
            "source": item["type"],
            "tags": item.get("tags", ["#AI"]),
            "summary": item.get("summary", item["description"][:100]),
            "url": item["url"]
        }

        # 添加发布时间
        if item.get("date"):
            news_item["date"] = item["date"]

        # 添加热度指标
        if item["type"] == "HuggingFace" and item.get("likes"):
            news_item["likes"] = item.get("likes")
        elif item["type"] == "GitHub" and item.get("stars"):
            news_item["stars"] = item.get("stars")

        all_news.append(news_item)

    # 生成每日总结
    if all_news:
        # 按来源分组统计
        sources_count = {}
        for n in all_news:
            sources_count[n["source"]] = sources_count.get(n["source"], 0) + 1

        titles_text = " | ".join([f"{n['source']}: {n['title'][:40]}" for n in all_news[:8]])
        summary_prompt = f"""分析今日 AI 领域的主要进展，用一段话总结（80-120字）。

今日新闻（共{len(all_news)}条）：
{titles_text}

要求：
1. 总结主要趋势和亮点（如：模型发布、技术突破、行业应用等）
2. 语言专业客观，避免形容词堆砌
3. 突出重点，不要流水账

只返回总结文字，不要其他内容！"""
        try:
            daily_summary = groq_llm.invoke(summary_prompt).content.strip()
        except:
            daily_summary = f"今日AI领域呈现多维度进展，涵盖{', '.join([f'{v}项{k}动态' for k,v in sources_count.items()])}。"
    else:
        daily_summary = "今日暂无重大 AI 进展。"

    # 返回结构化数据
    result = {
        "summary": daily_summary,
        "news": all_news
    }

    print(f"   ✅ 已生成 {len(all_news)} 条新闻")
    return {"final_report": json.dumps(result, ensure_ascii=False)}

# ================= 3. 构建图谱 (Graph) =================

workflow = StateGraph(AgentState)

# 1. 添加节点
workflow.add_node("init", init_node)
workflow.add_node("p_search", product_search_node)
workflow.add_node("p_verify", product_verify_node)
workflow.add_node("p_reflect", product_reflect_node)

workflow.add_node("hf_fetch", hf_node)
workflow.add_node("gh_fetch", github_node)
workflow.add_node("paper_fetch", paper_node)
workflow.add_node("writer", writer_node)

# 2. 定义边缘 (流程)

# 并行启动：初始化后，同时派发 4 个任务
workflow.add_edge(START, "init")
workflow.add_edge("init", "p_search")
workflow.add_edge("init", "hf_fetch")
workflow.add_edge("init", "gh_fetch")
workflow.add_edge("init", "paper_fetch")

# Product ReAct 循环
workflow.add_edge("p_search", "p_verify")
workflow.add_edge("p_verify", "p_reflect")
workflow.add_conditional_edges(
    "p_reflect",
    should_continue_product,
    {
        "join": "writer",       # LLM 判断够了 -> 去汇总
        "continue": "p_search"  # LLM 判断不够 -> 带着新 query 重搜
    }
)

# 其他板块直接汇入 Writer
workflow.add_edge("hf_fetch", "writer")
workflow.add_edge("gh_fetch", "writer")
workflow.add_edge("paper_fetch", "writer")

# 结束
workflow.add_edge("writer", END)

# 3. 编译
app = workflow.compile()

# ================= 4. 运行 =================
if __name__ == "__main__":
    print("🚀 Project Panorama: 全景信息聚合 Agent 启动...")

    try:
        # 1. 运行 Agent 生成报告
        final_state = app.invoke({"product_retries": 0})
        report = final_state["final_report"]

        # 2. 打印到控制台 (可选)
        print("\n\n" + "="*30 + " 最终简报 " + "="*30 + "\n")
        # print(report) # 嫌太长可以注释掉这行

        # 3. 保存到 data/news.json (用于网页展示)
        import json

        # 确保使用项目根目录的路径
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        data_dir = os.path.join(project_root, "data")
        json_path = os.path.join(data_dir, "news.json")

        # 确保 data 目录存在
        os.makedirs(data_dir, exist_ok=True)

        # 解析 LLM 返回的 JSON 字符串
        try:
            report_data = json.loads(report)
        except json.JSONDecodeError:
            print("⚠️ 解析 JSON 失败，使用默认格式")
            report_data = {
                "summary": "数据生成失败",
                "news": []
            }

        today_news = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "summary": report_data.get("summary", ""),
            "news": report_data.get("news", [])
        }

        # 读取现有数据
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                all_news = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            all_news = []

        # 更新或添加今天的数据
        today_str = datetime.now().strftime("%Y-%m-%d")
        updated = False
        for i, news in enumerate(all_news):
            if news.get("date") == today_str:
                all_news[i] = today_news
                updated = True
                break

        if not updated:
            all_news.append(today_news)

        # 保存回文件
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_news, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 数据已保存到 {json_path}")
        print(f"   今日新增 {len(report_data.get('news', []))} 条新闻")

    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()



        