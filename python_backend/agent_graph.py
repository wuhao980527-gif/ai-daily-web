import os
import json
import uuid
import operator
from datetime import datetime, timedelta
from typing import Annotated, List, TypedDict
from langgraph.graph import StateGraph, END, START

# 引入工具
from agent_tools import (
    llm, search_new_products, verify_product_page, 
    fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers
)

# 再次确保云端无代理
if not os.getenv("LOCAL_VPN"):
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

# 定义状态
class AgentState(TypedDict):
    final_json: str
    product_query: str
    product_raw_items: List[dict]
    product_verified_items: Annotated[List[str], operator.add]
    hf_models: List[str]
    github_repos: List[str]
    tech_papers: List[str]

# ================= 节点定义 =================

def init_node(state):
    print("⚙️ [Init] 任务初始化...")
    d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    # 简单的搜索词，少即是多
    return {"product_query": f'("AI Product" OR "AI Model" OR "Release") after:{d}', "product_verified_items": []}

def product_search_node(state):
    # Tavily 搜索
    return {"product_raw_items": search_new_products.invoke(state['product_query'])}

def product_verify_node(state):
    raw = state.get('product_raw_items', [])
    verified = []
    print(f"🔍 [Verify] 核查 {len(raw)} 条数据...")
    
    for item in raw:
        try:
            # 关键：直接拼接 Tavily 的 content 给 AI 读
            full_text = f"Title: {item.get('title')}\nURL: {item.get('url')}\nContent: {item.get('content')}"
            res = verify_product_page.invoke(full_text)
            
            if res.get('is_released'):
                verified.append(f"Product: {res['product_name']} | Date: {res['release_date']} | Desc: {res['description']} | URL: {item['url']}")
        except: pass
    return {"product_verified_items": verified}

def hf_node(s): return {"hf_models": fetch_hf_trending_models.invoke({})}
def gh_node(s): return {"github_repos": fetch_github_trending.invoke({})}
def paper_node(s): return {"tech_papers": fetch_big_tech_papers.invoke({})}

def writer_node(state):
    print("\n✍️ [Writer] 生成 JSON...")
    today = datetime.now().strftime('%Y-%m-%d')
    all_data = {
        "Products": state.get('product_verified_items', []),
        "HF": state.get('hf_models', []),
        "GitHub": state.get('github_repos', []),
        "Papers": state.get('tech_papers', [])
    }
    
    # 让 LLM 输出前端需要的 JSON 格式
    prompt = f"""
    将数据转换为纯 JSON 格式。
    数据: {str(all_data)}
    
    要求:
    1. 根对象包含 "date", "summary", "news" 三个字段。
    2. "date" 为 "{today}"。
    3. "summary" 为 50字左右的中文摘要。
    4. "news" 是数组，每项包含: "id", "title", "source" (Product/HuggingFace/GitHub/Papers), "tags" (数组), "summary", "url"。
    5. 不要输出 Markdown 标记，只输出纯 JSON 字符串。
    """
    try:
        res = llm.invoke(prompt)
        clean_json = res.content.replace("```json","").replace("```","").strip()
        # 简单验证一下是不是 JSON
        json.loads(clean_json) 
        return {"final_json": clean_json}
    except:
        # 兜底：如果 LLM 疯了，返回一个空 JSON 保证程序不崩
        return {"final_json": json.dumps({"date": today, "summary": "生成失败", "news": []})}

# ================= 构建图 =================
wf = StateGraph(AgentState)
wf.add_node("init", init_node)
wf.add_node("p_search", product_search_node)
wf.add_node("p_verify", product_verify_node)
wf.add_node("hf", hf_node)
wf.add_node("gh", gh_node)
wf.add_node("paper", paper_node)
wf.add_node("writer", writer_node)

wf.add_edge(START, "init")
wf.add_edge("init", "p_search")
wf.add_edge("init", "hf")
wf.add_edge("init", "gh")
wf.add_edge("init", "paper")
wf.add_edge("p_search", "p_verify")
wf.add_edge("p_verify", "writer")
wf.add_edge("hf", "writer")
wf.add_edge("gh", "writer")
wf.add_edge("paper", "writer")
wf.add_edge("writer", END)

app = wf.compile()

# ================= 主入口 =================
if __name__ == "__main__":
    print("🚀 启动 (Cloud Mode)...")
    try:
        res = app.invoke({"product_retries": 0})
        json_str = res["final_json"]
        
        # 写入文件逻辑
        new_data = json.loads(json_str)
        # 补全 ID
        for n in new_data.get('news', []): 
            if 'id' not in n: n['id'] = str(uuid.uuid4())[:8]

        # 路径处理
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_path = os.path.join(current_dir, '..', 'data', 'news.json')
        
        # 读取旧数据
        existing_data = []
        if os.path.exists(data_path):
            try:
                with open(data_path, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
            except: pass
        
        # 插入新数据 (去重)
        existing_data = [d for d in existing_data if d['date'] != new_data['date']]
        existing_data.insert(0, new_data)
        
        # 写入
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
        print("✅ 成功写入 data/news.json")
    except Exception as e:
        print(f"❌ 失败: {e}")
        exit(1)