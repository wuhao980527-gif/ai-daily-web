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

load_dotenv()

# ================= 1. 环境与初始化 =================
if not os.getenv("LOCAL_VPN"):
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

llm = ChatOpenAI(
    openai_api_key=os.getenv("MY_API_KEY"),
    base_url=os.getenv("MY_BASE_URL"),
    model_name=os.getenv("MY_MODEL_NAME"),
    temperature=0.5,
    request_timeout=300
)

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ================= 2. 纯 API 工具集 =================

@tool
def search_new_products(query: str) -> List[Dict]:
    """Tavily 搜索工具，用于查找最新的 AI 产品发布信息。"""
    print(f"   🕵️ [Tool] 正在搜索: {query}")
    try:
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
    """AI 核查工具，用于根据文本判断产品是否真实发布。"""
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
        摘要：{text}
        """)
        res = (prompt | verifier).invoke({"text": content_snippet[:3000]})
        return res.model_dump()
    except Exception as e:
        print(f"      ⚠️ 跳过: {e}")
        return {"is_released": False, "description": "Error"}

@tool
def fetch_hf_trending_models() -> List[str]:
    """获取 Hugging Face 热门模型列表。"""
    print("   🤗 [Tool] 获取 HF 榜单 (Requests版)...")
    try:
        url = "https://huggingface.co/api/models"
        params = {"sort": "likes7d", "direction": "-1", "limit": 10}
        
        # 强制 10秒超时
        resp = requests.get(url, params=params, timeout=10)
        
        models = resp.json()
        results = []
        limit_date = datetime.now() - timedelta(days=7)
        
        for m in models:
            created_at = m.get('createdAt')
            if created_at:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00')).replace(tzinfo=None)
                if dt >= limit_date:
                    results.append(f"Model: {m['modelId']} | Likes: {m['likes']} | URL: https://huggingface.co/{m['modelId']}")
                    if len(results) >= 5: break
        return results
    except Exception as e:
        print(f"      ⚠️ HF 获取失败 (已跳过): {e}")
        return []

@tool
def fetch_github_trending() -> List[str]:
    """获取 GitHub 热门 AI 项目列表。"""
    print("   🐙 [Tool] 获取 GitHub 榜单...")
    try:
        date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{date_str}&sort=stars&order=desc&per_page=5"
        resp = requests.get(url, headers={"User-Agent": "NewsAgent"}, timeout=10)
        items = resp.json().get("items", [])
        return [f"Repo: {i['full_name']} | Stars: {i['stargazers_count']} | Desc: {i['description']} | URL: {i['html_url']}" for i in items]
    except: return []

@tool
def fetch_big_tech_papers() -> List[str]:
    """搜索大厂发布的最新 AI 论文。"""
    print("   📜 [Tool] 获取论文...")
    try:
        res = tavily_client.search('site:huggingface.co/papers ("OpenAI" OR "DeepSeek" OR "Google")', max_results=5)
        return [f"Paper: {r['title']} | URL: {r['url']}" for r in res.get('results', [])]
    except: return []

ALL_TOOLS = [search_new_products, verify_product_page, fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers]