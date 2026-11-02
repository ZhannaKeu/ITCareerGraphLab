import networkx as nx

class InvalidGraph(ValueError):
    pass

def build_graph(skills, edges):
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(skills))
    for parent, child in sorted(set(edges)):
        if parent not in graph or child not in graph:
            raise InvalidGraph(f"Unknown skill in edge {parent} → {child}")
        graph.add_edge(parent, child)
    if not nx.is_directed_acyclic_graph(graph):
        cycle = nx.find_cycle(graph)
        raise InvalidGraph(f"Prerequisite cycle: {cycle}")
    return graph

def topological_order(graph, algorithm="kahn"):
    if algorithm == "kahn":
        return list(nx.lexicographical_topological_sort(graph))
    if algorithm != "dfs":
        raise ValueError("Unsupported algorithm")
    # Iterative DFS avoids Python recursion limits on large DAGs.
    visited, result = set(), []
    for root in sorted(graph, reverse=True):
        stack = [(root, False)]
        while stack:
            node, expanded = stack.pop()
            if expanded:
                result.append(node)
            elif node not in visited:
                visited.add(node)
                stack.append((node, True))
                stack.extend((child, False) for child in sorted(graph.successors(node), reverse=True) if child not in visited)
    return result[::-1]

def prerequisite_closure(graph, seeds):
    # Recursive dependency semantics, implemented with a stack for deep DAGs.
    closure, stack = set(), sorted(seeds, reverse=True)
    while stack:
        node = stack.pop()
        for parent in sorted(graph.predecessors(node)):
            if parent not in closure:
                closure.add(parent)
                stack.append(parent)
    return closure
