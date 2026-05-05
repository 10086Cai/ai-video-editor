# main.py - AI 视频智能剪辑 Agent 主入口

"""
AI 视频智能剪辑 Agent
=====================
创意二：AI 驱动的视频内容理解 + 自动剪辑

核心痛点：原始素材中有效内容分散，人工筛选费时费力。

核心逻辑流：
  Agent 逐帧分析 → 关键帧提取 → 多模态质量识别 →
  长链推理规划最优剪辑方案 → 自动 FFmpeg 合成输出

架构：单 Agent + 多工具调用（VideoAnalyzer / ClipPlanner / FFmpegExecutor）
"""

import os
import sys
import argparse
import logging
import json
import time
from datetime import datetime

from utils import setup_directories, cleanup_temp, get_video_info, check_dependencies
from video_analyzer import VideoAnalyzer
from clip_planner import ClipPlanner
from ffmpeg_executor import FFmpegExecutor

# ===== 日志配置 =====
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Main")


def parse_args():
    parser = argparse.ArgumentParser(
        description="AI 视频智能剪辑 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 基本用法
  python main.py input.mp4

  # 指定输出文件名
  python main.py input.mp4 --output my_edit.mp4

  # 指定目标时长（秒）
  python main.py input.mp4 --target-duration 60

  # 保存关键帧图片
  python main.py input.mp4 --save-keyframes

  # 只提取音频
  python main.py input.mp4 --audio-only

  # 只提取最后一帧
  python main.py input.mp4 --last-frame
        """,
    )
    parser.add_argument("input", help="输入视频文件路径")
    parser.add_argument("--output", "-o", default="", help="输出文件名（默认自动生成）")
    parser.add_argument(
        "--target-duration", "-t", type=float, default=0,
        help="目标视频时长（秒），0 表示自动（原时长 50%%）"
    )
    parser.add_argument(
        "--save-keyframes", "-k", action="store_true",
        help="是否保存关键帧图片"
    )
    parser.add_argument(
        "--audio-only", "-a", action="store_true",
        help="只提取音频，不做视频剪辑"
    )
    parser.add_argument(
        "--last-frame", "-l", action="store_true",
        help="只提取视频最后一帧"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true",
        help="保留临时文件（调试用）"
    )
    parser.add_argument(
        "--report", "-r", action="store_true",
        help="输出 JSON 格式的分析报告"
    )
    return parser.parse_args()


def check_env():
    """环境依赖检查"""
    logger.info("正在检查依赖环境...")
    deps = check_dependencies()
    all_ok = True

    for name, version in deps.items():
        if version:
            logger.info(f"  ✓ {name}: {version}")
        else:
            logger.error(f"  ✗ {name}: 未安装")
            all_ok = False

    if not all_ok:
        logger.error("依赖缺失，请运行：pip install -r requirements.txt")
        logger.error("并确保 ffmpeg 已安装并在 PATH 中")
        sys.exit(1)

    logger.info("依赖检查通过 ✓")


def run_agent(args) -> dict:
    """
    Agent 主流程
    
    返回执行结果 dict
    """
    result = {
        "input": args.input,
        "start_time": datetime.now().isoformat(),
        "status": "running",
        "outputs": [],
        "analysis": {},
        "plan": {},
    }

    t_start = time.time()

    # ── 0. 环境初始化 ──────────────────────────────────────
    setup_directories()
    logger.info(f"\n{'='*60}")
    logger.info(f"🎬 AI 视频智能剪辑 Agent 启动")
    logger.info(f"   输入: {args.input}")
    logger.info(f"{'='*60}\n")

    # 获取视频基础信息
    logger.info("📊 读取视频信息...")
    video_info = get_video_info(args.input)
    logger.info(
        f"  时长: {video_info['duration']:.2f}s | "
        f"分辨率: {video_info['width']}x{video_info['height']} | "
        f"FPS: {video_info['fps']:.2f} | "
        f"大小: {video_info['size_mb']} MB"
    )
    result["analysis"]["video_info"] = video_info

    executor = FFmpegExecutor(
        source_video=args.input,
        output_name=args.output or f"edited_{os.path.splitext(os.path.basename(args.input))[0]}.mp4",
    )

    # ── 特殊模式：只提取音频 ──────────────────────────────
    if args.audio_only:
        logger.info("\n🎵 音频提取模式...")
        audio_path = executor.extract_audio()
        if audio_path:
            result["outputs"].append(audio_path)
            result["status"] = "success"
            logger.info(f"✅ 音频提取完成：{audio_path}")
        else:
            result["status"] = "failed"
        return result

    # ── 特殊模式：只提取最后一帧 ──────────────────────────
    if args.last_frame:
        logger.info("\n🖼  最后一帧提取模式...")
        frame_path = executor.extract_last_frame()
        if frame_path:
            result["outputs"].append(frame_path)
            result["status"] = "success"
            logger.info(f"✅ 最后一帧提取完成：{frame_path}")
        else:
            result["status"] = "failed"
        return result

    # ── 1. 视频分析 Agent ─────────────────────────────────
    logger.info("\n🔍 Step 1/3: 视频逐帧分析中...")
    analyzer = VideoAnalyzer(args.input)
    frames = analyzer.analyze()

    if not frames:
        logger.error("视频分析失败：未提取到任何帧")
        result["status"] = "failed"
        return result

    summary = analyzer.get_summary()
    result["analysis"]["frame_summary"] = summary
    logger.info(
        f"  分析完成：{summary['total_frames_sampled']} 帧采样，"
        f"{summary['keyframe_count']} 个关键帧，"
        f"{summary['scene_count']} 个场景"
    )

    # 可选：保存关键帧图片
    if args.save_keyframes:
        saved = analyzer.save_keyframes()
        result["outputs"].extend(saved)
        logger.info(f"  关键帧已保存：{len(saved)} 张")

    # ── 2. 剪辑规划 Agent（长链推理）────────────────────────
    logger.info("\n🧠 Step 2/3: 长链推理规划剪辑方案...")

    # 覆盖目标时长配置
    if args.target_duration > 0:
        import config
        config.TARGET_DURATION = args.target_duration
        logger.info(f"  目标时长设定为 {args.target_duration}s")

    planner = ClipPlanner(
        scenes=analyzer.scenes,
        video_duration=video_info["duration"],
    )
    plan = planner.plan_edit()
    planner.print_plan()

    result["plan"] = {
        "clip_count": len(plan.clips),
        "total_duration": plan.total_duration,
        "reasoning_steps": len(plan.reasoning_log),
    }

    if not plan.clips:
        logger.error("剪辑规划失败：没有生成任何片段")
        result["status"] = "failed"
        return result

    # ── 3. FFmpeg 合成执行 ────────────────────────────────
    logger.info("\n🎞  Step 3/3: FFmpeg 合成执行中...")
    output_path = executor.execute(plan.clips)

    if output_path:
        result["outputs"].append(output_path)
        result["status"] = "success"
    else:
        result["status"] = "failed"

    # ── 清理临时文件 ──────────────────────────────────────
    if not args.no_cleanup:
        cleanup_temp()

    t_elapsed = time.time() - t_start
    result["elapsed_seconds"] = round(t_elapsed, 2)
    result["end_time"] = datetime.now().isoformat()

    return result


def print_result(result: dict):
    """打印执行结果摘要"""
    status_icon = "✅" if result["status"] == "success" else "❌"
    print(f"\n{'='*60}")
    print(f"{status_icon} 执行结果: {result['status'].upper()}")
    print(f"{'='*60}")
    print(f"  耗时: {result.get('elapsed_seconds', 0):.2f}s")
    if result["outputs"]:
        print(f"  输出文件 ({len(result['outputs'])} 个):")
        for p in result["outputs"]:
            size = os.path.getsize(p) / (1024 * 1024) if os.path.exists(p) else 0
            print(f"    → {p}  ({size:.2f} MB)")
    plan = result.get("plan", {})
    if plan:
        print(f"  剪辑片段: {plan.get('clip_count', 0)} 个")
        print(f"  输出时长: {plan.get('total_duration', 0):.2f}s")
        print(f"  推理步数: {plan.get('reasoning_steps', 0)} 步")
    print(f"{'='*60}\n")


def main():
    args = parse_args()

    # 输入文件检查
    if not os.path.exists(args.input):
        logger.error(f"输入文件不存在：{args.input}")
        sys.exit(1)

    # 环境检查
    check_env()

    # 运行 Agent
    try:
        result = run_agent(args)
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Agent 运行异常: {e}")
        sys.exit(1)

    # 打印结果
    print_result(result)

    # 可选：输出 JSON 报告
    if args.report:
        report_path = "edit_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"分析报告已保存：{report_path}")

    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
