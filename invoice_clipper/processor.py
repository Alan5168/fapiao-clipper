"""
发票处理核心 - 处理单张发票的完整流程
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from .database import insert_invoice, is_duplicate, exists_by_invoice_number, init_db
from .file_processor import (
    extract_text_from_pdf, ofd_to_pdf,
    build_archive_path, archive_invoice
)
from .recognizer import InvoiceRecognizer

logger = logging.getLogger(__name__)


class InvoiceProcessor:
    def __init__(self, config: dict):
        self.cfg = config
        self.db_path = Path(config["storage"]["db_path"]).expanduser()
        self.archive_dir = Path(config["storage"]["base_dir"]).expanduser()
        self.recognizer = InvoiceRecognizer(config)

        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # 初始化数据库
        init_db(self.db_path)
        logger.info(f"数据库初始化完成: {self.db_path}")

    def process_file(self, file_path: Path, source: str = "manual") -> Optional[dict]:
        """处理单个文件"""
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"文件不存在: {file_path}")
            return None

        suffix = file_path.suffix.lower()
        if suffix not in [".pdf", ".ofd", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"]:
            logger.warning(f"不支持的文件类型: {suffix}")
            return None

        # OFD 转 PDF / 图片直接使用
        pdf_path = file_path
        if suffix == ".ofd":
            try:
                pdf_path = ofd_to_pdf(file_path)
                logger.info(f"OFD 转 PDF 成功: {pdf_path.name}")
            except Exception as e:
                logger.error(f"OFD 转换失败: {e}")
                return None

        # 提取文本
        try:
            raw_text = extract_text_from_pdf(pdf_path)
            logger.debug(f"提取文本 {len(raw_text)} 字符: {pdf_path.name}")
        except Exception as e:
            logger.error(f"PDF 文本提取失败: {pdf_path.name} - {e}")
            raw_text = ""

        # ============================================================
        # 内容验证：必须有"发票号码"+ 包含"发票"（覆盖所有类型：电子发票/出租车发票/定额发票等）
        text_lower = raw_text.lower()
        has_number = "发票号码" in text_lower
        has_invoice_word = "发票" in text_lower
        if not (has_number and has_invoice_word):
            logger.warning(
                f"⚠️ 非发票文件，跳过: {file_path.name} "
                f"(发票号码:{has_number}, 含发票字样:{has_invoice_word})"
            )
            return None

        result = self.recognizer.recognize(pdf_path, raw_text)
        if not result or not result.is_valid:
            logger.error(f"识别失败: {pdf_path.name}")
            return None

        # 从 EngineResult.data 获取字段
        fields = result.data

        # 去重检查（双重保护）
        inv_no = fields.get("invoice_number") or ""
        amount_raw = fields.get("amount_with_tax") or 0
        try:
            amount = float(amount_raw)
        except (ValueError, TypeError):
            amount = 0.0

        # 保护1：发票号+金额完全相同 → 严格重复
        if inv_no and is_duplicate(str(self.db_path), inv_no, amount):
            logger.warning(f"重复发票（发票号+金额相同），跳过: {inv_no} / {amount:.2f}")
            return None
        # 保护2：同一发票号已存在（不管金额）→ 防止误识别导致重复入库
        if inv_no and exists_by_invoice_number(str(self.db_path), inv_no):
            logger.warning(f"重复发票（发票号已存在），跳过: {inv_no}")
            return None

        # 归档文件
        dest_path = build_archive_path(self.archive_dir, fields)
        archived = archive_invoice(pdf_path, dest_path, move=True)

        # OFD 原文件也移走（已转换完）
        if suffix == ".ofd" and file_path.exists():
            ofd_archive = self.archive_dir / "ofd_original" / file_path.name
            ofd_archive.parent.mkdir(parents=True, exist_ok=True)
            archive_invoice(file_path, ofd_archive, move=True)

        # 入库
        record = {
            "invoice_number":   inv_no,
            "invoice_code":     fields.get("invoice_code"),
            "date":            fields.get("date"),
            "amount":          fields.get("amount"),
            "amount_with_tax": amount,
            "tax":             fields.get("tax"),
            "seller":          fields.get("seller"),
            "buyer":           fields.get("buyer"),
            "category":        fields.get("category"),
            "invoice_type":    fields.get("invoice_type"),
            "source":          source,
            "original_filename": file_path.name,
            "stored_path":     str(archived),
            "created_at":      datetime.now().isoformat(),
            "raw_text":        raw_text[:2000],
            "raw_json":        str(fields),
        }
        invoice_id = insert_invoice(str(self.db_path), record)
        record["id"] = invoice_id

        # ── 自动验真 ───────────────────────────────────────
        try:
            from invoice_clipper.verifier import verify_invoice
            v_result = verify_invoice(
                {**fields, "stored_path": str(archived)},
                db_path=str(self.db_path),
                validity_days=self.cfg.get("validity_days", 365),
            )
            from invoice_clipper.database import update_verification_result
            update_verification_result(str(self.db_path), invoice_id, v_result)
            # 打印警告
            for w in v_result.get("warnings", []):
                icon = "🚫" if w["level"] == "BLOCK" else "⚠️"
                logger.warning(f"{icon} #{invoice_id} {w['code']}: {w['message']}")
        except Exception as e:
            logger.warning(f"验真模块异常: {e}")

        logger.info(
            f"✅ 入库 #{invoice_id}: {fields.get('date')} | "
            f"{fields.get('seller')} | ¥{amount:.2f} | {inv_no}"
        )
        return record

    def process_directory(self, dir_path: Path, source: str = "dir") -> list:
        """处理目录中所有 PDF/OFD 文件（带进度条）"""
        dir_path = Path(dir_path)
        results = []
        files = list(dir_path.glob("*.pdf")) + list(dir_path.glob("*.ofd")) + \
                list(dir_path.glob("*.PDF")) + list(dir_path.glob("*.OFD"))

        total = len(files)
        if total == 0:
            logger.info(f"目录无发票文件: {dir_path}")
            return results

        logger.info(f"发现 {total} 个文件待处理: {dir_path}")

        # 使用 tqdm 进度条
        try:
            from tqdm import tqdm
            iterator = tqdm(files, desc="处理进度", unit="张",
                          bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]")
        except ImportError:
            iterator = files
            logger.info("提示：安装 tqdm 可显示进度条 (pip install tqdm)")

        for f in iterator:
            result = self.process_file(f, source=source)
            if result:
                results.append(result)

        return results
