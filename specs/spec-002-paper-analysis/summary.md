# spec-002 汇总：论文自动分析

> 本文档汇总 spec-002 从需求、实施、返工到验收的全部结论，替代分散在 `spec.md`、`plan.md`、`acceptance.md` 及各轮验收记录中的临时信息。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-002-paper-analysis`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-paper-analysis.md`、`.ai/decisions/2026-08-24-llm-orchestration.md`

## 背景与目标

对 spec-001 下载的论文进行自动分析，为后续创新点设计提供输入。解析 PDF 全文 → LLM 结构化分析 → 入库 → 前端展示与导出。

## 功能需求清单（FR-1 ~ FR-16，全部完成）

- FR-1：解析已下载论文 PDF 全文（PyMuPDF）。
- FR-2：单篇结构化分析（总结/实验与结果/局限与展望/关键词标签 4 维度）。
- FR-3：输出语言可切换（zh/en）。
- FR-4：批量分析（异步逐篇）。
- FR-5：多篇对比综述（共同主题/差异/研究空白）。
- FR-6：结果入库 SQLite，重复覆盖。
- FR-7：前端单篇详情展示。
- FR-8：Markdown 导出（单篇与综述）。
- FR-9：分析进度/状态展示。
- FR-10：失败记录具体原因（error 字段）。
- FR-11：分析前校验已下载，未下载返回明确错误。
- FR-12：单篇详情用模态框（Modal）展示。
- FR-13：单篇分块级进度条（progress + message）。
- FR-14：批量每行独立进度条。
- FR-15：PDF 下载进度条。
- FR-16：综述异步后台 + 进度条。

非功能：NFR-1 复用 LLM 配置；NFR-2 长文本分块；NFR-3 密钥安全；NFR-4 结构化 JSON + 校验重试；NFR-5 LLM 超时（120s）。

## 后端接口

- `POST /api/analyze/{arxiv_id}` — 单篇分析（后台）
- `POST /api/analyze/batch` — 批量分析（后台）
- `GET /api/analyses` / `GET /api/analyses/{arxiv_id}` — 查询分析（含 progress/message/error）
- `GET /api/analyses/{arxiv_id}/export` — 导出单篇 Markdown
- `POST /api/review` — 对比综述（异步）
- `GET /api/reviews/{id}` — 查询综述（含 progress/error）
- `GET /api/reviews/{id}/export` — 导出综述 Markdown

## 验收结果

验收标准 AC-1 ~ AC-19 **全部 PASS**。

| 轮次 | 结果 | 说明 |
|---|---|---|
| 1 | PASS | 核心分析功能（PDF 解析/4 维度/批量/综述/导出），45 个 pytest |
| 2 | PASS | bug 修复：失败原因记录 + 未下载校验 + LLM 超时（AC-12~14），51 个 pytest |
| 3 | PASS | 增强：模态框 + 全部长耗时操作进度条（AC-15~19），56 个 pytest |

- 自动化测试：后端 `pytest` **56 passed**；前端 `npm run build` 通过。
- 真实验证：真实 PDF 提取 39497 字符；真实 LLM 分析成功（模型 `deepseek-v4-flash-0731`）。

## 过程中修复的 bug

1. 「分析选中」静默失败：根因是未下载就分析，且异常被 `except Exception` 吞掉 → 增加 error 记录 + 未下载 409 校验。
2. 分析抽屉闪烁：`handleAnalysisStatus` 未用 `useCallback` 导致引用不稳定 → 用 `useCallback` 包裹。

## 使用方式

1. `.\start.ps1` 启动（后端 8001、前端 5174）。
2. 搜索 → 下载论文 → 点「分析」（模态框）或「分析选中/全部」（批量）。
3. 分析/下载/综述均有进度条；失败会显示具体原因。
4. 对比综述：勾选 ≥2 篇后点「对比综述」。

## 遗留问题（非阻塞）

1. `App.tsx` 中状态变量仍命名 `drawerOpen`（实际控制 Modal），纯命名遗留。
2. 前端构建产物 chunk 偏大（~1.17 MB，gzip ~371 KB）——性能告警。
3. PDF 文本提取质量受双栏/公式/扫描件影响；长文本经分块+合并处理。
