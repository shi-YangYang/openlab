# 实施计划：论文自动分析（spec-002）

## 任务拆分

1. PDF 全文解析模块（提取文本，复用 spec-001 下载的 PDF）。
2. 分析数据结构与 LLM 结构化分析（单篇，4 维度，中/英）。
3. 存储（`analyses` 表）与分析 API（单篇/批量/状态查询）。
4. 多篇对比综述 API（`reviews` 表）。
5. 前端：分析入口、详情展示、语言切换、状态、Markdown 导出。

## 实施顺序

PDF 解析 → 单篇分析 → 存储 + API → 对比综述 → 前端。

## 涉及文件/模块

- `backend/`（新增 pdf 解析、analysis 模块，扩展 database/main/schemas）。
- `frontend/`（新增分析详情页/组件）。
- `tests/`（新增分析相关测试）。

## 技术要点

- PDF 解析：PyMuPDF（`fitz`）或 pdfplumber。
- LLM 结构化输出：LangChain（`ChatOpenAI` + `with_structured_output` 或 JSON + pydantic 校验），复用 spec-001 配置。
- 长文本：分块 + 摘要/截断策略，控制单次请求 token。
- 存储：`analyses`（arxiv_id UNIQUE，content TEXT 存 JSON，language、status、created_at/updated_at）；`reviews`（arxiv_ids TEXT，content TEXT，language、status、created_at）。
- 异步：批量分析用 BackgroundTasks/队列 + 状态字段（pending/running/done/failed）。
- 接口草案：
  - `POST /api/analyze/{arxiv_id}`（body: language）— 单篇分析
  - `POST /api/analyze/batch`（body: arxiv_ids, language）— 批量分析
  - `POST /api/review`（body: arxiv_ids, language）— 对比综述
  - `GET /api/analyses/{arxiv_id}` — 查询单篇结果
  - `GET /api/reviews/{id}` — 查询综述结果
  - `GET /api/analyses/{arxiv_id}/export` — 导出 Markdown

## 风险与应对

- PDF 文本质量：解析失败/为空时记录失败状态并提示。
- 上下文长度：分块 + 每块摘要后合并。
- JSON 解析失败：pydantic 校验 + 重试 + 降级记录失败状态。
