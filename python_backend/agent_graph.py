import os
import json
import uuid
import operator
from datetime import datetime, timedelta
from typing import Annotated, List, TypedDict
from langgraph.graph import StateGraph, END, START

# 引入新工具
from agent_tools import (
    llm, search_new_products, verify_product_page, 
    fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers
)

# 确保云端无代理
if not os.getenv("LOCAL_VPN"):
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

class AgentState(TypedDict):
    final_json: str
    product_query: str
    product_retries: int
    product_raw_items: List[dict]
    product_verified_items: Annotated[List[str], operator.add]
    hf_models: List[str]
    github_repos: List[str]
    tech_papers: List[str]

def init_node(state):
    print("⚙️ [Init] 任务初始化...")
    d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    return {"product_query": f'("AI Product" OR "AI Model" OR "Release") after:{d}', "product_retries": 0, "product_verified_items": []}

def product_search_node(state):
    # 这一步 Tavily 已经带回了 content
    return {"product_raw_items": search_new_products.invoke(state['product_query'])}

def product_verify_node(state):
    raw = state.get('product_raw_items', [])
    verified = []
    print(f"🔍 [Verify] 核查 {len(raw)} 条数据 (离线模式)...")
    
    for item in raw:
        try:
            # 关键修改：把 Tavily 抓到的 content 拼起来喂给 AI
            # 绝对不要再用 requests 去访问 item['url']！
            full_text = f"Title: {item.get('title')}\nURL: {item.get('url')}\nContent: {item.get('content')}"
            
            res = verify_product_page.invoke(full_text)
            
            if res.get('is_released'):
                verified.append(f"Product: {res['product_name']} | Date: {res['release_date']} | Desc: {res['description']} | URL: {item['url']}")
        except: pass
    return {"product_verified_items": verified}

def product_reflect_node(state):
    # 简单的重试逻辑
    new_r = state['product_retries'] + 1
    print(f"🔄 [Reflect] 重试第 {new_retries} 次...")
    return {"product_query": "New AI Tools Release", "product_retries": new_r}

def should_continue(state):
    if len(state['product_verified_items']) >= 3 or state['product_retries'] >= 2:
        return "join"
    return "reflect"

def writer_node(state):
    print("\n✍️ [Writer] 正在生成 JSON...")
    today = datetime.now().strftime('%Y-%m-%d')
    all_data = {
        "Products": state.get('product_verified_items', []),
        "HF": state.get('hf_models', []),
        "GitHub": state.get('github_repos', []),
        "Papers": state.get('tech_papers', [])
    }
    
    prompt = f"""
    将数据转为 JSON (date: {today})。
    数据: {str(all_data)}
    要求: 
    1. 包含 summary, news 列表 (字段: id, title, source, tags, summary, url)。
    2. summary 必须详实 (50字+)。
    3. 纯 JSON 返回。
    """
    try:
        res = llm.invoke(prompt)
        return {"final_json": res.content.replace("```json","").replace("```","").strip()}
    except:
        return {"final_json": json.dumps({"date": today, "summary": "Error", "news": []})}

# 构建图
wf = StateGraph(AgentState)
wf.add_node("init", init_node)
wf.add_node("p_search", product_search_node)
wf.add_node("p_verify", product_verify_node)
wf.add_node("p_reflect", product_reflect_node)
wf.add_node("hf", lambda s: {"hf_models": fetch_hf_trending_models.invoke({})})
wf.add_node("gh", lambda s: {"github_repos": fetch_github_trending.invoke({})})
wf.add_node("paper", lambda s: {"tech_papers": fetch_big_tech_papers.invoke({})})
wf.add_node("writer", writer_node)

wf.add_edge(START, "init")
wf.add_edge("init", "p_search")
wf.add_edge("init", "hf")
wf.add_edge("init", "gh")
wf.add_edge("init", "paper")
wf.add_edge("p_search", "p_verify")
wf.add_conditional_edges("p_verify", should_continue, {"join": "writer", "reflect": "p_reflect"})
wf.add_edge("p_reflect", "p_search")
wf.add_edge("hf", "writer")
wf.add_edge("gh", "writer")
wf.add_edge("paper", "writer")
wf.add_edge("writer", END)

app = wf.compile()

if __name__ == "__main__":
    print("🚀 启动 (Cloud Mode)...")
    try:
        res = app.invoke({"product_retries": 0})
        # 写入逻辑
        json_str = res["final_json"]
        new_data = json.loads(json_str)
        # ... (这里省略文件写入代码，保持你原来的即可，核心是上面逻辑变了) ...
        # 为了完整性，简单写一下写入
        current_dir = os.path.dirname(os.path.abspath(__file__))
        f_path = os.path.join(current_dir, '..', 'data', 'news.json')
        
        # 补全 ID
        for n in new_data.get('news', []): 
            if 'id' not in n: n['id'] = str(uuid.uuid4())[:8]

        old = []
        if os.path.exists(f_path):
            with open(f_path, 'r') as f: old = json.load(f)
        
        old = [d for d in old if d['date'] != new_data['date']]
        old.insert(0, new_data)
        
        with open(f_path, 'w') as f: json.dump(old, f, ensure_ascii=False, indent=2)
        print("✅ 成功写入 news.json")
    except Exception as e:
        print(f"❌ 失败: {e}")
        exit(1)