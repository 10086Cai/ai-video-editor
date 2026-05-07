#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orchestrator — 主控 Agent，协调整个知识图谱构建流程

完整流程:
  ┌──────────────────────────────────────────────────────┐
  │  输入: 文件/目录路径                                   │
  │      │                                               │
  │  DocumentParser.parse()  ── 多格式文档解析            │
  │      │                                               │
  │  EntityExtractor.extract()  ── 多策略实体抽取         │
  │  (Strategy 1~4: 关键词/正则/词频/代码感知)            │
  │      │                                               │
  │  RelationBuilder.build_relations()  ── 多层级关系推断 │
  │  (Level 1~3: 共现/模式匹配/结构推断)                  │
  │      │                                               │
  │  GraphBuilder.build()  ── 图构建 + 统计              │
  │      │                                               │
  │  导出: JSON / DOT / Mermaid                           │
  │      │                                               │
  │  QueryAgent.query()  ── 自然语言查询                  │
  └──────────────────────────────────────────────────────┘
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from document_parser import DocumentParser
from entity_extractor import EntityExtractor
from relation_builder import RelationBuilder
from graph_builder import GraphBuilder
from query_agent import QueryAgent
from config import GRAPH_STORE_FILE, OUTPUT_DIR


class Orchestrator:
    """知识图谱构建主控 Agent"""

    def __init__(self, verbose: bool = True):
        self.parser = DocumentParser()
        self.extractor = EntityExtractor()
        self.relation_builder = RelationBuilder()
        self.graph = GraphBuilder()
        self.verbose = verbose

        os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 主入口: 从文件/目录构建 ────────────────────────────────────────

    def build_from_source(
        self,
        source_path: str,
        store_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        从文件或目录构建知识图谱。

        Args:
            source_path: 文件路径或目录路径
            store_path: 图谱保存路径（可选）

        Returns:
            构建结果摘要
        """
        store_path = store_path or os.path.join(OUTPUT_DIR, GRAPH_STORE_FILE)
        self._log(f"\n{'='*60}")
        self._log(f"  个人知识图谱 Agent  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        self._log(f"{'='*60}")
        self._log(f"  输入源: {source_path}")

        # ── Step 1: 文档解析 ─────────────────────────────────────────
        self._log(f"\n[Step 1] 文档解析...")
        if os.path.isdir(source_path):
            parsed_docs = self.parser.parse_directory(source_path)
        elif os.path.isfile(source_path):
            parsed_docs = [self.parser.parse(source_path)]
        else:
            raise FileNotFoundError(f"路径不存在: {source_path}")

        self._log(f"  解析完成: {len(parsed_docs)} 个文件")

        total_sections = sum(len(d["sections"]) for d in parsed_docs)
        total_chars = sum(d["metadata"].get("char_count", 0) for d in parsed_docs)
        self._log(f"  总 section 数: {total_sections}")
        self._log(f"  总字符数: {total_chars}")

        # ── Step 2: 实体抽取 ─────────────────────────────────────────
        self._log(f"\n[Step 2] 实体抽取...")
        all_entities: List[Dict[str, Any]] = []
        for doc in parsed_docs:
            result = self.extractor.extract(doc)
            all_entities.extend(result["entities"])
            self._log(f"  {os.path.basename(doc['source'])}: {result['entity_count']} 个实体")

        self._log(f"  抽取完成: {len(all_entities)} 个实体（去重前）")

        # ── Step 3: 关系推断 ─────────────────────────────────────────
        self._log(f"\n[Step 3] 关系推断...")
        all_relations: List[Dict[str, Any]] = []
        for doc in parsed_docs:
            # 为每个文档单独建立关系
            doc_entities = [e for e in all_entities if e.get("source") == doc["source"]]
            if doc_entities:
                rel_result = self.relation_builder.build_relations(doc_entities, doc)
                all_relations.extend(rel_result["relations"])

        # 跨文档合并
        all_relations = self.relation_builder.merge_relations(all_relations)
        self._log(f"  推断完成: {len(all_relations)} 条关系（合并后）")

        # ── Step 4: 图构建 ───────────────────────────────────────────
        self._log(f"\n[Step 4] 知识图谱构建...")
        self.graph = GraphBuilder(store_path=store_path)
        stats = self.graph.build(all_entities, all_relations)

        # 保存
        saved_path = self.graph.save(store_path)
        self._log(f"  节点: {stats['node_count']}, 边: {stats['edge_count']}")
        self._log(f"  连通分量: {stats['connected_components']}")
        self._log(f"  已保存: {saved_path}")

        # ── Step 5: 导出 ─────────────────────────────────────────────
        dot_path = os.path.join(OUTPUT_DIR, "knowledge_graph.dot")
        self.graph.export_dot(dot_path)
        self._log(f"  DOT 导出: {dot_path}")

        mermaid = self.graph.export_mermaid()
        mermaid_path = os.path.join(OUTPUT_DIR, "knowledge_graph.mmd")
        with open(mermaid_path, "w", encoding="utf-8") as f:
            f.write(mermaid)
        self._log(f"  Mermaid 导出: {mermaid_path}")

        # 保存完整日志
        log_path = os.path.join(OUTPUT_DIR, "build_log.json")
        log_data = {
            "source": source_path,
            "docs_parsed": len(parsed_docs),
            "entities_found": len(all_entities),
            "relations_found": len(all_relations),
            "stats": stats,
            "timestamp": datetime.now().isoformat(),
        }
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "stats": stats,
            "store_path": saved_path,
            "dot_path": dot_path,
            "mermaid_path": mermaid_path,
            "log_path": log_path,
            "entities": all_entities,
            "relations": all_relations,
        }

    # ── 交互式查询 ────────────────────────────────────────────────────

    def query_interactive(self, store_path: Optional[str] = None) -> None:
        """启动交互式查询模式"""
        store_path = store_path or os.path.join(OUTPUT_DIR, GRAPH_STORE_FILE)

        if not self.graph.load(store_path):
            print(f"图谱文件不存在: {store_path}")
            print("请先使用 build_from_source() 构建图谱。")
            return

        qa = QueryAgent(self.graph.nodes, self.graph.edges)
        print(f"\n{'='*60}")
        print(f"  知识图谱交互查询  |  {len(self.graph.nodes)} 节点, {len(self.graph.edges)} 关系")
        print(f"  输入问题进行查询，输入 'quit' 退出")
        print(f"{'='*60}\n")

        while True:
            try:
                question = input("Q: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n再见！")
                break

            if not question:
                continue
            if question.lower() in ("quit", "exit", "q"):
                print("再见！")
                break

            result = qa.query(question)
            print(f"\nA: {result['answer']}")

    # ── 单次查询 ──────────────────────────────────────────────────────

    def query(self, question: str,
              store_path: Optional[str] = None) -> Dict[str, Any]:
        """单次查询"""
        store_path = store_path or os.path.join(OUTPUT_DIR, GRAPH_STORE_FILE)

        if not self.graph.load(store_path):
            return {"answer": "图谱文件不存在，请先构建图谱", "data": None}

        qa = QueryAgent(self.graph.nodes, self.graph.edges)
        return qa.query(question)

    # ── 工具 ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        if self.verbose:
            print(msg)
