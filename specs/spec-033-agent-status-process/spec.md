# Spec：Agent 运行状态与过程展示重构（spec-033）

## 元信息

- **Spec 编号**：`spec-033-agent-status-process`
- **状态**：`completed`
- **创建日期**：2026-08-30
- **类型**：中大 Spec（后端状态治理与历史还原 + 前端流式渲染重构）
- **参考**：opencode / codex 的运行状态与过程折叠交互
- **负责人**：协调开发 Agent

## 背景与动机（用户反馈 + 根因）

1. **状态条丑且语义错位**：状态条是独立一行挂在消息列表最底部（`statusRow`），流式输出时悬在已完成消息的 toolbar 下方；"思考中…"在产出文本后仍然显示，观感像卡死。
2. **中间消息与最终回复混排**：一次运行中 Agent 每轮的说明文字与最终回复全部拼进同一个消息块（token 事件无条件 append 到最后一个 assistant turn），无法区分过程与结论。
3. **僵尸运行态**：运行中后端进程重启/崩溃后，DB 残留 `running=1, status='thinking'`，此后每次打开该会话永久显示"思考中…"（正常完成的清理逻辑存在，但无启动恢复）。
4. **历史不一致**：重新打开会话后，中间说明文字与工具调用卡片丢失（`normalize_history` 丢弃带 tool_calls 的 AI 消息与 ToolMessage）。

## 已确认的设计决策（用户拍板）

1. **内联活动指示器**：运行状态内联附着在当前生成消息下方（含耗时），完成立即消失，不再有独立状态行。
2. **完成后自动折叠**：运行中过程内容展开可见，回合完成后自动收进「思考与过程」折叠框，最终回复独立正常显示。
3. **历史也还原**：重新打开旧会话时，中间过程与工具调用卡片完整还原进折叠框。

## 现状（代码事实）

- 前端 `useAgentState.ts`：`token` 事件无条件 append 到最后一个 assistant turn 的 text（跨轮合并）；`tool_call` 追加到同 turn 的 toolCalls；`status` 事件设置 `statusLabel`（"思考中…"/"执行中：xxx"）；`AgentChatMessages.tsx` 列表底部 `{(loading||running) && statusRow}`。
- 后端 `agent.py`：`_set_status_emit()` 在每次 LLM 调用前发 `thinking`、工具执行时发 `executing:<tool>`；正常完成 `finally` 中 `set_running(False)` + `set_status("")`；但**进程崩溃/被杀时无恢复**。
- 持久化：LangChain 消息序列含中间 AI 消息（带 tool_calls）与 ToolMessage，但 `normalize_history()` 丢弃它们，仅输出非空文本 AI 消息 → 历史丢失过程。

## 需求描述

### 1. 僵尸运行态治理（后端）

- FR-1：应用启动时（lifespan）将所有会话的 `running` 置 0、`status` 置空（单进程模型下重启后不可能有真实运行任务；崩溃残留就此消除）。

### 2. 回合结构重构：过程与结论分离（前端流式 + 后端历史）

- FR-2：Turn 数据模型增加 `intermediate?: boolean`。一次 run 的回合切分规则：
  - 每轮 LLM 产出的文本 = 一个文本 turn；
  - 每轮的工具调用 = 该轮文本 turn 之后的工具调用（归属同一 turn 或相邻 turn，实现取其一，但必须保序）；
  - **回合结束时，除最后一轮文本外，此前所有轮次标记 `intermediate=true`**（判据：后面跟着工具调用）；最后一轮纯文本 = 最终回复。
- FR-3：实时流式逻辑改造（`useAgentState`）：
  - `token`：若最后一个 assistant turn 已被工具调用"封闭"（其后已有工具调用），则新建 turn 承接后续文本；否则 append。
  - `tool_call`：将当前 run 中已有且未标记的文本 turn 全部标记 `intermediate=true`（这些轮次产生了后续动作）。
  - `done`：最后一轮文本 turn 保持 `intermediate=false`；触发自动折叠（FR-6）。
- FR-4：历史还原（后端 `normalize_history` 增强）：
  - 输出项扩展：`{role, content, time, model, intermediate, toolCalls}`；
  - `intermediate` 判定：同一条用户消息之后、非最后一条 AI 消息 → true；AI 消息带 tool_calls → true；最后一条纯文本 AI 消息 → false；
  - `toolCalls`：从 AIMessage.tool_calls 与对应 ToolMessage 重建 `[{tool, args, result, status}]`（status 按 ToolMessage 内容推断：正常 done，异常 error——实现从简，无 ToolMessage 或被拒绝时按现有 entry 结构尽力还原）；
  - 带工具调用但文本为空的 AI 消息不再丢弃（输出空 content + toolCalls 的 item），保证工具卡片还原。
- FR-5：历史渲染：按 `intermediate` 分组，最终回复正常渲染（含 spec-030 toolbar），中间内容进折叠框（FR-6），工具卡片与实时样式一致。

### 3. 内联活动指示器（前端，替代 statusRow）

- FR-6：删除列表底部独立 `statusRow`；改为**内联指示器**：
  - 位置：正在流式/执行的最后一条消息气泡下方（小号次要色，克制风格）；
  - 内容：LLM 调用中（未收到首 token）→ `思考中 · Ns`；工具执行中 → `执行中：<tool> · Ns`；token 流式期间不重复显示思考字样（可选极简流式指示，实现取其一）；
  - `Ns` 为该阶段已耗时（秒，实时跳动）；
  - `pending_approval` 时显示 `等待你的确认`；
  - `done`/`error`/`stopped` 后立即消失；
  - 消息列表为空（首轮尚未产出任何内容）时，指示器显示在空区域顶部。
- FR-7：思考强度/压缩提示等其他既有状态元素不变。

### 4. 过程折叠框（前端）

- FR-8：同一 run 的 intermediate 回合渲染进一个 Collapse 折叠框，置于该 run 最终回复的上方：
  - 标题：`思考与过程 · N 步`（N = 折叠的轮次数）；
  - **运行中展开**（过程实时可见，当前活动指示器内联其中）；**done 后自动收起**（用户可再点开，手动展开后不强制再收起）；
  - 框内每轮保留原有渲染（Markdown 文本 + 工具调用卡片），样式弱化（次要色/小号）。
- FR-9：旧会话兼容：历史项无 `intermediate`/`toolCalls` 字段（旧数据）时，按现状逐条渲染，不折叠、不报错。

### 5. 非功能需求

- NFR-1：不引入新依赖。
- NFR-2：WS 协议仅新增字段（status 事件可带阶段起始时间戳或由前端计时，实现取其一），不做破坏性变更。
- NFR-3：spec-030 toolbar、spec-032 审批流、附件、压缩行为不受影响。
- NFR-4：后端 `normalize_history` 变更配单测；前端 build 通过。

## 范围

### 包含（In Scope）

- 后端：启动清理、`normalize_history` 增强（intermediate + toolCalls 重建）。
- 前端：流式回合切分、内联指示器（含计时）、过程折叠框、历史渲染适配。
- 后端单测 + 前端 build。

### 不包含（Out of Scope）

- 思维链（reasoning content）单独流式展示（模型未返回独立 reasoning 字段）。
- 过程内容的搜索/过滤。
- 多 run 并行的折叠分组（单会话单 run 串行现状）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 流式回合切分依赖事件顺序（token/tool_call 交替），实现需处理 `pending_approval` 打断后的恢复（approve 后继续同一 run：封闭状态延续）。
- 耗时计时以前端事件到达时间为准（后端发时间戳更精确，二选一由实施定，spec 不强约束）。
- 旧数据无 intermediate 标志的分组边界（无 runId）按"最后一条 AI 文本为结论、其余为过程"近似还原，可能与实时略有差异，可接受。
