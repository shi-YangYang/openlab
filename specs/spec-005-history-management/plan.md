# 实施计划：历史管理（spec-005）

## 任务拆分

1. 后端：`GET /api/innovations` 列表接口（元信息 + 数量，不含 content）+ schemas（InnovationHistoryItem）。
2. 前端：把「历史搜索」页升级为「历史」页（tab：搜索历史 / 创新点历史）。
3. 前端：创新点历史列表组件（时间、来源论文、数量、状态），点击弹窗查看完整快照。
4. 测试。

## 实施顺序

后端列表接口 → 历史页 tab 改造 → 创新点历史列表与详情 → 测试。

## 涉及文件/模块

- `backend/app/main.py`、`database.py`、`schemas.py`（新增列表接口）。
- `frontend/src/App.tsx`（历史页 tab）、新增 `InnovationHistoryList.tsx`、复用 `InnovationModal` 或新建只读详情。
- `tests/` 新增历史列表测试。

## 技术要点

- `database.list_innovations()` 返回元信息（不含 content）或详情（含 content）需区分；列表接口用不含 content 的查询。
- 历史页用 AntD `Tabs` 切换「搜索历史」「创新点历史」。
- 创新点历史点击详情复用只读展示（标题/描述/依据/预期贡献），不触发重新生成。

## 风险与应对

- 列表响应大小：列表不含 content，详情按需加载。
