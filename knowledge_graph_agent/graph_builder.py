#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GraphBuilder — 知识图谱构建与存储 Agent

功能:
  1. 将实体和关系构建为图结构
  2. 持久化为 JSON
  3. 导出为 Graphviz DOT 格式（可渲染为可视化图）
  4. 导出为 Mermaid 格式（可在 Markdown 中直接渲染）
  5. 计算图统计信息（节点数、边数、度分布、连通分量）
  6. 支持增量更新（新文档合并到已有图谱）
"""

import os
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from collections import defaultdict
from config import GRAPH_STORE_FILE, DOT_EXPORT_FILE, ENTITY_TYPES


class GraphBuilder:
    """知识图谱构建与存储 Agent"""

    def __init__(self, store_path: str = GRAPH_STORE_FILE):
        self.store_path = store_path
        self.nodes: Dict[str, Dict[str, Any]] = {}    # name → node_data
        self.edges: List[Dict[str, Any]] = []          # list of edges
        self.build_trace: List[Dict[str, Any]] = []

    # ── 构建 ──────────────────────────────────────────────────────────

    def build(
        self,
        all_entities: List[Dict[str, Any]],
        all_relations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """从实体和关系构建知识图谱"""
        self.build_trace = []

        # 添加节点
        for ent in all_entities:
            name = ent["name"]
            if name in self.nodes:
                # 合并：提升置信度，追加来源
                self.nodes[name]["confidence"] = max(
                    self.nodes[name]["confidence"], ent["confidence"]
                )
                if ent.get("source") and ent["source"] not in self.nodes[name].get("sources", []):
                    self.nodes[name].setdefault("sources", []).append(ent["source"])
                if ent.get("context"):
                    self.nodes[name].setdefault("contexts", []).append(ent["context"][:100])
            else:
                self.nodes[name] = {
                    "name": name,
                    "type": ent["type"],
                    "confidence": ent["confidence"],
                    "sources": [ent["source"]] if ent.get("source") else [],
                    "contexts": [ent["context"][:100]] if ent.get("context") else [],
                }

        self._log("AddNodes", len(all_entities), len(self.nodes))

        # 添加边
        for rel in all_relations:
            src = rel["source"]
            tgt = rel["target"]
            # 确保两端节点存在
            if src not in self.nodes:
                self.nodes[src] = {"name": src, "type": "unknown", "confidence": 0.3, "sources": [], "contexts": []}
            if tgt not in self.nodes:
                self.nodes[tgt] = {"name": tgt, "type": "unknown", "confidence": 0.3, "sources": [], "contexts": []}

            self.edges.append({
                "source": src,
                "target": tgt,
                "type": rel["type"],
                "confidence": rel["confidence"],
                "evidence": rel.get("evidence", ""),
                "inference_method": rel.get("inference_method", ""),
            })

        self._log("AddEdges", len(all_relations), len(self.edges))

        stats = self.get_stats()
        self._log("Stats", "-", stats)

        return stats

    # ── 持久化 ────────────────────────────────────────────────────────

    def save(self, path: Optional[str] = None) -> str:
        """保存图谱为 JSON"""
        path = path or self.store_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        data = {
            "nodes": self.nodes,
            "edges": self.edges,
            "stats": self.get_stats(),
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return path

    def load(self, path: Optional[str] = None) -> bool:
        """从 JSON 加载已有图谱"""
        path = path or self.store_path
        if not os.path.isfile(path):
            return False

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.nodes = data.get("nodes", {})
        self.edges = data.get("edges", [])
        return True

    # ── 导出 DOT ─────────────────────────────────────────────────────

    def export_dot(self, path: str = DOT_EXPORT_FILE) -> str:
        """导出为 Graphviz DOT 格式"""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        # 节点颜色映射
        type_colors = {
            "person": "#378ADD", "project": "#534AB7", "technology": "#3B6D11",
            "concept": "#BA7517", "event": "#A32D2D", "organization": "#0F6E56",
            "document": "#72243E", "location": "#085041", "unknown": "#888780",
        }

        # 边样式映射
        edge_styles = {
            "uses": '[color="#3B6D11", style=solid]',
            "depends_on": '[color="#BA7517", style=dashed]',
            "part_of": '[color="#378ADD", style=dotted]',
            "contains": '[color="#534AB7", style=bold]',
            "created_by": '[color="#0F6E56", style=solid]',
            "related_to": '[color="#888780", style=solid]',
        }

        lines = ['digraph KnowledgeGraph {', '  rankdir=LR;', '  node [shape=box, style=filled, fontname="sans-serif", fontsize=11];', '']

        # 节点
        for name, node in self.nodes.items():
            color = type_colors.get(node.get("type", "unknown"), "#888780")
            safe_name = name.replace('"', '\\"')
            label_type = ENTITY_TYPES.get(node.get("type", "unknown"), node.get("type", "?"))
            lines.append(f'  "{safe_name}" [fillcolor="{color}", label="{safe_name}\\n({label_type})"];')

        lines.append("")

        # 边
        seen_edges: Set[Tuple[str, str, str]] = set()
        for edge in self.edges:
            src = edge["source"].replace('"', '\\"')
            tgt = edge["target"].replace('"', '\\"')
            rel = edge["type"]
            ekey = (src, tgt, rel)
            if ekey in seen_edges:
                continue
            seen_edges.add(ekey)

            style = edge_styles.get(rel, '[color="#888780"]')
            label = REL_TYPE_LABELS.get(rel, rel)
            conf = edge.get("confidence", 0)
            lines.append(f'  "{src}" -> "{tgt}" [label="{label} ({conf:.1f})" {style}];')

        lines.append("}")
        dot_content = "\n".join(lines)

        with open(path, "w", encoding="utf-8") as f:
            f.write(dot_content)

        return path

    # ── 导出 Mermaid ─────────────────────────────────────────────────

    def export_mermaid(self) -> str:
        """导出为 Mermaid 格式（可在 Markdown 中直接渲染）"""
        type_map = {
            "person": "👤", "project": "📁", "technology": "⚙️",
            "concept": "💡", "event": "📅", "organization": "🏢",
            "document": "📄", "location": "📍", "unknown": "❓",
        }

        lines = ["graph LR"]

        seen_edges: Set[Tuple[str, str]] = set()
        for edge in self.edges:
            src = edge["source"].replace(" ", "_")
            tgt = edge["target"].replace(" ", "_")
            rel = edge["type"]
            ekey = (src, tgt)
            if ekey in seen_edges:
                continue
            seen_edges.add(ekey)
            lines.append(f'  {src}["{edge["source"]}"] -->|{rel}| {tgt}["{edge["target"]}"]')

        return "\n".join(lines)

    # ── 图统计 ────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """计算图的统计信息"""
        node_count = len(self.nodes)
        edge_count = len(self.edges)

        # 度分布
        degree: Dict[str, int] = defaultdict(int)
        for edge in self.edges:
            degree[edge["source"]] += 1
            degree[edge["target"]] += 1

        # 按类型统计节点
        type_dist: Dict[str, int] = defaultdict(int)
        for node in self.nodes.values():
            type_dist[node.get("type", "unknown")] += 1

        # 按类型统计关系
        rel_dist: Dict[str, int] = defaultdict(int)
        for edge in self.edges:
            rel_dist[edge["type"]] += 1

        # Hub 节点（度最高的前5个）
        top_hubs = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:5]

        # 连通分量（BFS）
        components = self._find_components()

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "avg_degree": round(sum(degree.values()) / max(node_count, 1), 2),
            "max_degree": max(degree.values()) if degree else 0,
            "type_distribution": dict(type_dist),
            "relation_distribution": dict(rel_dist),
            "top_hubs": [{"node": n, "degree": d} for n, d in top_hubs],
            "connected_components": len(components),
            "largest_component": len(max(components, key=len)) if components else 0,
        }

    def _find_components(self) -> List[Set[str]]:
        """BFS 查找连通分量"""
        adj: Dict[str, Set[str]] = defaultdict(set)
        for edge in self.edges:
            adj[edge["source"]].add(edge["target"])
            adj[edge["target"]].add(edge["source"])

        visited: Set[str] = set()
        components: List[Set[str]] = []

        for node in self.nodes:
            if node not in visited:
                component: Set[str] = set()
                queue = [node]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    component.add(current)
                    queue.extend(adj[current] - visited)
                components.append(component)

        return components

    # ── 查询接口 ──────────────────────────────────────────────────────

    def get_neighbors(self, node_name: str) -> Dict[str, Any]:
        """获取节点的所有邻居"""
        neighbors = {"in": [], "out": [], "bidirectional": []}
        for edge in self.edges:
            if edge["source"] == node_name:
                neighbors["out"].append(edge)
            if edge["target"] == node_name:
                neighbors["in"].append(edge)

        return neighbors

    def search_nodes(self, keyword: str, node_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """按关键词搜索节点"""
        results = []
        kw_lower = keyword.lower()
        for name, node in self.nodes.items():
            if kw_lower in name.lower():
                if node_type and node.get("type") != node_type:
                    continue
                results.append(node)
        return results

    def get_subgraph(self, node_name: str, depth: int = 1) -> "GraphBuilder":
        """获取以某节点为中心的子图（BFS遍历）"""
        sub = GraphBuilder()
        visited: Set[str] = set()
        queue = [(node_name, 0)]

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)

            if current in self.nodes:
                sub.nodes[current] = self.nodes[current]

            for edge in self.edges:
                if edge["source"] == current and edge["target"] not in visited:
                    sub.edges.append(edge)
                    queue.append((edge["target"], d + 1))
                elif edge["target"] == current and edge["source"] not in visited:
                    sub.edges.append(edge)
                    queue.append((edge["source"], d + 1))

        return sub

    # ── 工具 ──────────────────────────────────────────────────────────

    def _log(self, step: str, inp: Any, out: Any):
        self.build_trace.append({"step": step, "input": inp, "output": out})


# 关系类型中文标签
REL_TYPE_LABELS = {
    "uses": "使用", "part_of": "属于", "depends_on": "依赖",
    "contains": "包含", "related_to": "相关", "created_by": "创建",
    "works_on": "参与", "located_in": "位于", "references": "引用",
    "precedes": "先于", "extends": "扩展",
}
