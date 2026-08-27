# spec-022 Agent 交互与论文库体验修复决策

## 决策标题

确定 bug 修复与 UX 改进一批（10 项）的具体方案。

## 元信息

- **日期**：2026-08-27
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-022-usability-batch

## 背景与问题

协调开发 Agent 对产品全面走查后归纳出 3 个 bug、5 个 UX 问题、2 个改进点，经用户确认全部纳入本次修复。

## 决策

1. **分析按钮未下载态禁用**：`paperActionColumn` 中「分析」按钮在 `statusMap[arxiv_id] !== 'downloaded'` 时禁用（Tooltip「请先下载」）；百度学术仍隐藏该按钮。
2. **重复上传同名 PDF 可清理**：上传来源论文（source=upload）允许在论文库直接删除（已有能力），补充：同文件名再次上传时提示已存在同名记录（按原始文件名记录到 title 不可靠，改为后端 confirm 响应带 `duplicate_of: arxiv_id|None`；前端提示「已存在相似上传记录」，仍允许继续）。
3. **agent 页模型列表随当前配置组刷新**：LlmConfigForm 保存成功后广播 `storage` 事件（localStorage 写时间戳）；AgentPage 监听并重新拉取 getLlmConfig 刷新模型/思考强度选项。
4. **消息气泡加时间戳**：assistant 气泡底部小字显示本轮完成时间；user 气泡右下角显示发送时间。Turn 结构加 `time: string`。
5. **表格分页可调**：PaperTable 分页改 `showSizeChanger: true`、`pageSizeOptions: [10,20,50,100]`。
6. **中断后状态语义**：会话列表里 interrupted 会话标题旁加橙色 Tag「已中断」；输入框 placeholder 提示「可继续发送新指令」。前端 stopped 事件后 message.info 明确提示。
7. **失败的工具调用默认展开**：Collapse 的 defaultActiveKey 包含 status==='error' 或 'rejected' 的条目 key。
8. **危险命令参数展示优化**：审批 Modal 对 `run_command`/`run_shell_command` 类参数，若有 `command` 字段则以等宽代码块单独大字展示命令原文，其余 JSON 折叠在下方。
9. **失败一键重试**：
   - 分析页失败时 Alert 内加「重试分析」按钮（复用 handleAnalyze 同语言）；
   - 综述页 failed 时显示「重试」（createReview 同参）;
   - 创新点页 record?.id 失败时按钮回为「生成创新点」可重发（天然支持，确认 UI 文案即可）。
10. **历史三页统一过滤**：搜索历史页、实验方案历史页补齐与创新点历史一致的关键词过滤输入框（按各自可检索字段过滤）。

## 理由

- 1/6/7 针对的是真实误操作路径，成本极低收益明确。
- 2 采用提示而非硬阻断，尊重「就是想再传一份」的场景。
- 3 用 storage 事件做跨组件通知是最小改动，不引入全局状态库。

## 影响与后果

- Turn 类型与 WS done/stopped 事件不动，仅前端本地状态加字段。
- 上传响应 schema 增加可选 duplicate_of 字段，向后兼容。
