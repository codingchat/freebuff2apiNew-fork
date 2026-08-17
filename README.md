<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white" alt="Python">  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white" alt="FastAPI">
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
| 🔄 **多账号轮询** | 多 Token 自动轮换，每次请求切换下一个可用账号；429 限流自动冷却并跳过，失败账号自动剔除 |
| 🧠 **按模型限流隔离** | 429 冷却按 (账号, 模型) 隔离，一个模型限流不影响同账号其他模型 |
| 📊 **模型可用矩阵** | 概览页实时展示每个模型在每个 Token 上的可用状态与冷却倒计时 |
| 🛡️ **健康自愈** | 启动批量验证 Token、冷却到期自动半开探测恢复、成功调用重置失败计数 |
| 📊 **管理面板** | 现代化 React 管理后台，支持实时日志、Token 管理、网络检测等 |
| 🌊 **流式输出** | 完整支持 SSE 流式响应（Streaming） |
| 🚀 **一键部署** | 支持 Vercel Serverless 和本地/服务器部署 |
| 🔒 **安全认证** | HMAC 签名 Session Cookie、登录限流、CSRF 防护 |
| 📱 **响应式设计** | 管理面板适配桌面端和移动端（移动端抽屉导航、响应式表格/表单） |

---

## 📝 更新日志

### v4.0.0（2026-08-17）— 🔄 三模式账号轮换 + 请求体保护 + 0.0.63 协议对齐

**新增**：

- **账号轮换三模式 UI**：Token 管理页三态开关（并发/半并发/串行），默认串行；切换即时生效，无需重启
- **请求体大小限制 UI**：Token 管理页可设置 `FREEBUFF_MAX_REQUEST_BODY_BYTES`，默认 2 MB；超限返回 413 并写入日志
- **日志增强**：运行日志页新增搜索框和分类筛选（客户端请求/入站请求/出站请求）；日志时间改为北京时间；413 拒绝会写入日志
- **模型映射本地快照**：动态模型注册表成功拉取后保存 `model_registry_snapshot.json`；GitHub/jsDelivr 不可用时从快照恢复，最后硬编码兜底
- **0.0.63 协议对齐**：session 请求带 `x-freebuff-multi-session`；chat 移除旧版 `x-freebuff-instance-id` 头；`codebuff_metadata` 增加 `freebuff_multi_session`；`reasoning_effort` 移入 `freebuff_reasoning_effort`
- **空流友好报错**：上游空流重试一次后仍失败，返回中文解释 + 原始错误，不再返回空响应

**移除**：

- **移除 `FREEBUFF_ACCOUNT_CONCURRENCY` 环境变量**：旧的每账号并发数字配置已由 `FREEBUFF_ROTATION_MODE` 三模式替代，内部固定为 premium 1 + unlimited 1 双通道

**验证**：全量测试 169 passed；前端 Vite 构建通过；动态模型注册表本地快照生成成功。

### v0.3.0（2026-08-02）— 📱 管理面板移动端适配

**新增**：

- **移动端导航（新）**：此前手机（<1024px）打开管理面板没有任何导航入口，无法切换页面。本次新增顶部汉堡菜单与滑出式抽屉导航，包含全部 9 个页面入口（概览/Token 管理/API Key/运行日志/请求记录/Env 查看/网络检测/模型测试/设置），点击跳转后自动关闭，支持点击遮罩关闭，带进入/退出动画并尊重系统“减弱动态效果”设置。
- **页面工具栏响应式**：请求记录、运行日志、Token 管理等页面的搜索框 / 筛选下拉 / 操作按钮组在窄屏下自动换行排列，不再横向溢出或挤压。
- **表单纵向堆叠**：API Key 新增、Token 添加、模型测试、设置页（管理员密钥、代理配置、代理认证）等多输入框表单在手机上由并排改为纵向排列，输入框宽度占满。
- **表格与长文本显示全**：小屏下所有表格字号与单元格内边距自动收紧，外层容器保留横向滚动以查看完整列；API Key 长密钥自动换行不溢出、请求记录错误信息由截断改为完整换行展示、运行日志行在手机上改为“元数据行 + 消息行”两行布局。
- **字体可读性**：全局禁用 iOS 自动字号缩放（`-webkit-text-size-adjust`），避免输入框聚焦时字体被系统放大。

**改动文件**：`web/src/components/layout/AppLayout.tsx`（抽屉导航）、`web/src/index.css`（全局移动端规则与动画）、`web/src/pages/`下 9 个页面、`freebuff2api/admin_static/`（构建产物）

**验证**：`tsc` 类型检查 + Vite 构建通过；Chrome CDP 以 390×844 移动端视口实测全部页面 `scrollWidth == 视口宽度`（无水平溢出）、抽屉导航 9 项可用、表格可横向滚动查看全部列；桌面端（≥1024px）布局不变。

### v0.2.0（2026-08-01）— 🔄 多账号轮询与健康管理

**新增**：

- **多账号轮询**：`FREEBUFF_TOKEN` 支持逗号分隔多 Token，每次请求后指针前进轮换账号（真正的 round-robin），串行请求也会依次使用不同 Token；跳过 429 冷却/失效/超并发账号
- **429 按模型冷却**：限流按 `(账号, 模型)` 隔离，仅限流模型受影响，同账号其他模型继续可用；429 响应携带 `Retry-After` 头
- **账号健康管理**：启动并发验证所有 Token（失效自动剔除）、连续瞬时故障 3 次标记失效、成功调用重置失败计数、冷却到期自动半开探测恢复
- **概览页模型可用矩阵**：每个模型 × 每个 Token 的实时可用状态（可用/限流冷却/失效/验证中），悬停显示冷却倒计时
- **账号轮换三模式**：Token 管理页三态切换（并发/半并发/串行），默认串行；区分正常额度 429 与 ban，premium 被 ban 后停用到下一个北京时间 15:00
- **轮询指针持久化**：当前账号写入 `.env` 的 `CURRENT_TOKENNum`，重启后续轮
- **管理面板增强**：Token 页展示状态徽章/冷却倒计时/最近 429 详情，支持手动轮换、激活指定账号、重新校验全部账号

**改动文件**：`token_rotation.py`（新增）、`codebuff.py`、`app.py`、`admin.py`、`config.py`、前端 `DashboardPage`/`TokenPage`、`tests/test_token_rotation.py`

**验证**：`tests/test_token_rotation.py` 22 个用例通过；全量回归 139 passed（仅 3 个 pre-existing 的 proxy_url 旧测试失败）；端到端实测 round-robin、按模型冷却、半开探测、并发上限全部正常。

### v0.1.1（2026-08-01）— 🐛 修复上游 403 `free_mode_cli_required`

**问题**：直接调用 Freebuff API 时返回 `403 free_mode_cli_required`（"Free mode is only available through the freebuff CLI"），导致所有模型无法使用。

**根因**：上游服务端会校验 chat/completions 请求体中的 system 提示词是否为 CLI 的真实 Buffy 提示词（`"You are Buffy, the strategic coding assistant...Freebuff..."`）。旧版使用伪造的 `"You are Buffy. [System Override...]"` 前缀，被服务端识别为非 CLI 请求后拒绝。

**修复**：

- 新增 `freebuff2api/buffy_prompt.py`：从 freebuff CLI 二进制（v0.0.135）提取的真实 Buffy 系统提示词模板，日期动态生成
- `openai_compat.py`：`normalize_chat_messages` 始终在第一条 system 消息注入真实 Buffy 提示词（用户自定义 system 内容追加在其后，不再覆盖）
- `codebuff.py`：chat 请求 User-Agent 版本 `ai-sdk/provider-utils/3.0.20` → `3.0.25`（与 CLI 一致）

**验证**：端到端实测 session → agent-runs → chat/completions 返回 200 + SSE 流式响应，测试套件零回归。

> **⚠️ 测试现状（2026-08-01）**：当前 `pytest tests/` 因 `tests/test_new_features.py`（旧脚本，模块级断言）收集失败（1 error、0 collected），排除后其余 120 个用例中 5 个失败、115 个通过。详见 [progress.md](progress.md)「2026-08-01 全面代码审查」章节。


## 🚀 快速开始

### 环境要求

- Python 3.11–3.13（`.python-version` 锁定 3.13，3.14 已实测通过）
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
# 多账号：逗号分隔多个 Token，自动轮询切换
FREEBUFF_TOKEN=token1,token2,token3

# 🔐 API Key（必填）
# 用于调用 /v1/* 接口的访问密钥
FREEBUFF_API_KEY=sk-your-api-key

# 🛡️ 管理员密钥（必填）
# 用于登录管理面板
FREEBUFF_ADMIN_KEY=sk-admin

# 🔁 账号轮换模式（可选，默认 balanced）
# throughput   = 所有账号同时扇出，吞吐最大，风险最高
# balanced     = free 扇出；premium 同时只用 1 个账号，正常额度耗尽才轮换
# conservative = free 也只用第 1 个账号；premium 轮换同上
FREEBUFF_ROTATION_MODE=balanced

# 📦 请求体大小上限（可选，默认 307200 = 300KB）
# 超过该大小直接 413，避免把上游打崩
FREEBUFF_MAX_REQUEST_BODY_BYTES=2097152
```

> 💡 当前轮询账号由系统自动写入 `.env` 的 `CURRENT_TOKENNum`（无需手动配置），重启后从该账号继续轮换。

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

### 方式三：Docker 部署（暂不可用）

> ⚠️ 仓库暂未提供 `Dockerfile`，暂不支持 `docker build`。需要容器化部署时，请先用方式二跑通本地/服务器部署，或自行编写 Dockerfile（推荐 `python:3.13-slim` + `uvicorn freebuff2api.app:app`）。

---

## 📚 API 文档

### OpenAI 兼容接口

#### 获取模型列表

```http
GET /v1/models
Authorization: Bearer YOUR_API_KEY
```

> 返回每个模型的 `context_window` / `max_output_tokens` / `input_modalities` / `output_modalities`(Anthropic Models API 兼容字段),Claude Code 等客户端据此自适应钳制上下文与输出上限,避免因 `max_tokens` 超上游免费层上限(32,768)导致空响应。

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
| 📊 **概览** | 服务状态、Token 数量、模型数量、部署环境；**模型可用矩阵**（每个模型在每个 Token 上的可用状态与冷却倒计时） |
| 🔑 **Token 管理** | 添加/编辑/删除 Freebuff Token，验证有效性，**手动轮换/激活指定账号/批量校验**，状态徽章与冷却倒计时 |
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
| `FREEBUFF_TOKEN` | ✅ | - | Freebuff Token（多个用逗号分隔；兼容 `CODEBUFF_TOKEN`） |
| `FREEBUFF_API_KEY` | ✅ | - | API 访问密钥（兼容 `OPENAI_API_KEY`） |
| `FREEBUFF_ADMIN_KEY` | ✅ | `sk-admin` | 管理面板密钥（⚠️ 必须修改） |
| `FREEBUFF_API_BASE_URL` | ❌ | `https://www.codebuff.com` | 上游 API 地址（兼容 `CODEBUFF_BASE_URL`） |
| `ZEROCLICK_BASE_URL` | ❌ | `https://zeroclick.dev` | 广告提供商 Zeroclick 上游地址 |
| `FREEBUFF_TIMEOUT` | ❌ | `60` | 请求超时（秒） |
| `FREEBUFF_PROXY_ENABLED` | ❌ | `false` | 是否启用代理 |
| `FREEBUFF_PROXY_TYPE` | ❌ | `socks5` | 代理协议（http/https/socks5/socks5h） |
| `FREEBUFF_PROXY_HOST` | ❌ | - | 代理主机 |
| `FREEBUFF_PROXY_PORT` | ❌ | `1080` | 代理端口 |
| `FREEBUFF_PROXY_USERNAME` | ❌ | - | 代理用户名（可选） |
| `FREEBUFF_PROXY_PASSWORD` | ❌ | - | 代理密码（可选） |
| `FREEBUFF_DEBUG` | ❌ | `false` | 调试模式（等价 `FREEBUFF_LOG_LEVEL=DEBUG`） |
| `FREEBUFF_LOG_LEVEL` | ❌ | `INFO` | 日志等级 |
| `FREEBUFF_LOG_BODY_CHARS` | ❌ | `2000` | 调试日志中请求/响应体截断字符数（debug 模式默认 0） |
| `FREEBUFF_LOG_COLOR` | ❌ | `true` | 彩色日志（设置 `NO_COLOR` 时默认关闭） |
| `FREEBUFF_ADMIN_LOG_LINES` | ❌ | `1000` | 管理面板内存日志保留条数 |
| `FREEBUFF_HOST` | ❌ | `0.0.0.0` | 监听地址 |
| `FREEBUFF_PORT` | ❌ | `8000` | 监听端口 |
| `FREEBUFF_API_KEYS` | ❌ | - | 多 API Key JSON 配置（替代单一 `FREEBUFF_API_KEY`） |
| `FREEBUFF_MAX_REQUEST_RECORDS` | ❌ | `5000` | 请求记录内存保留上限 |
| `FREEBUFF_ROTATION_MODE` | ❌ | `conservative` | 账号轮换模式：`throughput` / `balanced` / `conservative` |
| `FREEBUFF_MAX_REQUEST_BODY_BYTES` | ❌ | `2097152` | 请求体大小上限（字节，默认 2 MB），超过返回 413 |
| `FREEBUFF_MAX_TOOLS` | ❌ | `50` | 单请求工具数上限，超过只保留前 N 个（降低外来客户端指纹） |
| `FREEBUFF_MAX_MESSAGES` | ❌ | `100` | 消息数上限，超过保留 system + 最近 N 条 |
| `FREEBUFF_EMPTY_STREAM_TIMEOUT` | ❌ | `120` | 空流超时（秒），超过返回明确错误 |
| `FREEBUFF_LOG_STREAM_CHUNKS` | ❌ | `false` | 是否逐块记录 SSE chunk（生产建议 false） |
| `FREEBUFF_SESSION_ID` | ❌ | 随机 | 上游会话 ID（通常自动生成，无需设置） |
| `FREEBUFF_SYSTEM_PROMPT_OVERRIDE` | ❌ | - | 覆盖注入的 Buffy 系统提示词（追加在真实 Buffy 提示词之后） |
| `FREEBUFF_AD_PROVIDERS` | ❌ | `gravity,carbon` | 广告提供商顺序（逗号分隔；上游现已不接受 `zeroclick`） |
| `FREEBUFF_CLIENT_ID` | ❌ | 随机 | 模拟客户端设备 ID |
| `FREEBUFF_TIMEZONE` | ❌ | `Asia/Shanghai` | 模拟客户端时区 |
| `FREEBUFF_LOCALE` | ❌ | `zh-CN` | 模拟客户端语言 |
| `FREEBUFF_OS` | ❌ | `windows` | 模拟客户端操作系统 |

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
│   ├── openai_compat.py   # OpenAI 格式兼容层（注入官方 Buffy 前缀 + end_turn 签名）
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
</p>
