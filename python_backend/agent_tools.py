import os
import requests
from typing import List, Dict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil import parser
import re

# LangChain 组件
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import WebBaseLoader
from pydantic import BaseModel, Field

# 第三方客户端
from tavily import TavilyClient
from huggingface_hub import HfApi

load_dotenv()

# ================= 初始化 =================
# 这里的配置会直接读取同目录下的 .env 文件
llm = ChatOpenAI(
    openai_api_key=os.getenv("MY_API_KEY"),
    base_url=os.getenv("MY_BASE_URL"),
    model_name=os.getenv("MY_MODEL_NAME"),
    temperature=0
)
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ================= 结构化校验 =================
class ProductVerification(BaseModel):
    product_name: str = Field(description="产品名称")
    is_released: bool = Field(description="是否已正式发布")
    is_recent: bool = Field(description="是否为近期(近1个月)发布")
    release_date: str = Field(description="具体发布日期")
    description: str = Field(description="客观描述")

# ================= 工具集 =================

@tool
def search_new_products(query: str) -> List[Dict]:
    """【板块1】搜索全网 AI 新品"""
    print(f"   🕵️ [Tool] 正在搜索: {query}")
    try:
        q = f"{query} -tutorial -review -list -best"
        return tavily_client.search(q, max_results=5).get('results', [])
    except Exception as e:
        print(f"      ❌ 搜索报错: {e}")
        return []

@tool
def verify_product_page(url: str) -> dict:
    """【板块1】核实新品真实性"""
    print(f"      📖 [Tool] 正在核实: {url[:40]}...")
    try:
        loader = WebBaseLoader(url)
        # 设置超时防止卡死
        loader.requests_kwargs = {'timeout': 10}
        docs = loader.load()
        content = docs[0].page_content[:4000]
        
        verifier = llm.with_structured_output(ProductVerification)
        prompt = ChatPromptTemplate.from_template("""
        请阅读网页，核实是否为**新发布的 AI 产品**。
        1. 真实性：官方宣布或权威媒体。
        2. 时效性：近期（近1个月）。
        3. 客观描述：不要营销词。
        网页内容：{text}
        """)
        res = (prompt | verifier).invoke({"text": content})
        return res.model_dump()
    except:
        return {"is_released": False}

@tool
def fetch_hf_trending_models() -> List[str]:
    """【板块2】Hugging Face 热榜"""
    print("   🤗 [Tool] 拉取 HF 热门模型...")
    try:
        api = HfApi()
        models = api.list_models(sort="likes7d", direction=-1, limit=10)
        results = []
        limit_date = datetime.now().astimezone() - timedelta(days=7)
        
        for m in models:
            if m.created_at and m.created_at >= limit_date:
                info = f"Model: {m.modelId} | Likes: {m.likes} | Date: {m.created_at.strftime('%Y-%m-%d')} | URL: https://huggingface.co/{m.modelId}"
                results.append(info)
                if len(results) >= 5: break
        return results
    except Exception as e:
        print(f"   ❌ HF 错误: {e}")
        return []

@tool
def fetch_github_trending() -> List[str]:
    """【板块3】GitHub 趋势"""
    print("   🐙 [Tool] 拉取 GitHub 趋势...")
    try:
        date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{date_str}&sort=stars&order=desc&per_page=5"
        resp = requests.get(url, timeout=10)
        items = resp.json().get("items", [])
        return [f"Repo: {i['full_name']} | Stars: {i['stargazers_count']} | Desc: {i['description']} | URL: {i['html_url']}" for i in items]
    except Exception as e:
        print(f"   ❌ GitHub 错误: {e}")
        return []

@tool
def fetch_big_tech_papers() -> List[str]:
    """【板块4】大厂论文 (简化版)"""
    print("   📜 [Tool] 搜索大厂论文...")
    try:
        # 这里为了简化，直接用 Tavily 搜 HF Papers
        query = 'site:huggingface.co/papers ("OpenAI" OR "Google" OR "DeepSeek" OR "Meta")'
        res = tavily_client.search(query, max_results=5)
        return [f"Paper: {r['title']} | URL: {r['url']}" for r in res.get('results', [])]
    except:
        return []