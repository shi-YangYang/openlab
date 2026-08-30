# 验收标准：spec-029-release-version-notes

## 验收清单

- AC-1：push tag `v0.2.0` 后 CI 构建成功，Release 资产名为 `openlab.Setup.0.2.0.exe`（与 tag 版本一致），不存在 0.1.0 旧资产残留。
- AC-2：Release 描述以 `## Commits in v0.2.0` 开头，随后为该 tag 覆盖范围的 commit message 列表（`- <subject>` 逐行），与 git log 一致，中文无乱码。
- AC-3：本地 `git log --pretty=format:"- %s" <prev>..<tag>` 输出与 Release 描述列表一致（首个 tag 时为全量历史）。
- AC-4：根 `package.json` version 为 `0.2.0`；tag 非法（非 SemVer）时 CI 在版本注入步骤显式失败。
- AC-5：全程未新增 secrets（仅使用 github.token / GITHUB_TOKEN）。

## 验证方式

AC-1/2/5 以 GitHub Actions run 结果与 Release 页面为准；AC-3/4 本地 pwsh 模拟验证（已通过：中文正常、utf8NoBOM 生效、npm version 0.2.0 成功、本地 electron-builder 产物名为 `openlab Setup 0.2.0.exe`）。
