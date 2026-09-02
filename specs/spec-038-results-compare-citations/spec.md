# Spec：实验结果对比 + 引用导出（spec-038）

## 元信息

- **Spec 编号**：`spec-038-results-compare-citations`
- **状态**：`completed`
- **创建日期**：2026-08-31
- **类型**：中大 Spec（后端提取/解析 + 前端对比视图与导出）
- **来源**：科研闭环缺口分析——"设计→执行"已有，"结果分析"缺失；引用导出为科研刚需
- **负责人**：协调开发 Agent

## 现状（已核实）

- `experiment_runs` 表：id/experiment_id/server_id/mode/status/current_step/log_path/pid/launch_command/steps_json/error/created_at/updated_at；训练以 nohup 后台运行，日志存 `data/experiment_runs/{run_id}.log`；monitor 检测进程退出后 `_emit_status("succeeded")`（experiment_runner.py:463）。**无 metrics 概念**。
- `update_experiment_run(run_id, **fields)` 通用更新器（db/experiments.py:208）。
- 前端：PaperWorkspace 已有 `selectedIds` 多选；ExperimentHistoryList 有 runsColumns 表格。
- papers 表：arxiv_id/title/authors(JSON)/categories/published/url/source，baidu/cnki 来源元数据可能不全。

## 需求描述

### A. 实验结果对比

- FR-1 **Metrics 提取器**（新建 `backend/app/metrics_extractor.py`）：
  - 启发式正则提取常见 ML 指标：`key=value` / `key: value` / `key value` 模式（loss/acc/accuracy/f1/precision/recall/mAP/AUC/bleu/rouge/perplexity/pearson/spearman 及带前缀变体 val_/test_/best_ 等，大小写不敏感；忽略 epoch/step/iter/it/s/lr 等非指标键）；
  - 每个指标取**最后一次出现**（最终值）；数值转 float；`%` 后缀保留在数值中（如 95.2），key 归一为小写下划线；
  - 解析失败/无命中返回 `{}`，绝不抛错（启发式）。
- FR-2 **自动提取 + 存储**：run 状态变为 `succeeded` 时自动解析 `log_path` 并写入新列 `experiment_runs.metrics TEXT`（JSON：`{key: value}`；`_migrate` 加列）。历史已完成的 run 不回填（可用手动重解析）。
- FR-3 **API**（routes/experiments.py）：
  - run 详情 schema 增加 `metrics`（dict 或 None）；
  - `POST /api/experiment-runs/{id}/metrics/extract`：手动重新解析（覆盖存储）→ 返回 metrics；
  - `PUT /api/experiment-runs/{id}/metrics`：手动编辑覆盖（body 为 JSON 对象，值须可转 float）；
  - `POST /api/experiment-runs/compare`：body `{ids: [...]}`（2-10 个）→ `{runs: [{id, experiment_title, mode, status, server_id, duration_seconds, created_at, metrics, error}], metric_keys: [并集，排序]}`；duration = updated_at - created_at（秒，尽力解析）；id 不存在 404。
- FR-4 **前端对比视图**（ExperimentHistoryList）：
  - runs 表格加行选择（checkbox），选中 ≥2 出现「对比」按钮 → Modal 对比表：行 = metric_keys 并集 + 基础信息行（状态/耗时/服务器/时间），列 = 各 run（表头含 experiment_title + run id）；无该指标的格显示 `-`；
  - 运行详情区显示提取到的 metrics（Tag 列表：`loss=0.12`）+「重新解析」按钮。
- FR-5 **手动编辑**：对比 Modal 中每个数值格双击可编辑（回车保存调 PUT；失败 toast）。（若实现代价过大可降级为详情区编辑，报告中说明取舍。）

### B. 引用导出（BibTeX / GB/T 7714）

- FR-6 **后端**（新建 `backend/app/citations.py`）：
  - `POST /api/papers/export/citations` body `{arxiv_ids: [...], format: "bibtex"|"gbt7714"}` → `text/plain; charset=utf-8` 附件下载（`Content-Disposition: filename=papers.bib` / `references.txt`）；ids 为空 400；
  - BibTeX：`@article{key, title={}, author={A and B and C}, year={}, journal={arXiv preprint arXiv:XXXX.XXXXX}（source=arxiv 时）/ url 对应 note, url={}}`；key = `首作者姓小写+年份+标题首词`，重复加 `-a/-b` 后缀；LaTeX 特殊字符转义（`& % # _`）；
  - GB/T 7714：`[序号] 作者1, 作者2, 等. 标题[J/OL]. 年份[2026-08-31]. URL.`（作者 >3 取前 3 + "等"；无年份/URL 字段跳过对应段）；
  - 元数据缺失容错：authors/published 为空时生成不含该字段的合法条目。
- FR-7 **前端**：PaperWorkspace 工具栏加「导出引用」Dropdown（BibTeX / GB/T 7714），基于 `selectedIds`（≥1 启用）调 API，fetch blob 触发浏览器下载。

## 非功能需求

- NFR-1：零新依赖；metrics 解析为启发式且永不抛错。
- NFR-2：`metrics` 列对旧数据为 NULL → schema/detail 返回 None，前端显示"未提取"。

## 验收标准

- AC-1：提取器单测覆盖多种日志格式（`loss=0.1`、`Acc: 95.2%`、`Epoch 3 - f1_score 0.88`、`val_loss 0.45`）且取最终值；无关行不误提（`epoch 3`、`lr 0.001` 不进指标）。
- AC-2：succeeded 自动提取入库；`POST .../extract` 重解析；`PUT` 手动编辑生效。
- AC-3：compare 接口返回并集 metric_keys 与各 run 概要；不存在的 id 404。
- AC-4：BibTeX 输出正确（key 去重、转义、arXiv journal 格式、缺字段容错）。
- AC-5：GB/T 7714 格式正确（>3 作者 et al.、无字段跳过）。
- AC-6：前端对比 Modal 与导出按钮可用；build 通过。
- AC-7：pytest 全量通过。
