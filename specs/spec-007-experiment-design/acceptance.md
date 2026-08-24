# 验收标准与验收记录：实验设计（spec-007）

## 验收标准

- AC-1（对应 FR-1）：基于创新点可生成实验方案。
- AC-2（对应 FR-2）：基于论文分析可生成实验方案。
- AC-3（对应 FR-3）：方案含假设、目标、数据集、基线、评价指标。
- AC-4（对应 FR-4）：生成数量可配置（1-3，默认 1），实际数量符合。
- AC-5（对应 FR-5）：输出语言 zh/en 可切换。
- AC-6（对应 FR-6）：实验方案入库 SQLite 并可查询。
- AC-7（对应 FR-7）：前端结构化展示实验方案。
- AC-8（对应 FR-8）：可导出实验方案 Markdown。
- AC-9（对应 NFR-2）：密钥不入库、不硬编码、不打印。
- AC-10（对应 NFR-4）：LLM 调用配置了超时。

## 验收步骤

1. 启动后端与前端。
2. 从创新点历史选一个创新点生成实验方案，验证字段与数量。
3. 从论文库选论文生成实验方案，验证基于分析生成。
4. 配置数量（如 2）与语言（en），验证生效。
5. 查询入库结果，导出 Markdown。
6. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-24 | PASS | 无（AC-1~10 全部通过，后端 pytest 105 passed，前端 build 通过，独立脚本 27/27 通过，无回归） | 可进入下一环节 |

## 验收结论

- **结论**：PASS
- **验收轮次**：1
- **验收日期**：2026-08-24
- **验收依据**：spec.md（FR-1~8 / NFR-1~4）、acceptance.md（AC-1~10）、决策记录 2026-08-24-experiment-design.md。
- **逐条判定**：
  - AC-1（创新点生成方案）：PASS。`experiment.generate_experiments`（backend/app/experiment.py:146-153）取创新点 content 作输入；test_experiment_from_innovation + 独立脚本验证字段齐全、count=2。
  - AC-2（论文分析生成方案）：PASS。`_assemble_papers_inputs`（experiment.py:116-131）取 analyses，无分析时回退 title+abstract；test_experiment_from_papers + 独立脚本验证两分支均 done。
  - AC-3（方案字段）：PASS。`ExperimentPlan`（schemas.py:213-218）含 hypothesis/goal/datasets/baselines/metrics；test_experiment_record_schema_fields 通过。
  - AC-4（数量 1-3 默认 1）：PASS。`ExperimentRequest.count` 默认 1（schemas.py:238），接口校验 1<=count<=3（main.py:492-493）；test_experiment_count_validation + 独立脚本 count 0/4 -> 400。
  - AC-5（语言 zh/en）：PASS。language pattern ^(zh|en)$（schemas.py:239），系统提示词按语言切换；test_experiment_language_controls_prompt + 独立脚本验证 en/zh 提示词。
  - AC-6（入库 SQLite 可查询）：PASS。experiments 表 + insert/get/list_experiment（database.py:59-70, 524-603）；test_experiment_* 通过。
  - AC-7（前端结构化展示）：PASS。ExperimentModal.tsx 展示假设/目标/数据集/基线/指标 + 进度 + 数量 1-3 + 语言 + 导出；入口在 InnovationHistoryList.tsx（「实验方案」按钮）与 PaperWorkspace.tsx（「生成实验方案」按钮）。
  - AC-8（导出 Markdown）：PASS。`experiments_to_markdown`（export.py:142-175）+ 接口 GET /api/experiments/{id}/export（main.py:543-559）；test_experiment_export_markdown + 独立脚本验证 content-type/attachment/内容。
  - AC-9（密钥安全）：PASS。密钥仅由 get_effective_config 读取传入 ChatOpenAI（experiment.py:81-92），experiments 表无 api_key 字段，独立脚本验证含密钥记录 JSON 不含密钥。
  - AC-10（LLM 超时）：PASS。`request_timeout=LLM_REQUEST_TIMEOUT_SECONDS`（experiment.py:91）；test_experiment_chat_sets_request_timeout 通过。
- **测试运行**：后端 `pytest -q` → 105 passed（2.87s）；前端 `npm run build` → 通过（vite build，仅 chunk 体积警告，无错误）；独立验证脚本 27/27 通过。
- **无回归**：spec-002/004 等既有测试全部包含在 105 passed 中，前端 build 无类型错误。
- **发现问题**：无阻塞项。仅前端 build 提示 chunk > 500kB 的体积警告（非错误，不影响功能）。
