# freebuff2api — lrnev 治理上手

本项目使用 **lrnev** 治理（`.lrnev/` 工作区在项目根目录）。

## 每次会话开始（尤其要改代码时）

1. 先调 `lrnev_guide` 了解工作流（或直接看下面的速查）。
2. 调 `project_status`（scene: `01-freebuff2api`）接手当前进度；`governance_map` 看 scene→spec 全景。
3. 需要动手改代码/推进治理时，确认有对应 Spec/Task 并 `task_update(in_progress)`，完成再 `task_update(completed)`。
4. 纯只读/答问题不需要走任何治理流程。

## 项目要点（详见 `.lrnev/PROJECT.md` 与 `.lrnev/ARCHITECTURE.md`）

- 项目：将 Freebuff 免费模型转为 OpenAI `/v1/chat/completions` + Anthropic `/v1/messages` 兼容 API 的网关（FastAPI + httpx），前端为 React 19 管理面板（web/，构建产物在 freebuff2api/admin_static/）。
- 版本：v0.1.1（2026-08-01，修复上游 403 `free_mode_cli_required`）。
- **已知遗留问题**（见 spec `plan-review-fix` 与 Errorbook）：
  - `tests/test_new_features.py`（旧脚本）在 pytest 收集期抛错，导致 `pytest tests/` 0 收集、1 error；另有 5 个用例失败。
  - `openai_compat.normalize_chat_messages` 有重复守卫 + 错位 docstring；`app.py` 有未使用的 `_ping_loop` 死代码；流式结束 finally 重复记账。
  - README 与代码不一致：Docker 部署无 Dockerfile、`FREEBUFF_PROXY_URL` 已废弃（改为分离字段）、环境变量表不全。

## 环境/工作区

- lrnev MCP 由 `~/.pi/agent/bin/lrnev-mcp-ws` 启动，工作区经 `LRNEV_WORKSPACE` 定位（本项目根）。
- 上游默认 `https://www.codebuff.com`；测试用 `.venv/bin/python -m pytest tests/`（当前收集失败，需先修 test_new_features.py）。
