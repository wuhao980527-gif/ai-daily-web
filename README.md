# 🤖 AI Daily Insight (Project Panorama)

> **Next-Gen AI Trend Aggregator powered by Multi-Agent Systems.**
> 全自动化的 AI 趋势聚合平台。**LangGraph Agent** 负责智能编排，**Next.js** 负责高颜值呈现。

![License](https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square)
![Architecture](https://img.shields.io/badge/Architecture-ReAct-purple?style=flat-square)
![Next.js](https://img.shields.io/badge/Frontend-Next.js_14-black?style=flat-square)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange?style=flat-square)
![LLM](https://img.shields.io/badge/Kernel-GPT--4o-green?style=flat-square)

## 📖 项目简介 (Introduction)

**AI Daily Insight** 是一个基于 **LLM Agent** 的全栈自动化数据产品。它致力于解决信息过载问题，构建了一个**自主运行的 AI 数据分析师**。

该系统摒弃了传统的关键词爬虫，而是采用 **ReAct (Reasoning + Acting)** 认知架构。Agent 能够像人类一样：
1.  **规划 (Plan)**：动态生成多维度的搜索策略。
2.  **执行 (Act)**：调用 Tavily 搜索引擎和各大科技平台 API。
3.  **反思 (Reflect)**：自我检查数据质量，发现不足时自动调整搜索词重试。
4.  **生成 (Generate)**：最终合成结构化的 JSON 数据并驱动前端更新。

---

## 🏗️ 系统架构 (System Architecture)

本项目核心基于 **LangGraph** 构建了一个**有向有环图 (Cyclic Graph)**，实现了具有自我纠错能力的 Agent 工作流。

```mermaid
graph TD
    %% 定义样式
    classDef startend fill:#f9f,stroke:#333,stroke-width:2px;
    classDef process fill:#e1f5fe,stroke:#0277bd,stroke-width:2px;
    classDef decision fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;
    classDef output fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px;

    Start((🚀 Start)) --> Init[⚙️ Init Node<br/>生成动态搜索策略]
    Init --> Parallel{⚡ 并行分发}
    
    %% 并行分支
    Parallel -->|API 直连| HF[🤗 HuggingFace<br/>Trending Models]
    Parallel -->|API 直连| GH[🐙 GitHub<br/>Dev Trends]
    Parallel -->|API 直连| Papers[📜 Arxiv/BigTech<br/>Research Papers]
    Parallel -->|ReAct Loop| Search[🔍 Product Search<br/>Tavily API]

    %% ReAct 循环逻辑
    Search --> Verify[🛡️ Verify Node<br/>验证页面 & 提取信息]
    Verify --> Check{Quality Check<br/>数据量达标?}
    
    Check -- No (不足) --> Reflect[🧠 Reflect Node<br/>反思并生成新关键词]
    Reflect --> Search
    
    Check -- Yes (达标) --> Writer
    HF --> Writer
    GH --> Writer
    Papers --> Writer

    %% 汇总输出
    Writer[✍️ Writer Node<br/>GPT-4o 汇总清洗 & JSON生成] --> JSON[(💾 Data/news.json)]
    JSON --> Deploy[🚀 Git Push &<br/>Vercel Auto Deploy]
    Deploy --> End((✅ End))

    class Start,End startend;
    class Init,Search,Verify,Reflect,HF,GH,Papers,Writer process;
    class Parallel,Check decision;
    class JSON,Deploy output;