# 实施计划：实验设计（spec-007）

## 任务拆分

1. 数据模型与存储：`experiments` 表（迁移幂等）+ schemas（ExperimentPlan、ExperimentRecord 等）。
2. 实验方案生成模块（创新点/论文两来源，复用 innovations/analyses 作为输入，结构化输出 + 校验重试 + 超时）。
3. 异步后台任务 + 进度（progress/status/error），生成接口 + 查询 + 导出。
4. 前端：生成入口（创新点历史页「生成实验方案」+ 论文库页「生成实验方案」）、方案展示、数量配置、语言切换、导出。
5. 测试。

## 实施顺序

存储 → 生成逻辑 → 接口 → 前端 → 测试。

## 涉及文件/模块

- `backend/app/`（新增 experiment 模块，扩展 database/main/schemas）。
- `frontend/src/`（新增实验方案展示组件，扩展创新点历史/论文库入口）。
- `tests/` 新增实验设计测试。

## 技术要点

- `experiments` 表：`id, source_type, innovation_id, arxiv_ids, content, language, status, error, progress, created_at`。
- 生成逻辑：source_type=innovation 取该创新点 content 作输入；source_type=papers 取多篇 analyses（或摘要回退）作输入。
- 结构化输出用 JSON + pydantic 校验 + 重试；`ChatOpenAI` 加 `request_timeout`。
- 异步后台任务 + progress（0→50→100），失败写 error。
- 接口：`POST /api/experiments`、`GET /api/experiments/{id}`、`GET /api/experiments/{id}/export`。

## 风险与应对

- 方案质量：提示词要求「具体、可执行、与来源一致」。
- JSON 解析失败：校验 + 重试 + 失败记录 error。
