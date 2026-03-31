from __future__ import annotations

from collections import defaultdict

import networkx as nx


def _partition_with_fallback(graph: nx.Graph) -> list[set[str]]:
    try:
        import community as community_louvain

        membership = community_louvain.best_partition(graph, weight="weight", random_state=42)
        grouped: dict[int, set[str]] = defaultdict(set)
        for node, community_id in membership.items():
            grouped[community_id].add(node)
        return list(grouped.values())
    except ImportError:
        if hasattr(nx.community, "louvain_communities"):
            return [set(group) for group in nx.community.louvain_communities(graph, weight="weight", seed=42)]
        return [set(group) for group in nx.community.greedy_modularity_communities(graph, weight="weight")]


def detect_communities(exercise_ids: list[str], edges: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
    graph = nx.Graph()
    graph.add_nodes_from(exercise_ids)
    for edge in edges:
        graph.add_edge(edge["source"], edge["target"], weight=edge["score"])

    if graph.number_of_edges() == 0:
        partitions = [{node} for node in sorted(exercise_ids)]
    else:
        partitions = _partition_with_fallback(graph)

    partitions = sorted((sorted(group) for group in partitions), key=lambda members: (-len(members), members[0]))
    communities: dict[str, dict] = {}
    community_by_exercise: dict[str, str] = {}

    for index, members in enumerate(partitions):
        community_id = str(index)
        communities[community_id] = {
            "members": members,
            "size": len(members),
        }
        for member in members:
            community_by_exercise[member] = community_id

    return communities, community_by_exercise
