FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（FFmpeg + OpenCV 运行库）
# 注意：Debian 12 (Bookworm) 中 libgl1-mesa-glx 已被 libgl1 替代
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip "setuptools<70" wheel && \
    pip install --no-cache-dir -r requirements.txt

# 创建运行时目录
RUN mkdir -p uploads outputs temp

COPY . .

# Hugging Face Spaces 标准端口 7860
EXPOSE 7860

# app.py 会读取 PORT 环境变量（HF 注入 PORT=7860）
CMD ["python", "app.py"]
