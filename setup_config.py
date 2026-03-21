#!/usr/bin/env python3
"""
发票夹子 · 交互式配置向导
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
    print("=" * 50)
    print("  发票夹子 · 首次配置向导")
    print("=" * 50)

    # 1. 发票存放目录
    print("\n─── 发票存放目录 ───")
    default_dir = str(Path.home() / "Documents" / "发票夹子")
    inv_dir = ask("发票存放目录（绝对路径）", default_dir)
    inv_dir = str(Path(inv_dir).expanduser().resolve())
    print(f"  -> {inv_dir}")

    # 2. 识别引擎选择
    print()
    print("─── 发票识别引擎（第1级 Python 正则始终免费可用）───")
    print()
    print("  [1] Ollama 本地模型（推荐，完全免费）")
    print("       ├─ 第2级: GLM-OCR（~4GB，大部分电脑能跑）")
    print("       └─ 第3级: Qwen3-VL（~6GB，兜底）")
    print()
    print("  [2] 硅基流动云端 API（新用户送¥16免费额度）")
    print("       └─ 视觉模型调用，扫描件/图片用云端")
    print()
    print("  [3] PaddleOCR 本地（完全免费，需 pip 安装）")
    print()
    print("  [4] 跳过（稍后手动配置）")
    print()
    choice = ask("选择引擎", default="1", options=["1", "2", "3", "4"])

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
        "# 发票夹子 · 配置文件（由 setup_config.py 自动生成）",
        "# ============================================================",
        "",
        "storage:",
        "  base_dir: " + inv_dir,
        "  db_path: " + inv_dir + "/invoices.db",
        "",
    ]

    if choice == "1":
        # Ollama 本地
        lines += [
            "# 发票识别配置",
            "# 识别逻辑：",
            "#   第1级 Python 正则（免费，数字 PDF 直接出字段）",
            "#   第2级 Ollama GLM-OCR（本地，~4GB）",
            "#   第3级 Ollama Qwen3-VL（本地，~6GB，兜底）",
            "ocr:",
            "  ollama:",
            "    base_url: http://127.0.0.1:11434",
            "    glm_model: glm-ocr:latest",
            "    model: qwen3-vl:latest",
        ]
        hint = (
            "  还没装 Ollama？\n"
            "  1. curl -fsSL https://ollama.ai/install.sh | sh\n"
            "  2. ollama pull glm-ocr:latest\n"
            "  3. ollama pull qwen3-vl:latest\n"
            "  运行: python3 main.py scan"
        )

    elif choice == "2":
        # 硅基流动云端
        print()
        print("  [新用户送¥16免费额度，够用1000+张发票]")
        print("  注册: https://account.siliconflow.cn/zh/login?redirect=https%3A%2F%2Fcloud.siliconflow.cn&invitation=wV34tYbt")
        api_key = ask("输入硅基流动 API Key（注册后获取）", default="")
        lines += [
            "# 发票识别配置",
            "# 识别逻辑：",
            "#   第1级 Python 正则（免费，数字 PDF 直接出字段）",
            "#   第2级 硅基流动云端视觉模型（扫描件/图片）",
            "ocr:",
            "  siliconflow:",
            "    api_key: \"" + (api_key or "YOUR_API_KEY") + "\"",
            "    base_url: https://api.siliconflow.cn/v1",
            "    model: Pro/PaddleOCR-VL-1.5",
        ]
        hint = (
            "  还没硅基流动账号？\n"
            "  1. 点上方链接注册（用我的邀请码有奖励）\n"
            "  2. 获取 API Key 后填入上方 siliconflow.api_key\n"
            "  运行: python3 main.py scan"
        )

    elif choice == "3":
        # PaddleOCR 本地
        lines += [
            "# 发票识别配置",
            "# 识别逻辑：",
            "#   第1级 Python 正则（免费，数字 PDF 直接出字段）",
            "#   第2级 PaddleOCR（本地，完全免费，需要 pip 安装）",
            "ocr:",
            "  paddleocr:",
            "    enabled: true",
        ]
        hint = "  pip install paddlepaddle paddleocr\n  运行: python3 main.py scan"

    else:
        lines += [
            "# 发票识别配置（稍后手动填写）",
            "ocr:",
            "  # 稍后在 config.yaml 中配置 ollama / siliconflow / paddleocr",
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
    print("=" * 50)
    print(f"  配置完成: {config_file}")
    print()
    print("  下一步:")
    print("  " + hint.replace("\n", "\n  "))
    print("=" * 50)


if __name__ == "__main__":
    main()
