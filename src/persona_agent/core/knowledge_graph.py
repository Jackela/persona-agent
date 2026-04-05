"""Knowledge graph for RoleRAG-based character knowledge management.

This module implements the knowledge graph structure used by RoleRAG for:
1. Entity storage with semantic normalization
2. Relationship tracking
3. Boundary-aware retrieval
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Entity(BaseModel):
    """An entity in the knowledge graph.

    Entities represent people, places, objects, concepts, etc.
    that the character knows about.
    """

    name: str  # Canonical entity name (after normalization)
    original_names: list[str] = Field(default_factory=list)  # Aliases/variants
    entity_type: str = "unknown"  # character, location, object, concept, etc.
    description: str = ""
    embedding: list[float] | None = None  # Vector embedding for semantic search

    # Metadata
    source: str = ""  # Where this entity was extracted from
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return False
        return self.name == other.name


class Relation(BaseModel):
    """A relationship between two entities."""

    source: str  # Source entity name
    target: str  # Target entity name
    relation_type: str  # Type of relationship (friend, enemy, located_at, etc.)
    description: str = ""  # Textual description of the relationship
    strength: float = Field(0.5, ge=0.0, le=1.0)  # Relationship intensity

    # Metadata
    source_text: str = ""  # Original text describing the relationship
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    def __hash__(self) -> int:
        return hash((self.source, self.target, self.relation_type))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Relation):
            return False
        return (
            self.source == other.source
            and self.target == other.target
            and self.relation_type == other.relation_type
        )


@dataclass
class RetrievalResult:
    """Result of a knowledge graph retrieval."""

    entities: list[Entity] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    context_text: str = ""
    has_out_of_scope: bool = False
    out_of_scope_entities: list[tuple[str, str]] = field(
        default_factory=list
    )  # (entity, rationale)


class KnowledgeGraph:
    """Knowledge graph for character knowledge management.

    Implements the graph structure used by RoleRAG for:
    - Entity storage and retrieval
    - Relationship tracking
    - Semantic normalization
    - Boundary-aware classification
    """

    def __init__(self):
        """Initialize empty knowledge graph."""
        self.graph = nx.DiGraph()
        self.entities: dict[str, Entity] = {}
        self.relations: list[Relation] = []

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the knowledge graph.

        Args:
            entity: Entity to add
        """
        self.entities[entity.name] = entity
        self.graph.add_node(
            entity.name,
            entity=entity,
            embedding=entity.embedding,
        )
        logger.debug(f"Added entity: {entity.name} ({entity.entity_type})")

    def add_relation(self, relation: Relation) -> None:
        """Add a relationship between entities.

        Args:
            relation: Relation to add
        """
        # Ensure entities exist
        if relation.source not in self.entities:
            logger.warning(f"Source entity not found: {relation.source}")
            return
        if relation.target not in self.entities:
            logger.warning(f"Target entity not found: {relation.target}")
            return

        self.relations.append(relation)
        self.graph.add_edge(
            relation.source,
            relation.target,
            relation=relation,
            relation_type=relation.relation_type,
            strength=relation.strength,
        )
        logger.debug(f"Added relation: {relation.source} -> {relation.target}")

    def get_entity(self, name: str) -> Entity | None:
        """Get an entity by name.

        Args:
            name: Entity name (canonical or alias)

        Returns:
            Entity if found, None otherwise
        """
        # Direct lookup
        if name in self.entities:
            return self.entities[name]

        # Check aliases
        for entity in self.entities.values():
            if name in entity.original_names:
                return entity

        return None

    def get_relations(self, entity_name: str, relation_type: str | None = None) -> list[Relation]:
        """Get all relations for an entity.

        Args:
            entity_name: Name of the entity
            relation_type: Optional filter by relation type

        Returns:
            List of relations
        """
        if entity_name not in self.graph:
            return []

        relations = []
        for _, _, edge_data in self.graph.edges(entity_name, data=True):
            relation = edge_data.get("relation")
            if relation and (relation_type is None or relation.relation_type == relation_type):
                relations.append(relation)

        # Also get incoming relations
        for _, _, edge_data in self.graph.in_edges(entity_name, data=True):
            relation = edge_data.get("relation")
            if relation and (relation_type is None or relation.relation_type == relation_type):
                relations.append(relation)

        return relations

    def get_neighbors(self, entity_name: str, depth: int = 1) -> dict[str, list[str]]:
        """Get neighbors of an entity at specified depth.

        Args:
            entity_name: Starting entity
            depth: How many hops to traverse

        Returns:
            Dict mapping entity names to paths
        """
        if entity_name not in self.graph:
            return {}

        neighbors = {}
        for target in nx.single_source_shortest_path_length(self.graph, entity_name, cutoff=depth):
            if target != entity_name:
                path = nx.shortest_path(self.graph, entity_name, target)
                neighbors[target] = path

        return neighbors

    def get_1hop_neighbors(self, entity_name: str) -> list[Entity]:
        """Get all 1-hop neighbors of an entity.

        Args:
            entity_name: Center entity

        Returns:
            List of neighboring entities
        """
        if entity_name not in self.graph:
            return []

        neighbors = []
        for neighbor_name in self.graph.neighbors(entity_name):
            if neighbor_name in self.entities:
                neighbors.append(self.entities[neighbor_name])

        # Also get predecessors
        for neighbor_name in self.graph.predecessors(entity_name):
            if neighbor_name in self.entities:
                neighbors.append(self.entities[neighbor_name])

        return neighbors

    def find_entity_by_embedding(
        self, embedding: list[float], top_k: int = 5
    ) -> list[tuple[Entity, float]]:
        """Find entities by semantic similarity to embedding.

        Args:
            embedding: Query embedding vector
            top_k: Number of results to return

        Returns:
            List of (entity, similarity_score) tuples
        """
        if not embedding:
            return []

        query_vec = np.array(embedding)
        similarities = []

        for entity in self.entities.values():
            if entity.embedding:
                entity_vec = np.array(entity.embedding)
                # Cosine similarity
                similarity = np.dot(query_vec, entity_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(entity_vec)
                )
                similarities.append((entity, float(similarity)))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def extract_subgraph(self, entity_names: list[str], depth: int = 1) -> KnowledgeGraph:
        """Extract a subgraph around specified entities.

        Args:
            entity_names: Center entities
            depth: Traversal depth

        Returns:
            New KnowledgeGraph with subgraph
        """
        subgraph = KnowledgeGraph()
        included_entities = set()

        for entity_name in entity_names:
            if entity_name not in self.graph:
                continue

            # Get entities within depth
            for target, _distance in nx.single_source_shortest_path_length(
                self.graph, entity_name, cutoff=depth
            ):
                included_entities.add(target)

        # Copy entities
        for name in included_entities:
            if name in self.entities:
                subgraph.add_entity(self.entities[name])

        # Copy relations between included entities
        for relation in self.relations:
            if relation.source in included_entities and relation.target in included_entities:
                subgraph.add_relation(relation)

        return subgraph

    def to_context_text(self, entity_names: list[str] | None = None) -> str:
        """Convert knowledge graph to text context for prompts.

        Args:
            entity_names: Specific entities to include (None = all)

        Returns:
            Formatted context text
        """
        if entity_names is None:
            entity_names = list(self.entities.keys())

        lines = []
        for name in entity_names:
            entity = self.get_entity(name)
            if not entity:
                continue

            lines.append(f"## {entity.name}")
            if entity.description:
                lines.append(entity.description)

            # Add relations
            relations = self.get_relations(name)
            if relations:
                lines.append("\nRelationships:")
                for rel in relations[:5]:  # Limit to top 5
                    lines.append(f"- {rel.description} (strength: {rel.strength:.2f})")

            lines.append("")

        return "\n".join(lines)

    def entity_exists(self, name: str) -> bool:
        """Check if an entity exists (by canonical name or alias).

        Args:
            name: Entity name to check

        Returns:
            True if entity exists
        """
        if name in self.entities:
            return True

        return any(name in entity.original_names for entity in self.entities.values())

    def contradicts(self, claim: str, entity_name: str) -> bool:
        """Check if a claim contradicts known facts about an entity.

        Args:
            claim: Claim to check
            entity_name: Entity to check against

        Returns:
            True if claim contradicts known facts
        """
        # This is a placeholder - would need LLM-based contradiction detection
        entity = self.get_entity(entity_name)
        if not entity:
            return False

        # Simple heuristic: check if claim contradicts description
        # In practice, this would use an LLM to judge contradiction
        return False

    def supports(self, claim: str, entity_name: str) -> bool:
        """Check if a claim is supported by known facts.

        Args:
            claim: Claim to check
            entity_name: Entity to check against

        Returns:
            True if claim is supported
        """
        entity = self.get_entity(entity_name)
        # This is a placeholder - would need LLM-based support detection
        return entity is not None

    def merge_entities(self, canonical_name: str, aliases: list[str]) -> None:
        """Merge multiple entity names into a canonical entity.

        This implements entity normalization from RoleRAG.

        Args:
            canonical_name: The canonical name to use
            aliases: Other names that refer to the same entity
        """
        if canonical_name not in self.entities:
            logger.warning(f"Canonical entity not found: {canonical_name}")
            return

        canonical = self.entities[canonical_name]

        for alias in aliases:
            if alias in self.entities and alias != canonical_name:
                # Merge alias entity into canonical
                alias_entity = self.entities[alias]
                canonical.original_names.extend(alias_entity.original_names)
                canonical.original_names.append(alias)

                # Redirect relations
                for relation in self.relations:
                    if relation.source == alias:
                        relation.source = canonical_name
                    if relation.target == alias:
                        relation.target = canonical_name

                # Redirect edges in graph before removing alias node
                if self.graph.has_node(alias):
                    # Get all edges from alias
                    for _, target, data in list(self.graph.edges(alias, data=True)):
                        self.graph.add_edge(canonical_name, target, **data)
                    # Get all edges to alias
                    for source, _, data in list(self.graph.in_edges(alias, data=True)):
                        if source != canonical_name:  # Avoid self-loop
                            self.graph.add_edge(source, canonical_name, **data)
                    # Remove alias node
                # Remove alias entity from dict
                del self.entities[alias]

        logger.info(f"Merged {len(aliases)} aliases into {canonical_name}")

    def statistics(self) -> dict[str, Any]:
        """Get statistics about the knowledge graph.

        Returns:
            Dict with graph statistics
        """
        return {
            "num_entities": len(self.entities),
            "num_relations": len(self.relations),
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "entity_types": {entity.entity_type for entity in self.entities.values()},
            "is_connected": nx.is_weakly_connected(self.graph),
            "density": nx.density(self.graph),
        }

    def clear(self) -> None:
        """Clear all data from the knowledge graph."""
        self.graph.clear()
        self.entities.clear()
        self.relations.clear()
        logger.info("Knowledge graph cleared")
