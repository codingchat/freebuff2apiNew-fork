# Changelog

本项目所有值得记录的变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [SemVer](https://semver.org/lang/zh-CN/)。

## Unreleased

### 新增

- 管理后台移动端适配：新增移动端抽屉导航（原移动端无导航入口），页面标题/工具栏/表单响应式换行，表格与长文本在小屏下完整显示不截断，全局禁用 iOS 自动字号缩放。
- 管理后台统一加载体验：新增品牌加载首屏（`PageLoading`），Token 管理 / Env 查看 / 请求记录 / 运行日志页面首次加载改为骨架屏占位，登录按钮与网络检测加载态统一 spinner。
- 多账号轮询与健康管理：按模型冷却（429 冷却、半开探测自动恢复）、账号失效标记、手动轮换/激活（管理后台 Token 页可见每账号状态）。

### 修复

- 修复上游广告接口 400 报错：上游 `/api/v1/ads` 已移除 `zeroclick` provider（仅接受 `gravity|carbon`），默认广告提供商由 `gravity,zeroclick` 改为 `gravity,carbon`，并同步更新 `.env.example` / README / 测试。
- 修复 `usePolling` 刷新竞态：刷新时旧请求结果不再覆盖新数据。
- 修复上游 403 `free_mode_cli_required`：改用真实 Buffy 系统提示词注入。
- 修复鉴权守卫、网络检测页、Token 页交互问题。
- 延迟关闭账号池，Token 更新不打断进行中的请求。
- 修复前端 lint 错误（`react-hooks` 新规则：渲染期访问 ref / 调用 impure 函数）。

## 0.1.0 - 2026-07-31

### 新增

- 初始版本：将 Freebuff 免费模型转为 OpenAI `/v1/chat/completions` 与 Anthropic `/v1/messages` 兼容 API 的网关。
- React 19 管理后台：概览、Token 管理、API Key、运行日志、请求记录、Env 查看、网络检测、模型测试、设置。
- 多主题支持、请求统计与模型可用矩阵仪表盘。
- 代理配置重构：分离的字段配置、自定义 Logo。
