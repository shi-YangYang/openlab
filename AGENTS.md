# AGENTS.md

本文件是 openlab 项目的项目级 Agent 说明与基础约束。所有参与本项目开发的 Agent（协调开发 Agent、实施 Agent、验收 Agent）在开始工作前必须先阅读本文件。

## 项目简介

openlab 是一个开源科研 Agent 框架，目标是将科研流程自动化，覆盖以下环节：

- **文献挖掘**：自动检索、收集与解析科研文献。
- **假设生成**：基于文献与数据自动生成科研假设。
- **实验设计**：自动设计实验方案。
- **SSH 服务器部署自动化**：自动将实验部署到远程 SSH 服务器并运行。

## 开发模式

本项目遵循 **SDD（规格驱动开发）** 流程，并融合多 Agent 协作开发模式。

### Agent 角色

- **协调开发 Agent**：主 Agent。负责与用户沟通、处理决策、编写和维护 Spec，以及调度和管理子 Agent。
- **实施 Agent**：子 Agent。负责按照已确认的 Spec 实施具体开发任务。
- **验收 Agent**：子 Agent。负责根据 Spec 独立检查和验收实施结果。

### 协作流程

1. 协调开发 Agent 与用户沟通需求，共同起草并完善 Spec。
2. Spec 确认后，由协调开发 Agent 创建实施 Agent 完成实施。
3. 实施 Agent 返回后，协调开发 Agent 创建新的验收 Agent 独立验收。
4. 验收未通过则创建新的实施 Agent 返工，再重新验收，直到通过。
5. 最终结果由协调开发 Agent 汇总后交用户审查。
6. Spec 通过最终验收后，协调开发 Agent 执行完成收尾（见 `.ai/workflows/completion.md`）：标记 `completed`、汇总 `summary.md`、安全核查；仅在用户明确要求提交后，才 commit 并 push。

### 职责边界

- 协调开发 Agent 不直接编写或修改业务代码（`frontend/`、`backend/`），只负责沟通、决策、Spec 维护与调度。
- 实施 Agent 负责编码，不负责验收。
- 验收 Agent 负责独立验收，不得代替实施 Agent 修改业务代码。
- 子 Agent 不得绕过协调开发 Agent 直接替用户做项目决策。
- 禁止子 Agent 再创建子 Agent。

## 目录结构

```
AGENTS.md
constitution/
  mission.md          # 项目使命和核心目标
  roadmap.md          # 项目路线图
  tech-stack.md       # 技术栈和技术约束
specs/                # Spec 目录，每个 Spec 使用单独子目录
docs/                 # 外部参考资料（DOCX、XLSX、JSON 等）
tests/                # 测试文件、验收脚本
.ai/
  decisions/          # 重要决策记录
  workflows/          # 多 Agent 协作工作流程
  prompts/            # Agent 初始化、任务分配、结果返回模板
  rules/              # Agent 需要遵守的项目约束
```

## 基础约束

- 凡存在不明确之处，禁止猜测；需要决策时向协调开发 Agent（或用户）询问。
- 重要决策记录到 `.ai/decisions/`。
- 重要对话结论、需求变化须留痕，不能只保存在对话上下文中。
- Spec 命名遵循 `specs/spec-001-short-name`、`specs/spec-002-short-name` 格式。
- 实施 Agent 不需要验收，任务完成后应立即删除该子 Agent。
- 当任务同时涉及前后端修改时，只派一个实施 Agent 实施，无需并行开多个实施 Agent。
- README 遵循 standard-readme 规范（见 `.ai/rules/documentation.md`）。

## Agent 必读文件约定

各子 Agent 初始化时，需按以下要求阅读文件：

1. **固定必读文件**：精确列出路径（如 `AGENTS.md`、相关 `constitution/*.md`、相关 `.ai/rules/*.md`）。
2. **当前任务必读文件**：对应 Spec、相关决策记录和任务交接文档。
3. **按条件必读文件**：返工记录、实施报告、验收报告等（视任务阶段而定）。

阅读顺序：固定必读文件 → 当前任务必读文件 → 按条件必读文件。冲突时以优先级更高的文件为准（Spec 与决策记录优先于一般约定）。
