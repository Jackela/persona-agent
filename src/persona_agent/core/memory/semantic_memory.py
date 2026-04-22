"""Semantic memory - facts, concepts, and knowledge graph."""

from __future__ import annotations

import importlib.util
from datetime import datetime
from typing import Any

NETWORKX_AVAILABLE = importlib.util.find_spec("networkx") is not None


class SemanticMemory:
    """Semantic memory - facts, concepts, and knowledge graph.

    Stores factual knowledge as a directed graph using NetworkX:
    - Nodes represent entities
    - Edges represent relationships (with predicate labels)
    - Supports entity queries and graph traversal

    If NetworkX is not installed, graph operations gracefully degrade
    to no-ops or empty results. Fact storage continues to work via
    the internal facts dictionary.
    """

    def __init__(self):
        """Initialize semantic memory with empty knowledge graph."""
        if NETWORKX_AVAILABLE:
            import networkx as nx

            self.graph: Any = nx.DiGraph()
        else:
            self.graph = None
        self._facts: dict[str, list[tuple[str, float]]] = {}  # entity -> [(fact, confidence)]

    def add_fact(self, entity: str, fact: str, confidence: float = 1.0) -> None:
        """Add a factual statement about an entity."""
        entity = entity.lower().strip()
        fact = fact.strip()
        confidence = max(0.0, min(1.0, confidence))

        # Add to facts dictionary
        if entity not in self._facts:
            self._facts[entity] = []
        self._facts[entity].append((fact, confidence))

        # Add entity as node in graph
        if self.graph is not None:
            if entity not in self.graph:
                self.graph.add_node(entity, node_type="entity")

            # Add fact as a "has_fact" relationship
            fact_node = f"fact:{entity}:{len(self._facts[entity])}"
            self.graph.add_node(fact_node, node_type="fact", content=fact)
            self.graph.add_edge(
                entity,
                fact_node,
                predicate="has_fact",
                confidence=confidence,
            )

    def add_relationship(
        self,
        subject: str,
        predicate: str,
        obj: str,
        confidence: float = 1.0,
    ) -> None:
        """Add a relationship to the knowledge graph."""
        if self.graph is None:
            return

        subject = subject.lower().strip()
        obj = obj.lower().strip()
        predicate = predicate.lower().strip()
        confidence = max(0.0, min(1.0, confidence))

        # Add nodes if they don't exist
        if subject not in self.graph:
            self.graph.add_node(subject, node_type="entity")
        if obj not in self.graph:
            self.graph.add_node(obj, node_type="entity")

        # Add edge with relationship metadata
        self.graph.add_edge(
            subject,
            obj,
            predicate=predicate,
            confidence=confidence,
            timestamp=datetime.now().isoformat(),
        )

    def query_entity(self, entity: str) -> dict[str, Any]:
        """Query all known information about an entity."""
        entity = entity.lower().strip()

        # Get facts (always available, even without NetworkX)
        facts = self._facts.get(entity, [])

        if self.graph is None or entity not in self.graph:
            return {
                "entity": entity,
                "exists": bool(facts),
                "facts": [{"fact": f, "confidence": c} for f, c in facts],
                "outgoing_relations": [],
                "incoming_relations": [],
            }

        # Get outgoing relationships
        outgoing = []
        for _, target, data in self.graph.out_edges(entity, data=True):
            if data.get("predicate") != "has_fact":
                outgoing.append(
                    {
                        "predicate": data.get("predicate", "related_to"),
                        "object": target,
                        "confidence": data.get("confidence", 1.0),
                    }
                )

        # Get incoming relationships
        incoming = []
        for source, _, data in self.graph.in_edges(entity, data=True):
            if data.get("predicate") != "has_fact":
                incoming.append(
                    {
                        "subject": source,
                        "predicate": data.get("predicate", "related_to"),
                        "confidence": data.get("confidence", 1.0),
                    }
                )

        return {
            "entity": entity,
            "exists": True,
            "facts": [{"fact": f, "confidence": c} for f, c in facts],
            "outgoing_relations": outgoing,
            "incoming_relations": incoming,
        }

    def extract_entities(self, text: str) -> list[str]:
        """Extract entities from text.

        Returns an empty list to comply with GDPR - regex-based PII
        extraction has been removed.
        """
        return []

    def get_related_entities(self, entity: str, depth: int = 1) -> list[str]:
        """Get entities related within N hops in the knowledge graph."""
        if self.graph is None:
            return []

        entity = entity.lower().strip()

        if entity not in self.graph:
            return []

        related: set[str] = set()

        # Use BFS to find related entities up to depth
        visited: set[str] = {entity}
        current_level: set[str] = {entity}

        for _ in range(depth):
            next_level: set[str] = set()
            for node in current_level:
                # Outgoing edges
                for neighbor in self.graph.successors(node):
                    if neighbor not in visited:
                        # Skip fact nodes
                        if self.graph.nodes[neighbor].get("node_type") == "entity":
                            related.add(neighbor)
                            next_level.add(neighbor)
                        visited.add(neighbor)

                # Incoming edges
                for neighbor in self.graph.predecessors(node):
                    if neighbor not in visited:
                        if self.graph.nodes[neighbor].get("node_type") == "entity":
                            related.add(neighbor)
                            next_level.add(neighbor)
                        visited.add(neighbor)

            current_level = next_level
            if not current_level:
                break

        return sorted(related)

    def find_path(self, entity1: str, entity2: str) -> list[dict] | None:
        """Find relationship path between two entities."""
        if self.graph is None:
            return None

        entity1 = entity1.lower().strip()
        entity2 = entity2.lower().strip()

        if entity1 not in self.graph or entity2 not in self.graph:
            return None

        try:
            import networkx as nx

            path = nx.shortest_path(self.graph, entity1, entity2)
            relationships = []

            for i in range(len(path) - 1):
                source, target = path[i], path[i + 1]
                edge_data = self.graph.get_edge_data(source, target)
                relationships.append(
                    {
                        "from": source,
                        "to": target,
                        "predicate": (
                            edge_data.get("predicate", "related_to") if edge_data else "related_to"
                        ),
                    }
                )

            return relationships
        except Exception:
            return None

    def get_all_entities(self) -> list[str]:
        """Get all entities in the knowledge graph."""
        if self.graph is None:
            return list(self._facts.keys())

        return [
            node for node, data in self.graph.nodes(data=True) if data.get("node_type") == "entity"
        ]


__all__ = ["SemanticMemory"]
