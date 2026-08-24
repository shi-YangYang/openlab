# spec-008 SSH 部署与监控决策

## 决策标题

确定 SSH 服务器部署与监控（spec-008）的范围、实现方式与凭据存储。

## 元信息

- **日期**：2026-08-24
- **状态**：accepted
- **决策者**：用户
- **关联 Spec**：spec-008-ssh-deploy-monitor

## 决策

1. **范围**：服务器连接管理 + 代码部署 + 服务器监控（自动跑实验留待后续 spec）。
2. **SSH 实现**：Python paramiko。
3. **凭据存储**：本地配置文件（不入库、不入 git，类似 `llm_config.json`）。
4. **代码部署**：SFTP 上传本地文件 + 服务器 git clone，两者都支持。

## 理由

- 连接/部署/监控是「把实验跑到 GPU 服务器」的基础，先打通再谈自动跑实验。
- paramiko 跨平台、可控，比调用系统 ssh 命令更易集成到 Python 后端。
- 凭据存本地文件与 LLM API Key 一致，避免入库/入 git。

## 影响与后果

- 新增 `servers` 本地配置（`data/servers.json`）+ 服务器管理/部署/监控接口。
- 前端新增「服务器」导航页。
- 依赖新增 paramiko。
