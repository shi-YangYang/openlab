# Summary：spec-038-results-compare-citations

## 完成日期

2026-09-02

## 实施内容

### A. 实验结果对比（补完科研闭环"结果分析"环节）

1. **Metrics 提取器**（metrics_extractor.py 新建）：白名单正则（loss/acc/f1/mAP/bleu 等 + val_/test_/best_ 前缀变体，排除 epoch/step/iter/lr）；取最后出现值；`%` 保留数值；key 归一小写下划线；永不抛错。**词尾保护 `(?![\w.])` 防 `loss=0.12s` 误提**；正则保持 Python 3.10 兼容（实施中曾用 3.11+ 原子组，已修正为前瞻等价写法）。**管道表格解析**（真实测试补充）：识别 `epoch | train_loss | test_loss` 式表头 + 数据行，取最后一行为最终指标（epoch/step 列排除），与正则策略合并、表格优先；用户真实训练日志由此正确提取 `train_loss/test_loss`。
2. **存储与自动提取**：`experiment_runs.metrics TEXT` 列（_migrate）；`succeeded` 时自动解析 log_path 入库（异常仅 warning）；`set_experiment_run_metrics` 不动 updated_at（保 duration 准确）；历史 run 不回填（可手动重解析）。
3. **API**：run detail 含 metrics；`POST /{id}/metrics/extract`（重解析）；`PUT /{id}/metrics`（手动编辑，值校验 400）；`POST /compare`（ids 2-10，返回各 run 概要 + metric_keys 并集；路由注册在 /{run_id} 之前）。
4. **前端**：runs 表 rowSelection → 「对比」Modal（行=基础信息+指标并集，缺 `-`；**指标格双击编辑**，Enter 保存/Esc 取消/失败还原/清空删除）；详情 metrics Tags + 「重新解析」按钮。

### B. 引用导出

5. **citations.py 新建**：BibTeX（key=首作者姓+年+标题首词、-a/-b 去重、LaTeX 转义 `& % # _`、arXiv journal 格式、缺字段容错）与 GB/T 7714（>3 作者"等"、[J/OL]、无字段跳过）。
6. **API**：`POST /api/papers/export/citations`（text/plain 附件 papers.bib / references.txt；ids 空 400、format 非法 400）。
7. **前端**：PaperWorkspace 工具栏「导出引用」Dropdown（基于 selectedIds=arxiv_id，≥1 启用），blob 下载。

## 验证结果

- pytest 全量 **449 passed**（新增 24 + 正则边界 1 + 表格解析 3）；`npm run build` 通过。
- 验收独立 e2e：succeeded 自动提取→detail→compare 并集→PUT 编辑→导出响应头/内容全链路；**真实库复核无合成数据残留**（实施者测试泄漏事故已自行清理）。
- **真实日志端到端**：run#4（真实训练日志，竖线表格格式）经 `/metrics/extract` 正确提取 `{"train_loss": 0.223536, "test_loss": 0.18254}`（最后一轮）。
- **真实库冒烟**：BibTeX/GB·T 7714 用真实 3 篇论文导出格式正确；runs 列表正常。
- 观察项：用户库中部分旧论文缺作者/年份元数据（key 降级 unknown*），引用格式合法但不完整——属数据质量问题非功能缺陷。

## 已知低优先级遗留

- 前端对比 Modal 内 metric_keys 随删除指标重算（全空行边界已消除）。
- e2e 临时库位于系统 TEMP（已隔离，无污染）。

## 遗留事项

- 无阻塞。大工程清单剩余：Docker 沙箱、SQLite 外键/迁移、重复工具调用保护、（新增）论文元数据补全。
