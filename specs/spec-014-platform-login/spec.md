# Spec：平台登录态管理（spec-014）

## 元信息

- **Spec 编号**：`spec-014-platform-login`
- **状态**：accepted
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-platform-login.md`
- **负责人**：协调开发 Agent

## 背景与动机

知网/百度学术是 JS 反爬 + 验证码，脚本抓不到结果。spec-014 引入真实浏览器登录态管理：用户在浏览器里手动完成验证，系统保存 Cookie 后复用，从而能搜到这两个平台的结果。

## 目标

- 设置页管理知网/百度学术登录态（状态展示、登录、退出）。
- 登录时打开真实浏览器，用户手动验证，系统自动检测成功并保存 Cookie。
- 搜索复用登录态；无登录态/过期时提示并引导登录 + 降级外链。

## 范围

### 包含（In Scope）

- Playwright 登录流程 + 自动检测登录成功。
- 登录态本地存储与复用。
- 搜索 provider（知网/百度）改造为 Playwright + 登录态。
- 设置页登录管理 UI + 搜索时的登录引导。

### 不包含（Out of Scope）

- 自动过滑块验证码（OpenCV）。
- 其他平台的登录态。

## 需求描述

### 功能需求

- FR-1：设置页展示知网/百度学术登录状态（未登录 / 登录中 / 已登录 / 过期）。
- FR-2：点击「登录」启动 Playwright 真实浏览器打开对应平台，用户手动完成验证。
- FR-3：系统自动检测登录成功（URL 从验证页跳走 / 验证页消失），保存 storage_state 到本地文件。
- FR-4：搜索知网/百度时复用登录态（Playwright + Cookie）抓取结果。
- FR-5：无登录态搜索时返回「需登录」提示 + fallback 外链。
- FR-6：登录态过期（搜索遇验证码/失效）时标记过期，提示引导重新登录 + fallback 外链。
- FR-7：提供「退出登录」，清除登录态。

### 非功能需求

- NFR-1：依赖 Playwright（chromium）。
- NFR-2：登录态文件不入库、不入 git（`data/` 已 gitignore）。
- NFR-3：登录流程带超时（如 5 分钟），超时自动关闭浏览器并标记失败。

## 数据结构约定

- 登录态：`data/platform_sessions/<platform>.json`（Playwright storage_state）。
- 平台状态：`{platform, state: not_logged_in | logging_in | logged_in | expired}`。

## 后端接口草案

- `GET /api/platforms` — 两平台登录状态列表。
- `POST /api/platforms/{platform}/login` — 启动登录（异步，返回登录进行中）。
- `GET /api/platforms/{platform}/status` — 查询登录状态。
- `POST /api/platforms/{platform}/logout` — 退出登录。

## 依赖与前置条件

- Playwright + chromium（`playwright` 包，`playwright install chromium`）。
- spec-013 的搜索源抽象（SearchProvider）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 自动检测登录成功的标记因平台而异，需容错。
- Playwright 浏览器会话的并发与生命周期管理。
- Cookie 有效期短，需定期重新登录。
