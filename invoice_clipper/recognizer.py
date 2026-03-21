"""
发票识别模块

架构（两级 + 本地兜底）：
  第1级  Python 正则  → 免费，数字 PDF 直接出字段
  第2级  Ollama GLM-OCR（轻量~4GB） → 图片/扫描件
  第3级  Ollama Qwen3-VL（兜底）   → GLM-OCR 失败时

说明：
  大部分发票（数字 PDF）第1级搞定，零成本。
  只有扫描件/照片才走第2/3级。
"""

import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

VISION_PROMPT = """请识别这张发票图片，提取关键字段并以 JSON 格式返回：
{
  "invoice_number": "发票号码（右上角）",
  "invoice_code": "发票代码",
  "date": "开票日期，格式 YYYY-MM-DD",
  "amount": 不含税金额（金额小写）,
  "amount_with_tax": 价税合计（发票上最大的金额，等于不含税金额+税额，通常在右下角或合计栏）,
  "tax": 税额（单独的一行，通常比价税合计小很多）,
  "seller": "销售方名称",
  "buyer": "购买方名称",
  "category": "餐饮/交通/住宿/办公/服务/商品/其他",
  "invoice_type": "发票类型"
}

【重要】区分金额字段：
- amount_with_tax（价税合计）= 发票上最大的金额，是最终要付的钱
- tax（税额）= 单独列出的税金，通常比价税合计小很多
- amount（不含税金额）= 价税合计 - 税额

只返回 JSON，不要解释。"""


def _is_valid_result(result: dict) -> bool:
    if not result:
        return False
    return bool(result.get("amount_with_tax") is not None)


def _parse_json_safe(text: str) -> Optional[dict]:
    text = text.strip()
    for part in text.split("```"):
        part = part.strip().lstrip("json").strip()
        try:
            return json.loads(part)
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None


class BaseVisionEngine:
    name = "base"

    def __init__(self, config: dict):
        self.cfg = config

    def is_available(self) -> bool:
        raise NotImplementedError

    def extract(self, image_bytes: bytes) -> Optional[dict]:
        raise NotImplementedError


class OllamaVisionEngine(BaseVisionEngine):
    """Ollama 本地视觉模型"""

    def __init__(self, config: dict, model_key: str, model_name: str):
        super().__init__(config)
        self.model_key = model_key
        self.model_name = model_name
        ocfg = config.get("ocr", {}).get("ollama", {})
        self.base_url = ocfg.get("base_url", "http://127.0.0.1:11434")

    def is_available(self) -> bool:
        try:
            import httpx
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            available = [m.get("name", "") for m in resp.json().get("models", [])]
            ok = any(self.model_name.split(":")[0] in m for m in available)
            if ok:
                logger.info(f"✅ 第2级视觉引擎: {self.model_name}")
            return ok
        except Exception:
            return False

    def extract(self, image_bytes: bytes) -> Optional[dict]:
        import httpx
        b64 = base64.b64encode(image_bytes).decode()
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": VISION_PROMPT, "images": [b64]}],
            "stream": False,
        }
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=60)
        if resp.status_code != 200:
            return None
        content = resp.json().get("message", {}).get("content", "")
        return _parse_json_safe(content)


class InvoiceRecognizer:
    """两级识别器：正则 → 视觉模型"""

    def __init__(self, config: dict):
        self.cfg = config
        ocr_cfg = config.get("ocr", {})
        self.vision_engines = []
        ollama_cfg = ocr_cfg.get("ollama", {})
        if ollama_cfg:
            models = ollama_cfg.get("models", [])
            if not models:
                models = [("glm_ocr", "glm-ocr:latest"), ("qwen_vl", "qwen3-vl:30b")]
            for key, name in models:
                engine = OllamaVisionEngine(config, key, name)
                if engine.is_available():
                    self.vision_engines.append(engine)

    def recognize(self, pdf_path: Path, raw_text: str = "") -> Optional[dict]:
        result = self._extract_by_regex(raw_text)
        if _is_valid_result(result):
            logger.info("第1级：Python 正则提取成功")
            return result
        logger.warning("第1级字段不全，进入第2级")
        for engine in self.vision_engines:
            logger.info(f"第2级：{engine.model_name} 视觉识别")
            try:
                image_bytes = self._pdf_to_image(pdf_path)
                if image_bytes:
                    result = engine.extract(image_bytes)
                    if _is_valid_result(result):
                        return result
            except Exception as e:
                logger.warning(f"视觉引擎 {engine.name} 失败: {e}")
        return None

    def _extract_by_regex(self, text: str) -> Optional[dict]:
        if not text:
            return None
        result = {}
        
        # 发票号码（20位数字）
        all_20digits = re.findall(r'\b(\d{20})\b', text)
        if all_20digits:
            result["invoice_number"] = all_20digits[0]
        
        # 开票日期
        m = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', text)
        if m:
            result["date"] = m.group(1)
        
        # 提取所有 ¥ 后面的金额
        amounts = re.findall(r'[¥￥]\s*([0-9,]+\.?\d*)', text)
        if amounts:
            amounts = sorted(set([float(a.replace(',', '')) for a in amounts]))
            if amounts:
                result["amount_with_tax"] = amounts[-1]  # 最大的是价税合计
            if len(amounts) >= 2 and amounts[0] < amounts[-1] * 0.2:
                result["tax"] = amounts[0]  # 最小的是税额
            if len(amounts) >= 3:
                for a in amounts:
                    if a != amounts[0] and a != amounts[-1]:
                        result["amount"] = a
                        break
        
        # 销售方
        m = re.search(r'(北京[^有限\s]+有限公司)', text)
        if not m:
            m = re.search(r'(陵水[^有限\s]+有限公司)', text)
        if m:
            result["seller"] = m.group(1).strip()
        
        # 购买方
        buyers = re.findall(r'(陵水[^有限\s]*有限公司)', text)
        if buyers:
            result["buyer"] = buyers[0]
        
        return result if result else None

    def _pdf_to_image(self, pdf_path: Path) -> Optional[bytes]:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes
        except Exception as e:
            logger.error(f"PDF 转图片失败: {e}")
            return None