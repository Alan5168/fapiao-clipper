---
name: fapiao-clipper
description: >
  发票夹子 v1.2 - 本地大模型驱动的发票自动识别与报销管理工具。
  四级降级链：PDF文本提取 → GLM-OCR → TurboQuant → Qwen3-VL。
  新增：OpenDataLoader PDF引擎（有序输出+表格结构）。
  功能：8项风控验真 + 一键导出 Excel + 合并 PDF。
version: 1.2.0
metadata:
  openclaw:
    emoji: "🧾"
    homepage: https://github.com/Alan5168/invoice-clipper
    requires:
      bins: [python3]
    always: false
---

# 发票夹子 (Invoice Clipper) v1.2

纯 Python CLI 工具，OpenClaw / Claude Code / KimiClaw 等任何 Agent 平台均可使用。

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

## 五级识别链 (v1.2)

| 级别 | 引擎 | 触发条件 | 特点 |
|------|------|---------|------|
| 第1级-A | PyMuPDF | 可搜索 PDF（默认） | 毫秒级，无需Java |
| 第1级-B | OpenDataLoader | 可搜索 PDF（可选） | 有序输出+表格结构，需Java |
| 第2级 | Ollama GLM-OCR | 图片/扫描件 | ~2.2GB 内存 |
| 第3级 | TurboQuant Ollama | 可选，32GB以下机器 | ~500MB（4-5x压缩）|
| 第4级 | Ollama Qwen3-VL | 最终fallback | ~6.1GB 内存 |

大部分发票走第1级，零成本。

## PDF 提取引擎对比

| 特性 | PyMuPDF | OpenDataLoader |
|------|---------|---------------|
| 速度 | 毫秒级 | ~2秒（JVM启动）|
| 阅读顺序 | 乱序 | ✅ 有序（XY-Cut++）|
| 表格结构 | 纯文本 | ✅ Markdown表格 |
| 坐标输出 | 无 | ✅ JSON bounding boxes |
| 依赖 | 无 | Java 11+ |

**推荐场景**：
- 日常处理 → PyMuPDF（够用）
- 批量处理 → OpenDataLoader（一次JVM启动多文件）
- 需字段坐标验证 → OpenDataLoader

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

## OpenDataLoader 配置 (v1.2 新增)

在 `config/config.yaml` 中启用：

```yaml
pdf_extractor:
  engine: opendataloader  # 或 pymupdf（默认）
  opendataloader:
    java_home: /opt/homebrew/opt/openjdk@11/libexec/openjdk.jdk/Contents/Home
    batch_size: 10
    include_json: false
```

安装依赖：
```bash
pip install opendataloader-pdf
brew install openjdk@11
```

## TurboQuant 配置 (v1.1)

TurboQuant server 启动后，在 `config/config.yaml` 中启用：

```yaml
ocr:
  turboquant:
    enabled: true
    base_url: http://127.0.0.1:8080
    glm_model: glm-ocr:latest
    qwen_model: qwen3-vl:latest
```

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

## 注意事项

- 原文件永不删除，`exclude` 仅标记
- 发票有效期默认 365 天（可配置）
- 有 OpenClaw/Claude Code → 第1级搞定后，Agent 直接读数据库，不消耗 API
- TurboQuant 是可选优化，未启用时自动跳过
- OpenDataLoader 需要安装 Java 11+