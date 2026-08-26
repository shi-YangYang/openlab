# Spec：内容与功能优化（spec-017）

## 元信息

- **Spec 编号**：`spec-017-ux-optimization`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-ux-optimization.md`
- **负责人**：协调开发 Agent

## 背景与动机

1. 服务器详情页功能块（监控/部署/环境配置/终端）逐块堆积，用户需滚动很久才能定位目标。
2. 论文「分析」「生成创新点」「生成实验方案」「对比综述」均为弹窗，交互割裂；服务器「详情」已是二级页面，体验更好，应统一为二级页面。
3. 浏览器标签标题「openlab · 文献搜索与下载」过时且不准确，应统一为「openlab科研agent」。

## 目标

- 服务器详情页各功能区折叠，默认全部折叠，按需展开。
- 论文分析、对比综述、生成创新点、生成实验方案由弹窗改为二级页面，带面包屑。
- 浏览器标签标题统一为「openlab科研agent」。

## 范围

### 包含（In Scope）

- 服务器详情页功能区折叠（默认全折叠）。
- 分析、对比综述、生成创新点、生成实验方案四个弹窗改为二级页面。
- 入口按钮改为路由跳转。
- 浏览器标题修改。

### 不包含（Out of Scope）

- 折叠状态持久化（记住上次展开/折叠）。
- 创新点历史/实验方案历史中的「查看」只读弹窗（保留为弹窗）。
- 后端改动（本次纯前端）。
- 移动端/响应式专项优化。

## 需求描述

### 功能需求

- FR-1：服务器详情页用 AntD `Collapse` 折叠「监控」「部署」「环境配置」「终端」四个区块，`defaultActiveKey=[]`（默认全部折叠），点击标题展开对应区块；各区块内容保持现状。
- FR-2：新增「论文分析」二级页面，路由 `/papers/:arxivId/analysis`：
  - 面包屑「论文库 / {论文标题}」，第一段可点击返回 `/library`；论文标题通过 `arxivId` 查询（复用 `listPapers([arxivId])`），未查到则回退显示 `arxivId`。
  - 内容复用原 `AnalysisModal` 逻辑（语言选择、触发分析、状态轮询、结果展示、导出 Markdown）。
- FR-3：新增「对比综述」二级页面，路由 `/papers/review?ids=id1,id2,...`，面包屑「论文库 / 对比综述」；复用原 `ReviewModal` 逻辑。
- FR-4：新增「生成创新点」二级页面，路由 `/papers/innovation?ids=id1,id2,...`，面包屑「论文库 / 生成创新点」；复用原 `InnovationModal` 逻辑。
- FR-5：新增「生成实验方案」二级页面，路由：
  - 来源论文：`/papers/experiment?ids=id1,id2,...`，面包屑「论文库 / 生成实验方案」。
  - 来源创新点：`/papers/experiment?innovation_id=123`，面包屑「创新点历史 / 生成实验方案」。
  - 复用原 `ExperimentModal` 逻辑（`sourceType` 由 `innovation_id` 是否存在推断）。
- FR-6：入口改造：
  - `PaperTable` 的「分析」按钮改为跳转 `/papers/{arxivId}/analysis`。
  - `PaperWorkspace` 的「对比综述」「生成创新点」「生成实验方案」按钮改为跳转对应路由（携带已选 `ids`；未选择时行为与现有一致，即对比综述作用于全部、创新点/实验方案要求至少选 1 篇）。
  - `InnovationHistoryList` 的「实验方案」按钮改为跳转 `/papers/experiment?innovation_id={id}`。
- FR-7：浏览器标题：`frontend/index.html` 的 `<title>` 改为 `openlab科研agent`。

### 非功能需求

- NFR-1：二级页面直接访问 URL 可正常渲染（不依赖路由 state）；多选论文 id 通过查询参数逗号分隔传递，刷新不丢失。
- NFR-2：页面卸载时清理轮询定时器与进行中的状态，避免内存泄漏（复用现有 modal 的 cleanup 逻辑）。
- NFR-3：改造后 `npm run build` 通过；`pytest tests -q` 不受影响（无后端改动）。

## 路由与数据结构约定

- 新增路由：
  - `/papers/:arxivId/analysis`
  - `/papers/review`（query: `ids`）
  - `/papers/innovation`（query: `ids`）
  - `/papers/experiment`（query: `ids` 或 `innovation_id`）
- 面包屑第一段链接：论文相关 → `/library`；来源创新点的实验方案 → `/history/innovation`。

## 依赖与前置条件

- 依赖 spec-002（分析）、spec-004（创新点）、spec-007（实验方案）、spec-008/009（服务器详情）、spec-015（路由结构）。
- 复用现有 API 与 hooks，无新增后端接口、无新增依赖。

## 验收标准

概述见下，详细步骤见 `acceptance.md`。

- 服务器详情页默认全折叠，可逐块展开。
- 四个功能由弹窗变为二级页面，面包屑正确、可直接访问 URL、刷新不丢参。
- 标题显示为「openlab科研agent」。
- 前端 build 通过，后端测试通过。

## 风险与开放问题

- 从弹窗改页面后，轮询与卸载清理需正确处理，避免定时器泄漏。
- 多选论文 id 较多时 URL 较长，一般可接受；如需更长可后续改为状态传递。
- 面包屑标题查询需容错（论文已删除等情况回退显示 arxivId）。
