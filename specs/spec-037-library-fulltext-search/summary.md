# Summary：spec-037-library-fulltext-search

## 完成日期

2026-08-31

## 实施内容（论文库全文检索，零配置零向量）

1. **FTS 层**（db/papers_fts.py 新建）：FTS5 虚拟表 `papers_fts`（trigram tokenizer，paper_id UNINDEXED + title/abstract/analysis_text/source）；启动探测可用性（不可用降级仅日志，不阻塞应用）；update/remove/rebuild/rebuild_if_empty/search_paper_fts 全套函数。
2. **同步点**：论文 upsert/delete、分析 upsert 后同步 FTS 行（try/except 不阻断写库）；lifespan 异步幂等建索引（空表且有存量论文时全量重建）。
3. **API**：`GET /api/papers/search?q=&limit=50`（空 q 400、FTS 不可用 503、rank 排序、matched_in 命中来源标注）+ `POST /api/papers/search/rebuild`。
4. **Agent 新工具 `search_library`**：库内检索（非危险，直接执行），Agent 可回答"我库里哪些论文提到 X"。
5. **<3 字符兜底**：任一词条 <3 字符（中文两字词）整体走 LIKE（四列 + ESCAPE 转义 + AND 语义），避免 trigram 短词空结果。
6. **前端**：PaperWorkspace 顶部 Input.Search，结果替换列表 + 清除恢复全量；空结果 Empty 提示。

## 多词语义决策

FTS MATCH 分支：每词双引号短语 AND 连接（逐步收窄）；混合长短词整体走 LIKE 保持同一 AND 语义。

## 验证结果

- pytest 全量 **420 passed**（新增 12）；`npm run build` 通过。
- 验收独立 e2e：中文子串/大小写/分析后新词命中/删除不命中/rebuild 幂等；**SQL 注入面 12 组恶意 q 全部安全**（LIKE 转义 + MATCH 引号双写 + 参数化）。
- 已知低危 2 条（rebuild 计数含单篇失败；LIKE 分支排序为 rowid 非 rank——trigram 固有限制）。

## 补充加固（真实库冒烟发现，2026-08-31）

真实冒烟时发现：papers 表存在 NULL 元数据行时，`GET /api/papers` 因 `PaperRecord` 必填字段校验失败而整页 500（本次触发源是 spec-035 冒烟残留数据，已清理；但上传/平台解析未来同样可能写入 NULL）。随本 spec 一并加固：

- `Paper` 基类 `title/abstract/published/pdf_url/url` 改 `Optional[str]`（对照建表语句可空列）。
- analysis/experiment/innovation/tools 的 `paper.get(x, "")` 改 `or ""`（防 None 透传 LLM payload）。
- 前端 types 同步 `string | null`（渲染本已容忍）。
- 新增回归用例：直插 NULL 行 → `GET /api/papers` 200。
- pytest **421 passed**。

## 遗留事项

- 无阻塞。真实库冒烟通过（真实标题词命中、多词 AND、两字词 LIKE 兜底、rebuild 幂等 15 篇）。
