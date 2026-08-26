# 验收标准与验收记录：多平台搜索与本地 PDF 上传（spec-013）

## 验收标准

- AC-1（对应 FR-1）：论文库页可上传本地 PDF。
- AC-2（对应 FR-2）：上传后提取标题/作者/摘要/日期元数据。
- AC-3（对应 FR-3）：提取的元数据先展示在可编辑表单，用户确认后才入库（必须有审查环节）。
- AC-4（对应 FR-4）：确认后元数据入库并显示在论文库表格。
- AC-5（对应 FR-5）：上传后可触发完整 4 维度分析。
- AC-6（对应 FR-6）：搜索源抽象含 arXiv/SemanticScholar/BaiduXueshu/Cnki。
- AC-7（对应 FR-7）：Semantic Scholar API 搜索可用。
- AC-8（对应 FR-8）：百度学术/知网爬虫失败时降级外链。
- AC-9（对应 FR-9）：多平台结果聚合，含 fallbacks。
- AC-10（对应 FR-10）：搜索表单平台多选（全选/部分）。
- AC-11（对应 FR-11）：LLM 搜索工具支持 platform 参数。

## 验收步骤

1. 启动后端与前端。
2. 搜索表单选不同平台（全选/部分），验证多平台结果与 fallback 外链。
3. 上传一个 PDF，验证元数据回填表格，再触发完整分析。
4. agent 搜索指定平台，验证 platform 参数生效。
5. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-26 | PASS | AC-1~11 全部通过；pytest 199 passed；前端 build 通过 | 可进入完成收尾流程 |

## 验收结论

- **结论**：PASS
- **逐条判定**：
  - AC-1（FR-1 上传本地 PDF）：PASS。`frontend/src/components/UploadPdfModal.tsx` 使用 `Upload.Dragger accept=".pdf"`；`PaperWorkspace.tsx` 提供「上传 PDF」入口（`App.tsx` 挂载 `UploadPdfModal`）。
  - AC-2（FR-2 提取元数据）：PASS。`backend/app/upload.py` `extract_metadata` 用 LLM 返回 `PaperMetadata{title,authors,abstract,published}`；`main.py upload_paper_pdf` 经 `pdf.extract_text` 后调用。测试 `test_extract_metadata_uses_llm`。
  - AC-3（FR-3 审查环节、upload 不入库）：PASS。上传接口仅暂存 PDF、返回 `pdf_token + paper`，不调用入库；前端先展示可编辑表单，点「保存」才调 `confirm`。实测上传后（confirm 前）`/api/papers` 数量为 0。
  - AC-4（FR-4 确认后入库并显示）：PASS。`confirm_paper_pdf` upsert 且 `source="upload"`、`set_status("downloaded")`；测试 `test_upload_and_confirm_flow` 验证 `source/status/arxiv_id` 与 `/api/papers` 可见。
  - AC-5（FR-5 可触发完整 4 维度分析）：PASS。确认后标记 `downloaded` + `local_pdf_path`，满足 `_is_downloaded`；`analysis.run_analysis_job` 从 `local_pdf_path` 提取文本。
  - AC-6（FR-6 搜索源抽象）：PASS。`backend/app/search/base.py` `SearchProvider`(ABC)，`arxiv.py/semantic_scholar.py/baidu_xueshu.py/cnki.py` 四实现；`aggregator._PROVIDER_CLASSES` 注册。
  - AC-7（FR-7 Semantic Scholar API）：PASS。`semantic_scholar.py` 走 Graph API；测试 `test_semantic_scholar_normalizes`。
  - AC-8（FR-8 爬虫失败降级外链）：PASS。`aggregator.search` 用 `asyncio.gather(return_exceptions=True)`，异常平台写入 `fallbacks`（`fallback_url`）。测试 `test_aggregator_merges_and_falls_back`、`test_baidu_provider_raises_on_timeout`、`test_search_provider_failure_degrades_to_fallback`。
  - AC-9（FR-9 多平台聚合含 fallbacks）：PASS。`aggregator.search` 返回 `{papers, fallbacks}`；`main.py /api/search` 与 `/api/search/topic` 均透传。
  - AC-10（FR-10 前端平台多选）：PASS。`SearchForm.tsx` `Checkbox.Group` + 「全选」`indeterminate` 切换，`platforms` 传入请求。
  - AC-11（FR-11 LLM 工具 platform 参数）：PASS。`agent/tools.py` `SearchPapersArgs/SearchByTopicArgs` 含 `platforms`，`search_papers/search_by_topic` 透传到 `aggregate_search`。
- **测试运行情况**：
  - 后端：`backend\.venv\Scripts\python.exe -m pytest -q` → `199 passed in 8.33s`。
  - 前端：`npm run build`（tsc && vite build）→ 成功（仅 chunk 体积告警，非错误）。
  - 独立实测（TestClient + mock LLM）：upload 不入库（confirm 前 papers 为 0）、confirm 后 `source=upload/status=downloaded`、多平台聚合 `papers/fallbacks` 结构正常。
- **不回归判定**：无回归。全量 pytest 199 项通过，覆盖既有 spec 用例（数据库迁移、下载、搜索历史、分析等）及新增用例。
- **发现问题**：无阻塞问题。仅前端 vite 构建的 chunk >500kB 体积提示（非功能性，不阻断验收）。
- **阻塞项**：无。
