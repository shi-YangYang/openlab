# spec-010 汇总：Agent 核心

> 本文档汇总 spec-010 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-010-agent-core`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-agent-core.md`

## 背景与目标

把 spec-001~009 的后端能力封装成 LLM 工具，构建 agent 循环，让 LLM 自主编排执行科研全流程，这是项目成为「Agent 框架」的关键。

## 功能需求清单（FR-1 ~ FR-9，全部完成）

- FR-1：封装 13 个工具（文献 4 + 分析 4 + 服务器 5）。
- FR-2：agent 循环（LLM 推理 → 调工具 → 观察 → 直到最终回答）。
- FR-3：任务式 + 对话式交互。
- FR-4：会话管理（内存 session）。
- FR-5：`POST /api/agent/chat`。
- FR-6：前端 Agent 页面。
- FR-7：工具调用日志。
- FR-8：危险命令确认（run_command/deploy_code 暂停 + 待确认）。
- FR-9：`POST /api/agent/approve`（确认执行/拒绝跳过）。

非功能：NFR-1 复用 LangChain；NFR-2 密钥安全；NFR-3 慢工具超时保护。

## 后端接口

- `POST /api/agent/chat`（session_id?, message）
- `POST /api/agent/approve`（session_id, approve）

## 验收结果

验收标准 AC-1 ~ AC-11 **全部 PASS**（轮次 1）。`pytest` 152 passed，前端 build 通过。

## 使用方式

- 顶部「Agent」页：给任务目标或对话，agent 自主调用工具完成；危险命令需确认。

## 遗留（后续 spec-011 处理）

- LLM 回复 Markdown 未渲染。
- 会话仅内存（重启丢失），无会话列表/管理。
- 对话框 UI 需优化。
