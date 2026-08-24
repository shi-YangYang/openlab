# 技术栈与技术约束

> 本文件为技术栈的规划与约束。标注「待确认」的项需在与用户沟通并记录决策后确定。

## 总体架构

- 前后端分离的 Web 系统（**已确认**）。
- 后端负责科研 Agent 核心逻辑、LLM 编排、任务调度与 SSH 部署，可运行在本地 Windows，通过 PowerShell 调用 SSH 连接远程服务器。
- 前端负责交互界面、流程可视化与结果展示。

## 已确认决策

- 论文数据源：arXiv。
- LLM 提供方：OpenAI 兼容 API（可切换 DeepSeek/通义/GPT 等）。
- 用户规模：个人自用，无需多用户/权限体系。

## 后端（已确认框架）

- 语言/框架：Python + FastAPI（**已确认**）。
- LLM 编排：LangChain（**已确认**，`langchain` + `langchain-openai`，`ChatOpenAI` 自定义 base_url 保持 OpenAI 兼容）。
- 任务调度：待确认（如 Celery / APScheduler / RQ）。
- SSH 连接：通过本地 PowerShell 内置 SSH（**已确认**）；实现方式待确认。

## 前端（已确认）

- 框架：React + TypeScript（**已确认**）。
- 构建工具：Vite（**已确认**）。
- UI 组件库：Ant Design（**已确认**）。
- 状态管理：待确认（如 zustand / Redux）。

## 数据存储

- 主数据库：SQLite（**已确认**，个人自用起步）。
- 文献元数据：SQLite（**已确认**）；PDF 全文：本地文件目录（**已确认**）。
- 缓存/队列：待确认（如任务调度需要，Redis）。

## 测试与质量

- 测试框架：后端 pytest，前端 Vitest + Testing Library（建议）。
- 验收脚本统一存放于 `tests/`。

## 约束

- 选择的技术栈需记录到 `.ai/decisions/`。
- 优先选择生态成熟、社区活跃、便于开源的方案。
- 所有外部依赖需评估许可证兼容性（与 MIT 许可证兼容）。
- 涉及密钥（LLM API Key、SSH 凭据等）不得硬编码或提交到仓库。
