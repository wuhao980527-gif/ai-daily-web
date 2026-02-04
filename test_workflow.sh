#!/bin/bash

# 测试脚本 - 模拟 GitHub Actions 环境
# 使用方法: bash test_workflow.sh

echo "🧪 开始测试工作流..."
echo ""

# 检查必要的环境变量
if [ -z "$MY_API_KEY" ] || [ -z "$MY_BASE_URL" ] || [ -z "$MY_MODEL_NAME" ] || [ -z "$TAVILY_API_KEY" ]; then
    echo "⚠️ 环境变量未设置，从 .env 文件加载..."
    if [ -f "python_backend/.env" ]; then
        export $(cat python_backend/.env | grep -v '^#' | xargs)
        echo "✅ 已加载 .env 文件"
    else
        echo "❌ 错误: 找不到 python_backend/.env 文件"
        echo "请先创建 .env 文件并配置 API Keys"
        exit 1
    fi
fi

echo ""
echo "📋 环境变量检查:"
echo "  MY_API_KEY: ${MY_API_KEY:0:10}..."
echo "  MY_BASE_URL: $MY_BASE_URL"
echo "  MY_MODEL_NAME: $MY_MODEL_NAME"
echo "  TAVILY_API_KEY: ${TAVILY_API_KEY:0:10}..."
echo ""

# 确保不使用本地代理
export LOCAL_VPN=""

# 安装依赖
echo "📦 安装 Python 依赖..."
pip install -q -r python_backend/requirements.txt

# 运行 Agent
echo ""
echo "🚀 运行 Agent..."
python python_backend/agent_graph.py

# 检查结果
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 测试成功！"
    echo ""
    echo "📄 检查生成的文件:"
    if [ -f "data/news.json" ]; then
        echo "  ✅ data/news.json 已生成"
        echo ""
        echo "文件大小: $(wc -c < data/news.json) bytes"
        echo "最新记录日期: $(cat data/news.json | grep -o '"date":"[^"]*' | head -1 | cut -d'"' -f4)"
    else
        echo "  ❌ data/news.json 未生成"
    fi
else
    echo ""
    echo "❌ 测试失败，请检查错误信息"
    exit 1
fi
