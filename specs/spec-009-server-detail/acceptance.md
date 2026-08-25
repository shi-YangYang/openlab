# 验收标准与验收记录：服务器详情页与监控可视化（spec-009）

## 验收标准

- AC-1（对应 FR-1）：一级列表每服务器有编辑/详情/删除/测试四个操作。
- AC-2（对应 FR-2）：二级详情页存在，顶部面包屑「服务器列表 / 服务器名」。
- AC-3（对应 FR-3）：详情页顶部监控可视化（GPU/CPU/内存/磁盘图表或表格）。
- AC-4（对应 FR-4）：监控返回结构化数据，解析失败回退原始输出。
- AC-5（对应 FR-5）：部署本地路径支持手动输入 + 文件/文件夹选择器。
- AC-6（对应 FR-6）：环境配置有预设命令 + 自定义命令执行。
- AC-7（对应 FR-7）：命令执行结果在界面展示。
- AC-8（对应 NFR-2）：凭据不入库、不打印、脱敏。
- AC-9（对应 NFR-3）：监控解析容错（无 GPU/命令缺失不崩溃）。

## 验收步骤

1. 启动后端与前端。
2. 服务器列表看四个操作，点详情进入二级页，面包屑正确。
3. 详情页监控可视化展示 GPU/CPU/内存/磁盘。
4. 部署本地路径手动输入 + 文件选择器选择文件上传。
5. 环境配置执行预设命令与自定义命令，查看输出。
6. 运行 pytest 通过。

## 验收记录

（由验收 Agent 填写）

| 轮次 | 日期 | 结果（PASS/FAIL/BLOCKED） | 问题说明 | 结论/后续 |
| ---- | ---- | ---- | ---- | ---- |
| 1 | 2026-08-25 | FAIL | AC-1~9 全部通过（139 passed、前端 build 通过）；但 `deploy/upload` multipart 路径穿越防护不完整：`_safe_rel_path` 仅过滤 `.`/`..` 组件，未处理绝对路径（以 `/` 开头）与盘符/UNC 路径，`tmpdir / rel` 会逃逸临时目录（POSIX 下可任意写文件，如 `/etc/passwd`；Windows 下触发未处理异常 500）。与实施报告「含路径穿越防护」不符。 | 返工：`_safe_rel_path` 需剥离/拒绝绝对路径前缀（前导 `/`、盘符、UNC），或改为仅取 basename 并校验；修复后复验。 |
| 2 | 2026-08-25 | PASS | F1 修复确认：`_safe_rel_path` 剥离前导 `/`、`\`、空段、`.`、`..`、盘符段（`^[a-zA-Z]:$`），空回退 `upload`；新增 `_resolve_upload_target` 用 `resolve()` + `is_relative_to(root)` 校验，逃逸抛 `HTTPException(400)`，不写盘、不 500。独立复现（`/etc/passwd`、`../../evil.txt`、`C:\Windows\x`、`\\host\share`、`..\..\win-evil.txt`，含 raw multipart 直发绕过 httpx 的 basename 归一化）均不逃逸 tmpdir；`_resolve_upload_target` 对 `/etc/passwd`、`../evil`、`..\evil`、`C:\Windows\x` 直接入参均返回 400。pytest 142 passed；前端 `tsc && vite build` 通过。AC-1~9 无回归。 | 通过验收，进入收尾。 |

## 验收结论

**PASS**（F1 路径穿越安全缺陷已修复，AC-1~9 无回归）

- F1 修复判定：PASS。`backend/app/main.py:656-673` 的 `_safe_rel_path` 与 `_resolve_upload_target` 配合，剥离绝对路径前缀（`/`、`\`、盘符、UNC）并做 resolve 后越界校验（逃逸返回 400）。
- 不回归判定：AC-1~9 全部通过（pytest 142 passed，前端 build 通过）。
- 证据：`tests/test_servers.py:332-390`（`test_safe_rel_path_normalizes_malicious_names`、`test_resolve_upload_target_rejects_escape`、`test_deploy_upload_multipart_malicious_filenames_stay_in_tmpdir`）；验收 Agent 独立复现脚本全部通过。
