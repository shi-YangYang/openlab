# spec-007 汇总：实验设计

> 本文档汇总 spec-007 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-007-experiment-design`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-experiment-design.md`

## 背景与目标

基于创新点（spec-004）或论文分析（spec-002），用 LLM 生成结构化实验方案，为后续 SSH 部署与自动跑实验（spec-008+）提供依据。

## 功能需求清单（FR-1 ~ FR-8，全部完成）

- FR-1：基于创新点生成实验方案（innovation_id）。
- FR-2：基于论文分析生成实验方案（arxiv_ids）。
- FR-3：方案含假设、目标、数据集、基线、评价指标。
- FR-4：数量可配置（1-3，默认 1）。
- FR-5：语言可切换（zh/en）。
- FR-6：结果入库 SQLite 可查询。
- FR-7：前端结构化展示。
- FR-8：导出 Markdown。

非功能：NFR-1 复用 LLM 配置；NFR-2 密钥安全；NFR-3 结构化 JSON + 校验重试；NFR-4 LLM 超时。

## 后端接口

- `POST /api/experiments`（source_type/innovation_id/arxiv_ids/count/language）— 生成（异步 + 进度）
- `GET /api/experiments/{id}` — 查询（含 progress/status/error/content）
- `GET /api/experiments/{id}/export` — 导出 Markdown

## 验收结果

验收标准 AC-1 ~ AC-10 **全部 PASS**（轮次 1）。`pytest` 105 passed，前端 build 通过。

## 使用方式

- 论文库页勾选论文 →「生成实验方案」。
- 创新点历史页某条创新点 →「实验方案」。
- 两者共用 ExperimentModal（数量 1-3、语言切换、进度、展示、导出）。
