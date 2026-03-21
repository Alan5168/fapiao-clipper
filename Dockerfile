# ============================================================
# Invoice Clipper — Docker 一键部署
# 用法: docker-compose up
# ============================================================
FROM python:3.11-slim

# 安装系统依赖（PDF 渲染 / OCR / 中文支持）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预装 PaddleOCR 模型（首次启动会自动下载）
RUN pip install --no-cache-dir paddlepaddle paddleocr

# 复制应用代码
COPY . .

# 容器默认运行命令：交互式 CLI
CMD ["python3", "main.py", "--help"]
