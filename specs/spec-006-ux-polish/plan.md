# 实施计划：本地搜索过滤 + LLM 连通性测试 + 布局优化（spec-006）

## 任务拆分

1. 后端：`POST /api/llm/test` 连通性测试接口（超时、不打印密钥、返回 ok/message/latency_ms）。
2. 前端：论文库/搜索页共享的本地过滤（PaperWorkspace 加搜索框，按标题/作者过滤 papers）。
3. 前端：历史页两个 tab 的本地过滤（SearchHistoryList 按 query；InnovationHistoryList 按 arxiv_id）。
4. 前端：设置页「连通性测试」按钮 + 结果展示（用表单当前值）。
5. 前端：布局空白修复（Layout minHeight 调整）。
6. 测试。

## 实施顺序

后端测试接口 → 本地过滤 → 连通性测试前端 → 布局修复 → 测试。

## 涉及文件/模块

- `backend/app/main.py`、`schemas.py`（连通性测试接口）。
- `frontend/src/components/PaperWorkspace.tsx`、`SearchHistoryList.tsx`、`InnovationHistoryList.tsx`、`LlmConfigForm.tsx`、`App.tsx`、`api.ts`、`types.ts`。
- `tests/` 新增连通性测试用例。

## 技术要点

- 连通性测试：`httpx`（带 timeout，如 15s）调用 `{base_url}/chat/completions`，payload 用最小消息 + `max_tokens=1`；成功返回 ok=true + latency；失败捕获异常返回 ok=false + 错误信息；不打印 api_key。
- 本地过滤：用 React state 存关键字，对 papers/历史列表做 `filter`（标题/作者/query/arxiv_id 的 toLowerCase 子串匹配），纯客户端。
- 布局：`App.tsx` 的 `Layout` 去掉/减小 `minHeight: 100vh`，消除分页器下方空白。

## 风险与应对

- 连通性测试网络异常：try/except 捕获并返回友好错误；设置超时。
