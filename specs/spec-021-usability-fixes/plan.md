# Spec 021 实施计划

## 概览

小步快跑：3 个批次（后端限流、搜索表单文案、两处 UI 修正）+ 测试。

## 批次划分

### 批次 1：后端 Semantic Scholar 限流应对

- `backend/app/config.py`：`settings.semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")`。
- `backend/app/search/semantic_scholar.py`：
  - 常量：`MAX_RETRIES=2`、退避序列 `(1.0, 2.0)`、`RETRY_AFTER_CAP=5.0`。
  - `search()` 包重试循环：429/5xx/网络异常时按 `Retry-After`（解析失败取指数退避，封顶 5s）等待后重试；client 由调用方注入时可复用同一 client 重试。
  - 配置了 API Key 时请求头加 `x-api-key`。
- `backend/app/search/aggregator.py`：
  - 新增 `_describe_failure(exc)`：LoginRequired/LoginExpired 维持原判定；HTTPStatusError(429) → 「官方接口限流(429)，已自动重试仍未恢复」；其他 → 脱敏后的前 120 字符摘要。
  - fallback 条目附加 `message`。
- `backend/app/schemas.py`：`SearchFallback.message: Optional[str] = None`。
- `backend/.env.example`：补 `SEMANTIC_SCHOLAR_API_KEY=` 及注释（申请入口）。

### 批次 2：前端搜索表单

- `frontend/src/types.ts`：`SearchFallback.message?: string | null`。
- `frontend/src/App.tsx`：降级提示行展示 `f.message`。
- `frontend/src/components/SearchForm.tsx`：
  - Radio.Button 文案改「直接搜索」「AI 智能搜索」，各自包 Tooltip（说明见 FR-7）；
  - query label 动态化；占位提示替换。

### 批次 3：Agent 输入框 + 模型列表行宽

- `frontend/src/components/AgentPage.tsx`：消息输入框 `autoSize={{minRows:4, maxRows:10}}`。
- `frontend/src/components/LlmConfigForm.tsx`：
  - 单模型行容器改 `display:flex`；模型 id 固定宽、上下文长度固定宽、「思考强度」`flex:1 minWidth:300`、删除按钮固定——行高不再被换行撑高。

### 测试

- `tests/test_search_providers.py`：
  - 429→成功 的重试用例（fake client 计数）；
  - 连续 3 次 429 → 抛出；
  - 带 API Key 时请求头含 `x-api-key`；
  - `Retry-After` 封顶逻辑（可用 monkeypatch sleep 避免 UI 等待）。
- `tests/test_search_history.py` 或聚合相关测试：fallback message 断言（在聚合层用假 provider 抛 429 验证 message 文案与 need_login 不变）。
- 既有 semantic_scholar 归一化/登录类测试回归。

## 文件清单

- 后端：`config.py`、`search/semantic_scholar.py`、`search/aggregator.py`、`schemas.py`、`.env.example`
- 前端：`types.ts`、`App.tsx`、`components/SearchForm.tsx`、`components/AgentPage.tsx`、`components/LlmConfigForm.tsx`
- 测试：`tests/test_search_providers.py` 等

## 验证方式

- 后端：`pytest tests -q`；前端：`npm run build`；手工冒烟按 acceptance.md。
