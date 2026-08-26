# 实施计划：多平台搜索与本地 PDF 上传（spec-013）

## 任务拆分

1. 搜索源抽象：`SearchProvider` 接口 + arXiv/SemanticScholar/BaiduXueshu/Cnki 实现。
2. 多平台聚合：并发搜索、结果合并、fallbacks 降级。
3. 搜索接口改造：`platforms` 参数 + 响应含 fallbacks。
4. 本地 PDF 上传：multipart 上传 → PyMuPDF 提取 → LLM 元数据提取 → 返回 pdf_token + 元数据（暂不入库）。
5. 上传确认：`upload/confirm` 接收用户编辑后的元数据 + pdf_token 入库。
6. 前端：上传 PDF → 可编辑表单审查/修改 → 确认保存；搜索表单平台多选、fallback 外链展示。
7. Paper 模型 `source` 字段 + 数据库兼容。
8. LLM 工具 platform 参数。
9. 测试。

## 实施顺序

搜索源抽象 → 聚合 → 接口 → PDF 上传 → 数据模型 → 前端 → 工具 → 测试。

## 涉及文件/模块

- `backend/app/search/`（新增 provider 模块 + 聚合）。
- `backend/app/arxiv.py`（改造为 provider 或复用）。
- `backend/app/main.py`、`schemas.py`、`database.py`（source 字段、upload 接口）。
- `backend/app/agent/tools.py`（platform 参数）。
- `frontend/src/components/SearchForm.tsx`、`PaperWorkspace.tsx`、`api.ts`、`types.ts`。
- `tests/` 新增用例。

## 技术要点

- SearchProvider：`name` + `async search(query, max_results) -> List[Paper]`。
- Semantic Scholar：`https://api.semanticscholar.org/graph/v1/paper/search?query=...`（httpx）。
- 百度学术/知网：requests 抓搜索结果页解析标题/作者/摘要；超时 + UA；失败返回 fallback（外链 URL）。
- 聚合：`asyncio.gather` 各 provider，合并 papers，收集 fallbacks。
- 上传 PDF：`POST /api/papers/upload`（UploadFile）→ 存临时/本地 → PyMuPDF 提取 → LLM 提取元数据（标题/作者/摘要/日期，JSON + pydantic）→ upsert papers（source="upload"）。
- Paper `source` 字段：DB 补列 `_migrate`，默认 "arxiv"。
- 前端平台多选：Checkbox.Group，全选/部分，传入 platforms。
- 工具 platform 参数：search_papers/search_by_topic 加 `platforms: Optional[List[str]]`。

## 风险与应对

- 爬虫反爬：UA + 超时 + 降级外链。
- 知网爬虫极不稳定：以外链为主。
- 多平台字段归一化：缺字段置空。
