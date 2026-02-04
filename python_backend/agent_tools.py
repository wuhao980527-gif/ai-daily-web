import os
import requests
from typing import List, Dict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# LangChain 组件
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from tavily import TavilyClient
from huggingface_hub import HfApi

load_dotenv()

# ================= 1. 环境与初始化 =================
# 核心：在云端强制清除所有代理设置，防止连接 127.0.0.1 导致超时
if not os.getenv("LOCAL_VPN"):
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

# 初始化 LLM (超时设为 5分钟，防断)
llm = ChatOpenAI(
    openai_api_key=os.getenv("MY_API_KEY"),
    base_url=os.getenv("MY_BASE_URL"),
    model_name=os.getenv("MY_MODEL_NAME"),
    temperature=0.5,
    request_timeout=300
)

# 初始化 Tavily
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ================= 2. 纯 API 工具集 (无爬虫风险) =================

@tool
def search_new_products(query: str) -> List[Dict]:
    """Tavily 搜索，带回摘要，不访问原网页"""
    print(f"   🕵️ [Tool] 正在搜索: {query}")
    try:
        # include_answer=True 让 Tavily 给个总结，减少 LLM 负担
        # search_depth="advanced" 保证质量
        response = tavily_client.search(
            query, 
            max_results=5, 
            search_depth="advanced", 
            include_answer=True 
        )
        return response.get('results', [])
    except Exception as e:
        print(f"      ❌ 搜索报错: {e}")
        return []

@tool
def verify_product_page(content_snippet: str) -> dict:
    """纯文本核查，不联网，绝对稳"""
    print(f"      🧠 [Tool] AI 正在核查信息...")
    
    class ProductVerification(BaseModel):
        product_name: str = Field(description="产品名称")
        is_released: bool = Field(description="是否已正式发布")
        is_recent: bool = Field(description="是否为近期发布")
        release_date: str = Field(description="发布日期")
        description: str = Field(description="功能描述")

    try:
        verifier = llm.with_structured_output(ProductVerification)
        prompt = ChatPromptTemplate.from_template("""
        根据以下摘要判断是否为**近期发布的新 AI 产品**。
        仅依据文本判断，不要联网。
        
        摘要：{text}
        """)
        # 截取前 3000 字防止 Token 溢出
        res = (prompt | verifier).invoke({"text": content_snippet[:3000]})
        return res.model_dump()
    except Exception as e:
        print(f"      ⚠️ 跳过: {e}")
        return {"is_released": False, "description": "Error"}

@tool
def fetch_hf_trending_models() -> List[str]:
    """HuggingFace 官方 API"""
    print("   🤗 [Tool] 获取 HF 榜单...")
    try:
        api = HfApi()
        models = api.list_models(sort="likes7d", direction=-1, limit=10)
        results = []
        limit_date = datetime.now().astimezone() - timedelta(days=7)
        for m in models:
            if m.created_at and m.created_at >= limit_date:
                results.append(f"Model: {m.modelId} | Likes: {m.likes} | URL: https://huggingface.co/{m.modelId}")
                if len(results) >= 5: break
        return results
    except: return []

@tool
def fetch_github_trending() -> List[str]:
    """GitHub 官方 API"""
    print("   🐙 [Tool] 获取 GitHub 榜单...")
    try:
        date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{date_str}&sort=stars&order=desc&per_page=5"
        # 必须加 User-Agent 否则 GitHub 会拒绝
        resp = requests.get(url, headers={"User-Agent": "NewsAgent"}, timeout=10)
        items = resp.json().get("items", [])
        return [f"Repo: {i['full_name']} | Stars: {i['stargazers_count']} | Desc: {i['description']} | URL: {i['html_url']}" for i in items]
    except: return []

@tool
def fetch_big_tech_papers() -> List[str]:
    """Tavily 搜论文"""
    print("   📜 [Tool] 获取论文...")
    try:
        # Tavily 搜 HF Papers 非常稳
        res = tavily_client.search('site:huggingface.co/papers ("OpenAI" OR "DeepSeek" OR "Google")', max_results=5)
        return [f"Paper: {r['title']} | URL: {r['url']}" for r in res.get('results', [])]
    except: return []

# 导出工具列表
ALL_TOOLS = [search_new_products, verify_product_page, fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers]