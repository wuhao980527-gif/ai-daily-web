import os
import json
from typing import List, Dict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# LangChain & Tools
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from tavily import TavilyClient
from huggingface_hub import HfApi

load_dotenv()

# ================= 1. 环境配置 =================
# 强制清除代理，确保云端直连 Tavily API
if not os.getenv("LOCAL_VPN"):
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

# 初始化核心组件
llm = ChatOpenAI(
    openai_api_key=os.getenv("MY_API_KEY"),
    base_url=os.getenv("MY_BASE_URL"),
    model_name=os.getenv("MY_MODEL_NAME"),
    temperature=0.5,
    request_timeout=300 # 给 5 分钟，足够生成 JSON
)
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ================= 2. 纯 API 工具集 (无爬虫) =================

@tool
def search_new_products(query: str) -> List[Dict]:
    """【Tavily 代理搜索】直接获取内容，不自己爬网页，防止被封"""
    print(f"   🕵️ [Tool] Tavily 搜索中: {query}")
    try:
        # include_raw_content=True 是关键！让 Tavily 把网页内容直接带回来
        response = tavily_client.search(
            query, 
            max_results=6, 
            search_depth="advanced", 
            include_answer=True
        )
        return response.get('results', [])
    except Exception as e:
        print(f"      ❌ 搜索报错: {e}")
        return []

@tool
def verify_product_page(content_snippet: str) -> dict:
    """【AI 离线核查】只读 Tavily 传回来的文字，不联网，绝对不超时"""
    print(f"      🧠 [Tool] AI 正在分析搜索结果...")
    
    class ProductVerification(BaseModel):
        product_name: str = Field(description="产品名称")
        is_released: bool = Field(description="是否已正式发布")
        is_recent: bool = Field(description="是否为近期发布")
        release_date: str = Field(description="发布日期")
        description: str = Field(description="功能描述")

    try:
        verifier = llm.with_structured_output(ProductVerification)
        prompt = ChatPromptTemplate.from_template("""
        请根据以下搜索摘要，判断这是否为**近期发布的新 AI 产品**。
        不需要联网，仅根据文本判断。
        
        摘要内容：
        {text}
        """)
        # 截取前 5000 字防止 Token 溢出
        res = (prompt | verifier).invoke({"text": content_snippet[:5000]})
        data = res.model_dump()
        
        status = "🟢通过" if (data['is_released'] and data['is_recent']) else "🔴拒绝"
        print(f"         {status} | {data['product_name']}")
        return data
    except Exception as e:
        print(f"      ⚠️ 跳过: {e}")
        return {"is_released": False, "description": "Error"}

@tool
def fetch_hf_trending_models() -> List[str]:
    print("   🤗 [Tool] 获取 HF 榜单 (API)...")
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
    print("   🐙 [Tool] 获取 GitHub 榜单 (API)...")
    # GitHub API 不需要代理，直连即可
    try:
        import requests
        date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{date_str}&sort=stars&order=desc&per_page=5"
        resp = requests.get(url, headers={"User-Agent": "NewsAgent"}, timeout=10)
        items = resp.json().get("items", [])
        return [f"Repo: {i['full_name']} | Stars: {i['stargazers_count']} | Desc: {i['description']} | URL: {i['html_url']}" for i in items]
    except: return []

@tool
def fetch_big_tech_papers() -> List[str]:
    print("   📜 [Tool] 获取论文 (Tavily)...")
    try:
        # Tavily 搜论文非常稳，不需要改
        res = tavily_client.search('site:huggingface.co/papers ("OpenAI" OR "DeepSeek" OR "Google")', max_results=5)
        return [f"Paper: {r['title']} | URL: {r['url']}" for r in res.get('results', [])]
    except: return []

ALL_TOOLS = [search_new_products, verify_product_page, fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers]