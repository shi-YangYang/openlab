# Spec：创新点设计（spec-004）

## 元信息

- **Spec 编号**：`spec-004-innovation-points`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-innovation-points.md`、`.ai/decisions/2026-08-24-llm-orchestration.md`、`.ai/decisions/2026-08-24-paper-analysis.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-002 已能分析论文并做对比综述。spec-004 在此基础上，基于单篇论文分析或多篇对比综述，用 LLM 自动生成科研创新点，为后续实验设计（spec-005）提供输入。

## 目标

- 基于单篇论文分析生成创新点。
- 基于多篇论文对比综述生成创新点。
- 每个创新点包含：标题、描述、创新依据（引用来源论文与空白）、预期贡献。
- 数量可配置（1-10，默认 3），输出语言可切换中/英。
- 结果入库 SQLite，前端展示，支持 Markdown 导出。

## 范围

### 包含（In Scope）

- 后端：创新点生成（单篇/多篇，异步 + 进度）、存储、查询、导出接口。
- 前端：生成入口、创新点结构化展示、数量配置、语言切换、导出。

### 不包含（Out of Scope）

- 可行性/难度评估（本轮不做）。
- 实验设计（spec-005）。
- 创新点的正式验证。

## 需求描述

### 功能需求

- FR-1：基于单篇论文分析生成创新点。
- FR-2：基于多篇论文对比综述生成创新点。
- FR-3：每个创新点含标题、描述、创新依据（引用来源论文与空白）、预期贡献。
- FR-4：生成数量可配置（1-10，默认 3）。
- FR-5：输出语言可切换（zh/en，默认 zh）。
- FR-6：创新点结果持久化到 SQLite，可查询。
- FR-7：前端结构化展示创新点。
- FR-8：支持导出创新点为 Markdown。

### 非功能需求

- NFR-1：LLM 复用现有配置（LangChain + OpenAI 兼容 + 平台预设）。
- NFR-2：密钥安全沿用（不入库、不硬编码、不打印）。
- NFR-3：LLM 结构化 JSON 输出 + pydantic 校验 + 重试，失败记录 error。
- NFR-4：LLM 调用设置超时。

## 数据结构约定

创新点（JSON）：

```json
{
  "title": "string",
  "description": "string",
  "basis": ["string"],
  "expected_contribution": "string"
}
```

生成结果为一组创新点（JSON 数组）。

存储：`innovations` 表：`id, arxiv_ids(JSON 列表), content(JSON 数组), language, status, error, progress, created_at`。

## 后端接口草案

- `POST /api/innovations`（body: arxiv_ids, count, language）— 生成创新点（异步后台 + 进度），返回记录 id。
- `GET /api/innovations/{id}` — 查询创新点结果（含 status/progress/error）。
- `GET /api/innovations/{id}/export` — 导出 Markdown。

## 依赖与前置条件

- spec-002（`analyses`、`reviews` 数据）。
- LLM 配置（LangChain + OpenAI 兼容）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 创新点质量依赖分析/综述质量与 LLM 能力。
- 结构化 JSON 输出稳定性（用 pydantic 校验 + 重试兜底）。
