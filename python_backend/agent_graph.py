import os
import json
import uuid
import operator
from datetime import datetime, timedelta
from typing import Annotated, List, TypedDict

# LangGraph 组件
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import SystemMessage

# 引入工具
from agent_tools import (
    llm, 
    search_new_products, 
    verify_product_page, 
    fetch_hf_trending_models,
    fetch_github_trending,
    fetch_big_tech_papers
)

# 强制清理代理
if not os.getenv("LOCAL_VPN"):
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

# ================= 1. 定义状态 =================
class AgentState(TypedDict):
    final_json: str
    product_query: str
    product_retries: int
    product_raw_items: List[dict] # 这里存 Tavily 的完整结果
    product_verified_items: Annotated[List[str], operator.add]
    hf_models: List[str]
    github_repos: List[str]
    tech_papers: List[str]

# ================= 2. 定义节点 =================

def init_node(state: AgentState):
    print(f"⚙️ [Init] 初始化任务...")
    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    initial_query = f'("AI product" OR "AI model" OR "大模型" OR "发布") after:{target_date}'
    return {"product_query": initial_query, "product_retries": 0, "product_verified_items": []}

def product_search_node(state: AgentState):
    # 直接调用 search_new_products
    results = search_new_products.invoke(state['product_query'])
    return {"product_raw_items": results}

def product_verify_node(state: AgentState):
    raw = state.get('product_raw_items', [])
    verified = []
    print(f"🔍 [Verify] 正在基于搜索摘要进行核查 ({len(raw)}条)...")
    
    for item in raw:
        try:
            # ⚡️ 关键变化：直接把 Tavily 返回的 title 和 content 拼给 LLM 看
            # 不再访问 item['url']
            content_snippet = f"Title: {item.get('title')}\nContent: {item.get('content')}\nURL: {item.get('url')}"
            
            res = verify_product_page.invoke(content_snippet)
            
            if res.get('is_released'):
                info = f"Product: {res['product_name']} | Date: {res['release_date']} | Desc: {res['description']} | URL: {item['url']}"
                verified.append(info)
        except Exception as e:
            print(f"Verify Error: {e}")
            pass
            
    return {"product_verified_items": verified}

def product_reflect_node(state: AgentState):
    new_retries = state['product_retries'] + 1
    print(f"🔄 [Reflect] 重试第 {new_retries} 次...")
    backups = ["New AI Agent", "LLM release", "Sora"]
    new_q = backups[new_retries % len(backups)]
    return {"product_query": new_q, "product_retries": new_retries}

def should_continue_product(state: AgentState):
    if len(state['product_verified_items']) >= 3 or state['product_retries'] >= 2:
        return "join"
    return "reflect"

def hf_node(state: AgentState):
    return {"hf_models": fetch_hf_trending_models.invoke({})}

def github_node(state: AgentState):
    return {"github_repos": fetch_github_trending.invoke({})}

def paper_node(state: AgentState):
    return {"tech_papers": fetch_big_tech_papers.invoke({})}

def writer_node(state: AgentState):
    print("\n✍️ [Writer] 生成最终 JSON...")
    all_data = {
        "Products": state.get('product_verified_items', []),
        "HuggingFace": state.get('hf_models', []),
        "GitHub": state.get('github_repos', []),
        "Papers": state.get('tech_papers', [])
    }
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    prompt = f"""
    将以下 AI 数据转换为 JSON。
    数据: {str(all_data)}
    
    要求:
    1. 保留所有有效条目，不要删减。
    2. summary 字段要写 50-80 字的中文深度解析。
    3. tags 生成 3 个中文标签。
    4. 必须包含 id, title, source, tags, summary, url 字段。
    5. source 只能是: "Product", "HuggingFace", "GitHub", "Papers"。
    
    目标格式:
    {{
        "date": "{today_str}",
        "summary": "日报摘要...",
        "news": [ ... ]
    }}
    返回纯 JSON。
    """
    try:
        response = llm.invoke(prompt)
        clean_json = response.content.replace("```json", "").replace("```", "").strip()
        return {"final_json": clean_json}
    except Exception as e:
        print(f"❌ Writer Error: {e}")
        # 返回一个空数据的 JSON 防止崩溃
        return {"final_json": json.dumps({"date": today_str, "summary": "Error", "news": []})}

# ================= 3. 构建图谱 =================
workflow = StateGraph(AgentState)
workflow.add_node("init", init_node)
workflow.add_node("p_search", product_search_node)
workflow.add_node("p_verify", product_verify_node)
workflow.add_node("p_reflect", product_reflect_node)
workflow.add_node("hf_fetch", hf_node)
workflow.add_node("gh_fetch", github_node)
workflow.add_node("paper_fetch", paper_node)
workflow.add_node("writer", writer_node)

workflow.add_edge(START, "init")
workflow.add_edge("init", "p_search")
workflow.add_edge("init", "hf_fetch")
workflow.add_edge("init", "gh_fetch")
workflow.add_edge("init", "paper_fetch")
workflow.add_edge("p_search", "p_verify")
workflow.add_conditional_edges("p_verify", should_continue_product, {"join": "writer", "reflect": "p_reflect"})
workflow.add_edge("p_reflect", "p_search")
workflow.add_edge("hf_fetch", "writer")
workflow.add_edge("gh_fetch", "writer")
workflow.add_edge("paper_fetch", "writer")
workflow.add_edge("writer", END)

app = workflow.compile()

if __name__ == "__main__":
    print("🚀 启动 AI 日报生成器 (Fast Mode)...")
    try:
        final_state = app.invoke({"product_retries": 0})
        # ... 后续写入文件逻辑保持不变，为了省篇幅我省略了，你可以直接保留你原来的 main 函数部分 ...
        # (请确保这里的 main 函数逻辑和你之前的一样)
        
        # 为了方便你直接复制，我把写入部分也补全：
        json_str = final_state["final_json"]
        try:
            new_daily_data = json.loads(json_str)
            for item in new_daily_data.get('news', []):
                if 'id' not in item: item['id'] = str(uuid.uuid4())[:8]
        except:
            print(json_str); exit(1)
            
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_file_path = os.path.join(current_dir, '..', 'data', 'news.json')
        existing_data = []
        if os.path.exists(data_file_path):
            with open(data_file_path, 'r', encoding='utf-8') as f:
                try: existing_data = json.load(f)
                except: pass
        today = new_daily_data['date']
        existing_data = [d for d in existing_data if d['date'] != today]
        existing_data.insert(0, new_daily_data)
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        print("✅ 完成！")

    except Exception as e:
        print(f"❌ 运行错误: {e}")
        import traceback; traceback.print_exc()
        exit(1)