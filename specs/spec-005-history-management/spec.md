# Spec：历史管理（spec-005）

## 元信息

- **Spec 编号**：`spec-005-history-management`
- **状态**：completed（已完成）
- **创建日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-innovation-points.md`
- **负责人**：协调开发 Agent

## 背景与动机

spec-003 已有「历史搜索」页（搜索历史 + 快照恢复），spec-004 已把创新点存到 `innovations` 表，但没有历史浏览入口。需要一个统一的历史管理页，集中管理搜索历史与创新点历史，并保证历史条目可稳定重新展示当时的内容。

## 目标

- 统一「历史」页，tab 切换「搜索历史」「创新点历史」。
- 创新点历史：列表展示（时间、来源论文、创新点数量、状态），点击弹窗查看当时完整快照。
- 稳定重新展示：历史条目存完整快照，查看时不重新计算。

## 范围

### 包含（In Scope）

- 后端：`GET /api/innovations` 列表接口（元信息 + 数量，不含完整 content）。
- 前端：把「历史搜索」页升级为「历史」页，tab：搜索历史（现有）+ 创新点历史（新增）。
- 创新点历史列表 + 点击弹窗查看详情（只读快照）。

### 不包含（Out of Scope）

- 其它历史类型（综述历史等，留待扩展）。
- 创新点历史的编辑/重新生成（如需可复用 spec-004 生成）。

## 需求描述

### 功能需求

- FR-1：「历史」页统一管理，tab 切换「搜索历史」「创新点历史」。
- FR-2：创新点历史列表展示（时间、来源论文、创新点数量、状态）。
- FR-3：点击创新点历史条目，弹窗查看当时完整快照（稳定，不重新生成）。
- FR-4：搜索历史保持现有快照恢复能力（spec-003）。
- FR-5：创新点历史持久化（复用 `innovations` 表），重启后保留。

### 非功能需求

- NFR-1：列表接口不含完整 content（减小响应），详情接口返回完整 content。
- NFR-2：密钥安全沿用（不入库、不硬编码）。

## 数据结构约定

- 复用 `innovations` 表（`id, arxiv_ids, content, language, status, error, progress, created_at`）。
- 列表项：`InnovationHistoryItem`（id、arxiv_ids、创新点数量、language、status、created_at）。

## 后端接口草案

- `GET /api/innovations` — 创新点历史列表（元信息 + 数量，不含 content）。
- `GET /api/innovations/{id}` — 详情（含完整 content）。（已存在）

## 依赖与前置条件

- spec-003（搜索历史页）。
- spec-004（`innovations` 表与详情/导出接口）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- 历史条目随使用增多，可后续加分页/删除。
