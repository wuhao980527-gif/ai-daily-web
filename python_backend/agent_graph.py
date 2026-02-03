import os
import json
import uuid
import operator
from datetime import datetime, timedelta
from typing import Annotated, List, TypedDict

# LangGraph 组件
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import SystemMessage, HumanMessage

# 引入工具
from agent_tools import (
    llm, 
    search_new_products, 
    verify_product_page, 
    fetch_hf_trending_models,
    fetch_github_trending,
    fetch_big_tech_papers
)

# ========================================================
# 🌍 代理设置 (核心修改处)
# 作用：GitHub Actions (云端) 不需要代理，直连速度更快
# 本地运行如果需要代理，请在 .env 里加一行 LOCAL_VPN=true
# ========================================================
if os.getenv("LOCAL_VPN"):
    os.environ["http_proxy"] = "http://127.0.0.1:7897"
    os.environ["https_proxy"] = "http://127.0.0.1:7897"
    print("🌍 检测到 LOCAL_VPN 变量，已开启本地代理模式...")
else:
    print("☁️ 未检测到 LOCAL_VPN，使用云端直连模式 (GitHub Actions)...")


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
    
    # 搜索词策略 (保持原样)
    en_subjects = '"AI product" OR "AI model" OR "Embodied AI" OR "Humanoid Robot" '
    en_actions = '"launched" OR "released" OR "unveiled" OR "announced"'
    cn_subjects = '"AI新品" OR "大模型" OR "具身智能" OR "人形机器人" '
    cn_actions = '"发布" OR "上线" OR "推出" OR "亮相"'
    
    initial_query = f"({en_subjects} OR {cn_subjects}) ({en_actions} OR {cn_actions}) after:{target_date}"
    clean_query = " ".join(initial_query.split())
    
    return {"product_query": clean_query, "product_retries": 0, "product_verified_items": []}

def product_search_node(state: AgentState):
    results = search_new_products.invoke(state['product_query'])
    return {"product_raw_items": results}

def product_verify_node(state: AgentState):
    raw = state.get('product_raw_items', [])
    verified = []
    print(f"🔍 [Verify] 正在核查 {len(raw)} 条线索...")
    
    for item in raw:
        try:
            res = verify_product_page.invoke(item['url'])
            # 只要是发布的，全部保留，不轻易过滤
            if res.get('is_released'):
                info = f"Product: {res['product_name']} | Date: {res['release_date']} | Desc: {res['description']} | URL: {item['url']}"
                verified.append(info)
        except Exception:
            pass
            
    return {"product_verified_items": verified}

def product_reflect_node(state: AgentState):
    new_retries = state['product_retries'] + 1
    print(f"🔄 [Reflect] 结果不足，第 {new_retries} 次重试...")
    # 简单的备用词策略
    backups = ["LLM Agent Framework", "New AI Hardware", "Sora alternative", "Robotics AI"]
    new_q = backups[new_retries % len(backups)]
    return {"product_query": new_q, "product_retries": new_retries}

def should_continue_product(state: AgentState):
    # 策略：只要有 4 条以上就够了（保证和你的报告量级一致）
    if len(state['product_verified_items']) >= 4 or state['product_retries'] >= 3:
        return "join"
    return "reflect"

# --- API 直连节点 ---
def hf_node(state: AgentState):
    return {"hf_models": fetch_hf_trending_models.invoke({})}

def github_node(state: AgentState):
    return {"github_repos": fetch_github_trending.invoke({})}

def paper_node(state: AgentState):
    return {"tech_papers": fetch_big_tech_papers.invoke({})}

# --- 核心：Writer 生成 JSON (对应网页需求) ---
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
    
    # Prompt: 强制全量保留，绝不缩水
    prompt = f"""
    你是一个专业 AI 数据分析师。请将以下抓取到的数据，转化为符合前端标准的 **JSON 格式**。
    
    **原始数据**:
    {str(all_data)}
    
    **重要指令**:
    1. **数量不设上限**：请保留原始数据中所有有效的内容（Products, HuggingFace, GitHub 等全部保留）。不要因为为了精简而删除任何条目！
    2. **内容详实**：
       - 对于 `summary` 字段，请将原始数据中的“功能+评价”或“简介+用途”进行合并，写成一段详实的中文描述（约 50-80 字）。
       - 严禁只写一句话！必须包含具体的技术参数、功能点和应用场景，保持专业深度。
    3. **Tags 生成**：为每条新闻生成 3 个精准的中文标签（如 #AI芯片 #大模型 #开源）。
    4. **Source 映射**：
       - Products -> "Product"
       - HuggingFace -> "HuggingFace"
       - GitHub -> "GitHub"
       - Papers -> "Papers"

    **目标 JSON 结构**:
    {{
        "date": "{today_str}",
        "summary": "这里写一段约 50 字的中文摘要，总结今天的 AI 趋势。",
        "news": [
            {{
                "id": "随机生成的短ID",
                "title": "新闻标题(中文翻译)",
                "source": "来源分类",
                "tags": ["Tag1", "Tag2", "Tag3"],
                "summary": "详实的中文描述(包含功能、评价、用途等详细信息)",
                "url": "原始链接"
            }}
        ]
    }}
    
    **必须返回纯 JSON 字符串，不要 Markdown 格式。**
    """
    
    response = llm.invoke(prompt)
    # 清洗 Markdown 标记
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
    print("🚀 启动 AI 日报生成器 (Website Data Mode)...")
    
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
            
        print(f"✅ 数据生成成功 (包含 {len(new_daily_data['news'])} 条新闻)，准备写入文件...")
        
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
        
        # 5. 插入新数据 (覆盖同日期的)
        today = new_daily_data['date']
        existing_data = [d for d in existing_data if d['date'] != today]
        existing_data.insert(0, new_daily_data)
        
        # 6. 写入保存
        with open(data_file_path, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
            
        print(f"🎉 成功！最新全量日报已写入: {data_file_path}")
        print("💡 下一步: 在终端运行 'git push' 即可更新网站！")

    except Exception as e:
        print(f"❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()