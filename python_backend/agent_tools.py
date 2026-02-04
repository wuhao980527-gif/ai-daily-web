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

# 初始化
llm = ChatOpenAI(
    openai_api_key=os.getenv("MY_API_KEY"),
    base_url=os.getenv("MY_BASE_URL"),
    model_name=os.getenv("MY_MODEL_NAME"),
    temperature=0,
    timeout=30,  # 30秒超时，防止卡死
    max_retries=2  # 最多重试2次
)
tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ================= 1. 结构化校验 =================
class ProductVerification(BaseModel):
    """用于校验搜索到的新品是否真实、是否近期发布"""
    product_name: str = Field(description="产品名称")
    is_released: bool = Field(description="是否已正式发布/上线 (非传闻)")
    is_recent: bool = Field(description="是否为近期(近1个月)发布")
    release_date: str = Field(description="具体的发布日期或时间证据")
    description: str = Field(description="一句话客观描述产品功能(不带形容词)")

# ================= 2. 工具集 (完整增强版) =================

@tool
def search_new_products(query: str) -> List[Dict]:
    """【板块1-初筛】搜索全网 AI 新品发布信息"""
    print(f"   🕵️ [Tool] 正在搜索新品: {query}")
    try:
        q = f"{query} -tutorial -review -list -best"
        results = tavily_client.search(q, max_results=5).get('results', [])
        
        print(f"      ✅ 初筛命中 {len(results)} 条")
        return results
    except Exception as e:
        print(f"      ❌ 搜索报错: {e}")
        return []

@tool
def verify_product_page(url: str) -> dict:
    """【板块1-精筛】深度阅读网页，核实新品发布的真实性"""
    print(f"      📖 [Tool] 正在核实网页: {url[:40]}...")
    try:
        loader = WebBaseLoader(url)
        loader.requests_kwargs = {'timeout': 10}
        docs = loader.load()
        content = docs[0].page_content[:4000]
        
        verifier = llm.with_structured_output(ProductVerification)
        prompt = ChatPromptTemplate.from_template("""
        请阅读网页，客观核实这是否为一个**新发布的 AI 产品**。
        标准：
        1. 真实性：必须是官方宣布或权威媒体报道。
        2. 时效性：必须是近期（近1个月）发生的动作。
        3. 客观描述：只陈述功能，不要包含营销词汇。
        
        网页内容：{text}
        """)
        
        res = (prompt | verifier).invoke({"text": content})
        data = res.model_dump()
        
        status = "🟢通过" if (data['is_released'] and data['is_recent']) else "🔴拒绝"
        print(f"         {status} | {data['product_name']}")
        
        return data
    except Exception as e:
        print(f"      ❌ 核查报错: {e}")
        return {"is_released": False, "description": "Error"}

@tool
def fetch_hf_trending_models() -> List[str]:
    """
    【板块2】Hugging Face 近 7 天最热模型 Top 5（按7日点赞飙升排序）。
    策略：使用 likes7d 排序（代表7天内点赞增长最快）
    """
    print("   🤗 [Tool] 正在拉取 HF 热门模型（7天内点赞飙升榜）...")
    try:
        api = HfApi()
        # 按7日点赞数排序（这就是飙升榜）
        models = api.list_models(sort="likes7d", direction=-1, limit=50)

        results = []
        limit_date = datetime.now().astimezone() - timedelta(days=7)

        count = 0
        for m in models:
            # 筛选：7天内创建或更新的模型
            if m.created_at and m.created_at >= limit_date:
                model_id = m.modelId
                likes = m.likes
                date_str = m.created_at.strftime('%Y-%m-%d')
                model_url = f"https://huggingface.co/{model_id}"

                print(f"      📥 [HF] ({date_str}) {model_id} (⭐{likes} 7d增长)...")

                readme_content = "暂无详细介绍"
                try:
                    readme_url = f"https://huggingface.co/{model_id}/resolve/main/README.md"
                    resp = requests.get(readme_url, timeout=10)
                    if resp.status_code == 200:
                        readme_content = resp.text[:3000]
                except Exception:
                    pass

                info = (
                    f"=== Model: {model_id} ===\n"
                    f"URL: {model_url}\n"
                    f"Date: {date_str}\n"
                    f"Likes: {likes} | Tags: {m.tags}\n"
                    f"--- README Summary ---\n"
                    f"{readme_content}\n"
                    f"======================\n"
                )
                results.append(info)

                count += 1
                if count >= 5: break

        # 如果7天内新创建的模型不足5个，补充7天内点赞最高的
        if count < 5:
            print(f"      ⚠️ 7天内新模型不足，补充点赞最高的模型...")
            for m in models:
                if count >= 5:
                    break

                # 跳过已经添加的
                model_id = m.modelId
                if any(model_id in r for r in results):
                    continue

                likes = m.likes
                date_str = m.created_at.strftime('%Y-%m-%d') if m.created_at else "Unknown"
                model_url = f"https://huggingface.co/{model_id}"

                print(f"      📥 [HF] ({date_str}) {model_id} (⭐{likes})...")

                readme_content = "暂无详细介绍"
                try:
                    readme_url = f"https://huggingface.co/{model_id}/resolve/main/README.md"
                    resp = requests.get(readme_url, timeout=10)
                    if resp.status_code == 200:
                        readme_content = resp.text[:3000]
                except Exception:
                    pass

                info = (
                    f"=== Model: {model_id} ===\n"
                    f"URL: {model_url}\n"
                    f"Date: {date_str}\n"
                    f"Likes: {likes} | Tags: {m.tags}\n"
                    f"--- README Summary ---\n"
                    f"{readme_content}\n"
                    f"======================\n"
                )
                results.append(info)
                count += 1

        print(f"      ✅ HF 抓取成功: {count} 个（7天飙升榜）")
        return results
    except Exception as e:
        print(f"   ❌ HF API 错误: {e}")
        return []

@tool
def fetch_github_trending() -> List[str]:
    """
    【板块3】GitHub 近 7 天 AI 项目飙升榜 Top 5。
    策略：7天内新创建的AI项目，按Stars降序（新项目高stars=飙升快）
    """
    print("   🐙 [Tool] 正在拉取 GitHub 趋势（7天内新项目，Stars倒序）...")
    try:
        date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        # AI相关话题（覆盖广泛）
        ai_topics = "ai OR machine-learning OR deep-learning OR llm OR gpt OR agent OR transformer OR diffusion OR rag"
        url = f"https://api.github.com/search/repositories?q=({ai_topics})+created:>{date_str}&sort=stars&order=desc&per_page=20"
        headers = {"Accept": "application/vnd.github.v3+json"}

        resp = requests.get(url, headers=headers, timeout=10)
        items = resp.json().get("items", [])

        results = []
        count = 0
        for item in items:
            # 筛选：至少5个Stars（避免完全无人关注的项目）
            stars = item['stargazers_count']
            if stars < 5:
                continue

            full_name = item['full_name']
            repo_url = item['html_url']
            default_branch = item.get('default_branch', 'main')
            language = item.get('language') or "Unknown"
            created_at = item.get('created_at', '')[:10]

            print(f"      📥 [GitHub] ({language}) {full_name} (⭐{stars} 7天飙升)...")

            readme_text = "暂无详细介绍"
            try:
                raw_url = f"https://raw.githubusercontent.com/{full_name}/{default_branch}/README.md"
                r = requests.get(raw_url, timeout=5)
                if r.status_code == 200:
                    readme_text = r.text[:3000]
                else:
                    raw_url_m = f"https://raw.githubusercontent.com/{full_name}/master/README.md"
                    r2 = requests.get(raw_url_m, timeout=5)
                    if r2.status_code == 200: readme_text = r2.text[:3000]
            except Exception:
                pass

            info = (
                f"=== Repo: {full_name} ===\n"
                f"URL: {repo_url}\n"
                f"Date: {created_at}\n"
                f"Language: {language}\n"
                f"Stars: {stars} | Desc: {item['description']}\n"
                f"--- README snippet ---\n"
                f"{readme_text}\n"
                f"======================\n"
            )
            results.append(info)

            count += 1
            if count >= 5: break

        print(f"      ✅ GitHub 抓取成功: {count} 个（7天飙升榜）")
        return results
    except Exception as e:
        print(f"   ❌ GitHub API 错误: {e}")
        return []

@tool
def fetch_big_tech_papers() -> List[str]:
    """
    【板块4】国内外顶级实验室论文（7天内）
    策略：
    1. 源头去噪：只搜 Hugging Face Papers 和 ArXiv
    2. 时间范围：7天内发布的论文
    3. 机构筛选：国际顶级实验室（OpenAI/Google/Meta/Anthropic等）+ 国内顶级实验室（DeepSeek/Qwen/百度/字节等）
    4. 官方识别：使用正则匹配，精准识别官方报告
    """
    print("   📜 [Tool] 论文搜索（7天内，国内外顶级实验室）...")
    
    results = []
    seen_urls = set()
    papers = []
    
    # 核心关注名单（国内外顶级AI实验室）
    target_orgs = [
        # 国际顶级实验室
        "OpenAI", "Google", "DeepMind", "Meta", "Anthropic", "Microsoft",
        # 国内顶级实验室
        "DeepSeek", "Qwen", "Alibaba", "Tencent", "Baidu", "ByteDance",
        "01.AI", "Zhipu", "智谱", "ERNIE", "文心", "通义",
        "SenseTime", "商汤", "Megvii", "旷视"
    ]

    # 时间窗口：7天
    seven_days_ago = datetime.now() - timedelta(days=7)

    try:
        # =================================================================
        # 🎯 渠道 1: Hugging Face Papers (核心源，去噪能力最强)
        # =================================================================
        org_query = " OR ".join([f'"{org}"' for org in target_orgs])
        hf_query = f'site:huggingface.co/papers ({org_query})'
        
        try:
            res_hf = tavily_client.search(
                query=hf_query, 
                max_results=8, 
                search_depth="advanced",
                include_domains=["huggingface.co"]
            )
            results.extend(res_hf.get('results', []))
        except Exception as e:
            print(f"      ⚠️ HF 搜索微恙: {e}")

        # =================================================================
        # 🎯 渠道 2: ArXiv (源头补漏，防止 HF 收录延迟)
        # =================================================================
        arxiv_query = f'site:arxiv.org ({org_query}) AND ("Technical Report" OR "Paper")'
        try:
            res_arxiv = tavily_client.search(
                query=arxiv_query, 
                max_results=6, 
                search_depth="advanced",
                include_domains=["arxiv.org"]
            )
            results.extend(res_arxiv.get('results', []))
        except Exception as e:
            print(f"      ⚠️ Arxiv 搜索微恙: {e}")

        # =================================================================
        # 🧼 清洗逻辑 (严格去伪 + 智能官方识别)
        # =================================================================
        print(f"      ✅ 聚合命中 {len(results)} 条，开始严格核验...")

        # 映射表：把 url/title 里的词映射回标准机构名
        tech_map = {
            "openai": "OpenAI", "google": "Google", "deepmind": "Google DeepMind", 
            "meta": "Meta", "anthropic": "Anthropic", "microsoft": "Microsoft", 
            "qwen": "Qwen", "alibaba": "Alibaba", "deepseek": "DeepSeek", 
            "tencent": "Tencent", "yi": "01.AI"
        }

        for r in results:
            url = r['url']
            title = r['title']
            content = r.get('content', '')
            title_lower = title.lower()
            
            # --- 1. 去重 ---
            if url in seen_urls: continue
            seen_urls.add(url)

            # --- 2. 垃圾词过滤 (防止 SEO 污染) ---
            # 如果标题包含这些词，说明是营销号预测，直接杀掉
            bad_words = ["rumor", "prediction", "when is", "release date", "price", "stock", "leak"]
            if any(w in title_lower for w in bad_words):
                continue

            # --- 3. 日期“验尸” (The Grim Reaper Logic) ---
            is_new = False
            display_date = "Recent"

            # [逻辑 A] Arxiv ID 检查 (最硬核的校验)
            # URL 类似 https://arxiv.org/abs/2501.12345 (2501 代表 2025年01月)
            arxiv_match = re.search(r'/(2[4-9]\d{2})\.', url) 
            if arxiv_match:
                date_code = int(arxiv_match.group(1)) # 例如 2501
                # 计算当前年月 code (例如 2501)
                now = datetime.now()
                current_code = int(now.strftime("%y%m"))
                
                # 跨年处理逻辑：如果当前是 2501，上一月是 2412，差值是 89 (2501-2412)，所以不能简单相减
                # 简单判定：只允许当前月(2501) 或 上一个月(2412)
                # (这里简化处理，假设你只关心最近的)
                if date_code == current_code or \
                   (date_code == current_code - 1) or \
                   (current_code % 100 == 1 and date_code == current_code - 89): # 处理 2501 vs 2412
                    is_new = True
                    display_date = f"20{str(date_code)[:2]}-{str(date_code)[2:]} (Arxiv)"
            
            # [逻辑 B] API 日期检查
            elif r.get('published_date'):
                try:
                    pdate = parser.parse(r['published_date']).replace(tzinfo=None)
                    if pdate >= seven_days_ago:
                        is_new = True
                        display_date = pdate.strftime("%Y-%m-%d")
                except: pass
            
            # [逻辑 C] Hugging Face 兜底
            # HF Papers 页面上的通常都是新的，如果没有日期，暂时信任
            elif "huggingface.co/papers" in url:
                is_new = True
                display_date = "Recent (HF)"

            # ❌ 如果不是新的，直接丢弃
            if not is_new:
                continue

            # --- 4. 归属机构与“官方性”判定 (核心升级) ---
            org_label = "Big Tech"
            
            # === DeepSeek 特判逻辑 (正则版) ===
            if "deepseek" in title_lower:
                # (1) 排除法：如果是第三方评测，直接标记为社区内容或丢弃
                third_party_keywords = [
                    "survey", "evaluation", "benchmark", "analysis", "review", 
                    "vs.", "comparison", "finetuning", "implementation",
                    "understanding", "jailbreaking", "reproduction"
                ]
                if any(w in title_lower for w in third_party_keywords):
                    org_label = "Community (DeepSeek Related)"
                else:
                    # (2) 正则匹配法：只要符合 DeepSeek-XXX 格式，或者包含 "technical report"
                    # 匹配 deepseek-v3, deepseek-r1, deepseek-moe, deepseek-coder-v2 等
                    version_pattern = r"deepseek-[a-z0-9]+" 
                    
                    if "technical report" in title_lower or re.search(version_pattern, title_lower):
                        org_label = "DeepSeek (Official)"
                    else:
                        # 既不是第三方评测，又有 DeepSeek 名字，倾向于是官方
                        org_label = "DeepSeek (Official)"

            # === 其他大厂通用逻辑 ===
            else:
                for k, v in tech_map.items():
                    if k in title_lower or k in content.lower():
                        org_label = v
                        # 简单的第三方过滤
                        if any(w in title_lower for w in ["evaluation", "survey", "benchmark", "analysis"]):
                            org_label = f"{v} Related (Community)"
                        break

            # 5. 生成结果
            print(f"         - [收录] [{org_label}] {title[:30]}... ({display_date})")

            info = (
                f"=== Paper: {title} ===\n"
                f"Organization: {org_label}\n"
                f"Date: {display_date}\n"
                f"URL: {url}\n"
                f"Abstract: {content[:300]}...\n"
                f"======================\n"
            )
            papers.append(info)
            
            if len(papers) >= 5: break

        return papers

    except Exception as e:
        print(f"   ❌ 搜索错误: {e}")
        return []

# 导出
ALL_TOOLS = [search_new_products, verify_product_page, fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers]