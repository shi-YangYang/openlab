# Summary：spec-029-release-version-notes

## 完成日期

2026-08-30

## 实施内容

### 1. 版本号从 tag 注入（`.github/workflows/release.yml`）

- 新增 `Sync version from tag` 步骤：从 `GITHUB_REF_NAME` 提取 `v` 前缀后的 SemVer，正则校验，`npm version <ver> --no-git-tag-version --allow-same-version` 写入根 package.json，electron-builder 产物名/元数据随之同步。
- 本地根 package.json 同步至 `0.2.0`。

### 2. Release 描述 = commit 列表

- 新增 `Generate release notes` 步骤：`git describe --tags --abbrev=0 "<tag>^"` 取上一个 tag，`git log --pretty=format:"- %s" <prev>..<tag>` 生成列表（首个 tag 列出全量历史），写入 `release-notes.txt`（pwsh 7 `utf8NoBOM`，显式 UTF-8 输出编码防中文乱码）。
- Create Release 改用 `body_path: release-notes.txt`，移除 `generate_release_notes`。

### 3. 旧 Release asset 自动清理

- 新增 `Remove old release assets` 步骤：`gh api ... --jq '.assets[].id'` 枚举同名 release 的旧资产并逐个 DELETE；release 不存在则跳过。
- CI 迭代 1 次：初版用 `gh release view --json assets` + `ConvertFrom-Json` 失败——gh 输出多行 pretty JSON 被 PowerShell 捕获为字符串数组，逐行解析抛错。改为 `gh api --jq` 单值行输出后通过。

### 4. Checkout 历史补全

- `actions/checkout@v4` 增加 `fetch-depth: 0`（commit log 与 tags 完整获取）。

## 验证结果（commit `0d0f0be`，run success）

- Release `v0.2.0` 资产：仅 `openlab.Setup.0.2.0.exe`（172.7 MB），旧 `0.1.0` 资产已被自动删除。
- Release 描述：`## Commits in v0.2.0` 开头 + 41 条 commit message 列表，中文 UTF-8 无乱码（程序化断言通过：目标中文子串命中、无替换符）。
- 本地预验证：notes 脚本 pwsh 模拟通过；`npm version 0.2.0` 成功；本地 electron-builder 产物名 `openlab Setup 0.2.0.exe`。

## 交付物

- `.github/workflows/release.yml`：+3 步骤（版本注入 / notes 生成 / 旧资产清理）+ fetch-depth。
- `package.json` / `package-lock.json`：version 0.2.0。
- `specs/spec-029-release-version-notes/`：spec + acceptance + summary。

## 遗留事项

- 无。后续发版流程：正常 commit → 打 `vX.Y.Z` tag → CI 自动产出对应版本安装包与 commit 描述。
