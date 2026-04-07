"""
第2/3/4级引擎：Ollama 视觉模型
 - GLM-OCR（主力）
 - TurboQuant Ollama server（可选，32GB 内存优化）
 - Qwen3-VL（最终 fallback）
"""
import base64
import json
import logging
import re
from pathlib import Path
from typing import Optional

import httpx

from .base import BaseEngine, EngineResult

logger = logging.getLogger(__name__)

VISION_PROMPT = """请识别这张发票图片，严格以 JSON 格式返回以下字段：
{
  "invoice_number": "发票号码（20位数字）",
  "invoice_code": "发票代码（12位数字）",
  "date": "开票日期，格式 YYYY-MM-DD",
  "amount": "不含税金额（小写数字）",
  "amount_with_tax": "价税合计（最大的金额，等于不含税+税额）",
  "tax": "税额（单独列出的税金）",
  "seller": "销售方名称",
  "buyer": "购买方名称",
  "category": "餐饮/交通/住宿/办公/服务/商品/其他",
  "invoice_type": "发票类型（增值税电子普通发票/专用发票等）"
}

【重要金额规则】
- amount_with_tax（价税合计）= 发票上最大的金额
- tax（税额）= 单独列出的税金，比价税合计小很多
- amount（不含税金额）= 价税合计 - 税额

只返回 JSON，不要任何解释文字。"""


def _parse_json_safe(text: str) -> Optional[dict]:
    """从模型输出中安全解析 JSON"""
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


def _normalize_date(text: str) -> str:
    m = re.search(r'(\d{4})[-年](\d{1,2})[-月](\d{1,2})', text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return text


def _normalize_amount(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return None


def _post_process(data: dict) -> dict:
    """标准化字段格式"""
    if "date" in data and data["date"]:
        data["date"] = _normalize_date(str(data["date"]))
    for key in ["amount", "amount_with_tax", "tax", "amount"]:
        if key in data:
            data[key] = _normalize_amount(data[key])
    return data


class OllamaVisionEngine(BaseEngine):
    """
    Ollama 视觉模型引擎
    支持标准 Ollama server 和 TurboQuant 自定义 server
    """

    def __init__(self, config: dict, model_name: str, turboquant_url: Optional[str] = None):
        self.cfg = config
        self.model_name = model_name
        self.turboquant_url = turboquant_url  # e.g. "http://127.0.0.1:8080"

        # 优先使用 TurboQuant server
        if turboquant_url:
            self.base_url = turboquant_url.rstrip("/")
            self.is_turboquant = True
        else:
            ollama_cfg = config.get("ocr", {}).get("ollama", {})
            self.base_url = ollama_cfg.get("base_url", "http://127.0.0.1:11434")
            self.is_turboquant = False

    @property
    def name(self) -> str:
        prefix = "turboquant" if self.is_turboquant else "ollama"
        return f"{prefix}:{self.model_name}"

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code != 200:
                return False
            available = [m.get("name", "") for m in resp.json().get("models", [])]
            ok = any(self.model_name.split(":")[0] in m for m in available)
            if ok:
                mode = "TurboQuant" if self.is_turboquant else "Ollama"
                logger.info(f"✅ {mode} 视觉引擎可用: {self.model_name}")
            return ok
        except Exception as e:
            if self.is_turboquant:
                logger.warning(f"TurboQuant server {self.base_url} 不可用: {e}")
            return False

    def extract(self, file_path: str) -> EngineResult:
        """对图片文件执行 OCR 识别"""
        image_bytes = self._file_to_image(file_path)
        if not image_bytes:
            return EngineResult(data=None, confidence=0, engine=self.name, error="图片转换失败")

        b64 = base64.b64encode(image_bytes).decode()

        try:
            # TurboQuant server 也使用 /api/chat 接口
            payload = {
                "model": self.model_name,
                "messages": [{"role": "user", "content": VISION_PROMPT, "images": [b64]}],
                "stream": False,
            }
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=300,  # qwen3-vl 图片处理慢
            )
            if resp.status_code != 200:
                return EngineResult(data=None, confidence=0, engine=self.name, error=f"HTTP {resp.status_code}")

            content = resp.json().get("message", {}).get("content", "")
            data = _parse_json_safe(content)

            if not data:
                return EngineResult(data=None, confidence=0, engine=self.name, raw_text=content, error="JSON 解析失败")

            data = _post_process(data)

            # 关键字段缺失 → 低置信度
            required = ["invoice_number", "amount_with_tax"]
            missing = [k for k in required if not data.get(k)]
            confidence = 0.9 if not missing else 0.4

            return EngineResult(data=data, confidence=confidence, engine=self.name, raw_text=content)

        except Exception as e:
            return EngineResult(data=None, confidence=0, engine=self.name, error=str(e))

    def _file_to_image(self, file_path: str) -> Optional[bytes]:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._pdf_to_image(file_path)
        elif suffix in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            try:
                return Path(file_path).read_bytes()
            except Exception:
                return None
        else:
            return None

    def _pdf_to_image(self, pdf_path: str) -> Optional[bytes]:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            page = doc[0]
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            doc.close()
            return img_bytes
        except Exception as e:
            logger.error(f"PDF 转图片失败: {e}")
            return None
