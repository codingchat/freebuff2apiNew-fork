# 项目交接文档（HANDOFF）

> 更新：2026-08-17 | 分支：`main` | 最新提交：`432ba5a`

## 1. 项目是什么
将 Freebuff/Codebuff 的免费模型（DeepSeek V4 Pro/Flash、Luna、MiniMax M3、GLM 等）转成标准 OpenAI Chat Completions / Anthropic Messages API 的反代服务。

- 仓库：`darkest-x/freebuff2apiNew-fork`
- 技术栈：Python 3.11 + FastAPI + httpx；前端 React 19 + TypeScript + Vite
- 部署：Railway（生产）/ 本地 / Vercel

## 2. 核心架构
- 每个上游账号（`FREEBUFF_TOKEN` 逗号分隔）有两条串行通道：
  - premium 通道 1 条（Pro/Luna/MiniMax/GLM 等）
  - unlimited 通道 1 条（Flash/Mimo）
- 两条通道独立锁，互不阻塞、互不删除；同通道内请求串行复用 session
- 账号池按 `rotation_mode` 选号（throughput / balanced / conservative）
- 动态模型注册表每 6h 从 GitHub/jsDelivr 拉取，本地快照兜底，硬编码表最终兜底

## 3. 额度与 session（官方 0.0.63 确认）
- 扣费按 session 创建计，不是按对话条数
- premium 池：每天 6 次 session，每次约 1 小时（+30min grace）
- 太平洋日重置 = 北京时间 15:00
- session 跨 15:00 不会中断，按自身 expiresAt 存活；15:00 后新建才用新额度
- unlimited 池：Flash/Mimo 不限额，但官方并发上限 3（我们只开 1 条保守）

## 4. 协议对齐（0.0.63）
已对齐官方桌面端：
- session POST/GET/DELETE 带 `x-freebuff-multi-session: 1`
- chat 不发送 `x-freebuff-instance-id` 头
- chat UA：`ai-sdk/openai-compatible/0.0.0-test/codebuff ai-sdk/provider-utils/3.0.25 runtime/bun/1.3.14`
- system prompt 开头：`You are Buffy, the coding agent behind Codebuff...`
- `codebuff_metadata` 字段：`freebuff_instance_id`、`freebuff_multi_session`、`trace_session_id`、`run_id`、`client_id`、`cost_mode`、`freebuff_reasoning_effort`（可选）、`llm_step_number`（每 run 递增）
- `provider`: `{"data_collection":"deny"}`
- `stop`: `["\"cb_easp\""]`
- reasoning_effort：支持模型（Pro/Flash/Luna/Fable/Muse）合法值放行，非法回退默认；不支持模型不发送

## 5. 三个轮换模式
| 模式 | unlimited | premium | ban 后 |
|:---|:---|:---|:---|
| throughput | 全部账号扇出 | 全部账号扇出 | 原行为 |
| balanced | 全部账号扇出 | 全局只 1 个，正常 429 才轮换 | premium 停到下个 15:00 |
| conservative（默认） | 只用第 1 个账号 | 同上 | premium 停到下个 15:00 |

- 正常额度：429 `rate_limited` → 冷却账号/模型，premium 轮换
- 账号 ban：403 / `banned` / `country_blocked` → 标记 invalid，premium 全局停到下个 15:00
- Policy Violation：**只封当前模型**到下个 15:00，不封账号（Luna 官方问题）

## 6. 请求体保护与工具指纹
- `FREEBUFF_MAX_REQUEST_BODY_BYTES` 默认 2097152（2MB）
- `FREEBUFF_MAX_TOOLS` 默认 50（官方桌面约 40，太多 MCP 工具 = 外来客户端指纹）
- 超过工具数上限：只保留前 N 个，注入 `end_turn` 签名，不报错
- 超过请求体：413 `request_body_too_large`，并写入日志

## 7. 已知问题与修复
- `premium_slot_taken`：重启后本地缓存丢失，旧实例占槽。修复：提取 `currentInstanceId` → DELETE 旧实例 → 重试创建
- 空流：先重建同模型 session+run 重试一次；仍失败返回友好错误 + `upstream_message`
- 520：官方上游服务器崩溃（Render），不是模型上下文限制
- Luna Policy Violation：官方已知问题，我们只封模型
- 客户端不压缩上下文：ZCode 等会发 234 个 MCP 工具 + 全量历史；我们靠工具上限 + 请求体上限保护

## 8. 抓包方法（Anything Analyzer）
- Anything Analyzer 已安装：`D:\AppHub\Network\Anything Analyzer\Anything Analyzer.exe`
- 官方 EXE 的 chat/session 请求由 Bun 进程发，不走系统代理
- 正确姿势：Anything Analyzer MITM 代理 + Proxifier 强制 `bun.exe` 走代理
- 已有抓包会话：Anything Analyzer 会话 123

## 9. 恢复上下文检查清单
1. 读本文件
2. 读 `../AGENTS.md`
3. 读 `../SKILL.md`
4. 读 `../TODO.md`
5. 检查 git 分支：`git -C ../freebuff2apiNew-fork status -sb`
6. 检查最新日志：`../log.txt`
7. 官方客户端源码：`/mnt/c/.../orchestrator/orchestrator.js`
8. 跑测试：`cd ../freebuff2apiNew-fork && PYTHONPATH=/home/ovo/workspace/revew/.pipdeps:. python3 -m pytest -q`
