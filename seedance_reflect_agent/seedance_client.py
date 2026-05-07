#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
火山方舟 Seedance 1.5 Pro 视频生成 API 对接脚本
API Key : ark-c936524a-41fc-49a1-a9e2-8ca1e20e74da-cd379
模型 ID : doubbao-seedance-1-5-pro-251215
API 文档: https://www.volcengine.com/docs/82379/1520757
"""

import os
import sys
import time
import json
import argparse
import requests
from typing import Optional, List, Dict, Any


# ── 配置（已内置，可直接运行）──────────────────────
BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_API_KEY = "ark-c936524a-41fc-49a1-a9e2-8ca1e20e74da-cd379"
MODEL_ID = "doubao-seedance-1-5-pro-251215"  # 经测试，直接用模型 ID 可以成功调用
# ────────────────────────────────────────────────────


class SeedanceClient:
    """火山方舟 Seedance 1.5 Pro 视频生成客户端"""

    def __init__(self, api_key: str, model_id: str = MODEL_ID):
        self.api_key = api_key
        self.model_id = model_id
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        })

    # ─────────────────────────────────────────────
    # 1. 提交视频生成任务
    #    POST /api/v3/contents/generations/tasks
    # ─────────────────────────────────────────────

    def create_video(
        self,
        prompt: str,
        resolution: str = "1080p",
        ratio: str = "16:9",
        duration: int = 5,
        fps: int = 24,
        watermark: bool = False,
        seed: int = -1,
        camerafixed: bool = False,
        images: Optional[List[str]] = None,
        generate_audio: bool = False,
        draft: bool = False,
        draft_task_id: Optional[str] = None,
        service_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """提交视频生成任务（异步），返回 JSON 响应"""
        url = f"{BASE_URL}/contents/generations/tasks"

        # content: 至少包含一个 text 类型
        content = [{"type": "text", "text": prompt}]

        # 图生视频：追加 image_url 条目
        if images:
            for i, img_url in enumerate(images):
                item: Dict[str, Any] = {
                    "type": "image_url",
                    "image_url": {"url": img_url},
                }
                # 首尾帧：第一张 → first_frame，第二张 → last_frame
                if len(images) >= 2:
                    item["role"] = "first_frame" if i == 0 else "last_frame"
                content.append(item)

        # 组装请求体
        payload: Dict[str, Any] = {
            "model": self.model_id,
            "content": content,
        }

        # parameters: 生成参数
        params: Dict[str, Any] = {
            "resolution": "480p" if draft else resolution,
            "ratio": ratio,
            "durationSeconds": duration,
            "fps": fps,
        }
        if watermark:
            params["watermark"] = True
        if seed != -1:
            params["seed"] = seed
        if camerafixed:
            params["cameraFixed"] = True
        if generate_audio:
            params["generateAudio"] = True
        if draft:
            params["draft"] = True
        if draft_task_id:
            params["draftTaskId"] = draft_task_id
        if service_tier:
            params["serviceTier"] = service_tier

        payload["parameters"] = params

        print(f"\n[提交] POST {url}")
        print(f"       model : {self.model_id}")
        print(f"       prompt: {prompt[:60]}{'...' if len(prompt) > 60 else ''}")

        resp = self.session.post(url, json=payload, timeout=30)
        print(f"[响应] HTTP {resp.status_code}")
        try:
            data = resp.json()
            print(f"       正文: {json.dumps(data, ensure_ascii=False)[:400]}")
        except Exception:
            print(f"       正文: {resp.text[:400]}")
        resp.raise_for_status()
        return resp.json()

    # ─────────────────────────────────────────────
    # 2. 查询任务状态
    #    GET  /api/v3/contents/generations/tasks/{task_id}
    # ─────────────────────────────────────────────

    def get_video_task(self, task_id: str) -> Dict[str, Any]:
        """查询单个任务状态，返回 JSON 响应"""
        url = f"{BASE_URL}/contents/generations/tasks/{task_id}"
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def wait_for_video(
        self,
        task_id: str,
        poll_interval: int = 10,
        max_wait: int = 600,
    ) -> Dict[str, Any]:
        """
        轮询等待视频生成完成
        状态值（实测）: running → succeeded / failed
        """
        print(f"\n[等待] 任务 {task_id}，最长 {max_wait} 秒...\n")
        start = time.time()
        while True:
            if time.time() - start > max_wait:
                raise TimeoutError(f"任务 {task_id} 在 {max_wait} 秒内未完成")

            result = self.get_video_task(task_id)
            status = result.get("status", "UNKNOWN")
            elapsed = int(time.time() - start)
            progress = result.get("progress", "")
            print(f"  [{elapsed:4d}s] 状态: {status:12s} {progress}")

            if status == "succeeded":
                # 提取视频 URL（可能有多种位置）
                video_url = ""
                content_data = result.get("content")
                if isinstance(content_data, dict):
                    video_url = content_data.get("video_url", "")
                if not video_url:
                    videos = result.get("videos", [])
                    if videos and isinstance(videos, list):
                        v0 = videos[0] if videos else {}
                        video_url = v0.get("url", "") if isinstance(v0, dict) else ""
                print(f"  ✅ 完成！视频地址: {video_url[:100]}...")
                return result

            if status == "failed":
                reason = result.get("fail_reason", "未知原因")
                raise RuntimeError(f"视频生成失败: {reason}")

            time.sleep(poll_interval)

    # ─────────────────────────────────────────────
    # 3. 下载视频到本地
    # ─────────────────────────────────────────────

    def download_video(self, video_url: str, save_path: str) -> str:
        """下载视频到本地文件，返回本地路径"""
        print(f"\n[下载] {video_url[:80]}...")
        print(f"  → 保存到: {save_path}")
        resp = self.session.get(video_url, timeout=300, stream=True)
        resp.raise_for_status()

        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        downloaded = 0
        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        size_kb = downloaded // 1024
        print(f"  ✅ 下载完成: {size_kb} KB")
        return save_path

    # ─────────────────────────────────────────────
    # 4. 一站式：提交 → 等待 → 下载
    # ─────────────────────────────────────────────

    def generate_and_download(
        self,
        prompt: str,
        save_path: str,
        resolution: str = "1080p",
        ratio: str = "16:9",
        duration: int = 5,
        images: Optional[List[str]] = None,
        generate_audio: bool = False,
        **kwargs,
    ) -> str:
        """一站式完成：提交任务 → 等待完成 → 下载视频，返回本地路径"""
        print(f"\n{'=' * 60}")
        print(f"提示词 : {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"分辨率 : {resolution}")
        print(f"比例   : {ratio}")
        print(f"时长   : {duration}s")
        print(f"{'=' * 60}")

        # 1. 提交任务
        result = self.create_video(
            prompt=prompt,
            resolution=resolution,
            ratio=ratio,
            duration=duration,
            images=images,
            generate_audio=generate_audio,
            **kwargs,
        )
        # 提交响应格式: {"id": "cgt-..."}
        task_id = result.get("id") or result.get("task_id") or (result.get("data") or {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"提交失败，未返回 task_id: {json.dumps(result, ensure_ascii=False)[:300]}")
        print(f"\n[Task ID] {task_id}")

        # 2. 等待完成
        data = self.wait_for_video(task_id)

        # 3. 提取视频 URL
        video_url = ""
        content_data = data.get("content")
        if isinstance(content_data, dict):
            video_url = content_data.get("video_url", "")
        if not video_url:
            videos = data.get("videos", [])
            if videos and isinstance(videos, list):
                v0 = videos[0] if videos else {}
                video_url = v0.get("url", "") if isinstance(v0, dict) else ""
        if not video_url:
            raise RuntimeError("返回结果中没有 video_url，完整响应: " + json.dumps(data, ensure_ascii=False)[:500])

        # 4. 下载
        return self.download_video(video_url, save_path)


# ── CLI 入口 ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="火山方舟 Seedance 1.5 Pro 视频生成 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 文生视频（1080p，5秒）
  python seedance_client.py --prompt "一朵花在阳光下缓缓绽放" --output result.mp4

  # 图生视频（首帧）
  python seedance_client.py --prompt "女孩睁开眼" --image https://... --output result.mp4

  # 首尾帧视频（两张图片）
  python seedance_client.py --prompt "镜头环绕人物" --image url1 --image url2 --output result.mp4

  # 有声视频（Seedance 1.5 Pro 专属）
  python seedance_client.py --prompt "海浪拍打着礁石" --audio --output result.mp4

  # 样片模式（快速低清预览）
  python seedance_client.py --prompt "雪山延时摄影" --draft --output draft.mp4

环境变量:
  SEEDANCE_API_KEY   - API Key（ark- 或 sk- 开头，默认值已内置）
""",
    )

    parser.add_argument("--prompt", required=True, help="视频生成提示词")
    parser.add_argument("--output", required=True, help="输出视频文件路径")
    parser.add_argument("--api-key", default=DEFAULT_API_KEY, help="API Key（默认使用内置值）")
    parser.add_argument("--model", default=MODEL_ID, help="模型 ID（默认内置）")
    parser.add_argument("--resolution", default="1080p", choices=["480p", "720p", "1080p"], help="分辨率")
    parser.add_argument("--ratio", default="16:9", help="宽高比，如 16:9、9:16、1:1")
    parser.add_argument("--duration", type=int, default=5, help="视频时长（秒），范围 2~12")
    parser.add_argument("--image", action="append", dest="images", help="输入图片 URL（可多次指定）")
    parser.add_argument("--audio", action="store_true", help="生成带音频的视频（仅 1.5 Pro）")
    parser.add_argument("--watermark", action="store_true", help="添加水印")
    parser.add_argument("--camerafixed", action="store_true", help="固定镜头（减少运镜幅度）")
    parser.add_argument("--seed", type=int, default=-1, help="随机种子，-1 表示随机")
    parser.add_argument("--draft", action="store_true", help="样片模式（快速预览，仅 480p）")
    parser.add_argument("--flex", action="store_true", help="离线推理模式（成本低，耗时较长）")

    args = parser.parse_args()

    # 创建客户端
    client = SeedanceClient(api_key=args.api_key, model_id=args.model)

    # 生成并下载
    try:
        output_path = client.generate_and_download(
            prompt=args.prompt,
            save_path=args.output,
            resolution=args.resolution,
            ratio=args.ratio,
            duration=args.duration,
            images=args.images,
            generate_audio=args.audio,
            watermark=args.watermark,
            camerafixed=args.camerafixed,
            seed=args.seed,
            draft=args.draft,
            service_tier="flex" if args.flex else None,
        )
        print(f"\n🎉 全部完成！视频已保存到:\n  {output_path}")
        print(f"\n⚠️  视频 URL 有效期约 48 小时，已下载到本地无需担心过期")
        return 0
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
