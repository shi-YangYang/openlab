# 验收标准：spec-034-production-hardening

（与 spec.md 验收标准一致：AC-1 ~ AC-7，详见 spec.md 末节。补充验收方式说明：）

- AC-1 的 CI 实际运行在 push 后由协调 Agent 观察 GitHub Actions 结果确认（PUSH-VERIFY）。
- AC-2/3/4/6 以 pytest（含 caplog）实现自动化验收。
- AC-5 以 grep + 单测（构造 build_llm 检查属性）双验。
