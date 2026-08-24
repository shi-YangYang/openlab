# 后端技术栈决策

## 决策标题

确定后端语言/框架与数据存储方案。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-001-paper-search-download

## 背景与问题

项目采用前后端分离 Web 系统，需确定后端语言/框架与数据存储方案。

## 备选方案

- 后端：Python + FastAPI / Node.js + NestJS / Python + Django。
- 数据存储：SQLite / PostgreSQL。

## 决策

1. **后端**：Python + FastAPI。
2. **数据存储**：SQLite（个人自用起步）。
3. **文献存储**：元数据入库 SQLite，PDF 全文存本地文件目录。

## 理由

- FastAPI 便于对接 arXiv API、论文解析，且后续 SSH（Paramiko）、AI 生态都是 Python 优势。
- 个人自用场景，SQLite 单文件最简，无需额外部署数据库服务。

## 影响与后果

- 后端技术栈据此搭建，前端技术栈待确认。
- 后续若需要并发任务队列，再引入 Redis/任务调度。
