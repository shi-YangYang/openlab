# spec-013 多平台搜索与本地 PDF 上传决策

## 决策标题

确定 spec-013 的平台范围、无 API 平台实现方式与上传 PDF 的处理。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-013-multi-source-upload

## 决策

1. **平台范围**：arXiv（已有）+ Semantic Scholar + 百度学术 + 知网 CNKI。
2. **无 API 平台实现**：爬虫抓取，失败时降级为外链跳转（openlab 内搜后跳转到平台搜索结果页）。
3. **上传 PDF**：提取元数据（标题/作者/摘要）回填表格，之后用户可选用 spec-002 做完整 4 维度分析。

## 理由

- Semantic Scholar 有开放 API，较稳定；百度学术/知网无 API，只能爬虫+降级外链。
- 上传 PDF 先回填元数据、再可选完整分析，兼顾快速入库与深度分析。

## 影响与后果

- 新增搜索源抽象（SearchProvider）+ 多平台聚合。
- Paper 模型新增 `source` 字段；搜索结果含 fallbacks（外链）。
- 上传 PDF 复用 PyMuPDF + LangChain LLM。
- 前端搜索表单与 LLM 搜索工具增加平台多选参数。
