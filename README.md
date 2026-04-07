# 发票夹子 v1.5.2 🧾

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE) [![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)]() [![GitHub Stars](https://img.shields.io/github/stars/Alan5168/fapiao-clipper?style=social)](https://github.com/Alan5168/fapiao-clipper/stargazers) [![ClawHub](https://img.shields.io/badge/ClawHub-install-green.svg)](https://clawhub.ai/skills/fapiao-clipper)

> 中国发票专用 · 本地 AI 识别 · 3 分钟上手

[快速开始](#快速开始) · [功能特性](#功能特性) · [使用示例](#使用示例) · [架构说明](#架构说明)

---

## 痛点解决 💡

| 场景 | 传统方式 | 发票夹子 |
|------|---------|---------|
| 收票 | 手动下载邮箱附件 | 📧 自动扫描下载 |
| 识别 | 手工录入/云OCR（怕泄露）| 🔒 本地 AI 识别，零上传 |
| 整理 | Excel 手工统计 | 📊 自动分类+一键导出 |
| 验真 | 税局网站逐张查 | ✅ 自动验真+风险预警 |

---

## 快速开始 🚀（3 分钟）

### 1. 安装（30 秒）

**方式一：一键安装（推荐）**
如果你使用 [OpenClaw](https://openclaw.ai)，一行命令搞定：
```bash
npx clawhub@latest install fapiao-clipper
```
👉 https://clawhub.ai/skills/fapiao-clipper

**方式二：GitHub 手动安装**
```bash
git clone https://github.com/Alan5168/fapiao-clipper.git
cd fapiao-clipper
pip install -r requirements.txt
```

### 2. 配置邮箱（1 分钟）

```bash
cp config/config.yaml.template config/config.yaml
# 编辑 config/config.yaml 填入邮箱 IMAP 信息
```

### 3. 运行（1 分钟）

```bash
python3 main.py scan   # 扫描邮箱和本地目录
python3 main.py list   # 查看已识别发票
python3 main.py export --format both  # 导出报销 Excel + 合并 PDF
```

🎉 完成！文件在 `~/Documents/发票夹子/exports/`，直接发给财务。

### 4. Web UI 界面（可选，推荐）

发票夹子提供图形化 Web 界面，更适合财务人员日常使用：

**安装步骤：**

```bash
# 1. 克隆代码
git clone https://github.com/Alan5168/fapiao-clipper.git
cd fapiao-clipper

# 2. 创建虚拟环境并安装（推荐）
python3 -m venv .venv
source .venv/bin/activate  # Windows 用 .venv\Scripts\activate
pip install -e .

# 嫌麻烦也可以直接安装到用户目录（macOS/Linux）
pip install --user -e .

# 3. 配置（填入邮箱 IMAP 信息）
cp config/config.yaml.template config/config.yaml

# 4. 启动 Web UI
streamlit run app.py
```

浏览器自动打开 http://localhost:8501

> 💡 局域网外访问（公司WiFi/手机热点）：需要 Tailscale（详见下文「远程访问」章节）

> ⚠️ 必须先 `pip install -e .` 安装包，否则 Streamlit 无法导入 `invoice_clipper` 模块。

**功能说明**：
- **📤 扫描发票**：拖拽上传 PDF/图片，实时显示识别结果
- **📋 发票列表**：表格展示所有发票，支持状态筛选和批量操作
- **🔍 查询筛选**：按日期范围、销售方、购买方精准查找
- **📥 导出报销**：一键导出 Excel 明细表 + PDF 报销包

**特点**：
- 无需命令行，浏览器即可操作
- 实时预览，识别结果即时可见
- 批量管理，支持多选标记排除/恢复

![Web UI 界面预览](./docs/web-ui-preview.png)
*上图：发票列表页面，展示所有发票的日期、号码、金额和状态*


---

### 🌐 远程访问（局域网外）

Web UI 默认只在本地 `localhost:8501` 访问。如果需要在公司 WiFi、iPhone 热点等**非局域网**环境下访问，有两种方式：

#### 方式一：Tailscale（推荐，免费）

1. **安装 Tailscale**：[tailscale.com/download](https://tailscale.com/download)
   ```bash
   brew install --cask tailscale
   ```

2. **在你的 Mac Studio 和手机上安装 Tailscale**，用同一账号登录

3. **开启 exit node**（手机使用 Mac Studio 的网络）：
   ```bash
   tailscale set --exit-node=mac-studio-hostname
   ```

4. **访问地址**：`http://<mac-studio的Tailscale IP>:8501`

> 💡 OpenClaw 已内置 Tailscale，你的 Mac Studio Tailscale 地址在 `openclaw status` 里可以看到。

#### 方式二：frp 内网穿透（无需额外软件）

如果你有公网服务器，可以用过 frp 将 `localhost:8501` 暴露到公网：
```ini
[streamlit]
type = tcp
local_ip = 127.0.0.1
local_port = 8501
remote_port = 18501
```


## 功能特性 ✨

### 🧠 智能识别（本地 AI）

**二级识别引擎**：

1. **PyMuPDF 文本提取**（毫秒级）
   - 支持可搜索 PDF 直接提取文字
   - 修复跨行匹配问题（seller/buyer 不再写反）
   - 日期统一标准化为 `YYYY-MM-DD`

2. **Qwen3-VL 视觉模型**（备用，~60s）
   - 扫描件/图片发票识别
   - 复杂布局智能解析
   - 本地运行，零数据上传

> 🔒 **隐私安全**：所有识别都在本地完成，发票数据不上传任何云服务。

### 📧 自动收票

- **邮箱扫描**：自动登录 IMAP 邮箱，下载发票 PDF/OFD 附件
- **链接解析**：识别邮件正文中的发票下载链接，自动抓取
- **目录监控**：指定文件夹监控，新发票自动入库

### 🔍 智能验真（8项财务风控）

自动对接国家税务总局查验平台，内置专业财务风控逻辑：

| # | 风控项 | 逻辑说明 |
|---|--------|---------|
| ✅ | 发票真伪验证 | 税局官方接口校验 |
| 🚫 | 作废/红冲检测 | 发现"作废"或"红冲"状态立即预警 |
| ⏰ | 365天超期预警 | 开票日期超过365天不合规，不能报销 |
| 🔄 | 重复报销检测 | 同一发票号码年内是否已报销过 |
| 🏢 | 销售方风险库 | 对接动态黑名单，异常企业立即标记 |
| 💰 | 金额阈值预警 | 单笔超过设定金额自动提醒（如5万以上） |
| 📐 | 税率异常检测 | 税率与行业常规不符则预警 |
| 🧾 | 增值税抵扣检查 | 增值税专用发票的抵扣联校验 |

### 📊 一键导出

```bash
python3 main.py export --format both
```

导出文件：
- `报销明细_YYYYMMDD.xlsx`：发票号码、日期、金额、销售方等完整字段
- `报销发票_YYYYMMDD.pdf`：所有发票合并为一个 PDF，方便打印报销

---

## 使用示例 💻

### 场景 1：月末集中报销

```bash
python3 main.py scan                              # 自动下载新发票
python3 main.py list                             # 查看本月发票
python3 main.py export --from 2024-03-01 --to 2024-03-31 --format both  # 导出报销
```

### 场景 2：验真排查

```bash
python3 main.py verify     # 批量验真所有发票
python3 main.py problems   # 查看问题发票（作废/超期/重复/风险）
```

### 场景 3：排除非报销项

```bash
python3 main.py exclude 123  # 第123号发票不报销
python3 main.py include 123  # 恢复报销
```

---

## 架构说明 🏗️

```
┌─────────────────────────────────────────────────────────┐
│                        发 票 夹 子                        │
└─────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          ▼                 ▼                  ▼
    ┌──────────┐     ┌───────────┐     ┌────────────┐
    │ 📧 邮箱  │     │ 📁 本地   │     │ 📄 单张    │
    │ IMAP扫描 │     │ 目录监控  │     │ 文件拖入   │
    └────┬─────┘     └─────┬─────┘     └─────┬──────┘
         │                 │                  │
         └─────────────────┼──────────────────┘
                           ▼
              ┌────────────────────────┐
              │     📥 发票入库        │
              │  （PDF / OFD / 图片）   │
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │  🔍 二级识别引擎        │
              │ ┌────────────────────┐ │
              │ │ 第1级：PyMuPDF     │ │  ← 毫秒级（可搜索PDF）
              │ │  文本提取           │ │
              │ └─────────┬──────────┘ │
              │ ┌─────────▼──────────┐ │
              │ │ 第2级：Qwen3-VL   │ │  ← 视觉备用（扫描件）
              │ │  本地视觉模型       │ │
              │ └────────────────────┘ │
              └───────────┬────────────┘
                          ▼
              ┌────────────────────────┐
              │  📋 数据处理层          │
              │  字段标准化 / 重复检测  │
              │  销售方黑名单匹配       │
              └───────────┬────────────┘
                          ▼
         ┌────────────────┼────────────────┐
         ▼                ▼                 ▼
  ┌────────────┐   ┌────────────┐   ┌─────────────┐
  │ 🔍 8项    │   │ 💾 SQLite  │   │ 📁 PDF     │
  │ 财务风控  │   │ 数据库     │   │ 归档存储   │
  │ 验真      │   │ 本地存储   │   │ 按日期分类 │
  └─────┬──────┘   └─────┬──────┘   └─────────────┘
        │                │
        └────────┬────────┘
                 ▼
        ┌────────────────────────┐
        │  📤 一键导出            │
        │  Excel明细 + 合并PDF    │
        └────────────────────────┘
```

---

## 技术栈 🛠️

- **PDF 处理**：PyMuPDF, pdfplumber
- **AI 识别**：Ollama (Qwen3-VL)
- **数据库**：SQLite
- **导出**：pandas, reportlab
- **验真**：国家税务总局查验平台

---

## 隐私与安全 🔒

- ✅ **纯本地运行**：所有数据处理都在本机完成
- ✅ **零数据上传**：发票信息不上传任何云服务
- ✅ **本地 AI 识别**：Ollama 完全本地部署
- ✅ **数据库本地存储**：SQLite 文件存储在用户目录

---

## 开源协议 📄

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

## 🦞 ClawHub 一键安装

```bash
npx clawhub@latest install fapiao-clipper
```

👉 https://clawhub.ai/skills/fapiao-clipper

---

## 📝 更新日志

### v1.3.0 (2024-04-03)
- ✨ 简化降级链为 2 级（PyMuPDF → Qwen3-VL）
- 🐛 修复 seller/buyer 跨行匹配问题
- 📅 日期统一标准化为 YYYY-MM-DD
- 🛡️ 新增 8 项财务风控验真（作废/红冲/超期/重复/黑名单/金额/税率/抵扣）
- 📝 适配小红书引流，README 重构

### v1.2.0
- 新增 OpenDataLoader PDF 引擎
- 新增 TurboQuant 内存优化支持

### v1.1.0
- 新增四级降级链路
- 新增自动验真功能

### v1.0.0
- 初始版本发布

---

<p align="center">
  <b>发票夹子 · 让报销不再头疼 🧾✨</b>
</p>

<p align="center">
  Made with ❤️ by Alan Li | 中国自由职业者 & 小微企业财务效率工具
</p>

<p align="center">
  <a href="https://github.com/Alan5168/fapiao-clipper">GitHub</a> •
  <a href="https://clawhub.ai/skills/fapiao-clipper">ClawHub</a>
</p>

### v1.4.0 (2026-04-07)

#### 🐛 Bug 修复
- **OFD 中文文件名支持**：`easyofd` 处理中文路径报编码错误，改为先复制到临时 ASCII 路径再转换
- **PDF seller/buyer 提取修复**：PyMuPDF 提取的文本字符间有空格（字符定位问题），导致销售方/购买方正则匹配失败，改为先去掉所有空格再提取
- **email_watcher HTML 解析**：jss.com 等查验平台链接返回 HTML 而非 PDF，现能从 HTML 中提取真实 PDF 链接

#### ⚡ 性能/体验优化
- **qwen3-vl 超时延长**：图片识别超时从 120s 增至 300s（5分钟），适应慢速硬件
- **DPI 提高**：PDF 转图片 DPI 从 200 提升至 300，图片分辨率提升 45%

#### 🛡️ 安全/质量
- **发票内容验证**：新增入库前检查，必须同时包含"发票号码"+"发票"字样，防止结算单/订单等非发票文件混入数据库

