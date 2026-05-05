# video_analyzer.py - 视频逐帧分析 + 关键帧提取模块

import os
import cv2
import numpy as np
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from config import (
    FRAME_SAMPLE_INTERVAL,
    SCENE_CHANGE_THRESHOLD,
    TOP_FRAME_RATIO,
    KEYFRAME_DIR,
)

logger = logging.getLogger("VideoAnalyzer")


@dataclass
class FrameInfo:
    """单帧信息"""
    index: int              # 帧序号
    timestamp: float        # 时间戳（秒）
    score: float            # 重要性评分
    is_keyframe: bool       # 是否为关键帧
    scene_change: bool      # 是否为场景切换帧
    brightness: float       # 亮度均值
    blur_score: float       # 模糊度（越高越清晰）
    saved_path: Optional[str] = None  # 保存路径


@dataclass
class SceneSegment:
    """场景片段"""
    scene_id: int
    start_time: float
    end_time: float
    keyframe: FrameInfo
    frame_count: int
    avg_brightness: float
    description: str = ""

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class VideoAnalyzer:
    """
    视频分析器 Agent
    
    功能：
    1. 逐帧采样分析
    2. 场景切换检测
    3. 关键帧评分与提取
    4. 场景片段划分
    """

    def __init__(self, video_path: str):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"视频文件不存在: {video_path}")
        self.video_path = video_path
        self.cap = None
        self.frames: List[FrameInfo] = []
        self.scenes: List[SceneSegment] = []
        self.fps = 25.0
        self.total_frames = 0
        self.duration = 0.0
        logger.info(f"[VideoAnalyzer] 初始化，视频：{video_path}")

    def _open(self):
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            raise RuntimeError(f"无法打开视频文件: {self.video_path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps
        logger.info(
            f"  视频信息: {self.total_frames} 帧, {self.fps:.2f} fps, "
            f"时长 {self.duration:.2f}s"
        )

    def _close(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def _calc_blur_score(self, gray: np.ndarray) -> float:
        """Laplacian 方差法估计清晰度（越大越清晰）"""
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())

    def _calc_brightness(self, gray: np.ndarray) -> float:
        """计算帧亮度均值"""
        return float(np.mean(gray))

    def _calc_frame_diff(self, prev: np.ndarray, curr: np.ndarray) -> float:
        """计算两帧差异分数（MAE）"""
        diff = cv2.absdiff(prev, curr)
        return float(np.mean(diff))

    def analyze(self) -> List[FrameInfo]:
        """
        执行逐帧分析（主入口）
        返回所有采样帧的 FrameInfo 列表
        """
        self._open()
        try:
            return self._run_analysis()
        finally:
            self._close()

    def _run_analysis(self) -> List[FrameInfo]:
        logger.info("[VideoAnalyzer] 开始逐帧分析...")
        sample_step = max(1, int(self.fps * FRAME_SAMPLE_INTERVAL))
        prev_gray = None
        frame_idx = 0
        sampled_count = 0

        self.frames = []

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            if frame_idx % sample_step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                timestamp = frame_idx / self.fps

                # 场景变化检测
                scene_change = False
                diff_score = 0.0
                if prev_gray is not None:
                    diff_score = self._calc_frame_diff(prev_gray, gray)
                    scene_change = diff_score > SCENE_CHANGE_THRESHOLD

                blur = self._calc_blur_score(gray)
                brightness = self._calc_brightness(gray)

                # 综合评分（清晰度 + 场景变化权重 + 亮度适中加分）
                brightness_score = max(0, 1.0 - abs(brightness - 128) / 128)
                score = blur * 0.5 + (diff_score * 2 if scene_change else 0) + brightness_score * 20

                fi = FrameInfo(
                    index=frame_idx,
                    timestamp=timestamp,
                    score=score,
                    is_keyframe=False,
                    scene_change=scene_change,
                    brightness=brightness,
                    blur_score=blur,
                )
                self.frames.append(fi)
                prev_gray = gray
                sampled_count += 1

            frame_idx += 1

        logger.info(f"  采样完成，共 {sampled_count} 帧，开始筛选关键帧...")
        self._select_keyframes()
        self._segment_scenes()
        return self.frames

    def _select_keyframes(self):
        """按评分筛选关键帧（保留 TOP_FRAME_RATIO 比例）"""
        if not self.frames:
            return

        # 场景切换帧直接标记为关键帧
        for f in self.frames:
            if f.scene_change:
                f.is_keyframe = True

        # 对非场景切换帧按分数排序，取 TOP N
        non_scene = [f for f in self.frames if not f.scene_change]
        top_n = max(1, int(len(non_scene) * TOP_FRAME_RATIO))
        non_scene_sorted = sorted(non_scene, key=lambda x: x.score, reverse=True)
        for f in non_scene_sorted[:top_n]:
            f.is_keyframe = True

        kf_count = sum(1 for f in self.frames if f.is_keyframe)
        logger.info(f"  关键帧筛选完成：{kf_count} / {len(self.frames)} 帧被选为关键帧")

    def _segment_scenes(self):
        """基于场景切换帧划分场景片段"""
        self.scenes = []
        if not self.frames:
            return

        scene_id = 0
        scene_start = self.frames[0].timestamp
        scene_frames = []
        best_frame = self.frames[0]

        for fi in self.frames:
            if fi.scene_change and scene_frames:
                # 保存当前场景
                scene_end = fi.timestamp
                self.scenes.append(
                    SceneSegment(
                        scene_id=scene_id,
                        start_time=scene_start,
                        end_time=scene_end,
                        keyframe=best_frame,
                        frame_count=len(scene_frames),
                        avg_brightness=float(np.mean([f.brightness for f in scene_frames])),
                    )
                )
                scene_id += 1
                scene_start = fi.timestamp
                scene_frames = []
                best_frame = fi

            scene_frames.append(fi)
            if fi.score > best_frame.score:
                best_frame = fi

        # 最后一个场景
        if scene_frames:
            self.scenes.append(
                SceneSegment(
                    scene_id=scene_id,
                    start_time=scene_start,
                    end_time=self.duration,
                    keyframe=best_frame,
                    frame_count=len(scene_frames),
                    avg_brightness=float(np.mean([f.brightness for f in scene_frames])),
                )
            )

        logger.info(f"  场景划分完成：共 {len(self.scenes)} 个场景片段")

    def save_keyframes(self) -> List[str]:
        """
        将关键帧保存为图片
        返回保存路径列表
        """
        os.makedirs(KEYFRAME_DIR, exist_ok=True)
        saved_paths = []

        self._open()
        try:
            keyframes = [f for f in self.frames if f.is_keyframe]
            logger.info(f"[VideoAnalyzer] 保存 {len(keyframes)} 张关键帧...")

            for fi in keyframes:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, fi.index)
                ret, frame = self.cap.read()
                if ret:
                    path = os.path.join(
                        KEYFRAME_DIR,
                        f"keyframe_{fi.index:06d}_{fi.timestamp:.2f}s.jpg",
                    )
                    cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                    fi.saved_path = path
                    saved_paths.append(path)
        finally:
            self._close()

        logger.info(f"  关键帧已保存至 {KEYFRAME_DIR}/")
        return saved_paths

    def get_summary(self) -> dict:
        """返回分析摘要"""
        kf_count = sum(1 for f in self.frames if f.is_keyframe)
        return {
            "total_frames_sampled": len(self.frames),
            "keyframe_count": kf_count,
            "scene_count": len(self.scenes),
            "duration": self.duration,
            "scenes": [
                {
                    "id": s.scene_id,
                    "start": s.start_time,
                    "end": s.end_time,
                    "duration": s.duration,
                    "avg_brightness": s.avg_brightness,
                }
                for s in self.scenes
            ],
        }
