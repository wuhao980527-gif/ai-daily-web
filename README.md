# 🤖 AI Daily Insight (AI 全景日报)

> 全自动化的 AI 趋势聚合平台。
> **Python Agent** 负责抓取清洗，**Next.js** 负责高颜值呈现。

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Python](https://img.shields.io/badge/Python-3.11-yellow)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent-orange)

## 📖 项目简介 (Introduction)

**AI Daily Insight** 是一个全栈自动化新闻聚合项目。它致力于解决“信息过载”问题，通过 AI Agent 每天自动从全球各大科技源（Product Hunt, Hugging Face, GitHub, Arxiv）抓取最新动态，并生成结构化的中文简报。

### ✨ 核心特性

- **🕵️ 全自动抓取**: 基于 `LangGraph` 的 AI Agent，自动执行搜索、验证、反思工作流。
- **🧠 智能清洗**: 利用 LLM (GPT-4o) 对杂乱信息进行去重、翻译、摘要和标签化。
- **🎨 科技感 UI**: 采用 Tailwind CSS 设计的响应式界面，支持暗黑科技风卡片与动态光效。
- **📱 完美适配**: 移动端、桌面端自适应布局，支持历史日报归档折叠。
- **⚡ 静态部署**: 前端纯静态构建，可直接托管至 Vercel，访问速度极快。

---

## 🛠 技术栈 (Tech Stack)

### 🐍 Backend (数据生产)
- **LangChain / LangGraph**: 构建智能 Agent 工作流 (ReAct 架构)。
- **Tavily API**: 强大的 AI 搜索引擎，用于抓取实时网络数据。
- **Python**: 核心逻辑处理。

### ⚛️ Frontend (数据展示)
- **Next.js 14**: App Router 架构。
- **Tailwind CSS**: 极简样式与动画。
- **TypeScript**: 类型安全保证。

---

## 🚀 快速开始 (Quick Start)

### 1. 环境准备
- Node.js 18+
- Python 3.10+
- 科学上网环境 (如果在中国大陆)

### 2. 安装依赖

**后端依赖:**
```bash
pip install -r python_backend/requirements.txt
# 或者手动安装核心包
pip install langchain langchain-openai langgraph tavily-python python-dotenv