"""Build a knowledge graph from anime.json -> graph.json.

Nodes: one per anime (id, label, year, score, cover, format).
Edges: 5 types with weights (see config.GRAPH_DEFAULTS).
Hub control: any node with degree > hub_max_degree gets its weakest edges trimmed.
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from config import ANIME_JSON, GRAPH_DEFAULTS, GRAPH_JSON


def _load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _node_for(rec: dict) -> dict:
    return {
        "id": rec["id"],
        "label": (rec.get("titles") or {}).get("primary_zh") or rec.get("id"),
        "year": rec.get("year"),
        "score": (rec.get("rating") or {}).get("score"),
        "cover": (rec.get("cover") or {}).get("local") or (rec.get("cover") or {}).get("url"),
        "format": rec.get("format"),
        "section": rec.get("section_origin"),
        "studios": rec.get("studios") or [],
        "categories": rec.get("categories") or [],
    }


def build(anime: dict) -> dict:
    weights = GRAPH_DEFAULTS["edge_weights"]
    strong_rank = GRAPH_DEFAULTS["tag_strong_rank_min"]
    hub_max = GRAPH_DEFAULTS["hub_max_degree"]

    # ---- Nodes ----
    nodes = [_node_for(r) for r in anime.values()]
    ids = {r["id"] for r in anime.values()}

    # ---- Indexes for shared-attribute edges ----
    by_studio: dict[str, list[str]] = defaultdict(list)
    by_year: dict[int, list[str]] = defaultdict(list)
    by_genre: dict[str, set[str]] = defaultdict(set)

    for aid, rec in anime.items():
        for s in rec.get("studios") or []:
            by_studio[s].append(aid)
        if rec.get("year"):
            by_year[rec["year"]].append(aid)
        for g in rec.get("categories") or []:
            by_genre[g].add(aid)

    # Strong tags from anime.tags (post-rank-filter, but we did not preserve rank in db).
    # We approximate "strong" by: any tag that appears in ≤ N% of corpus → distinctive.
    tag_to_anime: dict[str, set[str]] = defaultdict(set)
    for aid, rec in anime.items():
        for t in rec.get("tags") or []:
            if t.startswith(("年份-", "studio-", "format-", "星級-")) or t in ("劇場版", "季番", "已完結"):
                continue
            tag_to_anime[t].add(aid)

    edges: list[dict] = []
    pair_added: dict[tuple, dict] = {}

    def add_edge(a: str, b: str, etype: str, weight: float, detail: str = ""):
        if a == b or a not in ids or b not in ids or weight <= 0:
            return
        key = tuple(sorted([a, b]) + [etype])
        if key in pair_added:
            pair_added[key]["weight"] = max(pair_added[key]["weight"], weight)
            if detail and detail not in pair_added[key]["detail"]:
                pair_added[key]["detail"].append(detail)
            return
        edge = {"source": a, "target": b, "type": etype, "weight": round(weight, 3), "detail": [detail] if detail else []}
        pair_added[key] = edge
        edges.append(edge)

    # ---- Franchise edges (from relations) ----
    for aid, rec in anime.items():
        rels = rec.get("relations") or {}
        for rt, refs in rels.items():
            if rt == "other":
                continue
            for ref in refs:
                add_edge(aid, ref, "franchise", weights["franchise"], rt)

    # ---- Same-studio ----
    for studio, ids_list in by_studio.items():
        if len(ids_list) < 2:
            continue
        for a, b in combinations(ids_list, 2):
            add_edge(a, b, "same_studio", weights["same_studio"], studio)

    # ---- Same-year ----
    for year, ids_list in by_year.items():
        if len(ids_list) < 2:
            continue
        for a, b in combinations(ids_list, 2):
            add_edge(a, b, "same_year", weights["same_year"], str(year))

    # ---- Shared-genre ----
    seen_genre_pairs: set[tuple[str, str]] = set()
    items = list(anime.items())
    for i, (aid, ra) in enumerate(items):
        ga = set(ra.get("categories") or [])
        if not ga:
            continue
        for aid2, rb in items[i + 1:]:
            gb = set(rb.get("categories") or [])
            inter = ga & gb
            if len(inter) >= 2:
                w = weights["shared_genre_per_overlap"] * len(inter)
                add_edge(aid, aid2, "shared_genre", w, ",".join(sorted(inter)))

    # ---- Shared-tag (use distinctive tags only: tag_to_anime size <= 30) ----
    distinctive = {t for t, ids_set in tag_to_anime.items() if 1 < len(ids_set) <= 30}
    for tag in distinctive:
        ids_list = sorted(tag_to_anime[tag])
        if len(ids_list) > 12:
            # cap: only connect a chain to avoid quadratic edge explosion
            for k in range(len(ids_list) - 1):
                add_edge(ids_list[k], ids_list[k + 1], "shared_tag", weights["shared_tag_per_overlap"], tag)
        else:
            for a, b in combinations(ids_list, 2):
                add_edge(a, b, "shared_tag", weights["shared_tag_per_overlap"], tag)

    # ---- Hub trimming: cap degree per node, trim weakest non-franchise edges ----
    if hub_max > 0:
        adj: dict[str, list[dict]] = defaultdict(list)
        for e in edges:
            adj[e["source"]].append(e)
            adj[e["target"]].append(e)

        kept_ids: set[int] = set()
        dropped_edges: set[int] = set()

        # Sort edges per node by importance (franchise first, then weight desc)
        def edge_key(e):
            return (0 if e["type"] == "franchise" else 1, -e["weight"])

        for node_id, node_edges in adj.items():
            node_edges.sort(key=edge_key)
            keep = node_edges[:hub_max]
            kept_ids.update(id(e) for e in keep)

        # Edges kept by AT LEAST one endpoint survive (avoids losing edges entirely
        # just because the OTHER endpoint is also a hub but has stricter ranking)
        new_edges = [e for e in edges if id(e) in kept_ids]
        edges = new_edges

    return {
        "version": 1,
        "nodes": nodes,
        "edges": edges,
        "edge_types": list(weights.keys()),
    }


def run() -> None:
    if not ANIME_JSON.exists():
        print(f"[graph] {ANIME_JSON} not found — run enrich first")
        sys.exit(2)
    anime = json.loads(ANIME_JSON.read_text(encoding="utf-8")).get("anime", {})
    g = build(anime)
    _save(GRAPH_JSON, g)
    print(f"[graph] wrote {len(g['nodes'])} nodes, {len(g['edges'])} edges to {GRAPH_JSON}")
    type_counts: dict[str, int] = {}
    for e in g["edges"]:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")
