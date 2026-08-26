# spec-020 Agent 流式传输与交互增强决策

## 决策标题

确定 Agent 流式传输的通道选型与事件协议、停止中断机制、以及上下文自动压缩策略。

## 元信息

- **日期**：2026-08-27
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-020-agent-streaming

## 背景与问题

1. Agent 对话目前是一次性返回完整结果，期间前端靠 2 秒轮询假装实时，体验差。
2. 运行中的任务无法中途停止，跑偏只能等满 20 步。
3. 无消息级复制、代码块复制与会话导出。
4. 长会话接近模型上下文上限时没有任何处理，最终请求会超限报错。

## 备选方案

- **方案 A：WebSocket 双向通道** —— 服务端主动推送 token/状态/审批事件，客户端经同一连接发送 chat/approve/stop；项目已有 WebSocket 先例（终端）。
- **方案 B：SSE 单向推送 + 保留 REST** —— 只能服务端→客户端单向，approve/stop 仍需额外 HTTP 往返，且断线管理与轮询残留逻辑更碎。

## 决策

1. **通道**：采用 WebSocket（`WS /api/agent/ws`，可选 `session_id` 参数）；移除旧的 `POST /api/agent/chat` 与 `/approve` REST 端点，避免双通道并存。会话增删改查仍走 REST。
2. **事件协议**：
   - 客户端→服务端：`chat{message, model?, reasoning_effort?}`、`approve{approve}`、`stop{}`
   - 服务端→客户端：`session{session_id}`、`status{text}`、`token{delta}`、`tool_call{entry}`、`pending_approval{tool,args}`、`compacted{}`、`done{reply,usage}`、`stopped{}`、`error{message}`
3. **停止中断**：每个会话同一时刻仅允许一个运行任务；收到 `stop` 即取消当前 asyncio 任务，`running=false`、`status=interrupted`，已生成的部分回复保留入库。注：取消在「步与步之间」生效，正在执行的单个工具会先执行完，此限制写入文档。
4. **上下文压缩**：每次调用 LLM 前，若最近一次 `input_tokens` ≥ 所选模型 `context_length`×80%，则把「系统提示 + 最近 6 条」之外的历史交给 LLM 摘要成一条摘要消息替换，落库并向客户端推 `compacted` 事件；摘要失败则跳过压缩不阻塞对话。模型未配置 `context_length` 时按无上限处理、不触发。
5. **复制/导出**：单条消息一键复制（Markdown 原文）、代码块右上角复制、会话导出 Markdown（后端 `GET /api/agent/sessions/{id}/export`，复用脱敏逻辑）。

## 理由

- 审批与停止本质是双向交互，WebSocket 一条连接解决推送+下发，且与终端实现一致，心智统一。
- 取消用 asyncio 任务取消即可，不需要进程级信号，复杂度最低。
- 压缩以 OpenRouter/OpenAI 惯例取 80% 阈值，「系统提示+最近几轮保留、其余摘要」是社区通用做法，成本一次小请求。

## 影响与后果

- 后端 agent 循环从 `ainvoke` 改造为支持事件回调的任务化执行；会话状态新增 `interrupted` 取值。
- 前端 AgentPage 传输层重构：删轮询，改长连接驱动（含断线重连）；新增复制/导出/停止 UI。
- 测试面扩大：需要伪造可流式的 LLM（astream 分片）与 WS 集成测试。
