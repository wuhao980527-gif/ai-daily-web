import os
import json
import time
import requests
from typing import List, Dict
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from dateutil import parser
import re

# LangChain 组件
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

# 第三方客户端
from tavily import TavilyClient

load_dotenv()

# ============================================================
# 🔧 网络配置 
# ============================================================
if not os.getenv("MY_BASE_URL") or not os.getenv("MY_API_KEY"):
    raise ValueError(
        "请配置 MY_BASE_URL 和 MY_API_KEY。本地用 .env，GitHub Actions 用 Repo Secrets。"
    )
if not os.getenv("LOCAL_VPN"):
    print("🌍 [Network] 云端模式：清除代理，全权交给 Tavily")
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)

# 初始化 LLM（120s 超时 + 重试，避免单次卡死）
llm = ChatOpenAI(
    openai_api_key=os.getenv("MY_API_KEY"),
    base_url=os.getenv("MY_BASE_URL"),
    model_name=os.getenv("MY_MODEL_NAME"),
    temperature=0.5,
    request_timeout=120,
    max_retries=2,
)

tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ================= 结构化校验 =================
class ProductVerification(BaseModel):
    product_name: str = Field(description="产品名称")
    is_released: bool = Field(description="是否已正式发布")
    is_recent: bool = Field(description="是否为近期(近1个月)发布")
    release_date: str = Field(description="具体的发布日期")
    description: str = Field(description="客观描述")

# ================= 工具集 (Tavily 纯享版) =================

@tool
def search_new_products(query: str) -> List[Dict]:
    """
    【板块1-搜索】直接让 Tavily 返回内容，不做二次爬取。
    """
    print(f"   🕵️ [Tool] Tavily 深度搜索: {query}")
    try:
        q = f"{query} -tutorial -review -list -best"
        # ⚡️ 关键修改：include_raw_content=True 让 Tavily 帮我们抓内容
        # search_depth="advanced" 保证质量
        response = tavily_client.search(
            q, 
            max_results=6, 
            search_depth="advanced", 
            include_raw_content=False, # raw太长容易超token，用 answer 或 content 足够
            include_answer=True 
        )
        
        results = response.get('results', [])
        print(f"      ✅ Tavily 返回 {len(results)} 条结果")
        
        # 为了兼容后续逻辑，我们把 content 塞进去
        return results
    except Exception as e:
        print(f"      ❌ 搜索报错: {e}")
        return []

@tool
def verify_product_page(item_str: str) -> dict:
    """
    【板块1-核实】利用 Tavily 已经抓回来的 content 进行核实，
    不再发起网络请求，彻底解决被墙和超时问题。
    注意：这里传入的参数改为字符串（包含 url 和 content）
    """
    # 这里的 item_str 其实是我们在 Graph 里传进来的，为了工具调用方便，我们做一个适配
    # 实际 Agent 调用时，它会根据 prompt 传入内容。
    # 我们简化逻辑：直接让 LLM 读传入的文本（不再上网）
    
    print(f"      🧠 [Tool] AI 离线核实信息...")
    
    try:
        verifier = llm.with_structured_output(ProductVerification)
        prompt = ChatPromptTemplate.from_template("""
        请根据以下搜索结果摘要，核实这是否为一个**新发布的 AI 产品**。
        不要联网，直接判断文本。
        
        标准：
        1. 真实性：官方宣布或权威媒体。
        2. 时效性：近期（近1个月）。
        
        搜索摘要内容：{text}
        """)
        content = item_str[:4000]
        chain = prompt | verifier
        for attempt in range(3):
            try:
                res = chain.invoke({"text": content})
                data = res.model_dump()
                status = "🟢通过" if (data['is_released'] and data['is_recent']) else "🔴拒绝"
                print(f"         {status} | {data['product_name']}")
                return data
            except Exception as e:
                if attempt < 2:
                    print(f"      ⏳ 核查超时，5s 后重试 ({attempt + 2}/3)...")
                    time.sleep(5)
                else:
                    raise
    except Exception as e:
        print(f"      ⚠️ 核查跳过: {e}")
        return {"is_released": False, "description": "Verification Skipped"}

@tool
def fetch_hf_trending_models() -> List[str]:
    """拉取 HuggingFace 近 7 天新增、按点赞量降序的 Top 5 模型。"""
    print("   🤗 [Tool] 拉取 HF 近 7 天新增模型 (点赞量降序 Top5)...")
    url = "https://huggingface.co/api/models?sort=likes7d&limit=80"
    limit_date = (datetime.now(timezone.utc) - timedelta(days=7)).replace(tzinfo=None)
    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": "NewsAgent/1.0"}, timeout=15)
            resp.raise_for_status()
            models = resp.json()
            # 1. 筛出近 7 天新增的
            recent = []
            for m in models:
                created = m.get("createdAt")
                if not created:
                    continue
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
                    if dt >= limit_date:
                        recent.append(m)
                except (ValueError, TypeError):
                    pass
            # 2. 按点赞量降序
            recent.sort(key=lambda m: m.get("likes", 0), reverse=True)
            # 3. 取 Top 5
            return [
                f"Model: {m.get('modelId', m.get('id', ''))} | Date: {m.get('createdAt', '')[:10]} | Likes: {m.get('likes', 0)} | URL: https://huggingface.co/{m.get('modelId', m.get('id', ''))}"
                for m in recent[:5]
            ]
        except Exception as e:
            print(f"      ⚠️ HuggingFace API 第{attempt+1}次失败: {e}")
            if attempt < 2:
                time.sleep(2)
    return []

@tool
def fetch_github_trending() -> List[str]:
    """拉取 GitHub 近 7 天 AI 相关热门仓库列表。"""
    print("   🐙 [Tool] 拉取 GitHub 趋势...")
    url = f"https://api.github.com/search/repositories?q=topic:ai+created:>{(datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')}&sort=stars&order=desc&per_page=5"
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "NewsAgent/1.0"}
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return [f"Repo: {i['full_name']} | Date: {i.get('created_at','')[:10]} | Stars: {i['stargazers_count']} | Desc: {i.get('description','')} | URL: {i['html_url']}" for i in items]
        except Exception as e:
            print(f"      ⚠️ GitHub API 第{attempt+1}次失败: {e}")
            if attempt < 2:
                time.sleep(2)
    return []

@tool
def fetch_big_tech_papers() -> List[str]:
    """通过 Tavily 搜索大厂 AI 论文。"""
    print("   📜 [Tool] 论文搜索...")
    try:
        query = 'site:huggingface.co/papers ("OpenAI" OR "Google" OR "DeepSeek" OR "Meta")'
        # Tavily 搜索论文非常稳
        res = tavily_client.search(query, max_results=5)
        return [f"Paper: {r['title']} | URL: {r['url']}" for r in res.get('results', [])]
    except:
        return []

ALL_TOOLS = [search_new_products, verify_product_page, fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers]