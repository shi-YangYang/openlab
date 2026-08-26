# Spec：浏览器交互式终端（spec-016）

## 元信息

- **Spec 编号**：`spec-016-web-terminal`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-web-terminal.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-008 实现了 SSH 连接管理、代码部署与监控，服务器详情页提供了「环境配置」的单次命令执行。但科研实验常需要交互式操作（conda 环境、vi 编辑、长驻进程、nvidia-smi 实时刷新等），单次命令执行无法满足。此前「Web 终端」曾留待 spec-010，但 spec-010 做成了 Agent 核心，终端一直未落地。spec-016 补上浏览器内到远程服务器的交互式终端。

## 目标

- 浏览器内交互式终端，支持颜色、光标、tab 补全等完整 TTY 体验。
- SSH 到远程服务器（复用 `servers.json` 凭据）。
- 终端窗口 resize 同步到远端 PTY；连接失败/断开给出清晰提示并释放资源。

## 范围

### 包含（In Scope）

- 后端 SSH 交互式终端（paramiko `invoke_shell`）。
- 前端 xterm.js 终端组件（连接、输入、resize、断开、错误提示）。
- 服务器详情页「终端」区块（SSH 终端）。
- WebSocket 会话生命周期管理（断开释放 channel）。

### 不包含（Out of Scope）

- 本地 shell 终端（留待后续 spec）。
- 多标签终端、终端会话持久化 / 断线重连恢复。
- 终端录制 / 回放。
- 多用户权限体系（个人自用）。
- SFTP 文件管理 GUI（已有部署上传功能）。

## 需求描述

### 功能需求

- FR-1：后端新增 WebSocket 端点 `WS /api/servers/{server_id}/terminal`，建立到该服务器的 paramiko 交互式 shell（`invoke_shell`，PTY），双向转发输入/输出；server_id 不存在或连接失败时关闭连接并回传错误信息。
- FR-2：终端尺寸同步：客户端发送 resize 消息（cols/rows），服务端同步到远端 PTY（`channel.resize_pty`）。
- FR-3：前端引入 `@xterm/xterm` + `@xterm/addon-fit`，实现可复用 `Terminal` 组件：建立 WebSocket、键盘输入回传、输出渲染、窗口 fit 与 resize、连接状态/错误展示、断开清理。
- FR-4：服务器详情页新增「终端」区块：打开到当前服务器的交互式终端。
- FR-5：WebSocket 断开（前端关闭、后端异常、SSH 掉线）时，后端释放对应 paramiko channel，避免泄漏。

### 非功能需求

- NFR-1：WebSocket 用 FastAPI 原生支持，不新增后端 WebSocket 框架（`uvicorn[standard]` 已含）。
- NFR-2：凭据安全：SSH 终端复用 `servers.json`，不新增明文暴露；日志不输出密码/私钥。
- NFR-3：每个 WebSocket 连接独立会话；服务端读写用异步转发，避免阻塞事件循环。
- NFR-4：终端输入输出按 UTF-8 解码（`errors=replace`），异常字符不乱码不崩溃。
- NFR-5：`vite.config.ts` 的 `/api` 代理开启 `ws: true`，透传 WebSocket。

## 消息协议约定

- 客户端 → 服务端：文本消息 = 键盘输入；JSON 消息 `{"type":"resize","cols":N,"rows":N}` = 终端尺寸调整。
- 服务端 → 客户端：文本消息 = 终端输出；错误时发送 JSON `{"type":"error","message":"..."}` 后关闭连接。

## 后端接口草案

- `WS /api/servers/{server_id}/terminal` — SSH 交互终端。

## 数据结构约定

- 复用现有 `servers.json` 结构（spec-008），无新增数据结构。
- 不持久化任何终端配置。

## 依赖与前置条件

- 后端：paramiko（已有）、`websockets`（随 `uvicorn[standard]` 已有）。
- 前端：新增 `@xterm/xterm`、`@xterm/addon-fit`。
- 依赖 spec-008（服务器凭据与 SSH 封装）。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- SSH 终端能连上服务器并交互执行命令（含 vi/tab 补全/颜色），resize 生效。
- 断开后后端资源释放；连接失败有清晰提示。
- 前端 build 通过，后端全量测试通过。

## 风险与开放问题

- 不同 shell（bash/zsh 等）的 prompt 与转义序列差异，需在 UTF-8 + `errors=replace` 下容错。
- WebSocket 与前端 Vite 代理需正确配置（`ws: true`），否则本地开发连接失败。
- 长驻进程（如训练）会长期占用连接，需保证断开时能终止远端进程。
