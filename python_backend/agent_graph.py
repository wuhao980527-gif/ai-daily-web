import os
import json
import uuid
import operator
from datetime import datetime, timedelta
from typing import Annotated, List, TypedDict

# LangChain / LangGraph 组件
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import StateGraph, END, START
from dotenv import load_dotenv

# 引入工具
from agent_tools import (
    llm, 
    search_new_products, 
    verify_product_page, 
    fetch_hf_trending_models,
    fetch_github_trending,
    fetch_big_tech_papers
)

# 加载环境变量
load_dotenv()

# ================= 1. 定义状态 =================
class AgentState(TypedDict):
    final_json: str  # 最终生成的 JSON 字符串
    
    # 中间数据
    product_query: str
    product_retries: int
    product_raw_items: List[dict]
    product_verified_items: Annotated[List[str], operator.add]
    
    hf_models: List[str]
    github_repos: List[str]
    tech_papers: List[str]

# ================= 2. 定义节点 =================

def init_node(state: AgentState):
    """初始化搜索词"""
    print(f"⚙️ [Init] 初始化任务...")
    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    # 构造更精准的搜索词
    query = f'("AI Product" OR "AI Model" OR "AI新品") ("released" OR "launch" OR "发布") after:{target_date}'
    return {"product_query": query, "product_retries": 0, "product_verified_items": []}

def product_search_node(state: AgentState):
    results = search_new_products.invoke(state['product_query'])
    return {"product_raw_items": results}

def product_verify_node(state: AgentState):
    raw = state.get('product_raw_items', [])
    verified = []
    print(f"🔍 [Verify] 正在核查 {len(raw)} 条线索...")
    
    for item in raw:
        try:
            # 这里的 item['url'] 传给工具
            res = verify_product_page.invoke(item['url'])
            if res.get('is_released'):
                # 拼接成字符串供 Writer 参考
                info = f"Product: {res['product_name']} | Date: {res['release_date']} | Desc: {res['description']} | URL: {item['url']}"
                verified.append(info)
        except Exception:
            pass
            
    return {"product_verified_items": verified}

def product_reflect_node(state: AgentState):
    """如果没搜到，换个词重试"""
    new_retries = state['product_retries'] + 1
    print(f"🔄 [Reflect] 结果不足，第 {new_retries} 次重试...")
    # 简单的备用词策略
    backups = ["LLM Agent Framework", "New AI Hardware", "Sora alternative"]
    new_q = backups[new_retries % len(backups)]
    return {"product_query": new_q, "product_retries": new_retries}

def should_continue_product(state: AgentState):
    # 只要有 2 条以上有效新闻，或者试了 2 次，就停止
    if len(state['product_verified_items']) >= 2 or state['product_retries'] >= 2:
        return "join"
    return "reflect"

# --- API 直连节点 ---
def hf_node(state: AgentState):
    return {"hf_models": fetch_hf_trending_models.invoke({})}

def github_node(state: AgentState):
    return {"github_repos": fetch_github_trending.invoke({})}

def paper_node(state: AgentState):
    return {"tech_papers": fetch_big_tech_papers.invoke({})}

# --- 核心：Writer 生成 JSON ---
def writer_node(state: AgentState):
    print("\n✍️ [Writer] 正在生成前端所需的 JSON 数据...")
    
    # 汇总所有数据
    all_data = {
        "Products": state.get('product_verified_items', []),
        "HuggingFace": state.get('hf_models', []),
        "GitHub": state.get('github_repos', []),
        "Papers": state.get('tech_papers', [])
    }
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    # Prompt: 强制要求输出 JSON，且字段要对应前端 news.json 的结构
    prompt = f"""
    你是一个 AI 新闻聚合器。请将以下抓取到的数据，转化为符合前端标准的 **JSON 格式**。
    
    **原始数据**:
    {str(all_data)}
    
    **目标 JSON 结构**:
    {{
        "date": "{today_str}",
        "summary": "这里写一段约 50 字的中文摘要，总结今天的 AI 趋势。",
        "news": [
            {{
                "id": "随机生成的短ID",
                "title": "新闻标题(中文)",
                "source": "来源(如 Product, HuggingFace, GitHub)",
                "tags": ["Tag1", "Tag2"],
                "summary": "一句话简介(中文)，不要太长",
                "url": "原始链接"
            }}
        ]
    }}
    
    **要求**:
    1. 必须返回纯 JSON 字符串，不要 Markdown 格式。
    2. news 列表最多保留 6-8 条最有价值的内容。
    3. 翻译所有英文内容为中文。
    """
    
    response = llm.invoke(prompt)
    # 清洗可能存在的 Markdown 标记
    clean_json = response.content.replace("```json", "").replace("```", "").strip()
    
    return {"final_json": clean_json}

# ================= 3. 构建图谱 =================
workflow = StateGraph(AgentState)

# 添加节点
workflow.add_node("init", init_node)
workflow.add_node("p_search", product_search_node)
workflow.add_node("p_verify", product_verify_node)
workflow.add_node("p_reflect", product_reflect_node)
workflow.add_node("hf_fetch", hf_node)
workflow.add_node("gh_fetch", github_node)
workflow.add_node("paper_fetch", paper_node)
workflow.add_node("writer", writer_node)

# 定义连线
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

# ================= 4. 主程序：运行并写入文件 =================
if __name__ == "__main__":
    print("🚀 启动 AI 日报生成器 (Local Mode)...")
    
    try:
        # 1. 运行 Agent
        final_state = app.invoke({"product_retries": 0})
        json_str = final_state["final_json"]
        
        # 2. 解析 JSON 确保格式正确
        try:
            new_daily_data = json.loads(json_str)
            # 补救措施：如果 LLM 忘了生成 id，我们手动补上
            for item in new_daily_data.get('news', []):
                if 'id' not in item:
                    item['id'] = str(uuid.uuid4())[:8]
        except json.JSONDecodeError:
            print("❌ LLM 生成的 JSON 格式有误，原始输出如下：")
            print(json_str)
            exit(1)
            
        print("✅ 数据生成成功，准备写入文件...")
        
        # 3. 路径定位：找到 ../data/news.json
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_file_path = os.path.join(current_dir, '..', 'data', 'news.json')
        
        # 4. 读取旧数据
        existing_data = []
        if os.path.exists(data_file_path):
            with open(data_file_path, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except:
                    pass
        
        # 5. 插入新数据 (如果今天已存在则覆盖，否则插入头部)
        today = new_daily_data['date']
        # 过滤掉旧的同日期数据
        existing_data = [d for d in existing_data if d['date'] != today]
        # 插入新的
        existing_data.insert(0, new_daily_data)
        
        # 6. 写入保存
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
        print(f"🎉 成功！文件已更新: {data_file_path}")
        print("💡 下一步: 在终端运行 'git push' 即可推送到网站！")

    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()