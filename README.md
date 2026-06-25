# ClipAI — 智能视频剪辑工具

基于 AI + FFmpeg 的本地视频剪辑 Web 应用，支持**用户自带 API Key 的 SaaS 模式**、自动去静音、智能字幕、音频降噪、简单动效。

> 🚀 **v2.0 更新：SaaS 化改造**
> - 每个用户使用自己的 DeepSeek API Key，部署者零成本
> - 完整的 API Key 安全保护：不写入代码、不写入日志、不持久化到文件
> - 支持环境变量 / .env 文件 / 用户表单输入三种配置方式

## 特性

- 拖拽上传视频，一键智能剪辑
- **用户自带 API Key（SaaS）** — 安全输入，不上传服务端，直接使用
- **DeepSeek LLM 导演** — 用大语言模型理解内容，做出专业剪辑决策
- **自动去静音** — 识别并删除停顿、废话、填充词
- **智能字幕** — Whisper 语音识别，自动生成带时间轴字幕
- **音频降噪** — FFT 频域降噪，去除环境噪音
- **关键放大动效** — 关键片段自动添加 Zoom In 效果
- **实时进度** — WebSocket 推送，处理过程一目了然
- **多风格预设** — Vlog / 播客 / 短视频 三种风格

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vanilla JS + CSS3（Open Design 规范） |
| 后端 | FastAPI + Python 3.12+ |
| 语音识别 | OpenAI Whisper |
| 剪辑决策 | DeepSeek LLM / 规则引擎双模式 |
| 视频执行 | FFmpeg + MoviePy |
| 音频处理 | pydub + FFmpeg afftdn |

---

## 快速启动

### 1. 克隆项目

```bash
git clone <your-repo>
cd ai-video-editor-web
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

**项目支持三种 API Key 配置方式，优先级从高到低：**

```
用户表单输入 > 环境变量 / .env 文件 > config.toml 文件 > 空值（回退规则引擎）
```

#### 方式 A：.env 文件（推荐本地开发）

```bash
# 复制模板文件
cp .env.example .env

# 编辑 .env 填入你的 Key
DEEPSEEK_API_KEY=sk-你的DeepSeekAPIKey
FFMPEG_PATH=ffmpeg
```

> `.env` 文件已在 `.gitignore` 中配置，不会提交到 Git。

#### 方式 B：系统环境变量（推荐生产部署）

**Windows (CMD):**
```cmd
set DEEPSEEK_API_KEY=sk-你的Key
set FFMPEG_PATH=ffmpeg
```

**Windows (PowerShell):**
```powershell
$env:DEEPSEEK_API_KEY = "sk-你的Key"
$env:FFMPEG_PATH = "ffmpeg"
```

**Linux / macOS:**
```bash
export DEEPSEEK_API_KEY=sk-你的Key
export FFMPEG_PATH=ffmpeg
```

#### 方式 C：用户自带 Key（SaaS 模式）

启动后访问 `http://localhost:8000`，在页面输入框中填入自己的 DeepSeek API Key，**Key 直接通过后端透传到 LLM 请求，不落盘、不记录**。

### 4. 配置 FFmpeg

**方案 A：自动配置（推荐）**

```bash
python setup_ffmpeg.py
```

**方案 B：手动配置**

1. 从 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载 `ffmpeg-release-essentials.zip`
2. 解压到任意目录（如 `C:\Program Files\FFmpeg`）
3. 将 `bin` 目录添加到系统 PATH
4. 在 `.env` 中设置 `FFMPEG_PATH=C:/Program Files/FFmpeg/bin/ffmpeg.exe`

### 5. 启动服务

```bash
python app.py
```

浏览器打开：**http://localhost:8000**

启动时会自动打印配置状态（API Key 脱敏显示）：

```
[Config] DeepSeek API Key: ✅ 已配置 (sk-abC...xYz1)
[Config] Base URL: https://api.deepseek.com/v1
[Config] Model: deepseek-chat
[Config] FFmpeg: ffmpeg
[Config] Max Upload: 500 MB
```

---

## 环境变量完整配置参考

| 变量名 | 默认值 | 说明 | 是否必填 |
|--------|--------|------|----------|
| `DEEPSEEK_API_KEY` | 空字符串 | DeepSeek API Key | SaaS 模式下可留空 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | DeepSeek API 地址 | 否 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 | 否 |
| `DEEPSEEK_TEMPERATURE` | `0.3` | 温度参数 | 否 |
| `FFMPEG_PATH` | `ffmpeg` | FFmpeg 可执行文件路径 | 如果未在 PATH 中则必填 |
| `FFPROBE_PATH` | `ffprobe` | FFprobe 可执行文件路径 | 如果未在 PATH 中则必填 |
| `WHISPER_MODEL` | `base` | Whisper 模型大小 | 否 |
| `WHISPER_LANGUAGE` | `auto` | 语音识别语言 | 否 |
| `MAX_UPLOAD_MB` | `500` | 最大上传文件大小（MB） | 否 |
| `TEMP_CLEANUP_MIN` | `30` | 临时文件清理间隔（分钟） | 否 |

---

## 平台部署指南

### Docker 部署

```bash
# 构建镜像
docker build -t ai-video-editor .

# 运行（传入环境变量）
docker run -p 8000:8000 \
  -e DEEPSEEK_API_KEY=sk-你的Key \
  -e FFMPEG_PATH=ffmpeg \
  ai-video-editor
```

### Render 一键部署

项目已包含 `render.yaml`，支持 Render 一键部署：

1. Fork 本仓库到 GitHub
2. 在 Render 创建 New Web Service
3. 选择你的仓库，系统自动识别 `render.yaml`
4. 在 Environment 页面添加 `DEEPSEEK_API_KEY`（可选，留空即 SaaS 模式）
5. 部署完成

### Hugging Face Spaces 部署（免费，无需银行卡）

**注意：Hugging Face 免费 Space 会在 15 分钟无活动后自动休眠，下次访问需等待唤醒。**

#### 部署步骤

1. 打开 [https://huggingface.co/spaces](https://huggingface.co/spaces)，登录账号
2. 点击 **Create new Space**
3. 填写信息：
   - **Space name**: `ai-video-editor`（或任意名称）
   - **License**: MIT
   - **Space SDK**: 选择 **Docker**（空白）
   - **Space hardware**: CPU free（默认）
   - 其他保持默认
4. 在 **Files** 标签页，点击 **Upload files**，上传本仓库所有文件
   - 或选择 **Connect to GitHub**，连接你的 GitHub 仓库
5. 等待自动构建（约 2-5 分钟）

#### 配置环境变量

构建完成后，进入 **Settings → Variables and Secrets**：

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `DEEPSEEK_API_KEY` | `sk-xxx` | 你的 DeepSeek Key（可选，留空走 SaaS 模式） |
| `MAX_UPLOAD_MB` | `50` | Hugging Face 免费版建议设为 50（存储限制） |

点击 **Save** 后 Space 会自动重启。

####  Hugging Face 限制

| 限制项 | 免费版 | 说明 |
|--------|--------|------|
| 内存 | 2 GB | 处理 1080p 视频可能吃紧，建议上传 720p 以下 |
| 存储 | 20 GB | 包含系统和依赖，实际可用约 10 GB |
| 休眠 | 15 分钟无活动 | 休眠后首次访问需等待 30-60 秒唤醒 |
| 上传大小 | 约 50 MB | 取决于具体硬件限制 |
| 单次运行时长 | 无硬性限制 | 但长视频处理可能超时 |

> 💡 **建议**：Hugging Face 适合演示和轻量使用。如果需要处理大视频或常驻服务，建议使用 Render 或其他 VPS。

### 生产环境最佳实践

- **永远不要**将 `.env` 文件或 `config.toml` 提交到 Git（已配置 `.gitignore`）
- **生产环境**优先使用系统环境变量，而非 `.env` 文件
- **SaaS 模式**下，部署者无需配置任何 Key，用户自带即可
- 如需托管模式，在服务器环境变量中设置 `DEEPSEEK_API_KEY`，所有用户共用

---

## 项目结构

```
ai-video-editor-web/
├── app.py                    # FastAPI 主入口
├── config.toml.example       # 配置模板（不含敏感信息）
├── .env.example              # 环境变量模板
├── .gitignore               # Git 忽略配置（含 .env, config.toml）
├── requirements.txt          # Python 依赖
├── setup_ffmpeg.py           # FFmpeg 自动配置脚本
├── Dockerfile               # Docker 构建（支持 Render + Hugging Face）
├── render.yaml              # Render 部署配置
├── modules/
│   ├── config.py            # 配置加载（环境变量优先）
│   ├── transcriber.py       # Whisper 语音识别
│   ├── analyzer.py          # 剪辑分析（规则 + LLM）
│   ├── llm_director.py      # DeepSeek LLM 导演（SaaS Key 透传）
│   ├── renderer.py           # FFmpeg/MoviePy 渲染
│   └── audio_processor.py  # 音频降噪/处理
├── templates/
│   └── index.html            # 前端页面（含 API Key 输入框）
├── static/
│   ├── css/style.css         # 样式（Open Design）
│   └── js/main.js            # 前端交互
├── uploads/                  # 上传文件（运行时创建，不提交）
├── outputs/                  # 输出成片（运行时创建，不提交）
└── temp/                     # 临时文件（运行时创建，不提交）
```

---

## 关于"多模态 AI"的问题

**Q: 需要接入多模态 AI（理解视频画面）吗？**

A: **不是必须的。** 当前系统的剪辑决策是"语音驱动"的：

```
视频 → Whisper 语音识别 → 文本 + 时间轴 → LLM 分析 → 剪辑决策
```

这已经能做出非常好的效果，因为大多数口播/播客/Vlog 视频的核心内容都在语音里。

**多模态（如 GPT-4o、Qwen2-VL）锦上添花，但不是必需的：**
- 多模态可以理解画面内容、表情、场景切换，但成本更高
- 当前 DeepSeek 文本模型做导演决策已经足够聪明
- 后续如需增强，可以扩展 `llm_director.py` 接入多模态 API

---

## 注意事项

- 首次运行会下载 Whisper `base` 模型（约 74MB）
- 视频处理是 CPU 密集型，长视频可能需要几分钟
- `.env` 和 `config.toml` 已配置在 `.gitignore` 中，不会提交到 Git
- 前端 API Key 输入框使用 `type="password"`，输入时不可见

## License

MIT
