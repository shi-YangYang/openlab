# Summary：spec-036-search-per-platform-limit

## 完成日期

2026-08-31

## 实施内容

**根因**：聚合器每平台各查 N 条正确，但 `routes/search.py` 在合并结果上全局截断 `[: max_results]`，平台按 arxiv→S2→百度→知网 拼接，截断后基本只剩第一平台。

**修复**：
- 新增 `_per_platform_limit(papers, max_results)`（routes/search.py）：按 `source` 字段分组、每组截 N、保持首次出现顺序；`_filter_by_date` 先行。keyword 与 topic 两处路由统一替换。
- Agent 工具 `max_results` 描述更新为「每个平台各返回的最大条数」（行为不变）。
- 新增 tests/test_search_route.py 5 用例（四平台 40 条、短平台不影响他台、日期过滤后分组截断、历史存完整结果）。

## 验证结果

- pytest 全量 **408 passed**（+5）；验收独立核对含 source 缺失兜底（空组独立计数）与非恒真断言抽查。

## 遗留事项

- 无。语义变化提示：搜索页同参数下结果总量 = 每平台 N 条之和（此前为全局 N 条）。
