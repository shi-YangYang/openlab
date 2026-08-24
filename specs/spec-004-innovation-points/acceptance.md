# 验收标准与验收记录：创新点设计（spec-004）

## 验收标准

- AC-1（对应 FR-1）：基于单篇论文分析可生成创新点。
- AC-2（对应 FR-2）：基于多篇论文对比综述可生成创新点。
- AC-3（对应 FR-3）：每个创新点含标题、描述、创新依据、预期贡献。
- AC-4（对应 FR-4）：生成数量可配置（1-10，默认 3），实际生成数量符合。
- AC-5（对应 FR-5）：输出语言 zh/en 可切换。
- AC-6（对应 FR-6）：创新点结果入库 SQLite 并可查询。
- AC-7（对应 FR-7）：前端结构化展示创新点。
- AC-8（对应 FR-8）：可导出创新点 Markdown。
- AC-9（对应 NFR-2）：密钥不入库、不硬编码、不打印。
- AC-10（对应 NFR-4）：LLM 调用配置了超时。

## 验收步骤

1. 启动后端与前端。
2. 选一篇已分析论文，生成创新点，验证数量与字段。
3. 选多篇论文生成创新点，验证基于综述生成。
4. 配置数量（如 5）与语言（en），验证生效。
5. 查询入库结果，导出 Markdown。
6. 运行 pytest 通过。

## 验收记录

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 无阻塞问题；仅前端 build 存在 chunk >500kB 的性能提示（非错误，属既有现象） | AC-1~10 全部通过，无回归，可进入下一环节 |

## 验收结论

- **结论**：PASS
- **测试**：后端 `pytest` 82 passed（含 test_innovation.py 12 条用例）；前端 `npm run build` 通过（tsc + vite）。
- **逐条判定**：
  - AC-1（单篇生成）PASS：`innovation.generate_innovations` 复用 `database.get_analysis`/摘要回退组装单篇输入；`tests/test_innovation.py::test_single_paper_innovation` 通过。
  - AC-2（多篇生成）PASS：循环组装多篇 analyses；`test_multi_paper_innovation` 通过。
  - AC-3（字段齐全）PASS：`schemas.InnovationPoint` 含 title/description/basis/expected_contribution；`test_innovation_record_schema_fields` 及实际运行确认 4 字段齐全。
  - AC-4（数量 1-10，默认 3）PASS：`InnovationRequest.count=Field(default=3)` + 接口 `1<=count<=10` 校验；`test_innovation_count_validation`、`test_innovation_default_count_is_3`、`test_innovation_count_controls_result` 通过。
  - AC-5（语言 zh/en）PASS：`language=Field(pattern="^(zh|en)$")`；非法语言实测 422；`test_innovation_language_controls_prompt` 通过。
  - AC-6（入库并可查询）PASS：`innovations` 表 + `insert_innovation/get_innovation/list_innovations`；实测入库后 GET 返回 done/progress 100。
  - AC-7（前端结构化展示）PASS：`InnovationModal.tsx` 结构化渲染标题/描述/依据/预期贡献；入口在共享 `PaperWorkspace`（搜索页与论文库均可用，`App.tsx` 两处 workspace 均传入 `onOpenInnovation`）。
  - AC-8（导出 Markdown）PASS：`export.innovations_to_markdown` + `GET /api/innovations/{id}/export`；`test_innovation_export_markdown` 通过。
  - AC-9（密钥不入库/不硬编码/不打印）PASS：`innovations` 表无 api_key 列，实测记录 JSON 无 api_key/sk-；密钥仅经 `get_effective_config` 传给 ChatOpenAI。
  - AC-10（LLM 超时）PASS：`_chat` 中 `request_timeout=120.0`；`test_innovation_chat_sets_request_timeout` 通过。
- **不回归判定**：PASS。搜索/下载/分析/综述/历史/LLM 配置相关用例（全套 82 条）全部通过。
- **发现问题**：无。
- **阻塞项**：无。
