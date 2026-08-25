# Spec：Agent 会话持久化与 UI 优化（spec-011）

## 元信息

- **Spec 编号**：`spec-011-agent-session-ui`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-agent-core.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-010 实现了 Agent 核心，但会话仅存内存（重启即丢）、无会话列表/管理，且 LLM 回复的 Markdown 未渲染、对话框 UI 简陋。spec-011 补齐会话持久化、管理与渲染体验。

## 目标

- 会话持久化到 SQLite，重启后保留。
- 会话列表、新建、删除、重命名（自动生成标题）。
- LLM 回复渲染 Markdown。
- 优化对话框 UI（侧边栏 + 气泡）。

## 范围

### 包含（In Scope）

- 会话持久化（SQLite `agent_sessions` 表）。
- 会话管理接口（列表/新建/重命名/删除）。
- 前端会话侧边栏 + 管理操作。
- Markdown 渲染。
- 对话框 UI 优化。

### 不包含（Out of Scope）

- 长期记忆（向量库/跨会话记忆）。
- 流式输出。

## 需求描述

### 功能需求

- FR-1：会话持久化到 SQLite（messages JSON），重启后保留。
- FR-2：会话列表（侧边栏，按更新时间倒序，显示标题与时间）。
- FR-3：新建会话。
- FR-4：删除会话（带确认）。
- FR-5：会话标题：首次消息自动生成标题（截断），支持手动重命名。
- FR-6：LLM 回复渲染 Markdown（标题/列表/代码块/表格等）。
- FR-7：对话框 UI 优化（会话侧边栏 + 聊天气泡 + 布局）。

### 非功能需求

- NFR-1：密钥安全沿用（不入库、不打印、脱敏）。
- NFR-2：Markdown 渲染防 XSS（用安全渲染库，如 react-markdown）。

## 数据结构约定

`agent_sessions` 表：`id, title, created_at, updated_at, messages(JSON)`。

## 后端接口草案

- `GET /api/agent/sessions` — 会话列表（不含 messages）。
- `POST /api/agent/sessions` — 新建会话，返回 id。
- `PUT /api/agent/sessions/{id}` — 重命名（title）。
- `DELETE /api/agent/sessions/{id}` — 删除会话。
- `POST /api/agent/chat` — 复用，改为持久化 messages、自动标题。

## 依赖与前置条件

- spec-010（agent 核心、chat/approve）。
- 前端新增 markdown 渲染依赖（react-markdown + remark-gfm）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- Markdown 渲染 XSS：用 react-markdown（默认转义 HTML）。
