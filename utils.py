# utils.py - 工具函数模块

import os
import shutil
import subprocess
import json
import logging
from pathlib import Path
from typing import Optional
from config import FFPROBE_PATH, OUTPUT_DIR, KEYFRAME_DIR, TEMP_DIR

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("utils")


def setup_directories():
    """初始化输出目录结构"""
    for d in [OUTPUT_DIR, KEYFRAME_DIR, TEMP_DIR]:
        os.makedirs(d, exist_ok=True)
    logger.info(f"目录初始化完成：{OUTPUT_DIR} / {KEYFRAME_DIR} / {TEMP_DIR}")


def cleanup_temp():
    """清理临时文件目录"""
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
        os.makedirs(TEMP_DIR, exist_ok=True)
    logger.info("临时目录已清理")


def get_video_info(video_path: str) -> dict:
    """
    使用 ffprobe 获取视频元信息
    返回: {duration, width, height, fps, nb_frames, size_mb}
    """
    cmd = [
        FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)

        video_stream = next(
            (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
            None,
        )
        if not video_stream:
            raise ValueError(f"未找到视频流：{video_path}")

        # 解析帧率（可能是 "30/1" 或 "30000/1001" 格式）
        fps_str = video_stream.get("r_frame_rate", "25/1")
        num, den = map(int, fps_str.split("/"))
        fps = num / den if den else 25.0

        duration = float(info.get("format", {}).get("duration", 0))
        size_bytes = int(info.get("format", {}).get("size", 0))

        return {
            "duration": duration,
            "width": int(video_stream.get("width", 0)),
            "height": int(video_stream.get("height", 0)),
            "fps": fps,
            "nb_frames": int(video_stream.get("nb_frames", 0)) or int(duration * fps),
            "size_mb": round(size_bytes / (1024 * 1024), 2),
            "codec": video_stream.get("codec_name", "unknown"),
            "has_audio": any(
                s.get("codec_type") == "audio" for s in info.get("streams", [])
            ),
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe 执行失败: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"视频信息获取失败: {e}")
        raise


def format_time(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS.mmm"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def seconds_to_timestamp(seconds: float) -> str:
    """将秒转为 ffmpeg 可用的时间戳字符串"""
    return format_time(seconds)


def check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def check_dependencies() -> dict:
    """检查所有依赖是否就绪"""
    deps = {}
    try:
        import cv2
        deps["opencv"] = cv2.__version__
    except ImportError:
        deps["opencv"] = None

    try:
        import numpy
        deps["numpy"] = numpy.__version__
    except ImportError:
        deps["numpy"] = None

    deps["ffmpeg"] = check_ffmpeg()
    return deps
