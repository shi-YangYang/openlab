# Spec：功能维护与可用性修正（spec-021）

## 元信息

- **Spec 编号**：`spec-021-usability-fixes`
- **状态**：completed（已完成）
- **创建日期**：2026-08-27
- **关联决策**：`.ai/decisions/2026-08-27-usability-fixes.md`
- **负责人**：协调开发 Agent

## 背景与动机

1. Semantic Scholar 搜索失败，实测根因为官方 Graph API 未认证共享配额触发 **429 Too Many Requests**（非代码回退）；现有降级机制静默吞掉原因，用户只见「搜索失败」。
2. Agent 页消息输入框过矮，长文本输入/查看困难。
3. LLM 配置组模型列表「思考强度」多值输入过窄导致内部换行、行高拉长整页。
4. 搜索页两种搜索模式的命名与提示不直观。

## 目标

- Semantic Scholar 限流可自愈、可选提额、失败原因可见。
- 三处 UI 可用性问题修正。

## 范围

### 包含（In Scope）

- 后端限流重试 + 可选 API Key + fallback 原因透传。
- 前端搜索表单文案与 Tooltip。
- Agent 输入框增高；模型列表思考强度输入加宽（flex 弹性）。

### 不包含（Out of Scope）

- 其他平台的错误处理改造。
- 搜索表单结构重排 / 平台选择交互变化。

## 需求描述

### 功能需求

- FR-1：`SemanticScholarProvider.search` 对 429 与 5xx 及网络异常最多重试 2 次；等待时长优先取响应 `Retry-After` 头（封顶 5s），否则指数退避 1s→2s；仍失败则抛出由聚合器降级。超时总量控制不显著拖慢聚合响应。
- FR-2：新增 `SEMANTIC_SCHOLAR_API_KEY` 环境变量（`config.settings` 注入）：配置后请求附加 `x-api-key` 头以提升官方配额；`backend/.env.example` 补充说明与申请入口注释。
- FR-3：聚合器 `fallbacks` 条目新增可选 `message`：非登录类异常生成简短中文原因摘要（429 → 「官方接口限流(429)，已自动重试仍未恢复」；其他 → 摘要原始错误文本前 120 字符并脱敏）。登录类沿用 need_login/expired 标记不变。
- FR-4：`SearchFallback`（schema 与前端类型）增加可选 `message` 字段；搜索页降级提示行在原有文案后附加该原因。
- FR-5：Agent 页消息输入框 `autoSize` 改为 `{minRows: 4, maxRows: 10}`。
- FR-6：LLM 配置组模型列表单行改 flex 布局：「思考强度」输入弹性伸展（最小约 300px），不再因值多换行而撑高行高；删除按钮固定右侧。
- FR-7：搜索页模式与文案：
  - 两枚模式按钮文字改为「直接搜索」「AI 智能搜索」，各包裹 Tooltip：
    - 直接搜索：把输入内容原样提交给所选平台精确检索。
    - AI 智能搜索：先由 LLM 把研究主题改写成更精准的检索式再搜索（结果下方会展示生成的检索式）。
  - 输入框 label 随模式切换为「搜索关键词」/「研究主题描述」。
  - 占位提示改为直白表述：
    - keyword：`输入标题、关键词或短语，例如 attention mechanism survey`
    - topic：`用一两句话描述你的研究方向或问题，AI 会自动将其改写为更精准的检索式`

### 非功能需求

- NFR-1：`SearchFallback.message` 为可选字段，向后兼容。
- NFR-2：新增测试覆盖重试成功、重试耗尽抛出、API Key 头注入、fallback message 透传。
- NFR-3：`pytest tests -q` 与 `npm run build` 通过。

## 数据结构约定

- `SearchFallback`: `{platform, url, need_login, expired, message?}`（message 可选）。
- 新环境变量：`SEMANTIC_SCHOLAR_API_KEY`（默认空）。

## 依赖与前置条件

- 依赖 spec-013（搜索源抽象与降级框架）。
- Semantic Scholar API Key 为可选增强（无 Key 时依赖重试与降级）。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- 429 时自动重试；仍失败则前端能看到明确的原因文案。
- 配置 API Key 后请求携带该头。
- 其余三项 UI 修正生效。

## 风险与开放问题

- 重试等待期间聚合器整体响应会被该平台拖慢最多约 3 秒（并发下其他平台不受影响）。
