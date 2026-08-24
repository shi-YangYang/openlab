# 验收标准与验收记录：搜索历史与本地记录（spec-003）

## 验收标准

- AC-1（对应 FR-1）：前端启动自动加载并展示已下载论文库。
- AC-2（对应 FR-2）：搜索后历史自动记录（含结果快照）。
- AC-3（对应 FR-3）：历史列表展示 query、mode、时间、结果数。
- AC-4（对应 FR-4）：点击历史条目恢复该次搜索结果快照。
- AC-5（对应 FR-5）：单条删除与清空全部历史生效。
- AC-6（对应 FR-6）：历史持久化到 SQLite，重启后保留。
- AC-7（对应 NFR-1）：单条快照条数受上限限制（默认 50）。
- AC-8（对应 FR-7）：顶部导航栏存在，可切换搜索/论文库/历史搜索/设置四个页面。
- AC-9（对应 FR-8）：搜索页功能正常（搜索表单 + 结果）。
- AC-10（对应 FR-9）：论文库页展示已下载论文，分析/下载/对比综述操作可用。
- AC-11（对应 FR-10）：历史搜索页展示/恢复/删除/清空正常。
- AC-12（对应 FR-11）：设置页 LLM 配置（平台预设 + 自定义）正常。

## 验收步骤

1. 启动后端与前端，确认前端自动加载已下载论文库。
2. 执行一次关键词搜索与一次主题搜索，确认历史被记录。
3. 查看历史列表，确认展示 query/mode/时间/结果数。
4. 点击历史条目，确认结果快照被恢复展示。
5. 删除单条、清空全部，确认生效。
6. 重启后端/前端，确认历史仍在。
7. 运行 pytest 通过。

## 验收记录

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 无阻塞问题；AC-1~12 全部满足，后端 pytest 64 passed，前端 build 通过，独立运行时验证 16/16 通过 | 通过，进入收尾 |

## 验收结论

结论：**PASS**（验收 Agent 独立验收）

### 逐条判定（AC-1~12）

- **AC-1（FR-1）PASS**：`frontend/src/App.tsx:54-56` 启动 `useEffect` 调 `libraryWorkspace.loadLibrary()`；`hooks/usePaperWorkspace.ts:108-127` `loadLibrary` 调 `listPapers()` 填充论文库页。
- **AC-2（FR-2）PASS**：`backend/app/main.py:100`（关键词）、`main.py:120`（主题）搜索成功后调 `database.save_search_history`；失败时在保存前抛异常，不记录（`test_search_history.py:81-90` + 独立验证通过）。
- **AC-3（FR-3）PASS**：`database.list_search_history`（`database.py:392-406`）返回 `paper_count` 且 `pop("papers")`；前端 `SearchHistoryList.tsx:75-124` 展示 query/mode/时间/结果数四列。
- **AC-4（FR-4）PASS**：`SearchHistoryList.tsx:43-53` 点击拉取 `getSearchHistory` 后 `onRestore`；`App.tsx:84-88` 恢复快照并切回搜索页。
- **AC-5（FR-5）PASS**：`main.py:137-147` DELETE 单条/清空；前端 `SearchHistoryList.tsx:55-73` 单删/清空后刷新列表。
- **AC-6（FR-6）PASS**：`database.py:48-54` `search_history` 表 + `init_db`/`_migrate` 幂等；`test_history_migration_idempotent` 与独立「旧库迁移无损」验证通过。
- **AC-7（NFR-1）PASS**：`config.py:54-56` `SEARCH_HISTORY_SNAPSHOT_LIMIT` 默认 50；`database.py:381` 快照 `papers[: limit]`；`test_history_snapshot_limit` + 独立验证截断为 50 通过。
- **AC-8（FR-7）PASS**：`App.tsx:98-112` AntD `Layout`(Header + 水平 `Menu` + Content) + 四菜单项（搜索/论文库/历史搜索/设置）。
- **AC-9（FR-8）PASS**：搜索页 = `SearchForm` + `PaperWorkspace`（`App.tsx:114-133`），LLM 配置已移除。
- **AC-10（FR-9）PASS**：论文库页复用 `PaperWorkspace`，下载/分析/对比综述按钮齐备（`PaperWorkspace.tsx:38-57`）。
- **AC-11（FR-10）PASS**：历史页展示/恢复/单删/清空均已实现并验证。
- **AC-12（FR-11）PASS**：设置页 `LlmConfigForm`（平台预设 + base_url/model/api_key 自定义）正常。

### 不回归判定

PASS：后端 `pytest` **64 passed**（含 search/analysis/llm/llm_config/pdf/database/arxiv 全部既有测试）；前端 `npm run build`（tsc + vite）**构建通过**。

### 测试实际运行

- `backend\.venv\Scripts\python.exe -m pytest -q` → `64 passed in 1.88s`。
- `frontend npm run build` → vite 构建成功（仅 chunk 体积提示，非错误）。
- 独立运行时验证脚本（TestClient + 临时库）16/16 通过：关键词/主题搜索记录、列表 paper_count 不含 papers、单条含 papers、单删/清空、失败搜索不记录、默认快照上限 50、旧库迁移无损。

### 发现问题 / 阻塞项

- 发现问题：无。
- 阻塞项：无。
