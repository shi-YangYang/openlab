# 前端技术栈决策

## 决策标题

确定前端框架与 UI 组件库。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-001-paper-search-download

## 背景与问题

项目采用前后端分离 Web 系统，需确定前端框架与 UI 组件库。

## 备选方案

- 框架：React + TypeScript / Vue 3 + TypeScript / 仅后端 API。
- UI 组件库：Ant Design / Tailwind CSS / MUI / 不引入。

## 决策

1. **框架**：React + TypeScript + Vite。
2. **UI 组件库**：Ant Design。

## 理由

- React 生态成熟、TS 类型支持好，是科研工具类 Web 的常见选择。
- Ant Design 组件齐全、风格现代，能快速搭建搜索与流程展示界面。

## 影响与后果

- 前端项目据此搭建，后端已确认为 Python + FastAPI。
- 状态管理方案（如 zustand / Redux）待需要时再确认。
