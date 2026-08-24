# spec-008 汇总：SSH 服务器部署与监控

> 本文档汇总 spec-008 从需求、实施到验收的全部结论。最终状态：**已完成（completed）**。

## 元信息

- **Spec 编号**：`spec-008-ssh-deploy-monitor`
- **状态**：completed（已完成）
- **创建/完成日期**：2026-08-24
- **关联决策**：`.ai/decisions/2026-08-24-ssh-deploy.md`

## 背景与目标

把实验代码部署到远程 GPU 服务器：SSH 服务器连接管理、代码部署（SFTP 上传 + git clone）、服务器监控，为后续自动跑实验打基础。

## 功能需求清单（FR-1 ~ FR-7，全部完成）

- FR-1：服务器增删改查，凭据存本地 `data/servers.json`。
- FR-2：测试 SSH 连接，返回成功/失败与耗时。
- FR-3：服务器列表凭据脱敏（不返回密码/私钥）。
- FR-4：git clone 部署。
- FR-5：SFTP 上传本地文件/目录。
- FR-6：服务器监控（nvidia-smi/free/df/uptime/ps）。
- FR-7：前端「服务器」页。

非功能：NFR-1 paramiko；NFR-2 凭据安全；NFR-3 超时与错误处理。

## 后端接口

- `GET/POST /api/servers`、`PUT/DELETE /api/servers/{id}`
- `POST /api/servers/{id}/test`
- `POST /api/servers/{id}/deploy/clone`、`/deploy/upload`
- `POST /api/servers/{id}/monitor`

## 验收结果

验收标准 AC-1 ~ AC-10 **全部 PASS**（轮次 1）。`pytest` 124 passed，前端 build 通过。

## 验收后追加的修复

1. 密码/私钥互斥：切到密钥认证会清掉旧密码，避免「凭据」同时显示密码和私钥。
2. SSH 认证修复：`auth_type=key` 但未填私钥时明确报错，不再静默回退密码认证；私钥解析失败也被正确捕获（不再 500）。
3. 同步更新了对应测试（`test_servers.py`），`pytest` 125 passed。

## 使用方式

- 顶部「服务器」页：添加服务器（密码或密钥认证）→ 测试连接 → 部署（git clone / 上传）→ 监控。
