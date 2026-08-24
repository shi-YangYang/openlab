# 实施计划：创新点设计（spec-004）

## 任务拆分

1. 数据模型与存储：`innovations` 表（迁移幂等）+ schemas（InnovationPoint、InnovationRecord 等）。
2. 创新点生成模块（单篇/多篇，复用 analyses/reviews 作为输入，结构化输出 + 校验重试 + 超时）。
3. 异步后台任务 + 进度（progress/status/error），生成接口 + 查询 + 导出。
4. 前端：生成入口（论文库页选中论文 → 生成创新点）、创新点展示、数量配置、语言切换、导出。
5. 测试。

## 实施顺序

存储 → 生成逻辑 → 接口 → 前端 → 测试。

## 涉及文件/模块

- `backend/app/`（新增 innovation 模块，扩展 database/main/schemas）。
- `frontend/src/`（新增创新点展示组件，扩展 PaperWorkspace/App）。
- `tests/` 新增创新点测试。

## 技术要点

- `innovations` 表：`id, arxiv_ids(TEXT JSON), content(TEXT JSON), language, status, error, progress, created_at`。
- 生成逻辑参考 `analysis.generate_review`：单篇取该论文 analysis（或摘要回退）；多篇取多篇 analysis（或摘要回退）拼装输入。
- 结构化输出用 JSON + pydantic 校验（手写 JSON 更稳），重试；`ChatOpenAI` 加 `request_timeout`。
- 异步后台任务 + progress（0→50→100），失败写 error。
- 接口：`POST /api/innovations`、`GET /api/innovations/{id}`、`GET /api/innovations/{id}/export`。

## 风险与应对

- 创新点质量：提示词明确要求「有依据、可追溯、不空泛」。
- JSON 解析失败：校验 + 重试 + 失败记录 error。
