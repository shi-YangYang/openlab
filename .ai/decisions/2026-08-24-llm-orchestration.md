# LLM 编排与多平台支持决策

## 决策标题

LLM 编排层采用 LangChain，并支持多平台预设 + 自定义。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-001-paper-search-download（补充）

## 背景与问题

- 项目后续涉及文献分析、假设生成、实验设计等多步 LLM 编排，需避免重复造轮子。
- 需支持几乎所有提供 OpenAI 兼容接口的大众平台（DeepSeek、阿里、硅基流动、智谱等）。

## 备选方案

- LLM 编排层：LangChain / LangGraph / httpx 直连。
- 多平台支持：平台预设 + 自定义 / 仅文档说明 / 维持现状。

## 决策

1. **LLM 编排层**：LangChain（`langchain` + `langchain-openai`），用 `ChatOpenAI` 自定义 `base_url` 保持 OpenAI 兼容。
2. **多平台支持**：内置平台预设（base_url + 默认模型）+ 可自定义。

## 理由

- 项目本质是科研 Agent 框架，后续 RAG、Agent、工具调用可直接复用 LangChain。
- `ChatOpenAI` 的 `base_url` 可指向任意 OpenAI 兼容服务，天然支持多平台。

## 影响与后果

- spec-001 的 `llm.py` 从 httpx 直连改为 LangChain `ChatOpenAI`。
- 增加平台预设机制（后端提供预设列表，前端下拉选择 + 自定义）。
- 新增依赖 `langchain`、`langchain-openai`。
