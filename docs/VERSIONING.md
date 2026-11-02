# 版本与发布约定

## 分支

- `main`：稳定分支，只接受可复现、测试通过的变更；
- 实验性改动可以先在 fork/本地分支，验证后再合入（当前项目以单人研究为主）。

## 版本号（SemVer）

| 版本 | 内容 |
|---|---|
| `v0.1.0` | 研究框架 + 回测报告 + $1,000 paper 账户 |
| `v0.2.0` | $100 多账户 paper + 杠杆测算 + CI |
| `v0.3.x` | paper 第 30 天结果 / 新研究（待发布） |

## 每次发布要做什么

1. 更新 [CHANGELOG.md](../CHANGELOG.md)（新增/变更/修复）；
2. `python -m unittest discover -s tests` 全过；
3. `scripts/check.ps1` 自检 PASS；
4. `git tag -a vX.Y.Z -m "..."` 打 annotated tag；
5. 推送 `main` 与 tags 到 GitHub；
6. 在 GitHub Releases 用 tag 创建 release（附报告摘要与链接）。

## GitHub 状态

- 本地仓库：`C:\量化项目`（44+ commits，含 paper 运行数据）；
- 远程仓库：**尚未创建/推送**（需要 GitHub 认证或手动建仓）；
- CI：`.github/workflows/tests.yml` 已就绪，推送后自动运行单元测试；
- 标签：`v0.1.0`、`v0.2.0` 已在本地创建，推送后出现在 GitHub。

## 敏感数据

- `data/`、`paper/*.log`、`paper/heartbeat.txt`、`paper/STOP` 已在 `.gitignore`；
- 仓库内无 API 密钥/私钥/助记词（`scripts/check.ps1` 每次扫描）。
