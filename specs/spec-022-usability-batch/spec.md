# Spec：Agent 交互与论文库体验修复批（spec-022）

## 元信息

- **Spec 编号**：`spec-022-usability-batch`
- **状态**：completed（已完成）
- **创建日期**：2026-08-27
- **关联决策**：`.ai/decisions/2026-08-27-usability-batch.md`
- **负责人**：协调开发 Agent

## 背景与动机

产品走查发现的 3 个 bug、5 个 UX 问题、2 个改进点，需一次性收口。

## 目标

见决策记录 10 条，逐项落实。

## 范围

### 包含（In Scope）

- 决策记录中的全部 10 项。

### 不包含（Out of Scope）

- 全局状态管理引入、后端架构调整、移动端适配。

## 需求描述

### 功能需求

- FR-1（bug）：论文表格「分析」按钮仅在 `status==='downloaded'` 时可用；未下载时禁用 + Tooltip「请先下载该论文」；baidu_xueshu 来源仍不显示按钮。
- FR-2（bug）：PDF 上传 confirm 成功但服务端检测到同名上传时，响应含 `duplicate_of: <arxiv_id>`；前端 message.warning 提示「已存在相似的上传记录」，不阻断。
- FR-3（bug）：配置组保存成功后写 `localStorage.setItem('openlab.llm.updated', String(Date.now()))`；AgentPage `storage` 事件监听刷新模型下拉与思考强度选项。
- FR-4：Turn 增加 `time?: string`；user 气泡右下角、assistant 气泡底部以 12px 次要色显示时间（HH:mm）。
- FR-5：PaperTable 分页 `{pageSize:10, showSizeChanger:true, pageSizeOptions:[10,20,50,100]}`。
- FR-6：会话列表 interrupted 会话加 `<Tag color="orange">已中断</Tag>`（sessions 接口 status 已有该值）；stopped 后 message.info('任务已中断')。
- FR-7：agent 工具调用 Collapse 中失败项（status 为 error/rejected）默认展开。
- FR-8：审批 Modal 内，当 args 含 command 字段时，命令原文以深色等宽块置顶展示（大号等宽字体），完整 JSON 折叠其下（默认收起）。
- FR-9：一键重试：
  - PaperAnalysisPage failed Alert 加「重试分析」按钮；
  - ReviewPage failed Alert 加「重试综述」按钮；
  - InnovationPage 失败态确认可再次点击生成（若已是如此，仅确保文案不变）。
- FR-10：SearchHistoryList 与 ExperimentHistoryList 增加与创新点历史一致的头部关键词过滤输入框（搜索历史按 query 过滤；实验方案历史按来源/语言过滤）。

### 非功能需求

- NFR-1：所有 schema 变更向后兼容（新字段可选）。
- NFR-2：`pytest tests -q` 与 `npm run build` 通过。

## 数据结构约定

- `PaperUploadResult` / confirm 响应增加可选 `duplicate_of: Optional[str] = None`。
- Turn（前端本地）增加 `time?: string`。

## 依赖与前置条件

- spec-013/015/016~021 的既有实现。

## 验收标准

详细步骤见 `acceptance.md`。

## 风险与开放问题

- storage 事件仅跨 tab 触发的问题规避：同页 LLM 表单保存后由 App 层回调兜底刷新（实施时二选一保证生效即可）。
