# spec-004 汇总：创新点设计

> 本文档汇总 spec-004 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-004-innovation-points`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-innovation-points.md`

## 背景与目标

基于 spec-002 的单篇分析或多篇对比综述，用 LLM 自动生成科研创新点，为后续实验设计提供输入。

## 功能需求清单（FR-1 ~ FR-8，全部完成）

- FR-1：单篇论文分析生成创新点。
- FR-2：多篇对比综述生成创新点。
- FR-3：每个创新点含标题、描述、创新依据（引用来源与空白）、预期贡献。
- FR-4：数量可配置（1-10，默认 3）。
- FR-5：语言可切换（zh/en）。
- FR-6：结果入库 SQLite 可查询。
- FR-7：前端结构化展示。
- FR-8：导出 Markdown。

非功能：NFR-1 复用 LLM 配置；NFR-2 密钥安全；NFR-3 结构化 JSON + 校验重试；NFR-4 LLM 超时。

## 后端接口

- `POST /api/innovations`（arxiv_ids, count, language）— 生成（异步 + 进度）
- `GET /api/innovations/{id}` — 查询（含 progress/status/error/content）
- `GET /api/innovations/{id}/export` — 导出 Markdown

## 验收结果

验收标准 AC-1 ~ AC-10 **全部 PASS**（轮次 1）。`pytest` 82 passed，前端 build 通过。

## 使用方式

论文库/搜索页勾选论文 →「生成创新点」→ 选择数量与语言 → 查看创新点列表 → 导出 Markdown。
