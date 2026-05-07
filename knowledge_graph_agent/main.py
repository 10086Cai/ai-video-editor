#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py — 个人知识图谱 Agent CLI 入口

用法:
  # 从文件构建图谱
  python main.py build README.md

  # 从目录构建图谱
  python main.py build ./my_project/

  # 交互式查询
  python main.py query

  # 单次查询
  python main.py ask "有哪些技术"
  python main.py ask "Python和什么有关"
  python main.py ask "统计"

  # 一站式：构建 + 查询
  python main.py run ./src/ --ask "最热门的技术是什么"
"""

import argparse
import sys
from orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser(
        description="个人知识图谱 Agent — 从文档自动构建知识图谱并支持自然语言查询",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
查询示例:
  python main.py build ./my_code/
  python main.py query
  python main.py ask "有哪些技术"
  python main.py ask "Python和什么有关"
  python main.py ask "GraphBuilder和QueryAgent的关系"
  python main.py ask "统计"
  python main.py run ./src/ --ask "最热门的技术"
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="命令")

    # build
    build_p = subparsers.add_parser("build", help="从文件/目录构建知识图谱")
    build_p.add_argument("source", help="文件路径或目录路径")
    build_p.add_argument("--output", default=None, help="图谱保存路径")

    # query
    query_p = subparsers.add_parser("query", help="交互式查询模式")
    query_p.add_argument("--graph", default=None, help="图谱文件路径")

    # ask
    ask_p = subparsers.add_parser("ask", help="单次查询")
    ask_p.add_argument("question", help="自然语言问题")
    ask_p.add_argument("--graph", default=None, help="图谱文件路径")

    # run (build + ask)
    run_p = subparsers.add_parser("run", help="构建 + 查询")
    run_p.add_argument("source", help="文件路径或目录路径")
    run_p.add_argument("--ask", required=True, help="构建后立即查询的问题")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    orch = Orchestrator(verbose=True)

    if args.command == "build":
        result = orch.build_from_source(args.source, store_path=args.output)
        print(f"\n{'='*60}")
        print(f"  构建完成")
        print(f"  节点: {result['stats']['node_count']}")
        print(f"  关系: {result['stats']['edge_count']}")
        print(f"  图谱: {result['store_path']}")
        print(f"  DOT:  {result['dot_path']}")
        print(f"{'='*60}")
        return 0

    elif args.command == "query":
        orch.query_interactive(store_path=args.graph)
        return 0

    elif args.command == "ask":
        result = orch.query(args.question, store_path=args.graph)
        print(f"\n{result['answer']}")
        return 0

    elif args.command == "run":
        orch.build_from_source(args.source)
        print()
        result = orch.query(args.ask)
        print(f"\n{result['answer']}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
