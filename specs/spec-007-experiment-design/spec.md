# Spec：实验设计（spec-007）

## 元信息

- **Spec 编号**：`spec-007-experiment-design`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-experiment-design.md`、`.ai/decisions/2026-08-24-llm-orchestration.md`、`.ai/decisions/2026-08-24-innovation-points.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-004 已能生成创新点，spec-002 已能分析论文。spec-007 在此基础上，基于创新点或论文分析，用 LLM 生成结构化实验方案，为后续 SSH 部署与自动跑实验（spec-008+）提供依据。

## 目标

- 基于创新点生成实验方案。
- 基于论文分析生成实验方案。
- 实验方案包含：假设与目标、数据集与基线、评价指标。
- 数量可配置（1-3，默认 1），输出语言可切换中/英。
- 结果入库 SQLite，前端展示，支持 Markdown 导出。

## 范围

### 包含（In Scope）

- 后端：实验方案生成（创新点/论文两来源，异步 + 进度）、存储、查询、导出接口。
- 前端：生成入口、实验方案结构化展示、数量配置、语言切换、导出。

### 不包含（Out of Scope）

- 实验步骤/流程与预期结果（本轮不做）。
- SSH 部署与跑实验（spec-008+）。

## 需求描述

### 功能需求

- FR-1：基于创新点生成实验方案（输入 innovation_id）。
- FR-2：基于论文分析生成实验方案（输入 arxiv_ids）。
- FR-3：实验方案含假设（hypothesis）、目标（goal）、数据集（datasets）、基线（baselines）、评价指标（metrics）。
- FR-4：生成数量可配置（1-3，默认 1）。
- FR-5：输出语言可切换（zh/en，默认 zh）。
- FR-6：实验方案结果持久化到 SQLite，可查询。
- FR-7：前端结构化展示实验方案。
- FR-8：支持导出实验方案为 Markdown。

### 非功能需求

- NFR-1：LLM 复用现有配置（LangChain + OpenAI 兼容 + 平台预设）。
- NFR-2：密钥安全沿用（不入库、不硬编码、不打印）。
- NFR-3：LLM 结构化 JSON 输出 + pydantic 校验 + 重试，失败记录 error。
- NFR-4：LLM 调用设置超时。

## 数据结构约定

实验方案（JSON）：

```json
{
  "hypothesis": "string",
  "goal": "string",
  "datasets": ["string"],
  "baselines": ["string"],
  "metrics": ["string"]
}
```

生成结果为一组实验方案（JSON 数组）。

存储：`experiments` 表：`id, source_type, innovation_id, arxiv_ids, content, language, status, error, progress, created_at`。

## 后端接口草案

- `POST /api/experiments`（body: source_type[innovation|papers], innovation_id?, arxiv_ids?, count, language）— 生成实验方案（异步 + 进度），返回记录 id。
- `GET /api/experiments/{id}` — 查询实验方案结果（含 progress/status/error/content）。
- `GET /api/experiments/{id}/export` — 导出 Markdown。

## 依赖与前置条件

- spec-004（`innovations` 数据）。
- spec-002（`analyses` 数据）。
- LLM 配置（LangChain + OpenAI 兼容）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 实验方案质量依赖创新点/分析质量与 LLM 能力。
- 结构化 JSON 输出稳定性（用 pydantic 校验 + 重试兜底）。
