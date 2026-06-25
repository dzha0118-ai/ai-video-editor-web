# 一键部署到 Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/dzha0118-ai/ai-video-editor-web)

## 本地运行

```bash
pip install -r requirements.txt
python app.py
```

访问 http://localhost:8001

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | 部署者兜底 Key（可选） | 空 |
| `FFMPEG_PATH` | FFmpeg 路径 | `ffmpeg` |
| `MAX_UPLOAD_MB` | 上传限制 | 500 |

## 使用说明

1. 打开网页
2. 填入自己的 DeepSeek API Key（可选）
3. 上传视频
4. 选择剪辑选项，开始处理
5. 下载成片

API Key 仅用于本次请求，不会存储在服务器。
