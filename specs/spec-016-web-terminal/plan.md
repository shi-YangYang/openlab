# Spec 016 实施计划

## 概览

本次改动横跨后端（WebSocket 终端会话 + SSH PTY）与前端（xterm.js 组件 + 服务器详情页）。按依赖顺序分 3 个批次实施，每批完成即可独立验证。

## 批次划分

### 批次 1：后端 SSH 交互终端

- `backend/app/ssh.py`：新增 `open_shell(server)` 返回 paramiko 交互式 channel（`invoke_shell`，默认 PTY），并封装 resize 与读取。
- `backend/app/terminal.py`（新建）：终端会话管理：
  - `ssh_terminal_ws(server_id, websocket)`：建 channel、异步双向转发（输入→channel.send，channel→输出）、处理 resize、断开时关闭 channel。
  - 错误时回传 `{"type":"error","message":...}` 后关闭。
- `backend/app/main.py`：新增 `@app.websocket("/api/servers/{server_id}/terminal")`，复用 `_require_server(server_id)`。

### 批次 2：前端 xterm.js 终端组件

- `frontend/package.json`：新增 `@xterm/xterm`、`@xterm/addon-fit`。
- `frontend/src/components/Terminal.tsx`（新建）：
  - 初始化 `Terminal` + `FitAddon`，挂载到容器，`fit()` 自适应。
  - 建立 WebSocket（`ws(s)://` 按当前协议推导），`onData` 回传输入。
  - 监听窗口 resize → 发送 `{"type":"resize",...}`；`onresize` → `fit()`。
  - 状态展示（连接中/已连接/错误/已断开）与「重连/关闭」按钮；卸载时关闭 socket 与 term。
- `frontend/vite.config.ts`：`/api` 代理加 `ws: true`。
- `frontend/src/api.ts`：新增 `terminalWsUrl(path)` 辅助函数（按 location 协议拼 ws/wss + base）。

### 批次 3：接入服务器详情页

- `frontend/src/components/ServerDetailPage.tsx`：新增「终端」`Card`，内嵌 `<Terminal path={/api/servers/{id}/terminal} />`。

## 文件清单

### 后端
- `backend/app/terminal.py`（新建）
- `backend/app/ssh.py`（新增 open_shell）
- `backend/app/main.py`（新增 WebSocket 端点）

### 前端
- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/src/components/Terminal.tsx`（新建）
- `frontend/src/components/ServerDetailPage.tsx`
- `frontend/src/api.ts`

### 测试
- `tests/test_terminal.py`（新建）：SSH 终端会话创建/输入输出/resize/断开释放、错误处理（mock paramiko）。
- `tests/test_ssh.py`（补充 open_shell 用例，如需）。

## 验证方式

- 后端：`pytest tests -q`。
- 前端：`npm run build`。
- 手工冒烟：按 acceptance.md 逐项验证（真实 SSH 服务器）。
