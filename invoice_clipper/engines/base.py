"""基础引擎抽象"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class EngineResult:
    """识别结果"""
    data: Optional[dict]       # 字段字典
    confidence: float          # 置信度 0-1
    engine: str                # 来源引擎名
    raw_text: str = ""        # 原始文本（供调试）
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.data is not None and self.confidence > 0


class BaseEngine:
    name = "base"
    priority = 99  # 越小越先

    def is_available(self) -> bool:
        """引擎是否可用"""
        raise NotImplementedError

    def extract(self, file_path: str) -> EngineResult:
        """对文件执行识别"""
        raise NotImplementedError
