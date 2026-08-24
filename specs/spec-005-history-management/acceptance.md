# 验收标准与验收记录：历史管理（spec-005）

## 验收标准

- AC-1（对应 FR-1）：「历史」页有 tab，可切换「搜索历史」「创新点历史」。
- AC-2（对应 FR-2）：创新点历史列表展示时间、来源论文、创新点数量、状态。
- AC-3（对应 FR-3）：点击创新点历史条目，弹窗展示当时完整快照（不重新生成）。
- AC-4（对应 FR-4）：搜索历史快照恢复仍正常（spec-003 不回归）。
- AC-5（对应 FR-5）：创新点历史重启后保留（复用 innovations 表）。
- AC-6（对应 NFR-1）：列表接口不含 content，详情接口含 content。

## 验收步骤

1. 启动后端与前端。
2. 历史页切换两个 tab。
3. 生成若干创新点后，创新点历史列表正确展示。
4. 点击条目查看详情，内容与生成时一致。
5. 搜索历史恢复功能正常。
6. 重启后创新点历史仍在。
7. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 无 | 全部 AC 通过，可进入下一环节 |

## 验收结论

**结果：PASS**

- AC-1~AC-6 全部 PASS，无回归。
- 后端 `pytest`：86 passed。
- 前端 `npm run build`：通过（tsc + vite build 成功）。
- 实际运行验证（TestClient + mock LLM）：`GET /api/innovations` 返回元信息（不含 content，含 paper_count=2、innovation_count=3、language/status/created_at）；`GET /api/innovations/{id}` 返回完整 content（3 条创新点）；重启（重新 init_db）后创新点历史仍在。

逐条判定：

| AC | 结果 | 证据 |
| ---- | ---- | ---- |
| AC-1 | PASS | `frontend/src/App.tsx:159-175` Tabs（搜索历史/创新点历史），导航 label「历史」`App.tsx:30` |
| AC-2 | PASS | `frontend/src/components/InnovationHistoryList.tsx:71-110` 列：时间/来源论文/创新点数量/状态 |
| AC-3 | PASS | `InnovationHistoryList.tsx:48-58` 点击调 `getInnovation(id)` 只读弹窗，不调用 `createInnovations` |
| AC-4 | PASS | `SearchHistoryList.tsx` 恢复逻辑不变；`test_search_history.py` 全部通过 |
| AC-5 | PASS | `backend/app/database.py:453-485` `list_innovation_history` 复用 `innovations` 表；`test_innovation_history_migration_preserves_data` 通过 |
| AC-6 | PASS | `database.py:481` 列表 `pop("content")`；`schemas.py:151-158` `InnovationHistoryItem` 无 content 字段；详情 `get_innovation` 返回 content |
