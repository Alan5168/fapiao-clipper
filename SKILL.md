---
name: fapiao-clipper
description: >
  发票夹子 v1.4 - 本地大模型驱动的发票自动识别与报销管理工具。
  2级降级链：PyMuPDF文本提取（修复跨行匹配）→ Qwen3-VL视觉模型。
  新增：seller/buyer跨行匹配修复、日期标准化。
  功能：8项风控验真 + 一键导出 Excel + 合并 PDF。
version: 1.4.0
metadata:
  openclaw:
    emoji: "🧾"
    homepage: https://github.com/Alan5168/fapiao-clipper
    requires:
      bins: [python3]
    always: false
---

# 发票夹子 (Invoice Clipper) v1.3

纯 Python CLI 工具，OpenClaw / Claude Code / KimiClaw 等任何 Agent 平台均可使用。

## v1.3 重大更新

**简化架构为 2 级**（2026-04-03）：
- 第1级：PyMuPDF 文本提取（修复跨行匹配）
- 第2级：Qwen3-VL 视觉模型（备用）
- 去掉 GLM-OCR（不稳定）和 TurboQuant（未启用）

## 设计理念

```
发票 → 放文件夹
      ↓
PDF 提取文字（两种引擎可选）
      ↓ 读不出才走第2级
视觉模型（扫描件才触发）
      ↓
存入 SQLite 数据库
      ↓
Agent 直接读数据库回答问题 ← 完全不消耗 API token
```

## 二级识别链 (v1.3)

| 级别 | 引擎 | 触发条件 | 特点 |
|------|------|---------|------|
| 第1级 | PyMuPDF | 可搜索 PDF（默认） | 毫秒级，无需Java |
| 第2级 | Ollama Qwen3-VL | 图片/扫描件 | ~6.1GB 内存 |

大部分发票走第1级，零成本。

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

## 意图识别规则

| 用户说 | 执行的命令 |
|--------|-----------|
| "扫描发票" / "整理邮箱" | `scan` |
| "本月发票" / "列出所有" | `list` |
| "XX商家发票" | `query --seller XX` |
| "导出报销" | `export --from ... --to ... --format both` |
| "不要报销#3那张" | `exclude 3` |

## Agent 平台使用

### 零配置（推荐首次使用）

不想编辑 YAML？运行交互向导，回答几个问题即可：

```bash
python3 {baseDir}/setup_config.py
```

## 安装

```bash
git clone https://github.com/Alan5168/fapiao-clipper.git
cd fapiao-clipper
pip install -r requirements.txt
cp config/config.yaml.template config/config.yaml
```

## 注意事项

- 原文件永不删除，`exclude` 仅标记
- 发票有效期默认 365 天（可配置）
- 有 OpenClaw/Claude Code → 第1级搞定后，Agent 直接读数据库，不消耗 API
