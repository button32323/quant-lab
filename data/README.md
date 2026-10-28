# 数据目录

本目录用于存放本地行情/资金费等数据，**不入 git**（见 `.gitignore`）。

## 约定

| 子目录 | 内容 |
|---|---|
| `cache/` | API 原始响应缓存（可按需清理） |
| `panels/` | 清洗后的分析面板（Parquet/CSV） |
| `raw/` | 原始下载数据 |

## 拉数据示例

```bash
python scripts/demo/hl_fetch.py --coin HYPE --interval 1d
```

数据来自 Hyperliquid 公开 API，无需密钥。
