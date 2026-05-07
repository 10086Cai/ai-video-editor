#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QueryAgent — 自然语言知识图谱查询 Agent

支持自然语言问题，通过关键词匹配 + 图遍历回答查询。

查询模式（自动识别）:
  - 实体详情: "XXX是什么?" "告诉我关于XXX"
  - 邻居查询: "XXX和什么有关?" "XXX使用了什么技术?"
  - 关系查询: "XXX和YYY之间有什么关系?"
  - 搜索: "有哪些技术?" "找到所有项目"
  - 路径查询: "XXX到YYY之间有什么联系?"
  - 统计: "图谱有多少节点?" "最热门的技术是什么?"

输出:
{
    "query_type": str,
    "answer": str,
    "data": {...},
    "reasoning_trace": [...]
}
"""

import re
from typing import Dict, Any, List, Optional, Set
from collections import deque
from config import ENTITY_TYPES


class QueryAgent:
    """自然语言知识图谱查询 Agent"""

    def __init__(self, graph_nodes: Dict[str, Dict[str, Any]],
                 graph_edges: List[Dict[str, Any]]):
        self.nodes = graph_nodes
        self.edges = graph_edges
        self.reasoning_trace: List[Dict[str, Any]] = []

        # 构建邻接表
        self.adj: Dict[str, List[Dict[str, Any]]] = {}
        for edge in graph_edges:
            self.adj.setdefault(edge["source"], []).append(edge)
            # 反向边
            rev = {
                "source": edge["target"],
                "target": edge["source"],
                "type": edge["type"],
                "confidence": edge["confidence"],
                "evidence": edge.get("evidence", ""),
            }
            self.adj.setdefault(edge["target"], []).append(rev)

    # ── 主入口 ────────────────────────────────────────────────────────

    def query(self, question: str) -> Dict[str, Any]:
        """处理自然语言查询"""
        self.reasoning_trace = []
        question = question.strip()

        # 识别查询类型
        query_type, entities = self._classify_query(question)
        self._log("ClassifyQuery", question, {"type": query_type, "entities": entities})

        # 分发到对应处理器
        handlers = {
            "entity_detail": self._handle_entity_detail,
            "neighbor": self._handle_neighbor,
            "relation": self._handle_relation,
            "search": self._handle_search,
            "path": self._handle_path,
            "stats": self._handle_stats,
            "unknown": self._handle_unknown,
        }

        handler = handlers.get(query_type, self._handle_unknown)
        result = handler(question, entities)

        return {
            "query_type": query_type,
            "query": question,
            "answer": result.get("answer", "未找到相关结果"),
            "data": result.get("data"),
            "reasoning_trace": self.reasoning_trace,
        }

    # ── 查询分类 ──────────────────────────────────────────────────────

    def _classify_query(self, question: str):
        """识别查询类型和涉及的实体"""
        # 提取问题中可能匹配的实体名
        mentioned_entities = self._extract_mentioned_entities(question)

        # 统计/全局查询
        if any(w in question for w in ["多少", "统计", "几个", "总数", "最热门", "最受欢迎", "度最高"]):
            return "stats", mentioned_entities

        # 关系查询（两个实体 + "关系"）
        if "关系" in question or "联系" in question or "之间" in question:
            if len(mentioned_entities) >= 2:
                return "relation", mentioned_entities[:2]
            return "relation", mentioned_entities

        # 路径查询
        if any(w in question for w in ["怎么连", "路径", "怎样从"]):
            return "path", mentioned_entities

        # 搜索（按类型）
        type_keywords = {
            "技术": "technology", "项目": "project", "概念": "concept",
            "人物": "person", "组织": "organization", "文档": "document",
            "事件": "event",
        }
        for cn_key, en_type in type_keywords.items():
            if cn_key in question and ("有哪些" in question or "找到" in question or "列出" in question or "所有" in question):
                return "search", [en_type]

        # 邻居查询
        if any(w in question for w in ["和什么", "相关", "关联", "连接", "依赖", "使用了", "包含"]):
            if mentioned_entities:
                return "neighbor", mentioned_entities[:1]

        # 实体详情
        if mentioned_entities:
            return "entity_detail", mentioned_entities[:1]

        return "unknown", mentioned_entities

    def _extract_mentioned_entities(self, question: str) -> List[str]:
        """从问题中提取与图谱节点匹配的实体名"""
        mentioned = []
        q_lower = question.lower()
        # 按名称长度降序匹配（优先匹配更长的名称）
        sorted_nodes = sorted(self.nodes.keys(), key=len, reverse=True)
        for name in sorted_nodes:
            if name.lower() in q_lower and name not in mentioned:
                mentioned.append(name)
        return mentioned

    # ── 处理器 ────────────────────────────────────────────────────────

    def _handle_entity_detail(self, question: str,
                                entities: List[str]) -> Dict[str, Any]:
        if not entities:
            return {"answer": "请在问题中指定一个实体名称", "data": None}

        name = entities[0]
        node = self.nodes.get(name)

        if not node:
            # 模糊搜索
            candidates = [n for n in self.nodes if name.lower() in n.lower()]
            if candidates:
                node = self.nodes[candidates[0]]
                name = candidates[0]
            else:
                return {"answer": f"未找到实体: {name}", "data": None}

        type_cn = ENTITY_TYPES.get(node.get("type", "unknown"), node.get("type", "?"))
        neighbors = self.adj.get(name, [])

        answer = f"[{name}] 类型: {type_cn}\n"
        answer += f"置信度: {node.get('confidence', 0):.2f}\n"

        if node.get("sources"):
            answer += f"来源: {', '.join(node['sources'][:5])}\n"

        if node.get("contexts"):
            answer += f"上下文: {node['contexts'][0][:80]}\n"

        if neighbors:
            answer += f"\n关联 ({len(neighbors)}个):\n"
            for nb in neighbors[:10]:
                rel_cn = self._rel_label(nb["type"])
                answer += f"  --{rel_cn}--> {nb['target']}\n"

        return {"answer": answer, "data": {"node": node, "neighbors": neighbors}}

    def _handle_neighbor(self, question: str,
                           entities: List[str]) -> Dict[str, Any]:
        if not entities:
            return {"answer": "请在问题中指定一个实体名称", "data": None}

        name = entities[0]
        neighbors = self.adj.get(name, [])

        if not neighbors:
            return {"answer": f"{name} 没有已知的关联实体", "data": None}

        # 按关系类型分组
        grouped: Dict[str, List[str]] = {}
        for nb in neighbors:
            rel_cn = self._rel_label(nb["type"])
            grouped.setdefault(rel_cn, []).append(nb["target"])

        answer = f"[{name}] 的关联实体 ({len(neighbors)}个):\n"
        for rel, targets in grouped.items():
            answer += f"\n  {rel}:\n"
            for t in targets:
                answer += f"    - {t}\n"

        return {"answer": answer, "data": {"grouped": grouped}}

    def _handle_relation(self, question: str,
                           entities: List[str]) -> Dict[str, Any]:
        if len(entities) < 2:
            return {"answer": "请指定两个实体来查询关系", "data": None}

        a, b = entities[0], entities[1]
        direct = []
        for edge in self.edges:
            if (edge["source"] == a and edge["target"] == b) or \
               (edge["source"] == b and edge["target"] == a):
                direct.append(edge)

        answer = f"[{a}] 与 [{b}] 之间的关系:\n"

        if direct:
            for d in direct:
                rel_cn = self._rel_label(d["type"])
                answer += f"  直接关系: {rel_cn} (置信度 {d['confidence']:.2f})\n"
                if d.get("evidence"):
                    answer += f"  证据: {d['evidence'][:100]}\n"
        else:
            answer += "  无直接关系\n"

        # 尝试找间接路径
        path = self._find_shortest_path(a, b)
        if path and len(path) > 2:
            answer += f"\n  间接路径: {' → '.join(path)}\n"

        return {"answer": answer, "data": {"direct": direct, "path": path}}

    def _handle_search(self, question: str,
                         entities: List[str]) -> Dict[str, Any]:
        target_type = entities[0] if entities else None

        results = []
        for name, node in self.nodes.items():
            if target_type and node.get("type") != target_type:
                continue
            deg = len(self.adj.get(name, []))
            results.append({"name": name, "type": node.get("type"), "degree": deg})

        results.sort(key=lambda x: x["degree"], reverse=True)

        type_cn = ENTITY_TYPES.get(target_type, "全部") if target_type else "全部"
        answer = f"{type_cn}类型的实体 ({len(results)}个):\n"
        for r in results[:20]:
            type_label = ENTITY_TYPES.get(r["type"], r["type"])
            answer += f"  - {r['name']} ({type_label}, 关联{r['degree']}个)\n"

        return {"answer": answer, "data": {"results": results}}

    def _handle_path(self, question: str,
                       entities: List[str]) -> Dict[str, Any]:
        if len(entities) < 2:
            return {"answer": "请指定起止实体", "data": None}

        a, b = entities[0], entities[1]
        path = self._find_shortest_path(a, b)

        if not path:
            return {"answer": f"[{a}] 和 [{b}] 之间没有连通路径", "data": None}

        answer = f"[{a}] → [{b}] 的最短路径 (长度 {len(path)-1}):\n"
        for i in range(len(path) - 1):
            rels = [e for e in self.edges
                    if (e["source"] == path[i] and e["target"] == path[i+1]) or
                       (e["source"] == path[i+1] and e["target"] == path[i])]
            rel_cn = self._rel_label(rels[0]["type"]) if rels else "?"
            answer += f"  {path[i]} --{rel_cn}--> {path[i+1]}\n"

        return {"answer": answer, "data": {"path": path}}

    def _handle_stats(self, question: str,
                        entities: List[str]) -> Dict[str, Any]:
        node_count = len(self.nodes)
        edge_count = len(self.edges)

        type_dist: Dict[str, int] = {}
        for node in self.nodes.values():
            t = node.get("type", "unknown")
            type_dist[t] = type_dist.get(t, 0) + 1

        degree: Dict[str, int] = {}
        for edge in self.edges:
            degree[edge["source"]] = degree.get(edge["source"], 0) + 1
            degree[edge["target"]] = degree.get(edge["target"], 0) + 1

        top = sorted(degree.items(), key=lambda x: x[1], reverse=True)[:5]

        answer = f"知识图谱统计:\n"
        answer += f"  节点总数: {node_count}\n"
        answer += f"  关系总数: {edge_count}\n"
        answer += f"\n  节点类型分布:\n"
        for t, count in sorted(type_dist.items(), key=lambda x: x[1], reverse=True):
            t_cn = ENTITY_TYPES.get(t, t)
            answer += f"    {t_cn}: {count}\n"
        answer += f"\n  关联最多的节点 (Hub):\n"
        for name, deg in top:
            answer += f"    {name}: {deg}个关联\n"

        return {"answer": answer, "data": {"type_dist": type_dist, "top_hubs": top}}

    def _handle_unknown(self, question: str,
                          entities: List[str]) -> Dict[str, Any]:
        # 尝试关键词搜索
        if entities:
            return self._handle_entity_detail(question, entities)

        return {"answer": "无法理解您的问题。试试:\n"
                          "  - \"XXX是什么\"\n"
                          "  - \"XXX和什么有关\"\n"
                          "  - \"XXX和YYY的关系\"\n"
                          "  - \"有哪些技术\"\n"
                          "  - \"统计\" 或 \"最热门\"", "data": None}

    # ── 工具 ──────────────────────────────────────────────────────────

    def _find_shortest_path(self, start: str, end: str,
                             max_depth: int = 6) -> Optional[List[str]]:
        """BFS 最短路径"""
        if start not in self.nodes or end not in self.nodes:
            return None
        if start == end:
            return [start]

        visited: Set[str] = {start}
        queue = deque([(start, [start])])

        while queue:
            current, path = queue.popleft()
            if len(path) > max_depth:
                continue

            for edge in self.adj.get(current, []):
                neighbor = edge["target"]
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                new_path = path + [neighbor]
                if neighbor == end:
                    return new_path
                queue.append((neighbor, new_path))

        return None

    def _rel_label(self, rel_type: str) -> str:
        from graph_builder import REL_TYPE_LABELS
        return REL_TYPE_LABELS.get(rel_type, rel_type)

    def _log(self, step: str, inp: Any, out: Any):
        self.reasoning_trace.append({"step": step, "input": inp, "output": out})
