# Spec：文献搜索与下载（arXiv）

## 元信息

- **Spec 编号**：`spec-001-paper-search-download`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-project-kickoff.md`、`.ai/decisions/2026-08-24-backend-stack.md`、`.ai/decisions/2026-08-24-llm-orchestration.md`
- **负责人**：协调开发 Agent

## 背景与动机

openlab 科研流程的第一步是自动从 arXiv 搜索并下载相关论文，为后续论文分析、创新点设计提供输入。

## 目标

- 用户可通过 Web 界面发起 arXiv 论文搜索。
- 支持两种搜索方式：直接输入关键词/检索式；输入主题描述由 LLM 拆解为检索式。
- 自动下载命中的论文 PDF 全文与元数据。
- PDF 存本地目录，元数据存 SQLite，供后续模块使用。

## 范围

### 包含（In Scope）

- 后端（Python + FastAPI）：
  - arXiv API 搜索（关键词/检索式）。
  - 主题描述 → 检索式的 LLM 拆解（LangChain ChatOpenAI，OpenAI 兼容）。
  - PDF 全文下载。
  - 元数据（标题、作者、摘要、分类、日期、arXiv ID、PDF 链接）入库 SQLite。
  - 可配置结果数量，支持分类/日期过滤。
  - LLM 多平台支持：内置平台预设（base_url + 默认模型）+ 自定义。
- 前端（React + TypeScript + Vite + Ant Design）：搜索入口、结果列表、下载状态展示，LLM 平台预设选择与自定义配置。
- 开发工具：一键启动脚本 `start.ps1`（检测/安装依赖 + concurrently 合并输出启动前后端）。

### 不包含（Out of Scope）

- 论文内容分析（后续 spec）。
- 创新点设计（后续 spec）。
- 其他数据源（Semantic Scholar 等）。
- 多用户/权限体系。

## 需求描述

### 功能需求

- FR-1：用户可通过关键词/检索式搜索 arXiv。
- FR-2：用户可输入主题描述，系统用 LLM 拆解为检索式后搜索。
- FR-3：搜索结果以列表展示（标题、作者、摘要、分类、日期、arXiv ID）。
- FR-4：可配置每次返回数量，支持按分类（如 cs.AI）与日期范围过滤。
- FR-5：可下载选中（或全部）论文的 PDF 全文到本地目录。
- FR-6：下载的论文元数据持久化到 SQLite，重复下载被跳过。
- FR-7：展示下载进度/状态。
- FR-8：LLM 调用基于 LangChain（ChatOpenAI 自定义 base_url），保持 OpenAI 兼容。
- FR-9：提供平台预设列表（常见平台 base_url + 默认模型），后端提供查询接口，前端支持下拉选择与自定义。
- FR-10：LLM 配置（base_url/api_key/model）可持久化到本地配置文件（非数据库、不入 git），不硬编码密钥。
- FR-11：提供一键启动脚本 `start.ps1`，自动检测并安装依赖（Python venv + 后端依赖；Node/npm + 前端依赖），然后通过 concurrently 合并输出启动前后端；后端默认端口 8001，端口可通过参数/环境变量配置，前端代理端口与之一致。

### 非功能需求

- NFR-1：LLM API Key 通过配置（本地配置文件/环境变量）提供，不硬编码、不入库。
- NFR-2：遵守 arXiv API 使用规范（限速）。
- NFR-3：个人自用，单用户，无需鉴权。

## 业务规则

- 重复下载判断：以 arXiv ID 唯一标识，已存在则跳过或提示。
- PDF 存储路径：本地目录按约定组织（如 `data/papers/<arxiv_id>.pdf`）。

## 依赖与前置条件

- 后端项目骨架（Phase 1）。
- OpenAI 兼容 API 配置。
- 依赖：langchain、langchain-openai。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- arXiv API 限速与稳定性。
- LLM 主题拆解的准确率需在实际使用中调优。
