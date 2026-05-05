# ffmpeg_executor.py - FFmpeg 合成执行模块

import os
import subprocess
import logging
from typing import List, Optional
from config import (
    FFMPEG_PATH,
    OUTPUT_DIR,
    TEMP_DIR,
    OUTPUT_VIDEO_CODEC,
    OUTPUT_AUDIO_CODEC,
    OUTPUT_CRF,
    OUTPUT_PRESET,
)
from clip_planner import ClipSegment

logger = logging.getLogger("FFmpegExecutor")


class FFmpegExecutor:
    """
    FFmpeg 执行层 Agent
    
    功能：
    1. 按剪辑方案裁剪片段
    2. 拼接所有片段
    3. 应用转场效果
    4. 输出最终视频
    """

    def __init__(self, source_video: str, output_name: str = "output_edited.mp4"):
        self.source_video = source_video
        self.output_path = os.path.join(OUTPUT_DIR, output_name)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
        logger.info(f"[FFmpegExecutor] 初始化，输出：{self.output_path}")

    def _run(self, cmd: List[str], step_name: str = "") -> bool:
        """执行 FFmpeg 命令，返回是否成功"""
        logger.info(f"  执行: {' '.join(cmd[:6])}...")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                logger.error(f"  FFmpeg 失败 ({step_name}):\n{result.stderr[-500:]}")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.error(f"  FFmpeg 超时 ({step_name})")
            return False
        except Exception as e:
            logger.error(f"  FFmpeg 异常 ({step_name}): {e}")
            return False

    def cut_clip(self, clip: ClipSegment) -> Optional[str]:
        """
        裁剪单个片段，返回临时文件路径
        使用 -ss 精确起始 + -t 时长
        """
        out_path = os.path.join(TEMP_DIR, f"clip_{clip.clip_id:03d}.mp4")
        duration = clip.end_time - clip.start_time

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-ss", str(clip.start_time),
            "-i", self.source_video,
            "-t", str(duration),
            "-c:v", OUTPUT_VIDEO_CODEC,
            "-crf", str(OUTPUT_CRF),
            "-preset", OUTPUT_PRESET,
            "-c:a", OUTPUT_AUDIO_CODEC,
            "-avoid_negative_ts", "make_zero",
            out_path,
        ]
        if self._run(cmd, f"cut_clip_{clip.clip_id}"):
            logger.info(
                f"  ✓ 片段{clip.clip_id} 裁剪完成: "
                f"[{clip.start_time:.2f}s~{clip.end_time:.2f}s] → {out_path}"
            )
            return out_path
        return None

    def concat_clips(self, clip_paths: List[str]) -> bool:
        """
        使用 concat demuxer 拼接所有片段
        生成拼接列表文件，然后调用 FFmpeg 合并
        """
        if not clip_paths:
            logger.error("没有片段可以拼接")
            return False

        # 生成 concat 列表文件
        list_path = os.path.join(TEMP_DIR, "concat_list.txt")
        with open(list_path, "w", encoding="utf-8") as f:
            for p in clip_paths:
                # Windows 路径需要转正斜杠
                safe_path = p.replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        logger.info(f"  拼接列表：{len(clip_paths)} 个片段 → {self.output_path}")

        cmd = [
            FFMPEG_PATH,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            self.output_path,
        ]
        return self._run(cmd, "concat")

    def add_fade_transitions(self, clip_paths: List[str], clips: List[ClipSegment]) -> List[str]:
        """
        为需要淡入淡出的片段添加转场效果
        返回处理后的路径列表（未修改的直接原路返回）
        """
        processed = []
        fade_duration = 0.5  # 淡入/淡出时长（秒）

        for i, (path, clip) in enumerate(zip(clip_paths, clips)):
            if clip.transition == "fade" and i > 0:
                out_path = os.path.join(TEMP_DIR, f"clip_{clip.clip_id:03d}_fade.mp4")
                dur = clip.duration

                # 添加视频淡入（开头 0.5s）
                vf = f"fade=t=in:st=0:d={fade_duration}"
                # 如果有足够时长，也加淡出
                if dur > fade_duration * 2:
                    vf += f",fade=t=out:st={dur - fade_duration:.3f}:d={fade_duration}"

                cmd = [
                    FFMPEG_PATH,
                    "-y",
                    "-i", path,
                    "-vf", vf,
                    "-c:v", OUTPUT_VIDEO_CODEC,
                    "-crf", str(OUTPUT_CRF),
                    "-preset", OUTPUT_PRESET,
                    "-c:a", OUTPUT_AUDIO_CODEC,
                    out_path,
                ]
                if self._run(cmd, f"fade_{clip.clip_id}"):
                    processed.append(out_path)
                    logger.info(f"  ✓ 片段{clip.clip_id} 淡入淡出处理完成")
                    continue

            processed.append(path)

        return processed

    def execute(self, clips: List[ClipSegment]) -> Optional[str]:
        """
        主执行入口：按顺序裁剪 → 转场 → 拼接
        返回输出文件路径（失败返回 None）
        """
        if not clips:
            logger.error("[FFmpegExecutor] 没有片段，终止执行")
            return None

        logger.info(f"[FFmpegExecutor] 开始执行，共 {len(clips)} 个片段...")

        # 1. 逐片裁剪
        clip_paths = []
        for clip in clips:
            path = self.cut_clip(clip)
            if path:
                clip_paths.append(path)
            else:
                logger.warning(f"  ⚠ 片段{clip.clip_id} 裁剪失败，跳过")

        if not clip_paths:
            logger.error("  所有片段裁剪失败")
            return None

        logger.info(f"  裁剪完成：{len(clip_paths)} / {len(clips)} 个片段成功")

        # 2. 转场处理
        valid_clips = [c for c in clips if
                       os.path.join(TEMP_DIR, f"clip_{c.clip_id:03d}.mp4")
                       in clip_paths or
                       os.path.join(TEMP_DIR, f"clip_{c.clip_id:03d}.mp4").replace("\\", "/")
                       in [p.replace("\\", "/") for p in clip_paths]]
        processed_paths = self.add_fade_transitions(clip_paths, valid_clips)

        # 3. 拼接
        if len(processed_paths) == 1:
            # 只有一个片段，直接复制
            import shutil
            shutil.copy2(processed_paths[0], self.output_path)
            logger.info(f"  单片段，直接输出：{self.output_path}")
        else:
            success = self.concat_clips(processed_paths)
            if not success:
                logger.error("  拼接失败")
                return None

        if os.path.exists(self.output_path):
            size_mb = os.path.getsize(self.output_path) / (1024 * 1024)
            logger.info(
                f"[FFmpegExecutor] ✅ 输出成功：{self.output_path} "
                f"({size_mb:.2f} MB)"
            )
            return self.output_path

        logger.error("[FFmpegExecutor] 输出文件未生成")
        return None

    def extract_audio(self, output_name: str = "audio.mp3") -> Optional[str]:
        """单独提取音频"""
        out_path = os.path.join(OUTPUT_DIR, output_name)
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", self.source_video,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            out_path,
        ]
        if self._run(cmd, "extract_audio"):
            logger.info(f"  音频提取完成：{out_path}")
            return out_path
        return None

    def extract_last_frame(self, output_name: str = "last_frame.jpg") -> Optional[str]:
        """提取视频最后一帧"""
        out_path = os.path.join(OUTPUT_DIR, output_name)
        cmd = [
            FFMPEG_PATH,
            "-y",
            "-sseof", "-3",
            "-i", self.source_video,
            "-update", "1",
            "-q:v", "1",
            out_path,
        ]
        if self._run(cmd, "extract_last_frame"):
            logger.info(f"  最后一帧提取完成：{out_path}")
            return out_path
        return None
