# 实施计划：平台登录态管理（spec-014）

## 任务拆分

1. Playwright 集成：登录态管理模块（保存/读取/删除 storage_state）。
2. 登录流程：启动 headed 浏览器 → 轮询自动检测登录成功 → 保存 storage_state → 关闭。
3. 平台状态接口（列表/登录/状态/退出）。
4. 搜索 provider 改造：知网/百度用 Playwright + storage_state，无登录态抛「需登录」，过期抛「过期」。
5. 前端：设置页登录管理 UI + 搜索时的登录引导提示。
6. 测试。

## 实施顺序

登录态模块 → 登录流程 → 状态接口 → provider 改造 → 前端 → 测试。

## 涉及文件/模块

- `backend/app/platforms/`（新增登录态管理 + Playwright 封装）。
- `backend/app/search/cnki.py`、`baidu_xueshu.py`（改用 Playwright）。
- `backend/app/main.py`、`schemas.py`。
- `frontend/src/components/LlmConfigForm.tsx` 或新增 `PlatformLogin` 组件、设置页、api.ts/types.ts。
- `tests/` 新增用例（mock Playwright）。

## 技术要点

- 登录态：`data/platform_sessions/<platform>.json` 存 `storage_state`（cookies + localStorage）。
- 登录流程：`async_playwright().chromium.launch(headless=False)` → 打开平台搜索页（触发验证）→ 后台轮询检测「验证页消失」（URL 不含 `/verify/`、title 不含「验证」）→ 检测到保存 `context.storage_state()` → 关闭浏览器；超时 5 分钟关闭并标记失败。
- 搜索：`new_context(storage_state=...)` 复用 Cookie，导航搜索页，等结果渲染，解析标题/作者/摘要。
- 无登录态：provider 抛「需登录」异常，aggregator 转成 fallback + 附加 need_login 标记。
- 过期：搜索遇验证页，标记 expired 并抛「登录态过期」。
- Playwright 是阻塞 IO，登录/搜索在独立线程/进程执行，避免阻塞 FastAPI 事件循环。

## 风险与应对

- 自动检测登录成功标记不稳定：提供多标记（URL/title）+ 超时兜底。
- 浏览器并发：用锁/单例限制同时登录/搜索。
