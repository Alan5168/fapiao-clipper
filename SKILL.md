---
name: fapiao-clipper
description: >
  发票夹子 - 本地大模型驱动的发票自动识别与报销管理工具。
  发票放进文件夹 → Python 直接读文字 → Agent 直接读数据库回答"收到哪些发票"
  扫描件才触发视觉模型。功能：8项风控验真 + 一键导出 Excel + 合并 PDF。
version: 1.0.0
metadata:
  openclaw:
    emoji: "🧾"
    homepage: https://github.com/Alan5168/invoice-clipper
    requires:
      bins: [python3]
    always: false
---

# 发票夹子 (Invoice Clipper)

纯 Python CLI 工具，OpenClaw / Claude Code / KimiClaw 等任何 Agent 平台均可使用。

## 设计理念

```
发票 → 放文件夹
      ↓
Python 提取文字（第1级，99%免费）
      ↓ 读不出才走第2级
视觉模型（扫描件才触发）
      ↓
存入 SQLite 数据库
      ↓
Agent 直接读数据库回答问题 ← 完全不消耗 API token
```

## 数据库（Agent 直接读）

发票处理后存在 `~/Documents/发票夹子/invoices.db`（SQLite）。

Agent 可以直接用自然语言读数据库，例如：
- "这个月收到哪些发票？"
- "有没有超过365天的发票？"
- "XX公司的发票有吗？"

**不需要额外调用任何大模型 API**，Agent 用自己的上下文就能直接读。

## 命令速查

| 用户意图 | 执行命令 |
|---------|---------|
| 扫描发票 | `python3 {baseDir}/main.py scan` |
| 列出发票 | `python3 {baseDir}/main.py list` |
| 查询日期 | `python3 {baseDir}/main.py query --from 2026-03-01 --to 2026-03-31` |
| 标记不报销 | `python3 {baseDir}/main.py exclude <ID>` |
| 恢复报销 | `python3 {baseDir}/main.py include <ID>` |
| 导出报销 | `python3 {baseDir}/main.py export --from 2026-03-01 --to 2026-03-31 --format both` |
| 批量验真 | `python3 {baseDir}/main.py verify` |
| 查看问题发票 | `python3 {baseDir}/main.py problems` |
| 同步黑名单 | `python3 {baseDir}/main.py blacklist-sync` |

## 识别引擎说明

| 级别 | 触发条件 | 引擎 | 费用 |
|------|---------|------|------|
| 第1级 | 数字 PDF | Python 正则 | **免费** |
| 第1.5级 | 第1级字段不全 | 文本 LLM | ¥0.1/1M tokens |
| 第2级 | 扫描件/图片 | 按 provider 选择 | 按模型价格 |
| 第3级 | 全部失败 | PaddleOCR | **免费** |

大部分发票走第1级，零成本。

## 意图识别规则

| 用户说 | 执行的命令 |
|--------|-----------|
| "扫描发票" / "整理邮箱" | `scan` |
| "本月发票" / "列出所有" | `list` |
| "XX商家发票" | `query --seller XX` |
| "导出报销" | `export --from ... --to ... --format both` |
| "不要报销#3那张" | `exclude 3` |

---

## Agent 平台使用

### 零配置（推荐首次使用）

不想编辑 YAML？运行交互向导，回答几个问题即可：

```
python3 {baseDir}/setup_config.py
```

### OpenClaw / Claude Code / KimiClaw 等

调用示例：

```bash
# KimiClaw / Claude Code 等：直接让用户回答向导问题
python3 {baseDir}/setup_config.py

# 发票进来后让 Agent 回答
# Agent 只需读 SQLite：select * from invoices
```

## 注意事项

- 原文件永不删除，`exclude` 仅标记
- 发票有效期默认 365 天（可配置）
- 有 OpenClaw/Claude Code → 第1级搞定后，Agent 直接读数据库，不消耗 API