# 实施计划：搜索历史与本地记录（spec-003）

## 任务拆分

1. `search_history` 表与 database 函数（保存/列表/取单条/删除/清空，迁移幂等）。
2. 搜索接口（`/api/search`、`/api/search/topic`）自动记录历史（含快照，限制 N 篇）。
3. 历史 API（列表/单条/删除/清空）。
4. 前端 UI 改造：顶部导航栏（AntD Layout），拆分为搜索/论文库/历史搜索/设置四个页面。
5. 搜索页、论文库页（启动加载）、历史搜索页、设置页的页面实现。
6. 测试。

## 实施顺序

存储 → 搜索记录 → 历史 API → 前端导航与页面拆分 → 各页面 → 测试。

## 涉及文件/模块

- `backend/app/database.py`、`main.py`、`schemas.py`（新增历史相关）。
- `frontend/src/App.tsx`、`api.ts`、`types.ts`、新增历史面板组件。
- `tests/` 新增历史相关测试。

## 技术要点

- `search_history` 表：`id, query, mode, papers(TEXT JSON), created_at`；用 `_migrate` 幂等建表。
- 搜索成功后将结果（截取前 N 篇，默认 50）作为快照存入历史；失败搜索不记录。
- 历史列表接口返回元信息 + `paper_count`，不含完整 papers（减小响应）；单条接口返回完整快照。
- 前端启动 `useEffect` 调 `GET /api/papers` 填充论文库；历史面板点击条目拉取单条快照并填充结果表格。

## 风险与应对

- 快照膨胀：限制每历史 N 篇，并支持删除/清空。
- 旧库兼容：`_migrate` 幂等建表。
