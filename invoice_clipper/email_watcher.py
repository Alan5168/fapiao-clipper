"""
邮箱监控 + 附件下载
新增：邮件正文链接自动识别与下载（智能识别发票链接）
"""
import imaplib
import email
import json
import logging
import re
import urllib.parse
from pathlib import Path
from email.header import decode_header
from typing import List, Optional
import httpx

logger = logging.getLogger(__name__)

# 发票链接关键词（URL中出现这些词很可能是发票链接）
INVOICE_URL_KEYWORDS = [
    "invoice", "fapiao", "fp", "ofd", "tax", "verify",
    "jcsk", "keruyun", "kry", "chinatax", "fpcy",
    "dzfp", "dzswj", "etax",
]


def _decode_str(s) -> str:
    if isinstance(s, bytes):
        return s.decode("utf-8", errors="replace")
    if s is None:
        return ""
    parts = decode_header(s)
    result = []
    for part, charset in parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _load_seen(seen_path: Path) -> set:
    if seen_path.exists():
        return set(json.loads(seen_path.read_text()))
    return set()


def _save_seen(seen_path: Path, seen: set):
    seen_path.write_text(json.dumps(list(seen)))


def _get_email_body(msg: email.message.EmailMessage) -> str:
    """提取邮件正文（纯文本 + HTML 降级）"""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body += payload.decode(charset, errors="replace")
            elif content_type == "text/html" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    body += re.sub(r"<[^>]+>", " ", html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")
    return body


def _is_invoice_url(url: str) -> bool:
    """智能判断 URL 是否是发票链接"""
    url_lower = url.lower()
    
    # 1. URL 直接以 .pdf 或 .ofd 结尾
    if url_lower.endswith((".pdf", ".ofd")):
        return True
    
    # 2. URL 包含发票相关关键词
    for kw in INVOICE_URL_KEYWORDS:
        if kw in url_lower:
            return True
    
    # 3. URL 路径看起来像发票文件
    parsed = urllib.parse.urlparse(url_lower)
    path = parsed.path
    if any(ext in path for ext in [".pdf", ".ofd", "_pdf", "_ofd"]):
        return True
    
    return False


def _extract_invoice_links(body: str) -> List[str]:
    """从邮件正文中智能提取发票下载链接"""
    all_links = re.findall(r'https?://[^\s<>"\']+', body)
    
    invoice_links = []
    for url in all_links:
        url = url.rstrip('.,;:，。；：）)')
        if _is_invoice_url(url):
            invoice_links.append(url)
    
    return list(set(invoice_links))


def _download_from_url(url: str, timeout: int = 30) -> Optional[bytes]:
    """从 URL 下载文件内容，自动判断是否是发票文件"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/pdf, application/octet-stream, */*",
        }
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url, headers=headers)
            
            content_type = resp.headers.get("content-type", "").lower()
            is_invoice = (
                "pdf" in content_type or
                "ofd" in content_type or
                "octet-stream" in content_type or
                str(resp.url.path).lower().endswith((".pdf", ".ofd"))
            )
            
            if resp.status_code == 200 and is_invoice and len(resp.content) > 1024:
                logger.info(f"链接下载成功: {url[:60]}... ({len(resp.content):,} bytes)")
                return resp.content
                
    except Exception as e:
        logger.debug(f"下载异常: {url[:40]} — {e}")
    return None


def _save_payload(payload: bytes, filename: str, inbox_dir: Path) -> Path:
    """保存文件，自动处理重名"""
    ext = Path(filename).suffix.lower()
    if not ext:
        ext = ".pdf"
    save_path = inbox_dir / filename
    if save_path.exists():
        stem = save_path.stem
        for i in range(1, 200):
            candidate = inbox_dir / f"{stem}_{i}{ext}"
            if not candidate.exists():
                save_path = candidate
                break
    save_path.write_bytes(payload)
    return save_path


def fetch_invoice_attachments(config: dict, inbox_dir: Path) -> List[Path]:
    """主入口：扫描邮箱，下载发票附件 + 智能识别邮件中的发票链接"""
    email_cfg = config.get("email", {})
    server = email_cfg.get("imap_server", "imap.mail.me.com")
    port = email_cfg.get("imap_port", 993)
    username = email_cfg.get("username", "")
    password = email_cfg.get("password", "")
    folder = email_cfg.get("folder", "INBOX")

    if not username or not password:
        logger.warning("邮箱未配置，跳过邮件扫描")
        return []

    inbox_dir.mkdir(parents=True, exist_ok=True)
    seen_path = inbox_dir.parent / ".email_seen.json"
    seen = _load_seen(seen_path)
    new_files: List[Path] = []

    try:
        mail = imaplib.IMAP4_SSL(server, port)
        mail.login(username, password)
        mail.select(folder)

        _, msg_ids = mail.search(None, "ALL")
        raw = msg_ids[0]
        if not raw:
            mail.logout()
            return []
        ids = raw.split()

        new_ids = [i for i in ids if i.decode() not in seen]
        if not new_ids:
            logger.info("没有新邮件")
            mail.logout()
            return []

        logger.info(f"发现 {len(new_ids)} 封新邮件")

        for msg_id in new_ids:
            mid_str = msg_id.decode()
            _, msg_data = mail.fetch(msg_id, "(BODY[])")
            if not msg_data or msg_data[0] is None:
                continue
            raw_msg = msg_data[0][1]
            if not isinstance(raw_msg, bytes):
                continue
            msg = email.message_from_bytes(raw_msg)

            # ---- 1. 下载附件 ----
            for part in msg.walk():
                filename = part.get_filename()
                if not filename:
                    continue
                filename = _decode_str(filename)
                ext = Path(filename).suffix.lower()
                if ext not in (".pdf", ".ofd"):
                    continue
                payload = part.get_payload(decode=True)
                if not payload:
                    continue
                save_path = _save_payload(payload, filename, inbox_dir)
                new_files.append(save_path)
                logger.info(f"下载附件: {save_path.name}")

            # ---- 2. 智能下载邮件正文中的发票链接 ----
            body = _get_email_body(msg)
            links = _extract_invoice_links(body)
            for url in links:
                logger.info(f"发现发票链接: {url[:60]}")
                content = _download_from_url(url)
                if content:
                    parsed = urllib.parse.urlparse(url)
                    filename = Path(parsed.path).name
                    if not filename or "." not in filename:
                        filename = "invoice_from_link.pdf"
                    save_path = _save_payload(content, filename, inbox_dir)
                    new_files.append(save_path)
                    logger.info(f"链接文件已保存: {save_path.name}")

            seen.add(mid_str)

        _save_seen(seen_path, seen)
        mail.logout()

    except Exception as e:
        logger.error(f"邮件拉取失败: {e}")

    return new_files