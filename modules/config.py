# -*- coding: utf-8 -*-
"""
配置加载模块

优先级（从高到低）：
1. 环境变量（os.environ）
2. .env 文件（python-dotenv 加载）
3. config.toml 文件
4. 代码默认值

安全原则：
- .env 和 config.toml 包含真实 Key，绝对不要提交到 Git
- .env.example 是模板，可以提交，供他人参考
- 启动时会打印配置状态（Key 脱敏显示）
"""
import os
from pathlib import Path
import toml

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

BASE_DIR = Path(__file__).parent.parent.resolve()
CONFIG_PATH = BASE_DIR / "config.toml"
ENV_PATH = BASE_DIR / ".env"

def _load_dotenv():
    """加载 .env 文件（如果存在）"""
    if load_dotenv and ENV_PATH.exists():
        load_dotenv(str(ENV_PATH), override=True)
        print(f"[Config] 已加载 .env 文件: {ENV_PATH}")
        return True
    return False

def load_config():
    """加载配置，环境变量优先"""
    # 先加载 .env 文件到环境变量
    _load_dotenv()
    
    defaults = {
        "deepseek": {
            "api_key": os.environ.get("DEEPSEEK_API_KEY", ""),
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
            "temperature": float(os.environ.get("DEEPSEEK_TEMPERATURE", "0.3")),
        },
        "ffmpeg": {
            "ffmpeg_path": os.environ.get("FFMPEG_PATH", "ffmpeg"),
            "ffprobe_path": os.environ.get("FFPROBE_PATH", "ffprobe"),
        },
        "whisper": {
            "model_size": os.environ.get("WHISPER_MODEL", "base"),
            "language": os.environ.get("WHISPER_LANGUAGE", "auto"),
        },
        "app": {
            "max_upload_mb": int(os.environ.get("MAX_UPLOAD_MB", "500")),
            "temp_cleanup_min": int(os.environ.get("TEMP_CLEANUP_MIN", "30")),
        },
    }
    
    # 如果 config.toml 存在，用它的值覆盖默认值（但环境变量仍优先）
    if CONFIG_PATH.exists():
        try:
            user_config = toml.load(CONFIG_PATH)
            for section, values in user_config.items():
                if section in defaults:
                    for key, val in values.items():
                        env_key = f"{section.upper()}_{key.upper()}" if section != "deepseek" else f"DEEPSEEK_{key.upper()}"
                        # 环境变量存在时不覆盖；否则用 config.toml 的值覆盖默认值
                        if env_key not in os.environ and key not in defaults[section]:
                            defaults[section][key] = val
                        elif env_key not in os.environ and key in defaults[section]:
                            defaults[section][key] = val
        except Exception as e:
            print(f"[Config] WARNING: 读取 config.toml 失败: {e}")
    
    return defaults

# 全局配置对象
CONFIG = load_config()

# 导出常用配置
DEEPSEEK_API_KEY = CONFIG["deepseek"]["api_key"]
DEEPSEEK_BASE_URL = CONFIG["deepseek"]["base_url"]
DEEPSEEK_MODEL = CONFIG["deepseek"]["model"]
DEEPSEEK_TEMPERATURE = CONFIG["deepseek"]["temperature"]

FFMPEG_PATH = CONFIG["ffmpeg"]["ffmpeg_path"]
FFPROBE_PATH = CONFIG["ffmpeg"]["ffprobe_path"]

WHISPER_MODEL = CONFIG["whisper"]["model_size"]
WHISPER_LANGUAGE = CONFIG["whisper"]["language"]

MAX_UPLOAD_MB = CONFIG["app"]["max_upload_mb"]

def print_config_status():
    """打印配置状态（Key 脱敏）"""
    key = DEEPSEEK_API_KEY
    key_status = f"✅ 已配置 ({key[:6]}...{key[-4:]})" if key else "❌ 未配置"
    print(f"[Config] DeepSeek API Key: {key_status}")
    print(f"[Config] Base URL: {DEEPSEEK_BASE_URL}")
    print(f"[Config] Model: {DEEPSEEK_MODEL}")
    print(f"[Config] FFmpeg: {FFMPEG_PATH}")
    print(f"[Config] Max Upload: {MAX_UPLOAD_MB} MB")
    
    if not key:
        print("[Config] ⚠️ 提示: 未检测到 API Key。请通过以下方式配置：")
        print("  1. 环境变量: set DEEPSEEK_API_KEY=sk-xxx")
        print("  2. .env 文件: 复制 .env.example 为 .env 并填入 Key")
        print("  3. 用户将使用自带 Key 模式（SaaS）")
