#!/usr/bin/env python3
"""
发票夹子 · 交互式配置向导 (v1.1)
运行方式：python3 setup_config.py
"""
import sys
from pathlib import Path

CONFIG_DIR = Path(__file__).parent.resolve() / "config"


def ask(question, default="", options=None):
    prompt = question
    if options:
        prompt += f" ({'/'.join(options)})"
    if default:
        prompt += f" [默认: {default}]"
    prompt += ": "
    try:
        answer = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n配置取消。")
        sys.exit(0)
    if not answer and default:
        return default
    if options and answer not in options:
        print(f"  → 使用默认值: {default}")
        return default
    return answer


def ask_yesno(question, default="n"):
    return ask(question, default, ["y", "n"]).lower() == "y"


def main():
    print()
    print("=" * 60)
    print("  发票夹子 v1.1 · 首次配置向导")
    print("=" * 60)

    # 1. 发票存放目录
    print("\n─── 发票存放目录 ───")
    default_dir = str(Path.home() / "Documents" / "发票夹子")
    inv_dir = ask("发票存放目录（绝对路径）", default_dir)
    inv_dir = str(Path(inv_dir).expanduser().resolve())
    print(f"  -> {inv_dir}")

    # 2. 识别引擎选择
    print()
    print("─── 发票识别引擎（4级降级，本地优先）───")
    print()
    print("  [1] Ollama 本地（推荐，完全免费）")
    print("       ├─ 第1级: PDF文本提取（免费，数字PDF秒出）")
    print("       ├─ 第2级: GLM-OCR（~2.2GB，图片/扫描件）")
    print("       └─ 第3级: Qwen3-VL（~6.1GB，最终兜底）")
    print()
    print("  [2] Ollama + TurboQuant（32GB 以下机器推荐）")
    print("       ├─ 同上，但 KV Cache 压缩 4-5x")
    print("       └─ 需要编译 TheTom/llama-cpp-turboquant")
    print()
    print("  [3] 硅基流动云端 API（新用户送¥16免费额度）")
    print()
    print("  [4] PaddleOCR 本地（完全免费，需 pip 安装）")
    print()
    choice = ask("选择引擎", default="1", options=["1", "2", "3", "4"])

    # 2.1 TurboQuant 额外配置
    tq_enabled = False
    tq_base_url = ""
    if choice == "2":
        print()
        print("─── TurboQuant 配置 ───")
        print("  TurboQuant server 通常运行在本地 8080 端口")
        tq_base_url = ask("TurboQuant server 地址", default="http://127.0.0.1:8080")
        print(f"  -> {tq_base_url}")
        print("  如果还没编译 TurboQuant，请先：")
        print("  1. git clone https://github.com/TheTom/llama-cpp-turboquant")
        print("  2. 按 README 编译（需要 cmake 和 C++ 工具链）")
        print("  3. 启动 server 后再运行本向导")
        tq_enabled = True

    # 3. 邮件监控
    print("\n─── 邮件监控（可选）───")
    enable_email = ask_yesno("是否监控邮箱发票?", default="n")
    email_block = ""
    if enable_email:
        imap = ask("IMAP 服务器", default="imap.mail.me.com",
                   options=["imap.mail.me.com", "imap.qq.com", "imap.163.com"])
        user = ask("邮箱地址")
        pw = ask("App专用密码（在appleid.apple.com生成）")
        link = ask_yesno("自动下载邮件中的发票链接?", default="y")
        email_block = (
            "email:\n"
            "  enabled: true\n"
            "  imap_server: " + imap + "\n"
            "  imap_port: 993\n"
            '  username: "' + user + '"\n'
            '  password: "' + pw + '"\n'
            "  folder: INBOX\n"
            "  download_dir: " + inv_dir + "/inbox\n"
            "  auto_follow_links: " + ("true" if link else "false") + "\n"
            "  trusted_link_domains:\n"
            "    - verify.tax\n"
            "    - inv.verify\n"
            "    - fpcy.cn\n"
            "    - tax.natappvirtual.cn"
        )

    # 4. 黑名单
    enable_bl = ask_yesno("启用失信主体黑名单（每月同步一次）?", default="y")

    # 5. 生成配置
    lines = [
        "# ============================================================",
        "# 发票夹子 v1.1 · 配置文件（由 setup_config.py 自动生成）",
        "# ============================================================",
        "",
        "storage:",
        "  base_dir: " + inv_dir,
        "  db_path: " + inv_dir + "/invoices.db",
        "",
    ]

    if choice in ("1", "2"):
        # Ollama 本地
        lines += [
            "# 发票识别配置",
            "# 识别链路（4级降级）：",
            "#   第1级: PDF 文本提取（PyMuPDF / pdfplumber）",
            "#   第2级: Ollama GLM-OCR（本地，~2.2GB）",
            "#   第3级: TurboQuant Ollama（可选，内存优化）",
            "#   第4级: Ollama Qwen3-VL（最终兜底）",
            "ocr:",
            "  provider: ollama",
            "  ollama:",
            "    base_url: http://127.0.0.1:11434",
            "    glm_model: glm-ocr:latest",
            "    qwen_model: qwen3-vl:latest",
        ]
        if tq_enabled:
            lines += [
            "  turboquant:",
            "    enabled: true",
            "    base_url: " + tq_base_url,
            "    glm_model: glm-ocr:latest",
            "    qwen_model: qwen3-vl:latest",
            ]
        else:
            lines += [
            "  turboquant:",
            "    enabled: false",
            "    base_url: http://127.0.0.1:8080",
            "    glm_model: glm-ocr:latest",
            "    qwen_model: qwen3-vl:latest",
            ]
        hint = (
            "  还没装 Ollama？\n"
            "  1. curl -fsSL https://ollama.ai/install.sh | sh\n"
            "  2. ollama pull glm-ocr:latest\n"
            "  3. ollama pull qwen3-vl:latest\n"
            "  运行: python3 main.py scan"
        )

    elif choice == "3":
        print()
        print("  [新用户送¥16免费额度，够用1000+张发票]")
        print("  注册: https://account.siliconflow.cn/zh/login?redirect=https%3A%2F%2Fcloud.siliconflow.cn&invitation=wV34tYbt")
        api_key = ask("输入硅基流动 API Key", default="")
        lines += [
            "# 发票识别配置",
            "ocr:",
            "  provider: siliconflow",
            "  siliconflow:",
            "    api_key: \"" + (api_key or "YOUR_API_KEY") + "\"",
            "    base_url: https://api.siliconflow.cn/v1",
            "    vision_model: Pro/PaddleOCR-VL-1.5",
            "    text_model: Pro/deepseek-ai/DeepSeek-V3.2",
        ]
        hint = "  运行: python3 main.py scan"

    elif choice == "4":
        lines += [
            "# 发票识别配置",
            "ocr:",
            "  provider: paddleocr",
            "  paddleocr:",
            "    enabled: true",
        ]
        hint = "  pip install paddlepaddle paddleocr\n  运行: python3 main.py scan"

    else:
        lines += [
            "# 发票识别配置（稍后手动填写）",
            "ocr:",
            "  # 稍后在 config.yaml 中配置",
        ]
        hint = "  稍后编辑 config/config.yaml"

    lines += [
        "",
        "watch_dirs:",
        "  - " + inv_dir + "/inbox",
    ]

    if email_block:
        lines += ["", email_block]

    lines += [
        "",
        "verification:",
        "  validity_days: 365",
        "  personal_exceptions:",
        "    - 差旅",
        "    - 交通",
        "    - 住宿",
        "    - 通讯",
        "    - 出行",
        "",
        "# 失信黑名单已启用" if enable_bl else "# 失信黑名单未启用",
    ]

    CONFIG_DIR.mkdir(exist_ok=True)
    config_file = CONFIG_DIR / "config.yaml"
    config_file.write_text("\n".join(lines))

    print()
    print("=" * 60)
    print(f"  ✅ 配置完成: {config_file}")
    print()
    print("  下一步:")
    print("  " + hint.replace("\n", "\n  "))
    print("=" * 60)


if __name__ == "__main__":
    main()
