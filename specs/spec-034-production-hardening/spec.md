# Spec：生产化加固批（spec-034）

## 元信息

- **Spec 编号**：`spec-034-production-hardening`
- **状态**：`completed`
- **创建日期**：2026-08-30
- **类型**：中 Spec（后端 + CI）
- **来源**：代码库优化分析（清单一，1-5 项）
- **负责人**：协调开发 Agent

## 背景（均已核实）

1. CI 仅 tag 打包，**pytest/前端 build 从未在 CI 执行**。
2. 全部 LLM 调用（agent/analysis/innovation/experiment/upload/decompose_topic）单次调用，**零重试**，网络抖动即任务失败。
3. 后端**零日志**（grep logging 零命中），排障无据。
4. FastAPI **无全局异常处理器**（app.py 仅 CORS），未捕获异常返回默认页面且无记录。
5. 部分 ChatOpenAI 实例未设 `request_timeout`：`llm.py:56-61`、`upload.py`、`translation.py`、`agent/tools.py:359-362`，存在无限挂起风险。

## 需求描述

### FR-1 CI 测试门禁（`.github/workflows/test.yml` 新建）

- 触发：push 到 main + pull_request。
- job `backend`（windows-latest，与开发环境同平台避免平台性失败）：setup Python 3.12 → `pip install -r backend/requirements.txt` → `pip install pytest pytest-asyncio httpx`（如未含于 requirements）→ 运行 `pytest backend/tests -q`（工作目录/环境变量按测试现有约定）。
- job `frontend`（windows-latest）：setup Node 20 → `npm install`（frontend）→ `npm run build`。
- 两 job 并行；任一失败则失败。

### FR-2 LLM 调用重试

- 新增共享重试助手（放 `backend/app/llm.py`）：`ainvoke_with_retry(llm, messages, max_retries=2)`——异常退避重试（1s、2s），仅对连接类/超时/限流/5xx 类异常（httpx.TimeoutException/ConnectError、openai APIConnectionError/RateLimitError/APITimeoutError/InternalServerError 及 langchain 等价异常，实现按 import 可用性防御）。
- 应用点（全部改为经助手调用）：
  - `agent/agent.py` `_invoke_llm`（流式路径特殊处理：**仅在收到首个 chunk 前**可整体重试；已产出 token 后失败不重试，直接抛出）；
  - `analysis.py`、`innovation.py`、`experiment.py`（各自的 chunk/生成调用）；
  - `upload.py`、`llm.py` 的 `decompose_topic`。
- 重试行为记 warning 日志（依赖 FR-3）。
- 最终失败仍抛原异常，由既有任务失败路径处理（不改变现有失败语义）。

### FR-3 标准日志

- `app/app.py` 模块级配置 `logging`（INFO，格式 `%(asctime)s %(levelname)s %(name)s %(message)s`），logger 名 `openlab`。
- 关键点埋点（克制，不逐请求刷屏）：应用启动/关闭、Agent run 开始/结束/异常、审批发起与结果、实验管线开始/每步结果/失败、LLM 重试触发与最终失败、下载任务开始/完成/失败、权限配置读写。
- 业务异常已有对外路径的（任务 failed + error 字段）不重复刷日志。

### FR-4 全局异常处理

- `app.py` 注册 `add_exception_handler(Exception)`：记录异常堆栈（logging）+ 返回 `JSONResponse({"detail": "Internal server error"})` 500。
- 不拦截 HTTPException（FastAPI 默认已处理）。

### FR-5 LLM 超时补齐

- `llm.py` 的 `build_llm` 与其余 3 处直接构造 `ChatOpenAI`（`upload.py`、`translation.py`、`agent/tools.py`）统一 `request_timeout=120.0`（与既有 120s 约定一致）。

## 非功能需求

- NFR-1：不引入新第三方依赖（retry 手写，不用 tenacity）。
- NFR-2：现有失败语义与 API 响应结构不变；重试仅增加韧性。
- NFR-3：pytest 全量通过 + 新增用例（重试助手、全局异常处理器、timeout 存在性）；CI yml 语法自检。

## 范围

- 包含：上述 5 项。
- 不包含：tracing/结构化日志框架、ruff/eslint 接入、队列、下载并发（后续批次）。

## 验收标准

- AC-1：`.github/workflows/test.yml` 存在且语法正确；本地无法验证 CI 运行（需 push 后观察，验收阶段允许标记 PUSH-VERIFY）。
- AC-2：mock LLM 前 2 次抛连接异常、第 3 次成功 → `ainvoke_with_retry` 返回成功且日志含 warning；3 次全失败 → 抛最后异常。
- AC-3：流式路径：首 chunk 前异常触发重试；首 chunk 后异常不重试直接抛。
- AC-4：`TestClient` 触发未处理异常（如临时路由抛 RuntimeError）→ 500 + `{"detail": "Internal server error"}`，日志含堆栈。
- AC-5：全库 `ChatOpenAI(` 构造点均有 `request_timeout`。
- AC-6：关键路径日志埋点生效（pytest caplog 抽查 agent 开始/LLM 重试）。
- AC-7：pytest 全量通过；`npm run build` 不涉及（前端零改动）。
