"""
OpenDataLoader PDF 提取器 - 有序文本提取 + 表格结构保留
可作为 PyMuPDF 的增强替代方案
"""
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Java 环境路径（已安装在 Mac Studio）
JAVA_HOME = "/opt/homebrew/opt/openjdk@11/libexec/openjdk.jdk/Contents/Home"


def check_java_available() -> bool:
    """检查 Java 环境是否可用"""
    java_path = os.path.join(JAVA_HOME, "bin", "java")
    return os.path.exists(java_path)


def extract_text_from_pdf_odl(
    pdf_path: Path,
    format: str = "markdown",
    include_json: bool = False
) -> tuple[str, Optional[dict]]:
    """
    使用 opendataloader-pdf 提取 PDF 文本
    
    优势：
    - 阅读顺序正确（XY-Cut++ 算法）
    - 表格结构保留
    - 输出带 bounding boxes（JSON）
    
    Args:
        pdf_path: PDF 文件路径
        format: 输出格式 (markdown / text)
        include_json: 是否同时输出 JSON（带坐标）
    
    Returns:
        (文本内容, JSON数据或None)
    """
    if not check_java_available():
        raise RuntimeError(
            f"Java 环境不可用。请确保 {JAVA_HOME} 存在。\n"
            "安装方法: brew install openjdk@11"
        )
    
    try:
        import opendataloader_pdf
    except ImportError:
        raise RuntimeError(
            "opendataloader-pdf 未安装。请运行: pip install opendataloader-pdf"
        )
    
    # 设置 Java 环境变量
    os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ["PATH"] = f"{JAVA_HOME}/bin:{os.environ.get('PATH', '')}"
    
    # 创建临时输出目录
    output_dir = tempfile.mkdtemp()
    
    try:
        # 调用 opendataloader-pdf
        output_format = format if not include_json else f"{format},json"
        opendataloader_pdf.convert(
            input_path=[str(pdf_path)],
            output_dir=output_dir,
            format=output_format
        )
        
        # 读取 markdown 输出
        md_file = os.path.join(output_dir, pdf_path.name.replace('.pdf', '.md'))
        text = ""
        if os.path.exists(md_file):
            with open(md_file) as f:
                text = f.read()
        
        # 读取 JSON 输出（如果需要）
        json_data = None
        if include_json:
            json_file = os.path.join(output_dir, pdf_path.name.replace('.pdf', '.json'))
            if os.path.exists(json_file):
                import json
                with open(json_file) as f:
                    json_data = json.load(f)
        
        return text, json_data
    
    finally:
        # 清理临时目录
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)


def batch_extract_text_odl(
    pdf_paths: list[Path],
    format: str = "markdown"
) -> dict[str, str]:
    """
    批量提取 PDF 文本（一次 JVM 启动，多文件处理）
    
    相比单文件处理，减少 JVM 启动开销
    
    Args:
        pdf_paths: PDF 文件路径列表
        format: 输出格式
    
    Returns:
        {文件名: 文本内容} 字典
    """
    if not check_java_available():
        raise RuntimeError(f"Java 环境不可用: {JAVA_HOME}")
    
    try:
        import opendataloader_pdf
    except ImportError:
        raise RuntimeError("opendataloader-pdf 未安装")
    
    os.environ["JAVA_HOME"] = JAVA_HOME
    os.environ["PATH"] = f"{JAVA_HOME}/bin:{os.environ.get('PATH', '')}"
    
    output_dir = tempfile.mkdtemp()
    
    try:
        opendataloader_pdf.convert(
            input_path=[str(p) for p in pdf_paths],
            output_dir=output_dir,
            format=format
        )
        
        results = {}
        for pdf_path in pdf_paths:
            md_file = os.path.join(output_dir, pdf_path.name.replace('.pdf', '.md'))
            if os.path.exists(md_file):
                with open(md_file) as f:
                    results[pdf_path.name] = f.read()
        
        return results
    
    finally:
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)


def smart_extract_text(
    pdf_path: Path,
    prefer_odl: bool = False,
    include_json: bool = False
) -> tuple[str, Optional[dict]]:
    """
    智能选择 PDF 提取引擎
    
    优先级：
    1. 如果 prefer_odl=True 且 Java 可用 → opendataloader-pdf
    2. 否则 → PyMuPDF（快速，无需 Java）
    
    Args:
        pdf_path: PDF 文件路径
        prefer_odl: 是否优先使用 opendataloader-pdf
        include_json: 是否输出 JSON（仅 ODL 支持）
    
    Returns:
        (文本内容, JSON数据或None)
    """
    if prefer_odl and check_java_available():
        try:
            logger.info(f"使用 opendataloader-pdf 提取: {pdf_path.name}")
            return extract_text_from_pdf_odl(pdf_path, include_json=include_json)
        except Exception as e:
            logger.warning(f"opendataloader-pdf 失败，降级到 PyMuPDF: {e}")
    
    # 使用 PyMuPDF
    from .file_processor import extract_text_from_pdf
    logger.info(f"使用 PyMuPDF 提取: {pdf_path.name}")
    text = extract_text_from_pdf(pdf_path)
    return text, None