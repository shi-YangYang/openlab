# Spec：可靠性修复批（spec-035）

## 元信息

- **Spec 编号**：`spec-035-reliability-batch`
- **状态**：`completed`
- **创建日期**：2026-08-31
- **类型**：中 Spec（后端为主 + 少量前端）
- **来源**：代码库优化分析（清单二，6-10 项）
- **负责人**：协调开发 Agent

## 背景（均已核实）

1. 批量 PDF 下载为串行 for 循环（downloader.py:102）；进程崩溃后 `downloading` 状态永久残留（无启动恢复）。
2. Agent 审批挂起 `session.pending` 仅存内存——进程重启后丢失，用户消息悬挂无下文（spec-035 前提：消息本身已持久化）。
3. LLM JSON 解析的三层容错逻辑（剥 fence → 截取 → Pydantic 校验）在 7 处重复手写。
4. 实验运行 `_drivers` 仅内存，进程重启后 running 状态的 run 永久悬挂。
5. spec-032/033 验收记录的低危遗留：折叠分组 key 用消息索引（追加消息可能串组）、权限下拉加载失败无限 loading、pending_approval 事件不带黑名单标记。

## 需求描述

### FR-1 下载并发化 + 启动恢复

- `run_download_job` 由串行 for 改为受控并发（`asyncio.Semaphore(3)`），保持：单篇进度回调写库、失败原因记录、幂等跳过已下载、重试逻辑不变。
- 应用启动（lifespan）：将所有状态为 `downloading` 的论文置为 `failed`，失败原因"应用重启中断"。

### FR-2 审批 pending 持久化

- `agent_sessions` 表新增 `pending TEXT` 列（沿用现有 `_migrate` 加列机制）。
- `session.pending` 设置/清除时同步写库（新增 `sessions.set_pending(session_id, pending_dict_or_None)`；序列化 JSON，含 tool_calls/model/reasoning_effort）。
- `get_session_detail` 返回项增加 `pending`（无则 None）；`AgentSessionDetail` schema 同步。
- 前端 `refreshDetail`：`detail.pending` 非空 → 设置 `pendingApproval`（重启/重开/重连后自动恢复审批弹窗）；approve 走现有 WS 流程（`run_approve` 从持久化 pending 恢复，清 pending 时同步清库）。
- 启动**不**清 pending（与 running 不同：pending 是合法的跨重启状态）。

### FR-3 JSON 解析统一

- 新建 `backend/app/llm_json.py`：`parse_llm_json(text: str, model_cls: type[BaseModel])`——剥 code fence → 直接 `json.loads` → 失败截取首尾 `{}`/`[]` 再 parse → `model_cls.model_validate` → 任一步失败抛 `ValueError`（带阶段信息）。
- 替换 7 处重复实现（analysis.py、innovation.py、experiment.py、upload.py、llm.py decompose_topic、agent/tools.py 部署命令生成等——以 grep 实际命中为准），各文件的重试循环保留、仅调用共享解析器。
- 行为保持兼容：替换前后对同样输入的解析结果一致（以现有测试与新增对照用例保证）。

### FR-4 实验运行僵尸态恢复

- 应用启动（lifespan）：扫描 `experiment_runs`——`running` 状态置 `interrupted`（error 信息"应用重启，运行中断"）；`paused` 状态视 `resume_with_action` 是否依赖内存 driver 决定：依赖则同样置 `interrupted`，不依赖则保留（实施者核实后二选一，报告中说明）。

### FR-5 前端遗留修复（3 项）

- 折叠分组 key 稳定化：改为基于分组内容的稳定 key（如组内首 turn 的 `time + text 前 32 字符` 的 hash），消息追加不影响既有分组的手动展开状态。
- 权限下拉（AgentPermissionSelect）：`usePermissions` 加载失败时显示可重试的错误态（Tooltip 提示 + 点击重试），不再无限 loading。
- `pending_approval` WS 事件与持久化 pending 增加 `forbidden: bool`（权限引擎命中黑名单时为 true）；前端弹窗对 `forbidden` 隐藏「本会话允许」按钮（后端 fail-closed 语义不变，仅 UX 诚实化）。

## 非功能需求

- NFR-1：不引入新依赖；不改变 API 响应既有字段语义（仅新增字段）。
- NFR-2：下载并发的进度写入需线程/协程安全（沿用现有 db 连接模式）。
- NFR-3：pytest 全量通过 + 新增用例；`npm run build` 通过。

## 验收标准

- AC-1：3 篇下载任务并发执行（mock 下载耗时，总耗时明显小于串行 3 倍单耗时；进度与失败路径正常）。
- AC-2：写残留 downloading 论文 → 启动清理 → 状态 failed + 原因"应用重启中断"。
- AC-3：设置 pending → 重启进程（重放 lifespan）→ `get_session_detail` 返回 pending → 前端逻辑恢复弹窗（前端部分 CODE-REVIEW）；approve 后 pending 清库。
- AC-4：`parse_llm_json` 单测：正常 JSON / 带 fence / 带前后噪声 / 非法输入抛 ValueError；7 处替换后 pytest 全量通过证明行为兼容。
- AC-5：写残留 running/paused 实验 run → 启动清理 → interrupted（paused 的处理方式在报告中说明）。
- AC-6：前端 3 项修复 build 通过 + CODE-REVIEW（分组 key 稳定性推演、错误态渲染、forbidden 隐藏按钮）。
- AC-7：pytest 全量通过；`npm run build` 通过。
