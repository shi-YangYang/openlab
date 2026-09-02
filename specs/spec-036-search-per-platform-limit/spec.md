# Spec：搜索返回数量语义修正（spec-036）

## 元信息

- **Spec 编号**：`spec-036-search-per-platform-limit`
- **状态**：`completed`
- **创建日期**：2026-08-31
- **类型**：小 Spec（后端路由修正）
- **来源**：用户反馈——搜索页设置返回 10 条、四平台全开，实际往往只返回第一个平台的 10 条
- **负责人**：协调开发 Agent

## 背景与根因（已核实）

- 聚合器（aggregator.py）行为正确：每个 provider 各自按 `max_results` 查询，结果合并不截断。
- **根因**：`routes/search.py` 两处（keyword 64-66 行、topic 90-92 行）在合并结果上做**全局截断** `[: max_results]`——平台拼接顺序 arxiv → semantic_scholar → baidu → cnki，截断后基本只剩第一个平台的结果。
- 前端不截断（App.tsx 直接渲染 `res.papers`）。
- Agent 工具 `search_papers`（tools.py:203）无截断，行为本就是每平台 N 条。

## 已确认的设计决策（用户拍板）

**「返回数量」语义 = 每平台各 N 条**：设置 10 + 四平台全开 → 最多 40 条。

## 需求描述

- FR-1：`routes/search.py` 两处截断改为**按平台分组截断**：`_filter_by_date` 先行（保持现状），然后按每条结果的 `source` 字段分组、各组截 `[: max_results]`、合并返回（保序：平台首次出现顺序）。
- FR-2：`agent/tools.py` `search_papers` 与 `search_by_topic` 的 `max_results` 参数描述更新为「每个平台各返回的最大条数」（工具行为不变，仅描述准确化）。
- FR-3：搜索历史保存完整多平台结果（去全局截断后自然生效，无额外改动）。

## 验收标准

- AC-1：mock 聚合返回 arxiv×10 + s2×10 + baidu×10 + cnki×10 → keyword/topic 接口返回 40 条，每平台各 10 条。
- AC-2：某平台返回 3 条 → 该平台只有 3 条，其他平台不受影响。
- AC-3：日期过滤后单平台超 N 条 → 该平台截到 N 条（分组截断在过滤后生效）。
- AC-4：现有测试适配（如有断言总条数 ≤ max_results 的用例需按新语义更新）；pytest 全量通过。
