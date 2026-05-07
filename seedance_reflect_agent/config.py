#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全局配置 — Seedance Reflect+Retry Agent
"""

# ── Seedance API ─────────────────────────────────────────────────────
SEEDANCE_API_KEY = "ark-c936524a-41fc-49a1-a9e2-8ca1e20e74da-cd379"
SEEDANCE_MODEL_ID = "doubao-seedance-1-5-pro-251215"
SEEDANCE_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

# ── 生成参数默认值 ────────────────────────────────────────────────────
DEFAULT_RESOLUTION = "480p"   # 默认样片模式，节省配额；正式生成换 "1080p"
DEFAULT_RATIO = "16:9"
DEFAULT_DURATION = 5          # 秒
DEFAULT_FPS = 24
DEFAULT_DRAFT = True          # True = 样片模式（快速预览）

# ── Reflect+Retry 控制 ────────────────────────────────────────────────
MAX_RETRY_ROUNDS = 3          # 最多自我反思优化轮次
MIN_SCORE_THRESHOLD = 0.75    # 得分 >= 此值则接受，不再重试
EVAL_WEIGHTS = {              # 各维度评估权重
    "prompt_alignment": 0.40,
    "visual_quality": 0.25,
    "motion_smoothness": 0.20,
    "composition": 0.15,
}

# ── 输出目录 ──────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
LOG_DIR = "logs"
