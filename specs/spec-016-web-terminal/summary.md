# Spec 016 总结

## 元信息

- **Spec 编号**：`spec-016-web-terminal`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-web-terminal.md`

## 目标

在浏览器内提供到远程服务器的交互式终端（SSH），支持完整 TTY 体验（颜色、光标、tab 补全、交互程序），并同步终端尺寸到远端 PTY。

## 技术栈

- 后端：FastAPI 原生 WebSocket + paramiko `invoke_shell`（PTY）。
- 前端：`@xterm/xterm` + `@xterm/addon-fit`。
- 代理：`vite.config.ts` 的 `/api` 代理开启 `ws: true`。

## 需求清单

- FR-1：`WS /api/servers/{server_id}/terminal`，paramiko 交互式 shell 双向转发。
- FR-2：resize 消息（cols/rows）同步到远端 `channel.resize_pty`。
- FR-3：可复用 `Terminal` 前端组件（连接/输入/resize/状态/清理）。
- FR-4：服务器详情页「终端」区块。
- FR-5：断开时释放 paramiko channel，防泄漏。
- NFR：异步转发不阻塞事件循环；UTF-8(errors=replace)；错误经 `ssh._redact` 脱敏。

## 接口

- `WS /api/servers/{server_id}/terminal` — SSH 交互终端。
- 消息协议：文本 = 输入/输出；JSON `{"type":"resize","cols":N,"rows":N}` = 尺寸调整；`{"type":"error","message":"..."}` = 错误。

## 验收结果

- 实施 Agent：后端 `pytest tests -q` → **243 passed**（基线 235 + 新增 8）；前端 `npm run build` 通过。
- 验收 Agent：AC-1 / AC-2 / AC-3 / 回归 全部 **PASS**；安全核查 PASS（无硬编码密钥、错误脱敏、改动范围仅限 spec-016 相关文件）。
- 观察项（不阻塞）：依赖真实 SSH 服务器的交互验证（vi/top/颜色、真实 resize、SSH 掉线重连）需人工冒烟；`ssh._redact` 不脱敏私钥内容（既有约定，非本次引入）。

## 决策引用

- `.ai/decisions/2026-08-26-web-terminal.md`：本次只做 SSH 终端（本地 shell 留待后续 spec）；交互式长连接 + xterm.js。

## 使用方式

1. 配置一台 SSH 服务器（`data/servers.json`，见 spec-008）。
2. 进入「服务器」→ 某服务器「详情」，页面底部「终端」区块即开即用。
3. 断开/重连由组件「断开/重连」按钮控制；关闭页面自动释放连接。

## 遗留问题

- 本地 shell 终端（后续 spec）。
- 多标签终端、会话持久化 / 断线重连恢复、终端录制回放（未纳入本次范围）。
