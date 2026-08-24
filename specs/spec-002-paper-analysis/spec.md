# Spec：论文自动分析（spec-002）

## 元信息

- **Spec 编号**：`spec-002-paper-analysis`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-paper-analysis.md`、`.ai/decisions/2026-08-24-llm-orchestration.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-001 已实现从 arXiv 搜索并下载论文（PDF + 元数据入库）。spec-002 在此基础上，对已下载的论文进行自动分析，提取结构化信息，为后续创新点设计（spec-003）提供输入。

## 目标

- 解析已下载论文的 PDF 全文。
- 用 LLM 提取结构化分析（总结、实验与结果、局限与展望、关键词/标签）。
- 支持单篇分析、批量分析、多篇对比综述。
- 分析结果入库，前端展示，支持 Markdown 导出。
- 输出语言可切换中/英。

## 范围

### 包含（In Scope）

- PDF 全文文本解析。
- 单篇结构化分析（4 个维度）。
- 批量分析（异步逐篇，含进度/状态）。
- 多篇对比综述（共同主题、差异、研究空白）。
- 分析结果持久化到 SQLite。
- 前端：分析入口、详情展示、语言切换、状态、Markdown 导出。

### 不包含（Out of Scope）

- 创新点设计（spec-003）。
- 实验设计（后续 spec）。
- 其他数据源（Semantic Scholar 等）。

## 需求描述

### 功能需求

- FR-1：解析已下载论文的 PDF 全文文本（复用 spec-001 的 PDF）。
- FR-2：对单篇论文生成结构化分析，包含：
  - 结构化总结：研究问题/动机、方法、贡献、结论。
  - 实验与结果：数据集、基线、评测指标、关键结果。
  - 局限与展望：局限性、未来工作。
  - 关键词/标签。
- FR-3：分析输出语言可切换（中文/英文），由接口参数控制。
- FR-4：支持批量分析多篇论文（异步逐篇，含进度/状态）。
- FR-5：支持多篇论文对比综述（共同主题、差异、研究空白）。
- FR-6：分析结果持久化到 SQLite，重复分析覆盖更新。
- FR-7：前端展示单篇分析详情（结构化视图）。
- FR-8：支持导出分析结果为 Markdown（单篇与综述）。
- FR-9：展示分析进度/状态。
- FR-10：分析/综述失败时记录具体失败原因（`error` 字段），并在查询结果中返回。
- FR-11：分析前校验论文已下载（PDF 存在）；未下载时返回明确错误（非静默失败），前端给出提示。
- FR-12：单篇分析详情用模态框（Modal）展示，替代抽屉（Drawer）。
- FR-13：单篇分析展示分块级进度条（`progress` 0-100 及提示文案 `message`）。
- FR-14：批量分析时，每篇论文在结果表格中展示独立进度条。
- FR-15：PDF 下载展示进度条（`progress` 0-100）。
- FR-16：对比综述改为异步后台执行并展示进度（`progress` 0-100）。

### 非功能需求

- NFR-1：LLM 复用现有配置（LangChain + OpenAI 兼容 + 平台预设）。
- NFR-2：处理 PDF 长文本（分块/截断，避免超出模型上下文）。
- NFR-3：密钥安全沿用 spec-001（不入库、不硬编码、不打印）。
- NFR-4：LLM 需返回结构化结果（JSON），解析失败时降级处理并记录状态。
- NFR-5：LLM 调用需设置超时，避免单请求无限挂起阻塞整批顺序执行。

## 业务规则

- 分析对象以 `arxiv_id` 唯一标识，重复分析覆盖旧结果。
- 单篇分析依赖 PDF 已下载；PDF 缺失时给出明确提示。
- 输出语言由 `language` 参数（`zh`/`en`）控制，默认 `zh`。

## 数据结构约定

单篇分析结果（JSON）：

```json
{
  "summary": {
    "research_problem": "string",
    "method": "string",
    "contributions": ["string"],
    "conclusion": "string"
  },
  "experiments": {
    "datasets": ["string"],
    "baselines": ["string"],
    "metrics": ["string"],
    "key_results": "string"
  },
  "limitations": "string",
  "future_work": "string",
  "keywords": ["string"],
  "tags": ["string"]
}
```

对比综述结果（JSON）：

```json
{
  "common_themes": ["string"],
  "differences": ["string"],
  "research_gaps": ["string"],
  "summary": "string"
}
```

存储：`analyses` 表（arxiv_id 唯一，content 存 JSON）+ `reviews` 表（arxiv_ids 列表，content 存 JSON）。

进度：`papers`、`analyses`、`reviews` 表新增 `progress` 列（int 0-100）；`analyses` 额外新增 `message` 列（进度提示文案）。下载按字节进度、分析按分块进度、综述按运行/完成进度更新。

## 依赖与前置条件

- spec-001（PDF 下载与元数据）。
- LLM 配置（LangChain + OpenAI 兼容）。
- PDF 解析依赖（如 PyMuPDF）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- PDF 文本提取质量（双栏、公式、图表、扫描件）。
- LLM 上下文长度限制与长文本处理。
- 结构化 JSON 解析失败率。
