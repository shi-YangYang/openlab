# Spec：论文库全文检索（spec-037）

## 元信息

- **Spec 编号**：`spec-037-library-fulltext-search`
- **状态**：`completed`
- **创建日期**：2026-08-31
- **类型**：中 Spec（后端 FTS + 前端论文库搜索入口）
- **来源**：优化清单三讨论收敛——不做向量/embedding，仅做零配置的库内全文检索
- **负责人**：协调开发 Agent

## 背景

论文库目前只能按列表浏览/翻页，无法在库内检索（"我库里哪些论文提到 X"要靠搜索页重新外部搜索）。每篇论文已有结构化分析（summary/keywords/tags），内容是现成的。决策：**不做向量**，用 SQLite 内置 FTS5 建全文索引，零配置零新依赖。

## 关键技术决策

- **tokenizer 用 `trigram`**（FTS5 内置）：unicode61 不分词中文（连续汉字成单 token，中文查询基本失效），trigram 支持中文子串匹配，SQLite 3.34+ 自带（Python 3.10+ 内置 SQLite 版本满足）。
- 索引内容：标题 + 摘要 + 分析摘要文本 + keywords + tags（有分析用分析，没分析用元数据兜底）。
- 同步机制：papers/analyses 变化时重建对应行（触发器难以覆盖 JSON 字段解析，用应用层同步：论文入库/删除、分析完成时更新 FTS 行）+ 提供手动重建接口。

## 需求描述

### 后端

- FR-1：新建 FTS5 虚拟表 `papers_fts`（`tokenize='trigram'`，contentless 或 external content 视实现取简），索引字段：`title`、`abstract`、`analysis_text`（分析摘要+keywords+tags 拼接）、`source`。
- FR-2：同步点——论文入库/上传确认/删除、分析完成/删除时同步 FTS 行（增删改保持一致）；提供 `POST /api/papers/search/rebuild` 手动全量重建（返回重建条数）。
- FR-3：检索接口 `GET /api/papers/search?q=...&limit=50`：FTS5 MATCH 查询（trigram 下天然支持子串），返回论文元数据 + 命中来源标注；空 q 返回 400；结果按 FTS rank 排序。
- FR-4：Agent 工具 `search_library`（新增）：库内全文检索，让 Agent 能回答"我库里哪些论文提到 X"（参数 q + limit，描述说明是库内检索非外部搜索）。

### 前端

- FR-5：论文库页（PaperWorkspace）顶部加库内检索框：回车/按钮触发，结果复用现有论文列表展示（含"清除检索回到全部"）；空态/无结果提示。

### 非功能

- NFR-1：零新依赖（FTS5 为 SQLite 内置；启动时探测可用性，不可用则功能降级返回明确错误，不阻塞应用）。
- NFR-2：中文子串查询可用（trigram 保证）；英文大小写不敏感。
- NFR-3：启动时对已有论文库自动全量建索引（幂等，空库跳过）。

## 验收标准

- AC-1：中文子串检索（如摘要含"注意力机制"能被"注意力"命中）；英文大小写不敏感。
- AC-2：分析完成后新分析内容可被检索（keywords/tags 命中）；论文删除后不再命中。
- AC-3：rebuild 接口幂等，重建后检索结果一致。
- AC-4：`search_library` 工具可被 Agent 调用并返回正确结果（mock 或真实路径单测）。
- AC-5：前端检索框可用、清除恢复全列表；build 通过。
- AC-6：pytest 全量通过（FTS 同步/检索/重建/Agent 工具单测）。
