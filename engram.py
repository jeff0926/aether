"""
Engram - Subgraph Persistence / Working Memory layer for AETHER capsules.

An engram (neuroscience) is the physical memory trace a memory leaves in the brain.
This module manages the equivalent for an AETHER agent: which KG nodes were "activated"
during a session, how strongly, and what persists into the next.
"""

import json
from pathlib import Path
from datetime import datetime
from collections import deque

import kg as kg_module

# Default engram configuration
DEFAULT_CONFIG = {
    "max_hop": 2,
    "max_nodes": 20,
    "decay_rate": 0.15,
    "salience_threshold": 0.2,
}

# Conflict detection verb patterns (v1 - lightweight)
CONFLICT_VERBS = [
    "sold", "no longer", "deleted", "removed", "cancelled",
    "changed", "not anymore", "canceled"
]


def score_salience(
    nodes: list[dict],
    mentioned_ids: list[str],
    turn_count: int = 0,
    kg: dict = None,
    decay_rate: float = 0.15,
) -> dict:
    """
    Compute salience scores for all nodes.

    Scoring rules:
    - Direct mention (@id in mentioned_ids): 1.0
    - Inferred (neighbor of direct mention within 1 hop): 0.6
    - Historical (accessed before, not this turn): max(0.0, prior_score - decay_rate * turns_since_access)
    - Never accessed: 0.0
    - Deprecated nodes: always 0.0

    Args:
        nodes: List of node dicts from the KG
        mentioned_ids: Node @ids directly mentioned this turn
        turn_count: How many turns since each node was last accessed
        kg: Optional KG dict for neighbor lookup (needed for inferred scoring)
        decay_rate: Salience reduction per turn for unaccessed nodes

    Returns:
        Dict mapping node_id to salience score (0.0–1.0)
    """
    scores = {}
    mentioned_set = set(mentioned_ids)

    # Build neighbor map if KG provided (for inferred scoring)
    neighbors_of_mentioned = set()
    if kg is not None:
        all_node_ids = {n.get("@id") for n in nodes if n.get("@id")}
        for node in nodes:
            node_id = node.get("@id")
            if node_id in mentioned_set:
                # Find neighbors: any field value that matches a known @id
                for key, value in node.items():
                    if key.startswith("@"):
                        continue
                    if isinstance(value, str) and value in all_node_ids:
                        neighbors_of_mentioned.add(value)
                    elif isinstance(value, list):
                        for v in value:
                            if isinstance(v, str) and v in all_node_ids:
                                neighbors_of_mentioned.add(v)

    for node in nodes:
        node_id = node.get("@id")
        if not node_id:
            continue

        # Deprecated nodes always score 0.0
        if node.get("aether:origin") == "deprecated":
            scores[node_id] = 0.0
            continue

        # Direct mention
        if node_id in mentioned_set:
            scores[node_id] = 1.0
            continue

        # Inferred (neighbor of mentioned, within 1 hop)
        if node_id in neighbors_of_mentioned:
            scores[node_id] = 0.6
            continue

        # Historical decay
        access_count = node.get("aether:access_count", 0)
        if access_count > 0:
            # Assume prior_score of 1.0, decay by turns
            prior_score = 1.0
            decayed = max(0.0, prior_score - decay_rate * turn_count)
            scores[node_id] = decayed
        else:
            # Never accessed
            scores[node_id] = 0.0

    return scores


def extract_subgraph(
    kg: dict,
    salient_ids: list[str],
    max_hop: int = 2,
    max_nodes: int = 20,
    salience_scores: dict = None,
) -> list[dict]:
    """
    Return the active subgraph - nodes reachable from salient nodes within max_hop degrees.

    Traversal rules:
    - BFS from each salient node
    - Follow any field whose value matches a known @id in the KG (treat as edge)
    - Stop at max_hop depth
    - If result exceeds max_nodes, keep highest-salience nodes
    - Never include deprecated nodes

    Args:
        kg: The knowledge graph dict
        salient_ids: Node @ids with salience above threshold
        max_hop: Max degrees of separation from salient nodes
        max_nodes: Hard cap on nodes in the active subgraph
        salience_scores: Optional dict of {node_id: score} for sorting

    Returns:
        List of node dicts, ordered by salience desc
    """
    nodes = kg_module.get_nodes(kg)

    # Build lookup maps
    node_by_id = {n.get("@id"): n for n in nodes if n.get("@id")}
    all_ids = set(node_by_id.keys())

    # Track visited nodes and their hop depth
    visited = {}  # node_id -> hop_depth
    result_ids = set()

    # BFS from each salient node
    for start_id in salient_ids:
        if start_id not in node_by_id:
            continue

        queue = deque([(start_id, 0)])

        while queue:
            current_id, depth = queue.popleft()

            # Skip if already visited at equal or lesser depth
            if current_id in visited and visited[current_id] <= depth:
                continue

            visited[current_id] = depth

            # Get the node
            node = node_by_id.get(current_id)
            if not node:
                continue

            # Skip deprecated nodes
            if node.get("aether:origin") == "deprecated":
                continue

            result_ids.add(current_id)

            # Stop expanding if at max_hop
            if depth >= max_hop:
                continue

            # Find neighbors (fields whose values match known @ids)
            for key, value in node.items():
                if key.startswith("@"):
                    continue
                neighbor_ids = []
                if isinstance(value, str) and value in all_ids:
                    neighbor_ids.append(value)
                elif isinstance(value, list):
                    for v in value:
                        if isinstance(v, str) and v in all_ids:
                            neighbor_ids.append(v)

                for neighbor_id in neighbor_ids:
                    if neighbor_id not in visited or visited[neighbor_id] > depth + 1:
                        queue.append((neighbor_id, depth + 1))

    # Collect result nodes
    result_nodes = [node_by_id[nid] for nid in result_ids if nid in node_by_id]

    # Sort by salience (descending)
    if salience_scores:
        result_nodes.sort(key=lambda n: salience_scores.get(n.get("@id"), 0), reverse=True)
    else:
        # Default: salient_ids first, then others
        salient_set = set(salient_ids)
        result_nodes.sort(key=lambda n: (0 if n.get("@id") in salient_set else 1))

    # Cap at max_nodes
    if len(result_nodes) > max_nodes:
        result_nodes = result_nodes[:max_nodes]

    return result_nodes


def build_manifest(
    capsule_id: str,
    subgraph: list[dict],
    salience_scores: dict,
    turn_id: str = "",
) -> dict:
    """
    Serialize the active subgraph as a JSON-LD Engram Manifest.

    Args:
        capsule_id: Capsule name / @id
        subgraph: Output of extract_subgraph
        salience_scores: {node_id: float} from score_salience
        turn_id: Optional turn identifier

    Returns:
        JSON-LD manifest dict
    """
    # Calculate max hop depth used
    max_hop_used = 0

    active_nodes = []
    for node in subgraph:
        node_id = node.get("@id", "")
        salience = salience_scores.get(node_id, 0.0)

        # Determine hop depth (0 for direct mentions, estimate for others)
        if salience >= 1.0:
            hop_depth = 0
        elif salience >= 0.6:
            hop_depth = 1
        else:
            hop_depth = 2

        max_hop_used = max(max_hop_used, hop_depth)

        active_nodes.append({
            "@id": node_id,
            "engram:salience": round(salience, 2),
            "engram:hop_depth": hop_depth,
        })

    manifest = {
        "@context": {
            "aether": "http://aether.dev/ontology#",
            "engram": "http://aether.dev/engram#"
        },
        "@type": "engram:Manifest",
        "engram:capsule_id": capsule_id,
        "engram:turn_id": turn_id,
        "engram:created": datetime.now().isoformat(),
        "engram:schema_version": "1.0",
        "engram:source_capsule": capsule_id,
        "engram:active_nodes": active_nodes,
        "engram:node_count": len(active_nodes),
        "engram:max_hop_used": max_hop_used,
    }

    return manifest


def save_manifest(manifest: dict, capsule_path: str | Path) -> Path:
    """
    Write engram.jsonld into the capsule folder as optional sidecar.

    Args:
        manifest: The manifest dict to save
        capsule_path: Path to the capsule folder

    Returns:
        Path to written file
    """
    capsule_path = Path(capsule_path)
    capsule_path.mkdir(parents=True, exist_ok=True)

    file_path = capsule_path / "engram.jsonld"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return file_path


def load_manifest(capsule_path: str | Path) -> dict | None:
    """
    Load engram from capsule folder.

    Args:
        capsule_path: Path to the capsule folder

    Returns:
        Manifest dict, or None if no prior engram exists (cold start)
    """
    capsule_path = Path(capsule_path)
    file_path = capsule_path / "engram.jsonld"

    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def detect_conflict(
    kg: dict,
    statement: str,
    active_node_ids: list[str],
) -> dict:
    """
    Check whether a new statement contradicts any currently active KG node.

    Conflict detection rules (v1 - lightweight):
    - Tokenize the statement
    - For each active node, check if the node's label appears AND the statement
      contains a contradicting verb pattern
    - If match: return conflict = True, conflicted_node_id = the matched node

    Args:
        kg: The knowledge graph dict
        statement: New user/agent statement to check
        active_node_ids: Currently active nodes to check against

    Returns:
        Dict with: conflict (bool), conflicted_node_id (str|None), reason (str)
    """
    nodes = kg_module.get_nodes(kg)
    node_by_id = {n.get("@id"): n for n in nodes if n.get("@id")}

    statement_lower = statement.lower()

    # Check if statement contains any conflict verbs
    has_conflict_verb = any(verb in statement_lower for verb in CONFLICT_VERBS)

    if not has_conflict_verb:
        return {
            "conflict": False,
            "conflicted_node_id": None,
            "reason": "No conflict verb patterns found"
        }

    # Check each active node
    for node_id in active_node_ids:
        node = node_by_id.get(node_id)
        if not node:
            continue

        # Get node label
        label = node.get("rdfs:label", "")
        if not label:
            # Try extracting from @id
            if "/" in node_id:
                label = node_id.split("/")[-1].replace("_", " ")

        if not label:
            continue

        label_lower = label.lower()

        # Check if label appears in statement
        if label_lower in statement_lower:
            # Find which conflict verb matched
            matched_verb = next((v for v in CONFLICT_VERBS if v in statement_lower), "")
            return {
                "conflict": True,
                "conflicted_node_id": node_id,
                "reason": f"Statement contains '{label}' with conflict verb '{matched_verb}'"
            }

    return {
        "conflict": False,
        "conflicted_node_id": None,
        "reason": "No conflicts detected"
    }


def warm_context(
    capsule_path: str | Path,
    kg: dict,
) -> dict:
    """
    Load prior engram and return the active node list ready for context injection.
    This is the session start entrypoint.

    Args:
        capsule_path: Path to the capsule folder
        kg: The knowledge graph dict

    Returns:
        Dict with:
        - warm: bool (False if no prior engram / cold start)
        - active_nodes: list[dict] (full node dicts from KG matching manifest)
        - missing_ids: list[str] (manifest IDs that no longer exist in KG)
        - manifest: dict | None (raw manifest, or None)
    """
    manifest = load_manifest(capsule_path)

    if manifest is None:
        return {
            "warm": False,
            "active_nodes": [],
            "missing_ids": [],
            "manifest": None,
        }

    nodes = kg_module.get_nodes(kg)
    node_by_id = {n.get("@id"): n for n in nodes if n.get("@id")}

    active_nodes = []
    missing_ids = []

    manifest_nodes = manifest.get("engram:active_nodes", [])
    for mn in manifest_nodes:
        node_id = mn.get("@id")
        if not node_id:
            continue

        if node_id in node_by_id:
            node = node_by_id[node_id]
            # Skip deprecated nodes
            if node.get("aether:origin") != "deprecated":
                active_nodes.append(node)
        else:
            missing_ids.append(node_id)

    return {
        "warm": True,
        "active_nodes": active_nodes,
        "missing_ids": missing_ids,
        "manifest": manifest,
    }


def commit_session(
    capsule_id: str,
    capsule_path: str | Path,
    kg: dict,
    mentioned_ids: list[str],
    turn_id: str = "",
    config: dict = None,
) -> dict:
    """
    Session end entrypoint. Run full engram pipeline and write sidecar.

    Internally calls: score_salience -> extract_subgraph -> build_manifest -> save_manifest

    Args:
        capsule_id: Capsule name / @id
        capsule_path: Path to the capsule folder
        kg: The knowledge graph dict
        mentioned_ids: Node @ids touched this session
        turn_id: Optional turn identifier
        config: Engram block from definition.json; uses defaults if None

    Returns:
        Dict with: manifest_path (str), node_count (int), manifest (dict)
    """
    # Merge config with defaults
    cfg = {**DEFAULT_CONFIG, **(config or {})}

    nodes = kg_module.get_nodes(kg)

    # Score salience
    salience_scores = score_salience(
        nodes=nodes,
        mentioned_ids=mentioned_ids,
        turn_count=0,  # Current turn
        kg=kg,
        decay_rate=cfg["decay_rate"],
    )

    # Get salient IDs (above threshold)
    salient_ids = [
        node_id for node_id, score in salience_scores.items()
        if score >= cfg["salience_threshold"]
    ]

    # Extract subgraph
    subgraph = extract_subgraph(
        kg=kg,
        salient_ids=salient_ids,
        max_hop=cfg["max_hop"],
        max_nodes=cfg["max_nodes"],
        salience_scores=salience_scores,
    )

    # Build manifest
    manifest = build_manifest(
        capsule_id=capsule_id,
        subgraph=subgraph,
        salience_scores=salience_scores,
        turn_id=turn_id,
    )

    # Save manifest
    manifest_path = save_manifest(manifest, capsule_path)

    return {
        "manifest_path": str(manifest_path),
        "node_count": len(subgraph),
        "manifest": manifest,
    }


if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 60)
    print("ENGRAM.PY SELF-TEST")
    print("=" * 60)

    # Create test KG
    test_kg = {
        "@context": {
            "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
            "aether": "http://aether.dev/ontology#"
        },
        "@graph": [
            {
                "@id": "aether:core/warren_buffett",
                "rdfs:label": "Warren Buffett",
                "aether:origin": "core",
                "aether:confidence": 1.0,
                "aether:access_count": 5,
                "aether:related": "aether:core/berkshire_hathaway",
            },
            {
                "@id": "aether:core/berkshire_hathaway",
                "rdfs:label": "Berkshire Hathaway",
                "aether:origin": "core",
                "aether:confidence": 1.0,
                "aether:access_count": 3,
            },
            {
                "@id": "aether:core/value_investing",
                "rdfs:label": "Value Investing",
                "aether:origin": "core",
                "aether:confidence": 0.9,
                "aether:access_count": 0,
            },
            {
                "@id": "aether:deprecated/old_fact",
                "rdfs:label": "Old Fact",
                "aether:origin": "deprecated",
                "aether:confidence": 0.5,
            },
            {
                "@id": "aether:core/car",
                "rdfs:label": "car",
                "aether:origin": "core",
                "aether:confidence": 1.0,
            },
        ]
    }

    nodes = kg_module.get_nodes(test_kg)
    print(f"\nTest KG has {len(nodes)} nodes")

    # Test 1: score_salience - direct mention
    print("\n[Test 1] score_salience - direct mention")
    scores = score_salience(nodes, ["aether:core/warren_buffett"], kg=test_kg)
    assert scores["aether:core/warren_buffett"] == 1.0, "Direct mention should be 1.0"
    print("  PASS: Direct mention score = 1.0")

    # Test 2: score_salience - inferred
    print("\n[Test 2] score_salience - inferred (neighbor)")
    scores = score_salience(nodes, ["aether:core/warren_buffett"], kg=test_kg)
    assert scores["aether:core/berkshire_hathaway"] == 0.6, "Inferred neighbor should be 0.6"
    print("  PASS: Inferred neighbor score = 0.6")

    # Test 3: score_salience - decay
    print("\n[Test 3] score_salience - decay")
    scores = score_salience(nodes, [], turn_count=5, kg=test_kg, decay_rate=0.15)
    # Warren Buffett has access_count=5, so historical
    expected = max(0.0, 1.0 - 0.15 * 5)  # 0.25
    assert abs(scores["aether:core/warren_buffett"] - expected) < 0.01, f"Decayed score should be ~{expected}"
    print(f"  PASS: Decayed score = {scores['aether:core/warren_buffett']:.2f}")

    # Test 4: score_salience - deprecated excluded
    print("\n[Test 4] score_salience - deprecated excluded")
    scores = score_salience(nodes, ["aether:deprecated/old_fact"], kg=test_kg)
    assert scores["aether:deprecated/old_fact"] == 0.0, "Deprecated should be 0.0"
    print("  PASS: Deprecated node score = 0.0")

    # Test 5: extract_subgraph - max_hop
    print("\n[Test 5] extract_subgraph - max_hop")
    subgraph = extract_subgraph(test_kg, ["aether:core/warren_buffett"], max_hop=1)
    subgraph_ids = {n.get("@id") for n in subgraph}
    assert "aether:core/warren_buffett" in subgraph_ids, "Salient node should be included"
    assert "aether:core/berkshire_hathaway" in subgraph_ids, "1-hop neighbor should be included"
    # value_investing is not connected, should not appear
    print(f"  PASS: Subgraph contains {len(subgraph)} nodes with 1-hop neighbors")

    # Test 6: extract_subgraph - max_nodes
    print("\n[Test 6] extract_subgraph - max_nodes")
    subgraph = extract_subgraph(test_kg, ["aether:core/warren_buffett"], max_hop=10, max_nodes=2)
    assert len(subgraph) <= 2, "Should not exceed max_nodes"
    print(f"  PASS: Subgraph capped at {len(subgraph)} nodes")

    # Test 7: build_manifest - schema
    print("\n[Test 7] build_manifest - schema")
    scores = score_salience(nodes, ["aether:core/warren_buffett"], kg=test_kg)
    subgraph = extract_subgraph(test_kg, ["aether:core/warren_buffett"])
    manifest = build_manifest("test-capsule", subgraph, scores, "t-001")
    required_fields = ["@context", "@type", "engram:capsule_id", "engram:turn_id",
                       "engram:created", "engram:schema_version", "engram:source_capsule",
                       "engram:active_nodes", "engram:node_count", "engram:max_hop_used"]
    for field in required_fields:
        assert field in manifest, f"Missing field: {field}"
    print(f"  PASS: Manifest has all {len(required_fields)} required fields")

    # Test 8: save/load roundtrip
    print("\n[Test 8] save_manifest / load_manifest roundtrip")
    with tempfile.TemporaryDirectory() as tmp:
        save_path = save_manifest(manifest, tmp)
        assert save_path.exists(), "File should be created"
        loaded = load_manifest(tmp)
        assert loaded is not None, "Should load successfully"
        assert loaded["engram:capsule_id"] == manifest["engram:capsule_id"], "Content should match"
        print(f"  PASS: Roundtrip successful")

    # Test 9: warm_context - cold start
    print("\n[Test 9] warm_context - cold start")
    with tempfile.TemporaryDirectory() as tmp:
        result = warm_context(tmp, test_kg)
        assert result["warm"] is False, "Should be cold start"
        assert result["manifest"] is None, "No manifest on cold start"
        print("  PASS: Cold start detected correctly")

    # Test 10: warm_context - warm start
    print("\n[Test 10] warm_context - warm start")
    with tempfile.TemporaryDirectory() as tmp:
        # First, commit a session to create engram
        commit_session("test-capsule", tmp, test_kg, ["aether:core/warren_buffett"])
        result = warm_context(tmp, test_kg)
        assert result["warm"] is True, "Should be warm start"
        assert len(result["active_nodes"]) > 0, "Should have active nodes"
        print(f"  PASS: Warm start with {len(result['active_nodes'])} active nodes")

    # Test 11: warm_context - missing_ids
    print("\n[Test 11] warm_context - missing_ids for stale nodes")
    with tempfile.TemporaryDirectory() as tmp:
        # Create a manifest with a node that doesn't exist in KG
        fake_manifest = {
            "@context": {"aether": "http://aether.dev/ontology#", "engram": "http://aether.dev/engram#"},
            "@type": "engram:Manifest",
            "engram:capsule_id": "test",
            "engram:active_nodes": [
                {"@id": "aether:core/warren_buffett", "engram:salience": 1.0},
                {"@id": "aether:nonexistent/node", "engram:salience": 0.8},
            ]
        }
        save_manifest(fake_manifest, tmp)
        result = warm_context(tmp, test_kg)
        assert "aether:nonexistent/node" in result["missing_ids"], "Should detect missing node"
        print(f"  PASS: Detected {len(result['missing_ids'])} missing node(s)")

    # Test 12: detect_conflict - verb pattern
    print("\n[Test 12] detect_conflict - verb pattern match")
    result = detect_conflict(test_kg, "I sold the car yesterday", ["aether:core/car"])
    assert result["conflict"] is True, "Should detect conflict"
    assert result["conflicted_node_id"] == "aether:core/car", "Should identify car node"
    print(f"  PASS: Conflict detected for 'sold the car'")

    # Test 13: detect_conflict - no false positive
    print("\n[Test 13] detect_conflict - no false positive")
    result = detect_conflict(test_kg, "I bought a car yesterday", ["aether:core/car"])
    assert result["conflict"] is False, "Should NOT detect conflict for 'bought'"
    print(f"  PASS: No false positive for 'bought a car'")

    # Test 14: commit_session writes file
    print("\n[Test 14] commit_session - writes engram.jsonld")
    with tempfile.TemporaryDirectory() as tmp:
        result = commit_session("scholar-buffett", tmp, test_kg, ["aether:core/warren_buffett"], "t-042")
        assert os.path.exists(result["manifest_path"]), "engram.jsonld should be created"
        assert result["node_count"] > 0, "Should have nodes"
        print(f"  PASS: Created engram.jsonld with {result['node_count']} nodes")

    print("\n" + "=" * 60)
    print("ALL 14 SELF-TESTS PASSED")
    print("=" * 60)
