<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/Vercel-Deploy-black?logo=vercel&logoColor=white" alt="Vercel">
</p>

<h1 align="center">🚀 Freebuff2API</h1>

<p align="center">
  <strong>将 Freebuff 免费 AI 模型转换为标准 OpenAI Chat Completions API 格式</strong>
</p>

<p align="center">
  <a href="#-功能特性">功能特性</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-部署方式">部署方式</a> •
  <a href="#-api-文档">API 文档</a> •
  <a href="#-管理面板">管理面板</a> •
  <a href="#-模型列表">模型列表</a> •
  <a href="#-常见问题">常见问题</a>
</p>

---

## 🌟 功能特性

| 功能 | 说明 |
|:---:|:---|
| 🔄 **OpenAI 兼容** | 完全兼容 `/v1/chat/completions` 接口，可直接替代 OpenAI API |
| 🤖 **Anthropic 兼容** | 支持 `/v1/messages` 接口，兼容 Claude Code 等客户端 |
| 🆓 **完全免费** | 基于 Freebuff 免费模型，无需付费 |
| 🎯 **多模型支持** | DeepSeek V4 Flash/Pro、Kimi K2.6、MiniMax M2.7/M3、Mimo V2.5/V2.5 Pro、Gemini |
| 🔑 **多 API Key** | 支持创建多个 API Key，每个 Key 可配置独立的模型白名单 |
| 📊 **管理面板** | 现代化 React 管理后台，支持实时日志、Token 管理、网络检测等 |
| 🌊 **流式输出** | 完整支持 SSE 流式响应（Streaming） |
| 🚀 **一键部署** | 支持 Vercel Serverless 和本地/服务器部署 |
| 🔒 **安全认证** | HMAC 签名 Session Cookie、登录限流、CSRF 防护 |
| 📱 **响应式设计** | 管理面板适配桌面端和移动端 |

---

## 📝 更新日志

### v0.1.1（2026-08-01）— 🐛 修复上游 403 `free_mode_cli_required`

**问题**：直接调用 Freebuff API 时返回 `403 free_mode_cli_required`（"Free mode is only available through the freebuff CLI"），导致所有模型无法使用。

**根因**：上游服务端会校验 chat/completions 请求体中的 system 提示词是否为 CLI 的真实 Buffy 提示词（`"You are Buffy, the strategic coding assistant...Freebuff..."`）。旧版使用伪造的 `"You are Buffy. [System Override...]"` 前缀，被服务端识别为非 CLI 请求后拒绝。

**修复**：

- 新增 `freebuff2api/buffy_prompt.py`：从 freebuff CLI 二进制（v0.0.135）提取的真实 Buffy 系统提示词模板，日期动态生成
- `openai_compat.py`：`normalize_chat_messages` 始终在第一条 system 消息注入真实 Buffy 提示词（用户自定义 system 内容追加在其后，不再覆盖）
- `codebuff.py`：chat 请求 User-Agent 版本 `ai-sdk/provider-utils/3.0.20` → `3.0.25`（与 CLI 一致）

**验证**：端到端实测 session → agent-runs → chat/completions 返回 200 + SSE 流式响应，测试套件零回归。


## 🚀 快速开始

### 环境要求

- Python 3.11+（推荐 3.12）
- Node.js 18+（仅构建前端需要）

### 1. 克隆仓库

```bash
git clone https://github.com/t479842598/freebuff2apiNew.git
cd freebuff2apiNew
```

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，至少填写以下变量：

```env
# 🔑 Freebuff Token（必填）
# 从 https://www.codebuff.com 获取
FREEBUFF_TOKEN=your_token_here

# 🔐 API Key（必填）
# 用于调用 /v1/* 接口的访问密钥
FREEBUFF_API_KEY=sk-your-api-key

# 🛡️ 管理员密钥（必填）
# 用于登录管理面板
FREEBUFF_ADMIN_KEY=sk-admin
```

### 4. 启动服务

```bash
python main.py
# 或
uvicorn freebuff2api.app:app --host 0.0.0.0 --port 8000
```

### 5. 验证

```bash
# 健康检查
curl http://localhost:8000/healthz

# 获取模型列表
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer sk-your-api-key"

# 测试对话
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-api-key" \
  -d '{
    "model": "deepseek/deepseek-v4-flash",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 🌐 部署方式

### 方式一：Vercel 部署（推荐）

#### 1. Fork 仓库

在 GitHub 上 Fork 本仓库到你的账号。

#### 2. 连接 Vercel

1. 登录 [Vercel](https://vercel.com)
2. 点击 **"New Project"**
3. 选择 Fork 的仓库
4. 框架预设选择 **"Other"**
5. 点击 **"Deploy"**

#### 3. 配置环境变量

在 Vercel 项目设置中添加环境变量：

- `FREEBUFF_TOKEN` - 你的 Freebuff Token
- `FREEBUFF_API_KEY` - API 访问密钥
- `FREEBUFF_ADMIN_KEY` - 管理面板密钥

#### 4. 自定义域名（可选）

在 Vercel 项目设置 → **Domains** 中添加你的域名。

### 方式二：本地/服务器部署

```bash
# 使用 systemd 守护进程（Linux）
sudo tee /etc/systemd/system/freebuff2api.service <<EOF
[Unit]
Description=Freebuff2API Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/freebuff2api
ExecStart=/path/to/.venv/bin/uvicorn freebuff2api.app:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable freebuff2api
sudo systemctl start freebuff2api
```

### 方式三：Docker 部署

```bash
docker build -t freebuff2api .
docker run -d \
  -p 8000:8000 \
  -e FREEBUFF_TOKEN=your_token \
  -e FREEBUFF_API_KEY=sk-your-key \
  -e FREEBUFF_ADMIN_KEY=sk-admin \
  --name freebuff2api \
  freebuff2api
```

---

## 📚 API 文档

### OpenAI 兼容接口

#### 获取模型列表

```http
GET /v1/models
Authorization: Bearer YOUR_API_KEY
```

#### Chat Completions

```http
POST /v1/chat/completions
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "model": "deepseek/deepseek-v4-flash",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "temperature": 0.7
}
```

#### Anthropic Messages（Claude Code 兼容）

```http
POST /v1/messages
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json

{
  "model": "deepseek/deepseek-v4-flash",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "max_tokens": 4096
}
```

### 支持的参数

| 参数 | 支持 | 说明 |
|:---:|:---:|:---|
| `model` | ✅ | 模型 ID（见下方模型列表） |
| `messages` | ✅ | 消息数组 |
| `stream` | ✅ | 流式输出 |
| `temperature` | ✅ | 温度参数 |
| `max_tokens` | ✅ | 最大输出 token 数 |
| `top_p` | ✅ | Top-p 采样 |
| `stop` | ✅ | 停止词 |
| `tools` | ✅ | 工具调用（Function Calling） |

---

## 🖥️ 管理面板

访问 `http://localhost:8000/admin` 进入管理面板。

### 功能模块

| 模块 | 说明 |
|:---:|:---|
| 📊 **概览** | 服务状态、Token 数量、模型数量、部署环境 |
| 🔑 **Token 管理** | 添加/编辑/删除 Freebuff Token，支持验证有效性 |
| 🗝️ **API Key** | 创建多个 API Key，配置模型白名单 |
| 📝 **运行日志** | 实时查看服务日志，按等级筛选 |
| 📈 **请求记录** | 查看 API 调用历史，按模型/状态筛选 |
| ⚙️ **Env 查看** | 查看环境配置文件内容 |
| 🌐 **网络检测** | 检测公网 IP、地理位置、上游服务连通性 |
| 🧪 **模型测试** | 在线测试模型调用效果 |
| 🛡️ **设置** | 修改管理员密钥 |

### 技术栈

- **前端**: React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui 风格组件
- **构建**: Vite 8，输出到 `freebuff2api/admin_static/`
- **后端**: FastAPI 直接服务构建产物，SPA fallback 路由

---

## 🤖 模型列表

### Freebuff 免费模型

| 模型 ID | 提供商 | 说明 |
|:---|:---:|:---|
| `deepseek/deepseek-v4-flash` | DeepSeek | 🚀 快速响应，适合日常对话 |
| `deepseek/deepseek-v4-pro` | DeepSeek | 💪 高性能，适合复杂任务 |
| `moonshotai/kimi-k2.6` | Moonshot | 🌙 中文优化，长文本能力强 |
| `minimax/minimax-m2.7` | MiniMax | 🎯 多模态，性价比高 |
| `minimax/minimax-m3` | MiniMax | 🚀 最新版本，性能提升 |
| `mimo/mimo-v2.5` | Mimo | 🔬 代码能力强 |
| `mimo/mimo-v2.5-pro` | Mimo | 💪 Pro 版本，更强代码能力 |

### Google Gemini 免费模型

| 模型 ID | 说明 |
|:---|:---|
| `google/gemini-2.5-flash-lite` | ⚡ 轻量快速 |
| `google/gemini-3.1-flash-lite-preview` | 🔬 最新预览版 |
| `google/gemini-3.1-pro-preview` | 💪 Pro 版本 |

---

## ⚙️ 环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|:---|:---:|:---:|:---|
| `FREEBUFF_TOKEN` | ✅ | - | Freebuff Token（多个用逗号分隔） |
| `FREEBUFF_API_KEY` | ✅ | - | API 访问密钥 |
| `FREEBUFF_ADMIN_KEY` | ✅ | `sk-admin` | 管理面板密钥（⚠️ 必须修改） |
| `FREEBUFF_API_BASE_URL` | ❌ | `https://www.codebuff.com` | 上游 API 地址 |
| `FREEBUFF_TIMEOUT` | ❌ | `60` | 请求超时（秒） |
| `FREEBUFF_PROXY_ENABLED` | ❌ | `false` | 是否启用代理 |
| `FREEBUFF_PROXY_URL` | ❌ | - | 代理地址（支持 socks5） |
| `FREEBUFF_DEBUG` | ❌ | `false` | 调试模式 |
| `FREEBUFF_LOG_LEVEL` | ❌ | `INFO` | 日志等级 |
| `FREEBUFF_HOST` | ❌ | `0.0.0.0` | 监听地址 |
| `FREEBUFF_PORT` | ❌ | `8000` | 监听端口 |

---

## 🛡️ 安全建议

1. **修改默认密钥**：部署前务必修改 `FREEBUFF_ADMIN_KEY` 和 `FREEBUFF_API_KEY`
2. **使用 HTTPS**：生产环境建议配置 SSL/TLS
3. **限制访问**：通过防火墙或 API Key 限制访问来源
4. **定期轮换**：定期更换 Token 和 API Key

---

## 🔧 开发指南

### 前端开发

```bash
cd web

# 安装依赖
npm install

# 启动开发服务器（热重载）
npm run dev

# 构建生产版本
npm run build
```

前端使用：
- React 19 + TypeScript
- Tailwind CSS v4
- Vite 8 构建
- 代理到 `localhost:8000` 后端

### 项目结构

```
freebuff2apiNew/
├── freebuff2api/           # 🐍 Python 后端核心
│   ├── app.py             # FastAPI 主应用
│   ├── admin.py           # 管理面板 API
│   ├── codebuff.py        # Freebuff 上游客户端
│   ├── config.py          # 配置加载
│   ├── models.py          # 模型定义
│   ├── buffy_prompt.py    # 🐝 真实 Buffy system 提示词（上游校验必需）
│   ├── openai_compat.py   # OpenAI 格式兼容层
│   ├── anthropic_compat.py # Anthropic 格式兼容层
│   ├── usage.py           # 数据模型
│   ├── usage_store.py     # 存储层
│   ├── logging_config.py  # 日志配置
│   └── admin_static/      # 🎨 前端构建产物
├── web/                    # 🎨 React 前端源码
│   ├── src/pages/         # 10个页面组件
│   ├── src/components/    # UI 组件库
│   ├── src/hooks/         # React Hooks
│   └── src/lib/           # 工具函数
├── main.py                 # 🏃 本地运行入口
├── requirements.txt        # 📦 Python 依赖
├── vercel.json             # ⚙️ Vercel 配置
└── .env.example            # 📝 环境变量模板
```

---

## ❓ 常见问题

### Q: 获取 Token 后在哪里填写？

A: 有两种方式：
1. **管理面板**：访问 `/admin` → Token 管理 → 添加
2. **环境变量**：在 `.env` 文件中设置 `FREEBUFF_TOKEN`

### Q: 如何获取 Freebuff Token？

A: 访问 [https://www.codebuff.com](https://www.codebuff.com)，注册账号后在设置页面获取 API Token。

### Q: 支持哪些客户端？

A: 所有支持 OpenAI API 的客户端都可以使用，包括：
- ChatGPT Next Web
- LobeChat
- ChatBox
- Cursor
- VS Code + Continue
- Claude Code（使用 `/v1/messages` 接口）

### Q: Vercel 部署有访问限制吗？

A: Vercel 免费版有以下限制：
- 每月 100GB 带宽
- 每秒 1 次函数执行
- 函数执行时间 ≤ 10s

建议流量较大的用户使用本地/服务器部署。

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

- [Freebuff](https://freebuff.com) - 提供免费 AI 模型
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能 Python Web 框架
- [React](https://react.dev/) - 前端 UI 库
- [Tailwind CSS](https://tailwindcss.com/) - 实用优先的 CSS 框架
- [Vercel](https://vercel.com) - Serverless 部署平台

---

<p align="center">
  <strong>⭐ 如果觉得有用，请给个 Star 支持一下！</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/github/stars/t479842598/freebuff2apiNew?style=social" alt="Stars">
  <img src="https://img.shields.io/github/forks/t479842598/freebuff2apiNew?style=social" alt="Forks">
</p>
