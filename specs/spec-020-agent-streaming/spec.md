# Spec：Agent 流式传输与交互增强（spec-020）

## 元信息

- **Spec 编号**：`spec-020-agent-streaming`
- **状态**：completed（已完成）
- **创建日期**：2026-08-27
- **关联决策**：`.ai/decisions/2026-08-27-agent-streaming.md`
- **负责人**：协调开发 Agent

## 背景与动机

当前 Agent 存在四类体验硬伤：

1. 对话无流式输出，发送后需等待完整结果，期间靠 2 秒轮询刷新「思考中」状态。
2. 运行中的任务无法停止，跑偏只能等满 `MAX_STEPS`。
3. 消息无法复制、代码块无法复制、会话不能导出留存。
4. 长会话接近模型上下文上限时没有任何处理，最终请求直接超限报错。

## 目标

- Agent 对话全程实时流式呈现（token 级），状态事件实时推送，替代轮询。
- 支持随时中断运行中的任务。
- 提供消息复制、代码块复制与会话导出。
- 上下文接近上限时自动压缩历史，保证对话可持续。

## 范围

### 包含（In Scope）

- WebSocket 通道与事件协议（chat/approve/stop 下行，token/status/tool_call/pending_approval/compacted/done/stopped/error 上行）。
- 移除旧 REST chat/approve 端点；会话 CRUD 保持 REST。
- 任务化执行与取消（interrupted 状态）。
- 上下文自动压缩（阈值触发 + LLM 摘要 + 落库 + 通知前端）。
- 会话导出 Markdown 端点。
- 前端：WS 重连、打字机渲染、停止按钮、审批走 WS、复制按钮、代码块复制、导出按钮。

### 不包含（Out of Scope）

- 正在执行中的单个工具调用的即时打断（取消在步与步之间生效，见风险）。
- 多会话并行运行（同一时刻每会话仅一个任务；跨会话并行为既有行为保留）。
- 消息编辑与重新生成、失败重试、会话搜索。
- 思维链（reasoning_content）展示。

## 需求描述

### 功能需求

- FR-1：新增 `WS /api/agent/ws?session_id=`（参数可空；为空时首条 chat 自动建会话并推 `session` 事件）。事件协议见决策记录。
- FR-2：服务端把 agent 循环改为可携带事件回调的异步任务：每个 `AIMessage` 分片即时推送 `token{delta}`；状态变化推送 `status`；工具完成推送 `tool_call`；危险操作推送 `pending_approval`；结束推送 `done{reply,usage}`。同一会话重复 `chat` 在运行中时回 `error` 事件（对应 409 语义）。
- FR-3：移除 `POST /api/agent/chat` 与 `POST /api/agent/approve`；审批经 WS 的 `approve{}` 触发，继续复用内部 `run_approve`（沿用 pending 中保存的 model/reasoning_effort）。
- FR-4：停止中断：收到 `stop` 取消当前任务；置 `running=false`、`status="interrupted"`，已生成的部分回复与工具记录落库，回 `stopped{}`。列表接口的 status 字段自然携带该值。
- FR-5：上下文自动压缩：
  - 触发：循环内每次调用 LLM 前，最近一次 `input_tokens` ≥ 所选模型 `context_length × 80%` 时执行；模型未配 `context_length` 则不触发。
  - 动作：将「系统提示 + 最近 6 条消息」之外的历史交给 LLM（非流式、小 max_tokens）摘要为一条摘要消息替换原内容；成功后落库并推 `compacted{}`；失败跳过不阻塞。
- FR-6：新增 `GET /api/agent/sessions/{session_id}/export`：返回整段会话 Markdown（标题含会话名与导出时间，逐条 user/assistant，附工具调用摘要），Content-Disposition 附件下载，内容走 `_redact_secrets`。
- FR-7：前端传输层重构：
  - 维护当前会话的 WS 连接；切换会话重连；断线指数退避自动重连并在 UI 给出降级提示；连接期间禁用输入或提示未连接。
  - 打字机式追加 token 渲染到最新 assistant 气泡；`done` 用完整 reply 校准替换。
  - 「发送」「允许/拒绝」改走 WS；运行中显示「停止」按钮。
- FR-8：前端交互增强：
  - 每条消息（user/assistant）hover 显示一键复制（复制 Markdown 原文）并反馈已复制。
  - Markdown 代码块右上角复制按钮。
  - 头部「导出 Markdown」按钮下载当前会话。
  - 收到 `compacted` 后展示一次性轻提示（如 Tag「已压缩早期历史」）。

### 非功能需求

- NFR-1：WS 断线自动重连（指数退避，上限 5 次）；重连后按需拉取一次 REST 详情对齐状态。
- NFR-2：token 统计兼容分片累计：流式各 chunk 的 `usage_metadata` 缺失时按 0，最后以 `done.usage` 为准更新占用显示。
- NFR-3：压缩请求失败/超时不抛错不阻塞主对话（跳过即可）；压缩幂等——同一上下文不反复触发（压缩后 last_input_tokens 显著下降）。
- NFR-4：导出内容不含 API Key 与服务器密码（复用 `_redact_secrets`）。
- NFR-5：移除旧端点后全量测试同步更新；`pytest tests -q` 与 `npm run build` 通过。

## 消息协议约定

| 方向 | type | 载荷 | 说明 |
|---|---|---|---|
| C→S | chat | `{message, model?, reasoning_effort?}` | 发起一轮对话 |
| C→S | approve | `{approve: bool}` | 审批危险操作 |
| C→S | stop | `{}` | 中断当前任务 |
| S→C | session | `{session_id}` | 新建会话后下发 |
| S→C | status | `{text}` | thinking / executing:xxx(第N步) |
| S→C | token | `{delta}` | 回复增量 |
| S→C | tool_call | `{entry}` | 工具执行完成（含参数/结果/状态） |
| S→C | pending_approval | `{tool, args}` | 待审批 |
| S→C | compacted | `{}` | 已压缩历史 |
| S→C | done | `{reply, usage}` | 本轮结束 |
| S→C | stopped | `{}` | 已中断 |
| S→C | error | `{message}` | 错误（含运行中重复提交等） |

## 后端接口草案

- `WS /api/agent/ws?session_id=` —— 对话通道（新）。
- `GET /api/agent/sessions/{id}/export` —— 导出 Markdown（新）。
- 删除：`POST /api/agent/chat`、`POST /api/agent/approve`。
- 保留：sessions CRUD、`GET /api/agent/sessions/{id}`。

## 依赖与前置条件

- 依赖 spec-010~012（Agent）、spec-018/019（配置组与 usage/context_length）。
- LangChain `astream` 可用；项目已有 WebSocket（终端）先例。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- 对话实时逐字显示，工具执行/审批实时推送；轮询删除。
- 运行中可一键停止，状态与部分内容正确落库并可继续对话。
- 接近上下文上限自动压缩并有提示；摘要失败不影响使用。
- 单条消息/代码块可复制；会话可导出 Markdown。
- 后端测试与前端 build 通过。

## 风险与开放问题

- 各平台对 `reasoning_effort` 之外的流式兼容性差异（如某些网关不支持 SSE 分片）：必要时对该组退化为一次性返回（done 直发全文），协议不变。
- 「执行中工具不可打断」是本期明确限制，用户感知为停止有短暂延迟，UI 需文案说明。
- 长历史摘要的质量影响后续回答上下文完整性；以「保留最近 6 条 + 摘要」折中，摘要 prompt 明确要求保留关键结论/路径/文件名等事实。
