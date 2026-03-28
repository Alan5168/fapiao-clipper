"""第1级引擎：PDF 文本提取 (PyMuPDF / pdfplumber)"""
import logging
import re
from pathlib import Path
from typing import Optional

from .base import BaseEngine, EngineResult

logger = logging.getLogger(__name__)

# 发票关键字段正则模式
FIELD_PATTERNS = {
    "invoice_number": [
        r"发票号码[：:]\s*(\d{20})",
        r"\[(\d{20})\]",
        r"\b(\d{20})\b",
    ],
    "invoice_code": [
        r"发票代码[：:]\s*(\d{12})",
        r"\b(\d{12})\b",
    ],
    "date": [
        r"开票日期[：:]\s*(\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)",
    ],
    "amount_with_tax": [
        r"价税合计[（大].*?[¥￥]\s*([0-9,]+\.?\d*)",
        r"合计[（].*?[¥￥]\s*([0-9,]+\.?\d*)",
        r"[¥￥]\s*([0-9,]+\.?\d*)",  # 兜底：最大的金额
    ],
    "tax": [
        r"税额[（].*?[¥￥]\s*([0-9,]+\.?\d*)",
    ],
    "amount": [
        r"不含税金额[：:]\s*[¥￥]\s*([0-9,]+\.?\d*)",
    ],
    "seller": [
        r"销售方[名称]*[：:]\s*([^\n]{4,30})",
        r"销方[名称]*[：:]\s*([^\n]{4,30})",
    ],
    "buyer": [
        r"购买方[名称]*[：:]\s*([^\n]{4,30})",
        r"购方[名称]*[：:]\s*([^\n]{4,30})",
    ],
    "invoice_type": [
        r"发票类型[：:]\s*([^\n]+)",
    ],
}


def _normalize_date(text: str) -> str:
    """统一日期格式为 YYYY-MM-DD"""
    m = re.search(r'(\d{4})[-年](\d{1,2})[-月](\d{1,2})', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return text


def _parse_amounts(text: str) -> list:
    """提取所有金额并排序"""
    amounts = re.findall(r'[¥￥]\s*([0-9,]+\.?\d*)', text)
    return sorted(set([float(a.replace(',', '')) for a in amounts if a]))


def _extract_fields(text: str) -> Optional[dict]:
    """从文本中提取发票字段"""
    if not text or len(text) < 10:
        return None

    result = {}

    # 发票号码
    for pat in FIELD_PATTERNS["invoice_number"]:
        m = re.search(pat, text)
        if m:
            result["invoice_number"] = m.group(1).strip()
            break

    # 开票日期
    for pat in FIELD_PATTERNS["date"]:
        m = re.search(pat, text)
        if m:
            result["date"] = _normalize_date(m.group(1))
            break

    # 金额（先精确匹配，再兜底）
    amounts = _parse_amounts(text)
    if amounts:
        result["amount_with_tax"] = amounts[-1]  # 最大 = 价税合计
        if len(amounts) >= 2 and amounts[0] < amounts[-1] * 0.3:
            result["tax"] = amounts[0]          # 最小 = 税额
        if len(amounts) >= 3:
            for a in amounts[1:-1]:
                if a != amounts[0] and a != amounts[-1]:
                    result["amount"] = a
                    break

    # 销售方 / 购买方（简单名称匹配）
    seller_m = re.search(r'销售方[名称]*[：:]\s*([^\n]{4,30})', text)
    if seller_m:
        result["seller"] = seller_m.group(1).strip()
    buyer_m = re.search(r'购买方[名称]*[：:]\s*([^\n]{4,30})', text)
    if buyer_m:
        result["buyer"] = buyer_m.group(1).strip()

    # 发票类型
    type_m = re.search(r'发票类型[：:]\s*([^\n]+)', text)
    if type_m:
        result["invoice_type"] = type_m.group(1).strip()

    return result if result else None


def _is_searchable_pdf(pdf_path: str) -> bool:
    """判断 PDF 是否为可搜索（文本型）"""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        for page in doc:
            if page.get_text("text").strip():
                doc.close()
                return True
        doc.close()
        return False
    except Exception:
        return False


def _extract_text_fitz(pdf_path: str) -> Optional[str]:
    """用 PyMuPDF 提取文本"""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        texts = []
        for page in doc:
            t = page.get_text("text").strip()
            if t:
                texts.append(t)
        doc.close()
        return "\n".join(texts) if texts else None
    except Exception as e:
        logger.warning(f"PyMuPDF 提取失败: {e}")
        return None


def _extract_text_pdfplumber(pdf_path: str) -> Optional[str]:
    """用 pdfplumber 提取文本（含表格）"""
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            texts = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texts.append(t)
                # 同时尝试提取表格
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            texts.append(" | ".join(str(c) or "" for c in row))
        return "\n".join(texts) if texts else None
    except Exception as e:
        logger.warning(f"pdfplumber 提取失败: {e}")
        return None


class PdfTextEngine(BaseEngine):
    """第1级引擎：PDF 文本提取"""
    name = "pdf_text"
    priority = 1

    def is_available(self) -> bool:
        return True  # 始终可用，失败就降级

    def extract(self, file_path: str) -> EngineResult:
        path = Path(file_path)
        suffix = path.suffix.lower()

        # 只处理 PDF
        if suffix == ".pdf":
            raw = self._extract_pdf_text(file_path)
        elif suffix in (".ofd", ".png", ".jpg", ".jpeg"):
            # 图片/OFD 走 OCR
            return EngineResult(data=None, confidence=0, engine=self.name)
        else:
            return EngineResult(data=None, confidence=0, engine=self.name)

        if not raw or len(raw) < 20:
            return EngineResult(data=None, confidence=0, engine=self.name, raw_text=raw or "")

        # 提取字段
        fields = _extract_fields(raw)
        if not fields:
            return EngineResult(data=None, confidence=0, engine=self.name, raw_text=raw)

        # 简单置信度评估：字段越多越可信
        confidence = min(1.0, len(fields) / 5.0)
        logger.info(f"第1级 PDF 文本提取成功，置信度={confidence:.2f}，字段={list(fields.keys())}")

        return EngineResult(data=fields, confidence=confidence, engine=self.name, raw_text=raw)

    def _extract_pdf_text(self, pdf_path: str) -> Optional[str]:
        # 先尝试 PyMuPDF（更快）
        text = _extract_text_fitz(pdf_path)
        if text and len(text) > 50:
            return text
        # 再试 pdfplumber（支持表格）
        text2 = _extract_text_pdfplumber(pdf_path)
        if text2 and len(text2) > 50:
            return text2
        return text  # 返回任一结果
