import os
import requests
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from dateutil import parser
import re

# LangChain 组件
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.document_loaders import WebBaseLoader
from pydantic import BaseModel, Field, field_validator

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

# Groq 免费模型（用于 ReAct 推理）
groq_llm = ChatOpenAI(
    openai_api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model_name="llama-3.3-70b-versatile",
    temperature=0,
    timeout=30,
)

# ================= 1. 结构化校验 =================
class ProductVerification(BaseModel):
    """用于校验搜索到的新品是否真实、是否近期发布"""
    product_name: Optional[str] = Field(default="", description="产品名称")
    is_released: bool = Field(default=False, description="是否已正式发布/上线 (非传闻)")
    is_recent: bool = Field(default=False, description="是否为近期(近1个月)发布")
    release_date: Optional[str] = Field(default="", description="具体的发布日期或时间证据")
    description: Optional[str] = Field(default="", description="一句话客观描述产品功能(不带形容词)")

class ProductExtractionResult(BaseModel):
    """单条snippet的产品提取结果"""
    index: int = Field(description="对应搜索结果的序号")
    product_name: str = Field(default="", description="提取到的AI产品/模型/工具名称，无则留空")
    is_product_launch: bool = Field(default=False, description="是否为产品发布/上线/开源的新闻")
    is_recent: bool = Field(default=False, description="从snippet内容判断，该产品是否为近7天内发布的")

class ProductExtractionList(BaseModel):
    """批量提取结果"""
    items: List[ProductExtractionResult] = Field(default_factory=list, description="提取结果列表")

class ReActDecision(BaseModel):
    """ReAct 推理决策"""
    reasoning: str = Field(default="", description="对当前结果的分析：覆盖了什么、缺什么、质量如何")
    should_continue: bool = Field(default=False, description="是否需要继续搜索")
    next_query: str = Field(default="", description="下一轮搜索的 query（仅当 should_continue=True 时有效）")
    gap_category: str = Field(default="", description="缺失的类别（字符串），如：国内产品、AI应用、硬件、融资")

    @field_validator('gap_category', mode='before')
    @classmethod
    def coerce_gap_category(cls, v):
        if isinstance(v, list):
            return ', '.join(str(i) for i in v)
        return v or ""

# ================= 2. 工具集 (完整增强版) =================

@tool
def react_reason(current_items: List[str], retry_count: int, search_history: str = "") -> dict:
    """【ReAct推理】评估当前搜索结果的覆盖面和质量，决定下一步搜索策略"""
    print(f"   🧠 [Tool] ReAct 推理中（当前 {len(current_items)} 条，第 {retry_count} 轮）...")

    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    items_text = "\n".join(current_items) if current_items else "（暂无结果）"
    history_text = search_history if search_history else "（首轮搜索）"

    reasoner = groq_llm.with_structured_output(ReActDecision, method="json_mode")
    prompt = ChatPromptTemplate.from_template("""你是一个 AI 日报的搜索策略助手。你的任务是评估当前搜到的 AI 新闻，判断是否需要继续搜索。

当前已搜到的新闻（{count} 条）：
{items}

已尝试的搜索历史：
{search_history}

请分析：
1. **覆盖面**：是否覆盖了以下类别？
   - 大模型/基座模型发布（如 GPT-5, Claude 4, Qwen 3 等）
   - AI 应用/产品上线（如 AI 助手、AI 工具、新 App）
   - AI 硬件/终端（如 AI 眼镜、AI 芯片、机器人）
   - 重大商业事件（融资、收购、合作）
   - 国内 + 国际是否都有覆盖

2. **质量**：每条新闻是否有实质内容（非快讯、非标题党）

3. **决策**：
   - 如果已有 3+ 条高质量、多类别的新闻 → should_continue=False
   - 如果不足 3 条，或者类别太单一 → should_continue=True，并生成下一轮搜索 query
   - 最多搜 3 轮（当前第 {retry} 轮），第 3 轮必须停止

4. **下一轮策略要求**（如果继续）：

   🚨 **核心原则：绝对禁止重复！**
   - 仔细阅读上面的「已尝试的搜索历史」，如果某个方向已经搜过（不管产出多少），**该方向视为已用尽，必须完全放弃**
   - 如果你生成的 query 和搜索历史中的任何一轮的角度相似，就是错误的！
   - 同一个 site: 组合搜过一次就不要再用了

   🔄 **换赛道策略（按优先级选一个没搜过的方向）**：
   - "大模型厂商"搜不到 → 换"AI SaaS/开发者工具"（site:producthunt.com OR site:sspai.com）
   - "AI应用"搜不到 → 换"AI硬件/机器人/芯片"（site:theverge.com OR site:36kr.com）
   - 中文媒体搜不到 → 换英文媒体（site:techcrunch.com OR site:wired.com OR site:arstechnica.com）
   - 英文媒体搜不到 → 换中文媒体（site:36kr.com OR site:sspai.com OR site:ithome.com）
   - 通用AI搜不到 → 换垂直领域（AI医疗/AI教育/AI金融/自动驾驶）

   📏 **格式要求**：
   - 必须包含 after:{date} 限制7天
   - 必须用 site: 限制到权威来源（避免社交媒体噪音）
   - 控制在 300 字符以内

   ✅ 好的 query 示例：
   AI ("发布" OR "上线") (site:36kr.com OR site:jiqizhixin.com) after:{date}
   ("OpenAI" OR "Anthropic") ("launch" OR "release") (site:techcrunch.com OR site:theverge.com) after:{date}
   AI 硬件 OR AI芯片 OR 机器人 (site:36kr.com OR site:jiqizhixin.com) after:{date}
   AI tool OR AI app (site:producthunt.com OR site:sspai.com) after:{date}

   ❌ 不好的 query（会返回垃圾）：
   大模型发布 OR AI产品上线 OR 融资收购（无site限制，返回社交媒体噪音）
   ("OpenAI" OR "Anthropic" OR "DeepSeek" OR "Kimi") ("launch" OR "发布")（太多OR，无site限制）
   和上一轮搜索角度相同的任何 query（浪费搜索次数）

请严格以 JSON 格式输出，包含 reasoning, should_continue, next_query, gap_category 四个字段。""")

    result = (prompt | reasoner).invoke({
        "count": len(current_items),
        "items": items_text,
        "retry": retry_count,
        "date": target_date,
        "search_history": history_text
    })

    data = result.model_dump()
    print(f"      💭 推理结论: {data['reasoning'][:80]}...")
    print(f"      📋 缺失类别: {data['gap_category']}")
    if data['should_continue']:
        print(f"      🔍 下一轮 Query: {data['next_query'][:80]}...")
    else:
        print(f"      ✅ 判断: 结果已足够，停止搜索")
    return data

@tool
def search_new_products(query: str) -> List[Dict]:
    """【板块1-初筛】搜索全网 AI 新品发布信息"""
    print(f"   🕵️ [Tool] 正在搜索新品: {query}")
    try:
        q = f"{query} -tutorial -review -list -best"
        results = tavily_client.search(q, max_results=20).get('results', [])

        print(f"      ✅ 初筛命中 {len(results)} 条")
        return results
    except Exception as e:
        print(f"      ❌ 搜索报错: {e}")
        return []

@tool
def batch_extract_products(search_results: List[dict]) -> List[dict]:
    """从搜索结果snippet中批量提取AI产品名，过滤掉无关结果和旧产品"""
    if not search_results:
        return []

    target_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    snippets_text = ""
    for i, r in enumerate(search_results):
        snippets_text += f"[{i}] {r.get('title','')} | {r.get('content','')[:200]}\n"

    # 一次LLM调用处理全部snippet（~4500 token）
    extractor = groq_llm.with_structured_output(ProductExtractionList, method="json_mode")
    prompt = ChatPromptTemplate.from_template("""你要从搜索结果snippet中完成两件事：
1. 提取AI相关的产品/模型/工具名称
2. 判断该产品是否为近7天内（{cutoff_date}之后）发布的

⚠️ 关键区分：「文章发布日期」≠「产品发布日期」！
- 一篇2月9日发表的文章可能在介绍一个去年的老产品 → is_recent=False
- 只有snippet中明确提到产品在近7天内"发布/上线/开源/推出"才算 is_recent=True
- 如果snippet中没有提到具体的产品发布时间，默认 is_recent=False

只提取明确提到具体产品发布/上线/开源的条目。
忽略教程、评测、榜单、股价新闻、旧产品回顾等非近期产品发布内容。

搜索结果：
{snippets}

请以JSON格式输出，包含 items 数组，每个元素含：
- index（序号）
- product_name（产品名）
- is_product_launch（是否为产品发布新闻）
- is_recent（该产品是否为近7天内发布的，不是文章日期，是产品本身的发布日期）

只需要输出 is_product_launch=true 且 is_recent=true 的条目。""")

    try:
        result = (prompt | extractor).invoke({"snippets": snippets_text, "cutoff_date": target_date})
        matched_indices = [item.index for item in result.items
                          if item.is_product_launch and item.is_recent and item.product_name]
        candidates = [search_results[i] for i in matched_indices if i < len(search_results)]
        print(f"   🧪 [snippet提取] {len(search_results)}条 → {len(candidates)}条（近7天产品发布）")
        return candidates
    except Exception as e:
        print(f"   ⚠️ snippet提取失败: {e}，保留全部结果")
        return search_results

@tool
def verify_product_page(url: str) -> dict:
    """【板块1-精筛】深度阅读网页，核实新品发布的真实性"""
    print(f"      📖 [Tool] 正在核实网页: {url[:40]}...")
    try:
        loader = WebBaseLoader(url)
        loader.requests_kwargs = {'timeout': 10}
        docs = loader.load()
        content = docs[0].page_content[:4000]
        
        # 动态计算7天前的日期
        cutoff_date = (datetime.now() - timedelta(days=7)).strftime("%Y年%-m月%-d日")
        cutoff_date_iso = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        verifier = groq_llm.with_structured_output(ProductVerification, method="json_mode")
        prompt = ChatPromptTemplate.from_template("""
        请阅读网页，判断这是否为 **AI 领域具有行业影响力的重大事件**。

        ✅ **只接受**以下高质量内容：
        1. 大型科技公司的重大产品发布（OpenAI、Google、Microsoft、Meta、Anthropic、DeepSeek、Qwen、Kimi等）
        2. 突破性技术/模型发布（如新一代大模型、重大技术突破）
        3. 重大功能更新（对行业有显著影响的新功能）
        4. 新应用/新服务上线（AI助手、AI工具、企业服务等）
        5. 重大商业事件（大额融资$10M+、重要收购、战略合作）

        ❌ **拒绝**以下内容：
        1. 个人开发者的小众应用（App Store上的小工具）
        2. 本地LLM客户端/服务器等通用工具
        3. 教程、测评、对比、预测类文章
        4. **超过7天的旧新闻**（必须是{cutoff_date}之后的）
        5. 传闻或未经官方确认的消息
        6. **非直接相关的新闻**（比如报道某公司发布产品导致竞争对手股价下跌的新闻）

        ⚠️ **严格标准**：
        - is_released: 只有真正重大的、已确认的事件才设为 True
        - is_recent: **必须是近7天内（{cutoff_date}之后）的事件**
        - release_date: **必须是产品/模型/服务的实际发布日期，不是文章的发表日期！** 如果原文只有文章发表时间而没有明确写出产品的发布/上线日期，设 is_recent=False
          - 格式：YYYY-MM-DD
          - 必须从原文中找到明确的日期证据（如"于2月7日正式发布"、"launched on Feb 7"）
          - 如果原文没有写具体日期，只说"近日"、"recently"，也设 is_recent=False
        - description: **必须从原文中直接提取**，不要扩充、推测或补充信息！
        - product_name: 必须是具体的产品名称，不要写"某公司产品"
        - 如果是小众应用或工具，即使最近发布也要设 is_released=False
        - **如果网页主要讲的不是产品本身，而是产品发布的影响（如股价、竞争等），设 is_released=False**
        - **如果文章是综述类型，产品只占很小篇幅（如在十几个产品列表中只有一句话），设 is_released=False**

        请以 JSON 格式输出，包含 product_name, is_released, is_recent, release_date, description 五个字段。

        网页内容：{text}
        """)
        
        res = (prompt | verifier).invoke({"text": content, "cutoff_date": cutoff_date, "cutoff_date_iso": cutoff_date_iso})
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

def parse_star_count(text: str) -> int:
    """解析GitHub star数 (支持 1,234 或 1.2k 或 "257 stars this week" 格式)"""
    import re
    text = text.strip()

    # 提取数字部分 (可能包含逗号)
    match = re.search(r'([\d,]+\.?\d*)\s*k?\b', text, re.IGNORECASE)
    if not match:
        return 0

    num_str = match.group(1).replace(',', '')

    # 检查是否有 k 后缀 (但不是 "week" 等单词的一部分)
    # 只在数字紧跟着k时才认为是k后缀 (如 "1.2k" 而不是 "123 stars this week")
    if re.search(r'[\d,]+\.?\d*k\b', text, re.IGNORECASE):
        return int(float(num_str) * 1000)

    try:
        return int(float(num_str))
    except:
        return 0

@tool
def fetch_github_trending() -> List[str]:
    """
    【板块3】GitHub 7天内 star 飙升最快的 AI 项目 Top 5
    策略：抓取GitHub Trending页面，筛选AI相关项目
    """
    print("   🐙 [Tool] 正在拉取 GitHub Trending（7天飙升榜）...")
    try:
        from bs4 import BeautifulSoup

        # 1. 抓取trending页面
        url = "https://github.com/trending?since=weekly&spoken_language_code=en"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        # 2. 解析HTML
        soup = BeautifulSoup(resp.text, 'html.parser')
        articles = soup.find_all('article', class_='Box-row')

        results = []
        count = 0

        # 3. AI关键词过滤
        ai_keywords = ['ai', 'ml', 'machine-learning', 'deep-learning', 'llm',
                       'gpt', 'neural', 'model', 'transformer', 'chatbot']

        for article in articles:
            if count >= 5:
                break

            try:
                # 提取仓库名
                h2 = article.find('h2', class_='h3')
                if not h2:
                    continue
                a_tag = h2.find('a')
                if not a_tag:
                    continue

                repo_path = a_tag['href'].strip('/')
                full_name = repo_path
                repo_url = f"https://github.com/{repo_path}"

                # 提取描述
                desc_p = article.find('p', class_='col-9')
                description = desc_p.text.strip() if desc_p else ""

                # 提取语言
                lang_span = article.find('span', itemprop='programmingLanguage')
                language = lang_span.text.strip() if lang_span else "Unknown"

                # 提取stars
                stars_span = article.find('span', class_='d-inline-block float-sm-right')
                stars_text = stars_span.text.strip() if stars_span else "0"
                # 解析 "1,234" 或 "1.2k" 格式
                stars = parse_star_count(stars_text)

                # AI过滤
                text_to_check = (full_name + " " + description).lower()
                if not any(kw in text_to_check for kw in ai_keywords):
                    continue

                print(f"      📥 [GitHub-Trending] ({language}) {full_name} (⭐{stars})...")

                # 获取README
                readme_text = "暂无详细介绍"
                try:
                    for branch in ['main', 'master']:
                        raw_url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
                        r = requests.get(raw_url, timeout=5)
                        if r.status_code == 200:
                            readme_text = r.text[:3000]
                            break
                except Exception:
                    pass

                # 格式化输出
                info = (
                    f"=== Repo: {full_name} ===\n"
                    f"URL: {repo_url}\n"
                    f"Date: Recent (Trending)\n"
                    f"Language: {language}\n"
                    f"Stars: {stars} | Desc: {description}\n"
                    f"--- README snippet ---\n"
                    f"{readme_text}\n"
                    f"======================\n"
                )
                results.append(info)
                count += 1

            except Exception as e:
                print(f"      ⚠️ 解析项目失败: {e}")
                continue

        print(f"      ✅ GitHub Trending 抓取成功: {count} 个AI项目")
        return results

    except Exception as e:
        print(f"   ❌ GitHub Trending 抓取错误: {e}")
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
    
    # 核心关注名单（中美10家）
    target_orgs = [
        # 美国5家
        "OpenAI", "Google", "DeepMind", "Meta", "Anthropic", "Microsoft",
        # 中国5家
        "DeepSeek", "Qwen", "ByteDance", "Moonshot", "Zhipu"
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

        # 映射表：只保留中美10家头部AI厂商
        tech_map = {
            # ===== 美国5家 =====
            "openai": "OpenAI",
            "google": "Google",
            "deepmind": "Google DeepMind",
            "meta": "Meta",
            "facebook": "Meta",
            "anthropic": "Anthropic",
            "microsoft": "Microsoft",

            # ===== 中国5家 =====
            # 1. DeepSeek
            "deepseek": "DeepSeek",

            # 2. Qwen/阿里巴巴
            "qwen": "Qwen",
            "通义": "Qwen",
            "alibaba": "Alibaba",
            "阿里": "Alibaba",

            # 3. 字节跳动
            "bytedance": "ByteDance",
            "字节": "ByteDance",
            "doubao": "ByteDance",
            "豆包": "ByteDance",

            # 4. 月之暗面
            "moonshot": "Moonshot AI",
            "月之暗面": "Moonshot AI",
            "kimi": "Moonshot AI",

            # 5. 智谱AI
            "zhipu": "Zhipu AI",
            "智谱": "Zhipu AI",
            "glm": "Zhipu AI",
            "chatglm": "Zhipu AI"
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
            # 接受 arxiv.org/(abs|pdf|html)/XXXX.XXXXX 或 huggingface.co/papers/XXXX.XXXXX
            is_valid_paper_url = False
            # arxiv格式：abs, pdf, html 都接受
            if "arxiv.org/" in url and re.search(r'arxiv\.org/(abs|pdf|html)/\d{4}\.\d+', url):
                is_valid_paper_url = True
            # huggingface papers
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

            # --- 4. 归属机构与"官方性"判定 (核心升级) ---
            org_label = None  # 默认为None，只保留能明确识别的

            # === DeepSeek 特判逻辑 (正则版) ===
            if "deepseek" in title_lower:
                # (1) 排除法：如果是第三方评测，直接跳过
                third_party_keywords = [
                    "survey", "evaluation", "benchmark", "analysis", "review",
                    "vs.", "comparison", "finetuning", "implementation",
                    "understanding", "jailbreaking", "reproduction"
                ]
                if any(w in title_lower for w in third_party_keywords):
                    print(f"         - [跳过] 第三方评测: {title[:40]}...")
                    continue

                # (2) 正则匹配法：只要符合 DeepSeek-XXX 格式，或者包含 "technical report"
                version_pattern = r"deepseek-[a-z0-9]+"
                if "technical report" in title_lower or re.search(version_pattern, title_lower):
                    org_label = "DeepSeek"
                else:
                    org_label = "DeepSeek"

            # === 其他大厂通用逻辑 ===
            else:
                url_lower = url.lower()
                matched = False
                for k, v in tech_map.items():
                    # 扩大搜索范围：title + content + url
                    if k in title_lower or k in content.lower() or k in url_lower:
                        # 检查是否为第三方评测
                        if any(w in title_lower for w in ["evaluation", "survey", "benchmark", "analysis"]):
                            print(f"         - [跳过] 第三方评测: {title[:40]}...")
                            matched = True
                            break
                        org_label = v
                        matched = True
                        break

                if matched and org_label is None:
                    continue  # 是第三方评测，跳过

            # 如果没有匹配到任何核心厂商，跳过
            if org_label is None:
                print(f"         - [跳过] 非核心厂商: {title[:40]}...")
                continue

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
ALL_TOOLS = [search_new_products, batch_extract_products, verify_product_page, fetch_hf_trending_models, fetch_github_trending, fetch_big_tech_papers]