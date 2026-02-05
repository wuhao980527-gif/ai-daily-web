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
    timeout=120,  # 120秒超时，给LLM足够时间处理
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
        请阅读网页，判断这是否为 **AI 领域具有行业影响力的重大事件**。

        ✅ **只接受**以下高质量内容：
        1. 大型科技公司的重大产品发布（OpenAI、Google、Microsoft、Meta、Anthropic、DeepSeek、Qwen等）
        2. 突破性技术/模型发布（如新一代大模型、重大技术突破）
        3. 重大功能更新（对行业有显著影响的新功能）
        4. 重大商业事件（大额融资$10M+、重要收购、战略合作）

        ❌ **拒绝**以下内容：
        1. 个人开发者的小众应用（App Store上的小工具）
        2. 本地LLM客户端/服务器等通用工具
        3. 教程、测评、对比、预测类文章
        4. 超过7天的旧新闻
        5. 传闻或未经官方确认的消息

        ⚠️ **严格标准**：
        - is_released: 只有真正重大的、已确认的事件才设为 True
        - is_recent: 必须是近7天内的事件
        - 如果是小众应用或工具，即使最近发布也要设 is_released=False

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
    【板块3】GitHub 近 7 天新建或重大更新的 AI 项目 Top 5。
    策略：严格筛选7天内创建的新项目，或7天内有Release的重大更新项目
    """
    print("   🐙 [Tool] 正在拉取 GitHub 趋势（7天内新建/重大更新）...")
    try:
        date_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        headers = {"Accept": "application/vnd.github.v3+json"}
        results = []
        count = 0

        # ========== 策略1：7天内创建的新项目 ==========
        print(f"      🔍 搜索7天内创建的新AI项目...")
        url_new = f"https://api.github.com/search/repositories?q=ai+machine-learning+llm+created:>{date_str}+stars:>5&sort=stars&order=desc&per_page=10"

        resp_new = requests.get(url_new, headers=headers, timeout=10)
        items_new = resp_new.json().get("items", [])

        for item in items_new:
            if count >= 5:
                break

            stars = item['stargazers_count']
            full_name = item['full_name']
            repo_url = item['html_url']
            default_branch = item.get('default_branch', 'main')
            language = item.get('language') or "Unknown"
            created_at = item.get('created_at', '')[:10]
            description = item.get('description') or "暂无描述"

            print(f"      📥 [GitHub-新建] ({language}) {full_name} (⭐{stars}, 创建:{created_at})...")

            readme_text = "暂无详细介绍"
            try:
                raw_url = f"https://raw.githubusercontent.com/{full_name}/{default_branch}/README.md"
                r = requests.get(raw_url, timeout=5)
                if r.status_code == 200:
                    readme_text = r.text[:3000]
                else:
                    raw_url_m = f"https://raw.githubusercontent.com/{full_name}/master/README.md"
                    r2 = requests.get(raw_url_m, timeout=5)
                    if r2.status_code == 200:
                        readme_text = r2.text[:3000]
            except Exception:
                pass

            info = (
                f"=== Repo: {full_name} ===\n"
                f"URL: {repo_url}\n"
                f"Date: {created_at}\n"
                f"Language: {language}\n"
                f"Stars: {stars} | Desc: {description}\n"
                f"--- README snippet ---\n"
                f"{readme_text}\n"
                f"======================\n"
            )
            results.append(info)
            count += 1

        print(f"      ✅ 找到 {count} 个7天内新建的项目")

        # ========== 策略2：如果不足5个，补充"宁缺毋滥"原则，返回现有结果 ==========
        # 不再搜索老项目，严格遵守7天窗口
        if count < 5:
            print(f"      ℹ️  7天内新建的AI项目不足5个，遵循'宁缺毋滥'原则")

        print(f"      ✅ GitHub 抓取成功: {count} 个（7天内新建项目）")
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
    date_str = seven_days_ago.strftime('%Y-%m-%d')

    try:
        # =================================================================
        # 🎯 新策略：搜索最近7天的AI领域所有重要论文，然后严格筛选机构
        # =================================================================
        # 扩大搜索范围，提高召回率
        ai_keywords = '"LLM" OR "large language model" OR "multimodal" OR "AI" OR "machine learning"'

        # 渠道 1: HuggingFace Papers（最新trending）
        hf_query = f'site:huggingface.co/papers {ai_keywords} after:{date_str}'
        try:
            res_hf = tavily_client.search(
                query=hf_query,
                max_results=15,
                search_depth="advanced",
                include_domains=["huggingface.co"]
            )
            results.extend(res_hf.get('results', []))
        except Exception as e:
            print(f"      ⚠️ HF 搜索微恙: {e}")

        # 渠道 2: ArXiv（最新发布）
        arxiv_query = f'site:arxiv.org {ai_keywords} ("2602" OR "2601") "Technical Report"'
        try:
            res_arxiv = tavily_client.search(
                query=arxiv_query,
                max_results=15,
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

        # 映射表：把 url/title 里的词映射回标准机构名（扩充版）
        tech_map = {
            # 国际顶级实验室
            "openai": "OpenAI",
            "google": "Google",
            "deepmind": "Google DeepMind",
            "meta": "Meta",
            "facebook": "Meta",
            "anthropic": "Anthropic",
            "microsoft": "Microsoft",
            # 国内顶级实验室
            "qwen": "Qwen",
            "通义": "Qwen",
            "alibaba": "Alibaba",
            "阿里": "Alibaba",
            "deepseek": "DeepSeek",
            "tencent": "Tencent",
            "腾讯": "Tencent",
            "hunyuan": "Tencent",
            "混元": "Tencent",
            "baidu": "Baidu",
            "百度": "Baidu",
            "ernie": "Baidu",
            "文心": "Baidu",
            "bytedance": "ByteDance",
            "字节": "ByteDance",
            "doubao": "ByteDance",
            "豆包": "ByteDance",
            "01.ai": "01.AI",
            "yi": "01.AI",
            "zhipu": "Zhipu AI",
            "智谱": "Zhipu AI",
            "glm": "Zhipu AI",
            "sensetime": "SenseTime",
            "商汤": "SenseTime",
            "megvii": "Megvii",
            "旷视": "Megvii",
            "iflytek": "iFlytek",
            "讯飞": "iFlytek",
            "huawei": "Huawei",
            "华为": "Huawei"
        }

        for r in results:
            url = r['url']
            title = r['title']
            content = r.get('content', '')
            title_lower = title.lower()

            # --- 1. 去重 ---
            if url in seen_urls: continue
            seen_urls.add(url)

            # --- 2. 严格URL过滤：只接受真正的论文页面 ---
            # 只接受 arxiv.org/abs/XXXX.XXXXX 或 huggingface.co/papers/XXXX.XXXXX
            is_valid_paper_url = False
            if "arxiv.org/abs/" in url and re.search(r'arxiv\.org/abs/\d{4}\.\d+', url):
                is_valid_paper_url = True
            elif "huggingface.co/papers/" in url and re.search(r'huggingface\.co/papers/\d{4}\.\d+', url):
                is_valid_paper_url = True

            if not is_valid_paper_url:
                print(f"         - [跳过] 非论文URL: {url[:60]}...")
                continue

            # --- 3. 垃圾词过滤 (防止 SEO 污染) ---
            bad_words = ["rumor", "prediction", "when is", "release date", "price", "stock", "leak", "tutorial", "guide"]
            if any(w in title_lower for w in bad_words):
                continue

            # --- 3. 严格日期验证 (只接受7天内的论文) ---
            is_new = False
            display_date = "Unknown"

            # [方法 1] API 返回的日期（最可靠）
            if r.get('published_date'):
                try:
                    pdate = parser.parse(r['published_date']).replace(tzinfo=None)
                    if pdate >= seven_days_ago:
                        is_new = True
                        display_date = pdate.strftime("%Y-%m-%d")
                except: pass

            # [方法 2] 从 Arxiv URL 提取日期验证
            # URL 类似 https://arxiv.org/abs/2602.12345 (2602 代表 2026年02月)
            if not is_new:
                arxiv_match = re.search(r'/(2[4-9]\d{2})\.', url)
                if arxiv_match:
                    date_code = int(arxiv_match.group(1))
                    now = datetime.now()
                    current_code = int(now.strftime("%y%m"))

                    # 只接受当月和上月的论文（严格7天窗口）
                    prev_month_code = current_code - 1 if current_code % 100 > 1 else current_code - 89
                    if date_code == current_code or date_code == prev_month_code:
                        is_new = True
                        display_date = f"20{str(date_code)[:2]}-{str(date_code)[2:]}"

            # 如果日期无法验证或不在7天内，直接丢弃
            if not is_new:
                print(f"         - [跳过] 非7天内或日期不明: {title[:40]}...")
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
                url_lower = url.lower()
                for k, v in tech_map.items():
                    # 扩大搜索范围：title + content + url
                    if k in title_lower or k in content.lower() or k in url_lower:
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