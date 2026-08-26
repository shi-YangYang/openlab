# Spec 020 实施计划

## 概览

后端（WS 通道 + 任务化执行 + 压缩 + 导出）与前端（传输层重构 + 交互增强）并行推进有依赖，按 5 个批次串行实施。

## 批次划分

### 批次 1：后端 WS 通道与任务化执行

- `backend/app/agent/agent.py`：
  - `_run_loop` / `run_chat` / `run_approve` 增加可选 `emit`（异步回调）参数：状态、token 分片、tool_call、pending_approval、done、compacted 全部经 emit 推送。
  - 最终回复改用 `llm.astream`：分片即时 emit `token{delta}` 并累积；chunk 的 `usage_metadata` 累计 usage。
- 新建 `backend/app/agent/ws.py`（或并入 sessions 模块旁）：
  - `AgentRunner`：每会话任务管理（asyncio.Task 句柄字典），提供 `start_chat`、`start_approve`、`stop`；单会话运行中重复 chat 回 error。
  - stop → 取消任务 + `set_running(False)` + `set_status("interrupted")` + save_messages（保留部分内容）+ emit stopped。
- `backend/app/main.py`：
  - 新增 `@app.websocket("/api/agent/ws")`：解析 query session_id（可空）；循环收发 JSON；chat/approve 交给 AgentRunner；连接断开不强制取消任务（后台任务继续，重连可接续）。
  - 删除 `POST /api/agent/chat`、`POST /api/agent/approve` 及其 schema 引用（保留 AgentChatRequest 字段结构供 ws 消息解析复用或内联解析）。

### 批次 2：上下文自动压缩

- 新建逻辑置于 `backend/app/agent/compaction.py`（或并入 agent.py）：
  - `should_compact(last_input_tokens, context_length)`：≥80% 判定。
  - `compact_messages(session, llm_builder)`：取 system + 最近 KEEP_RECENT=6 条之外的历史 → 摘要 prompt（要求保留关键结论/文件路径/命令/数据事实）→ 替换为一条摘要 HumanMessage（前缀「[历史摘要]」）→ 返回是否成功。
- `_run_loop` 每次 LLM 调用前检查：命中阈值则压缩（用同一 build_llm 非流式调用），成功后 emit compacted 并落库；异常跳过。
- `context_length` 从 active group 所选模型的 models 元数据读取（经 `get_effective_config` 扩展或在 build_llm 处一并返回 model meta）；取不到按无上限处理。

### 批次 3：会话导出端点

- `backend/app/main.py`：`GET /api/agent/sessions/{id}/export`：
  - 组装 Markdown：`# {title}`、导出时间、逐条 `**user**:` / `**assistant**:` 正文；assistant 关联的 tool_calls 以折叠引用列出（工具名+状态+参数摘要）。
  - 内容经 `_redact_secrets`；`Response` 带 `Content-Disposition: attachment; filename="agent-{id}.md"`。

### 批次 4：前端传输层重构（AgentPage）

- 新建 `frontend/src/hooks/useAgentChannel.ts`：
  - 建立/切换/断线重连 WS（指数退避 ≤5 次）；暴露 send chat/approve/stop 与事件回调集合。
  - 重连成功且此前在 running 时拉一次 REST 详情对齐。
- `frontend/src/components/AgentPage.tsx` 改造：
  - 删除轮询分支与 applyResult 中对 REST 响应的依赖；改为事件驱动：
    - `token` → 最新 assistant 气泡流式追加；
    - `status` → 状态行文案；
    - `tool_call` → 对应气泡追加 toolCalls；
    - `pending_approval` → 打开审批 Modal；
    - `done` → 完整 reply 校准替换 + 更新 usage 显示；
    - `stopped` → 提示已中断；`compacted` → Tag 提示；`error` → message.error。
  - 会话切换时关闭旧连接建立新连接；新建会话流程改经 WS（首条 chat 建 session 后以 session 事件回填 id）。
  - 运行中显示「停止」按钮；审批按钮走 WS。

### 批次 5：复制 / 导出 / 细节

- 消息气泡 hover 显「复制」按钮：navigator.clipboard 写入原始 markdown 文本 + 已复制反馈。
- ReactMarkdown 自定义 `code` 渲染：代码块右上角小复制按钮。
- 头部加「导出 Markdown」：调 `GET /api/agent/sessions/{id}/export` 触发下载。
- `frontend/src/api.ts`：新增 `exportAgentSession(id)`；移除 chat/approve REST 封装（或标记内部不再使用并删除）。`types.ts` 增补导出所需类型。

### 测试与回归

- `tests/test_agent.py`：FakeLLM 实现 `astream` 分片（含 usage_metadata）；断言 token 事件序列、done.reply、usage 累计。
- `tests/test_agent_ws.py`（新）：TestClient `websocket_connect`：建会话→chat→收到 session/status/tool_call/done 序列；运行中发 stop→stopped 且 status=interrupted；运行中重复 chat→error。
- `tests/test_compaction.py`（新）：阈值判定边界（79%/80%/未配置）；压缩后消息替换结构正确；摘要失败跳过。
- `tests/test_agent_export.py`（新）：导出包含双方消息与脱敏；404。
- 既有 test_api.py 中删除对应 REST chat/approve 用例，更新引用。

## 文件清单

### 后端
- `backend/app/agent/agent.py`（astream + emit + 压缩触发）
- `backend/app/agent/ws.py`（新建，AgentRunner）
- `backend/app/agent/compaction.py`（新建）
- `backend/app/reasoning_efforts.py` 不变
- `backend/app/main.py`（WS 端点、export、删旧端点）
- `backend/app/schemas.py`（清理无用请求模型，保留必要）

### 前端
- `frontend/src/api.ts`、`frontend/src/types.ts`
- `frontend/src/hooks/useAgentChannel.ts`（新建）
- `frontend/src/components/AgentPage.tsx`

### 测试
- 上文所列新增/调整文件。

## 验证方式

- 后端：`pytest tests -q`（注意 TEMP 重定向 D:\tmp\pytest）。
- 前端：`npm run build`。
- 手工冒烟：双浏览器标签同时观察流式输出；中途停止；超长对话触发压缩；导出打开核对；审批经 WS 生效。
