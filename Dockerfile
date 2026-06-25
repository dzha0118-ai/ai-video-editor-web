FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（FFmpeg + 构建工具）
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建目录
RUN mkdir -p uploads outputs temp

COPY . .

# Hugging Face Spaces 标准端口 7860，Render 兼容 8001
EXPOSE 7860
EXPOSE 8001

# 让 app.py 自己读取 PORT 环境变量（Hugging Face 设置 PORT=7860）
CMD ["python", "app.py"]
