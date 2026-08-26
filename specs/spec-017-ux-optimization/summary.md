# Spec 017 总结

## 元信息

- **Spec 编号**：`spec-017-ux-optimization`
- **状态**：completed（已完成）
- **创建日期**：2026-08-26
- **关联决策**：`.ai/decisions/2026-08-26-ux-optimization.md`

## 目标

1. 服务器详情页功能区折叠，默认全部折叠。
2. 论文分析、对比综述、生成创新点、生成实验方案由弹窗改为二级页面，带面包屑。
3. 浏览器标签标题统一为「openlab科研agent」。

## 技术栈

- 纯前端改造，无后端改动、无新增依赖。
- AntD `Collapse` + `Breadcrumb` + react-router（`useParams` / `useSearchParams`）。

## 需求清单

- FR-1：服务器详情页四区块折叠，默认全折叠。
- FR-2：论文分析页 `/papers/:arxivId/analysis`。
- FR-3：对比综述页 `/papers/review?ids=...`。
- FR-4：生成创新点页 `/papers/innovation?ids=...`。
- FR-5：生成实验方案页 `/papers/experiment?ids=...` 或 `?innovation_id=...`。
- FR-6：入口按钮改为路由跳转。
- FR-7：标题改为 `openlab科研agent`。

## 接口与路由

- 新增路由：`/papers/:arxivId/analysis`、`/papers/review`、`/papers/innovation`、`/papers/experiment`。
- 复用现有 API，无新增后端接口。

## 验收结果

- 实施 Agent：前端 `npm run build` 通过，后端 `pytest tests -q` 243 passed。
- 验收 Agent：AC-1~AC-6 + 回归全部 **PASS**；安全与范围核查 PASS（仅前端与 spec 文档改动，无后端、无敏感文件）。
- 两个非阻塞观察项（见「遗留问题」）。

## 决策引用

- `.ai/decisions/2026-08-26-ux-optimization.md`

## 使用方式

- 服务器详情页各区块折叠，点击展开。
- 论文库「分析」「对比综述」「生成创新点」「生成实验方案」均跳转二级页面，可直达 URL、刷新不丢参。

## 遗留问题（非阻塞观察项）

1. 服务器详情折叠后，Collapse 面板 label 与展开后内层 Card 标题重复（如「监控」出现两次），属轻度 UI 冗余。
2. 论文分析页不再回写工作区表格「分析」状态列（原弹窗通过 `onStatusChange` 回写）；返回论文库时不会自动刷新分析状态，需重新搜索或整页刷新才恢复。

以上两项均为验收时的非阻塞观察项，可后续按需优化。
