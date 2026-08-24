# 验收标准与验收记录：论文自动分析（spec-002）

## 验收标准

- AC-1（对应 FR-1）：能解析已下载论文 PDF 并提取全文文本。
- AC-2（对应 FR-2）：单篇分析返回 4 个维度结构化结果（总结含研究问题/方法/贡献/结论；实验含数据集/基线/指标/关键结果；局限与未来工作；关键词/标签）。
- AC-3（对应 FR-3）：传入 `language=zh`/`en` 时输出对应语言。
- AC-4（对应 FR-4）：批量分析逐篇执行，可查询进度/状态。
- AC-5（对应 FR-5）：多篇对比综述返回共同主题、差异、研究空白。
- AC-6（对应 FR-6）：分析结果入库，重复分析覆盖更新。
- AC-7（对应 FR-7）：前端详情页展示结构化分析。
- AC-8（对应 FR-8）：可导出单篇与综述的 Markdown。
- AC-9（对应 FR-9）：前端展示分析进度/状态。
- AC-10（对应 NFR-2）：存在长文本分块/截断逻辑。
- AC-11（对应 NFR-3）：密钥不入库、不硬编码、不打印。
- AC-12（对应 FR-10）：分析/综述失败时记录具体失败原因（error 字段）并可查询。
- AC-13（对应 FR-11）：对未下载论文发起分析时返回明确错误，前端提示，而非静默标 failed。
- AC-14（对应 NFR-5）：LLM 调用配置了超时。
- AC-15（对应 FR-12）：单篇分析详情以模态框展示（非抽屉）。
- AC-16（对应 FR-13）：单篇分析有分块级进度与提示（progress/message）。
- AC-17（对应 FR-14）：批量分析时每篇论文展示独立进度条。
- AC-18（对应 FR-15）：PDF 下载有进度条（progress 0-100）。
- AC-19（对应 FR-16）：对比综述异步后台执行并有进度条。

## 验收步骤

1. 启动后端与前端。
2. 准备一篇已下载论文（spec-001 下载），触发单篇分析，验证 4 维度结构化结果。
3. 切换语言，验证中/英输出。
4. 触发批量分析，验证逐篇执行与状态/进度。
5. 触发多篇对比综述，验证共同主题/差异/研究空白。
6. 重复分析，验证结果覆盖更新。
7. 前端查看详情、导出 Markdown。
8. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 无阻塞问题；AC-1~AC-11 全部满足，spec-001 无回归（45 pytest 通过，前端 build 通过，真实 PDF 1706.03762 提取 39497 字符成功）。 | 可进入下一环节（spec-003）。 |
| 2 | 2026-08-24 | PASS | 无阻塞问题；AC-12/AC-13/AC-14 全部满足，AC-1~AC-11 无回归（51 pytest 通过，前端 build 通过，真实库迁移无损且幂等，11 papers/10 analyses/2 reviews 旧数据保留）。 | 可进入下一环节（spec-003）。 |
| 3 | 2026-08-24 | PASS | 无阻塞问题；AC-15~AC-19 全部满足（模态框替代抽屉、分块级进度/message、批量逐篇进度条、下载进度条、综述异步+进度），AC-1~AC-14 无回归（56 pytest 通过，前端 build 通过，独立 TestClient 实测 19 项全部通过，迁移幂等无损）。 | 可进入下一环节（spec-003）。 |

## 验收结论

**最终结论：PASS**（轮次 3 增强验收通过）

本轮（轮次 3）验收针对 FR-12~FR-16（AC-15~19）逐条判定如下：

| AC | 判定 | 证据 |
| ---- | ---- | ---- |
| AC-15（FR-12 模态框替代抽屉） | PASS | `frontend/src/components/AnalysisModal.tsx:7,134` 使用 antd `Modal`（非 Drawer），全仓 `frontend/src` 无 `Drawer` 导入、无 `AnalysisDrawer` 残留；`App.tsx:281-286` 用 `open`/`onClose` 控制；4 维度展示(`:200-233`)、语言切换(`:142-150`)、导出(`:154-161,118-129`) 均保留。前端 build 通过。 |
| AC-16（FR-13 分块级进度+提示） | PASS | `analysis.py:206,217-219` `analyze_paper_text` 增 `on_progress` 回调，在开始(`:222`)、单块(`:225`)、逐块(`:233`)、合并(`:236`)、完成(`:246`) 时调用；`analysis.py:264,266-267,286` `run_analysis_job` 经 `set_analysis_progress` 写 progress/message；`database.py:31-32,73-75` analyses 表含 progress/message 列；`schemas.py:134-135` `AnalysisRecord` 含 progress/message；`AnalysisModal.tsx:179-186` 展示 Progress + message。测试 `test_analyze_paper_text_calls_progress_callback`、`test_analysis_progress_written_to_db` 通过；实测 progress 序列 `[0,5,10,35,60,85,100]`、message=`分析完成`。 |
| AC-17（FR-14 批量逐篇进度条） | PASS | `PaperTable.tsx:111-139` 分析列在 `running` 时渲染 `Progress`+message；`App.tsx:81-100` `pollAnalysisStatuses` 逐篇轮询 progress/message；`run_analysis_job` 逐篇写 progress。测试 `test_analyze_batch_runs_sequentially` 通过。 |
| AC-18（FR-15 下载进度条） | PASS | `downloader.py:32-44` `download_pdf` 流式下载按 content-length 报字节进度（`aiter_bytes`），`run_download_job:63-76` 写 `papers.progress`；`database.py:20,72` papers 表含 progress 列；`schemas.py:21` `PaperRecord.progress`；`PaperTable.tsx:96-104` 下载中展示 Progress；`App.tsx` 轮询下载 progress。实测 on_progress 序列 `[10,50,90,100]` 落库 progress=100、status=downloaded。 |
| AC-19（FR-16 综述异步+进度） | PASS | `main.py:242` `insert_review(..., status="pending")` 后立即返回 pending（异步）；`analysis.py:325-342` `run_review_job` 后台推进 progress 0→50→100、写 status done/failed 与 error；`database.py:44,74,325` reviews 含 progress；`ReviewModal.tsx:32-42,102-106` 轮询 `getReview` 并展示 Progress。测试 `test_review_returns_comparative_result`、`test_review_failure_records_error`、`test_review_requires_at_least_two_papers` 通过；实测 POST 立即返回 pending，GET 最终 done/progress=100，失败时 failed/progress=100/error=`RuntimeError('boom')`。 |

本轮其它核验：
- **pytest**：全量 `56 passed in 1.54s`（含 test_api/test_arxiv/test_database/test_llm/test_llm_config/test_pdf/test_analysis；较轮次 2 新增 5 项 progress/message/review 相关测试）。
- **前端构建**：`npm run build` 通过（tsc + vite，3038 模块）。
- **独立 TestClient 实测（临时库）**：19 项全部通过 —— 分析 POST 200→done/progress=100/message 落库、progress 回调多段且达 100、下载 POST accepted+progress=100+status=downloaded+字节进度回调、review POST 立即 pending→GET done/progress=100/content 正确、review 失败→failed/progress=100/error 落库。
- **迁移幂等/无损（真实库副本）**：对 `backend/data/openlab.db` 副本连续两次 `init_db()`，papers=11、analyses=10、reviews=3 数量不变（before==after1==after2），failed 分析记录完整保留；progress/message 列正确追加且默认 0。
- **真实库现状**：papers=11、analyses=10、reviews=3（较轮次 2 多 1 条 reviews，为实施 Agent 验证综述异步时的自测数据，done/UTF-8 中文内容正常，progress=0 系迁移前插入的旧行，非当前代码缺陷）。

发现问题：无阻塞问题。仅一处非阻断观察——`App.tsx:24,159` 状态变量仍沿用旧名 `drawerOpen/setDrawerOpen`（实际已控制 Modal），纯命名遗留，不影响功能与 AC。

---

以下为轮次 2 的 AC-12~14 判定（本轮复测无回归，全量 pytest 仍通过）：

本轮（轮次 2）验收针对 FR-10/FR-11/NFR-5（AC-12~14）逐条判定如下：

| AC | 判定 | 证据 |
| ---- | ---- | ---- |
| AC-12（FR-10 失败原因记录可查询） | PASS | `backend/app/database.py:29,40` analyses/reviews 表新增 `error` 列；`_migrate`(`:63-68`) 对旧库无损幂等追加；`analysis.py:254` `run_analysis_job` 失败写 `error=repr(exc)`；`analysis.py:304` `create_review_record` 失败写 `error` 并 re-raise；`get_analysis/list_analyses/get_review/list_reviews` 经 `dict(row)` 返回 error；`schemas.py:132,143` `AnalysisRecord/ReviewRecord` 含 `error` 字段。测试 `test_analyze_missing_pdf_marks_failed`、`test_analyze_invalid_json_marks_failed`、`test_review_failure_records_error`、`test_migration_adds_error_column_without_data_loss` 通过；实测 mock LLM 抛 `RuntimeError('LLM timeout boom')` 后 `analyses.error`/`reviews.error` 均记录 `"RuntimeError('LLM timeout boom')"`。 |
| AC-13（FR-11 未下载返回明确错误非静默） | PASS | `main.py:77-81` `_is_downloaded` 校验 paper 存在 + `local_pdf_path` + `status=='downloaded'`；`main.py:190-202` 单篇：paper 不存在→404，未下载→409 `detail="论文尚未下载，请先下载: {id}"`；`main.py:167-187` 批量：任一未下载→409 列出全部未下载 id 且不提交任务（不创建分析行）；前端 `api.ts:25-35` `ApiError` 解析 `detail`；`AnalysisDrawer.tsx:107-108` 单篇 409→`请先下载该论文`；`App.tsx:165-166` 批量 409→`请先下载所选论文`；抽屉 `AnalysisDrawer.tsx:184-194` 展示 `record.error`。测试 `test_analyze_not_downloaded_returns_409`、`test_analyze_missing_paper_returns_404`、`test_analyze_batch_not_downloaded_returns_409` 通过；实测未下载 `9999.9999`→409 且无静默 failed 行，已下载 `1706.03762`→200 done。 |
| AC-14（NFR-5 LLM 超时） | PASS | `backend/app/analysis.py:31` `LLM_REQUEST_TIMEOUT_SECONDS = 120.0`；`analysis.py:108` `ChatOpenAI(..., request_timeout=LLM_REQUEST_TIMEOUT_SECONDS)`；测试 `test_chat_sets_request_timeout` 通过（断言 `request_timeout == 120.0`）。 |

本轮其它核验：
- **pytest**：全量 `51 passed in 1.10s`（含 test_api/test_arxiv/test_database/test_llm/test_llm_config/test_pdf/test_analysis）。
- **前端构建**：`npm run build` 通过（tsc + vite，3038 模块）。
- **迁移无损/幂等**：对真实库 `backend/data/openlab.db` 连续两次 `init_db()`，papers=11、analyses=10、reviews=2 数量不变，旧数据（含 `gr-qc/9810059` failed 记录）完整保留，`error` 列正确追加。
- **实际运行**：TestClient 临时库实测 10 项全部通过（未下载单篇→409/无静默行、缺失→404、批量含未下载→409 且不提交、已下载→200 done、mock 失败→error 落库、review 失败→502+error 落库）。

发现问题：无阻塞问题。轮次 1 观察到的 `run_analysis_job` 静默吞异常问题已在本轮修复（改为写 `error` 落库）。

---

以下为轮次 1 的 AC-1~AC-11 判定（本轮复测无回归，全量 pytest 仍通过）：

AC-1~AC-11 逐条判定如下：

| AC | 判定 | 证据 |
| ---- | ---- | ---- |
| AC-1（FR-1 解析 PDF） | PASS | `backend/app/pdf.py:20` 实现 PyMuPDF 提取；真实 PDF `backend/data/papers/1706.03762.pdf` 实际解析成功，提取 39497 字符；`tests/test_pdf.py` 3 项通过。 |
| AC-2（FR-2 四维度结构化） | PASS | `backend/app/schemas.py:72-92` `PaperAnalysis` 覆盖 summary(research_problem/method/contributions/conclusion)、experiments(datasets/baselines/metrics/key_results)、limitations/future_work、keywords/tags；`backend/app/analysis.py:34-51` 提示词 schema 一致；`test_analyze_single_paper` 校验字段通过。 |
| AC-3（FR-3 语言 zh/en） | PASS | `backend/app/schemas.py:102-113` language 限定 `^(zh\|en)$`，默认 zh；`backend/app/analysis.py:32` `_LANGUAGE_LABEL` zh→中文/en→English；`test_analyze_language_controls_prompt`、`test_analyze_default_language_is_zh` 通过。 |
| AC-4（FR-4 批量逐篇+状态） | PASS | `backend/app/analysis.py:227-252` 顺序逐篇执行，逐篇写 running/done/failed；`POST /api/analyze/batch`(`main.py:160`) 先置 pending 再入 BackgroundTasks；`test_analyze_batch_runs_sequentially` 通过。 |
| AC-5（FR-5 对比综述） | PASS | `backend/app/analysis.py:255-307` 基于已存分析生成 common_themes/differences/research_gaps/summary；`test_review_returns_comparative_result`、`test_review_requires_at_least_two_papers` 通过。 |
| AC-6（FR-6 入库+覆盖更新） | PASS | `backend/app/database.py:23-40` 建 analyses/reviews 表；`upsert_analysis`(`:177`) 用 `ON CONFLICT(arxiv_id) DO UPDATE` 覆盖；`test_analysis_overwrites_previous_result` 通过。 |
| AC-7（FR-7 前端详情） | PASS | `frontend/src/components/AnalysisDrawer.tsx:188-221` 展示总结/实验/局限/关键词标签结构化视图。 |
| AC-8（FR-8 Markdown 导出） | PASS | `backend/app/export.py:13/75` 单篇与综述导出；`GET /api/analyses/{id}/export`、`GET /api/reviews/{id}/export`(`main.py:198/237`)；`test_export_analysis_markdown`、`test_export_review_markdown` 通过。 |
| AC-9（FR-9 进度/状态展示） | PASS | `AnalysisDrawer.tsx:23-28` STATUS_META + 轮询(`:71-84`)；`App.tsx:68-85` `pollAnalysisStatuses`；`PaperTable.tsx:14-19` 分析状态列。 |
| AC-10（NFR-2 长文本分块） | PASS | `backend/app/analysis.py:28-29,112-138` `chunk_text`（12000 字符 + 200 重叠）+ 分块分析后合并(`:201-224`)；`test_chunk_text_long`、`test_analyze_paper_text_chunks_and_merges` 通过。 |
| AC-11（NFR-3 密钥安全） | PASS | analyses/reviews 表无 api_key 列（实测 PRAGMA：analyses `['id','arxiv_id','content','language','status','created_at','updated_at']`）；全仓（排除 node_modules/.venv/data）grep `sk-...`/硬编码 api_key 无命中（仅测试文件 fake key 与 spec-001 记录）；`backend/app` 无 print/log 输出密钥；`test_analyses_and_reviews_have_no_api_key_column` 通过。 |

其它核验：
- **路由遮蔽**：`POST /api/analyze/batch` 注册于 `POST /api/analyze/{arxiv_id}` 之前（实测路由表顺序），无遮蔽。
- **spec-001 回归**：全量 pytest 45 passed（含 test_api/test_arxiv/test_database/test_llm/test_llm_config）。
- **前端构建**：`npm run build` 通过（tsc + vite，3038 模块）。
- **真实 PDF**：`1706.03762.pdf`（Attention Is All You Need）实际提取 39497 字符成功，与实施报告一致。

发现问题：无阻塞问题。仅一处非阻断观察——`run_analysis_job` 的 `except Exception` 静默吞掉异常不落日志（`analysis.py:251-252`），不影响功能与 AC。
