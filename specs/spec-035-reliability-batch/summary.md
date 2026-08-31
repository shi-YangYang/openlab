# Summary：spec-035-reliability-batch

## 完成日期

2026-08-31

## 实施内容（可靠性修复批，优化清单一之二）

1. **下载并发化 + 启动恢复**：`run_download_job` 串行 → `Semaphore(3)` + gather（单篇进度/失败/幂等语义不变，闭包防串篇）；lifespan 启动时残留 `downloading` → failed（"应用重启中断"）。
2. **审批 pending 持久化**：`agent_sessions` 加 `pending TEXT` 列（_migrate）；设置/清除同步写库；`get_session_detail` 输出 `{tool, args, forbidden}`；重启/重开后前端自动恢复审批弹窗；approve 后清库；启动不清 pending（合法跨重启状态）。
3. **JSON 解析统一**：新建 `llm_json.py`（三层容错 + pydantic 校验 + container 参数）；替换 6 文件 8 调用点，重试循环保留；llm.py 失败回退原文语义保留。
4. **实验运行僵尸态**：启动清理 running/paused → interrupted（paused 经核实依赖内存 driver，无法跨重启恢复，一并重置）。
5. **前端 3 项遗留**：折叠分组 key 改 djb2 内容 hash（time|text前32|首toolCall，纯工具组防撞 key）；权限下拉加载失败显示"点击重试"错误态；`pending_approval`/持久化 pending 带 `forbidden`（黑名单 any() 判定）→ 弹窗隐藏「本会话允许」+ 警示行。

## 验证结果

- pytest 全量 **403 passed**（新增 16 用例：并发耗时断言、清理、pending round-trip、解析矩阵、僵尸 run）；`npm run build` 通过。
- 验收独立 e2e：pending 持久化 round-trip（含 model/reasoning_effort/forbidden）完整、approve 后清空、清理函数实测；验收产生的测试数据已全部清除。

## 已知低优先级遗留（不阻塞）

1. djb2 32 位 hash 理论可碰撞（实际概率极低）。
2. 流式文本跨越 32 字符边界时分组 key 变化一次、组重挂载（展开状态瞬时丢失）。
3. llm.py `_parse_content` 失败回退改为含 fence 的原文（语义更准确，非缺陷）。

## 遗留事项

- 无。优化清单剩余项（真 RAG、Docker 沙箱、重复工具调用去重、外键迁移）见优化分析清单一之三，待后续 spec。
