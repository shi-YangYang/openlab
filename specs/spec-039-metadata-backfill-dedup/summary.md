# Summary：spec-039-metadata-backfill-dedup

## 完成日期

2026-09-02

## 实施内容

1. **论文元数据补全**：`metadata_backfill.py` 新建——选 `source='arxiv'` 且缺 authors/published/categories 的论文（含空串形态），逐个经 `ArxivClient.fetch_by_ids`（arxiv.py 抽取 `_request` 共用限速/重试）回填**仅 6 个元数据字段**（title/abstract/authors/categories/published/pdf_url，本地字段绝不动），变更才写库 + FTS 同步；计数 {updated/skipped_non_arxiv/unchanged/failed}。API `POST /api/papers/metadata/backfill`（limit 1-20 同步执行）。前端论文库「补全元数据」按钮（loading + 完成提示 + 列表刷新）。
2. **重复工具调用保护**：`_run_loop` 权限门控后、执行前对**非危险工具**查重（规范化 JSON 参数 vs 历史 AIMessage.tool_calls → 紧随 ToolMessage）；命中跳过执行，回填 `"[重复调用已跳过] …此前结果前 800 字"` 的 ToolMessage + status=skipped 条目 emit + INFO 日志；危险工具（人工审批过）不做去重。

## 验证结果

- pytest 全量 **455 passed**（新增 6+）；`npm run build` 通过。
- 验收独立 e2e：backfill 计数与库更新、查重 skip/异参执行/危险工具不去重全链路复核。
- **真实库冒烟**：3 篇缺元数据论文全部补全（15/15 有 authors），BibTeX key 从 `unknownmusic` → `huang2018music`、author/year 字段完整。

## 遗留事项

- baidu/cnki 来源补全、标题模糊匹配（无可靠元数据源，Out of Scope）。
- 同一响应批次内两条同参 tool_call 不去重（tool_call_id 链语义，符合 spec 字面）。
