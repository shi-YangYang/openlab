# Spec：Agent 权限管理（spec-032）

## 元信息

- **Spec 编号**：`spec-032-agent-permissions`
- **状态**：`completed`
- **创建日期**：2026-08-30（修订 1：工具逐项开关 → Codex 式三级模式）
- **类型**：大 Spec（后端权限引擎 + 审批流扩展 + 设置页 UI）
- **负责人**：协调开发 Agent

## 背景与动机

当前 Agent 对 10 个工具（`DANGEROUS_TOOLS` 硬编码）一律暂停等待用户审批，包括本地沙箱内的代码执行等低风险操作，交互成本过高。需要一套分级权限管理系统。

参考 Codex 的三级权限模式（Full Access 等），以**全局模式**替代逐工具开关。

## 已确认的设计决策（用户拍板）

1. **权限粒度**：全局三级模式（见 FR-2），不做逐工具开关。
2. **安全底线不可绕过**：破坏性命令模式与高危工具在任何模式下都强制审批。
3. **本地沙箱默认放行**：标准模式下 `run_python_code` / `run_shell_command` 自动执行；远程命令按白名单。

## 现状（代码事实）

- 工具共 32 个；`tools.py` 的 `DANGEROUS_TOOLS`（10 个）+ `is_dangerous()` 决定是否审批：
  - 本地沙箱类：`run_python_code`、`run_shell_command`
  - 远程/部署/实验类：`run_command`（SSH 命令）、`deploy_code`、`deploy_upload`、`create_server`、`update_server`、`delete_server`、`run_experiment`、`stop_experiment_run`
  - 其余 22 个（搜索/下载/分析等）自动执行
- 审批流：agent 循环遇危险调用 → `session.pending` → WS `pending_approval` → `AgentApprovalModal`（允许/拒绝）→ `run_approve` 恢复。
- 本地配置存储模式：`backend/data/llm_config.json`（gitignored）+ `llm_config.py` 读写层。

## 需求描述

### 1. 三级权限模式

- FR-1：全局权限模式 `mode ∈ {"conservative", "standard", "full"}`：
  - `conservative`（保守）：全部 10 个工具均需审批（等同现行为），白名单不生效。
  - `standard`（标准，**默认**）：本地沙箱 2 工具自动执行；`run_command` 命中只读白名单自动执行；其余工具需审批。
  - `full`（完全访问）：所有工具自动执行，不弹审批。
- FR-2：**安全底线（任何模式不可绕过，硬编码不提供配置）**：
  - 工具黑名单 `FORBIDDEN_TOOLS = {"delete_server"}`：恒需审批。
  - 命令黑名单 `FORBIDDEN_COMMAND_PATTERNS`（对 `run_command`/`run_shell_command` 的命令串整串 fnmatch 匹配，不区分大小写）：`rm -rf /*`、`rm -rf ~*`、`mkfs*`、`dd if=*`、`shutdown*`、`reboot*`、`halt*`、`init 0`、`init 6`、`poweroff*`、`chmod -R 777 /*`、`* > /dev/sd*`、`fdisk*`、`wipefs*`、`:(){*` → 恒需审批。

### 2. 权限评估引擎（新增 `backend/app/agent/permissions.py`）

- FR-3：统一评估函数 `evaluate(tool, args) -> "allow" | "ask"`，优先级从高到低：
  1. 工具黑名单（delete_server）→ `ask`。
  2. 命令黑名单命中 → `ask`。
  3. `mode == "full"` → `allow`。
  4. 会话级放行集（内存，见 FR-7）→ `allow`。
  5. `mode == "standard"`：`run_python_code`/`run_shell_command` → `allow`；`run_command` 命中白名单 → `allow`。
  6. `mode == "conservative"` → `ask`（默认落点）。
- FR-4：默认只读白名单（仅 `run_command` 生效，fnmatch 通配）：
  `nvidia-smi*`、`nvcc *`、`pwd`、`whoami`、`ls*`、`cat *`、`head *`、`tail *`、`df*`、`free*`、`du *`、`ps *`、`which *`、`echo *`、`python *--version`、`pip list*`、`pip show *`、`pip freeze*`、`git status*`、`git log*`、`git diff*`、`git branch`、`git show*`、`git remote -v`。
- FR-5：防绕过：命令含 `;`、`&&`、`||`、`|` 复合操作符时不匹配白名单（回退 `ask`）；黑名单匹配不受此限。
- FR-6：持久化 `backend/data/agent_permissions.json`（gitignored，损坏时回退默认并重建）：
  ```json
  { "mode": "standard", "command_whitelist": ["nvidia-smi*", "..."], "updated_at": "..." }
  ```
- FR-7：会话级放行：审批弹窗选「本会话允许」→ 该工具加入 `Session` 内存放行集（重启/新会话失效，不持久化）；对黑名单命令仍无效（FR-3 优先级）。
- FR-8：`tools.py` 执行入口改为调用 `evaluate()`；`DANGEROUS_TOOLS`/`is_dangerous` 保留为"需评估集合"（22 个安全工具仍直接执行）。

### 3. 审批流扩展

- FR-9：审批接口 `run_approve(..., scope)`，`scope ∈ {"once", "session"}`（缺省 `once` 向后兼容）；`session` = 执行本次 pending 并加入会话放行集。
- FR-10：原设计的「永久允许」按钮移除（全局模式语义下无工具级持久配置）；弹窗底部提供提示文案：「不想再被询问？可在设置中切换为完全访问模式」。

### 4. 权限管理 API（`routes/agent.py` + schemas）

- FR-11：`GET /api/agent/permissions` → `{mode, command_whitelist}`。
- FR-12：`PUT /api/agent/permissions` → 校验（mode 合法值；whitelist 字符串数组，非法条目剔除）并保存，即时生效。
- FR-13：`POST /api/agent/permissions/reset` → 恢复默认（`standard` + 默认白名单）。

### 5. 权限模式选择入口（设置页 + Agent 工具栏，同一全局模式）

- FR-14：**全局唯一模式**：`mode` 为单一全局配置，不存在会话级/页面级独立模式；在任何入口修改后立即持久化，并对所有会话的下一次工具调用立即生效。
- FR-14a：**入口一：设置页「Agent 权限」卡片**：
  - 三模式 Radio Group 单选：
    - `保守模式` — 每一步危险操作都需要你确认（等同旧行为）
    - `标准模式（推荐）` — 本地沙箱代码与只读命令自动执行，其余操作逐次确认
    - `完全访问` — 全部工具自动执行，仅安全底线（破坏性命令）仍需确认
- FR-14b：远程命令白名单编辑器（仅标准模式生效，文案注明）：标签式多值输入（ant Tag + Input），可增删；提供「恢复默认白名单」按钮。
- FR-14c：「恢复默认」按钮；顶部说明文案注明安全底线不可配置。
- FR-17：**入口二：Agent 输入框下方工具栏下拉框**（参考 Codex，与设置页同一数据源）：
  - 位置：底部工具栏（`.toolbar` 行，加号按钮与模型选择器附近）。
  - 形态：**antd Select 下拉框**，当前模式为选中值，三个选项（保守模式 / 标准模式 / 完全访问）与设置页一致；宽度紧凑，不挤占模型选择器。
  - 切换即持久化并全局生效；选 `完全访问` 时弹风险确认（确认后才切换）。
  - 醒目区分：`完全访问` 激活时下拉框使用警示色（红/橙色文字与边框），普通模式为中性样式。
  - 与设置页状态实时同步（切页回来显示一致）。

### 6. 非功能需求

- NFR-1：不引入新依赖。
- NFR-2：权限文件与 `llm_config.json` 同目录、同 gitignore 策略，绝不入库。
- NFR-3：向后兼容：无权限文件按默认（standard）运行；旧会话行为不变。
- NFR-4：评估核心为纯函数（黑名单/白名单/模式匹配可单测）；会话态互相隔离。

## 范围

### 包含（In Scope）

- 后端权限引擎、持久化、API、审批 scope 扩展、agent 循环集成。
- 前端审批弹窗改造（三按钮 + 提示）、设置页模式卡片与白名单编辑。
- 单元测试（评估矩阵）+ API 测试。

### 不包含（Out of Scope）

- 逐工具策略配置（已否决）。
- 按命令粒度的审批记忆。
- 多用户/角色体系。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- full 模式下除黑名单外全部自动执行（含删除服务器记录以外的服务器写操作、部署、实验）——设置页文案需明确提示风险。
- 白名单可能被复合命令绕过——FR-5 已约束。
