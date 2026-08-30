# Spec：Release 版本号与描述规范化（spec-029）

## 元信息

- **Spec 编号**：`spec-029-release-version-notes`
- **状态**：`completed`
- **创建日期**：2026-08-30
- **来源**：spec-028 上线后 v0.2.0 Release 暴露的两个问题（用户反馈）
- **负责人**：协调开发 Agent

## 背景与动机

v0.2.0 Release 验证时发现：

1. 安装包名为 `openlab.Setup.0.1.0.exe`，版本取自根 `package.json`（0.1.0），与 tag `v0.2.0` 不一致（spec-028 将版本同步列为 Out of Scope，现转为需求）。
2. Release 描述由 `generate_release_notes` 自动生成（PR/贡献者视角），用户期望描述与该 tag 包含的 commit 保持一致。

## 目标

- CI 打包的安装包版本号自动与 tag 一致（`vX.Y.Z` → `X.Y.Z`）。
- Release 描述自动生成 = 该 tag 相对上一个 tag 的 commit message 列表。
- 同一 tag 重复发布时，旧 Release asset 自动清理，避免残留旧版本安装包。

## 范围

### 包含（In Scope）

- `.github/workflows/release.yml` 修改：
  - checkout `fetch-depth: 0`（commit log 与 tags 完整获取）。
  - 新增"从 tag 提取 SemVer 并写入根 package.json"步骤（npm version --no-git-tag-version）。
  - 新增"生成 release notes"步骤（`git log --pretty=format:"- %s" <prev>..<tag>`）。
  - 新增"清理既有 release 旧 asset"步骤（gh CLI + GITHUB_TOKEN）。
  - Create Release 改用 `body_path`，移除 `generate_release_notes`。
- 本地根 `package.json` version 同步至 0.2.0。

### 不包含（Out of Scope）

- 版本号语义校验以外的自动化（如自动 bump、changelog 文件）。
- macOS / Linux。
- 代码签名。

## 需求描述

### 功能需求

- FR-1：CI 中从 `GITHUB_REF_NAME`（`vX.Y.Z`）提取 SemVer，校验格式后以 `npm version X.Y.Z --no-git-tag-version --allow-same-version` 写入根 package.json，electron-builder 产物名/元数据随之变为 `X.Y.Z`。
- FR-2：Release body 生成规则：`git describe --tags --abbrev=0 "<tag>^"` 取上一个 tag，`git log --pretty=format:"- %s" <prev>..<tag>` 列出 commit message（首 tag 时仅当前 tag 自身 commit）；无 commit 时占位 `- (no commits)`。
- FR-3：Create Release 前若同名 release 已存在，删除其全部旧 asset（gh release view + gh api DELETE），release 不存在则跳过。

### 非功能需求

- NFR-1：全程使用 GitHub 自动注入的 `GITHUB_TOKEN`，不新增 secrets。
- NFR-2：commit message 中文在 CI（pwsh 7）下无乱码（显式 UTF-8 输出编码）。

## 验收标准

见 `acceptance.md`。

## 风险与开放问题

- `fetch-depth: 0` 增加少量 checkout 时间（仓库小，可忽略）。
- 本地 PowerShell 5.1 与 CI pwsh 7 编码差异：本地仅做逻辑验证，最终以 CI 结果为准。
