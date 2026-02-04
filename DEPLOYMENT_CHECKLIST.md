# 🚀 GitHub Actions 部署检查清单

## ✅ 已完成的代码修复

### 1. 移除硬编码代理设置 ✅
- **问题**: 代码中硬编码了 `127.0.0.1:7897` 代理
- **影响**: GitHub Actions 服务器无法访问本地代理，导致失败
- **修复**: 改为从环境变量 `LOCAL_VPN` 读取，GitHub Actions 中设为空

### 2. 修复文件路径问题 ✅
- **问题**: 使用相对路径 `data/news.json` 可能导致找不到文件
- **影响**: 数据保存失败
- **修复**: 使用绝对路径，自动检测项目根目录

### 3. 添加错误处理 ✅
- **问题**: 任何一个数据源失败会导致整个流程失败
- **影响**: 稳定性差
- **修复**: 为每个节点添加 try-catch，允许部分失败

### 4. 添加超时控制 ✅
- **问题**: LLM 调用可能无限等待
- **影响**: GitHub Actions 可能超时（15分钟限制）
- **修复**: 设置 30秒超时 + 最多2次重试

---

## 📋 部署前检查

### GitHub Secrets 配置（你已完成）
访问: https://github.com/wuhao980527-gif/ai-daily-web/settings/secrets/actions

确认以下 4 个 Secrets 已配置：
- ✅ `MY_API_KEY`
- ✅ `MY_BASE_URL`
- ✅ `MY_MODEL_NAME`
- ✅ `TAVILY_API_KEY`

---

## 🧪 本地测试（推荐先测试）

在提交到 GitHub 前，先在本地测试：

```bash
cd /Users/admin/Desktop/ai-daily-web
bash test_workflow.sh
```

这个脚本会：
1. 检查环境变量
2. 安装依赖
3. 运行 Agent
4. 验证生成的 data/news.json

**如果本地测试通过，再提交到 GitHub！**

---

## 🚢 提交到 GitHub

### 1. 提交修改
```bash
cd /Users/admin/Desktop/ai-daily-web
git add .
git commit -m "fix: 修复 GitHub Actions 兼容性问题

- 移除硬编码本地代理设置
- 修复文件路径为绝对路径
- 添加错误处理和超时控制
- 添加测试脚本"
git push
```

### 2. 手动触发测试
访问: https://github.com/wuhao980527-gif/ai-daily-web/actions

1. 点击 "Daily AI Insight Update" workflow
2. 点击右侧 "Run workflow" 按钮
3. 选择 `main` 分支
4. 点击绿色 "Run workflow" 按钮

### 3. 查看运行日志
- 等待约 3-5 分钟
- 点击运行记录查看详细日志
- 检查每个步骤是否成功

---

## 🔍 常见问题排查

### 如果 GitHub Actions 失败：

#### 1. API Key 错误
**症状**: `Authentication failed` 或 `401 Unauthorized`
**解决**:
- 检查 GitHub Secrets 中的 `MY_API_KEY` 是否正确
- 确认 API Key 有效且有额度

#### 2. 超时错误
**症状**: `timeout` 或运行超过 15 分钟
**解决**:
- 检查 `MY_BASE_URL` 是否可以从美国访问（GitHub 服务器在美国）
- 尝试使用更快的 API 提供商（如 Groq）

#### 3. 依赖安装失败
**症状**: `pip install` 步骤报错
**解决**:
- 检查 requirements.txt 是否完整
- 可能需要锁定版本号

#### 4. 文件权限错误
**症状**: `Permission denied` 写入文件
**解决**:
- 确认 workflow 中有 `permissions: contents: write`（已配置）

#### 5. 数据格式错误
**症状**: 前端显示异常
**解决**:
- 检查生成的 data/news.json 格式是否正确
- 可能需要调整 writer_node 的输出格式

---

## 📊 预期结果

### 成功标志：
1. ✅ GitHub Actions 显示绿色 ✓
2. ✅ 仓库中 `data/news.json` 有新的 commit
3. ✅ Vercel 自动触发重新部署
4. ✅ 访问 https://ai-daily-web-r.vercel.app/ 看到今天的数据

### 查看运行结果：
```bash
# 拉取最新代码
git pull

# 查看生成的数据
cat data/news.json
```

---

## 🔄 定时运行

配置成功后，系统将：
- **每天 UTC 01:00**（北京时间 09:00）自动运行
- 自动抓取最新 AI 资讯
- 自动提交到仓库
- Vercel 自动部署更新

---

## 📞 需要帮助？

如果遇到问题，请：
1. 查看 GitHub Actions 的详细日志
2. 复制错误信息
3. 告诉我具体的错误提示

祝部署顺利！🎉
