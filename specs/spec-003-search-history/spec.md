# Spec：搜索历史与本地记录（spec-003）

## 元信息

- **Spec 编号**：`spec-003-search-history`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **负责人**：协调开发 Agent

## 背景与动机

用户每次进入系统都需要重新搜索，浪费时间。需要本地记录能力：启动时自动加载论文库、记录搜索历史与结果快照，点击历史即可恢复，无需重复搜索。

## 目标

- 启动时自动加载已下载论文库并展示。
- 每次搜索自动记录历史（查询词 + 模式 + 结果快照）。
- 点击历史条目恢复该次搜索结果，无需重新搜索。
- 支持删除单条 / 清空全部历史，历史持久化到 SQLite。
- UI 改造：顶部导航栏 + 多页面布局（搜索 / 论文库 / 历史搜索 / 设置）。

## 范围

### 包含（In Scope）

- 后端：`search_history` 表 + 保存/查询/删除接口。
- 前端：启动加载论文库、历史面板、点击恢复快照、删除/清空。
- 前端 UI 改造：顶部导航栏（AntD Layout：Header + 水平 Menu + Content），拆分为搜索 / 论文库 / 历史搜索 / 设置四个页面。

### 不包含（Out of Scope）

- 其它数据源、多用户/权限。

## 需求描述

### 功能需求

- FR-1：前端启动时自动加载已下载论文库并展示（无需搜索）。
- FR-2：关键词/主题搜索时自动记录历史（query、mode、结果快照 JSON）。
- FR-3：展示搜索历史列表（query、mode、时间、结果数）。
- FR-4：点击历史条目恢复该次搜索结果快照。
- FR-5：支持删除单条历史、清空全部历史。
- FR-6：历史持久化到 SQLite，重启后保留。
- FR-7：顶部导航栏（AntD Layout：Header + 水平 Menu + Content），含品牌标识与页面切换。
- FR-8：搜索页：搜索表单 + 搜索结果表格（LLM 配置从搜索页移除）。
- FR-9：论文库页：展示已下载论文（启动自动加载），保留分析/批量分析/对比综述/下载操作。
- FR-10：历史搜索页：历史列表 + 点击恢复快照 + 删除/清空。
- FR-11：设置页：LLM 配置（平台预设 + base_url/model/api_key 自定义）。

### 非功能需求

- NFR-1：单条历史快照最多保存 N 篇（默认 50），避免数据库膨胀。
- NFR-2：密钥安全沿用 spec-001（不入库、不硬编码）。

## 数据结构约定

`search_history` 表：`id, query, mode, papers(JSON 快照), created_at`。

## 后端接口草案

- `GET /api/search/history` — 历史列表（元信息 + 结果数，不含完整 papers）。
- `GET /api/search/history/{id}` — 单条快照（含 papers）。
- `DELETE /api/search/history/{id}` — 删除单条。
- `DELETE /api/search/history` — 清空全部。
- 保存：在 `POST /api/search` 与 `POST /api/search/topic` 内部自动记录。

## 依赖与前置条件

- spec-001（搜索与下载，含 `/api/papers`）。
- SQLite 存储（复用现有数据库）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 快照占用空间（用 NFR-1 限制条数控制）。
