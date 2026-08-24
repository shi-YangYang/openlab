# 验收标准与验收记录：本地搜索过滤 + LLM 连通性测试 + 布局优化（spec-006）

## 验收标准

- AC-1（对应 FR-1）：论文库搜索框能按标题/作者即时过滤。
- AC-2（对应 FR-2）：搜索页搜索框能过滤结果。
- AC-3（对应 FR-3）：历史页两个 tab 的搜索框能过滤（搜索历史按 query、创新点历史按 arxiv_id）。
- AC-4（对应 FR-4）：连通性测试能测表单当前值，返回成功/失败与耗时。
- AC-5（对应 FR-5）：论文库页无多余空白、无多余垂直滚动条。
- AC-6（对应 NFR-1）：连通性测试有超时、不打印密钥、不保存配置。
- AC-7（对应 NFR-2）：本地过滤不触发后端请求。

## 验收步骤

1. 启动后端与前端。
2. 论文库/搜索页输入关键字，验证按标题/作者过滤。
3. 历史页两个 tab 输入关键字，验证过滤。
4. 设置页填配置点「连通性测试」，验证成功/失败提示与耗时。
5. 观察论文库页底部无多余空白、无多余垂直滚动条。
6. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 无 | AC-1~7 全部通过，pytest 92 passed，前端 build 通过 |

## 验收结论

PASS。AC-1~7 全部满足，无回归。

- AC-1 PASS：`frontend/src/components/PaperWorkspace.tsx:30-40` 按标题/作者（toLowerCase 子串）过滤，论文库复用该组件（`App.tsx:152-157`）。
- AC-2 PASS：搜索页同样复用 `PaperWorkspace`（`App.tsx:145-149`），同一过滤逻辑。
- AC-3 PASS：`SearchHistoryList.tsx:76-80` 按 query；`InnovationHistoryList.tsx:108-114` 按 arxiv_ids。
- AC-4 PASS：`LlmConfigForm.tsx:69-92` 用 `form.getFieldsValue()` 当前值测试，`130-143` 展示成功耗时/失败信息；后端 `main.py:247-290` 返回 ok/message/latency_ms。
- AC-5 PASS：`App.tsx` 由 `<Layout style={{ minHeight: '100vh' }}>` 改为 `<Layout>`（git diff 确认）。
- AC-6 PASS：`main.py:266` `httpx.AsyncClient(timeout=15.0)`；无打印 api_key；未调用 `save_config`；错误经 `_redact` 脱敏。
- AC-7 PASS：过滤为纯客户端 `useMemo`，`onChange` 仅 `setKeyword`，无后端请求。

测试：`pytest -q` 92 passed；`npm run build`（tsc && vite build）通过。独立脚本验证：空配置→ok=false；mock 成功→ok=true+latency_ms；HTTP 401 错误不含真实 api_key；未写入 llm_config.json。
