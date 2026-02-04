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
os.environ["http_proxy"] = "http://127.0.0.1:7897"
os.environ["https_proxy"] = "http://127.0.0.1:7897"
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
        # 调用 agent_tools 里的核查工具
        res = verify_product_page.invoke(item['url'])
        
        # 只有真正发布且是近期的新品才保留
        if res['is_released'] and res['is_recent']:
            # 格式化数据，方便主编直接使用
            info = (
                f"Product: {res['product_name']}\n"
                f"Date: {res['release_date']}\n"  # <--- 新增这一行
                f"Desc: {res['description']}\n"
                f"URL: {item['url']}"
            )
            verified.append(info)
            
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
    return {"hf_models": fetch_hf_trending_models.invoke({})}

def github_node(state: AgentState):
    return {"github_repos": fetch_github_trending.invoke({})}

def paper_node(state: AgentState):
    return {"tech_papers": fetch_big_tech_papers.invoke({})}

# --- 核心：主编汇总 ---

def writer_node(state: AgentState):
    """汇总四个板块的数据，生成 Markdown 日报"""
    print("\n✍️ [Writer] 数据就位，生成最终简报...")
    
    # 数据判空处理，防止 None 导致报错
    p_items = state.get('product_verified_items', [])
    h_items = state.get('hf_models', [])
    g_items = state.get('github_repos', [])
    paper_items = state.get('tech_papers', [])
    
    # 拼装上下文
    context = f"""
    【1. 新品发布】
    {chr(10).join(p_items) if p_items else "无重大发布。"}
    
    【2. Hugging Face 热榜】
    {chr(10).join(h_items) if h_items else "接口未返回数据。"}
    
    【3. GitHub 趋势】
    {chr(10).join(g_items) if g_items else "接口未返回数据。"}
    
    【4. 大厂论文】
    {chr(10).join(paper_items) if paper_items else "无最新论文。"}
    """
    
    # 详细的 Prompt
    prompt = f"""
    你是一名极其严谨的 AI 数据分析师。请整理一份 **AI 每日数据简报 ({datetime.now().strftime('%Y-%m-%d')})**。
    
    **⚠️ 格式排版铁律 (Python Markdown 兼容性要求)**：
    1. **4空格缩进**：嵌套的子列表（如功能、评价、简介），必须使用 **4个空格** 的缩进！少于4个会被解析为同一行。
    2. **空行隔离**：在进入列表 `-` 之前，必须先留一个 **空行**。
    3. **中英双语**：保留英文标题，但描述全部翻译成中文。

    **核心原则**：
    1. **客观汇总**：仅罗列事实，不要添加任何主观评论（如“太强了”、“颠覆性”）。
    2. **拒绝幻觉**：如果情报中只有 2 条新品，就只写 2 条，不要编造。
    3. **格式规范**：严格遵守下方的 Markdown 结构。
    4. **格式规范**：主要内容翻译成中文，标题可以沿用英文。

    **输出格式模板**：

    # 📊 AI 全景数据简报 ({datetime.now().strftime('%Y-%m-%d')})

    ## 1. 🆕 全球 AI 新品发布 (Product Launches)
    *筛选已核实的真实发布信息*

    - **[产品名]** ([Link](url))📅 <提取Date字段>
        - **功能**: <功能描述&主要内容>
        - **评价**: <客观评价/市场意义>


    ## 2. 🤗 Hugging Face 热门模型 (Trending Models)
    *基于 7 天内点赞数 Top 5*

    - **[Model ID]** ([Link](url)) (⭐Likes)📅<提取Date字段>
        - **简介**: <阅读 'README Summary'，总结该模型最核心的亮点（如：是微调版？是量化版？支持多长 Context？在某个Benchmark上超越了谁？），或者有什么其他亮点？>
        - **场景**: <根据 README 里的 Usage 或描述判断。例如：'适合医疗问答'、'适合低显存部署'、'适合角色扮演'、'适合代码补全'>

    ## 3. 🐙 GitHub 开发者趋势 (Dev Trends)
    *基于 7 天内 Stars 增长 Top 5*

    - **[项目名]** ([Link](url)) (⭐Stars)📅<提取Date字段>
        - **简介**: <阅读 'README snippet'，概括项目功能&亮点>
        - **用途**: <推断其面向人群，或者应用场景。>

    ## 4. 📜 大厂前沿论文 (Big Tech Papers)
    *聚焦 Google, OpenAI, Meta, Anthropic, Qwen 等大厂近 7 天动态*

    - **[<提取Source字段>] [英文标题] (中文译名)** ([Link](url))📅<提取Date字段>
        - **摘要**: <阅读 'Snippet'，用一句话概括核心贡献（如：提出新架构、解决幻觉问题、发布新模型、优化推理速度）>
        - **领域**: <归纳技术方向。例如：'大模型对齐'、'多模态生成'、'高效推理'、'Agent 规划'>

    ---
    *数据来源: Tavily, Hugging Face, GitHub API, Arxiv | 生成时间: {datetime.now().strftime('%H:%M')}*

    **原始情报数据**：
    {context}
    
    请直接输出 Markdown 内容，不要包含 "Here is the report" 等废话。
    """
    
    response = llm.invoke(prompt)
    return {"final_report": response.content}

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
        today_news = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "content": report
        }

        # 读取现有数据
        try:
            with open("data/news.json", "r", encoding="utf-8") as f:
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
        with open("data/news.json", "w", encoding="utf-8") as f:
            json.dump(all_news, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 数据已保存到 data/news.json")

    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()



        