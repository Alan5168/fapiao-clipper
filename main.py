#!/usr/bin/env python3
"""
发票夹子 - 主入口
"""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
import yaml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    cfg_path = Path(__file__).parent / "config" / "config.yaml"
    if not cfg_path.exists():
        logger.error(f"配置文件不存在: {cfg_path}")
        sys.exit(1)
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def cmd_scan(config: dict) -> str:
    """扫描所有监控目录和邮箱"""
    from invoice_clipper.processor import InvoiceProcessor
    from invoice_clipper.email_watcher import fetch_invoice_attachments

    proc = InvoiceProcessor(config)
    total = 0

    # 拉取邮件附件 - 使用配置中的下载目录
    email_cfg = config.get("email", {})
    download_dir = email_cfg.get("download_dir")
    if download_dir:
        inbox_dir = Path(download_dir).expanduser()
    else:
        inbox_dir = Path(config["storage"]["base_dir"]) / "inbox"
    
    email_files = fetch_invoice_attachments(config, inbox_dir)
    for f in email_files:
        if proc.process_file(f, source="email"):
            total += 1

    # 扫描本地监控目录
    for watch_dir in config.get("watch_dirs", []):
        watch_path = Path(watch_dir).expanduser()
        if watch_path.exists():
            results = proc.process_directory(watch_path, source="dir")
            total += len(results)
        else:
            logger.warning(f"监控目录不存在: {watch_path}")

    return f"✅ 扫描完成，共处理 {total} 张发票"


def cmd_list(config: dict) -> str:
    """列出所有发票"""
    from invoice_clipper.database import query_invoices

    # 查询所有发票
    invoices = query_invoices(
        Path(config["storage"]["db_path"]).expanduser(),
        {"only_included": False}  # 显示所有发票
    )

    if not invoices:
        return "没有发票记录"

    total_amount = sum(i.get("amount_with_tax") or 0 for i in invoices)
    lines = [f"共 {len(invoices)} 张发票，合计 ¥{total_amount:.2f}：\n"]
    for inv in invoices:
        inv_id = inv.get("id")
        date = inv.get("date") or ""
        seller = inv.get("seller") or ""
        buyer = inv.get("buyer") or ""
        amount = inv.get("amount_with_tax") or 0
        status = "❌" if inv.get("excluded") else "✅"
        lines.append(f"  {status} #{inv_id} | {date} | {seller} | {buyer} | ¥{amount:.2f}")

    return "\n".join(lines)


def cmd_query(config: dict, date_from: str = None, date_to: str = None,
              seller: str = None, buyer: str = None) -> str:
    """查询发票"""
    from invoice_clipper.database import query_invoices

    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "seller": seller,
        "buyer": buyer,
    }
    invoices = query_invoices(
        Path(config["storage"]["db_path"]).expanduser(), filters
    )

    if not invoices:
        return "没有找到符合条件的发票"

    total_amount = sum(i.get("amount_with_tax") or 0 for i in invoices)
    lines = [f"共 {len(invoices)} 张发票，合计 ¥{total_amount:.2f}：\n"]
    for inv in invoices:
        inv_id = inv.get("id")
        date = inv.get("date") or ""
        seller_name = inv.get("seller") or ""
        buyer_name = inv.get("buyer") or ""
        amount = inv.get("amount_with_tax") or 0
        status = "❌" if inv.get("excluded") else "✅"
        lines.append(f"  {status} #{inv_id} | {date} | {seller_name} | {buyer_name} | ¥{amount:.2f}")

    return "\n".join(lines)


def cmd_export(config: dict, date_from: str = None, date_to: str = None,
               seller: str = None, buyer: str = None, exclude_ids: list = None,
               fmt: str = "both") -> str:
    """导出发票"""
    from invoice_clipper.database import query_invoices
    from invoice_clipper.exporter import (
        export_excel, export_merged_pdf, export_pdf_folder, build_export_label
    )

    # 查询发票
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "seller": seller,
        "buyer": buyer,
        "exclude_ids": exclude_ids,
    }
    invoices = query_invoices(
        Path(config["storage"]["db_path"]).expanduser(), filters
    )

    if not invoices:
        return "没有找到符合条件的发票"

    # 导出目录
    export_dir = Path.home() / "Documents" / "发票夹子" / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名标签
    label = build_export_label(filters)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    results = []
    total_amount = sum(i.get("amount_with_tax") or 0 for i in invoices)

    # 导出 Excel
    if fmt in ["excel", "both"]:
        excel_path = export_dir / f"报销明细_{label}_{timestamp}.xlsx"
        export_excel(invoices, excel_path)
        results.append(f"📊 Excel: {excel_path}")

    # 导出合并 PDF
    if fmt in ["merged_pdf", "both"]:
        pdf_path = export_dir / f"报销发票_{label}_{timestamp}.pdf"
        result = export_merged_pdf(invoices, pdf_path)
        if result:
            results.append(f"📄 合并PDF: {pdf_path}")

    # 导出文件夹
    if fmt == "folder":
        folder_path = export_dir / f"报销发票_{label}_{timestamp}"
        export_pdf_folder(invoices, folder_path)
        results.append(f"📁 文件夹: {folder_path}")

    # 汇总
    summary = f"✅ 导出完成！共 {len(invoices)} 张发票，合计 ¥{total_amount:.2f}\n"
    summary += "\n".join(results)
    return summary


def cmd_exclude(config: dict, inv_id: int) -> str:
    """标记发票为不报销"""
    from invoice_clipper.database import update_invoice_status

    update_invoice_status(
        Path(config["storage"]["db_path"]).expanduser(),
        inv_id,
        excluded=True,
    )
    return f"✅ 发票 #{inv_id} 已标记为不报销（原文件保留）"


def cmd_include(config: dict, inv_id: int) -> str:
    """恢复发票为可报销"""
    from invoice_clipper.database import update_invoice_status

    update_invoice_status(
        Path(config["storage"]["db_path"]).expanduser(),
        inv_id,
        excluded=False,
    )
    return f"✅ 发票 #{inv_id} 已恢复为可报销"


def cmd_process(config: dict, file_path: str) -> str:
    """处理单个文件"""
    from invoice_clipper.processor import InvoiceProcessor

    proc = InvoiceProcessor(config)
    result = proc.process_file(Path(file_path))

    if result:
        return f"✅ 处理成功：{result.get('seller')} | ¥{result.get('amount_with_tax', 0):.2f}"
    else:
        return f"❌ 处理失败（可能是重复发票或识别错误）"


def cmd_verify(config: dict, inv_id: int = None) -> str:
    """验真发票"""
    from invoice_clipper.database import query_invoices
    from invoice_clipper.verifier import verify_invoice

    db_path = Path(config["storage"]["db_path"]).expanduser()
    
    if inv_id:
        invoices = query_invoices(db_path, {"exclude_ids": [], "only_included": False})
        invoices = [i for i in invoices if i.get("id") == inv_id]
    else:
        # 验真所有未检查的
        invoices = query_invoices(db_path, {"only_included": False})
        invoices = [i for i in invoices if i.get("tax_status") == "unchecked"]

    if not invoices:
        return "没有需要验真的发票"

    results = []
    for inv in invoices:
        result = verify_invoice(inv, config)
        results.append(f"#{inv.get('id')}: {result.get('tax_status', 'unknown')}")

    return "\n".join(results)


def cmd_blacklist_sync(config: dict) -> str:
    """同步失信黑名单"""
    from invoice_clipper.blacklist import sync_blacklist
    return sync_blacklist(config)


def main():
    parser = argparse.ArgumentParser(description="发票夹子 - 自动整理发票")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # scan
    subparsers.add_parser("scan", help="扫描邮箱和监控目录")

    # list
    subparsers.add_parser("list", help="列出所有发票")

    # process
    process_parser = subparsers.add_parser("process", help="处理单个文件")
    process_parser.add_argument("file", help="文件路径")

    # query
    query_parser = subparsers.add_parser("query", help="查询发票")
    query_parser.add_argument("--from", dest="date_from", help="开始日期 YYYY-MM-DD")
    query_parser.add_argument("--to", dest="date_to", help="结束日期 YYYY-MM-DD")
    query_parser.add_argument("--seller", help="销售方名称")
    query_parser.add_argument("--buyer", help="购买方名称")

    # exclude
    exclude_parser = subparsers.add_parser("exclude", help="标记不报销")
    exclude_parser.add_argument("id", type=int, help="发票ID")

    # include
    include_parser = subparsers.add_parser("include", help="恢复报销")
    include_parser.add_argument("id", type=int, help="发票ID")

    # export
    export_parser = subparsers.add_parser("export", help="导出报销")
    export_parser.add_argument("--from", dest="date_from", help="开始日期 YYYY-MM-DD")
    export_parser.add_argument("--to", dest="date_to", help="结束日期 YYYY-MM-DD")
    export_parser.add_argument("--seller", help="销售方名称")
    export_parser.add_argument("--buyer", help="购买方名称")
    export_parser.add_argument("--exclude-ids", help="排除的发票ID，逗号分隔")
    export_parser.add_argument("--format", dest="fmt", default="both",
                               choices=["excel", "merged_pdf", "folder", "both"],
                               help="导出格式")

    # verify
    verify_parser = subparsers.add_parser("verify", help="验真发票")
    verify_parser.add_argument("id", type=int, nargs="?", help="发票ID（可选，不填则验真所有）")

    # blacklist-sync
    subparsers.add_parser("blacklist-sync", help="同步失信黑名单")

    args = parser.parse_args()
    config = load_config()

    if args.command == "scan":
        print(cmd_scan(config))
    elif args.command == "list":
        print(cmd_list(config))
    elif args.command == "process":
        print(cmd_process(config, args.file))
    elif args.command == "query":
        print(cmd_query(config, args.date_from, args.date_to, args.seller, args.buyer))
    elif args.command == "exclude":
        print(cmd_exclude(config, args.id))
    elif args.command == "include":
        print(cmd_include(config, args.id))
    elif args.command == "export":
        exclude_ids = None
        if args.exclude_ids:
            exclude_ids = [int(x.strip()) for x in args.exclude_ids.split(",")]
        print(cmd_export(config, args.date_from, args.date_to, args.seller, args.buyer,
                        exclude_ids, args.fmt))
    elif args.command == "verify":
        print(cmd_verify(config, args.id))
    elif args.command == "blacklist-sync":
        print(cmd_blacklist_sync(config))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()