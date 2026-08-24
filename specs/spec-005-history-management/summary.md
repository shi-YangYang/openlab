# spec-005 汇总：历史管理

> 本文档汇总 spec-005 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-005-history-management`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24

## 背景与目标

统一管理历史数据：把「历史搜索」页升级为「历史」页（tab：搜索历史 / 创新点历史），并提供创新点历史列表 + 稳定快照查看。

## 功能需求清单（FR-1 ~ FR-5，全部完成）

- FR-1：历史页 tab 切换「搜索历史」「创新点历史」。
- FR-2：创新点历史列表展示（时间、来源论文、数量、状态）。
- FR-3：点击查看完整快照（不重新生成）。
- FR-4：搜索历史快照恢复保持（spec-003）。
- FR-5：创新点历史持久化（复用 innovations 表）。

非功能：NFR-1 列表不含 content、详情含 content；NFR-2 密钥安全。

## 后端接口

- `GET /api/innovations` — 创新点历史列表（不含 content，含 paper_count/innovation_count）
- `GET /api/innovations/{id}` — 详情（含 content）
- `DELETE /api/innovations/{id}` — 删除单条
- `DELETE /api/innovations` — 删除全部

## 验收结果

验收标准 AC-1 ~ AC-6 **全部 PASS**（轮次 1）。`pytest` 86 passed，前端 build 通过。

## 验收后追加的细节

1. 创新点历史单条删除（`DELETE /api/innovations/{id}` + 前端按钮）。
2. 创新点历史「删除全部」（`DELETE /api/innovations` + 前端按钮，与搜索历史「清空全部」一致）。
3. 来源论文弹窗改为与论文库一致的表格（复用 `basePaperColumns`），标题可点链接、分类用 Tag。
4. 来源论文表格增加「分析」「查看论文」操作按钮（复用 `paperActionColumn`），可直接跳去分析或看原文。
5. 来源弹窗 arxiv_id 单行不换行、弹窗加宽。

## 使用方式

「历史」页 → tab 切换「搜索历史」/「创新点历史」；创新点历史可查看快照、查看来源论文（含分析/查看论文操作）、单条删除、删除全部。
