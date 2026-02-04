import operator
from typing import Annotated, List, TypedDict
from datetime import datetime, timedelta

# LangGraph 核心组件
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import SystemMessage, HumanMessage


# 引入 V3.0 工具集
from agent_tools import (
    llm,
    search_new_products,
    verify_product_page,
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
    product_query: str
    product_retries: int
    product_raw_items: List[dict]
    product_verified_items: Annotated[List[str], operator.add]
    
    # --- 板块 2/3/4: 列表数据 ---
    hf_models: List[str]
    github_repos: List[str]
    tech_papers: List[str]

# ================= 2. 定义节点 (Nodes) =================

def init_node(state: AgentState):
    """初始化：在这里统一生成带日期的搜索词"""
    print(f"⚙️ [Init] 系统初始化...")
    
    # 1. 动态计算日期 (7天前)
    # 比如今天是 24号，算出来就是 2024-12-17
    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # 2. 组装最强搜索词 (中英混合 + 软硬兼施 + 强制近期)
    # 英文部分
    en_subjects = '"AI product" OR "AI model" OR "Embodied AI" OR "Humanoid Robot" '
    en_actions = '"launched" OR "released" OR "unveiled" OR "announced"'
    
    # 中文部分 (针对国内大厂和创业公司)
    cn_subjects = '"AI新品" OR "大模型" OR "具身智能" OR "人形机器人" '
    cn_actions = '"发布" OR "上线" OR "推出" OR "亮相"'
    
    # 组合: (英文词 OR 中文词) AND (英文动作 OR 中文动作) AND (日期限制)
    initial_query = f"""
    ({en_subjects} OR {cn_subjects}) 
    ({en_actions} OR {cn_actions}) 
    after:{target_date}
    """
    
    # 压缩空格，防止 Query 超长
    clean_query = " ".join(initial_query.split())
    
    return {
        "product_query": clean_query,
        "product_retries": 0,
        "product_verified_items": [] 
    }
# --- 板块 1: 新品 ReAct 循环逻辑 ---

def product_search_node(state: AgentState):
    """执行搜索"""
    results = search_new_products.invoke(state['product_query'])
    return {"product_raw_items": results}

def product_verify_node(state: AgentState):
    """核查搜索结果"""
    raw = state.get('product_raw_items', [])
    verified = []
    print(f"\n🔍 [Graph] 正在核实 {len(raw)} 条新品线索...")

    for item in raw:
        try:
            # 调用 agent_tools 里的核查工具
            res = verify_product_page.invoke(item['url'])

            # 只有真正发布且是近期的新品才保留
            if res.get('is_released') and res.get('is_recent'):
                # 格式化数据，方便主编直接使用
                info = (
                    f"Product: {res.get('product_name', 'Unknown')}\n"
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
    """反思：如果不够5条，换个角度搜"""
    new_retries = state['product_retries'] + 1
    current_q = state['product_query']
    
    print(f"🔄 [Reflect] 新品不足 (当前 {len(state['product_verified_items'])} 条)，第 {new_retries} 次重试...")
    
    # 让 LLM 生成新词
    msg = [
        SystemMessage(content="你是搜索策略专家。我们需要找到更多本周发布的 AI 硬件或应用。"),
        HumanMessage(content=f"""
        刚才搜的是: '{current_q}'。
        
        请生成一个新的搜索词。策略：
        1. **语言切换**：如果刚才含中文，这次只用英文；反之亦然。
        2. **关键词切换**：尝试 'AI Robot', 'AI App', 'LLM Service'。
        3. **格式要求**：只返回搜索词本身，不要废话。
        """)
    ]
    new_query = llm.invoke(msg).content
    print(f"💡 [Reflect] 新策略: {new_query}")
    
    return {"product_query": new_query, "product_retries": new_retries}

def should_continue_product(state: AgentState):
    """决策逻辑：凑够 5 条，或者试了 3 次就停"""
    count = len(state['product_verified_items'])
    retries = state['product_retries']
    
    if count >= 5 or retries >= 5:
        print(f"🛑 [Decision] 停止搜索 (Count: {count}, Retries: {retries})")
        return "join"
    return "reflect"

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

    # 收集所有原始数据
    raw_items = []

    # ==================== 解析新品 ====================
    for item_str in p_items:
        try:
            lines = item_str.strip().split('\n')
            data = {}
            for line in lines:
                if ":" in line:
                    key, val = line.split(":", 1)
                    data[key.strip()] = val.strip()

            if data.get("Product") and data.get("URL"):
                raw_items.append({
                    "type": "Product",
                    "title": data.get("Product"),
                    "url": data.get("URL"),
                    "description": data.get("Desc", ""),
                    "date": data.get("Date", "")
                })
        except Exception as e:
            print(f"⚠️ 解析新品出错: {e}")

    # ==================== 解析 HF 模型 ====================
    for item_str in h_items:
        try:
            # 提取 Model ID 和 URL
            model_match = re.search(r'Model:\s*(.+?)(?:\n|$)', item_str)
            url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', item_str)
            readme_match = re.search(r'README Summary ---\n(.+?)(?:\n=|$)', item_str, re.DOTALL)

            if model_match and url_match:
                raw_items.append({
                    "type": "HuggingFace",
                    "title": model_match.group(1).strip().replace("===", "").strip(),
                    "url": url_match.group(1).strip(),
                    "description": readme_match.group(1).strip()[:500] if readme_match else "",
                    "date": ""
                })
        except Exception as e:
            print(f"⚠️ 解析 HF 模型出错: {e}")

    # ==================== 解析 GitHub 项目 ====================
    for item_str in g_items:
        try:
            repo_match = re.search(r'Repo:\s*(.+?)(?:\n|$)', item_str)
            url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', item_str)
            lang_match = re.search(r'Language:\s*(.+?)(?:\n|$)', item_str)
            readme_match = re.search(r'README snippet ---\n(.+?)(?:\n=|$)', item_str, re.DOTALL)

            if repo_match and url_match:
                raw_items.append({
                    "type": "GitHub",
                    "title": repo_match.group(1).strip().replace("===", "").strip(),
                    "url": url_match.group(1).strip(),
                    "description": readme_match.group(1).strip()[:500] if readme_match else "",
                    "language": lang_match.group(1).strip() if lang_match else "Unknown",
                    "date": ""
                })
        except Exception as e:
            print(f"⚠️ 解析 GitHub 项目出错: {e}")

    # ==================== 解析论文 ====================
    for item_str in paper_items:
        try:
            title_match = re.search(r'Paper:\s*(.+?)(?:\n|$)', item_str)
            url_match = re.search(r'URL:\s*(.+?)(?:\n|$)', item_str)
            org_match = re.search(r'Organization:\s*(.+?)(?:\n|$)', item_str)
            abstract_match = re.search(r'Abstract:\s*(.+?)(?:\n=|$)', item_str, re.DOTALL)

            if title_match and url_match:
                raw_items.append({
                    "type": "Papers",
                    "title": title_match.group(1).strip().replace("===", "").strip(),
                    "url": url_match.group(1).strip(),
                    "description": abstract_match.group(1).strip()[:300] if abstract_match else "",
                    "organization": org_match.group(1).strip() if org_match else "",
                    "date": ""
                })
        except Exception as e:
            print(f"⚠️ 解析论文出错: {e}")

    # ==================== 用一次 LLM 调用处理所有数据 ====================
    if raw_items:
        # 构建 prompt
        items_text = ""
        for i, item in enumerate(raw_items):
            items_text += f"\n[{i}] 类型:{item['type']} | 标题:{item['title']} | 描述:{item['description'][:100]}...\n"

        prompt = f"""你是 AI 新闻编辑。请为以下 {len(raw_items)} 条新闻生成中文摘要和标签。

{items_text}

要求：
1. 每条新闻生成一句话的中文摘要（50字以内）
2. 每条新闻提取2-3个中文标签（格式：#标签）
3. 输出格式必须严格为 JSON 数组：
[
  {{"index": 0, "summary": "摘要文本", "tags": ["#标签1", "#标签2"]}},
  {{"index": 1, "summary": "摘要文本", "tags": ["#标签1", "#标签2"]}}
]

只输出 JSON，不要其他文字！"""

        try:
            response = llm.invoke(prompt).content
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
        all_news.append({
            "id": item_id,
            "title": item["title"],
            "source": item["type"],
            "tags": item.get("tags", ["#AI"]),
            "summary": item.get("summary", item["description"][:100]),
            "url": item["url"]
        })

    # 生成每日总结
    if all_news:
        titles_text = ", ".join([n["title"][:30] for n in all_news[:8]])
        summary_prompt = f"用一句话总结今天 AI 领域的主要进展（不超过50字）。今日新闻包括：{titles_text}"
        try:
            daily_summary = llm.invoke(summary_prompt).content.strip()
        except:
            daily_summary = f"今日共有 {len(all_news)} 条 AI 相关动态。"
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

# Product 板块的 ReAct 循环
workflow.add_edge("p_search", "p_verify")
workflow.add_conditional_edges(
    "p_verify",
    should_continue_product,
    {
        "join": "writer",      # 够了 -> 去汇总
        "reflect": "p_reflect" # 不够 -> 去反思
    }
)
workflow.add_edge("p_reflect", "p_search") # 反思完 -> 带着新词重搜

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



        