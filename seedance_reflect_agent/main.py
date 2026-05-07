#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — CLI 入口

用法示例:
  python main.py --intent "夕阳下的海浪拍打礁石，慢动作" --style 电影 --shot 全景
  python main.py --intent "赛博朋克城市夜景，霓虹灯闪烁" --style 赛博朋克 --shot 航拍
  python main.py --intent "一朵玫瑰花缓缓盛开" --draft --max-rounds 2
"""

import argparse
import sys
import json
from orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(
        description="Seedance Reflect+Retry 自优化 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
风格选项:
  写实 电影 赛博朋克 卡通 纪录片 商业 自然

景别选项:
  特写 近景 中景 全景 远景 航拍 跟随 推进 拉出 环绕

示例:
  python main.py --intent "雪山峰顶的日出延时摄影" --style 自然 --shot 航拍
  python main.py --intent "女孩在咖啡馆窗边看书" --style 电影 --shot 近景 --ratio 9:16
  python main.py --intent "机械臂在流水线上精准焊接" --style 商业 --shot 中景 --no-draft
        """,
    )

    parser.add_argument("--intent", required=True, help="视频内容意图（中文自然语言描述）")
    parser.add_argument("--style", default="写实",
                        choices=["写实", "电影", "赛博朋克", "卡通", "纪录片", "商业", "自然"],
                        help="视频风格（默认: 写实）")
    parser.add_argument("--shot", default="中景",
                        choices=["特写", "近景", "中景", "全景", "远景", "航拍", "跟随", "推进", "拉出", "环绕"],
                        help="镜头景别（默认: 中景）")
    parser.add_argument("--extras", default="", help="附加提示词（英文，可选）")
    parser.add_argument("--resolution", default="480p",
                        choices=["480p", "720p", "1080p"], help="视频分辨率（默认: 480p 样片）")
    parser.add_argument("--ratio", default="16:9", help="宽高比（默认: 16:9）")
    parser.add_argument("--duration", type=int, default=5, help="视频时长秒数（默认: 5）")
    parser.add_argument("--max-rounds", type=int, default=3, help="最大自优化轮次（默认: 3）")
    parser.add_argument("--no-draft", action="store_true", help="关闭样片模式，使用正式分辨率生成")
    parser.add_argument("--api-key", default=None, help="覆盖默认 API Key")
    parser.add_argument("--json-output", action="store_true", help="以 JSON 格式输出最终结果")

    args = parser.parse_args()

    use_draft = not args.no_draft

    orchestrator = Orchestrator(
        api_key=args.api_key or None,
        max_rounds=args.max_rounds,
        resolution=args.resolution,
        ratio=args.ratio,
        duration=args.duration,
        draft=use_draft,
        verbose=not args.json_output,
    )

    try:
        result = orchestrator.run(
            user_intent=args.intent,
            style=args.style,
            shot=args.shot,
            extras=args.extras,
        )
    except KeyboardInterrupt:
        print("\n\n⛔ 用户中断")
        return 1
    except Exception as e:
        print(f"\n❌ 运行出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

    if args.json_output:
        # 移除不可序列化字段
        safe_result = {k: v for k, v in result.items() if k != "history"}
        print(json.dumps(safe_result, ensure_ascii=False, indent=2, default=str))
    else:
        print("\n" + "═" * 60)
        print("  最终结果")
        print("═" * 60)
        print(f"  状态      : {'✅ 成功' if result['success'] else '⚠️ 最优结果（未达阈值）'}")
        print(f"  最优得分  : {result['best_score']:.4f}")
        print(f"  执行轮次  : {result['rounds']}")
        print(f"  视频文件  : {result['best_video_path'] or '（生成失败）'}")
        print(f"  最终提示词: {result['final_prompt'][:100]}...")
        print(f"  日志文件  : {result['log_path']}")
        print("═" * 60)

    return 0 if result["success"] else 2


if __name__ == "__main__":
    sys.exit(main())
