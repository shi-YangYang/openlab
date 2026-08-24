# 实施计划：文献搜索与下载（arXiv）

## 任务拆分

1. 后端项目骨架（FastAPI + 配置 + 目录结构）。
2. arXiv 搜索模块（调用 arXiv API，返回结构化结果）。
3. LLM 主题拆解模块（LangChain ChatOpenAI，主题 → 检索式）。
4. PDF 下载与元数据入库模块（SQLite）。
5. 前端搜索界面与结果展示（React + TypeScript + Vite + Ant Design）。
6. LLM 平台预设（后端预设列表 + 前端下拉选择 + 自定义配置持久化）。
7. 一键启动脚本 `start.ps1`（检测/安装依赖 + concurrently 合并输出启动前后端）。

## 实施顺序

后端骨架 → 搜索 → LLM 拆解 → 下载入库 → 前端。

## 涉及文件/模块

- `backend/`（新增）。
- `frontend/`（新增，React + TypeScript + Vite + Ant Design）。

## 技术要点

- arXiv API：`https://export.arxiv.org/api/query`（Atom 格式）。
- SQLite 表 `papers`：`id, arxiv_id, title, authors, abstract, categories, published, pdf_url, local_pdf_path, status, created_at`。
- LLM 调用：LangChain ChatOpenAI（自定义 base_url 保持 OpenAI 兼容），平台预设 + 自定义。
- 异步任务：PDF 下载耗时，采用 FastAPI BackgroundTasks 或简单队列。

## 风险与应对

- arXiv 限速：加请求间隔与重试。
- PDF 下载失败：记录状态，允许重试。
