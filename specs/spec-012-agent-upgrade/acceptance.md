# 验收标准与验收记录：Agent 专项升级（spec-012）

## 验收标准

- AC-1（对应 FR-1）：历史记录查询工具可用（搜索历史/创新点/综述/实验）。
- AC-2（对应 FR-2）：服务器增删改工具可用，凭据脱敏，危险需确认。
- AC-3（对应 FR-3）：SFTP 上传部署工具可用，危险需确认。
- AC-4（对应 FR-4）：`run_python_code` 可执行 Python 代码并返回结果。
- AC-5（对应 FR-5）：`run_shell_command` 可执行本地 shell 并返回结果。
- AC-6（对应 FR-6）：每会话独立沙箱目录。
- AC-7（对应 FR-7）：沙箱 subprocess + 超时 + 无密钥环境。
- AC-8（对应 FR-8）：状态细分为 thinking / executing:<tool>，含步骤计数。
- AC-9（对应 FR-9）：前端展示细分状态。

## 验收步骤

1. 启动后端与前端。
2. agent 请求查询历史记录，验证返回。
3. agent 请求服务器增删改，验证危险确认与脱敏。
4. agent 执行 Python 代码与 shell 命令，验证沙箱隔离与超时。
5. 观察前端状态从「思考中」到「执行中：工具名」的切换。
6. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-26 | PASS | 无阻塞问题；AC-1~9 全部通过，pytest 185 passed，前端 build 通过，无回归 | 通过，可进入收尾流程 |

## 验收结论

**结论：PASS**

逐条判定：

- AC-1（历史查询工具）：PASS。`tools.py:285-298` 实现 `list_search_history`/`list_innovations`/`list_reviews`/`list_experiments`（只读，非危险）；`tests/test_agent_upgrade.py` 四条历史工具用例通过，实测返回正确。
- AC-2（服务器 CRUD）：PASS。`tools.py:301-358` 实现 create/update/delete，均标 `dangerous=True` 并返回 `servers.redact()` 脱敏（无 password/private_key，仅 has_password/has_key）；实测 `create_server` 结果不含明文密钥。
- AC-3（SFTP 上传）：PASS。`tools.py:361-365` + `DeployUploadArgs` 实现 `deploy_upload`（local_path+remote_path），`dangerous=True`；`test_deploy_upload_tool` 通过。
- AC-4（run_python_code）：PASS。`tools.py:368-369` → `sandbox.run_python`（`sys.executable -c`），标危险；测试与实测均返回 stdout。
- AC-5（run_shell_command）：PASS。`tools.py:372-373` → `sandbox.run_shell`（shell=True），标危险；测试与实测均返回 stdout。
- AC-6（每会话沙箱目录）：PASS。`sandbox.py:54-57` 生成 `data/sandbox/<session_id>/`；`test_sandbox_dir_created_and_per_session` 通过。
- AC-7（subprocess+超时+无密钥环境）：PASS。`sandbox.py:70-108` 用 `subprocess.run(cwd, timeout=60, capture_output, env=白名单)`；白名单 `_ALLOWED_ENV_KEYS` 不含密钥；超时/隔离/无密钥测试通过。
- AC-8（状态细分）：PASS。`agent_sessions.status` 列（`database.py:87,119,781-790`），`_run_loop` 写 `thinking`/`executing:<tool> (第N步)`，`finally` 清空（`agent.py:167,195,227-229`）；实测状态轨迹 `thinking → executing:list_search_history (第1步) → thinking → ""`。
- AC-9（前端展示）：PASS。`AgentPage.tsx:68-74` 解析 status 展示「思考中…/执行中：工具名 (第N步)」，`types.ts`/`api.ts`/`schemas.py` 含 status 字段。

不回归判定：pytest 全量 185 passed（含 spec-001~011 既有用例），前端 `tsc && vite build` 通过，无回归。

测试实际运行：`backend/.venv` 下 `python -m pytest -q` = 185 passed in 7.37s；`frontend npm run build` 成功。
