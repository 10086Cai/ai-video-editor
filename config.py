# config.py - 全局配置文件

import os

# ===== FFmpeg 配置 =====
# 如果 ffmpeg 已在 PATH 中，直接填 "ffmpeg"；否则填绝对路径
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.environ.get("FFPROBE_PATH", "ffprobe")

# ===== 帧分析配置 =====
# 关键帧采样间隔（秒）：每隔多少秒采一帧进行分析
FRAME_SAMPLE_INTERVAL = 2.0

# 关键帧判断阈值：帧差异分数超过此值则视为场景切换
SCENE_CHANGE_THRESHOLD = 30.0

# 最小片段时长（秒）：低于此时长的片段会被合并
MIN_CLIP_DURATION = 3.0

# 最大片段时长（秒）：超过此时长的片段会被分割
MAX_CLIP_DURATION = 30.0

# ===== 输出配置 =====
OUTPUT_DIR = "output"
KEYFRAME_DIR = "keyframes"
TEMP_DIR = "temp"

# 输出视频编码参数
OUTPUT_VIDEO_CODEC = "libx264"
OUTPUT_AUDIO_CODEC = "aac"
OUTPUT_CRF = 23          # 视频质量：0(无损) ~ 51(最差)，推荐 18~28
OUTPUT_PRESET = "fast"   # 编码速度：ultrafast/fast/medium/slow

# ===== Agent 推理配置 =====
# 最大推理轮次（防止死循环）
MAX_REASONING_STEPS = 10

# 关键帧保留比例：从所有采样帧中保留最有价值的比例
TOP_FRAME_RATIO = 0.3

# 最终视频目标时长（秒），0 表示不限制
TARGET_DURATION = 0
