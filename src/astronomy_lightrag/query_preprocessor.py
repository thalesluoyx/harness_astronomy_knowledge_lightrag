"""
query_preprocessor.py
Astronomical Query Expansion & Exact Entity Matching Preprocessor.

Solves the dense-vector dilution problem for short astronomical designations
(e.g. 'M31', 'M42', 'C14', 'UHC') by:
1. Identifying catalog designations & celestial terms using Chinese/English boundary-safe regex.
2. Expanding queries with authoritative cross-catalog aliases and bilingual terms.
3. Extracting exact entity candidates for hybrid dual-track routing (exact match injection).
"""
import re
from typing import Tuple, List, Dict

try:
    from .domain_dict import build_unified_catalog_map
except ImportError:
    from astronomy_lightrag.domain_dict import build_unified_catalog_map

# Load unified catalog map from authoritative domain dictionary
ASTRONOMICAL_CATALOG_MAP: Dict[str, List[str]] = build_unified_catalog_map()

# Augment with query-specific variations and aliases
_EXTRA_ALIASES: Dict[str, List[str]] = {
    "M31": [
        "仙女座大星系", "Andromeda Galaxy", "NGC 224",
        "Great Nebula in Andromeda", "Great Nebula In Andromeda",
        "Great Spiral Nebula in Andromeda", "Great Spiral Nebula In Andromeda",
        "M31 (Andromeda Galaxy)", "Andromeda Galaxy (M31)", "Great Andromeda Galaxy"
    ],
    "NGC 2244": ["玫瑰星团", "Central Cluster of Rosette", "Caldwell 50"],
    "NGC 2451": ["船尾座星组", "Puppis Asterism"],
    "UHC": ["Ultra High Contrast", "超高反差滤镜", "UHC滤镜", "[O III]", "H-beta"],
    "OIII": ["O-III", "双重电离氧滤镜", "Oxygen-III", "5007埃", "5000埃"],
    "O-III": ["OIII", "双重电离氧滤镜", "Oxygen-III", "5007埃"],
    "H-BETA": ["H-β", "氢Beta滤镜", "Hydrogen-Beta", "4861埃"],
}

for k, vals in _EXTRA_ALIASES.items():
    if k in ASTRONOMICAL_CATALOG_MAP:
        for v in vals:
            if v not in ASTRONOMICAL_CATALOG_MAP[k]:
                ASTRONOMICAL_CATALOG_MAP[k].append(v)
    else:
        ASTRONOMICAL_CATALOG_MAP[k] = vals

# Compiled regex patterns using Chinese/English boundary lookarounds
# (?<![a-zA-Z0-9]) ensures we do not match inside 'LM31' or 'M310'
# (?![a-zA-Z0-9]) ensures clean trailing boundary
COMPILED_PATTERNS = {
    key: re.compile(rf"(?<![a-zA-Z0-9]){re.escape(key)}(?![a-zA-Z0-9])", re.IGNORECASE)
    for key in ASTRONOMICAL_CATALOG_MAP.keys()
}


def preprocess_astronomy_query(query: str) -> Tuple[str, List[str]]:
    """
    Expands an astronomical query with aliases and extracts exact entity keywords.

    Args:
        query: Raw user query string.

    Returns:
        tuple (expanded_query, detected_entities):
        - expanded_query: Query with bilingual aliases injected to maximize dense vector recall.
        - detected_entities: Exact entity names/aliases for dual-track injection.
    """
    if not query:
        return query, []

    expanded = query
    detected_entities: List[str] = []

    for key, aliases in ASTRONOMICAL_CATALOG_MAP.items():
        pattern = COMPILED_PATTERNS[key]
        match = pattern.search(query)
        if match:
            # Check which aliases are NOT already in the user query
            missing_aliases = [
                a for a in aliases[:3]
                if a.lower() not in query.lower()
            ]

            if missing_aliases:
                # Format: "M31 (仙女座大星系 / Andromeda Galaxy / NGC 224)"
                expansion_text = f" ({' / '.join(missing_aliases)})"
                # Replace only the first occurrence to avoid repetitive text
                expanded = pattern.sub(f"{match.group(0)}{expansion_text}", expanded, count=1)

            # Collect detected entities for exact match routing
            if key not in detected_entities:
                detected_entities.append(key)
            for a in aliases:
                if a not in detected_entities:
                    detected_entities.append(a)

    return expanded, detected_entities


_HOOK_INSTALLED = False

def install_exact_match_hook():
    """
    Hooks LightRAG's internal _get_node_data to inject exact matching graph nodes (Problem 2).
    Ensures that when catalog targets (like M31) are queried, their exact graph nodes and
    associated relationships are retrieved even if dense vector similarity dilutes them.
    """
    global _HOOK_INSTALLED
    if _HOOK_INSTALLED:
        return

    import asyncio
    import logging
    import lightrag.operate as op

    logger = logging.getLogger("astronomy_lightrag.exact_match")
    orig_get_node_data = op._get_node_data

    async def hooked_get_node_data(
        query: str,
        knowledge_graph_inst,
        entities_vdb,
        query_param,
        query_embedding=None,
    ):
        node_datas, use_relations = await orig_get_node_data(
            query,
            knowledge_graph_inst,
            entities_vdb,
            query_param,
            query_embedding=query_embedding,
        )

        injected_entities = getattr(query_param, "_exact_match_entities", None)
        if injected_entities is None and isinstance(query_param.ll_keywords, list):
            injected_entities = query_param.ll_keywords

        if injected_entities:
            existing_names = {n["entity_name"].lower() for n in node_datas}
            missing_injected = []
            for ent_name in injected_entities:
                if ent_name.lower() not in existing_names:
                    if await knowledge_graph_inst.has_node(ent_name):
                        missing_injected.append(ent_name)

            if missing_injected:
                logger.info(f"[Exact Match Injection] Injecting missing graph nodes: {missing_injected}")
                injected_dict, injected_deg = await asyncio.gather(
                    knowledge_graph_inst.get_nodes_batch(missing_injected),
                    knowledge_graph_inst.node_degrees_batch(missing_injected),
                )
                extra_nodes = []
                for name in missing_injected:
                    nd = injected_dict.get(name)
                    if nd:
                        extra_nodes.append({
                            **nd,
                            "entity_name": name,
                            "rank": injected_deg.get(name, 100),
                            "created_at": None,
                        })

                if extra_nodes:
                    node_datas = extra_nodes + node_datas
                    extra_relations = await op._find_most_related_edges_from_entities(
                        extra_nodes,
                        query_param,
                        knowledge_graph_inst,
                    )
                    use_relations = extra_relations + use_relations
                    logger.info(f"[Exact Match Injection] Augmented to {len(node_datas)} nodes, {len(use_relations)} relations")

        return node_datas, use_relations

    op._get_node_data = hooked_get_node_data
    _HOOK_INSTALLED = True

