# Summary：spec-034-production-hardening

## 完成日期

2026-08-30

## 实施内容（生产化加固批）

1. **CI 测试门禁**：新建 `.github/workflows/test.yml`——push(main)/PR 触发，backend（windows-latest + py3.12 + pytest）与 frontend（Node 20 + npm run build）双 job 并行；pytest 依赖缺失项在 CI 步骤补装（requirements.txt 不动）。
2. **LLM 调用重试**：`llm.py` 新增 `ainvoke_with_retry`（try-import 防御式收集 httpx/openai 可重试异常，1s/2s 退避，warning 日志，不可重试直抛）；接入 agent 非流式回退、analysis/innovation/experiment/upload/decompose_topic；流式路径按 `got_first_chunk` 边界重试（首 chunk 前重启整个 astream，之后直抛）。
3. **标准日志**：app.py basicConfig（INFO）；埋点：启停、Agent run 生命周期、审批、实验管线每步、下载任务、权限写路径、未捕获异常堆栈；权限 load 逐请求路径刻意不加（防刷屏）。
4. **全局异常处理**：`exception_handler(Exception)` → logging.exception + 500 `{"detail": "Internal server error"}`；不拦截 HTTPException。
5. **LLM 超时补齐**：全库 9 处 `ChatOpenAI` 构造点全部 `request_timeout=120`（AST 扫描单测守护，新增构造点自动受检）。

## 验证结果

- pytest 全量 **387 passed**（378 + 新增 9：重试成功/耗尽/不可重试、流式边界、500 路径、AST timeout 扫描、caplog 日志）。
- 验收独立核对 FR-1~FR-5 全落实；无超范围改动、无新依赖、API 失败语义不变。
- AC-1（CI 实际运行）为 PUSH-VERIFY，随本次 push 观察首个 test workflow。

## 遗留事项

- 可重试异常集合覆盖 httpx+openai 传输层；接非 httpx 传输 provider 时需扩充。
- ruff/eslint 接入、下载并发、审批 pending 持久化等属后续批次（分析清单二/三）。
