# Spec：元数据补全 + 重复调用保护（spec-039）

## 元信息

- **Spec 编号**：`spec-039-metadata-backfill-dedup`
- **状态**：`completed`
- **创建日期**：2026-09-02
- **类型**：小 Spec（后端为主 + 前端一个按钮）
- **来源**：spec-038 真实测试观察（库内论文缺作者/年份 → 引用导出不完整）+ 优化清单遗留
- **负责人**：协调开发 Agent

## 现状（已核实）

1. papers 表 15 篇中大部分缺 authors/published（BibTeX key 降级 `unknown*`、GB·T 无年份段）。arXiv 来源论文可用现有 `ArxivClient`（backend/app/arxiv.py，内置 3s 限速 + 指数退避重试）按 arxiv_id 精确回填。
2. Agent 循环（agent/agent.py `_run_loop`）对 LLM 返回的 tool_calls 无去重：模型偶发同参重复调用同一工具（尤其搜索/分析类），浪费 token 与时间。危险工具已有人工审批兜底。

## 需求描述

### A. 论文元数据补全

- FR-1：`backend/app/metadata_backfill.py`（或并入合适模块）：`backfill_metadata(limit=20) -> {updated, skipped_non_arxiv, unchanged, failed}`——
  - 选出 `source='arxiv'` 且 `authors IS NULL OR authors='[]' OR published IS NULL OR categories IS NULL` 的论文（id 升序，最多 limit 篇）；
  - 逐个调 ArxivClient 按 arxiv_id 查询（沿用内置限速/重试），命中则**仅更新元数据字段**（title/abstract/authors/categories/published/pdf_url——本地字段 local_pdf_path/status/progress/error 绝不动），更新后触发 FTS 同步（spec-037）；
  - 未命中/异常计 failed；baidu/cnki 来源计 skipped_non_arxiv；
  - 无缺失论文时返回全零计数（幂等）。
- FR-2：API `POST /api/papers/metadata/backfill`（同步执行，单次上限 20 篇 ≈ 限速下 ≤70s）→ 返回计数；前端按钮 loading 等待。
- FR-3：前端论文库工具栏加「补全元数据」按钮：调 API → 完成后刷新列表 + message.info(`已补全 N 篇`)；BibTeX/GB·T 导出随之完整。

### B. 重复工具调用保护

- FR-4：`_run_loop` 执行**非危险工具**前查重——在 `session.messages` 历史中查找是否存在**同名工具 + 规范化 JSON 参数完全相等**的历史调用；命中则**跳过实际执行**，直接回填 `ToolMessage(content="[重复调用已跳过] 与历史调用完全相同，此前结果：{上次结果前 800 字符}")`；
  - 危险工具（走审批）与沙箱执行类不做去重（人工确认过的调用尊重执行）；
  - 上次结果定位：历史 AIMessage.tool_calls 按序对应其后的 ToolMessage；
  - 参数规范化：`json.dumps(args, sort_keys=True, ensure_ascii=False)`。
- FR-5：去重命中记 INFO 日志（spec-034 日志体系）。

## 非功能需求

- NFR-1：零新依赖；backfill 沿用 ArxivClient 限速，不并发轰炸 arXiv。
- NFR-2：补全只写元数据字段，绝不覆盖本地状态。

## 验收标准

- AC-1：单测——mock ArxivClient：缺失论文被回填（authors/published/categories 更新、本地字段不动、FTS 同步被调）；baidu/cnki 计 skipped；arXiv 查无此 id 计 failed；无缺失时全零。
- AC-2：API 集成测试（TestClient）：POST backfill 返回计数；库列表刷新可见新元数据。
- AC-3：去重单测——同一非危险工具同参第二次调用不执行（ToolMessage 含"重复调用已跳过"与上次结果）；不同参数正常执行；危险工具不去重。
- AC-4：pytest 全量通过；前端 build 通过。

## 范围

- 包含：上述 A/B。
- 不包含：baidu/cnki 来源补全（无可靠元数据源）、标题模糊匹配补全、跨会话调用缓存。
