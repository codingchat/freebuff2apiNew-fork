
## 2026-08-01 - Task: 账号轮询增强 — round-robin + 模型可用矩阵 + 优化 1-6

### What was done
在已迁移的账号轮询基础上，按用户要求增强：
1. **真正的 round-robin**：每次请求后指针前进，串行请求也轮换账号（验证：6 次 reserve → 0,1,2,0,1,2），跳过 busy/超并发/blocked/invalid
2. **按模型冷却（优化①）**：429 冷却按 (账号, 模型) 记录，仅限流模型受影响；请求按目标模型过滤
3. **成功重置失败计数（优化②）**：acquire_session 成功即 reset_failures
4. **半开探测（优化③）**：冷却到期账号后台探测，成功→active、失败→重新冷却 30s
5. **负载均衡（优化④）**：round-robin 顺序轮换 + last_used 记录
6. **精确唤醒（优化⑤）**：半开探测/解封完成 notify_all 唤醒等待者
7. **每账号并发上限（优化⑥）**：busy 布尔改 active_requests 计数 + FREEBUFF_ACCOUNT_CONCURRENCY 配置
8. **概览页模型可用矩阵**：/admin/api/overview 新增 model_availability（每模型×每账号状态），DashboardPage 新增"模型可用情况"表格卡片

### Testing
- pytest tests/test_token_rotation.py：22 个用例全部通过（新增 4 个按模型冷却/矩阵/重置计数用例）
- 全量回归（排除已知问题的 test_new_features.py）：139 passed，仅 3 个 pre-existing 失败（test_config.py 的 proxy_url 旧字段）
- 端到端验证：round-robin 串行轮换、按模型冷却、并发上限、成功重置计数、半开探测 全部正常

### Notes
改动文件：
- freebuff2api/token_rotation.py (修改) — 按模型冷却 (_blocked_until 键=(index,model))、model_availability 矩阵、mark_success、账号级聚合查询
- freebuff2api/codebuff.py (修改) — round-robin、active_requests 并发计数、半开探测 (_maybe_trigger_half_open_probes/_half_open_probe)、handle_error 带 model
- freebuff2api/app.py (修改) — _handle_upstream_error 带 model，6 处调用点传模型
- freebuff2api/config.py (修改) — max_concurrency_per_account + FREEBUFF_ACCOUNT_CONCURRENCY
- freebuff2api/admin.py (修改) — overview 返回 model_availability
- web/src/types/index.ts、pages/DashboardPage.tsx (修改) — 模型可用矩阵类型与卡片
- freebuff2api/admin_static/ (重新构建) — 新哈希 index-D-HV0ZTP.js
- tests/test_token_rotation.py (修改) — 新增 4 个测试
- .env.example (修改) — FREEBUFF_ACCOUNT_CONCURRENCY

回滚方式：git checkout 相关文件（无 git 提交时用备份）



### What was done
从 freebufferNew 迁移账号轮询与健康管理：逗号分隔的 FREEBUFF_TOKEN 视为多账号，429 限流自动冷却并切换账号、瞬时故障(502/500)计数剔除、启动批量验证、管理面板手动轮换/激活/校验，当前账号指针持久化到 .env 的 CURRENT_TOKENNum。

### Testing
- pytest tests/test_token_rotation.py：18 个用例全部通过
- 全量回归（排除已知问题的 test_new_features.py）：135 passed，仅 3 个 pre-existing 失败（test_config.py 的 proxy_url 旧字段测试，config.py 已废弃该字段，HEAD 即失败，未改动）
- 端到端验证：3 账号初始化/手动轮换/激活/30s 防抖/429 冷却+Retry-After/3 次 502 剔除 全部正常

### Notes
改动文件：
- freebuff2api/token_rotation.py (新增) — RotationState 账号状态机、parse_429_info、CURRENT_TOKENNum 持久化
- freebuff2api/codebuff.py (修改) — CodebuffClient 懒加载 httpx 客户端；CodebuffAccountPool 接入轮询（跳过 blocked/invalid/busy、全冷却等待最早解封、429 即切、502/500 计数）、handle_error/manual_rotate/set_active/validate_accounts/account_statuses
- freebuff2api/app.py (修改) — lifespan 启动 validate_accounts、_handle_upstream_error 接入 6 处异常路径、429 响应 Retry-After 头
- freebuff2api/admin.py (修改) — _rotation_payload、_config_payload 附加 accounts/rotation、新增 POST /admin/api/tokens/rotate|activate/{index}|validate
- tests/test_token_rotation.py (新增) — 18 个单元测试
- tests/test_codebuff_client.py (修改) — 适配懒加载客户端 + proxy 分离字段
- tests/test_admin.py / test_app_messages.py (修改) — patch validate_accounts 避免测试真实请求上游；admin 页面断言匹配新构建产物
- web/src/types/index.ts、lib/api-client.ts、pages/TokenPage.tsx (修改) — 轮询 UI（状态徽章/冷却倒计时/手动控制/429 详情）
- freebuff2api/admin_static/ (重新构建) — 与 freebufferNew 构建产物一致

回滚方式：git checkout freebuff2api/{codebuff,app,admin}.py 并删除 token_rotation.py 及测试改动



### What was done
新增 Anthropic (Claude) Messages API 兼容端点 /v1/messages，实现 Anthropic 格式 ↔ OpenAI 格式双向转换。新增 anthropic_compat.py 模块，修改 app.py、models.py、openai_compat.py、config.py，新增 53 个测试用例。

### Testing
- pytest tests/ 全部 120 个测试通过 (67 原有回归 + 53 新增)，零失败
- 覆盖范围：消息转换、工具调用双向映射、流式/非流式、SSE 编码、错误响应、鉴权校验、参数验证

### Notes
改动文件清单：
- reebuff2api/anthropic_compat.py (新增) — Anthropic 兼容层：消息规范化、上游 payload 构建、非流式累加器、流式状态机、SSE 编码、错误响应
- reebuff2api/app.py (修改) — 新增 /v1/messages 端点 + _check_anthropic_auth 鉴权 + 流式/非流式 handler
- reebuff2api/models.py (修改) — 新增 Anthropic 模型别名 (claude-sonnet-4-20250514 等 → Freebuff 模型)
- reebuff2api/openai_compat.py (修改) — _UPSTREAM_CHAT_KEYS 新增 	op_k；
ormalize_chat_messages 支持 system_prompt 参数实现 Buffy prompt 可配置/可禁用
- reebuff2api/config.py (修改) — 新增 system_prompt_override 字段 + FREEBUFF_SYSTEM_PROMPT_OVERRIDE 环境变量
- 	ests/test_anthropic_compat.py (新增) — 37 个单元测试：消息转换、工具映射、payload 构建、累加器、流状态机、SSE 编码、错误响应
- 	ests/test_app_messages.py (新增) — 16 个端点测试：鉴权、模型校验、参数验证、格式化兼容

回滚方式：从 D:\桌面\freebuff2api-main-backup-20260623-163621 恢复整个项目

## 2026-06-23 - Task: 后台管理完善 — 请求记录 + 多 API Key + 模型限制

### What was done
为 freebuff2api 后台管理新增三大能力：API 请求历史记录（时间/模型/耗时/Tokens）、多 API Key 管理（每个 Key 可独立设置名称、密钥、允许调用的模型）、Key 级模型限制（请求模型不在白名单则返回 403）。同时增强概览页显示实时请求统计。

### Testing
- tests/test_new_features.py：10 项全部通过
- 全模块 Python 编译检查通过
- app 初始化路由注册正常（38 条路由）

### Notes
改动文件：freebuff2api/usage.py (新增)、freebuff2api/usage_store.py (新增)、freebuff2api/config.py (修改)、freebuff2api/app.py (修改)、freebuff2api/admin.py (修改)、freebuff2api/admin_static/index.html (修改)、tests/test_new_features.py (新增)、data/ (新增)

回滚方式：git revert 本次 commit

## 2026-06-24 - Task: PR #3 代码审查与 Bug 修复

### What was done
拉取 main 最新合并 PR #3 (4 个 commit)，逐项审查 8 处改动，发现并修复 1 个 Bug：OpenAI /v1/chat/completions 端点 403 错误误返回 Anthropic 格式。更新 README 更新日志。

### Testing
- pytest tests/ 全部 120 个测试通过

### Notes
改动文件清单：
- freebuff2api/app.py (修改) — 修复 chat_completions 403 错误从 anthropic_error_payload 恢复为标准 OpenAI {"error": {...}} 格式
- README.md (修改) — 新增 2026-06-24 更新日志条目
- progress.md (修改) — 追加本轮任务记录

PR #3 合并内容（来自 qianze0628/main，4 commits）：
- anthropic_compat.py: reasoning_content 往返保留、SSE text block index 动态分配、空 content 守卫、model 名保留
- app.py: /v1/messages Anthropic 错误响应、requested_model 保留、/api/keep-warm 端点
- tests/test_app_messages.py: 错误响应断言适配 Anthropic format
- .vercel/: Vercel 项目配置文件（含 projectId/orgId，建议后续清理）

回滚方式：git revert cca2de3

## 2026-06-24 - Task: 移除 Anthropic 模型别名映射

### What was done
删除 models.py 中的 ANTHROPIC_MODEL_ALIASES 别名表和 _resolve_alias 函数，简化 resolve_model 逻辑。Anthropic /v1/messages 与 OpenAI /v1/chat/completions 统一只认原生模型 ID（deepseek/deepseek-v4-flash 等10个），传 Claude 风格名字直接返回 400。

### Testing
- pytest tests/ 全部 120 个测试通过（test_messages_endpoint_rejects_unknown_model 已同步更新为验证 400）
- 端到端 5 场景验证：短对话、9 轮多轮、20 轮长对话、system prompt、超长 prompt — 全部 200

### Notes
改动文件清单：
- freebuff2api/models.py (修改) — 删除 ANTHROPIC_MODEL_ALIASES 字典和 _resolve_alias 函数，去掉 resolve_model 中的别名分支
- tests/test_app_messages.py (修改) — test_messages_endpoint_accepts_anthropic_alias_model 重命名为 test_messages_endpoint_rejects_unknown_model，断言改为 assertEqual(400)

回滚方式：git revert 本次 commit

## 2026-06-24 - Task: 修复 Anthropic /v1/messages 长对话 tool_calls 500 错误 + admin API Key 页面显示修复

### What was done
修复 Claude Code 调用 /v1/messages 时长对话/多 tool_use 报 500 的问题：将同一 Anthropic assistant 消息中的多个 tool_use 合并为单个 OpenAI assistant 消息的 tool_calls 数组，避免上游因 insufficient tool messages following tool_calls message 拒绝请求。同时修复 admin API Key 列表页面名称和 key 显示顺序混淆的问题。

### Testing
- pytest tests/ 全部 120 个测试通过
- Claude Code 风格 15 条消息含 4 轮 tool_use/tool_result 的非流式请求：200 OK
- Claude Code 风格 5 条消息含工具的流式请求：200 OK，308 个 SSE 事件
- 端到端验证：name 用作标签（备注），key 用作认证凭证——name 传 x-api-key 返回 401，key 传 x-api-key 返回 200

### Notes
改动文件清单：
- freebuff2api/anthropic_compat.py (修改) — 合并同一消息的 tool_use 块为单条 assistant 消息的 tool_calls 数组
- tests/test_anthropic_compat.py (修改) — test_tool_use_block_maps_to_assistant_with_tool_calls 适配新的合并行为（3→2 条消息）
- freebuff2api/admin_static/index.html (修改) — API Key 列表显示顺序：key_prefix 加粗在前（主标识），name 灰色在后（备注标签）

回滚方式：git revert 本次 commit

## 2025-07-30 - Task: 后台管理前端迁移到 React 19 + TypeScript

### What was done
将管理面板从 Vue 3 单文件 SPA 迁移到 React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui 风格组件。参考 kimi2api 项目的技术栈和 UI 设计，全部适配 freebuff2api 后端 API。创建10个管理页面：登录、概览、Token 管理、API Key、运行日志、请求记录、Env 查看、网络检测、模型测试、设置。

### Testing
- `tsc -b && vite build` 零错误，1962 modules transformed
- `node --check admin_static/assets/index-Bt7sv0kt.js` 语法通过
- `python3 -m py_compile admin.py` 语法通过
- `python3 -m py_compile app.py` 语法通过
- Code review 完成：发现并修复路径穿越漏洞和死代码

### Notes
改动文件清单：
- `freebuff2api/admin.py` (修改) — SPA fallback 路由移到文件末尾，添加路径穿越防护
- `freebuff2api/app.py` (修改) — 移除 StaticFiles mount 死代码
- `freebuff2api/admin_static/` (替换) — Vue SPA → React 构建产物
- `web/` (新增) — React 前端完整源码

回滚方式：`git checkout -- freebuff2api/admin.py freebuff2api/app.py && rm -rf web/ freebuff2api/admin_static/`

## 2025-07-30 - Task: 编写 README.md 并推送到新仓库

### What was done
编写详细的 README.md（含 badges、功能列表、部署指南、API 文档、模型列表、FAQ），创建新仓库 https://github.com/t479842598/freebuff2apiNew.git 并推送全部代码。

### Testing
- `git push -u origin main` 成功

### Notes
新仓库：https://github.com/t479842598/freebuff2apiNew
Commit: e90382f

### What was done
优化 API Key 管理页面：key 显示改为前4+****+后4 脱敏格式，新增一键复制完整 key 按钮，使用说明移至列表上方，列表居中显示，每行内联操作按钮（编辑/删除/启用开关）。后端 list_all 改为返回完整 key 供前端复制使用。

### Testing
- Playwright 截图验证：key 脱敏显示、复制按钮、使用说明位置、列表居中、行内操作按钮均符合预期
- 120 个单元测试全部通过

### Notes
改动文件清单：
- freebuff2api/usage_store.py (修改) — list_all 改为 mask=False 返回完整 key
- freebuff2api/admin_static/index.html (修改) — key 脱敏显示+复制按钮+使用说明上移+居中+行内操作+copyApiKey 函数

回滚方式：git revert 本次 commit

---

## 2026-08-01 - Task: 全面代码审查与计划文档修正（plan-review-fix）

### 审查结论（C 系列缺陷清单，只记录不改码）

> 本次为计划文档审查：只修正 README/progress.md，不改任何源码。以下缺陷由后续 `codebase-bugfixes` Spec 按 C 编号承接修复。每条含 位置 / 现象 / 根因 / 解决方案 / 优先级。

#### C-01 `tests/test_new_features.py` 破坏 pytest 收集（P0，阻塞测试）
- **位置**：`tests/test_new_features.py:65`（模块级断言 `assert '请求记录' in content`）
- **现象**：`pytest tests/` → `collected 120 items / 1 error`、0 collected、被中断；报错 `assert '请求记录' in '<!doctype html>...'`（旧版 Vue SPA 页面已迁移为 React，字符串断言失效）
- **根因**：该文件是 2026-06-23 时期旧脚本，用模块级 `assert` 检查 `index.html` 内容，前端迁移 React 19 后 HTML 结构变化导致收集期抛错
- **解决方案**：删除模块级断言/改为 pytest 函数用例，或整体归档该旧脚本；随后再修 5 个失败用例
- **优先级**：P0（阻塞整个测试套件）

#### C-02 `openai_compat.normalize_chat_messages` 重复守卫 + docstring 错位（P2）
- **位置**：`freebuff2api/openai_compat.py:45-56`
- **现象**：函数开头 `if not isinstance(messages, list): return []` 连续出现两次（代码审查可见），docstring 位于首个 return 之后，成为死字符串
- **根因**：历史编辑合并时把 docstring 插到守卫后、且重复粘贴了守卫
- **解决方案**：删除重复守卫，把 docstring 移到函数体首行
- **优先级**：P2（功能等价，仅代码卫生）

#### C-03 `app.py _stream_anthropic_events`：`_ping_loop` 定义未使用（P2）
- **位置**：`freebuff2api/app.py:754-762`（`_ping_loop` 内嵌函数，`_ping_active` 标志在 750/792 行赋值）
- **现象**：`_ping_loop` 定义了但从未被调用/启动，keep-alive 特性实际未生效
- **根因**：实现时定义了生成器但遗漏 `asyncio.create_task` 启动
- **解决方案**：在流式循环前 `asyncio.create_task(_ping_loop())` 并收集 task 于 finally 取消；或删除死代码
- **优先级**：P2

#### C-04 `_stream_openai_chunks` finally 重复记账（P1）
- **位置**：`freebuff2api/app.py:390-393`（`finally` 块无条件 `_record_request(..., "success")`）
- **现象**：上游 CodebuffError 时先记 `error`，`finally` 又记一次 `success`，单次失败请求记两条
- **根因**：`except CodebuffError` 内已记账，`finally` 未加 `if not recorded` 守卫
- **解决方案**：用局部布尔标记是否已记账，`finally` 仅在未记时补记
- **优先级**：P1（数据准确性）

#### C-05 `_stream_anthropic_events` 错误路径只记 success；message_id 恒为 None（P1）
- **位置**：`freebuff2api/app.py:788-794`（`finally` 中 `_record_request(..., "success")` + `_schedule_finalize_run(client, run, None)`）
- **现象**：Anthropic 流式错误路径（CodebuffError）不记 error，统一记 success；`message_id` 参数恒为 None
- **根因**：`except CodebuffError` 只 yield 错误事件未记账，`finally` 无条件记 success；且 Anthropic 流未捕获 message id
- **解决方案**：仿 OpenAI 路径：except 内记 error + 布尔标记；流中捕获 `message.id` 传入 finalize
- **优先级**：P1

#### C-06 `admin.py _probe_url` 不可达 `return response`（P2）
- **位置**：`freebuff2api/admin.py:268`（函数末尾，`except` 之后）
- **现象**：`return response` 在 try/except 全分支 return 之后，永远不可达
- **根因**：重构遗留死代码
- **解决方案**：删除该行
- **优先级**：P2

#### C-07 `logging_config.redact_headers` 未脱敏 `x-api-key`（P0，安全）
- **位置**：`freebuff2api/logging_config.py:143-146`
- **现象**：调试日志打印请求头时，`x-api-key` 明文输出，泄露 API Key
- **根因**：`redact_headers` 仅覆盖 `authorization/cookie/set-cookie`，未含 `x-api-key`
- **解决方案**：`x-api-key` 加入脱敏集合（并覆盖 `x-api-key` 大小写变体）
- **优先级**：P0（安全）

#### C-08 `buffy_prompt.buffy_system_prompt` 用 `%-d` 日期格式（P1）
- **位置**：`freebuff2api/buffy_prompt.py:239`（`now.strftime("%B %-d, %Y")`）
- **现象**：`%-d` 是 GNU/BSD 扩展格式，Windows 的 `strftime` 抛 `ValueError: Invalid format string`；README 声称支持 Windows 部署
- **根因**：用了非跨平台格式
- **解决方案**：改为 `now.strftime("%B %d, %Y").replace(" 0", " ")` 或 `now.strftime("%B").capitalize() + ...` 手工组装
- **优先级**：P1（跨平台兼容）

#### C-09 `admin_static/assets` 残留历史构建（P2）
- **位置**：`freebuff2api/admin_static/assets/`
- **现象**：残留 `index-Bt7sv0kt.js`、`index-CX1RS6tT.js` 等历史构建文件，仅 `index-BoEgPtLg.js` 被 index.html 引用
- **根因**：多次前端构建未清理旧产物
- **解决方案**：构建时清理 assets 目录（如 `rm -rf` 旧文件）
- **优先级**：P2

#### C-10 `/v1/messages` 非流式异常路径一律 500（P1）
- **位置**：`freebuff2api/app.py:731-732`（`_collect_anthropic_message` 异常分支 `status_code=500`）
- **现象**：上游返回 4xx 时 Anthropic 非流式端点仍回 500，不映射 `error.status_code`；OpenAI 路径（app.py:144）已正确映射
- **根因**：实现遗漏 status_code 透传
- **解决方案**：`except CodebuffError` 使用 `error.status_code` 并透传错误体
- **优先级**：P1（协议一致性）

#### C-11 OpenAI 路径消息被 `normalize_chat_messages` 处理两次（P2）
- **位置**：`freebuff2api/app.py:250`（入口 normalize）+ `freebuff2api/openai_compat.py:135`（`build_upstream_payload` 内再次 normalize）
- **现象**：`/v1/chat/completions` 的 messages 先后被 normalize 两次，功能等价但重复注入/拼接
- **根因**：入口 normalize 后 payload 构建又 normalize 一次
- **解决方案**：二选一保留一处，删除另一处调用
- **优先级**：P2

### Testing

- `pytest tests/` 实测（2026-08-01）：**1 error（test_new_features.py 收集失败）、0 collected、被中断**
- `pytest tests/ --ignore=tests/test_new_features.py` 实测：**5 failed、115 passed**（test_admin ×1、test_codebuff_client ×1、test_config ×3）
- 测试现状声明已同步修正：README「测试套件零回归」后补充现状注记，progress.md 历史「120 个全部通过」条目保留为当时记录

### Notes

- 本任务只改文档（README.md / .env.example / progress.md），未改动任何源码
- 环境变量文档已与 `config.py` 对齐：废弃 `FREEBUFF_PROXY_URL`，补全分离代理字段与缺失变量
- Python 版本说明已与 `.python-version`（3.13）/`.venv`（3.14）对齐
- 回滚方式：`git checkout -- README.md .env.example progress.md`
