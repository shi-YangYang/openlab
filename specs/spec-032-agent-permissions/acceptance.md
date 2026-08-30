# 验收标准：spec-032-agent-permissions

## 权限引擎（单测为主）

- AC-1：评估矩阵全部正确：
  - `delete_server` → 三种模式下均 `ask`（不可绕过）。
  - `run_command` 执行 `rm -rf /` / `shutdown now` / `dd if=/dev/zero of=/dev/sda` → 三种模式下均 `ask`。
  - `standard` 模式：`run_python_code`/`run_shell_command` → `allow`；其命令命中黑名单 → `ask`；`run_command` 执行 `nvidia-smi` → `allow`（白名单），`pip install x` → `ask`；`deploy_code` → `ask`。
  - `conservative` 模式：全部 10 工具 → `ask`（含沙箱工具与白名单命令）。
  - `full` 模式：全部工具 → `allow`（黑名单工具/命令除外）。
- AC-2：会话放行：`standard` 下审批选「本会话允许」`run_command` → 该会话后续非黑名单命令 `allow`；其他会话不受影响；重启进程后失效。`conservative` 下会话放行同样生效（优先级高于模式）。
- AC-3：含 `;`/`&&`/`||`/`|` 的复合命令不匹配白名单（`standard` 下回退 `ask`）。
- AC-4：`agent_permissions.json` 缺失按默认（standard + 默认白名单）；文件损坏回退默认并重建，不崩溃。

## API

- AC-5：`GET /api/agent/permissions` 返回 `{mode, command_whitelist}`。
- AC-6：`PUT` 校验：非法 mode 400；白名单非字符串条目剔除；保存后 GET 一致且下一次工具调用即时生效。
- AC-7：`POST /reset` → `standard` + 默认白名单。

## 审批流

- AC-8：弹窗三按钮（允许一次/本会话允许/拒绝）+ 提示文案；`scope=session` 生效（AC-2）；缺省 `once` 行为与现状一致（向后兼容）。

## UI

- AC-9：设置页「Agent 权限」卡片：三模式 Radio 单选（默认 standard）、白名单编辑器增删与恢复默认、整体恢复默认。
- AC-10：模式切换为 `full` 时（任一入口）弹确认（告知风险）；黑名单在 full 下仍强制审批。
- AC-11：Agent 输入框下方工具栏出现**下拉框**权限选择器：antd Select 三选项、显示当前模式；任一入口切换后**全局即时生效**（下一次工具调用按新 mode），设置页与工具栏状态实时一致；`完全访问` 激活时为警示色醒目样式。

## 工程

- AC-12：pytest 全量通过（权限引擎评估矩阵单测 + API 测试）；`npm run build` 通过。
- AC-13：现有行为回归：流式对话、附件、压缩、spec-030 toolbar 正常。
