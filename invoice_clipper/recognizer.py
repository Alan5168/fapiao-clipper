"""
发票识别器 v2.0 - 简化版

二级降级链路：
  第1级  PDF 文本提取  → PyMuPDF / pdfplumber（可搜索 PDF 直接读文字）
  第2级  Ollama Qwen3-VL（最终 fallback）→ 图片/扫描件或第1级失败时

简化原因：
  - 去掉 GLM-OCR（返回 JSON 解析经常失败，不稳定）
  - 去掉 TurboQuant（未启用）
  - PyMuPDF 修复跨行匹配后，90%+ 发票可一次成功
"""
import logging
from pathlib import Path
from typing import Optional

from .engines import PdfTextEngine, OllamaVisionEngine, BaseEngine, EngineResult

logger = logging.getLogger(__name__)


class InvoiceRecognizer:
    """发票识别器（二级降级）"""

    def __init__(self, config: dict):
        self.cfg = config
        self.engines: list[BaseEngine] = []
        self._build_chain()

    def _build_chain(self):
        """构建二级引擎链"""
        ocr_cfg = self.cfg.get("ocr", {})
        ollama_cfg = ocr_cfg.get("ollama", {})
        qwen_model = ollama_cfg.get("qwen_model", "qwen3-vl:latest")

        # === 第1级：PDF 文本提取 ===
        self.engines.append(PdfTextEngine())
        logger.info("✅ 注册第1级引擎: pdf_text")

        # === 第2级：Qwen3-VL（唯一备用）===
        qwen_engine = OllamaVisionEngine(self.cfg, qwen_model)
        if qwen_engine.is_available():
            self.engines.append(qwen_engine)
            logger.info(f"✅ 注册第2级引擎: {qwen_engine.name}")
        else:
            logger.warning(f"⚠️ Qwen3-VL 不可用: {qwen_model}")

        # 按 priority 排序
        self.engines.sort(key=lambda e: e.priority)
        logger.info(f"📋 引擎链构建完成: {[e.name for e in self.engines]}")

    def recognize(self, file_path: str, raw_text: str = "") -> EngineResult:
        """
        对文件执行识别，按引擎链降级。
        """
        path = Path(file_path)
        logger.info(f"开始识别: {path.name}")

        for i, engine in enumerate(self.engines):
            logger.info(f"尝试第{i+1}级引擎: {engine.name}")
            result = engine.extract(str(path))

            if result.is_valid:
                logger.info(f"✅ 第{i+1}级 {engine.name} 识别成功，置信度={result.confidence:.2f}")
                self._log_result(result)
                return result

            logger.warning(f"⚠️ 第{i+1}级 {engine.name} 未通过（{result.error or '无效结果'}）")

        # 全部失败
        logger.error("❌ 所有引擎均失败")
        return EngineResult(data=None, confidence=0, engine="none", error="所有引擎均失败")

    def recognize_batch(self, file_paths: list[str]) -> list[EngineResult]:
        """批量识别"""
        return [self.recognize(fp) for fp in file_paths]

    def _log_result(self, result: EngineResult):
        """记录识别结果字段"""
        if result.data:
            fields = list(result.data.keys())
            logger.debug(f"识别字段: {fields}")