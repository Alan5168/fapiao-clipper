"""
发票识别引擎模块 (v1.1)

架构（四级降级）：
  第1级  PDF 文本提取  → PyMuPDF / pdfplumber 直接读可搜索 PDF
  第2级  Ollama GLM-OCR（本地） → 图片/扫描件
  第3级  TurboQuant Ollama（可选，自定义 server） → 内存优化模式
  第4级  Ollama Qwen3-VL（最终 fallback） → 释放资源

TurboQuant（可选）：
  - 适用 32GB 以下机器，KV Cache 压缩 4-5x
  - 通过自定义 server 地址接入（TheTom/llama-cpp-turboquant fork）
  - 不影响默认体验，未配置则走标准 Ollama
"""

from .base import BaseEngine, EngineResult
from .pdf_text import PdfTextEngine
from .ollama_vision import OllamaVisionEngine

__all__ = ["BaseEngine", "EngineResult", "PdfTextEngine", "OllamaVisionEngine"]
