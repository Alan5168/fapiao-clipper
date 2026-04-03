# 发票夹子 v1.3.0 🧾

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

```bash
# 克隆仓库
git clone https://github.com/Alan5168/fapiao-clipper.git
cd fapiao-clipper

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置邮箱（1 分钟）

复制模板配置文件：

```bash
cp config/config.yaml.template config/config.yaml
```

编辑 `config/config.yaml`：

```yaml
email:
  imap_server: imap.qq.com        # 你的邮箱 IMAP 服务器
  username: your_email@qq.com     # 你的邮箱
  password: your_auth_code        # 授权码（不是邮箱密码）
  download_dir: ~/Documents/发票夹子/inbox
```

> 💡 常见邮箱 IMAP 服务器：
> - QQ 邮箱：imap.qq.com
> - 163 邮箱：imap.163.com
> - Gmail：imap.gmail.com

### 3. 运行（1 分钟）

```bash
# 扫描邮箱和本地目录
python3 main.py scan

# 查看已识别发票
python3 main.py list

# 导出报销单（Excel + 合并 PDF）
python3 main.py export --format both
```

🎉 完成！报销文件已生成在 `~/Documents/发票夹子/exports/`。

---

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

### 🔍 智能验真

自动对接国家税务总局查验平台：

- ✅ 发票真伪验证
- ✅ 发票状态（正常/作废/红冲）
- ✅ 开票日期合规检查（超 365 天预警）
- ✅ 重复报销检测

### 📊 一键导出

```bash
# 导出 Excel 明细表 + 合并 PDF
python3 main.py export --format both

# 按日期筛选
python3 main.py export --from 2024-01-01 --to 2024-03-31
```

导出文件：
- `报销明细_YYYYMMDD.xlsx`：含发票号码、日期、金额、销售方等字段
- `报销发票_YYYYMMDD.pdf`：所有发票合并为一个 PDF，方便打印

---

## 使用示例 💻

### 场景 1：月末集中报销

```bash
# 1. 扫描邮箱和监控目录，自动下载新发票
python3 main.py scan

# 2. 查看本月发票统计
python3 main.py list

# 3. 导出本月的报销单
python3 main.py export --from 2024-03-01 --to 2024-03-31 --format both

# 4. 生成的文件在 ~/Documents/发票夹子/exports/，直接发给财务
```

### 场景 2：单张发票识别

```bash
# 处理单张发票（测试或补录）
python3 main.py process /path/to/发票.pdf

# 输出示例：
# ✅ 处理成功：北京某某科技有限公司 | ¥1,250.00
```

### 场景 3：排除非发票文件

```bash
# 查看所有发票（包括已标记不报销的）
python3 main.py list --all

# 标记某张发票不报销（如个人消费）
python3 main.py exclude 123

# 恢复报销
python3 main.py include 123
```

---

## 架构说明 🏗️

```
发票夹子 v1.3.0 架构
│
├─ 输入层
│  ├─ 邮箱 IMAP 扫描
│  ├─ 本地目录监控
│  └─ 单文件处理
│
├─ 识别层（本地 AI）
│  ├─ 第1级：PyMuPDF 文本提取（毫秒级）
│  │   └─ 修复跨行匹配，日期标准化
│  └─ 第2级：Qwen3-VL 视觉模型（备用）
│      └─ 扫描件/复杂布局识别
│
├─ 数据处理层
│  ├─ 字段标准化（日期、金额、名称）
│  ├─ 重复检测
│  └─ 验真对接（国家税务总局）
│
├─ 存储层
│  ├─ SQLite 数据库（本地）
│  └─ PDF 归档（按日期分类）
│
└─ 输出层
   ├─ Excel 明细导出
   ├─ 合并 PDF 导出
   └─ 验真报告
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

## 反馈与支持 💬

- **GitHub Issues**: [提交问题或建议](https://github.com/Alan5168/fapiao-clipper/issues)
- **小红书**: 关注「财务效率工具」相关话题，分享使用心得

---

<p align="center">
  发票夹子 · 让报销不再头疼 🧾✨
</p>

<p align="center">
  Made with ❤️ for Chinese freelancers & small business owners
</p>