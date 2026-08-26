# spec-016 浏览器终端决策

## 决策标题

确定浏览器内交互式终端（Web Terminal）的接入方式、传输协议与本地 shell 的实现方案。

## 元信息

- **日期**：2026-08-26
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-016-web-terminal

## 背景与问题

此前 `.ai/decisions/2026-08-24-server-detail.md` 将「Web 终端」留待 spec-010，但 spec-010 实际做成了 Agent 核心，终端功能一直未落地。现补做：用户需要能在浏览器里开一个交互式终端，既连远程服务器（复用 spec-008 的 `servers.json` 凭据），也能开本地 shell。

## 备选方案

- **方案 A：交互式长连接（WebSocket + PTY）** —— 实时双向收发，支持光标/颜色/vi/tab 补全等完整 TTY 体验，需新增前端 xterm.js 与后端 WebSocket。
- **方案 B：单次命令执行（复用现有 `POST /exec`）** —— 零新依赖，但无交互，体验差。

## 决策

1. **连接目标**：本次只做 SSH 到远程服务器（paramiko `invoke_shell`）；本地 shell 留待后续 spec。
2. **传输**：交互式长连接，FastAPI 原生 WebSocket（`uvicorn[standard]` 已含 websockets）。
3. **前端渲染**：xterm.js（`@xterm/xterm` + `@xterm/addon-fit`）。
4. **SSH 终端**：`WS /api/servers/{server_id}/terminal`，用 paramiko `invoke_shell` 建立 PTY，双向转发，支持 resize（`channel.resize_pty`）。

## 理由

- 交互式终端是「把实验跑到服务器」的关键一环，单次命令执行无法替代（conda 环境交互、vi 编辑、长驻进程）。
- paramiko 已是既有依赖，`invoke_shell` 天然支持 PTY，无需额外原生依赖即可落地。
- xterm.js 是业界标准终端模拟器，生态成熟、MIT 许可，与项目许可证兼容。

## 影响与后果

- 后端新增 WebSocket 端点与终端会话管理（每连接独立，断开即释放 channel，防泄漏）。
- 前端新增 xterm.js 依赖；服务器详情页新增「终端」区块。
- 需在 `vite.config.ts` 的 `/api` 代理加 `ws: true` 以透传 WebSocket。
