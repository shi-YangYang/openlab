# Spec：多平台搜索与本地 PDF 上传（spec-013）

## 元信息

- **Spec 编号**：`spec-013-multi-source-upload`
- **状态**：accepted
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-multi-source-upload.md`
- **负责人**：协调开发 Agent

## 背景与动机

当前搜索仅限 arXiv，且用户无法把自己已有的 PDF 导入论文库。spec-013 增加多平台搜索（Semantic Scholar、百度学术、知网）与本地 PDF 上传，并支持按平台选择搜索范围。

## 目标

- 论文库支持上传本地 PDF，提取元数据经用户审查/修改后回填，并可继续完整分析。
- 搜索支持多平台（arXiv / Semantic Scholar / 百度学术 / 知网），可选全选或部分。
- 无 API 平台爬虫失败时降级为外链跳转。

## 范围

### 包含（In Scope）

- 本地 PDF 上传 + 元数据提取 + 回填 + 可选分析。
- 搜索源抽象与多平台聚合。
- Semantic Scholar API 接入。
- 百度学术/知网爬虫（失败降级外链）。
- 搜索表单与 LLM 工具的 platform 多选参数。

### 不包含（Out of Scope）

- 知网全文下载（版权受限）。
- 登录/验证码处理（爬虫失败即降级外链）。

## 需求描述

### 功能需求

- FR-1：论文库页支持上传本地 PDF（文件选择器）。
- FR-2：上传后解析 PDF 文本（PyMuPDF），用 LLM 提取元数据（标题、作者、摘要、日期）。
- FR-3：提取的元数据在可编辑表单中展示，用户审查/修改后确认才保存（必须有审查环节，不直接入库）。
- FR-4：确认后元数据入库 papers 表并显示在论文库表格。
- FR-5：上传后可选用 spec-002 做完整 4 维度分析（复用 analyze）。
- FR-6：搜索源抽象（SearchProvider），实现 arXiv / Semantic Scholar / 百度学术 / 知网。
- FR-7：Semantic Scholar 通过 API 搜索。
- FR-8：百度学术/知网通过爬虫搜索，失败降级为外链跳转。
- FR-9：多平台结果聚合，返回 papers + fallbacks（外链）。
- FR-10：前端搜索表单支持平台多选（全选/部分）。
- FR-11：LLM 搜索工具（search_papers/search_by_topic）支持 platform 参数。

### 非功能需求

- NFR-1：爬虫失败降级外链，不中断整体搜索。
- NFR-2：凭据/密钥安全沿用。
- NFR-3：爬虫带超时与 UA，避免阻塞。

## 数据结构约定

- Paper 模型新增 `source` 字段（arxiv/semantic_scholar/baidu/cnki）。
- 搜索响应：`{papers: [...], fallbacks: [{platform, url}]}`。

## 后端接口草案

- 改造 `POST /api/search`、`POST /api/search/topic`：body 增加 `platforms`（可选列表，默认全部）。
- 新增 `POST /api/papers/upload`（multipart PDF 上传 → 提取元数据 → 返回 `pdf_token` + 元数据，暂不入库）。
- 新增 `POST /api/papers/upload/confirm`（`pdf_token` + 用户编辑后的元数据 → 入库）。

## 依赖与前置条件

- 已有 PyMuPDF、LangChain LLM、httpx。
- spec-002（分析）、spec-001（papers 表）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 百度学术/知网爬虫稳定性差、可能被反爬，以「降级外链」兜底。
- 多平台元数据字段不一致，需归一化到 Paper 模型。
