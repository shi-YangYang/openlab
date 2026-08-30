# Spec：Agent 消息悬浮 Toolbar（spec-030）

## 元信息

- **Spec 编号**：`spec-030-agent-message-toolbar`
- **状态**：`completed`
- **创建日期**：2026-08-30
- **负责人**：协调开发 Agent

## 背景与动机

Agent 聊天区域目前只有悬浮在气泡左/右侧的「复制原文」按钮，且消息时间仅有时:分、不持久化、无模型信息。用户需要：悬浮消息时在下方出现 toolbar，集中展示 模型名、发送时间、复制 操作。

## 目标

鼠标悬浮任意一条消息（用户/AI）时，该消息下方淡入一个 toolbar：

```
[模型名 deepseek-chat]   [2026-08-30 14:30]   [⧉复制]
```

## 范围

### 包含（In Scope）

- 前端：Agent 聊天消息列表（`AgentChatMessages.tsx` + `AgentPage.module.css`）新增悬浮 toolbar；删除旧悬浮复制按钮与气泡内时间。
- 后端：消息持久化补充 时间戳 与 模型名（LangChain `additional_kwargs`），历史接口返回这两个字段。
- 实时路径（WS）：前端本地记录完整时间与当前生效模型名。

### 不包含（Out of Scope）

- 代码块右上角「复制代码」按钮（保留现状）。
- 消息编辑/重发等其他操作。
- 会话列表、输入区等其他 Agent UI。

## 需求描述

### Toolbar 交互与布局（前端）

- FR-1：鼠标悬浮某条消息行时，该消息气泡正下方出现 toolbar（淡入，不遮挡内容）；移出后隐藏。
- FR-2：toolbar 内容顺序固定为：**模型名 → 时间 → 复制按钮**，三项之间有水平间隔（8–12px）。
- FR-3：模型名为纯文本字符串：
  - 用户消息显示发送该条消息时生效的模型名（如 `deepseek-chat`）。
  - AI 消息显示实际生成该回复的模型名。
  - 文本过长时省略号截断，悬浮 tooltip 显示完整模型名。
- FR-4：时间为纯文本，格式 `年-月-日 时:分`（`YYYY-MM-DD HH:mm`）。
- FR-5：复制按钮为**纯 icon**（CopyOutlined，text 型小按钮），悬浮 tooltip「复制」，点击复制该条消息的原始文本内容（沿用现有 `onCopyText(turn.text)`，AI 消息即原始 Markdown）。
- FR-6：两条消息之间预留足够垂直间距（≥ 28px），保证 toolbar 出现时不遮挡下一条消息。
- FR-7：删除现有悬浮在气泡左/右侧的「复制原文」按钮及其样式（`turnCopy` / `copyLeft` / `copyRight`）。
- FR-8：删除气泡内部的时间小字（`bubbleTime` / `assistantTime`）及相关样式。
- FR-9：旧会话消息缺失模型名或时间戳时，对应位置显示占位符 `-`（三项始终展示）。

### 数据与持久化（后端）

- FR-10：Agent 循环持久化消息时，为用户消息与 AI 消息写入 `additional_kwargs`：
  - `ts`：`YYYY-MM-DD HH:MM:SS` 本地时间字符串（用户消息 = 发送时刻；AI 消息 = 回复产生时刻）。
  - `model`：实际模型名（用户消息 = 本次会话请求生效的模型；AI 消息 = `cfg["model"]` 实际调用值）。
- FR-11：`normalize_history` 返回项从 `{role, content}` 扩展为包含 `time`（由 `ts` 格式化为 `YYYY-MM-DD HH:mm`）与 `model`；缺失字段返回 `null`，前端以 `-` 兜底。
- FR-12：实时 WS 路径不强制后端改造：前端在发送/接收 turn 时本地记录完整格式时间与当前生效模型名（数据来源：现有 LLM 配置态）。持久化仍以后端 FR-10 为准（刷新/重载后以历史接口为准）。

## 非功能需求

- NFR-1：不引入新依赖（Ant Design Tooltip/Button + CSS Modules 即可）。
- NFR-2：兼容旧会话数据（无 `ts`/`model` 的消息不报错）。
- NFR-3：前端构建（tsc + vite build）通过，Agent 现有行为（流式、审批、附件、压缩）不受影响。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- LangChain 消息经压缩（`compact_messages`）重建后 `additional_kwargs` 可能丢失：可接受（压缩后旧消息本就被摘要替代），实现时验证不报错即可。
- 用户在发送后切换配置组：实时显示以发送时刻生效模型为准，历史以持久化为准，两者可能不同（预期行为）。
