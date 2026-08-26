# spec-014 平台登录态管理决策

## 决策标题

确定知网/百度学术的登录态管理（spec-014）方案。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-014-platform-login

## 决策

1. **登录方式**：Playwright 打开真实浏览器（headed），用户手动完成平台验证（滑块/安全验证），系统**自动检测登录成功**（URL 跳转/验证页消失）并保存 Cookie。
2. **无登录态搜索**：返回「需登录」提示 + 降级外链（两者都要）。
3. **登录态过期**：搜索遇验证码/失效时标记过期，提示引导重新登录 + 降级外链。
4. **登录态存储**：本地文件（`data/platform_sessions/<platform>.json`，已被 gitignore）。

## 理由

- 知网/百度学术是 JS 反爬 + 验证码，真实浏览器 + 手动验证是唯一稳定途径；保存 Cookie 后可复用。
- 自动检测登录成功（URL 从验证页跳走）比手动确认更顺滑。
- 登录态存本地文件，与 LLM Key、服务器凭据一致，不入库不入 git。

## 影响与后果

- 新增 Playwright 依赖（chromium）。
- 设置页新增两平台登录管理。
- 搜索 provider（cnki/baidu）改为 Playwright + storage_state。
