# Spec：功能增强与 Bug 修复（spec-015）

## 元信息

- **Spec 编号**：`spec-015-ux-enhancements`
- **状态**：`draft`
- **创建日期**：2026-08-26
- **关联决策**：无（本次为 UI 布局、导航、配置与论文库管理增强）
- **负责人**：协调开发 Agent

## 背景与动机

spec-001 ~ 014 已搭建起完整的搜索、分析、创新点、实验方案、部署与 Agent 能力。在使用过程中暴露出若干体验与功能缺口：

1. 内容区最大宽度 1200px 偏窄，在大屏上浪费空间。
2. 顶部「历史」是单级菜单，进入后靠页内 Tabs 切换「搜索历史 / 创新点历史」，且「实验方案」历史无独立入口、无历史列表页（后端 `list_experiments` 已存在但无对应 API 与前端）。
3. LLM 配置仅支持 base_url/model/api_key 三项，缺少 reasoning_effort（思考强度）等扩展项，也无法在输入 key + base_url 后自动拉取该平台可用模型列表。
4. 论文库缺少删除功能，删除论文时也未清理本地 PDF。
5. 上传 PDF 时只提取元数据，未分析论文的来源 URL（下载地址），用户也无法手动补充。

## 目标

- 内容区宽度扩大，改善大屏阅读体验。
- 「历史」改为带子菜单的二级导航，补全「实验方案」历史页。
- LLM 配置支持更多自定义项（reasoning_effort），并能自动获取可用模型列表。
- 论文库支持删除（含本地 PDF 清理）。
- 上传 PDF 时分析并回填来源 URL，支持用户手动填写。

## 范围

### 包含（In Scope）

- 内容区最大宽度调整。
- 顶部菜单「历史」二级菜单（搜索历史 / 创新点历史 / 实验方案），删除原有页内 Tabs 与独立入口。
- 实验方案历史列表页（复用后端已有 `list_experiments`，补 API + 前端）。
- LLM 配置扩展：reasoning_effort 字段；`/models` 接口自动获取模型列表；模型改为下拉选择（可自定义）。
- 论文库删除功能：删除论文记录 + 本地 PDF + 关联分析记录。
- 上传 PDF 流程：LLM 分析来源 URL，不可得时允许用户手动填写，确认时入库。

### 不包含（Out of Scope）

- 论文库删除的级联删除扩展到 reviews/innovations/experiments（仅删 paper 与 analysis）。
- LLM 自动获取「思考强度」枚举（reasoning_effort 的可用值不做接口探测，仅提供 low/medium/high 预设）。
- 实验方案历史页的批量删除/清空（本次仅做单条删除）。
- 内容区宽度做成用户可配置（本次固定一个更宽的值）。
## 需求描述

### 功能需求

- FR-1：内容区（`Layout.Content`）改为响应式宽度：小屏使用固定内边距，大屏（≥1600px）最大宽度 1600 并水平居中；即 `maxWidth: 1600` + `width: '100%'` + `margin: '0 auto'` + `padding: 24`，使内容区随视口宽度自适应，不再固定 1200 上限。
- FR-2：顶部菜单「历史」改为带 `children` 的二级菜单，鼠标悬浮/点击展开三项：搜索历史、创新点历史、实验方案。
- FR-3：删除原「历史」页内的 Tabs 结构，三个历史各为独立路由页面：
  - `/history/search` → 搜索历史
  - `/history/innovation` → 创新点历史
  - `/history/experiment` → 实验方案历史
- FR-4：新增实验方案历史列表页：
  - 列表展示：时间、来源（论文/创新点）、语言、状态、方案数、操作（查看/导出/删除）。
  - 查看：弹窗展示实验方案内容（复用 ExperimentModal 的展示逻辑或独立详情弹窗）。
  - 导出：复用 `/api/experiments/{id}/export`。
  - 删除：新增 `DELETE /api/experiments/{id}` 与 `DELETE /api/experiments`（清空）。
- FR-5：后端补齐实验方案相关 API：`GET /api/experiments`（列表）、`DELETE /api/experiments/{id}`、`DELETE /api/experiments`。
- FR-6：LLM 配置新增 `reasoning_effort` 字段：
  - 后端 `LLMConfig` / `LLMConfigUpdate` 增加该字段并持久化到 `llm_config.json`。
  - 前端表单增加「思考强度」下拉（low / medium / high），仅当用户选择时随配置保存。
  - 各 LLM 调用点（analysis/upload/review/innovation/experiment）在调用 ChatOpenAI 时透传 `reasoning_effort`（若配置存在且非空）。
- FR-7：新增「获取模型」能力：
  - 后端新增 `POST /api/llm/models`：入参 `base_url` + `api_key`，向 `{base_url}/models` 发 GET（Bearer 认证），解析返回的 `data[].id`，返回模型 id 列表。
  - 前端在 LLM 配置表单增加「获取模型」按钮，成功后模型字段变为可搜索下拉（支持自定义输入）。
- FR-8：论文库删除功能：
  - 后端新增 `DELETE /api/papers/{arxiv_id}`：删除 papers 表记录、删除对应本地 PDF 文件、删除关联 analyses 记录；文件不存在时不报错。
  - 前端论文库表格操作列新增「删除」按钮（Popconfirm 二次确认），删除后刷新列表。
- FR-9：上传 PDF 分析来源 URL：
  - 后端 `upload.extract_metadata` 额外提取 `url`（来源 URL，如 arxiv.org/abs/xxx，不可得则空字符串）。
  - `PaperMetadata` 增加 `url` 字段。
  - 前端上传确认表单新增「来源 URL」输入项，预填 LLM 分析结果，可手动修改；确认时随 paper 入库（`url` 字段）。
  - 搜索/论文库中，来源为 upload 的论文其标题链接/查看原文能使用该 `url`。

### 非功能需求

- NFR-1：删除论文文件用安全的路径拼接（基于 arxiv_id 白名单字符校验），避免路径穿越。
- NFR-2：`/api/llm/models` 请求超时上限 15s，失败时返回明确错误而非抛 500。
- NFR-3：LLM 配置新增字段向后兼容：旧配置无 reasoning_effort 时按空处理，不影响现有调用。
- NFR-4：数据库迁移新增列时沿用现有 `_migrate` 机制，不重建表。

## 业务规则

- BR-1：reasoning_effort 仅在用户显式选择时生效；为空则沿用模型默认行为。
- BR-2：删除论文时，若本地 PDF 文件不存在，仍删除数据库记录（幂等）。
- BR-3：实验方案历史的状态沿用 pending/running/done/failed，展示沿用创新点历史的样式。
- BR-4：来源 URL 分析失败不影响 PDF 上传主流程，仅置空并交由用户填写。

## 依赖与前置条件

- 依赖 spec-002（分析）、spec-004（创新点）、spec-007（实验方案）、spec-013（上传）、spec-014（平台登录）。
- 后端已存在 `database.list_experiments()`、`database.get_experiment()`，仅需补删除与 API。
- `llm_config.py` 已有 base_url/api_key/model 三字段持久化，需扩展 reasoning_effort。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- 内容区变宽；历史菜单为二级菜单；三个历史页面可独立访问；实验方案历史可查看/导出/删除。
- LLM 配置可设置思考强度，可自动获取模型列表。
- 论文库可删除论文并清理本地 PDF。
- 上传 PDF 可分析并回填来源 URL，可手动填写。

## 风险与开放问题

- 各 OpenAI 兼容平台的 `/models` 接口返回格式与认证方式存在差异（部分平台不支持），需容错降级为「手动填写」。
- `reasoning_effort` 仅部分模型支持，透传后不支持的模型可能报错，需在文案中提示。
- 内容区采用 `maxWidth: 1600 + width: 100%` 的响应式布局，视口 < 1600 时自动收缩并保留内边距，避免小屏溢出。