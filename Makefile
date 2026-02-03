# 定义伪目标，防止和文件名冲突
.PHONY: install run clean update help

# 默认目标
help:
	@echo "🤖 AI Daily Insight - 管理命令"
	@echo "================================="
	@echo "make install  - 一键安装所有依赖 (Python + Node)"
	@echo "make run      - 启动数据生成 + 前端预览"
	@echo "make update   - 手动触发一次数据抓取"
	@echo "make clean    - 清理缓存文件"

# 一键安装
install:
	@echo "📦 正在安装 Python 依赖..."
	@pip install -r python_backend/requirements.txt
	@echo "📦 正在安装前端依赖..."
	@npm install
	@echo "✅ 环境安装完成！"

# 一键运行 (先跑数据，再开网页)
run:
	@echo "🐍 正在生成最新日报数据..."
	@python3 python_backend/agent_graph.py
	@echo "🚀 启动前端预览..."
	@npm run dev

# 单独更新数据
update:
	@python3 python_backend/agent_graph.py

# 清理垃圾
clean:
	@rm -rf node_modules
	@rm -rf .next
	@rm -rf python_backend/__pycache__
	@echo "🧹 清理完成"