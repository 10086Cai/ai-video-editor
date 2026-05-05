# AI 视频智能剪辑 Agent

> 基于创意二构建：AI 驱动的视频内容理解 + 自动剪辑

## 项目简介

### 核心痛点

原始视频素材中有效内容往往分散，大量片段存在画面模糊、亮度异常、重复内容等问题，传统人工筛选需要逐帧查看，费时费力。本项目通过 AI Agent 实现全自动的视频内容理解与智能剪辑。

### 核心逻辑流

```
输入视频
   │
   ▼
[VideoAnalyzer Agent] ──── 工具：OpenCV 逐帧采样
   │  · 每 2 秒采一帧分析
   │  · 场景切换检测（帧差分算法）
   │  · 关键帧评分（清晰度 + 亮度 + 场景权重）
   │
   ▼
[ClipPlanner Agent] ──── 长链推理（7 步 CoT）
   │  Step 1: 确定目标时长
   │  Step 2: 场景质量过滤（剔除过暗/过亮/极短）
   │  Step 3: 时长规范化（裁剪超长/补齐过短）
   │  Step 4: 优先级评分排序
   │  Step 5: 贪心时长对齐
   │  Step 6: 转场效果分配
   │  Step 7: 最终合法性校验
   │
   ▼
[FFmpegExecutor Agent] ──── 工具：FFmpeg CLI
   │  · 按方案逐片裁剪
   │  · 淡入淡出转场处理
   │  · concat demuxer 合并
   │
   ▼
输出精剪视频 (output/)
```

**架构**：单 Agent 多工具调用模式，每次处理可节省约 30 分钟人工操作。

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 安装 FFmpeg

- **Windows**: 从 https://ffmpeg.org/download.html 下载，解压后将 `bin/` 加入 PATH
- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

### 3. 运行

```bash
# 基本剪辑（自动保留约 50% 内容）
python main.py input.mp4

# 指定目标时长 60 秒
python main.py input.mp4 --target-duration 60

# 剪辑 + 保存关键帧
python main.py input.mp4 --save-keyframes

# 只提取音频
python main.py input.mp4 --audio-only

# 只提取最后一帧
python main.py input.mp4 --last-frame

# 输出分析报告
python main.py input.mp4 --report
```

---

## 参数说明

| 参数 | 缩写 | 说明 |
|------|------|------|
| `input` | - | 输入视频路径（必填） |
| `--output` | `-o` | 输出文件名（默认自动生成） |
| `--target-duration` | `-t` | 目标时长（秒），0 = 自动 |
| `--save-keyframes` | `-k` | 保存关键帧图片到 keyframes/ |
| `--audio-only` | `-a` | 只提取音频（MP3） |
| `--last-frame` | `-l` | 只提取最后一帧（JPEG） |
| `--no-cleanup` | - | 保留临时文件（调试用） |
| `--report` | `-r` | 输出 JSON 分析报告 |

---

## 目录结构

```
ai_video_editor/
├── main.py              # 主入口 / Agent 控制器
├── video_analyzer.py    # VideoAnalyzer Agent（帧分析 + 关键帧提取）
├── clip_planner.py      # ClipPlanner Agent（长链推理规划）
├── ffmpeg_executor.py   # FFmpegExecutor Agent（FFmpeg 合成）
├── config.py            # 全局配置
├── utils.py             # 工具函数
├── requirements.txt     # Python 依赖
├── README.md            # 本文档
├── output/              # 输出视频 / 音频 / 图片
├── keyframes/           # 关键帧截图（--save-keyframes 时生成）
└── temp/                # 临时片段（执行完成后自动清理）
```

---

## 配置调优（config.py）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `FRAME_SAMPLE_INTERVAL` | 2.0 | 采样间隔（秒），越小越精细但越慢 |
| `SCENE_CHANGE_THRESHOLD` | 30.0 | 场景切换阈值，越低越敏感 |
| `MIN_CLIP_DURATION` | 3.0 | 最小片段时长（秒） |
| `MAX_CLIP_DURATION` | 30.0 | 最大片段时长（秒） |
| `TOP_FRAME_RATIO` | 0.3 | 关键帧保留比例 |
| `TARGET_DURATION` | 0 | 目标时长（0=自动） |
| `OUTPUT_CRF` | 23 | 输出质量（18~28，越小越好） |

---

## 技术栈

- **Python 3.8+**
- **OpenCV** — 视频帧读取与图像分析
- **NumPy** — 帧差分计算与统计
- **FFmpeg** — 视频裁剪、合并、转码

---

## License

MIT
