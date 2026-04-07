# ClawHub 发布配置

## 项目信息

- **Name**: fapiao-clipper
- **Display Name**: 发票夹子
- **Version**: 1.5.0
- **Description**: 中国发票专用 · 本地 AI 识别 · 3 分钟上手
- **Author**: Alan Li
- **License**: MIT
- **Homepage**: https://github.com/Alan5168/fapiao-clipper
- **ClawHub**: https://clawhub.ai/skills/fapiao-clipper

## 标签

- 财务
- 发票
- 报销
- 中国
- OCR
- 本地 AI
- 效率工具

## 依赖

- Python 3.10+
- Ollama (本地 AI)
- PyMuPDF
- pandas
- SQLite

## 安装命令

```bash
npx clawhub@latest install fapiao-clipper
```

或手动安装：

```bash
git clone https://github.com/Alan5168/fapiao-clipper.git
cd fapiao-clipper
pip install -r requirements.txt
```

## 快速开始

```bash
# 1. 配置邮箱（编辑 config/config.yaml）
cp config/config.yaml.template config/config.yaml

# 2. 扫描发票
python3 main.py scan

# 3. 导出报销单
python3 main.py export --format both
```

## 功能特性

- 📧 自动收票：邮箱扫描 + 附件下载
- 🧠 本地 AI：Ollama Qwen3-VL 识别，零上传
- 📊 一键导出：Excel + 合并 PDF
- ✅ 自动验真：对接国家税务总局
- 🔒 隐私安全：纯本地运行，数据不上云

## 小红书引流

- 小红书文案：`/Users/alanli/.openclaw/workspace/xiaohongshu_post.md`
- 引流图制作指南：见 README "小红书快速上手指南" 章节

## 版本历史

- v1.5.2 (2026-04-07): 发票内容验证（必须含"发票号码"+"发票"字样）+ OFD中文路径修复 + PDF散列字符提取修复 + qwen3-vl超时延长至300s + DPI提升至300
- v1.4.1 (2026-04-05): Web UI全面重构，6项风控可视化，新增查验按钮
- v1.4.0 (2024-04-03): 简化架构为 2 级，修复跨行匹配
- v1.2.0: 新增 OpenDataLoader PDF 引擎
- v1.1.0: 新增四级降级链路
- v1.0.0: 初始版本

## 相关链接

- GitHub: https://github.com/Alan5168/fapiao-clipper
- ClawHub: https://clawhub.ai/skills/fapiao-clipper
- 小红书: 搜索 "发票夹子" 或 "财务效率工具"
- 问题反馈: https://github.com/Alan5168/fapiao-clipper/issues

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <b>发票夹子 · 让报销不再头疼 🧾✨</b>
</p>

<p align="center">
  Made with ❤️ by Alan Li | 中国自由职业者 & 小微企业的财务效率工具
</p>