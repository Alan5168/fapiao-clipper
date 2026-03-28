"""
发票识别器 v1.1

四级降级链路：
  第1级  PDF 文本提取  → PyMuPDF / pdfplumber（可搜索 PDF 直接读文字）
  第2级  Ollama GLM-OCR（本地）→ 图片/扫描件，零 API 成本
  第3级  TurboQuant Ollama（可选）→ 32GB 内存优化，KV Cache 压缩 4-5x
  第4级  Ollama Qwen3-VL（最终 fallback）→ 释放资源

配置示例（config.yaml）：
  ocr:
    ollama:
      base_url: http://127.0.0.1:11434
      glm_model: glm-ocr:latest
      qwen_model: qwen3-vl:latest
    turboquant:
      enabled: true
      base_url: http://127.0.0.1:8080   # TurboQuant server（TheTom/llama-cpp-turboquant fork）
      glm_model: glm-ocr:latest
      qwen_model: qwen3-vl:latest
"""
import logging
from pathlib import Path
from typing import Optional

from .engines import PdfTextEngine, OllamaVisionEngine, BaseEngine, EngineResult

logger = logging.getLogger(__name__)


class InvoiceRecognizer:
    """发票识别器（四级降级）"""

    def __init__(self, config: dict):
        self.cfg = config
        self.engines: list[BaseEngine] = []
        self._build_chain()

    def _build_chain(self):
        """按优先级构建引擎链"""
        ocr_cfg = self.cfg.get("ocr", {})

        # === 第1级：PDF 文本提取（始终注册）===
        self.engines.append(PdfTextEngine())

        # === 第2级：标准 Ollama GLM-OCR ===
        ollama_cfg = ocr_cfg.get("ollama", {})
        glm_model = ollama_cfg.get("glm_model", "glm-ocr:latest")
        qwen_model = ollama_cfg.get("qwen_model", "qwen3-vl:latest")

        glm_engine = OllamaVisionEngine(self.cfg, glm_model)
        if glm_engine.is_available():
            self.engines.append(glm_engine)
            logger.info(f"✅ 注册第2级引擎: {glm_engine.name}")
        else:
            logger.warning(f"⚠️ Ollama GLM-OCR 不可用: {glm_model}")

        # === 第3级：TurboQuant Ollama（可选）===
        tq_cfg = ocr_cfg.get("turboquant", {})
        if tq_cfg.get("enabled") and tq_cfg.get("base_url"):
            tq_glm = OllamaVisionEngine(
                self.cfg,
                tq_cfg.get("glm_model", glm_model),
                turboquant_url=tq_cfg.get("base_url"),
            )
            if tq_glm.is_available():
                self.engines.append(tq_glm)
                logger.info(f"✅ 注册第3级引擎（TurboQuant）: {tq_glm.name}")
            else:
                logger.warning(f"⚠️ TurboQuant server 不可用: {tq_cfg.get('base_url')}")
        else:
            logger.info("ℹ️ TurboQuant 未启用（可通 config.yaml 开启）")

        # === 第4级：Qwen3-VL fallback ===
        qwen_engine = OllamaVisionEngine(self.cfg, qwen_model)
        if qwen_engine.is_available():
            self.engines.append(qwen_engine)
            logger.info(f"✅ 注册第4级 fallback 引擎: {qwen_engine.name}")
        else:
            logger.warning(f"⚠️ Ollama Qwen3-VL 不可用: {qwen_model}")

        # 按 priority 排序（数字小的在前）
        self.engines.sort(key=lambda e: e.priority)
        logger.info(f"📋 引擎链构建完成: {[e.name for e in self.engines]}")

    def recognize(self, file_path: str, raw_text: str = "") -> EngineResult:
        """
        对文件执行识别，按引擎链降级。

        Args:
            file_path: 文件路径（PDF/OFD/图片）
            raw_text:  已有的原始文本（第1级失败时传入）

        Returns:
            EngineResult: 包含识别结果、置信度、来源引擎
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
